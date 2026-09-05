#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Amnesic Shell v2.4 — Anonymous Linux Terminal AI Agent (Powered by tgpt)
=======================================================
Usage:
  python3 agent.py              # runs via tgpt (pollinations/phind/isou, no key needed)
  python3 agent.py --help       # show this help

Features:
  - Primary API : tgpt Auto-Router (Zero keys, Zero login)
  - Tools       : bash, file read/write/delete/list, URL fetch
  - Memory      : multi-turn conversation history in RAM (wiped on exit)
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
TOOL_TIMEOUT   = 60
MAX_TOOL_LOOPS = 6

# Config file lives next to agent.py (inside VeraCrypt vault)
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "amnesic.conf")

# OVHcloud — fully anonymous, no key required
OVH_URL   = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions"
OVH_MODEL = "Meta-Llama-3_3-70B-Instruct"


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

search_tools Search installed Linux tools whose man page matches a keyword (uses apropos).
             Input : a single keyword (e.g. wifi, password, sql, network)
             Eg    : <tool><name>search_tools</name><input>wifi</input></tool>

== RULES ==
1. Always respond in the same language the user writes in.
2. Be concise but thorough.
3. Warn before any destructive operation.
4. Never suggest creating online accounts or entering personal data.
5. Context: Kali Linux environment, the user values privacy and anonymity.
6. If the user names a domain/category (e.g. "wifi", "password cracking") without naming
   a specific tool, use search_tools first to see what's installed, present the options,
   and wait for the user to pick one and name a target before running anything with bash.
7. For continuous or long-running commands (e.g. airodump-ng, ping, top), they will
   block the shell. You MUST wrap them in a timeout command (e.g., `timeout 15 airodump-ng wlan0`)
   so they terminate gracefully and return output.
8. DO NOT hallucinate or guess tools. If you present options to the user, ONLY present
   the exact tools that were returned by your search_tools query.
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
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "")
        if isinstance(out, bytes): out = out.decode('utf-8', 'replace')
        err = (e.stderr or "")
        if isinstance(err, bytes): err = err.decode('utf-8', 'replace')
        combined = out + ("\n[stderr]: " + err if err else "")
        msg = f"[WARNING] Command timed out after {TOOL_TIMEOUT}s."
        if combined.strip():
            return f"{combined.strip()}\n\n{msg}"
        return msg
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

def search_installed_tools(keyword: str) -> str:
    keyword = keyword.strip().lower()
    if not keyword or not keyword.isalnum():
        return "[ERROR] Lutfen gecerli bir arama kelimesi girin (ornek: wifi, sql, password)."

    try:
        # apropos komutu, sistemde kurulu olan araclarin aciklamalarinda kelimeyi arar.
        # Sadece calistirilabilir komutlar (section 1 ve 8) icin -s 1,8 kullanilir.
        r = subprocess.run(["apropos", "-s", "1,8", keyword], capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout.strip():
            return f"'{keyword}' ile ilgili sistemde kurulu calistirilabilir bir arac bulunamadi."

        lines = [line for line in r.stdout.strip().split('\n') if not line.endswith('()')]

        if not lines:
            return f"'{keyword}' ile ilgili arac bulunamadi."

        return f"'{keyword}' aramasi icin sistemde kurulu olan calistirilabilir araclar:\n" + "\n".join(lines[:15])
    except Exception as e:
        return f"[ERROR] Arac aramasi basarisiz: {str(e)}"

TOOLS = {
    "bash":         tool_bash,
    "file_read":    tool_file_read,
    "file_write":   tool_file_write,
    "file_delete":  tool_file_delete,
    "file_list":    tool_file_list,
    "fetch_url":    tool_fetch_url,
    "search_tools": search_installed_tools,
}

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

class AmnesicAPI:
    def __init__(self, key: str | None = None):
        self._last_warn = ""

    def call(self, messages: list) -> str:
        full_prompt = "System: " + SYSTEM_PROMPT + "\n\n"
        for msg in messages:
            role = "User" if msg["role"] == "user" else "Agent"
            full_prompt += f"{role}:\n{msg['content']}\n\n"
        full_prompt += "Agent:\n"

        import shutil, subprocess, os
        
        tgpt_bin = shutil.which("tgpt")
        if not tgpt_bin:
            agent_dir = os.path.dirname(os.path.abspath(__file__))
            local_tgpt = os.path.join(agent_dir, "tgpt")
            if os.path.exists(local_tgpt):
                tgpt_bin = local_tgpt
            else:
                self._warn("tgpt binary bulunamadi.", "PATH'de veya agent.py yaninda yok.")
                return self._dead()

        providers = ["koboldai", "isou", "pollinations", "phind"]
        result_stdout = ""
        success = False
        
        for provider in providers:
            try:
                result = subprocess.run(
                    [tgpt_bin, "--provider", provider, "-q", full_prompt],
                    capture_output=True, text=True, timeout=60
                )
                
                if result.returncode == 0 and result.stdout.strip() and not "Error" in result.stdout[:20]:
                    result_stdout = result.stdout.strip()
                    success = True
                    break
                else:
                    err = (result.stderr or result.stdout or "").strip()
                    self._warn(f"Provider '{provider}' failed, trying next...", err[:60])
            except subprocess.TimeoutExpired:
                self._warn(f"Provider '{provider}' timed out, trying next...", "")
            except Exception as e:
                self._warn(f"Provider '{provider}' error, trying next...", str(e)[:60])

        if not success:
            self._warn("All providers failed.", "No available AI endpoint.")
            return self._dead()
            
        return result_stdout

    def status(self) -> str:
        import subprocess, os, shutil
        tgpt_bin = shutil.which("tgpt")
        if not tgpt_bin:
            agent_dir = os.path.dirname(os.path.abspath(__file__))
            local_tgpt = os.path.join(agent_dir, "tgpt")
            if os.path.exists(local_tgpt):
                tgpt_bin = local_tgpt
        
        if not tgpt_bin:
            return f"{CE}tgpt missing in vault and PATH{R}"
            
        try:
            r = subprocess.run([tgpt_bin, "-v"], capture_output=True, text=True)
            if r.returncode == 0:
                ver = r.stdout.strip()
                return f"{CA}tgpt Auto-Router{R} {CD}({ver}){R}"
            return f"{CE}tgpt error{R}"
        except:
            return f"{CE}tgpt error{R}"

    def _warn(self, msg: str, hint: str = ""):
        if msg == self._last_warn: return
        self._last_warn = msg
        print(f"\n{CW}  ! {msg}{R}")
        if hint: print(f"{CD}    > {hint}{R}")

    def _dead(self) -> str:
        w = 50
        print(f"\n{CE}  {'─' * w}{R}")
        print(f"{CE}  AI Engine (tgpt) failed or is missing.{R}")
        print(f"  {CD}Please ensure 'tgpt' is installed globally or in the vault.{R}")
        print(f"{CE}  {'─' * w}{R}")
        return "__DEAD__"


def _w() -> int:
    return min(get_terminal_size().columns, 70)

def banner():
    print(f"""{CC}{CB}
 █████╗ ███╗   ███╗███╗   ██╗███████╗███████╗██╗ ██████╗
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
{CD}            Amnesic Shell v2.4 (Powered by tgpt){R}""")


def div():
    print(f"\n{CD}  {'─' * (_w() - 4)}{R}")

def first_run():
    return ""

def show_help(api: AmnesicAPI):
    print(f"""
{CB}  Status{R}
  {api.status()}

{CB}  Session{R}
  {CC}status{R}           Show detailed API + session info
  {CC}reset{R}            Clear conversation history
  {CC}clear{R}            Clear the terminal screen
  {CC}help{R}   {CC}?{R}        This help
  {CC}exit{R}             Quit Amnesic Shell
""")

def main():
    if not sys.stdout.isatty():
        pass
    else:
        import os
        os.system("cls" if os.name == "nt" else "clear")

    banner()

    api = AmnesicAPI()
    print(f"  {CD}Mode: Local Keyless (tgpt)   |   type {CC}help{CD} for commands   |   {CC}exit{CD} to quit{R}\n")

    conversation: list[dict] = []

    while True:
        try:
            raw = input(f"\n{CU}  >{R} ").strip()
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

        if cmd in ("status", "info"):
            print(f"\n  {api.status()}")
            print(f"  Config     {CD}{CONFIG_FILE}{R}")
            print(f"  History    {len(conversation) // 2} turn(s)")
            continue

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