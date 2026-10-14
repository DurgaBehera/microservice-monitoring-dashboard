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

How it's loaded:

- The dashboard JSON lives in `monitoring/grafana/dashboards/microservices-overview.json`.
- `monitoring/grafana/provisioning/dashboards/dashboards.yml` tells Grafana to load every JSON file from `/etc/grafana/dashboards`, which `docker-compose.yml` mounts from `monitoring/grafana/dashboards/`.
- Panels reference the provisioned Prometheus datasource by its fixed uid `prometheus`.
- You can edit the dashboard in the UI, but to keep changes, export the JSON (**Share → Export**) and save it over the file in the repo. Grafana re-reads the folder every 30 seconds.
- Panels only show data once there is traffic, so run the traffic loop below first.

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

# Requests per second, per endpoint
sum by (service, endpoint) (rate(http_requests_total[1m]))

# Error rate (4xx + 5xx) as a share of all requests, per service
sum by (service) (rate(http_requests_total{status=~"4..|5.."}[5m]))
  /
sum by (service) (rate(http_requests_total[5m]))

# 95th percentile latency per service
histogram_quantile(0.95, sum by (service, le) (rate(http_request_duration_seconds_bucket[5m])))

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
