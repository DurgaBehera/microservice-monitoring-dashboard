# Service uptime and the ServiceDown alert

## What it tracks

Each FastAPI service uses the default prometheus-client registry, which includes the process collector. That collector exports `process_start_time_seconds`, the Unix time the process started. From it:

| Panel | Query |
|---|---|
| Uptime (stat) | `time() - process_start_time_seconds{job=~".*-service"}` |
| Restarts in selected range | `changes(process_start_time_seconds{job=~".*-service"}[$__range])` |
| Uptime over time | `time() - process_start_time_seconds{job=~".*-service"}` |

Open the dashboard at http://localhost:3000 → Dashboards → **Service Uptime**.

## ServiceDown alert

Defined in `monitoring/prometheus/alerts.yml`:

```yaml
- alert: ServiceDown
  expr: up{job=~".*-service"} == 0
  for: 1m
  labels:
    severity: critical
```

## Trying it out

1. Start the stack: `docker compose up -d`
2. Stop one service: `docker compose stop payment-service`
3. Open http://localhost:9090/alerts. Within one scrape interval `ServiceDown` turns **pending** for `payment-service`, then **firing** after 1 minute. It is sent on to Alertmanager at http://localhost:9093.
4. Start it again: `docker compose start payment-service`. The alert resolves, uptime restarts from zero and the restart counter goes up by one.

Note: the restart counter only sees restarts that Prometheus scraped on both sides. A container that restarts between two scrapes may be missed.
