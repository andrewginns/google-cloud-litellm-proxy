#!/usr/bin/env python3
from litellm.proxy.proxy_server import ProxyConfig, main
import asyncio
import os

async def start_proxy():
    config = ProxyConfig()
    config.auth_required = False
    config.require_api_key = False
    config.database_url = ""
    config.use_background_health_checks = False
    config.config_file_path = "./config.yaml"
    await main(config=config)

if __name__ == "__main__":
    asyncio.run(start_proxy())
