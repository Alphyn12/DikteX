"""Geçmişi dışa aktarma (Faz 7.14).

Veri kullanıcının; uygulamadan çıkarabilmeli. İki biçim var ve ikisi ayrı işe
yarıyor:

* **Markdown** — okunmak için. Günlere göre gruplanmış, doğrudan bir nota
  yapıştırılabilir.
* **JSON** — işlenmek için. Tüm alanlar, kayıpsız.

## Ne dışa aktarılmıyor

Ses dosyaları. Kuyruktaki geçici kayıtlar dışında zaten ses saklanmıyor
(bkz. `storage/queue.py`), ve saklananlar gönderilir gönderilmez siliniyor.

## Maliyet ve gizlilik

Dışa aktarılan dosya **maskelenmemiş** ham metin içeriyor: kullanıcının kendi
verisi, kendi diskine yazılıyor ve buluta çıkmıyor. Ama dosyayı başka bir yere
taşırsa içinde ne olduğunu bilmeli — arayüzde bu yazıyor.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

log = logging.getLogger(__name__)

#: Dışa aktarmada atlanan alanlar.
#:
#: `folded` yalnız arama dizini için üretiliyor; kullanıcı için anlamı yok ve
#: her kaydı iki kez okutmak dosyayı gereksiz büyütür.
_SKIP_FIELDS = frozenset({"folded"})


def to_json(rows: list[dict[str, Any]]) -> str:
    """Kayıpsız JSON. Tüm alanlar, olduğu gibi."""
    cleaned = [
        {key: value for key, value in row.items() if key not in _SKIP_FIELDS}
        for row in rows
    ]
    payload = {
        "exportedAt": datetime.now().astimezone().isoformat(),
        "count": len(cleaned),
        "dictations": cleaned,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _local_day(iso: str) -> str:
    """UTC damgasını kullanıcının yerel gününe çevirir.

    Kayıtlar UTC saklanıyor (sıralama için doğrusu bu) ama kullanıcı gününü
    yerel saatle düşünüyor. Doğrudan ilk 10 karakteri almak, gece yarısı
    civarındaki kayıtları yanlış güne koyardı.
    """
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return iso[:10] or "bilinmiyor"


def _local_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%H:%M")
    except (ValueError, TypeError):
        return "--:--"


def to_markdown(rows: list[dict[str, Any]]) -> str:
    """Okunabilir Markdown — günlere göre gruplanmış."""
    if not rows:
        return "# DikteX geçmişi\n\n_Kayıt yok._\n"

    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_day[_local_day(str(row.get("created_at", "")))].append(row)

    lines = [
        "# DikteX geçmişi",
        "",
        f"_{len(rows)} kayıt · {datetime.now().astimezone().strftime('%d.%m.%Y %H:%M')}_",
        "",
    ]

    # Yeniden eskiye: kullanıcı en son ne yaptığını en üstte görmek istiyor.
    for day in sorted(by_day, reverse=True):
        lines += [f"## {day}", ""]
        for row in sorted(
            by_day[day], key=lambda r: str(r.get("created_at", "")), reverse=True
        ):
            app = row.get("app_name") or "—"
            time = _local_time(str(row.get("created_at", "")))
            lines.append(f"**{time}** · {app} · `{row.get('mode', 'quick')}`")
            lines.append("")
            lines.append(str(row.get("final_text", "")).strip())

            # Ham metin yalnız farklıysa: aynıysa aynı cümleyi iki kez
            # yazmak dosyayı okunmaz hâle getirir.
            raw = str(row.get("raw_text", "")).strip()
            if raw and raw != str(row.get("final_text", "")).strip():
                lines += ["", f"> _ham:_ {raw}"]
            lines.append("")

    return "\n".join(lines)
