"""Response envelope contract test.

Every endpoint MUST return `{"data": ..., "error": null}` on success
or `{"data": null, "error": {"code", "message"}}` on failure. The
enforcement is two-layered: route handlers return `Envelope[T]`
directly, and the `EnvelopeMiddleware` wraps any raw dict response.
"""

from __future__ import annotations


def test_health_returns_envelope(client):
    """`/api/v1/health` returns the canonical envelope."""
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) >= {"data", "error"}
    assert body["error"] is None
    assert body["data"] == {"status": "ok"}


def test_unknown_route_returns_envelope(client):
    """A 404 from FastAPI's default router is wrapped in the envelope."""
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert body["data"] is None
    assert body["error"] is not None
    assert body["error"]["code"] in ("not_found", "validation_error")
    assert isinstance(body["error"]["message"], str)


def test_login_with_no_credentials_returns_envelope(client):
    r = client.post("/api/v1/auth/login", json={})
    assert r.status_code == 422
    body = r.json()
    assert body["data"] is None
    assert body["error"] is not None
    assert body["error"]["code"] == "validation_error"


def test_login_with_wrong_credentials_returns_envelope(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@emalro.com.ar", "password": "wrong"},
    )
    assert r.status_code == 401
    body = r.json()
    assert body["data"] is None
    assert body["error"]["code"] == "invalid_credentials"
