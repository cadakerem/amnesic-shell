#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Amnesic Shell v2.4 — Anonymous Linux Terminal AI Agent
=======================================================
Usage:
  python3 agent.py              # anonymous mode (OVHcloud, no key)
  python3 agent.py --key KEY    # start with Groq key (skip setup)
  python3 agent.py --help       # show this help

Features:
  - Primary API : OVHcloud AI (anonymous, no key/login, Llama 3.3 70B)
  - Fallback API: Groq         (fast, free tier, key required)
  - Tools       : bash, file read/write/delete/list, URL fetch
  - Memory      : multi-turn conversation history in RAM (wiped on exit)
  - Config      : Groq key stored in amnesic.conf next to agent.py
  - Portable    : single file, zero dependencies (Python 3.8+ stdlib only)
"""
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    try:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os, re, sys, json, subprocess, urllib.request, urllib.error
from shutil import get_terminal_size

# ─────────────────────────────────────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

AGENT_NAME     = "Amnesic"
VERSION        = "2.4"
MAX_HISTORY    = 30
TOOL_TIMEOUT   = 30
MAX_TOOL_LOOPS = 6

# Config file lives next to agent.py (inside VeraCrypt vault)
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "amnesic.conf")

# OVHcloud — fully anonymous, no key required
OVH_URL   = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions"
OVH_MODEL = "Meta-Llama-3_3-70B-Instruct"

# Groq — fast, free tier, key required
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# ANSI colours
R   = "\033[0m"       # reset
CU  = "\033[94m"      # user prompt  (blue)
CA  = "\033[92m"      # agent reply  (green)
CT  = "\033[93m"      # tool name    (yellow)
CW  = "\033[33m"      # warning      (amber)
CE  = "\033[91m"      # error        (red)
CD  = "\033[90m"      # dim / muted  (grey)
CB  = "\033[1m"       # bold
CC  = "\033[96m"      # cyan accent

# ─────────────────────────────────────────────────────────────────────────────
#  SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Amnesic Shell, a powerful, privacy-focused AI agent running in a Linux terminal.
Help the user with any task by using the tools available to you.

== TOOL CALL FORMAT ==
When a task requires using a tool, output EXACTLY this XML block:

<tool>
<name>TOOL_NAME</name>
<input>TOOL_INPUT</input>
</tool>

You may call multiple tools in one response — they run sequentially.
After all results are returned, write your final answer clearly.

== AVAILABLE TOOLS ==

bash         Run any bash shell command.
             Input : shell command string
             Note  : warn the user before destructive commands (rm -rf, dd, mkfs…)
             Eg    : <tool><name>bash</name><input>df -h && free -h</input></tool>

file_read    Read and return the content of a file.
             Input : absolute or ~ path
             Eg    : <tool><name>file_read</name><input>/etc/os-release</input></tool>

file_write   Write content to a file (creates missing directories).
             Input : PATH|||CONTENT   (||| separates path from content)
             Eg    : <tool><name>file_write</name><input>/tmp/scan.sh|||#!/bin/bash
nmap -sV 192.168.1.0/24</input></tool>

file_delete  Permanently delete a file.
             Input : file path
             Eg    : <tool><name>file_delete</name><input>/tmp/scan.sh</input></tool>

file_list    List the contents of a directory.
             Input : directory path  (use . for current dir)
             Eg    : <tool><name>file_list</name><input>/home/kali</input></tool>

fetch_url    Fetch the text content of a URL.
             Input : full URL (https://...)
             Eg    : <tool><name>fetch_url</name><input>https://ifconfig.me</input></tool>

== RULES ==
1. Always respond in the same language the user writes in.
2. Be concise but thorough.
3. Warn before any destructive operation.
4. Never suggest creating online accounts or entering personal data.
5. Context: Kali Linux environment, the user values privacy and anonymity.
"""

# ─────────────────────────────────────────────────────────────────────────────
#  TOOLS
# ─────────────────────────────────────────────────────────────────────────────

def tool_bash(cmd: str) -> str:
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=TOOL_TIMEOUT, executable="/bin/bash"
        )
        out = (r.stdout or "").rstrip()
        err = (r.stderr or "").rstrip()
        combined = out + ("\n[stderr]: " + err if err else "")
        return combined.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"[ERROR] Command timed out after {TOOL_TIMEOUT}s."
    except FileNotFoundError:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=TOOL_TIMEOUT)
            out = (r.stdout or "") + (r.stderr or "")
            return out.strip() or "(no output)"
        except Exception as e:
            return f"[ERROR] {e}"
    except Exception as e:
        return f"[ERROR] {e}"

def tool_file_read(path: str) -> str:
    try:
        p = os.path.expanduser(path.strip())
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            c = f.read()
        if len(c) > 6000:
            c = c[:6000] + f"\n\n[... {len(c)} chars total, truncated]"
        return c or "(empty file)"
    except Exception as e:
        return f"[ERROR] {e}"

def tool_file_write(inp: str) -> str:
    if "|||" not in inp:
        return "[ERROR] Wrong format. Use: PATH|||CONTENT"
    path, content = inp.split("|||", 1)
    path = os.path.expanduser(path.strip())
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[OK] Written {len(content)} chars to '{path}'"
    except Exception as e:
        return f"[ERROR] {e}"

def tool_file_delete(path: str) -> str:
    path = os.path.expanduser(path.strip())
    try:
        os.remove(path)
        return f"[OK] Deleted '{path}'"
    except Exception as e:
        return f"[ERROR] {e}"

def tool_file_list(path: str) -> str:
    path = os.path.expanduser(path.strip()) or "."
    try:
        entries = sorted(os.listdir(path))
        lines = []
        for e in entries:
            full = os.path.join(path, e)
            if os.path.isdir(full):
                lines.append(f"  {CD}[dir]{R}  {e}/")
            else:
                try:
                    sz = _fmt_size(os.path.getsize(full))
                    lines.append(f"  {CD}[file]{R} {e}  {CD}({sz}){R}")
                except OSError:
                    lines.append(f"  {CD}[file]{R} {e}")
        return "\n".join(lines) if lines else "(empty directory)"
    except Exception as e:
        return f"[ERROR] {e}"

def tool_fetch_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            c = r.read().decode("utf-8", errors="replace")
        c = re.sub(r"<[^>]+>", " ", c)
        c = re.sub(r"\s{2,}", " ", c).strip()
        return (c[:4000] + "\n[... content truncated]") if len(c) > 4000 else c
    except urllib.error.HTTPError as e:
        return f"[HTTP {e.code}] {e.reason}"
    except Exception as e:
        return f"[ERROR] {e}"

def _fmt_size(n: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} GB"

TOOLS = {
    "bash":        tool_bash,
    "file_read":   tool_file_read,
    "file_write":  tool_file_write,
    "file_delete": tool_file_delete,
    "file_list":   tool_file_list,
    "fetch_url":   tool_fetch_url,
}

# ─────────────────────────────────────────────────────────────────────────────
#  API — OVHcloud (anonymous) + Groq (fallback)
# ─────────────────────────────────────────────────────────────────────────────

class AmnesicAPI:
    def __init__(self, groq_key: str | None = None):
        self.groq_key  = groq_key
        self.ovh_ok    = True
        self.groq_ok   = bool(groq_key)
        self._last_warn = ""

    def call(self, messages: list) -> str:
        # 1) Try OVHcloud (anonymous)
        if self.ovh_ok:
            result, err_type = self._post(OVH_URL, OVH_MODEL, messages, headers={})
            if err_type == "ok":
                return result
            elif err_type == "rate_limit":
                self.ovh_ok = False
                self._warn(
                    "OVHcloud rate limit reached (2 req/min).",
                    "Switching to Groq..." if self.groq_key else "Add a Groq key: save-key YOUR_KEY"
                )
            else:
                self._warn(f"OVHcloud error: {result[:80]}", "Trying Groq..." if self.groq_key else "")

        # 2) Try Groq (if key available)
        if self.groq_key and self.groq_ok:
            result, err_type = self._post(
                GROQ_URL, GROQ_MODEL, messages,
                headers={"Authorization": f"Bearer {self.groq_key}"}
            )
            if err_type == "ok":
                return result
            elif err_type == "rate_limit":
                self.groq_ok = False
                self._warn(
                    "Groq rate limit or daily quota reached.",
                    "Quota resets daily. OVHcloud will be retried next message."
                )
                self.ovh_ok = True
                return self._dead()
            elif err_type == "auth":
                self.groq_ok = False
                self._warn("Groq key is invalid or expired.", "Get a new key at: console.groq.com")
                return self._dead()
            else:
                self._warn(f"Groq error: {result[:80]}", "")
                return self._dead()

        return self._dead()

    def status(self) -> str:
        o = f"{CA}active{R}"  if self.ovh_ok  else f"{CE}limited{R}"
        if not self.groq_key:
            g = f"{CD}no key{R}"
        elif self.groq_ok:
            g = f"{CA}active{R}"
        else:
            g = f"{CE}limited{R}"
        return f"OVHcloud {o}   Groq {g}"

    def set_groq_key(self, key: str):
        self.groq_key = key.strip()
        self.groq_ok  = bool(self.groq_key)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _post(self, url: str, model: str, messages: list, headers: dict) -> tuple:
        payload = json.dumps(
            {
                "model": model,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                "max_tokens": 1500,
                "temperature": 0.65,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        h = {"Content-Type": "application/json"}
        h.update(headers)
        req = urllib.request.Request(url, data=payload, headers=h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip(), "ok"
        except urllib.error.HTTPError as e:
            body = ""
            try: body = e.read().decode("utf-8", "replace")
            except: pass
            if e.code == 429:
                return body[:120], "rate_limit"
            if e.code in (401, 403):
                return body[:120], "auth"
            return f"HTTP {e.code}: {body[:120]}", "error"
        except Exception as e:
            return str(e)[:120], "error"

    def _warn(self, msg: str, hint: str = ""):
        if msg == self._last_warn:
            return
        self._last_warn = msg
        print(f"\n{CW}  ! {msg}{R}")
        if hint:
            print(f"{CD}    > {hint}{R}")

    def _dead(self) -> str:
        w = 50
        if not self.groq_key:
            tip = f"  Add a key: {CW}save-key YOUR_KEY{R}"
        else:
            tip = f"  Wait a moment and try again."
        print(f"\n{CE}  {'─' * w}{R}")
        print(f"{CE}  No API is available right now.{R}")
        print(tip)
        print(f"{CE}  {'─' * w}{R}")
        return "__DEAD__"

# ─────────────────────────────────────────────────────────────────────────────
#  TOOL PARSER
# ─────────────────────────────────────────────────────────────────────────────

_TOOL_RE = re.compile(
    r"<tool>\s*<name>\s*(.*?)\s*</name>\s*<input>(.*?)</input>\s*</tool>",
    re.DOTALL | re.IGNORECASE,
)

def run_tools(response: str) -> tuple:
    matches = _TOOL_RE.findall(response)
    if not matches:
        return "", False
    results = []
    for name, inp in matches:
        name, inp = name.strip(), inp.strip()
        print(f"\n{CT}  >> {name}{R}  {CD}{inp[:80]}{R}", flush=True)
        fn = TOOLS.get(name)
        result = fn(inp) if fn else f"[ERROR] Unknown tool '{name}'. Valid: {', '.join(TOOLS)}"
        print(f"{CD}  << done{R}", flush=True)
        results.append(f"[{name}]:\n{result}")
    return "\n\n".join(results), True

def clean_response(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", _TOOL_RE.sub("", text)).strip()

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG  (amnesic.conf lives next to agent.py inside the vault)
# ─────────────────────────────────────────────────────────────────────────────

def cfg_load() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"{CW}  [config read error] {e}{R}")
        return {}

def cfg_save(data: dict) -> bool:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"{CW}  [config write error] {e}{R}")
        return False

def cfg_set_key(key: str) -> bool:
    d = cfg_load()
    d["groq_key"] = key
    ok = cfg_save(d)
    if ok:
        print(f"  {CA}Key saved to amnesic.conf{R}  {CD}(encrypted inside vault when locked){R}")
    return ok

def cfg_forget_key() -> bool:
    d = cfg_load()
    if "groq_key" not in d:
        print(f"  {CD}No key stored in config.{R}")
        return False
    del d["groq_key"]
    ok = cfg_save(d)
    if ok:
        print(f"  {CA}Key removed from config.{R}")
    return ok

# ─────────────────────────────────────────────────────────────────────────────
#  UI HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _w() -> int:
    return min(get_terminal_size().columns, 70)

def banner():
    w = _w()
    print(f"""
{CC}{CB}                █████╗ ███╗   ███╗███╗   ██╗███████╗███████╗██╗ ██████╗ 
                ██╔══██╗████╗ ████║████╗  ██║██╔════╝██╔════╝██║██╔════╝ 
                ███████║██╔████╔██║██╔██╗ ██║█████╗  ███████╗██║██║      
                ██╔══██║██║╚██╔╝██║██║╚██╗██║██╔══╝  ╚════██║██║██║      
                ██║  ██║██║ ╚═╝ ██║██║ ╚████║███████╗███████║██║╚██████╗ 
                ╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝╚═╝ ╚═════╝ 
                          ███████╗██╗  ██╗███████╗██╗     ██╗            
                          ██╔════╝██║  ██║██╔════╝██║     ██║            
                          ███████╗███████║█████╗  ██║     ██║            
                          ╚════██║██╔══██║██╔══╝  ██║     ██║            
                          ███████║██║  ██║███████╗███████╗███████╗       
                          ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝{R}
{CD}                             v{VERSION}   //   Anonymous AI Terminal{R}
""")

def div():
    print(f"\n{CD}  {'─' * (_w() - 4)}{R}")

def first_run():
    """Show only on first launch (no config). Returns groq_key or None."""
    w = _w()
    print(f"""
{CC}  ┌{'─' * (w - 4)}┐
  │{'  FIRST RUN SETUP — GROQ API KEY (OPTIONAL)'.center(w - 4)}│
  └{'─' * (w - 4)}┘{R}

  {CB}Primary API :{R}  OVHcloud  {CD}(anonymous, no key, 2 req/min){R}
  {CB}Fallback API:{R}  Groq      {CD}(fast, free tier — just needs an API key){R}

  When OVHcloud hits its rate limit, Amnesic Shell automatically switches to Groq.
  If you add a key now, it will be {CA}saved to amnesic.conf{R} inside the vault
  and loaded automatically on every future launch — you won't be asked again.

  {CD}Get a free Groq key at: console.groq.com  (email only, ~1 min){R}
""")
    try:
        key = input(f"  {CC}Enter Groq key{R}  {CD}(or press ENTER to skip):{R}  ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        key = ""

    if key:
        cfg_set_key(key)
        return key
    else:
        print(f"\n  {CD}Skipped. Running anonymous-only mode.")
        print(f"  You can add a key later by typing:  save-key YOUR_KEY{R}\n")
        return None

def show_help(api: AmnesicAPI):
    key_s = f"{CA}stored (amnesic.conf){R}" if api.groq_key else f"{CD}none  (anonymous mode){R}"
    print(f"""
{CB}  Status{R}
  {api.status()}
  Groq key   {key_s}
  Config     {CD}{CONFIG_FILE}{R}

{CB}  Key Management{R}
  {CC}save-key{R}  KEY    Save key permanently to vault (amnesic.conf)
  {CC}forget-key{R}       Remove saved key — revert to anonymous mode
  {CC}groq-key{R}  KEY    Use key this session only (not saved)

{CB}  Session{R}
  {CC}status{R}           Show detailed API + session info
  {CC}reset{R}            Clear conversation history
  {CC}clear{R}            Clear the terminal screen
  {CC}help{R}   {CC}?{R}        This help
  {CC}exit{R}             Quit Amnesic Shell

{CB}  What Amnesic Shell can do{R}
  Run shell commands         "what kernel version is this?"
  Read / write / delete files  "create a Python port scanner and save it"
  Browse directories         "what's in /home/kali?"
  Fetch URLs                 "fetch ifconfig.me — what's my IP?"
  Multi-turn memory          remembers the entire conversation (RAM only)
""")

# ─────────────────────────────────────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    cli_key = None

    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    if "--key" in args:
        idx = args.index("--key")
        try:
            cli_key = args[idx + 1]
        except IndexError:
            print("Usage: python3 agent.py --key GROQ_KEY")
            sys.exit(1)

    banner()

    # ── Key loading priority: CLI > amnesic.conf > first-run setup ──
    if cli_key:
        groq_key = cli_key
        print(f"  {CD}Key: provided via CLI argument.{R}\n")
    else:
        cfg = cfg_load()
        if cfg.get("groq_key"):
            groq_key = cfg["groq_key"]
            print(f"  {CA}Groq key loaded from amnesic.conf.{R}\n")
        else:
            groq_key = first_run()

    api = AmnesicAPI(groq_key=groq_key)
    mode = "OVHcloud + Groq fallback" if groq_key else "OVHcloud anonymous"
    print(f"  {CD}Mode: {mode}   |   type {CC}help{CD} for commands   |   {CC}exit{CD} to quit{R}\n")

    conversation: list[dict] = []

    while True:
        try:
            raw = input(f"\n{CU}  you >{R} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n  {CD}Amnesic Shell shutting down. Memory cleared.{R}\n")
            sys.exit(0)

        if not raw:
            continue

        cmd = raw.lower().strip()

        # ── Built-in commands ─────────────────────────────────────────────────

        if cmd in ("exit", "quit", "bye", "q"):
            print(f"\n  {CD}Amnesic Shell shutting down. Memory cleared.{R}\n")
            sys.exit(0)

        if cmd in ("clear", "cls"):
            os.system("clear" if os.name != "nt" else "cls")
            banner()
            continue

        if cmd in ("reset",):
            conversation.clear()
            print(f"  {CD}Conversation history cleared.{R}")
            continue

        if cmd in ("help", "?"):
            show_help(api)
            continue

        if cmd == "status":
            print(f"\n  {api.status()}")
            print(f"  Config     {CD}{CONFIG_FILE}{R}")
            print(f"  Groq key   {CA + 'saved' + R if api.groq_key else CD + 'none' + R}")
            print(f"  History    {len(conversation) // 2} turn(s)")
            continue

        if cmd.startswith("save-key"):
            parts = raw.split(maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                k = parts[1].strip()
                api.set_groq_key(k)
                api.groq_ok = True
                cfg_set_key(k)
            else:
                print(f"  {CW}Usage: save-key YOUR_KEY{R}")
            continue

        if cmd == "forget-key":
            cfg_forget_key()
            api.set_groq_key("")
            print(f"  {CD}Switched to anonymous mode for this session.{R}")
            continue

        if cmd.startswith("groq-key"):
            parts = raw.split(maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                api.set_groq_key(parts[1].strip())
                api.groq_ok = True
                print(f"  {CA}Key active for this session.{R}  {CD}(not saved — use save-key to persist){R}")
            else:
                print(f"  {CW}Usage: groq-key YOUR_KEY{R}")
            continue

        # ── Conversation ──────────────────────────────────────────────────────

        if len(conversation) > MAX_HISTORY:
            conversation = conversation[-MAX_HISTORY:]

        conversation.append({"role": "user", "content": raw})
        print(f"\n{CD}  thinking...{R}", end="", flush=True)

        for _ in range(MAX_TOOL_LOOPS):
            response = api.call(conversation)

            if response == "__DEAD__":
                if conversation and conversation[-1]["role"] == "user":
                    conversation.pop()
                break

            tool_out, had_tools = run_tools(response)

            if not had_tools:
                final = clean_response(response)
                div()
                print(f"\n{CA}  {AGENT_NAME} >{R} {final}\n")
                conversation.append({"role": "assistant", "content": response})
                break
            else:
                conversation.append({"role": "assistant", "content": response})
                conversation.append({
                    "role": "user",
                    "content": f"Tool results:\n{tool_out}\n\nNow give the user a clear final answer."
                })
                print(f"\n{CD}  processing...{R}", end="", flush=True)
        else:
            print(f"\n{CA}  {AGENT_NAME} >{R}  {CW}Max tool iterations reached.{R}\n")

if __name__ == "__main__":
    main()