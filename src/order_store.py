import json
import sqlite3
from pathlib import Path
from typing import Dict, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "orders.db"


def _ensure_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            status TEXT NOT NULL
        )
        """
    )
    conn.commit()


def init_db(db_path: Optional[Path] = None) -> sqlite3.Connection:
    db_file = DB_PATH if db_path is None else Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file), check_same_thread=False)
    _ensure_db(conn)
    return conn


def get_order_status(conn: sqlite3.Connection, order_id: str) -> Optional[str]:
    cur = conn.execute("SELECT status FROM orders WHERE order_id = ?", (order_id,))
    row = cur.fetchone()
    return row[0] if row else None


def upsert_order(conn: sqlite3.Connection, order_id: str, status: str) -> None:
    conn.execute(
        "INSERT INTO orders(order_id, status) VALUES(?, ?) ON CONFLICT(order_id) DO UPDATE SET status=excluded.status",
        (order_id, status),
    )
    conn.commit()


def list_orders(conn: sqlite3.Connection) -> Dict[str, str]:
    cur = conn.execute("SELECT order_id, status FROM orders")
    return {row[0]: row[1] for row in cur.fetchall()}


def migrate_from_json(conn: sqlite3.Connection, json_path: Path) -> int:
    if not Path(json_path).exists():
        return 0
    with open(json_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        return 0
    count = 0
    for k, v in data.items():
        upsert_order(conn, str(k), str(v))
        count += 1
    return count
