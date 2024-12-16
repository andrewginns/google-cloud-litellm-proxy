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
from litellm.proxy.proxy_server import ProxyConfig

class ArizeCallback(CustomLogger):
    def __init__(self):
        super().__init__()
        # Configure proxy settings to disable authentication
        proxy_config = ProxyConfig()
        proxy_config.auth_required = False
        proxy_config.require_api_key = False
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
                    request={"name": f"projects/{project_id}/secrets/ARIZE_TEST_SPACE_ID/versions/latest"}
                )
                space_id = space_id_response.payload.data.decode()
            except Exception as e:
                logging.info(f"Using environment variable for ARIZE_TEST_SPACE_ID: {e}")
                space_id = os.getenv('ARIZE_TEST_SPACE_ID')

            try:
                api_key_response = client.access_secret_version(
                    request={"name": f"projects/{project_id}/secrets/ARIZE_TEST_API_KEY/versions/latest"}
                )
                api_key = api_key_response.payload.data.decode()
            except Exception as e:
                logging.info(f"Using environment variable for ARIZE_TEST_API_KEY: {e}")
                api_key = os.getenv('ARIZE_TEST_API_KEY')

            # Initialize Arize OpenTelemetry
            logging.info(f"Initializing Arize OpenTelemetry with endpoint=https://otlp.arize.com:443")
            trace.set_tracer_provider(TracerProvider())

            # Configure detailed export logging
            class LoggingSpanProcessor(BatchSpanProcessor):
                def _export(self, spans):
                    try:
                        logging.info(f"Exporting {len(spans)} spans to Arize")
                        result = super()._export(spans)
                        logging.info("Successfully exported spans to Arize")
                        return result
                    except Exception as e:
                        logging.error(f"Failed to export spans to Arize: {e}", exc_info=True)
                        return False

            processor = LoggingSpanProcessor(
                OTLPSpanExporter(
                    endpoint="https://otlp.arize.com:443",
                    headers={
                        "space_id": space_id,
                        "api_key": api_key,
                        "Content-Type": "application/json",
                    },
                    insecure=False,
                )
            )
            trace.get_tracer_provider().add_span_processor(processor)
            HTTPXClientInstrumentor().instrument()
            logging.info(f"Arize OpenTelemetry initialized successfully with space_id={space_id}")
        except Exception as e:
            logging.error(f"Failed to initialize Arize logging in callback: {e}", exc_info=True)

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            model = kwargs.get("model")
            messages = kwargs.get("messages", [])
            user = kwargs.get("user")
            litellm_params = kwargs.get("litellm_params", {})
            metadata = litellm_params.get("metadata", {})

            # Extract Vertex AI specific fields
            content = response_obj.get("content", [])
            usage = response_obj.get("usage", {})
            response_id = response_obj.get("id", "")

            # Map response fields
            input_text = " ".join([msg.get("content", "") if isinstance(msg.get("content"), str)
                                 else msg.get("content", [{}])[0].get("text", "") for msg in messages])
            output_text = " ".join([c.get("text", "") for c in content if c.get("type") == "text"])

            # Log with detailed information
            logging.info(f"Logging completion to Arize - Model: {model}, ID: {response_id}, User: {user}")
            logging.info(f"Usage stats - Input tokens: {usage.get('input_tokens')}, Output tokens: {usage.get('output_tokens')}")

            # Create trace for Arize
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("llm_completion") as span:
                # Map model name to external_model_id format
                external_model_id = f"vertex_ai_{model.replace('/', '_').replace('-', '_')}"
                span.set_attribute("external_model_id", external_model_id)
                span.set_attribute("model", model)
                span.set_attribute("user", user)
                span.set_attribute("response_id", response_id)
                span.set_attribute("input_text", input_text)
                span.set_attribute("output_text", output_text)
                span.set_attribute("input_tokens", usage.get("input_tokens"))
                span.set_attribute("output_tokens", usage.get("output_tokens"))
                span.set_attribute("provider", "vertex_ai")

                # Add any additional metadata
                for key, value in metadata.items():
                    if isinstance(value, (str, int, float, bool)):
                        span.set_attribute(f"metadata_{key}", value)
        except Exception as e:
            logging.error(f"Failed to log success event to Arize: {e}", exc_info=True)

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        try:
            model = kwargs.get("model")
            messages = kwargs.get("messages", [])
            user = kwargs.get("user")
            exception_event = kwargs.get("exception")

            # Create trace for failed request
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("llm_completion_failure") as span:
                external_model_id = f"vertex_ai_{model.replace('/', '_').replace('-', '_')}"
                span.set_attribute("external_model_id", external_model_id)
                span.set_attribute("model", model)
                span.set_attribute("user", user)
                span.set_attribute("error", str(exception_event))
                span.set_attribute("provider", "vertex_ai")
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception_event)))

            logging.error(f"Logged failed completion to Arize - Model: {model}, User: {user}, Error: {exception_event}", exc_info=True)
        except Exception as e:
            logging.error(f"Failed to log failure event to Arize: {e}", exc_info=True)

    def log_stream_event(self, kwargs, response_obj, start_time, end_time):
        try:
            model = kwargs.get("model")
            messages = kwargs.get("messages", [])
            user = kwargs.get("user")

            # Create trace for stream event
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("llm_completion_stream") as span:
                external_model_id = f"vertex_ai_{model.replace('/', '_').replace('-', '_')}"
                span.set_attribute("external_model_id", external_model_id)
                span.set_attribute("model", model)
                span.set_attribute("user", user)
                span.set_attribute("provider", "vertex_ai")
                span.set_attribute("event_type", "stream")

            logging.info(f"Logged stream event to Arize - Model: {model}, User: {user}")
        except Exception as e:
            logging.error(f"Failed to log stream event to Arize: {e}", exc_info=True)

arize_callback_instance = ArizeCallback()
