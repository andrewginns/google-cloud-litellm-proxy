#!/usr/bin/env python3
from litellm.proxy.proxy_server import ProxyConfig, main
import asyncio
import os

# Set environment variables for authentication
os.environ["LITELLM_AUTH_REQUIRED"] = "false"
os.environ["LITELLM_REQUIRE_API_KEY"] = "false"

async def start_proxy():
    config = ProxyConfig()
    config.config_file_path = "./config.yaml"
    await main(config=config)

if __name__ == "__main__":
    asyncio.run(start_proxy())
