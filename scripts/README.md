# Ghost AI Agent

This directory contains the `ghost-agent.py` script, which serves as the core logic for the Amnesic Ghost AI Framework.

## Features
1. **Zero Footprint**: Receives all context entirely via standard input (stdin). No files are read from disk by the agent itself, and no history is written.
2. **Tor-Routed**: Uses `curl --socks5-hostname 127.0.0.1:9050` to route API requests (to Groq/Nvidia NIM) securely over the Tor network. DNS resolution is also tunneled.
3. **Environment Isolated**: API keys are expected to be set via environment variables (e.g. `GHOST_API_KEY`) ensuring no sensitive data is stored in config files.

## Usage
Provide the necessary environment variables and pipe your context into the agent:

```bash
export GHOST_API_KEY="your_api_key_here"
cat your_code.py | python3 scripts/ghost-agent.py
```
