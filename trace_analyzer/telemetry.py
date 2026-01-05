"""Telemetry setup for Trace Analyzer using OpenTelemetry."""

import logging
import os
import uuid
from typing import Optional

import google.auth
import google.auth.transport.grpc
import google.auth.transport.requests
import grpc
from google.auth.transport.grpc import AuthMetadataPlugin
from opentelemetry import trace, metrics, _logs
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

logger = logging.getLogger(__name__)

# Enable debug logging for OpenTelemetry to diagnose export issues
logging.getLogger("opentelemetry").setLevel(logging.DEBUG)

# Filter out the specific warning from google-generativeai types regarding function calls
class _FunctionCallWarningFilter(logging.Filter):
    def filter(self, record):
        return "Warning: there are non-text parts in the response" not in record.getMessage()

logging.getLogger().addFilter(_FunctionCallWarningFilter())
logging.getLogger("google.generativeai").addFilter(_FunctionCallWarningFilter())

# Global variables to hold providers
_tracer_provider: Optional[TracerProvider] = None
_meter_provider: Optional[MeterProvider] = None
_logger_provider: Optional[LoggerProvider] = None

def setup_telemetry(service_name: str = "trace-analyzer-agent") -> None:
    """
    Configures OpenTelemetry tracing and metrics with OTLP gRPC export.
    
    Exports to Google Cloud Tracing/Monitoring via telemetry.googleapis.com.
    """
    global _tracer_provider, _meter_provider

    # Avoid re-initializing or overriding existing providers
    if _tracer_provider is not None or os.environ.get("OTEL_SDK_DISABLED") == "true":
        return

    try:
        # Get Google Cloud credentials
        credentials, _ = google.auth.default()
        request = google.auth.transport.requests.Request()
        
        # Get Project ID
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or \
                     os.getenv("TRACE_PROJECT_ID") or \
                     getattr(credentials, "project_id", None) or \
                     getattr(credentials, "quota_project_id", None)
        
        # Prepare gRPC channel credentials with auth
        auth_metadata_plugin = AuthMetadataPlugin(credentials=credentials, request=request)
        channel_creds = grpc.composite_channel_credentials(
            grpc.ssl_channel_credentials(),
            grpc.metadata_call_credentials(auth_metadata_plugin),
        )

        # Define resource
        attributes = {
            SERVICE_NAME: service_name,
            "service.namespace": "trace_analyzer",
            "cloud.provider": "gcp",
            "service.instance.id": str(uuid.uuid4()),
        }

        # Dynamic environment detection
        is_vertex = any(os.environ.get(env) for env in [
            "AGENT_ENGINE_ID",
            "AIP_AGENT_NAME",
            "AIP_PROJECT_NUMBER",
            "CLOUD_ML_JOB_ID"
        ])
        
        if is_vertex:
            attributes["cloud.platform"] = "gcp_vertex_ai"
            logger.info("Detected Vertex AI / Agent Engine environment")
        else:
            # When running locally, we specify a generic resource to avoid
            # INVALID_ARGUMENT errors from the telemetry collector
            attributes["cloud.platform"] = "local"
            logger.info("Running in local development mode")
            
        if project_id:
            attributes["gcp.project_id"] = project_id
            
        resource = Resource.create(attributes=attributes)

        if project_id:
            logger.info(f"Resolved Google Cloud Project ID: {project_id}")
            print(f"TELEMETRY: Resolved Google Cloud Project ID: {project_id}")
        else:
            logger.warning("Could not resolve Google Cloud Project ID. Telemetry export may fail.")
            print(f"TELEMETRY WARNING: Could not resolve Google Cloud Project ID. Export will likely fail.")

        # Prepare headers (required for some GCP APIs if using a quota project different from auth project)
        headers = None
        if project_id:
            headers = (("x-goog-user-project", project_id),)

        # --- Tracing Setup ---
        # Only set if not already set to avoid warnings
        try:
            _tracer_provider = TracerProvider(resource=resource)
            trace_exporter = OTLPSpanExporter(
                credentials=channel_creds,
                endpoint="telemetry.googleapis.com:443",
                headers=headers,
            )
            _tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
            trace.set_tracer_provider(_tracer_provider)
        except ValueError:
            # Tracer provider already set
            _tracer_provider = trace.get_tracer_provider()
        
        # --- Metrics Setup ---
        try:
            metric_exporter = OTLPMetricExporter(
                credentials=channel_creds,
                endpoint="telemetry.googleapis.com:443",
                headers=headers,
            )
            metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=60000)
            _meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
            metrics.set_meter_provider(_meter_provider)
        except ValueError:
            _meter_provider = metrics.get_meter_provider()
        
        if project_id:
            logger.info(f"OpenTelemetry initialized for service: {service_name} (Project: {project_id})")
        
        logger.debug(f"OpenTelemetry Resource attributes: {resource.attributes}")

    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}", exc_info=True)
        # We generally don't want to crash the app if telemetry fails, so we pass
        pass

def get_tracer(name: str):
    """Returns a tracer for the given module name."""
    return trace.get_tracer(name)

def get_meter(name: str):
    """Returns a meter for the given module name."""
    return metrics.get_meter(name)
