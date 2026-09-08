# Amnesic Shell

> A stealthy, amnesic AI agent running securely inside a Linux terminal. 100% Keyless, zero footprint, and highly paranoid.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Dependencies](https://img.shields.io/badge/Dependencies-None%20(stdlib%20only)-brightgreen)
![Keyless](https://img.shields.io/badge/API_Key-Not_Required-success)

## What is Amnesic Shell?

**Amnesic Shell** is an autonomous, terminal-based AI assistant built for privacy and stealth. Designed for live boot Kali Linux environments (via VeraCrypt containers), it leaves absolutely zero footprint on the host system.

Powered entirely by **tgpt** (routing through free providers like Pollinations, Phind, and DuckDuckGo), it operates with a **100% Keyless Architecture**. You never need to register, log in, or provide an API key.

### Key Features

- 🕵️ **Zero Trace (In-Memory Bridge):** Conversation history lives exclusively in RAM and vanishes instantly upon exit. No configs or logs are written to disk.
- 🆓 **100% Keyless:** No Groq or OpenAI API keys required. It dynamically falls back between free LLM endpoints.
- ⚙️ **Paranoid Command Execution:** The AI can suggest Linux terminal commands. Every command is paused and requires explicit `/dev/tty` user consent (`y/N`) before running.
- 🛡️ **Anti-Prompt Injection:** Tool outputs (e.g., from `nmap` or `cat`) are strictly truncated and wrapped in system warnings to prevent rogue data from manipulating the AI.
- 🎨 **Interactive REPL & Piped Context:** Chat interactively or pipe files directly into the agent's brain (`cat file | python3 scripts/ghost-agent.py`).

---

## Setup & Usage

**Prerequisites:** Python 3.8+ (No `pip install` required)

```bash
# Clone the repository
git clone https://github.com/cadakerem/amnesic-shell.git
cd amnesic-shell
```

### 1. Interactive Mode
Launch the Ghost AI console to start chatting securely:
```bash
python3 scripts/ghost-agent.py
```

### 2. Hybrid Piped Mode
Pipe any file, log, or command output directly into the agent. It will analyze the data in-memory and then drop you into an interactive session:
```bash
nmap -sV 192.168.1.0/24 | python3 scripts/ghost-agent.py
```

---

## Architecture Overview

```text
[User Input / Piped Context]
              |
[tgpt Keyless API Router]  <-- Anonymous LLM (Pollinations, Phind, etc.)
              |
[Command Suggested?]
  ├── Yes ──> [Explicit y/N Consent via /dev/tty] 
  │                ├── Approved ──> [Execute] ──> [Sanitize Output] ──(loop)
  │                └── Denied   ──> [Skip]
  └── No  ──> [Final Answer Displayed to User]
```

---

## Privacy & OPSEC Notes

Amnesic Shell does not collect telemetry. However, standard OPSEC rules apply:
- **Network Routing:** For maximum anonymity, the agent routes traffic through **Tor** if available (`127.0.0.1:9050`). It forces `ALL_PROXY` environment variables into the `tgpt` engine.
- **Kill Switch:** Application-level proxying is not enough to prevent DNS leaks or raw socket leaks. Always use a transparent proxy with `iptables` rules that enforce a strict kill switch.

---

## Inspiration & Attribution

This project stands on the shoulders of giants:
- **[tgpt](https://github.com/aandrew-me/tgpt):** The core engine enabling our 100% keyless, zero-login LLM routing. Huge thanks to their work on maintaining access to free AI endpoints.
- **[can1357/oh-my-pi](https://github.com/can1357/oh-my-pi):** The `Ghost AI` (in-memory context bridging and isolated agent loop) architecture is deeply inspired by this project. While `oh-my-pi` is a massive Rust-based ecosystem, `amnesic-shell` takes its architectural ethos and distills it down into a dependency-free, zero-footprint Python implementation designed for live amnesic environments.
