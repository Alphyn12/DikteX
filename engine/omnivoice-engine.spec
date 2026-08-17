# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller tanımı — motoru tek klasörlük bir uygulamaya paketler (Faz 6.6).

## Neden `--onedir`, `--onefile` değil

Tek dosya sürümü her açılışta kendini geçici bir klasöre açıyor. Bu iki
sorun üretiyor: açılış birkaç saniye gecikiyor (dikte aracının en kötü
özelliği) ve bazı antivirüsler "kendini açan çalıştırılabilir" davranışını
şüpheli buluyor. Klasör sürümü hem hızlı açılıyor hem de electron-builder
zaten her şeyi tek bir kuruluma koyuyor.

## Elle eklenen yerel dosyalar

PyInstaller Python `import`larını takip ediyor ama **çalışma anında yol
üzerinden açılan** dosyaları göremiyor. Aşağıdakiler ölçülerek bulundu; her
biri eksik olduğunda motor sessizce ya da anlaşılmaz bir hatayla düşüyor:

* `_sounddevice_data` — PortAudio DLL'i. Yoksa mikrofon hiç açılmıyor.
* `_soundfile_data`   — libsndfile. Yoksa FLAC kodlaması çöküyor.
* `soundcard/*.py.h`  — cffi başlıkları, **çalışma anında okunuyor**.
                        Yoksa sistem sesi kaydı (toplantı) düşüyor.
* `pywin32_system32`  — pythoncom/pywintypes. Yoksa COM ve pano çalışmıyor.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

SITE = Path(SPECPATH) / ".venv" / "Lib" / "site-packages"

datas = [
    # PortAudio ve libsndfile: `sounddevice`/`soundfile` bunları paket
    # klasöründen dosya yolu ile açıyor, import etmiyor.
    (str(SITE / "_sounddevice_data"), "_sounddevice_data"),
    (str(SITE / "_soundfile_data"), "_soundfile_data"),
]

# `soundcard` cffi başlıklarını çalışma anında okuyor. `collect_data_files`
# `.h` uzantısını varsayılan olarak almıyor; açıkça istiyoruz.
datas += collect_data_files("soundcard", includes=["*.h", "*.py.h"])

binaries = [
    (str(SITE / "pywin32_system32" / "pythoncom313.dll"), "."),
    (str(SITE / "pywin32_system32" / "pywintypes313.dll"), "."),
]

hiddenimports = [
    # `keyring` arka ucunu giriş noktalarıyla (entry points) buluyor;
    # PyInstaller bu dolaylı yolu takip etmiyor. Yoksa API kasası açılmıyor.
    "keyring.backends.Windows",
    "keyring.backends.null",
    # pywin32'nin klasik kaçağı: `win32timezone` yalnız çalışma anında
    # import ediliyor.
    "win32timezone",
    # Uvicorn protokol uygulamalarını dize adıyla yüklüyor.
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
]
# `soundcard` platforma göre alt modül seçiyor; hepsini alıyoruz.
hiddenimports += collect_submodules("soundcard")

a = Analysis(
    ["omnivoice_engine/__main__.py"],
    pathex=[SPECPATH],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Motor arayüz çizmiyor; bu paketler yalnız boyut ekler.
    excludes=["tkinter", "matplotlib", "PIL", "pytest", "IPython"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="omnivoice-engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Konsol AÇIK: motorun günlükleri Electron tarafından stdout üzerinden
    # okunuyor (bkz. `electron/main/engine.ts`). Pencere `windowsHide` ile
    # gizleniyor, yani kullanıcı siyah bir kutu görmüyor ama günlükler akmaya
    # devam ediyor.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="omnivoice-engine",
)
