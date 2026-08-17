"""Sessizlikte otomatik durdurma (Faz 7.3).

Bu özelliğin iki başarısızlık biçimi var ve ikisi de kaydı mahvediyor:

* **Erken durmak** — kullanıcı kısayola basıp bir an düşünürse ya da cümle
  ortasında nefes alırsa kayıt yarıda biter. Söylediği şey eksik gider.
* **Hiç durmamak** — özellik ölüdür, kullanıcı klavyeye dönmek zorunda kalır.

Testlerin ağırlığı birincide, çünkü sessizce yanlış sonuç üreten o.

**Not:** İlk yazımda bu testler async seviye döngüsünü sürüyordu ve ikisi
**boş yere geçiyordu** — `asyncio.sleep(0)` gerçek zamanı ilerletmediği için
döngü hiç dönmemişti. Karar mantığı bu yüzden saf bir sınıfa (`SilenceWatcher`)
ayrıldı; artık zamanı testin kendisi ilerletiyor.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from omnivoice_engine.pipeline import dictation as dictation_module
from omnivoice_engine.pipeline.dictation import (
    DEFAULT_AUTO_STOP_SECONDS,
    DictationPipeline,
    DictationState,
    SilenceWatcher,
)

#: Gerçek seviye döngüsünün adımı.
TICK = 0.05
LOUD = 0.05
QUIET = 0.0005


def feed(watcher: SilenceWatcher, levels: list[float]) -> int | None:
    """Seviyeleri sırayla verir. Durdurma kararının kaçıncı adımda geldiğini döner."""
    for index, level in enumerate(levels):
        if watcher.observe(level, TICK):
            return index
    return None


class TestErkenDurmama:
    def test_konusma_duyulmadan_ASLA_durmaz(self) -> None:
        """En önemli test.

        Kullanıcı kısayola basıp düşünüyorsa kayıt daha başlamadan bitmemeli.
        Sayaç ancak konuşma duyulduktan SONRA işlemeye başlıyor.
        """
        watcher = SilenceWatcher(threshold_seconds=0.5)
        # 30 saniyelik kesintisiz sessizlik — kullanıcı henüz konuşmadı.
        assert feed(watcher, [0.0] * 600) is None
        assert watcher.silent_for == 0.0

    @pytest.mark.parametrize("duraklama", [0.5, 1.0, 1.5])
    def test_cumle_ici_duraklama_durdurmaz(self, duraklama: float) -> None:
        """İnsanlar cümle ortasında nefes alır ve virgülde durur."""
        watcher = SilenceWatcher(threshold_seconds=DEFAULT_AUTO_STOP_SECONDS)
        sessiz_adim = int(duraklama / TICK)
        levels = [LOUD] * 10 + [QUIET] * sessiz_adim + [LOUD] * 20
        assert feed(watcher, levels) is None

    def test_konusma_sayaci_sifirlar(self) -> None:
        """Duraklamadan sonra konuşulursa sayaç baştan başlamalı."""
        watcher = SilenceWatcher(threshold_seconds=1.0)
        feed(watcher, [LOUD] * 5 + [QUIET] * 15)  # 0.75 sn sessizlik
        assert watcher.silent_for > 0
        watcher.observe(LOUD, TICK)
        assert watcher.silent_for == 0.0

    def test_oda_gurultusu_konusma_sayilmaz(self) -> None:
        """Eşik altındaki sürekli uğultu kaydı sonsuza kadar açık tutmamalı."""
        watcher = SilenceWatcher(threshold_seconds=0.5)
        # Konuş, sonra fısıltı seviyesinin altında sabit gürültü.
        stopped_at = feed(watcher, [LOUD] * 5 + [0.004] * 100)
        assert stopped_at is not None


class TestDurdurma:
    def test_konusma_sonrasi_sessizlik_durdurur(self) -> None:
        watcher = SilenceWatcher(threshold_seconds=0.5)
        stopped_at = feed(watcher, [LOUD] * 10 + [QUIET] * 100)
        assert stopped_at is not None
        # 10 konuşma adımı + 0.5 sn / 0.05 = 10 sessiz adım.
        assert stopped_at == 19

    def test_esik_suresine_uyar(self) -> None:
        for esik in (0.5, 1.0, 2.0):
            watcher = SilenceWatcher(threshold_seconds=esik)
            stopped_at = feed(watcher, [LOUD] + [QUIET] * 200)
            assert stopped_at is not None
            gecen = (stopped_at) * TICK
            assert abs(gecen - esik) < TICK * 1.5, f"eşik {esik}: {gecen}"

    def test_kapaliyken_hic_durdurmaz(self) -> None:
        watcher = SilenceWatcher(threshold_seconds=0.0)
        assert not watcher.enabled
        assert feed(watcher, [LOUD] * 10 + [QUIET] * 1000) is None


class TestAyar:
    def _pipeline(self) -> DictationPipeline:
        async def emit(_message: dict[str, Any]) -> None:
            return None

        return DictationPipeline(
            mic=None,  # type: ignore[arg-type]
            stt=None,  # type: ignore[arg-type]
            llm=None,  # type: ignore[arg-type]
            db=None,  # type: ignore[arg-type]
            emit=emit,
        )

    def test_negatif_deger_kapatir(self) -> None:
        pipeline = self._pipeline()
        pipeline.set_auto_stop_seconds(-5)
        assert pipeline.auto_stop_seconds == 0.0

    def test_ust_sinir_uygulanir(self) -> None:
        """Çok uzun bir eşik, kapatmakla aynı şey — ama kullanıcı açık sanır."""
        pipeline = self._pipeline()
        pipeline.set_auto_stop_seconds(600)
        assert pipeline.auto_stop_seconds == 10.0

    def test_varsayilan_makul_araliginda(self) -> None:
        """Değer konuşma ritmine göre seçildi; kazayla değişmesin."""
        assert 1.0 <= DEFAULT_AUTO_STOP_SECONDS <= 2.5


class TestDonguEntegrasyonu:
    """Saf mantık bağlandı mı — döngü gerçekten `stop()` çağırıyor mu?"""

    @pytest.mark.asyncio
    async def test_dongu_stop_cagirir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Gerçek zamanı beklememek için adımı çok küçültüyoruz.
        monkeypatch.setattr(dictation_module, "_LEVEL_INTERVAL", 0.001)

        class _Mic:
            def __init__(self) -> None:
                self.calls = 0

            @property
            def level(self) -> float:
                self.calls += 1
                return LOUD if self.calls <= 3 else QUIET

            @property
            def recorded_seconds(self) -> float:
                return self.calls * 0.001

        stopped = asyncio.Event()

        async def emit(_message: dict[str, Any]) -> None:
            return None

        pipeline = DictationPipeline(
            mic=_Mic(),  # type: ignore[arg-type]
            stt=None,  # type: ignore[arg-type]
            llm=None,  # type: ignore[arg-type]
            db=None,  # type: ignore[arg-type]
            emit=emit,
            # Eşik 0.02 sn: 0.001'lik adımlarla 20 tur.
            auto_stop_seconds=0.02,
        )
        pipeline.state = DictationState.LISTENING

        async def fake_stop() -> None:
            pipeline.state = DictationState.PROCESSING
            stopped.set()

        pipeline.stop = fake_stop  # type: ignore[method-assign]

        task = asyncio.create_task(pipeline._stream_level())
        await asyncio.wait_for(stopped.wait(), timeout=5.0)
        task.cancel()
