"""Git deposu okuma (Properties V.5).

Kullanıcı terminalde veya IDE'de "commit mesajı yaz" dediğinde, ne
değiştirdiğini anlatmasını beklemek yerine `git diff`'i kendimiz okuruz.
Böylece mesaj gerçek değişikliği anlatır, kullanıcının hatırladığını değil.

Depo, dikte başladığındaki **aktif pencerenin** çalışma dizininden bulunur:
terminalse o dizin, IDE ise pencere başlığındaki proje. Bulunamazsa mod yine
çalışır — kullanıcının anlattığından mesaj üretir.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

#: Git komutları için üst sınır. Devasa bir depoda `git diff` uzun sürebilir.
_TIMEOUT_SECONDS = 10

#: İsteme sığdırılacak diff büyüklüğü. Tamamı gönderilirse hem pahalı olur
#: hem de model ayrıntıda boğulup özü kaçırır.
MAX_DIFF_CHARS = 12_000

#: Üretilmiş dosyalar mesajı anlamsız biçimde şişirir; diff'ten çıkarılır.
_NOISY_PATHS = (
    ":(exclude)package-lock.json",
    ":(exclude)pnpm-lock.yaml",
    ":(exclude)yarn.lock",
    ":(exclude)poetry.lock",
    ":(exclude)*.min.js",
    ":(exclude)*.min.css",
    ":(exclude)dist/*",
    ":(exclude)build/*",
)


@dataclass(frozen=True, slots=True)
class GitContext:
    """Bir depodaki bekleyen değişiklikler."""

    root: Path
    branch: str
    #: `git diff` çıktısı (kırpılmış olabilir).
    diff: str
    #: Değişen dosya adları.
    files: list[str]
    insertions: int
    deletions: int
    #: Değişiklikler `git add` ile hazırlanmış mı, yoksa çalışma dizininde mi?
    staged: bool
    truncated: bool

    @property
    def is_empty(self) -> bool:
        return not self.diff.strip()

    def summary_line(self) -> str:
        return (
            f"{len(self.files)} dosya · +{self.insertions} −{self.deletions} · "
            f"dal: {self.branch}"
        )


def _run(args: list[str], cwd: Path) -> str | None:
    """Git komutunu çalıştırır. Başarısızsa `None`."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT_SECONDS,
            check=False,
            # Konsol penceresi açılmasın.
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        log.debug("git %s başarısız", " ".join(args), exc_info=True)
        return None

    if result.returncode != 0:
        return None
    return result.stdout


def find_repository(start: Path) -> Path | None:
    """Verilen dizinden yukarı doğru git deposu arar."""
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def read_context(directory: Path) -> GitContext | None:
    """Depodaki bekleyen değişiklikleri okur.

    Önce `git add` ile hazırlanmış değişikliklere bakar; kullanıcı bilinçli
    olarak bir şeyleri hazırladıysa commit etmek istediği odur. Hazırlanmış
    bir şey yoksa çalışma dizinindeki değişikliklere düşer.
    """
    root = find_repository(directory)
    if root is None:
        return None

    branch = (_run(["rev-parse", "--abbrev-ref", "HEAD"], root) or "").strip() or "HEAD"

    for staged in (True, False):
        scope = ["--cached"] if staged else []
        stat = _run(["diff", *scope, "--numstat", "--", ".", *_NOISY_PATHS], root)
        if not stat or not stat.strip():
            continue

        files: list[str] = []
        insertions = 0
        deletions = 0
        for line in stat.strip().splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            added, removed, name = parts
            files.append(name)
            # İkili dosyalarda git "-" yazar.
            insertions += int(added) if added.isdigit() else 0
            deletions += int(removed) if removed.isdigit() else 0

        diff = _run(["diff", *scope, "--", ".", *_NOISY_PATHS], root) or ""
        truncated = len(diff) > MAX_DIFF_CHARS
        if truncated:
            diff = diff[:MAX_DIFF_CHARS]

        return GitContext(
            root=root,
            branch=branch,
            diff=diff,
            files=files,
            insertions=insertions,
            deletions=deletions,
            staged=staged,
            truncated=truncated,
        )

    return None


def read_context_for_window(window_title: str, process_name: str) -> GitContext | None:
    """Aktif pencereden depo bulmayı dener.

    IDE'ler pencere başlığında genelde proje adını taşır ama tam yolu
    taşımazlar; bu yüzden bulabildiğimiz yolları sırayla deniyoruz. Hiçbiri
    tutmazsa `None` döner ve mod diff'siz çalışır.
    """
    del process_name  # Şimdilik kullanılmıyor; imza ileride genişleyecek.

    candidates: list[Path] = []

    # Başlıkta tam yol geçiyor olabilir: "C:\proje\dosya.py — Editör"
    for token in window_title.replace("—", " ").replace("–", " ").split():
        if ":" in token and "\\" in token:
            path = Path(token.strip("\"'"))
            candidates.append(path if path.is_dir() else path.parent)

    candidates.append(Path.cwd())

    for candidate in candidates:
        try:
            if not candidate.exists():
                continue
        except OSError:
            continue
        context = read_context(candidate)
        if context is not None:
            return context

    return None
