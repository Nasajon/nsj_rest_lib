import logging
import os

from flask import Flask

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

# Lendo variáveis de ambiente
APP_NAME = os.getenv("APP_NAME", "nsj_rest_lib")
MOPE_CODE = os.getenv("MOPE_CODE")
DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", 20))
USE_SQL_RETURNING_CLAUSE = (
    os.getenv("USE_SQL_RETURNING_CLAUSE", "true").lower() == "true"
)

DATABASE_HOST = os.getenv("DATABASE_HOST", "")
DATABASE_PASS = os.getenv("DATABASE_PASS", "")
DATABASE_PORT = os.getenv("DATABASE_PORT", "")
DATABASE_NAME = os.getenv("DATABASE_NAME", "")
DATABASE_USER = os.getenv("DATABASE_USER", "")
DATABASE_DRIVER = os.getenv("DATABASE_DRIVER", "POSTGRES")

DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 1))

CLOUD_SQL_CONN_NAME = os.getenv("CLOUD_SQL_CONN_NAME", "")
ENV = os.getenv("ENV", "")


def get_logger():
    return logging.getLogger(APP_NAME)

# Endpoint do OpenTelemetry Collector
OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "otel-collector.prometheus-otel:4317")

# Configuração do exportador OTLP
otlp_exporter = OTLPMetricExporter(endpoint=OTLP_ENDPOINT)
reader = PeriodicExportingMetricReader(otlp_exporter)
provider = MeterProvider(metric_readers=[reader])

# Define o provedor global de métricas
metrics.set_meter_provider(provider)

application = Flask("app")
