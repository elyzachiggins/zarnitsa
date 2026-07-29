"""Auth and rate-limit tests.

The endpoints these protect each spend five model completions per call, so a
regression here is a billing incident rather than a bug.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from zarnitsa.api import security
from zarnitsa.api.security import SlidingWindowLimiter, rate_limit, require_api_key


@pytest.fixture
def app_with_guard(monkeypatch) -> FastAPI:
    app = FastAPI()

    from fastapi import Depends

    @app.get("/guarded", dependencies=[Depends(require_api_key), Depends(rate_limit)])
    async def guarded() -> dict[str, bool]:
        return {"ok": True}

    return app


@pytest.fixture(autouse=True)
def reset_limiter():
    security._limiter.reset()
    yield
    security._limiter.reset()


def _set_keys(monkeypatch, value: str) -> None:
    monkeypatch.setattr(security.settings, "api_keys", value)


# --- auth ------------------------------------------------------------------


def test_open_when_no_keys_configured(app_with_guard, monkeypatch) -> None:
    _set_keys(monkeypatch, "")
    assert TestClient(app_with_guard).get("/guarded").status_code == 200


def test_rejects_missing_key(app_with_guard, monkeypatch) -> None:
    _set_keys(monkeypatch, "secret1")
    assert TestClient(app_with_guard).get("/guarded").status_code == 401


def test_rejects_wrong_key(app_with_guard, monkeypatch) -> None:
    _set_keys(monkeypatch, "secret1")
    r = TestClient(app_with_guard).get("/guarded", headers={"X-API-Key": "nope"})
    assert r.status_code == 403


def test_accepts_x_api_key(app_with_guard, monkeypatch) -> None:
    _set_keys(monkeypatch, "secret1")
    r = TestClient(app_with_guard).get("/guarded", headers={"X-API-Key": "secret1"})
    assert r.status_code == 200


def test_accepts_bearer_token(app_with_guard, monkeypatch) -> None:
    _set_keys(monkeypatch, "secret1")
    r = TestClient(app_with_guard).get(
        "/guarded", headers={"Authorization": "Bearer secret1"}
    )
    assert r.status_code == 200


def test_accepts_any_configured_key(app_with_guard, monkeypatch) -> None:
    _set_keys(monkeypatch, "a-key, b-key , c-key")
    for key in ("a-key", "b-key", "c-key"):
        r = TestClient(app_with_guard).get("/guarded", headers={"X-API-Key": key})
        assert r.status_code == 200, key


# --- rate limiting ---------------------------------------------------------


def test_limiter_allows_up_to_limit() -> None:
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60)
    assert [limiter.check("id")[0] for _ in range(3)] == [True, True, True]


def test_limiter_blocks_past_limit() -> None:
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60)
    limiter.check("id")
    limiter.check("id")
    allowed, remaining, retry_after = limiter.check("id")
    assert not allowed
    assert remaining == 0
    assert retry_after > 0


def test_limiter_buckets_are_per_identity() -> None:
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
    assert limiter.check("alice")[0]
    assert limiter.check("bob")[0], "bob must not be blocked by alice's usage"


def test_limiter_window_expires(monkeypatch) -> None:
    clock = {"t": 1000.0}
    monkeypatch.setattr(security.time, "monotonic", lambda: clock["t"])
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
    assert limiter.check("id")[0]
    assert not limiter.check("id")[0]
    clock["t"] += 61
    assert limiter.check("id")[0], "window should have rolled over"


def test_endpoint_returns_429_with_retry_after(app_with_guard, monkeypatch) -> None:
    _set_keys(monkeypatch, "")
    monkeypatch.setattr(security._limiter, "limit", 2)
    client = TestClient(app_with_guard)
    assert client.get("/guarded").status_code == 200
    assert client.get("/guarded").status_code == 200
    blocked = client.get("/guarded")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_zero_limit_disables_limiter(app_with_guard, monkeypatch) -> None:
    _set_keys(monkeypatch, "")
    monkeypatch.setattr(security._limiter, "limit", 0)
    client = TestClient(app_with_guard)
    for _ in range(10):
        assert client.get("/guarded").status_code == 200
