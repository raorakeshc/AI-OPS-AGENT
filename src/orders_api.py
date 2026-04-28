import json
import os
from pathlib import Path
from threading import Lock
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field


APP_TITLE = "Orders Service"
APP_VERSION = "1.0.0"
DATA_PATH = Path("data/orders.json")

app = FastAPI(title=APP_TITLE, version=APP_VERSION)
_data_lock = Lock()


class OrderRecord(BaseModel):
    order_id: str = Field(..., min_length=1, max_length=10)
    status: str = Field(..., min_length=1)


class OrderStatusResponse(BaseModel):
    order_id: str
    status: str


class MessageResponse(BaseModel):
    message: str


def _load_orders() -> Dict[str, str]:
    if not DATA_PATH.exists():
        return {}
    with DATA_PATH.open("r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def _save_orders(orders: Dict[str, str]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("w", encoding="utf-8") as file_obj:
        json.dump(orders, file_obj, indent=2)


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
    if DATA_PATH.exists():
        return
    _save_orders({
        "123": "Shipped",
        "456": "In Transit",
        "789": "Delivered",
    })


@app.get("/health", response_model=MessageResponse)
def health() -> MessageResponse:
    return MessageResponse(message="orders-api healthy")


@app.get("/orders/{order_id}", response_model=OrderStatusResponse)
def get_order_by_path(
    order_id: str,
    authorization: Optional[str] = Header(default=None),
) -> OrderStatusResponse:
    _validate_bearer(authorization)

    with _data_lock:
        orders = _load_orders()

    status = orders.get(order_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    return OrderStatusResponse(order_id=order_id, status=status)


@app.get("/orders/status", response_model=OrderStatusResponse)
def get_order_by_query(
    order_id: str,
    authorization: Optional[str] = Header(default=None),
) -> OrderStatusResponse:
    _validate_bearer(authorization)

    with _data_lock:
        orders = _load_orders()

    status = orders.get(order_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    return OrderStatusResponse(order_id=order_id, status=status)


@app.post("/orders", response_model=OrderStatusResponse)
def create_or_upsert_order(
    payload: OrderRecord,
    authorization: Optional[str] = Header(default=None),
) -> OrderStatusResponse:
    _validate_bearer(authorization)

    with _data_lock:
        orders = _load_orders()
        orders[payload.order_id] = payload.status
        _save_orders(orders)

    return OrderStatusResponse(order_id=payload.order_id, status=payload.status)


@app.patch("/orders/{order_id}", response_model=OrderStatusResponse)
def update_order_status(
    order_id: str,
    payload: OrderRecord,
    authorization: Optional[str] = Header(default=None),
) -> OrderStatusResponse:
    _validate_bearer(authorization)

    if order_id != payload.order_id:
        raise HTTPException(status_code=400, detail="Path order_id and payload order_id must match")

    with _data_lock:
        orders = _load_orders()
        if order_id not in orders:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
        orders[order_id] = payload.status
        _save_orders(orders)

    return OrderStatusResponse(order_id=order_id, status=payload.status)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("orders_api:app", host="0.0.0.0", port=8081, reload=False)
