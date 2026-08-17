"""Sesle düzeltme istemi (Faz 7.15).

Pre-flight'ta çıktıyı beğenmeyen kullanıcı, fareyle düzeltmek yerine
"daha kısa yaz" ya da "resmi olsun" diyebiliyor. Sesli bir uygulamada sonucu
klavyeyle düzeltmek tuhaftı.

## En büyük risk: yeniden yazma

Model, düzeltme talimatını "yeni bir metin üret" diye anlarsa kullanıcının
cümlesi kaybolur. İstem bu yüzden iki şeyi ayrı ayrı sınırlıyor:

* Metin **verilen metindir**, yeni içerik üretilmeyecek.
* Talimat **yalnız o metne** uygulanacak; talimatın kendisi çıktıya girmeyecek.

İkincisi somut bir tuzak: kullanıcı "daha kısa yaz" dediğinde model bunu
metne ekleyip "Daha kısa yazıyorum: ..." diyebiliyor.
"""

from __future__ import annotations

from omnivoice_engine.llm.base import Prompt
from omnivoice_engine.pipeline.prompts import DELIMITER

_SYSTEM = f"""\
EN ÖNEMLİ KURAL — BUNU HİÇBİR KOŞULDA ÇİĞNEME:
Sana iki şey veriliyor: bir METİN ve o metne uygulanacak bir TALİMAT. \
İkisi de {DELIMITER} işaretleri arasında. Görevin, metni talimata göre \
yeniden yazmak.

KESİN SINIRLAR:
- Metne YENİ BİLGİ EKLEME. Talimat "uzat" dese bile var olan içeriği \
genişlet, uydurma ekleme.
- Talimatın kendisini çıktıya YAZMA. "Daha kısa yazıyorum:" gibi bir giriş \
cümlesi kurma.
- Metnin dilini DEĞİŞTİRME. Talimat Türkçe olsa bile metin İngilizceyse \
İngilizce kalır.
- Açıklama, yorum, soru ekleme. Yalnız yeniden yazılmış metni ver.
- Metni tırnak içine alma, kod bloğuna sarma.
- Talimat metinle ilgisizse ya da anlaşılmıyorsa metni OLDUĞU GİBİ geri ver.
"""


def refine_prompt(text: str, instruction: str, *, language: str | None = None) -> Prompt:
    """Var olan metni sesli bir talimata göre yeniden yazar."""
    # Sınırlayıcı ikisinin de içinde geçerse sınırı bozmasın.
    safe_text = text.replace(DELIMITER, "")
    safe_instruction = instruction.replace(DELIMITER, "")

    system = _SYSTEM
    if language:
        system += (
            f"\nMETNİN DİLİ: {language}. Çıktıyı da bu dilde ver.\n"
        )

    user = "\n".join(
        [
            "METİN:",
            DELIMITER,
            safe_text,
            DELIMITER,
            "",
            "TALİMAT:",
            DELIMITER,
            safe_instruction,
            DELIMITER,
        ]
    )
    # Sıcaklık düşük: düzeltme deterministik olmalı, aynı talimat aynı sonucu
    # vermeli. Yaratıcılık burada kullanıcının istemediği bir şey.
    return Prompt(system=system, user=user, temperature=0.2, max_tokens=2000)
