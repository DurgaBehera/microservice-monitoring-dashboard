"""Order Service - a simple FastAPI microservice instrumented with Prometheus metrics."""

import asyncio
import random
import time

from fastapi import FastAPI, HTTPException, Query, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

SERVICE_NAME = "order-service"

app = FastAPI(title="Order Service", version="1.0.0")

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["service", "method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["service", "method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


# Business metric (feature #9)
ORDERS_CREATED = Counter("orders_created_total", "Total number of orders created")


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        elapsed = time.perf_counter() - start
        # Use the route template (e.g. /orders/{order_id}) rather than the raw path
        # so metric label cardinality stays bounded.
        route = request.scope.get("route")
        endpoint = getattr(route, "path", None) or "unmatched"
        REQUEST_COUNT.labels(SERVICE_NAME, request.method, endpoint, str(status_code)).inc()
        REQUEST_LATENCY.labels(SERVICE_NAME, request.method, endpoint).observe(elapsed)


# ---------------------------------------------------------------------------
# Dummy data
# ---------------------------------------------------------------------------
ORDERS = [
    {"id": 101, "user_id": 1, "items": [{"sku": "KB-001", "name": "Mechanical Keyboard", "qty": 1}], "total": 4999.00, "currency": "INR", "status": "delivered"},
    {"id": 102, "user_id": 2, "items": [{"sku": "MS-014", "name": "Wireless Mouse", "qty": 2}], "total": 1798.00, "currency": "INR", "status": "shipped"},
    {"id": 103, "user_id": 2, "items": [{"sku": "HD-220", "name": "USB-C Hub", "qty": 1}], "total": 2499.00, "currency": "INR", "status": "processing"},
    {"id": 104, "user_id": 4, "items": [{"sku": "MN-270", "name": "27-inch Monitor", "qty": 1}], "total": 18999.00, "currency": "INR", "status": "pending"},
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {"service": SERVICE_NAME, "docs": "/docs", "metrics": "/metrics", "health": "/health"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/orders")
def list_orders():
    return {"count": len(ORDERS), "orders": ORDERS}


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    for item in ORDERS:
        if item["id"] == order_id:
            return item
    raise HTTPException(status_code=404, detail="Order not found")


class OrderCreate(BaseModel):
    user_id: int
    total: float = Field(gt=0)


@app.post("/orders", status_code=201)
def create_order(payload: OrderCreate):
    order = {
        "id": max(o["id"] for o in ORDERS) + 1,
        "user_id": payload.user_id,
        "items": [],
        "total": payload.total,
        "currency": "INR",
        "status": "pending",
    }
    ORDERS.append(order)
    ORDERS_CREATED.inc()
    return order


@app.get("/load-test")
async def load_test(
    delay_ms: int = Query(0, ge=0, le=5000),
    error_rate: float = Query(0.0, ge=0, le=1),
):
    """Target for load tests: waits delay_ms, then fails with HTTP 500 with probability error_rate."""
    await asyncio.sleep(delay_ms / 1000)
    if random.random() < error_rate:
        raise HTTPException(status_code=500, detail="Simulated failure")
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
