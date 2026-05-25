import time
import threading
from typing import Dict, Any
from fastapi import Request

PROMETHEUS_ENABLED = False
try:
    from prometheus_client import Counter, Histogram, make_asgi_app

    PROMETHEUS_ENABLED = True
except ImportError:
    Counter = None  # type: ignore
    Histogram = None  # type: ignore
    make_asgi_app = None  # type: ignore


# Prometheus metrics
if PROMETHEUS_ENABLED:
    REQUEST_COUNT = Counter("requests_total", "Total HTTP requests", ["path"])
    REQUEST_LATENCY = Histogram("request_latency_ms", "Request latency in ms", ["path"])
else:
    REQUEST_COUNT = None
    REQUEST_LATENCY = None


class Metrics:
    """Thread-safe in-memory metrics store for simple monitoring (kept for compatibility)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counts: Dict[str, int] = {}
        self._total_latency_ms: Dict[str, float] = {}

    def record(self, path: str, latency_ms: float):
        # update in-memory store
        with self._lock:
            self._counts[path] = self._counts.get(path, 0) + 1
            self._total_latency_ms[path] = self._total_latency_ms.get(path, 0.0) + latency_ms

        # update Prometheus metrics if available
        if PROMETHEUS_ENABLED and REQUEST_COUNT is not None and REQUEST_LATENCY is not None:
            try:
                REQUEST_COUNT.labels(path=path).inc()
                REQUEST_LATENCY.labels(path=path).observe(latency_ms)
            except Exception:
                pass

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            data = {}
            for path, count in self._counts.items():
                total = self._total_latency_ms.get(path, 0.0)
                avg = total / count if count else 0.0
                data[path] = {"count": count, "avg_latency_ms": round(avg, 2), "total_latency_ms": round(total, 2)}
            return data


metrics = Metrics()


class MonitoringMiddleware:
    """FastAPI middleware to measure request latency and record metrics."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.time()
        await self.app(scope, receive, send)
        elapsed = (time.time() - start) * 1000.0
        path = scope.get("path", "unknown")
        metrics.record(path, elapsed)


# ASGI app for Prometheus metrics
if PROMETHEUS_ENABLED and make_asgi_app is not None:
    prometheus_asgi_app = make_asgi_app()
else:
    async def prometheus_asgi_app(scope, receive, send):
        if scope["type"] != "http":
            await send({"type": "http.disconnect"})
            return
        await send({"type": "http.response.start", "status": 404, "headers": [[b"content-type", b"text/plain"]]})
        await send({"type": "http.response.body", "body": b"Prometheus is disabled (prometheus_client is not installed)", "more_body": False})
