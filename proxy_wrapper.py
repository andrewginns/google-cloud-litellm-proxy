#!/usr/bin/env python3
import os
import sys
from arize.otel import register
from openinference.instrumentation.litellm import LiteLLMInstrumentor

def setup_arize():
    space_id = os.getenv("ARIZE_SPACE_ID")
    api_key = os.getenv("ARIZE_API_KEY")

    if not space_id or not api_key:
        print("Warning: Arize credentials not found. Logging will be disabled.")
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
