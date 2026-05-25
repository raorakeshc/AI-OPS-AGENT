import json
import os
from pathlib import Path
from threading import Lock
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field

try:
    from .order_store import init_db, get_order_status, upsert_order, migrate_from_json, list_orders
    from .logging_config import configure_logging
    from .monitoring import MonitoringMiddleware, metrics, prometheus_asgi_app
    from .tracing import init_tracing
except ImportError:
    from order_store import init_db, get_order_status, upsert_order, migrate_from_json, list_orders
    from logging_config import configure_logging
    from monitoring import MonitoringMiddleware, metrics, prometheus_asgi_app
    from tracing import init_tracing

_db_conn = None


APP_TITLE = "Orders Service"
APP_VERSION = "1.0.0"
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "orders.json"

app = FastAPI(title=APP_TITLE, version=APP_VERSION)
_data_lock = Lock()

# configure logging and tracing early
configure_logging()
# initialize tracing (OTLP/Jaeger/console fallback)
tracer = init_tracing(service_name="orders-service")
# auto-instrument FastAPI and requests if available
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    FastAPIInstrumentor.instrument_app(app)
    RequestsInstrumentor().instrument()
except Exception:
    pass

# add monitoring middleware (ASGI-style)
app.add_middleware(MonitoringMiddleware)
# mount Prometheus metrics ASGI app at /metrics
app.mount("/metrics", prometheus_asgi_app)


class OrderRecord(BaseModel):
    order_id: str = Field(..., min_length=1, max_length=10)
    status: str = Field(..., min_length=1)


class OrderStatusResponse(BaseModel):
    order_id: str
    status: str


class MessageResponse(BaseModel):
    message: str


def _load_orders() -> Dict[str, str]:
    # legacy helper kept for compatibility; prefer SQLite methods
    if not DATA_PATH.exists():
        return {}
    with DATA_PATH.open("r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def _save_orders(orders: Dict[str, str]) -> None:
    # Legacy JSON persistence kept as a secondary store for small exports.
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("w", encoding="utf-8") as file_obj:
        json.dump(orders, file_obj, indent=2)


def _normalize_order_id(order_id: str) -> str:
    return str(order_id).strip()


def _validate_bearer(authorization: Optional[str]) -> None:
    required_token = os.getenv("ORDER_API_BEARER_TOKEN", "").strip()
    if not required_token:
        return

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    provided_token = authorization.replace("Bearer ", "", 1).strip()
    if provided_token != required_token:
        raise HTTPException(status_code=401, detail="Invalid bearer token")


@app.on_event("startup")
def startup_initialize_seed_data() -> None:
    global _db_conn
    # Initialize SQLite DB and migrate any existing JSON seed data
    _db_conn = init_db()
    existing = list_orders(_db_conn)
    if not existing:
        migrated = migrate_from_json(_db_conn, DATA_PATH)
        if migrated:
            # keep JSON file for human-readability, but DB is now primary
            pass
        else:
            # seed with defaults if nothing to migrate
            upsert_order(_db_conn, "123", "Shipped")
            upsert_order(_db_conn, "456", "In Transit")
            upsert_order(_db_conn, "789", "Delivered")


@app.get("/health", response_model=MessageResponse)
def health() -> MessageResponse:
    return MessageResponse(message="orders-api healthy")




@app.get("/orders/{order_id}", response_model=OrderStatusResponse)
def get_order_by_path(
    order_id: str,
    authorization: Optional[str] = Header(default=None),
) -> OrderStatusResponse:
    _validate_bearer(authorization)
    normalized_order_id = _normalize_order_id(order_id)
    with _data_lock:
        status = get_order_status(_db_conn, normalized_order_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Order {normalized_order_id} not found")

    return OrderStatusResponse(order_id=normalized_order_id, status=status)


@app.get("/orders/status", response_model=OrderStatusResponse)
def get_order_by_query(
    order_id: str,
    authorization: Optional[str] = Header(default=None),
) -> OrderStatusResponse:
    _validate_bearer(authorization)
    normalized_order_id = _normalize_order_id(order_id)
    with _data_lock:
        status = get_order_status(_db_conn, normalized_order_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Order {normalized_order_id} not found")

    return OrderStatusResponse(order_id=normalized_order_id, status=status)


@app.post("/orders", response_model=OrderStatusResponse)
def create_or_upsert_order(
    payload: OrderRecord,
    authorization: Optional[str] = Header(default=None),
) -> OrderStatusResponse:
    _validate_bearer(authorization)
    normalized_order_id = _normalize_order_id(payload.order_id)
    with _data_lock:
        upsert_order(_db_conn, normalized_order_id, payload.status)
        # also keep JSON export updated for humans/tools
        _save_orders(list_orders(_db_conn))

    return OrderStatusResponse(order_id=normalized_order_id, status=payload.status)


@app.patch("/orders/{order_id}", response_model=OrderStatusResponse)
def update_order_status(
    order_id: str,
    payload: OrderRecord,
    authorization: Optional[str] = Header(default=None),
) -> OrderStatusResponse:
    _validate_bearer(authorization)
    normalized_path_order_id = _normalize_order_id(order_id)
    normalized_payload_order_id = _normalize_order_id(payload.order_id)

    if normalized_path_order_id != normalized_payload_order_id:
        raise HTTPException(status_code=400, detail="Path order_id and payload order_id must match")

    with _data_lock:
        existing = get_order_status(_db_conn, normalized_path_order_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Order {normalized_path_order_id} not found")
        upsert_order(_db_conn, normalized_path_order_id, payload.status)
        _save_orders(list_orders(_db_conn))

    return OrderStatusResponse(order_id=normalized_path_order_id, status=payload.status)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("orders_api:app", host="0.0.0.0", port=8081, reload=False)
