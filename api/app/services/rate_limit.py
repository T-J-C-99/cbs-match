import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request


@dataclass
class RateDecision:
    allowed: bool
    retry_after_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> RateDecision:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            dq = self._events[key]
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= limit:
                retry_after = max(1, int(dq[0] + window_seconds - now))
                return RateDecision(allowed=False, retry_after_seconds=retry_after)
            dq.append(now)
            return RateDecision(allowed=True, retry_after_seconds=0)


limiter = InMemoryRateLimiter()


def _client_identifier(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "").strip()
    if xff:
        return xff.split(",")[0].strip()
    auth = request.headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return f"token:{auth[7:23]}"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def rate_limit_dependency(route_key: str, limit: int, window_seconds: int):
    def _dep(request: Request) -> None:
        ident = _client_identifier(request)
        key = f"{route_key}:{ident}"
        decision = limiter.check(key, limit=limit, window_seconds=window_seconds)
        if not decision.allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Retry in {decision.retry_after_seconds}s",
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )

    return Depends(_dep)
