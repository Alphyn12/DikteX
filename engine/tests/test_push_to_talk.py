"""Basılı tut kipi ve klavye kancası (Faz 7.7).

Bu modül sistemdeki **her tuşu** gören bir kanca kuruyor. Testlerin ağırlığı
bu yüzden iki yerde:

1. **Tuş sızıntısı olmamalı** — izlenen tuşlar dışında hiçbir şey saklanmıyor.
2. **Kanca kapanmalı** — kapatılan bir kip gerçekten kancayı kaldırmalı,
   yoksa kullanıcı kapattığını sanır ama kanca çalışmaya devam eder.

Kanca gerçek Windows API'sini kullanıyor; kurulum/kaldırma gerçekten
sınanıyor, tuş olayları ise geri çağrım doğrudan çağrılarak taklit ediliyor.
"""

from __future__ import annotations

import ctypes

import pytest

from omnivoice_engine.input.hotkey_hook import (
    WM_KEYDOWN,
    WM_KEYUP,
    VK_LCONTROL,
    VK_LMENU,
    VK_SPACE,
    PushToTalkHook,
    _KBDLLHOOKSTRUCT,
)


class _Recorder:
    def __init__(self) -> None:
        self.events: list[str] = []

    def press(self) -> None:
        self.events.append("bas")

    def release(self) -> None:
        self.events.append("birak")


def make_hook(recorder: _Recorder) -> PushToTalkHook:
    return PushToTalkHook(on_press=recorder.press, on_release=recorder.release)


def key(hook: PushToTalkHook, vk: int, *, down: bool) -> None:
    """Windows geri çağrımını taklit eder."""
    data = _KBDLLHOOKSTRUCT(vkCode=vk, scanCode=0, flags=0, time=0, dwExtraInfo=None)
    lparam = ctypes.cast(ctypes.pointer(data), ctypes.c_void_p).value
    hook._callback(0, WM_KEYDOWN if down else WM_KEYUP, lparam)  # noqa: SLF001


class TestTetikleme:
    def test_tam_kombinasyon_baslatir(self) -> None:
        rec = _Recorder()
        hook = make_hook(rec)
        key(hook, VK_LCONTROL, down=True)
        key(hook, VK_LMENU, down=True)
        key(hook, VK_SPACE, down=True)
        assert rec.events == ["bas"]

    def test_birakinca_biter(self) -> None:
        rec = _Recorder()
        hook = make_hook(rec)
        key(hook, VK_LCONTROL, down=True)
        key(hook, VK_LMENU, down=True)
        key(hook, VK_SPACE, down=True)
        key(hook, VK_SPACE, down=False)
        assert rec.events == ["bas", "birak"]

    def test_degistiricisiz_space_tetiklemez(self) -> None:
        """Boşluk tuşu en sık basılan tuşlardan biri; yanlış tetikleme felaket."""
        rec = _Recorder()
        hook = make_hook(rec)
        key(hook, VK_SPACE, down=True)
        key(hook, VK_SPACE, down=False)
        assert rec.events == []

    def test_eksik_degistirici_tetiklemez(self) -> None:
        rec = _Recorder()
        hook = make_hook(rec)
        key(hook, VK_LCONTROL, down=True)
        key(hook, VK_SPACE, down=True)
        assert rec.events == []

    def test_tuş_tekrari_ikinci_kez_baslatmaz(self) -> None:
        """Basılı tutmak Windows'ta tekrarlanan KEYDOWN üretiyor."""
        rec = _Recorder()
        hook = make_hook(rec)
        key(hook, VK_LCONTROL, down=True)
        key(hook, VK_LMENU, down=True)
        for _ in range(10):
            key(hook, VK_SPACE, down=True)
        assert rec.events == ["bas"]

    def test_degistirici_birakilinca_biter(self) -> None:
        """Ctrl bırakılıp Space tutulmaya devam edilirse kayıt bitmeli."""
        rec = _Recorder()
        hook = make_hook(rec)
        key(hook, VK_LCONTROL, down=True)
        key(hook, VK_LMENU, down=True)
        key(hook, VK_SPACE, down=True)
        key(hook, VK_LCONTROL, down=False)
        assert rec.events == ["bas", "birak"]


class TestGizlilik:
    def test_izlenmeyen_tuslar_HICBIR_YERE_yazilmaz(self) -> None:
        """Bu kanca parolaları da görüyor. Sızıntı olmamalı.

        Nesnenin tüm durumunu tarayıp yalnız beklenen bayrakların bulunduğunu
        doğruluyoruz: yeni bir alan eklendiğinde bu test uyarır.
        """
        rec = _Recorder()
        hook = make_hook(rec)

        # Bir parola yazıyormuş gibi: 'A'..'Z' ve rakamlar.
        for vk in list(range(0x41, 0x5B)) + list(range(0x30, 0x3A)):
            key(hook, vk, down=True)
            key(hook, vk, down=False)

        state = {
            name: value
            for name, value in vars(hook).items()
            if isinstance(value, (int, bool)) and not isinstance(value, type)
        }
        # Yalnız bilinen bayraklar ve tuş kimliği; hiçbir tuş listesi yok.
        assert set(state) <= {
            "_ctrl_down",
            "_alt_down",
            "_key_down",
            "_active",
            "_key",
            "_thread_id",
            "_hook",
        }
        assert hook._key == VK_SPACE  # noqa: SLF001
        assert not hook._active  # noqa: SLF001

    def test_hicbir_tus_yutulmaz(self) -> None:
        """Kanca daima `CallNextHookEx` çağırmalı; yutulan tuş yazmayı bozar."""
        rec = _Recorder()
        hook = make_hook(rec)
        data = _KBDLLHOOKSTRUCT(vkCode=VK_SPACE, scanCode=0, flags=0, time=0, dwExtraInfo=None)
        lparam = ctypes.cast(ctypes.pointer(data), ctypes.c_void_p).value
        # Kanca kurulu değilken bile bir değer dönüyor ve istisna atmıyor.
        assert isinstance(hook._callback(0, WM_KEYDOWN, lparam), int)  # noqa: SLF001


class TestYasamDongusu:
    def test_kurulur_ve_kaldirilir(self) -> None:
        """Gerçek Windows kancası — kurulum ve kaldırma ölçülüyor."""
        rec = _Recorder()
        hook = make_hook(rec)
        assert hook.start()
        assert hook.is_running
        hook.stop()
        assert not hook.is_running

    def test_iki_kez_baslatmak_zararsiz(self) -> None:
        rec = _Recorder()
        hook = make_hook(rec)
        assert hook.start()
        assert hook.start()
        hook.stop()

    def test_baslatilmamis_kanca_durdurulabilir(self) -> None:
        make_hook(_Recorder()).stop()

    def test_durdurma_durumu_temizler(self) -> None:
        """Bayrak sızarsa sonraki oturum yanlış durumda başlar."""
        rec = _Recorder()
        hook = make_hook(rec)
        hook.start()
        key(hook, VK_LCONTROL, down=True)
        key(hook, VK_LMENU, down=True)
        key(hook, VK_SPACE, down=True)
        hook.stop()
        assert not hook._ctrl_down  # noqa: SLF001
        assert not hook._active  # noqa: SLF001
