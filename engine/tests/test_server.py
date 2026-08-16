"""Sunucunun sözleşmesini doğrular.

Kritik nokta: kabuk motoru yalnız `ready` mesajını aldığında bağlandı sayar.
Bu el sıkışma bozulursa uygulama sonsuza kadar "başlatılıyor" durumunda kalır,
üstelik hiçbir şey hata vermez — bu yüzden testle korunuyor.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from omnivoice_engine import __version__
from omnivoice_engine.server.app import create_app


def test_health_reports_version() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


def test_health_never_leaks_key_values() -> None:
    """Sağlık uç noktası sağlayıcı adı verir, anahtar değeri vermez."""
    with TestClient(create_app()) as client:
        body = client.get("/health").json()

    for provider in body["providers"]:
        assert provider in {"groq", "openrouter", "gemini"}
        # Anahtar önekleri gövdede hiç geçmemeli.
        assert "gsk_" not in str(body)
        assert "sk-or-" not in str(body)


def test_websocket_sends_ready_on_connect() -> None:
    """Kabuk bağlanır bağlanmaz `ready` almalı — el sıkışmanın kalbi."""
    with TestClient(create_app()) as client, client.websocket_connect("/ws") as ws:
        message = ws.receive_json()

    assert message["type"] == "ready"
    assert message["version"] == __version__


def test_websocket_answers_ping() -> None:
    with TestClient(create_app()) as client, client.websocket_connect("/ws") as ws:
        ws.receive_json()  # ready
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


def test_unknown_message_does_not_close_connection() -> None:
    """Bilinmeyen kare bağlantıyı düşürmemeli; ileri sürüm uyumluluğu için."""
    with TestClient(create_app()) as client, client.websocket_connect("/ws") as ws:
        ws.receive_json()  # ready
        ws.send_json({"type": "gelecekteki-komut"})
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}
