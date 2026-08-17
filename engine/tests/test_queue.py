"""Başarısız dikte kuyruğu (Faz 7.2).

Bu modül kullanıcının sesini diske yazıyor — uygulamanın geri kalanının
bilinçli olarak yapmadığı bir şey. O yüzden testlerin ağırlığı **silmenin
gerçekten çalıştığında**: gönderilen kayıt kalmamalı, yaşlı kayıt kalmamalı,
sayı sınırı aşılmamalı. Sızan bir kayıt burada sessiz bir gizlilik borcudur.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from omnivoice_engine.storage.queue import MAX_AGE_DAYS, MAX_ITEMS, ClipQueue


@pytest.fixture
def queue(tmp_path: Path) -> ClipQueue:
    return ClipQueue(tmp_path / "queue")


def add(queue: ClipQueue, *, error: str = "bağlantı yok", mode: str = "quick"):
    return queue.add(
        audio=b"sahte-ses-baytlari",
        suffix=".flac",
        mode=mode,
        duration_seconds=3.4,
        error=error,
    )


class TestEkleme:
    def test_kayit_diske_yazilir(self, queue: ClipQueue) -> None:
        item = add(queue)
        assert item is not None
        assert item.audio_path.read_bytes() == b"sahte-ses-baytlari"
        assert item.error == "bağlantı yok"
        assert item.attempts == 0

    def test_listede_gorunur(self, queue: ClipQueue) -> None:
        add(queue)
        add(queue)
        assert len(queue.items()) == 2

    def test_en_eski_basta(self, queue: ClipQueue) -> None:
        first = add(queue, error="ilk")
        time.sleep(0.01)
        add(queue, error="ikinci")
        assert queue.items()[0].item_id == first.item_id

    def test_yazilamazsa_none_doner(self, tmp_path: Path) -> None:
        """Kuyruk hatası dikteyi büsbütün çökertmemeli."""
        # Klasör yerine dosya koyarak `mkdir`i başarısız kılıyoruz.
        blocked = tmp_path / "engel"
        blocked.write_text("dosya", encoding="utf-8")
        assert add(ClipQueue(blocked)) is None


class TestSilme:
    def test_gonderilen_kayit_silinir(self, queue: ClipQueue) -> None:
        """Kuyrukta kalan ses, tutulmaması gereken bir gizlilik borcudur."""
        item = add(queue)
        queue.remove(item)
        assert not item.audio_path.exists()
        assert not item.meta_path.exists()
        assert queue.items() == []

    def test_kimlikle_silme(self, queue: ClipQueue) -> None:
        item = add(queue)
        assert queue.remove_by_id(item.item_id)
        assert not queue.remove_by_id(item.item_id)

    def test_hepsini_temizle(self, queue: ClipQueue) -> None:
        add(queue)
        add(queue)
        assert queue.clear() == 2
        assert queue.items() == []
        # Ses dosyaları da gitmeli, yalnız üstveri değil.
        assert list(queue.directory.glob("*.flac")) == []


class TestBakim:
    def test_yasli_kayit_dusurulur(self, queue: ClipQueue) -> None:
        item = add(queue)
        meta = json.loads(item.meta_path.read_text(encoding="utf-8"))
        meta["createdAt"] = time.time() - (MAX_AGE_DAYS + 1) * 86400
        item.meta_path.write_text(json.dumps(meta), encoding="utf-8")

        assert queue.prune() == 1
        assert queue.items() == []
        assert not item.audio_path.exists()

    def test_sayi_siniri_asilmaz(self, queue: ClipQueue) -> None:
        for index in range(MAX_ITEMS + 5):
            add(queue, error=f"hata-{index}")
            time.sleep(0.002)  # kimlikler farklı olsun
        assert len(queue.items()) == MAX_ITEMS

    def test_sinirda_en_eski_gider(self, queue: ClipQueue) -> None:
        first = add(queue, error="en-eski")
        time.sleep(0.002)
        for index in range(MAX_ITEMS):
            add(queue, error=f"hata-{index}")
            time.sleep(0.002)
        assert all(item.item_id != first.item_id for item in queue.items())


class TestBozukVeri:
    def test_sesi_olmayan_ustveri_temizlenir(self, queue: ClipQueue) -> None:
        item = add(queue)
        item.audio_path.unlink()
        assert queue.items() == []
        # Artık üstveri de kalmamalı.
        assert not item.meta_path.exists()

    def test_bozuk_json_yok_sayilir(self, queue: ClipQueue) -> None:
        queue.directory.mkdir(parents=True, exist_ok=True)
        (queue.directory / "bozuk.json").write_text("{ bozuk", encoding="utf-8")
        assert queue.items() == []

    def test_bos_kuyruk(self, tmp_path: Path) -> None:
        assert ClipQueue(tmp_path / "yok").items() == []


class TestDeneme:
    def test_sayac_artar(self, queue: ClipQueue) -> None:
        item = add(queue)
        queue.mark_attempt(item)
        queue.mark_attempt(item)
        assert queue.items()[0].attempts == 2
