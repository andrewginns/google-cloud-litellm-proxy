#!/usr/bin/env python3
import os
import sys
from arize.otel import register
from openinference.instrumentation.litellm import LiteLLMInstrumentor
from google.cloud import secretmanager

def get_secret(secret_id):
    """Get secret from Secret Manager with fallback to environment variable."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{os.getenv('GOOGLE_CLOUD_PROJECT')}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Warning: Failed to get secret {secret_id} from Secret Manager: {e}")
        print(f"Note: GOOGLE_CLOUD_PROJECT environment variable is required for Secret Manager access")
        return None

def setup_arize():
    # Try Secret Manager first, then fall back to environment variables
    space_id = get_secret("ARIZE_TEST_SPACE_ID") or os.getenv("ARIZE_TEST_SPACE_ID")
    api_key = get_secret("ARIZE_TEST_API_KEY") or os.getenv("ARIZE_TEST_API_KEY")

    if not space_id or not api_key:
        print("Arize credentials (ARIZE_TEST_SPACE_ID, ARIZE_TEST_API_KEY) not found in Secret Manager or environment.")
        print("To enable Arize logging, either:")
        print("1. Configure credentials in Secret Manager (recommended) - requires GOOGLE_CLOUD_PROJECT")
        print("2. Set environment variables ARIZE_TEST_SPACE_ID and ARIZE_TEST_API_KEY")
        return

    try:
        tracer_provider = register(
            space_id=space_id,
            api_key=api_key,
            project_name="litellm-proxy",
        )
        LiteLLMInstrumentor().instrument(tracer_provider=tracer_provider)
        print("Arize logging initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize Arize logging: {e}")

def main():
    setup_arize()

    # Call litellm with all original arguments
    os.execvp("litellm", ["litellm"] + sys.argv[1:])

if __name__ == "__main__":
    main()
