FROM python:3.11-slim

WORKDIR /app

RUN pip install toolbox-core google-auth google-cloud-bigquery \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-gcp-trace \
    opentelemetry-exporter-otlp \
    opentelemetry-propagator-gcp \
    opentelemetry-instrumentation-logging \
    opentelemetry-instrumentation-fastapi \
    opentelemetry-instrumentation-flask \
    opentelemetry-instrumentation-requests

COPY config.yaml /app/config.yaml
COPY server.py /app/server.py

EXPOSE 8080

CMD ["python", "server.py"]
