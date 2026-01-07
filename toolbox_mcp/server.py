from toolbox_core import ToolboxServer
import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.cloud_trace_propagator import CloudTraceFormatPropagator
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

def setup_telemetry():
    """Configures OpenTelemetry for Google Cloud Trace or OTLP."""
    # Set up propagator for Google Cloud Trace (X-Cloud-Trace-Context)
    set_global_textmap(CloudTraceFormatPropagator())

    tracer_provider = TracerProvider()
    
    # Check if we should use OTLP (e.g. for Collector sidecar) or Direct GCP
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    
    try:
        if otlp_endpoint:
            # Use OTLP
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            print(f"Using OTLP Exporter to {otlp_endpoint}")
        else:
            # Use Google Cloud Trace Exporter (Default for Cloud Run)
            exporter = CloudTraceSpanExporter()
            print("Using Google Cloud Trace Exporter")

        tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(tracer_provider)
        
        # Instrument logging to capture log records as events in spans
        LoggingInstrumentor().instrument(set_logging_format=True)
        
        # Instrument common frameworks/libraries globally
        # This ensures that whatever ToolboxServer uses, we likely catch it.
        FastAPIInstrumentor().instrument()
        FlaskInstrumentor().instrument()
        RequestsInstrumentor().instrument()
        
    except Exception as e:
        print(f"Failed to setup telemetry: {e}")

def main():
    setup_telemetry()
    config_path = os.getenv("TOOLBOX_CONFIG", "/app/config.yaml")
    server = ToolboxServer(config_path)
    server.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    main()
