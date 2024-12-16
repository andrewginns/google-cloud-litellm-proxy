import logging
import os
from typing import Optional, Callable
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import SpanKind
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION, DEPLOYMENT_ENVIRONMENT
from litellm.proxy._types import CustomLogger
from litellm.proxy.proxy_config import ProxyConfig

class ArizeCallback(CustomLogger):
    def __init__(self):
        try:
            logging.info("Setting up Arize logging...")
            self._model_name = None  # Initialize model name
            self.setup_arize()
        except Exception as e:
            logging.error(f"Failed to initialize Arize logging: {e}", exc_info=True)

    def setup_arize(self):
        try:
            # Configure base resource attributes
            base_attributes = {
                SERVICE_NAME: "litellm-proxy",
                SERVICE_VERSION: "1.0.0",
                DEPLOYMENT_ENVIRONMENT: "production",
                "external.model.id": "vertex_ai_gemini_pro",  # Required by Arize
                "model.provider": "vertex_ai",  # Required by Arize
            }

            # Create base resource
            base_resource = Resource.create(base_attributes)
            logging.info(f"Created base resource with attributes: {base_attributes}")

            # Configure OTLP exporter with headers
            headers = [
                (b"x-api-key", os.getenv("ARIZE_TEST_API_KEY", "demo").encode()),
                (b"space-id", os.getenv("ARIZE_TEST_SPACE_ID", "demo").encode()),
            ]
            logging.info(f"Using OTLP headers: {headers}")

            otlp_exporter = OTLPSpanExporter(
                endpoint="otlp.arize.com:443",
                insecure=False,
                headers=headers,
            )

            # Create and register LoggingSpanProcessor for debugging
            class LoggingSpanProcessor(BatchSpanProcessor):
                def _export(self, spans):
                    try:
                        for span in spans:
                            # Log the resource attributes
                            resource_attrs = span.resource.attributes if span.resource else {}
                            logging.info(f"Span resource attributes: {resource_attrs}")
                            # Log the span attributes
                            logging.info(f"Span attributes: {span.attributes}")
                            logging.info(f"Exporting span: {span.name}")
                        return super()._export(spans)
                    except Exception as e:
                        logging.error(f"Error exporting spans: {e}", exc_info=True)
                        return False

            # Initialize tracer provider with base resource
            provider = TracerProvider(resource=base_resource)

            # Add processors to provider
            provider.add_span_processor(LoggingSpanProcessor(otlp_exporter))

            # Set global tracer provider
            trace.set_tracer_provider(provider)

            # Get tracer
            self.tracer = trace.get_tracer(__name__)

            # Initialize HTTPX instrumentation
            HTTPXClientInstrumentor().instrument()

            logging.info("Successfully set up Arize logging with OpenTelemetry")
        except Exception as e:
            logging.error(f"Error in setup_arize: {e}", exc_info=True)
            raise

    async def async_log_success_event(
        self,
        kwargs: dict,
        response_obj: dict,
        start_time: float,
        end_time: float,
        print_verbose: Optional[Callable] = None,
    ):
        try:
            # Extract model information
            model = kwargs.get("model", "")
            messages = kwargs.get("messages", [])

            # Create span with required attributes
            with self.tracer.start_as_current_span(
                name="litellm.completion.success",
                kind=SpanKind.CLIENT,
                attributes={
                    "external.model.id": "vertex_ai_gemini_pro",
                    "model.provider": "vertex_ai",
                    "model": model,
                    "messages": str(messages),
                    "response": str(response_obj),
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration_ms": (end_time - start_time) * 1000,
                }
            ) as span:
                # Log span creation
                logging.info(f"Created success span with attributes: {span.attributes}")

                # Add response-specific attributes
                if hasattr(response_obj, "choices") and len(response_obj.choices) > 0:
                    choice = response_obj.choices[0]
                    if hasattr(choice, "message"):
                        span.set_attribute("response_message", str(choice.message))
                    if hasattr(choice, "finish_reason"):
                        span.set_attribute("finish_reason", choice.finish_reason)

                # Add usage information if available
                if hasattr(response_obj, "usage"):
                    usage = response_obj.usage
                    span.set_attribute("prompt_tokens", getattr(usage, "prompt_tokens", 0))
                    span.set_attribute("completion_tokens", getattr(usage, "completion_tokens", 0))
                    span.set_attribute("total_tokens", getattr(usage, "total_tokens", 0))

                # Add any safety results if available
                if hasattr(response_obj, "vertex_ai_safety_results"):
                    span.set_attribute("safety_results", str(response_obj.vertex_ai_safety_results))

                logging.info("Successfully logged completion event to Arize")

        except Exception as e:
            logging.error(f"Error in async_log_success_event: {e}", exc_info=True)
            # Don't raise the exception to avoid affecting the main request flow
            pass

    async def async_log_failure_event(self,
                                    kwargs,
                                    error,
                                    start_time,
                                    end_time,
                                    print_verbose):
        try:
            # Create span for failure event
            with self.tracer.start_as_current_span(
                name="litellm.completion.failure",
                kind=SpanKind.CLIENT,
                attributes={
                    "external.model.id": "vertex_ai_gemini_pro",
                    "model.provider": "vertex_ai",
                    "model": kwargs.get("model", ""),
                    "error": str(error),
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration_ms": (end_time - start_time) * 1000,
                }
            ) as span:
                logging.info(f"Created failure span with attributes: {span.attributes}")
                logging.info("Successfully logged failure event to Arize")
        except Exception as e:
            logging.error(f"Error in async_log_failure_event: {e}", exc_info=True)
            pass

    def log_stream_event(self,
                        kwargs,
                        response_obj,
                        start_time,
                        end_time,
                        print_verbose):
        try:
            # Create span for stream event
            with self.tracer.start_as_current_span(
                name="litellm.completion.stream",
                kind=SpanKind.CLIENT,
                attributes={
                    "external.model.id": "vertex_ai_gemini_pro",
                    "model.provider": "vertex_ai",
                    "model": kwargs.get("model", ""),
                    "response": str(response_obj),
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration_ms": (end_time - start_time) * 1000,
                }
            ) as span:
                logging.info(f"Created stream span with attributes: {span.attributes}")
                logging.info("Successfully logged stream event to Arize")
        except Exception as e:
            logging.error(f"Error in log_stream_event: {e}", exc_info=True)
            pass

arize_callback_instance = ArizeCallback()
