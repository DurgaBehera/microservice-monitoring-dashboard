# Microservice Monitoring Dashboard

A small, ready-to-run demo of monitoring Python microservices with **FastAPI**, **Prometheus**, and **Grafana**, all wired together with **Docker Compose**.

Three FastAPI services (users, orders, payments) serve simple dummy data and expose Prometheus metrics. Prometheus scrapes them every 15 seconds, and Grafana comes pre-connected to Prometheus so you can start building dashboards right away.

## Prerequisites

- Docker with the Compose plugin (`docker compose version` should work)
- Free host ports: 8001, 8002, 8003, 9090, 3000

## Quick start

```bash
docker compose up --build
```

That's the only command you need. It builds the three service images, then starts them along with Prometheus and Grafana.

To run it in the background, stop it, or wipe stored data:

```bash
docker compose up --build -d   # run detached
docker compose logs -f         # follow logs
docker compose down            # stop and remove containers
docker compose down -v         # also delete Prometheus/Grafana data volumes
```

## Access URLs

| Component        | URL                            | Notes                                     |
|------------------|--------------------------------|-------------------------------------------|
| User Service     | http://localhost:8001          | `/users`, `/users/{user_id}`, `/health`, `/metrics`, `/docs` |
| Order Service    | http://localhost:8002          | `/orders`, `/orders/{order_id}`, `/health`, `/metrics`, `/docs` |
| Payment Service  | http://localhost:8003          | `/payments`, `/payments/{payment_id}`, `/health`, `/metrics`, `/docs` |
| Prometheus       | http://localhost:9090          | Targets page: http://localhost:9090/targets |
| Grafana          | http://localhost:3000          | Login: **admin / admin**                  |

Each service also has interactive API docs at `/docs` (Swagger UI).

### Try it out

```bash
curl http://localhost:8001/users
curl http://localhost:8001/users/1
curl http://localhost:8002/orders/101
curl http://localhost:8003/payments
curl http://localhost:8003/payments/9999   # 404, shows up in metrics too
curl http://localhost:8001/health          # {"status":"healthy"}
curl http://localhost:8001/metrics
```

Dummy IDs: users `1-4`, orders `101-104`, payments `5001-5004`.

## Grafana

- Default login: **admin / admin** (set in `.env`). Grafana may ask you to change the password on first login; you can skip that locally.
- A Prometheus datasource is **provisioned automatically** from `monitoring/grafana/provisioning/datasources/prometheus.yml`, pointing at `http://prometheus:9090`. You don't need to add it by hand.
- A ready-made **Microservices Overview** dashboard is provisioned automatically (see below). To build your own: **Dashboards → New → New dashboard → Add visualization**, pick the *Prometheus* datasource, and paste one of the queries below.

### Microservices Overview dashboard

Open it at **http://localhost:3000/d/microservices-overview** (or **Dashboards → Microservices → Microservices Overview**). It refreshes every 10 seconds and shows the last 15 minutes by default.

| Panel | What it shows | Query (simplified) |
|-------|---------------|--------------------|
| **Service Status** | UP (green) / DOWN (red) for each service, based on whether Prometheus could scrape it | `up{job=~"user-service\|order-service\|payment-service"}` |
| **Request Rate per Service** | Requests per second handled by each service | `sum by (service) (rate(http_requests_total[1m]))` |
| **Error Rate (%)** | Percentage of requests that returned a 5xx status, per service. Shows 0% when there are no errors | 5xx rate / total rate × 100 |
| **P95 Latency per Service** | 95th percentile response time per service | `histogram_quantile(0.95, sum by (service, le) (rate(http_request_duration_seconds_bucket[1m])))` |
| **Average Response Time per Service** | Mean response time across requests per service, in milliseconds; use alongside P95/P99 to see whether tail latency is much higher than the average | `(sum by (service) (rate(http_request_duration_seconds_sum[1m])) / sum by (service) (rate(http_request_duration_seconds_count[1m]))) * 1000` |
| **P99 Latency per Service** | 99th-percentile response time per service, in milliseconds; roughly 99% of requests complete at or below this value, highlighting slow-tail behavior | `histogram_quantile(0.99, sum by (service, le) (rate(http_request_duration_seconds_bucket[1m]))) * 1000` |
| **Request Success Rate (%)** | Percentage of requests that returned a 2xx status, per service (red below 95%, yellow below 99%, green at 99% and above). 4xx and 5xx both count as unsuccessful. Services with no traffic in the last minute show no line | 2xx rate / total rate × 100 |

Average response time is calculated from histogram `_sum` and `_count` rates. P99 is estimated from the histogram buckets, so its precision depends on the bucket boundaries configured by each service.

How it's loaded:

- The dashboard JSON lives in `monitoring/grafana/dashboards/microservices-overview.json`.
- `monitoring/grafana/provisioning/dashboards/dashboards.yml` tells Grafana to load every JSON file from `/etc/grafana/dashboards`, which `docker-compose.yml` mounts from `monitoring/grafana/dashboards/`.
- Panels reference the provisioned Prometheus datasource by its fixed uid `prometheus`.
- You can edit the dashboard in the UI, but to keep changes, export the JSON (**Share → Export**) and save it over the file in the repo. Grafana re-reads the folder every 30 seconds.
- Panels only show data once there is traffic, so run the traffic loop below first.

### Response Time Histogram dashboard

Open at http://localhost:3000/d/response-time-histogram. Shows how many requests fell into each response time bucket (bar chart) and how response times change over time (heatmap). The dashboard JSON is generated by `monitoring/generate_histogram_dashboard.py`.

### Verifying Latency Panels

Start the stack from the project directory:

```bash
docker compose up --build
```

Open Grafana at **http://localhost:3000** and generate requests using the service routes:

```bash
curl http://localhost:8001/users
curl http://localhost:8002/orders/101
curl http://localhost:8003/payments/5001
```

Allow Prometheus time to scrape the requests and populate the 1-minute rate windows, then select a dashboard time range that includes the generated traffic (for example, **Last 15 minutes**). Check target health at **http://localhost:9090/targets**. If the latency panels have no data, confirm the service targets are **UP** and check the services' `/metrics` output for `http_request_duration_seconds_bucket`, `http_request_duration_seconds_sum`, and `http_request_duration_seconds_count`.

## Alerting

Prometheus loads alert rules from `monitoring/prometheus/alerts.yml` (mounted at `/etc/prometheus/alerts.yml`) and sends firing alerts to Alertmanager.

- `HighErrorRate`: fires when a service's 5xx rate stays above 5% (with more than 0.1 req/s) for 1 minute.

Check that the rule is loaded at http://localhost:9090/rules. To validate the files without Docker: `promtool check rules monitoring/prometheus/alerts.yml`.

## Metrics

Every service records these metrics with an HTTP middleware:

| Metric                              | Type      | Labels                                  |
|-------------------------------------|-----------|-----------------------------------------|
| `http_requests_total`               | Counter   | `service`, `method`, `endpoint`, `status` |
| `http_request_duration_seconds`     | Histogram | `service`, `method`, `endpoint`         |

The `endpoint` label uses the **route template** (for example `/users/{user_id}`), not the raw URL, so the number of time series stays small no matter how many IDs are requested. Requests that match no route are labelled `unmatched`.

The default `prometheus-client` process and Python runtime metrics (`process_*`, `python_gc_*`, and so on) are exposed as well.

### Example PromQL queries

```promql
# Are all services up? (1 = up, 0 = down)
up{job=~"user-service|order-service|payment-service"}

# Requests per second, per service
sum by (service) (rate(http_requests_total[1m]))

# Success rate (%) per service: share of 2xx responses
100 * sum by (service) (rate(http_requests_total{status=~"2.."}[1m])) / (sum by (service) (rate(http_requests_total[1m])) > 0)

# Requests per second, per endpoint
sum by (service, endpoint) (rate(http_requests_total[1m]))

# Error rate (4xx + 5xx) as a share of all requests, per service
sum by (service) (rate(http_requests_total{status=~"4..|5.."}[5m]))
  /
sum by (service) (rate(http_requests_total[5m]))

# 95th percentile latency per service
histogram_quantile(0.95, sum by (service, le) (rate(http_request_duration_seconds_bucket[5m])))

# Average response time in milliseconds, per service
(sum by (service) (rate(http_request_duration_seconds_sum[1m])) / sum by (service) (rate(http_request_duration_seconds_count[1m]))) * 1000

# 99th percentile latency in milliseconds, per service
histogram_quantile(0.99, sum by (service, le) (rate(http_request_duration_seconds_bucket[1m]))) * 1000

# Average latency per endpoint
sum by (service, endpoint) (rate(http_request_duration_seconds_sum[5m]))
  /
sum by (service, endpoint) (rate(http_request_duration_seconds_count[5m]))
```

Tip: generate some traffic first so the graphs have data:

```bash
for i in $(seq 1 50); do
  curl -s localhost:8001/users > /dev/null
  curl -s localhost:8002/orders/10$((i % 5)) > /dev/null
  curl -s localhost:8003/payments > /dev/null
done
```

## Project structure

```
microservice-monitoring-dashboard/
├── services/
│   ├── user-service/            # FastAPI app: /users, /users/{user_id}
│   │   ├── app/main.py          # Endpoints, dummy data, Prometheus middleware + /metrics
│   │   ├── requirements.txt     # Pinned Python dependencies
│   │   └── Dockerfile           # python:3.11-slim image running uvicorn on port 8000
│   ├── order-service/           # FastAPI app: /orders, /orders/{order_id}
│   └── payment-service/         # FastAPI app: /payments, /payments/{payment_id}
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml       # Scrape config for the 3 services (+ Prometheus itself)
│   └── grafana/
│       ├── dashboards/
│       │   └── microservices-overview.json  # Provisioned dashboard: status, request rate, error %, P95 latency
│       └── provisioning/
│           ├── dashboards/
│           │   └── dashboards.yml       # Tells Grafana to load dashboards from the mounted folder
│           └── datasources/
│               └── prometheus.yml       # Auto-adds Prometheus (uid: prometheus) as the default datasource
├── docker-compose.yml           # Runs the 3 services, Prometheus and Grafana on one network
├── .env                         # Local dev defaults: ports and Grafana login
├── README.md
└── .gitignore
```

### How it fits together

- All containers share the `monitoring` Docker network, so they reach each other by service name (for example `user-service:8000`).
- Each service listens on port **8000 inside its container**. Docker maps them to host ports **8001, 8002, 8003**.
- Prometheus reads `monitoring/prometheus/prometheus.yml` and scrapes `user-service:8000/metrics`, `order-service:8000/metrics`, and `payment-service:8000/metrics`.
- Each service has a Docker healthcheck that calls `/health` with Python's standard library, since the slim image has no `curl`.
- Prometheus and Grafana data persist in named volumes (`prometheus-data`, `grafana-data`) until you run `docker compose down -v`.

## Configuration (`.env`)

`.env` is committed on purpose. It holds **local development defaults only** (host ports and the Grafana admin login), not real secrets. Docker Compose reads it automatically. Edit it to change ports or credentials, and don't put production secrets in it. Use an untracked `.env.local` or your deployment's secret store for those.

## Running a service without Docker

```bash
cd services/user-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```
