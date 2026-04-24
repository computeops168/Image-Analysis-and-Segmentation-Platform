from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.observability import record_rate_limited


@dataclass(frozen=True)
class RateLimitRule:
    method: str
    path: str
    limit_per_minute: int


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rules: list[RateLimitRule]):
        super().__init__(app)
        self._rules = tuple(rules)
        self._events: dict[tuple[str, str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _resolve_client_ip(self, request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for", "").strip()
        if forwarded_for:
            first = forwarded_for.split(",")[0].strip()
            if first:
                return first
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    def _matching_rule(self, request: Request) -> RateLimitRule | None:
        method = request.method.upper()
        path = request.url.path
        for rule in self._rules:
            if rule.method == method and rule.path == path:
                return rule
        return None

    async def dispatch(self, request: Request, call_next):
        rule = self._matching_rule(request)
        if rule is None:
            return await call_next(request)

        now = time.time()
        window_start = now - 60
        client_ip = self._resolve_client_ip(request)
        key = (client_ip, rule.method, rule.path)
        with self._lock:
            events = self._events[key]
            while events and events[0] < window_start:
                events.popleft()
            if len(events) >= rule.limit_per_minute:
                retry_after = max(1, int(events[0] + 60 - now))
                record_rate_limited(rule.method, rule.path)
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded"},
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)
        return await call_next(request)
