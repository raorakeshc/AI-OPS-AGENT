import time
import threading
from typing import Dict, Any
from fastapi import Request

# Prometheus client
from prometheus_client import Counter, Histogram, make_asgi_app


# Prometheus metrics
REQUEST_COUNT = Counter("requests_total", "Total HTTP requests", ["path"])
REQUEST_LATENCY = Histogram("request_latency_ms", "Request latency in ms", ["path"])


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

        # update Prometheus metrics
        try:
            REQUEST_COUNT.labels(path=path).inc()
            REQUEST_LATENCY.labels(path=path).observe(latency_ms)
        except Exception:
            # Prometheus client should be available, but ignore failures
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
prometheus_asgi_app = make_asgi_app()
