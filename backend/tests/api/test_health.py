"""GET /api/v1/health behavior."""

from __future__ import annotations


def test_health_returns_200(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200


def test_health_does_not_require_auth(client):
    # No cookie, no header — still 200.
    r = client.get("/api/v1/health")
    assert r.status_code == 200


def test_health_returns_data_status_ok(client):
    body = client.get("/api/v1/health").json()
    assert body["data"] == {"status": "ok"}
    assert body["error"] is None


def test_health_returns_etag_header(client):
    r = client.get("/api/v1/health")
    # ETag is set on public reads.
    assert "etag" in {k.lower() for k in r.headers.keys()}


def test_health_supports_if_none_match_304(client):
    r1 = client.get("/api/v1/health")
    etag = r1.headers["etag"]
    r2 = client.get("/api/v1/health", headers={"If-None-Match": etag})
    assert r2.status_code == 304
