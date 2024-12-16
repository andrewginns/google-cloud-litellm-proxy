#!/usr/bin/env python3
import os
import sys
import logging
from arize.otel import register
from openinference.instrumentation.litellm import LiteLLMInstrumentor
from google.cloud import secretmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_secret(secret_id):
    """Get secret from Secret Manager with fallback to environment variable."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{os.getenv('GOOGLE_CLOUD_PROJECT')}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logger.error(f"Failed to get secret {secret_id} from Secret Manager: {e}")
        logger.info("Note: GOOGLE_CLOUD_PROJECT environment variable is required for Secret Manager access")
        return None

def setup_arize():
    logger.info("Starting Arize setup...")

    # Try Secret Manager first, then fall back to environment variables
    space_id = get_secret("ARIZE_TEST_SPACE_ID") or os.getenv("ARIZE_TEST_SPACE_ID")
    api_key = get_secret("ARIZE_TEST_API_KEY") or os.getenv("ARIZE_TEST_API_KEY")

    if not space_id or not api_key:
        logger.error("Arize credentials not found in Secret Manager or environment")
        logger.info("To enable Arize logging, either:")
        logger.info("1. Configure credentials in Secret Manager (recommended) - requires GOOGLE_CLOUD_PROJECT")
        logger.info("2. Set environment variables ARIZE_TEST_SPACE_ID and ARIZE_TEST_API_KEY")
        return False

    try:
        logger.info("Initializing Arize tracer provider...")
        tracer_provider = register(
            space_id=space_id,
            api_key=api_key,
            project_name="litellm-tracing",  # Match example project name
        )
        logger.info("Instrumenting LiteLLM...")
        LiteLLMInstrumentor().instrument(tracer_provider=tracer_provider)
        logger.info("Arize logging initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Arize logging: {e}")
        return False

def main():
    if not setup_arize():
        logger.warning("Continuing without Arize logging")

    logger.info("Starting LiteLLM proxy...")
    # Use subprocess.run instead of execvp to maintain instrumentation
    import subprocess
    subprocess.run(["litellm"] + sys.argv[1:])

if __name__ == "__main__":
    main()
