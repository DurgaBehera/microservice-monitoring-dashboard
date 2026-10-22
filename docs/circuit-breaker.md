# Circuit Breaker Status (feature #17)

`order-service` calls `payment-service` through a small circuit breaker
(`services/order-service/app/circuit_breaker.py`, no extra dependencies).

| State | Gauge value | Behaviour |
|---|---|---|
| Closed | 0 | Calls go through. Consecutive failures are counted. |
| Open | 1 | Calls fail fast with **HTTP 503** and are counted as rejected. |
| Half-open | 2 | After the recovery timeout one trial call is allowed. Success closes the breaker, failure reopens it. |

## Endpoints (order-service)
- `POST /orders/{order_id}/pay` – calls payment-service (`GET /health`). Returns 200 on success, 502 if the call failed, 503 if the circuit is open.
- `GET /circuit-breaker` – current state as JSON.

## Configuration (env vars)
| Variable | Default |
|---|---|
| `PAYMENT_SERVICE_URL` | `http://payment-service:8000` |
| `CB_FAILURE_THRESHOLD` | `5` consecutive failures |
| `CB_RECOVERY_TIMEOUT_SECONDS` | `30` |
| `PAYMENT_TIMEOUT_SECONDS` | `2` |

## Metrics
- `circuit_breaker_state{service,target}` – 0 closed, 1 open, 2 half-open
- `circuit_breaker_transitions_total{service,target,from_state,to_state}`
- `circuit_breaker_rejected_calls_total{service,target}`

Grafana dashboard: **Circuit Breaker Status** (uid `circuit-breaker`).

## How to trigger it
```bash
docker compose up -d
docker compose stop payment-service
for i in $(seq 1 8); do curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8002/orders/101/pay; done
# 5x 502, then 503 (open)
docker compose start payment-service
sleep 30   # recovery timeout
curl -X POST localhost:8002/orders/101/pay   # trial call succeeds -> closed
```

## Tests
```bash
cd services/order-service
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```
