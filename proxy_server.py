#!/usr/bin/env python3
from litellm import completion
from litellm.callbacks.base_callback import BaseCallback
from fastapi import FastAPI, Request
from typing import Optional, List, Dict, Any
import asyncio
import os
import yaml
import sys
from arize_callback import arize_callback_instance

# Create FastAPI app
app = FastAPI()

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Initialize LiteLLM with callbacks
from litellm import LiteLLM
LiteLLM.callbacks = [arize_callback_instance]
LiteLLM.set_verbose = True

@app.post("/chat/completions")
async def chat_completion(request: Request):
    try:
        body = await request.json()
        model = body.get("model", "vertex_ai/mistral-large@2407")
        messages = body.get("messages", [])

        # Call LiteLLM directly with callback
        response = await completion(
            model=model,
            messages=messages,
            api_base="",  # Use default Vertex AI endpoint
            timeout=15
        )
        return response
    except Exception as e:
        print(f"Error in chat completion: {str(e)}", file=sys.stderr)
        raise

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
