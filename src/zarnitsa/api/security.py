"""Authentication and rate limiting for the council endpoints.

Why this exists: a single `/v1/council` call fans out to five model completions at
6–8k max_tokens each. Deployed publicly with no auth, the endpoint is a way for
anyone who finds the URL to spend the operator's model budget in a loop. These two
dependencies are the minimum needed to stop that.

The rate limiter is in-process. That is correct for a single-instance deployment
(Render's free tier) and wrong the moment there is more than one worker — each
process would keep its own counter and the effective limit would multiply. If this
ever scales out, move the window to Redis.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from hmac import compare_digest

from fastapi import Header, HTTPException, Request, status

from zarnitsa.config import settings

log = logging.getLogger(__name__)

_AUTH_WARNING_EMITTED = False


def _warn_once_if_open() -> None:
    global _AUTH_WARNING_EMITTED
    if not _AUTH_WARNING_EMITTED:
        _AUTH_WARNING_EMITTED = True
        log.warning(
            "ZARNITSA_API_KEYS is unset — council endpoints are UNAUTHENTICATED. "
            "Every request spends model budget. Set ZARNITSA_API_KEYS before exposing "
            "this service to a network."
        )


def _client_identity(request: Request, api_key: str | None) -> str:
    """Identity for rate-limiting purposes: the API key if present, else client IP."""
    if api_key:
        # Don't key the limiter on the raw secret.
        return f"key:{hash(api_key)}"
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        # Render and most proxies prepend the real client; take the first hop.
        return f"ip:{forwarded.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def _extract_key(x_api_key: str | None, authorization: str | None) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> str | None:
    """Reject requests without a valid shared secret.

    No-ops when ZARNITSA_API_KEYS is unset so local development doesn't need a key,
    but logs a warning once per process so an accidentally-public deploy is visible
    in the logs rather than silent.
    """
    allowed = settings.api_key_set
    presented = _extract_key(x_api_key, authorization)

    if not allowed:
        _warn_once_if_open()
        request.state.api_key = presented
        return presented

    if not presented:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing API key: send X-API-Key or Authorization: Bearer <key>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # compare_digest against every configured key so the response time doesn't leak
    # which prefix matched.
    if not any(compare_digest(presented, k) for k in allowed):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid API key",
        )

    request.state.api_key = presented
    return presented


class SlidingWindowLimiter:
    """Fixed-count sliding window, keyed by caller identity."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, identity: str) -> tuple[bool, int, float]:
        """Record a hit. Returns (allowed, remaining, retry_after_seconds)."""
        now = time.monotonic()
        bucket = self._hits[identity]
        cutoff = now - self.window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= self.limit:
            retry_after = max(0.0, bucket[0] + self.window - now)
            return False, 0, retry_after

        bucket.append(now)
        return True, self.limit - len(bucket), 0.0

    def reset(self) -> None:
        self._hits.clear()


_limiter = SlidingWindowLimiter(
    limit=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)


async def rate_limit(request: Request) -> None:
    """Cap council deliberations per identity per window.

    Depends on `require_api_key` having run first so `request.state.api_key` is set;
    route declarations list them in that order.
    """
    if _limiter.limit <= 0:
        return  # 0 or negative disables the limiter
    identity = _client_identity(request, getattr(request.state, "api_key", None))
    allowed, remaining, retry_after = _limiter.check(identity)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"rate limit exceeded: {_limiter.limit} deliberations per "
                f"{_limiter.window}s"
            ),
            headers={"Retry-After": str(int(retry_after) + 1)},
        )
    request.state.rate_limit_remaining = remaining
