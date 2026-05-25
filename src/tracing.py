import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
except Exception:
    OTLPSpanExporter = None

try:
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
except Exception:
    JaegerExporter = None


def init_tracing(service_name: str = "ai-ops-agent"):
    """Initialize OpenTelemetry tracing using OTLP if configured, otherwise Jaeger, otherwise console."""
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otel_endpoint and OTLPSpanExporter is not None:
        exporter = OTLPSpanExporter(endpoint=otel_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logging.getLogger(__name__).info("Tracing initialized with OTLP at %s", otel_endpoint)
    elif os.environ.get("JAEGER_AGENT_HOST") and JaegerExporter is not None:
        jaeger_agent_host = os.environ.get("JAEGER_AGENT_HOST")
        jaeger_agent_port = int(os.environ.get("JAEGER_AGENT_PORT", "6831"))
        exporter = JaegerExporter(agent_host_name=jaeger_agent_host, agent_port=jaeger_agent_port)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logging.getLogger(__name__).info("Tracing initialized with Jaeger at %s:%s", jaeger_agent_host, jaeger_agent_port)
    else:
        # Console exporter as fallback
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logging.getLogger(__name__).warning("Tracing initialized with console exporter (no OTLP/Jaeger configured)")

    trace.set_tracer_provider(provider)
    # Optionally auto-instrumentation can be done in app entry points
    return trace.get_tracer(__name__)
