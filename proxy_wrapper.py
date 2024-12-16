#!/usr/bin/env python3
import subprocess
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

logger = logging.getLogger(__name__)

def main():
    logger.info("Starting LiteLLM proxy...")
    try:
        # Pass through all command line arguments to litellm
        cmd = ["litellm"] + sys.argv[1:]
        if not any("--config" in arg for arg in cmd):
            cmd.extend(["--config", "config.yaml"])

        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start LiteLLM proxy: {e}")
        sys.exit(e.returncode)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
