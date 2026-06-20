"""
OpenTelemetry observability — traces, metrics, logs.
Configuración para Inteliaudit SaaS.
"""
import logging
from contextlib import asynccontextmanager

from config.settings import settings

logger = logging.getLogger("inteliaudit.telemetry")


def setup_telemetry(app=None):
    """
    Configura OpenTelemetry con exporters condicionales.
    Si OTEL_EXPORTER_OTLP_ENDPOINT está configurado, exporta a un collector.
    Si no, usa console exporter para desarrollo.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME

        resource = Resource.create({
            "service.name": "inteliaudit",
            "service.version": "0.1.0",
            "deployment.environment": "production" if not settings.debug else "development",
        })

        provider = TracerProvider(resource=resource)

        import os
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

        if otlp_endpoint:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            logger.info(f"OpenTelemetry: exporting to {otlp_endpoint}")
        else:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            exporter = ConsoleSpanExporter()
            logger.info("OpenTelemetry: console exporter (dev mode)")

        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # Instrument FastAPI if provided
        if app:
            try:
                from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
                FastAPIInstrumentor.instrument_app(app)
                logger.info("FastAPI instrumented with OpenTelemetry")
            except Exception as e:
                logger.warning(f"FastAPI instrumentation failed: {e}")

        # Instrument SQLAlchemy
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            SQLAlchemyInstrumentor().instrument()
            logger.info("SQLAlchemy instrumented with OpenTelemetry")
        except Exception as e:
            logger.warning(f"SQLAlchemy instrumentation failed: {e}")

        # Instrument httpx
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            HTTPXClientInstrumentor().instrument()
            logger.info("httpx instrumented with OpenTelemetry")
        except Exception as e:
            logger.warning(f"httpx instrumentation failed: {e}")

        return trace.get_tracer("inteliaudit")

    except ImportError:
        logger.info("OpenTelemetry not installed — telemetry disabled")
        return None
    except Exception as e:
        logger.warning(f"OpenTelemetry setup failed: {e}")
        return None


@asynccontextmanager
async def trace_span(name: str, attributes: dict = None):
    """Context manager para crear spans de tracería."""
    try:
        from opentelemetry import trace
        tracer = trace.get_tracer("inteliaudit")
        with tracer.start_as_current_span(name, attributes=attributes or {}) as span:
            yield span
    except Exception:
        # Fallback: no-op span
        class NoOpSpan:
            def set_attribute(self, k, v): pass
            def set_status(self, s): pass
            def add_event(self, n, a=None): pass
        yield NoOpSpan()
