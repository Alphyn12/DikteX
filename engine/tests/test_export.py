"""Geçmişi dışa aktarma (Faz 7.14).

Dışa aktarma "veri kullanıcının" sözünün somut hâli. İki şey kritik:

1. **Hiçbir kayıt kaybolmamalı.** Eksik dışa aktarım, kullanıcının yedeğinde
   olduğunu sandığı bir şeyin aslında olmaması demek.
2. **Zaman dilimi doğru olmalı.** Kayıtlar UTC saklanıyor; günlere ayırırken
   doğrudan ilk 10 karakteri almak gece yarısı civarındaki kayıtları yanlış
   güne koyardı — bu hata Faz 2'de bir kez yapılmıştı.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from omnivoice_engine.storage.export import to_json, to_markdown


def kayit(**degisiklikler: object) -> dict[str, object]:
    temel: dict[str, object] = {
        "id": 1,
        "created_at": "2026-08-17T09:30:00+00:00",
        "raw_text": "ham metin",
        "final_text": "işlenmiş metin",
        "mode": "quick",
        "app_name": "VS Code",
        "language": "tr",
        "total_ms": 1200,
        "cost_usd": 0.0001,
        "folded": "ham metin islenmis metin",
    }
    temel.update(degisiklikler)
    return temel


class TestJson:
    def test_tum_kayitlar_var(self) -> None:
        rows = [kayit(id=index) for index in range(5)]
        payload = json.loads(to_json(rows))
        assert payload["count"] == 5
        assert len(payload["dictations"]) == 5

    def test_alanlar_korunur(self) -> None:
        payload = json.loads(to_json([kayit()]))
        item = payload["dictations"][0]
        assert item["final_text"] == "işlenmiş metin"
        assert item["cost_usd"] == 0.0001

    def test_ARAMA_ALANI_atlanir(self) -> None:
        """`folded` yalnız arama dizini için; kullanıcı için anlamı yok."""
        payload = json.loads(to_json([kayit()]))
        assert "folded" not in payload["dictations"][0]

    def test_turkce_karakterler_korunur(self) -> None:
        """`ensure_ascii=False` olmasaydı 'ş' yerine \\u015f yazardı."""
        çıktı = to_json([kayit(final_text="şığüöç")])
        assert "şığüöç" in çıktı

    def test_bos_liste(self) -> None:
        payload = json.loads(to_json([]))
        assert payload["count"] == 0


class TestMarkdown:
    def test_tum_metinler_var(self) -> None:
        rows = [kayit(id=i, final_text=f"benzersiz metin {i}") for i in range(5)]
        çıktı = to_markdown(rows)
        for index in range(5):
            assert f"benzersiz metin {index}" in çıktı

    def test_gunlere_gruplanir(self) -> None:
        rows = [
            kayit(id=1, created_at="2026-08-17T09:00:00+00:00"),
            kayit(id=2, created_at="2026-08-16T09:00:00+00:00"),
        ]
        çıktı = to_markdown(rows)
        assert "## 2026-08-17" in çıktı
        assert "## 2026-08-16" in çıktı

    def test_yeniden_eskiye_siralanir(self) -> None:
        """Kullanıcı en son ne yaptığını en üstte görmek istiyor."""
        rows = [
            kayit(id=1, created_at="2026-08-15T09:00:00+00:00"),
            kayit(id=2, created_at="2026-08-17T09:00:00+00:00"),
        ]
        çıktı = to_markdown(rows)
        assert çıktı.index("## 2026-08-17") < çıktı.index("## 2026-08-15")

    def test_ayni_ham_metin_tekrarlanmaz(self) -> None:
        çıktı = to_markdown([kayit(raw_text="aynı", final_text="aynı")])
        assert çıktı.count("aynı") == 1

    def test_farkli_ham_metin_gosterilir(self) -> None:
        çıktı = to_markdown([kayit(raw_text="ham hâli", final_text="temiz hâli")])
        assert "ham hâli" in çıktı
        assert "temiz hâli" in çıktı

    def test_bos_liste_cokertmez(self) -> None:
        assert "Kayıt yok" in to_markdown([])

    def test_bozuk_tarih_cokertmez(self) -> None:
        çıktı = to_markdown([kayit(created_at="bozuk-tarih")])
        assert "işlenmiş metin" in çıktı


class TestZamanDilimi:
    def test_YEREL_gune_gore_gruplanir(self) -> None:
        """Kayıtlar UTC saklanıyor ama kullanıcı gününü yerel saatle düşünüyor.

        Doğrudan ilk 10 karakteri almak gece yarısı civarındaki kayıtları
        yanlış güne koyardı — bu hata Faz 2'de bir kez yapılmıştı.
        """
        # Yerel saatle bugünün 00:30'unu UTC'ye çeviriyoruz.
        yerel = datetime.now().astimezone().replace(
            hour=0, minute=30, second=0, microsecond=0
        )
        utc_damga = yerel.astimezone(UTC).isoformat()

        çıktı = to_markdown([kayit(created_at=utc_damga)])
        assert f"## {yerel.strftime('%Y-%m-%d')}" in çıktı

    def test_gece_yarisi_gecisi(self) -> None:
        yerel = datetime.now().astimezone().replace(
            hour=23, minute=45, second=0, microsecond=0
        )
        çıktı = to_markdown([kayit(created_at=yerel.astimezone(UTC).isoformat())])
        assert f"## {yerel.strftime('%Y-%m-%d')}" in çıktı

    @pytest.mark.parametrize("gun_farki", [0, 1, 7, 30])
    def test_farkli_gunler_ayrisir(self, gun_farki: int) -> None:
        temel = datetime.now().astimezone().replace(hour=12, minute=0, second=0)
        eski = temel - timedelta(days=gun_farki)
        rows = [
            kayit(id=1, created_at=temel.astimezone(UTC).isoformat()),
            kayit(id=2, created_at=eski.astimezone(UTC).isoformat()),
        ]
        çıktı = to_markdown(rows)
        beklenen = 1 if gun_farki == 0 else 2
        assert çıktı.count("## ") == beklenen
