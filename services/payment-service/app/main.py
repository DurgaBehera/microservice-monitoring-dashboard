"""Payment Service - a simple FastAPI microservice instrumented with Prometheus metrics."""

import time

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

SERVICE_NAME = "payment-service"

app = FastAPI(title="Payment Service", version="1.0.0")

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
        # Use the route template (e.g. /payments/{payment_id}) rather than the raw path
        # so metric label cardinality stays bounded.
        route = request.scope.get("route")
        endpoint = getattr(route, "path", None) or "unmatched"
        REQUEST_COUNT.labels(SERVICE_NAME, request.method, endpoint, str(status_code)).inc()
        REQUEST_LATENCY.labels(SERVICE_NAME, request.method, endpoint).observe(elapsed)


# ---------------------------------------------------------------------------
# Dummy data
# ---------------------------------------------------------------------------
PAYMENTS = [
    {"id": 5001, "order_id": 101, "amount": 4999.00, "currency": "INR", "method": "upi", "status": "captured"},
    {"id": 5002, "order_id": 102, "amount": 1798.00, "currency": "INR", "method": "card", "status": "captured"},
    {"id": 5003, "order_id": 103, "amount": 2499.00, "currency": "INR", "method": "netbanking", "status": "authorized"},
    {"id": 5004, "order_id": 104, "amount": 18999.00, "currency": "INR", "method": "card", "status": "failed"},
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


@app.get("/payments")
def list_payments():
    return {"count": len(PAYMENTS), "payments": PAYMENTS}


@app.get("/payments/{payment_id}")
def get_payment(payment_id: int):
    for item in PAYMENTS:
        if item["id"] == payment_id:
            return item
    raise HTTPException(status_code=404, detail="Payment not found")


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
