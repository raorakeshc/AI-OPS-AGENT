import os
import re
import json
import logging
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from langchain_core.tools import tool


@tool
def get_order_status(order_id: str) -> str:
    """Get shipping status for an order id. Safeguards enforced."""
    # Clean order_id: keep only digits
    digits_match = re.search(r"(\d+)", str(order_id))
    clean_id = digits_match.group(1) if digits_match else str(order_id).strip()

    if len(clean_id) > 10:
        return "Error: Invalid tool usage. order_id digits are too long. It must be 10 characters or fewer."

    api_url = os.getenv("ORDER_STATUS_API_URL", "").strip()
    timeout_raw = os.getenv("ORDER_STATUS_TIMEOUT", "8").strip()

    if not api_url:
        return "Order status service is not configured. Set ORDER_STATUS_API_URL."

    try:
        timeout_seconds = float(timeout_raw)
        if timeout_seconds <= 0:
            timeout_seconds = 8.0
    except ValueError:
        timeout_seconds = 8.0

    if "{order_id}" in api_url:
        final_url = api_url.replace("{order_id}", clean_id)
    else:
        connector = "&" if "?" in api_url else "?"
        final_url = f"{api_url}{connector}{urlencode({'order_id': clean_id})}"

    headers = {"Accept": "application/json"}
    request = Request(final_url, headers=headers, method="GET")

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            status_text = body.strip()
            return status_text if status_text else f"Order {order_id} status unavailable."

        if isinstance(payload, dict):
            if payload.get("status"):
                return str(payload["status"])
            data_section = payload.get("data")
            if isinstance(data_section, dict) and data_section.get("status"):
                return str(data_section["status"])
            order_section = payload.get("order")
            if isinstance(order_section, dict) and order_section.get("status"):
                return str(order_section["status"])
            if payload.get("message"):
                return str(payload.get("message"))

        return f"Order {order_id} status not found in service response."

    except HTTPError as http_error:
        if http_error.code == 404:
            return f"Order {order_id} not found."
        logging.error(f"Order status HTTP error for order_id={order_id}: {http_error}")
        return "Order status service returned an error. Please try again shortly."
    except URLError as url_error:
        logging.error(f"Order status network error for order_id={order_id}: {url_error}")
        return "Unable to reach order status service right now. Please try again shortly."
    except Exception as error:
        logging.error(f"Unexpected order status error for order_id={order_id}: {error}")
        return "Order status lookup failed due to a temporary issue."
