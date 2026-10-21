# Business metric (#9) and load test endpoint (#13)

## Orders created (#9)
`POST /orders` on order-service creates an order and increases the counter `orders_created_total`.

```bash
curl -X POST localhost:8002/orders -H "Content-Type: application/json" -d '{"user_id": 1, "total": 1499.5}'
curl -s localhost:8002/metrics | grep ^orders_created_total
```

## Load test endpoint (#13)
`GET /load-test?delay_ms=200&error_rate=0.25` on order-service waits `delay_ms` (max 5000) and then fails
with HTTP 500 with probability `error_rate` (0 to 1).

Send steady load for 60 seconds (Prometheus only looks every 15 s, so very short bursts can be missed):

```bash
end=$((SECONDS+60)); while [ $SECONDS -lt $end ]; do
  for i in 1 2 3 4 5; do curl -s -o /dev/null "localhost:8002/load-test?delay_ms=150&error_rate=0.25" & done; wait
done
```

## Dashboard
Grafana, **Business Metrics & Load Test**: http://localhost:3000/d/business-metrics
