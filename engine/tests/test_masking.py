"""Hassas veri maskeleme.

İki hata sınıfı var ve ikisi de sessiz:

* **Kaçırmak** — bir anahtar buluta gider, kullanıcı korunduğunu sanır.
* **Yanlış pozitif** — normal bir sayı maskelenir, kullanıcının metni bozulur.

Bu dosyadaki testlerin çoğu ikinci sınıfa ait, çünkü yanlış pozitif hem daha
sık hem de fark edilmesi daha zor.
"""

from __future__ import annotations

import pytest

from omnivoice_engine.privacy.masking import (
    PiiKind,
    is_valid_card,
    is_valid_iban,
    is_valid_national_id,
    mask,
    mask_all,
)

# Aşağıdaki değerlerin hepsi **sentetik**: algoritmayı sağlayan ama kimseye
# ait olmayan test verileri.
VALID_TCKN = "10000000146"       # sağlama toplamı tutan sentetik numara
VALID_CARD = "4111111111111111"  # Visa test kartı, herkese açık
VALID_IBAN = "TR330006100519786457841326"  # standart IBAN örneği


class TestSaglamaToplamlari:
    def test_gecerli_tckn(self) -> None:
        assert is_valid_national_id(VALID_TCKN)

    @pytest.mark.parametrize(
        "value",
        [
            "12345678901",  # sağlama tutmuyor
            "01234567890",  # sıfırla başlıyor
            "1234567890",   # 10 hane
            "abcdefghijk",
            "",
        ],
    )
    def test_gecersiz_tckn(self, value: str) -> None:
        assert not is_valid_national_id(value)

    def test_gecerli_kart(self) -> None:
        assert is_valid_card(VALID_CARD)

    @pytest.mark.parametrize("value", ["4111111111111112", "1234", "abcd"])
    def test_gecersiz_kart(self, value: str) -> None:
        assert not is_valid_card(value)

    def test_gecerli_iban(self) -> None:
        assert is_valid_iban(VALID_IBAN)

    def test_gecersiz_iban(self) -> None:
        assert not is_valid_iban("TR330006100519786457841327")


class TestYanlisPozitif:
    """Maskelenmemesi gerekenler. Bunları bozmak metni sessizce bozar."""

    @pytest.mark.parametrize(
        "metin",
        [
            "toplantı saat 14:30'da başlıyor",
            "sipariş numarası 12345678901 olarak kaydedildi",  # 11 hane, sağlama tutmuyor
            "telefonum 05551234567",  # 11 hane, sağlama tutmuyor
            "port 8756 üzerinden bağlanıyor",
            "2026 yılında 1500 kullanıcıya ulaştık",
            "commit hash'i a94f2b1c8e3d5f7a9b2c4d6e8f0a1b3c5d7e9f01",
            "uuid: 550e8400-e29b-41d4-a716-446655440000",
            "versiyon 3.5.1 yayınlandı",
        ],
    )
    def test_normal_metin_bozulmaz(self, metin: str) -> None:
        result = mask(metin)
        assert result.text == metin
        assert result.masked_count == 0

    def test_kod_degiskeni_maskelenmiyor(self) -> None:
        """`sk-` benzeri kısa dizeler anahtar değildir."""
        metin = "sk-test değişkenini kullan"
        assert mask(metin).text == metin


class TestTespit:
    def test_tckn_maskelenir(self) -> None:
        result = mask(f"kimlik numaram {VALID_TCKN}")
        assert VALID_TCKN not in result.text
        assert result.kinds == (PiiKind.NATIONAL_ID,)

    def test_kart_bosluklu_maskelenir(self) -> None:
        """Kullanıcı dikte ederken numarayı gruplayarak söylüyor."""
        result = mask("kartım 4111 1111 1111 1111 numarası")
        assert "4111" not in result.text
        assert result.kinds == (PiiKind.CARD,)

    def test_iban_maskelenir(self) -> None:
        result = mask(f"IBAN {VALID_IBAN} hesabına gönder")
        assert VALID_IBAN not in result.text

    @pytest.mark.parametrize(
        "anahtar",
        [
            "sk-abcdefghijklmnopqrstuvwxyz123456",
            "sk-ant-api03-abcdefghijklmnopqrstuvwxyz",
            # Gerçek biçim: `AIza` + 35 karakter = 39.
            "AIzaSyA01234567890123456789012345678",
            # Uzunluk değişse de yakalanmalı.
            "AIzaSyA0123456789012345678901234567890123",
            "gsk_abcdefghijklmnopqrstuvwxyz1234",
            "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
            "xoxb-1234567890-abcdefghijklm",
            "AKIAIOSFODNN7EXAMPLE",
        ],
    )
    def test_saglayici_anahtarlari(self, anahtar: str) -> None:
        result = mask(f"anahtar {anahtar} kullanılıyor")
        assert anahtar not in result.text
        assert result.kinds == (PiiKind.API_KEY,)

    def test_env_satiri(self) -> None:
        """Git diff'inde en sık karşımıza çıkacak biçim."""
        result = mask('OPENROUTER_API_KEY="degerli-gizli-anahtar-123"')
        assert "degerli-gizli-anahtar-123" not in result.text
        # Anahtar ADI kalmalı: model bağlamı görsün.
        assert "OPENROUTER_API_KEY" in result.text

    def test_ozel_anahtar_blogu(self) -> None:
        blok = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA1234\n"
            "-----END RSA PRIVATE KEY-----"
        )
        result = mask(f"dosyada\n{blok}\nvar")
        assert "MIIEowIBAAKCAQEA1234" not in result.text
        assert result.kinds == (PiiKind.PRIVATE_KEY,)


class TestGeriCevirme:
    def test_yer_tutucu_geri_donuyor(self) -> None:
        """Maskeleme tek yönlü olsaydı kullanıcının metni bozulurdu."""
        metin = f"kartım {VALID_CARD}"
        result = mask(metin)
        assert result.unmask(result.text) == metin

    def test_model_yer_tutucuyu_yeniden_yazsa_da_calisir(self) -> None:
        """Modeller `[PII-1]` yerine `[PII - 1]` yazabiliyor."""
        result = mask(f"kimlik {VALID_TCKN}")
        assert VALID_TCKN in result.unmask("Kimlik: [PII - 1]")

    def test_uydurma_yer_tutucu_oldugu_gibi_kalir(self) -> None:
        """Bilinmeyen numaraya yanlış bir değer yazmaktansa dokunmamak iyi."""
        result = mask(f"kimlik {VALID_TCKN}")
        assert result.unmask("[PII-99] geldi") == "[PII-99] geldi"

    def test_ayni_deger_ayni_yer_tutucu(self) -> None:
        result = mask(f"{VALID_TCKN} ve yine {VALID_TCKN}")
        assert result.masked_count == 1
        assert result.text.count("[PII-1]") == 2


class TestCakisma:
    def test_uzun_eslesme_kazanir(self) -> None:
        """Kart numarasının içinde geçerli bir TCKN dizisi bulunabiliyor.

        Kısa olanı seçmek numaranın bir kısmını açıkta bırakırdı — bu,
        hiç maskelememekten beter: kullanıcı korunduğunu sanır.
        """
        result = mask(f"kart {VALID_CARD}")
        assert VALID_CARD not in result.text
        assert result.masked_count == 1


class TestCokluParca:
    def test_ortak_harita(self) -> None:
        """İstem birden çok parçadan kuruluyor; harita ortak olmalı."""
        parts, result = mask_all(f"kimlik {VALID_TCKN}", f"yine {VALID_TCKN}", None)
        assert VALID_TCKN not in (parts[0] or "")
        assert VALID_TCKN not in (parts[1] or "")
        assert parts[2] is None
        # Aynı değer, tek yer tutucu.
        assert result.masked_count == 1

    def test_bos_ve_none_korunur(self) -> None:
        parts, result = mask_all("", None, "temiz metin")
        assert parts == ["", None, "temiz metin"]
        assert result.masked_count == 0
