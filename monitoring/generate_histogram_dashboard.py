import json

DS_UID = "prometheus"   # must match the uid in monitoring/grafana/provisioning/datasources/prometheus.yml (Grafana datasource provisioning)
BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]  # same as main.py

M = "http_request_duration_seconds"
DS = {"type": "prometheus", "uid": DS_UID}
EXCLUDE = 'endpoint!~"/metrics|/health"'


def selector(*parts):
    return "{" + ", ".join(parts) + "}"


def inc(b):
    return "sum(increase(" + M + "_bucket" + selector(EXCLUDE, 'le="' + repr(float(b)) + '"') + "[$__range]))"


targets, prev = [], None
for i, b in enumerate(BUCKETS):
    lo = "0" if prev is None else f"{prev * 1000:g}"
    expr = inc(b) if prev is None else inc(b) + " - " + inc(prev)
    targets.append({
        "refId": chr(65 + i), "datasource": DS, "expr": expr,
        "legendFormat": f"{lo}-{b * 1000:g} ms", "instant": True, "range": False,
    })
    prev = b

targets.append({
    "refId": chr(65 + len(BUCKETS)), "datasource": DS,
    "expr": "sum(increase(" + M + "_count" + selector(EXCLUDE) + "[$__range])) - " + inc(BUCKETS[-1]),
    "legendFormat": f">{BUCKETS[-1] * 1000:g} ms", "instant": True, "range": False,
})

heatmap_expr = "sum by (le) (increase(" + M + "_bucket" + selector(EXCLUDE) + "[1m]))"

dashboard = {
    "uid": "response-time-histogram",
    "title": "Response Time Histogram",
    "schemaVersion": 39, "version": 1, "refresh": "10s",
    "time": {"from": "now-15m", "to": "now"},
    "panels": [
        {
            "id": 1, "type": "bargauge",
            "title": "Response Time Distribution (requests per bucket)",
            "datasource": DS, "gridPos": {"h": 10, "w": 24, "x": 0, "y": 0},
            "targets": targets,
            "options": {
                "orientation": "vertical", "displayMode": "gradient", "showUnfilled": True,
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            },
            "fieldConfig": {"defaults": {"decimals": 0, "min": 0}, "overrides": []},
        },
        {
            "id": 2, "type": "heatmap", "title": "Response Time Heatmap",
            "datasource": DS, "gridPos": {"h": 10, "w": 24, "x": 0, "y": 10},
            "targets": [{
                "refId": "A", "datasource": DS, "format": "heatmap",
                "legendFormat": "{{le}}", "expr": heatmap_expr,
            }],
            "options": {"calculate": False, "yAxis": {"unit": "s"}, "cellGap": 1},
        },
    ],
}

out = "monitoring/grafana/dashboards/response-time-histogram.json"
with open(out, "w") as f:
    json.dump(dashboard, f, indent=2)
print("Wrote", out)
print("First bar query:", targets[0]["expr"])