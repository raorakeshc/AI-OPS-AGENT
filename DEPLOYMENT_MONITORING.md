# Deployment & Monitoring

This document describes packaging assumptions for local/cloud deployment, tracing and metrics setup (Prometheus + OpenTelemetry), centralized logs, and how to collect latency/quality evidence.

## Packaging

Assumptions:
- Python 3.10+ virtual environment or container image.
- `requirements.txt` contains runtime dependencies; additional instrumentation packages may be required:
  - `prometheus_client`
  - `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp`, `opentelemetry-exporter-jaeger`, `opentelemetry-instrumentation-fastapi`
- Persistent `data/` and `logs/` volumes are mounted in container deployments.

Local packaging (dev):
- Create a virtualenv and install requirements:

```bash
python -m venv .venv
.venv/Scripts/Activate.ps1  # Windows PowerShell
pip install -r requirements.txt
pip install prometheus_client opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp opentelemetry-exporter-jaeger opentelemetry-instrumentation-fastapi
```

Container packaging (example):
- Build a Docker image using the provided `Dockerfile` and mount volumes for `data/` and `logs/`.

## Tracing (OpenTelemetry)

Initialization:
- The app initializes tracing on startup (`src/tracing.py`). It prefers OTLP if `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
- If OTLP not configured, the Jaeger exporter is used if `JAEGER_AGENT_HOST`/`JAEGER_AGENT_PORT` are set.
- Otherwise, a console exporter is used for local debugging.

Configuration examples:
- Send traces to an OpenTelemetry Collector (OTLP):
```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318/v1/traces
```
- Send traces directly to Jaeger agent:
```bash
export JAEGER_AGENT_HOST=jaeger-agent
export JAEGER_AGENT_PORT=6831
```

What to expect:
- Spans for incoming HTTP requests and any instrumented libraries will be exported.
- Use Jaeger/OTel UI to inspect traces, find slow endpoints, and understand upstream/downstream calls.

## Metrics (Prometheus)

- The API mounts a Prometheus ASGI app at `/metrics` (provided by `prometheus_client.make_asgi_app`).
- The app records request counts and latency histograms per-path.

Prometheus scrape config example:
```yaml
scrape_configs:
  - job_name: 'ai-ops-orders'
    static_configs:
      - targets: ['orders-service:8081']
```

Metrics of interest:
- `requests_total{path="/orders/123"}` — total requests
- `request_latency_ms_bucket{path="/orders/123"}` — latency distribution

## Logging / Centralized Collector

- The app writes JSON-structured logs to stdout and to `logs/app.log` (rotating file).
- For centralized collection, deploy a log forwarder (Fluentd/Fluent Bit, OpenTelemetry Collector) to gather stdout or tail `logs/app.log`.
- Example: Configure Collector to read stdout logs from Docker containers or read the mounted `logs/` directory.

## Tracing + Metrics + Logs: Correlation

- Ensure services set a stable `service.name` and pass trace context to downstream services.
- Logs should include trace/span identifiers when available. (Future: add a structured logging filter to inject trace ids from OpenTelemetry into log records.)

## Evidence Collection: Latency & Quality

To produce empirical evidence, run a short benchmark and capture metrics and traces.

1. Run the API locally.
2. Warm up with a small number of requests.
3. Run a benchmark (example using `wrk` or a simple Python script) for N requests.
4. After the run, fetch Prometheus metrics and exported traces.

Quick example (Python script):
```python
import requests
for i in range(100):
    requests.get('http://localhost:8081/orders/123', headers={'Authorization':'Bearer demo_token_123'})
```

Then:
```bash
curl http://localhost:8081/metrics | sed -n '1,200p'
# or query Prometheus for aggregated metrics
# examine traces in Jaeger or OTel collector UI
```

Recommended next improvements
- Add Prometheus labels for HTTP method and status code.
- Inject trace IDs into structured logs.
- Add distributed tracing for downstream calls (e.g., KB retriever, LLM API calls) using instrumentations.
- Replace in-memory metrics with a robust exporter to Prometheus Pushgateway if needed.

*** End of Deployment & Monitoring Guide
