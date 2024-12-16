#!/usr/bin/env python3
from litellm.integrations.custom_logger import CustomLogger
import litellm
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
import os
import google.cloud.secretmanager as secretmanager
import logging

class ArizeCallback(CustomLogger):
    def __init__(self):
        super().__init__()
        self.setup_arize()

    def setup_arize(self):
        try:
            # Get credentials from Secret Manager
            client = secretmanager.SecretManagerServiceClient()
            project_id = os.getenv('GOOGLE_CLOUD_PROJECT')

            space_id = None
            api_key = None

            try:
                space_id_response = client.access_secret_version(
                    request={"name": f"projects/{project_id}/secrets/ARIZE_SPACE_ID/versions/latest"}
                )
                space_id = space_id_response.payload.data.decode()
            except Exception as e:
                logging.info(f"Using environment variable for ARIZE_SPACE_ID: {e}")
                space_id = os.getenv('ARIZE_SPACE_ID')

            try:
                api_key_response = client.access_secret_version(
                    request={"name": f"projects/{project_id}/secrets/ARIZE_API_KEY/versions/latest"}
                )
                api_key = api_key_response.payload.data.decode()
            except Exception as e:
                logging.info(f"Using environment variable for ARIZE_API_KEY: {e}")
                api_key = os.getenv('ARIZE_API_KEY')

            # Initialize Arize OpenTelemetry
            trace.set_tracer_provider(TracerProvider())
            processor = BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint="otlp.arize.com",
                    headers={
                        "space_id": space_id,
                        "api_key": api_key,
                    },
                )
            )
            trace.get_tracer_provider().add_span_processor(processor)
            HTTPXClientInstrumentor().instrument()
            logging.info("Arize logging initialized in callback")
        except Exception as e:
            logging.error(f"Failed to initialize Arize logging in callback: {e}")

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            model = kwargs.get("model")
            messages = kwargs.get("messages")
            user = kwargs.get("user")
            litellm_params = kwargs.get("litellm_params", {})
            metadata = litellm_params.get("metadata", {})

            cost = litellm.completion_cost(completion_response=response_obj)
            usage = response_obj.get("usage", {})

            logging.info(f"Logged successful completion to Arize - Model: {model}, User: {user}, Cost: {cost}")
        except Exception as e:
            logging.error(f"Failed to log success event to Arize: {e}")

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        try:
            model = kwargs.get("model")
            messages = kwargs.get("messages")
            user = kwargs.get("user")
            exception_event = kwargs.get("exception")

            logging.error(f"Logged failed completion to Arize - Model: {model}, User: {user}, Error: {exception_event}")
        except Exception as e:
            logging.error(f"Failed to log failure event to Arize: {e}")

    def log_stream_event(self, kwargs, response_obj, start_time, end_time):
        try:
            model = kwargs.get("model")
            user = kwargs.get("user")
            logging.info(f"Logged stream event to Arize - Model: {model}, User: {user}")
        except Exception as e:
            logging.error(f"Failed to log stream event to Arize: {e}")

arize_callback_instance = ArizeCallback()
