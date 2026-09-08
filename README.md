# Amnesic Shell

> A stealthy, amnesic AI agent running securely inside a Linux terminal via Groq API.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Dependencies](https://img.shields.io/badge/Dependencies-None%20(stdlib%20only)-brightgreen)

## What is Amnesic Shell?

**Amnesic Shell** is an autonomous, terminal-based AI assistant built for privacy and stealth. Originally designed for live boot Kali Linux environments (via VeraCrypt containers), it leaves absolutely zero footprint on the host system.

Powered strictly by **Groq API** (`llama-3.3-70b-versatile`), it is extremely fast and capable of interacting directly with your local system using native Linux tools.

### Key Features

- 🕵️ **Zero Trace:** Conversation history lives exclusively in RAM and vanishes instantly upon exit.
- ⚙️ **Native Linux Execution:** Executes `bash` commands, manages files, and reads directory structures locally.
- 🌐 **Web Access:** Can fetch and summarize raw text from websites.
- 🔒 **Encrypted Config:** Saves the optional API key locally (`amnesic.conf`), intended to be locked away inside an encrypted vault.
- 📦 **Zero Dependencies:** Relies strictly on the Python 3 standard library. No `pip install` required.
- 🎨 **Minimalist ANSI UI:** Hardcore, distraction-free terminal aesthetic.

---

## Setup & Usage

**Prerequisites:** Python 3.8+

```bash
# Clone the repository
git clone https://github.com/cadakerem/amnesic-shell.git
cd amnesic-shell

# Run the agent
python3 agent.py
```

### First Run & Configuration

On the very first launch, the shell will prompt you to enter a **Groq API Key**.
- You can get a free, fast API key from [console.groq.com](https://console.groq.com).
- Once entered, your key is safely stored in `amnesic.conf` in the exact same directory as the script. (Ideally, this directory should be mounted from an encrypted VeraCrypt volume).

### Built-in Agent Commands

Inside the shell, you can type special commands:
- `help` - View current API status, tool list, and key management commands.
- `save-key <KEY>` - Manually save or update your Groq API key.
- `forget-key` - Delete the `amnesic.conf` file to purge the API key from disk.
- `exit` or `quit` - Terminate the shell instantly.

---

## Capabilities (Tool Call System)

The AI dynamically uses tools to interact with your OS. It follows a pure ReAct (Reasoning and Acting) loop to autonomously solve complex tasks.

| Tool | Capability | Example Prompt |
|------|------------|----------------|
| `bash` | Executes arbitrary terminal commands | *"What is the current OS version?"* |
| `file_read` | Reads content from the file system | *"Read and summarize /var/log/syslog"* |
| `file_write` | Creates and writes to files | *"Write a python port scanner to scan.py"* |
| `file_delete` | Removes a specific file | *"Delete temp.txt"* |
| `file_list` | Lists the contents of a directory | *"What's inside /home/user?"* |
| `fetch_url` | Pulls raw content from a webpage | *"Fetch example.com and analyze it"* |

---

## Architecture Overview

```text
[User Input]
       |
[Groq API (Llama 3.3 70B)]  <-- High-speed LLM reasoning
       |
[Tool Call Needed?]
  ├── Yes ──> [Execute Local Tool] ──> [Send Output to API] ──(loop)
  └── No  ──> [Final Answer Displayed to User]
```

---

## Privacy & OPSEC Notes

Amnesic Shell does not collect telemetry. However, standard OPSEC rules apply:
- **API Endpoint:** Your prompts are sent to Groq or Nvidia NIM. Do not send highly sensitive personal data.
- **Network Routing:** For maximum anonymity, the experimental `ghost-agent.py` routes traffic through **Tor** (via `curl --socks5-hostname`). However, due to strict Web Application Firewalls (WAF) blocking Tor exit nodes, you may need to use rotating residential proxies, VPS, or obfs4 bridges if you encounter `Connection Reset` errors.
- **Kill Switch:** Application-level proxying (`torsocks`) is not enough to prevent DNS leaks or raw socket leaks. Always use a transparent proxy with `iptables` rules that enforce a strict kill switch.

---

## Inspiration & Attribution

The `Ghost AI` (in-memory context bridging and agent isolation) architecture is deeply inspired by [can1357/oh-my-pi](https://github.com/can1357/oh-my-pi). While `oh-my-pi` is a massive Rust-based project, `amnesic-shell` takes its architectural ethos and distills it down into a dependency-free, zero-footprint Python/Bash implementation designed for live amnesic environments.

---

## License

MIT License
