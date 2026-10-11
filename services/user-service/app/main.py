"""User Service - a simple FastAPI microservice instrumented with Prometheus metrics."""

import time

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

SERVICE_NAME = "user-service"

app = FastAPI(title="User Service", version="1.0.0")

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
        # Use the route template (e.g. /users/{user_id}) rather than the raw path
        # so metric label cardinality stays bounded.
        route = request.scope.get("route")
        endpoint = getattr(route, "path", None) or "unmatched"
        REQUEST_COUNT.labels(SERVICE_NAME, request.method, endpoint, str(status_code)).inc()
        REQUEST_LATENCY.labels(SERVICE_NAME, request.method, endpoint).observe(elapsed)


# ---------------------------------------------------------------------------
# Dummy data
# ---------------------------------------------------------------------------
USERS = [
    {"id": 1, "name": "Aarav Sharma", "email": "aarav.sharma@example.com", "role": "admin", "active": True},
    {"id": 2, "name": "Priya Patel", "email": "priya.patel@example.com", "role": "customer", "active": True},
    {"id": 3, "name": "Rohan Mehta", "email": "rohan.mehta@example.com", "role": "customer", "active": False},
    {"id": 4, "name": "Ananya Iyer", "email": "ananya.iyer@example.com", "role": "support", "active": True},
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


@app.get("/users")
def list_users():
    return {"count": len(USERS), "users": USERS}


@app.get("/users/{user_id}")
def get_user(user_id: int):
    for item in USERS:
        if item["id"] == user_id:
            return item
    raise HTTPException(status_code=404, detail="User not found")


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
