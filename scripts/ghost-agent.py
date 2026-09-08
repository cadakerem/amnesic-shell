import sys
import os
import json
import subprocess
import re

# ANSI Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    RESET = '\033[0m'

class ConnectionMode:
    TOR = "TOR"
    PROXY = "PROXY_POOL"
    DIRECT = "DIRECT"

class ConnectivityManager:
    def __init__(self):
        self.mode = None
        self.proxy_url = os.environ.get("GHOST_PROXY_URL") # e.g. socks5://user:pass@proxy:port

    def probe_curl(self, proxy_args, timeout=5) -> bool:
        """Probes the Groq API endpoint and verifies JSON body to bypass WAF HTML 200 OK challenges."""
        cmd = [
            "curl", "-s", "--max-time", str(timeout)
        ] + proxy_args + ["https://api.groq.com/openai/v1/models"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            try:
                data = json.loads(result.stdout)
                # If we get a valid JSON with 'error' (401 Missing API key) or 'data' (200 OK), it's Groq, not WAF.
                if "error" in data or "data" in data:
                    return True
            except json.JSONDecodeError:
                # Failed to parse JSON, likely a WAF HTML page or proxy error
                pass
            return False
        except Exception:
            return False

    def establish_connection(self):
        print(f"{Colors.CYAN}[*] Bypassing WAF & Checking Connectivity...{Colors.RESET}", file=sys.stderr)
        
        # 1. Try Tor
        print(f" ├─ Probing Tor Network (127.0.0.1:9050)...", file=sys.stderr, end="", flush=True)
        if self.probe_curl(["--socks5-hostname", "127.0.0.1:9050"]):
            self.mode = ConnectionMode.TOR
            print(f" {Colors.GREEN}[OK]{Colors.RESET}", file=sys.stderr)
            return
        print(f" {Colors.RED}[FAILED/BLOCKED]{Colors.RESET}", file=sys.stderr)

        # 2. Try Proxy Pool
        if self.proxy_url:
            print(f" ├─ Probing Fallback Proxy...", file=sys.stderr, end="", flush=True)
            if self.probe_curl(["-x", self.proxy_url]):
                self.mode = ConnectionMode.PROXY
                print(f" {Colors.GREEN}[OK]{Colors.RESET}", file=sys.stderr)
                return
            print(f" {Colors.RED}[FAILED]{Colors.RESET}", file=sys.stderr)
        else:
            print(f" ├─ No Fallback Proxy configured (GHOST_PROXY_URL).", file=sys.stderr)

        # 3. Fallback to Direct (Requires Explicit Consent)
        print(f" └─ {Colors.YELLOW}Warning: Secure channels failed. You are about to expose your real IP.{Colors.RESET}", file=sys.stderr)
        
        # We need to read from /dev/tty because stdin might be piped with context
        try:
            with open("/dev/tty", "r") as tty:
                print(f"    Allow DIRECT connection? (y/N): ", file=sys.stderr, end="", flush=True)
                choice = tty.readline().strip().lower()
                if choice in ['y', 'yes']:
                    print(f"    Probing Direct Connection...", file=sys.stderr, end="", flush=True)
                    if self.probe_curl([]):
                        self.mode = ConnectionMode.DIRECT
                        print(f" {Colors.GREEN}[OK]{Colors.RESET}", file=sys.stderr)
                        return
                    else:
                        print(f" {Colors.RED}[FAILED]{Colors.RESET}", file=sys.stderr)
                        print(f"{Colors.RED}[!] Could not reach API even via Direct connection.{Colors.RESET}", file=sys.stderr)
                        sys.exit(1)
                else:
                    print(f"{Colors.RED}[!] Aborted by user to preserve OPSEC.{Colors.RESET}", file=sys.stderr)
                    sys.exit(1)
        except OSError:
            print(f"{Colors.RED}[!] Cannot prompt for Direct connection consent (no tty). Aborting.{Colors.RESET}", file=sys.stderr)
            sys.exit(1)

    def get_curl_args(self):
        if self.mode == ConnectionMode.TOR:
            return ["--socks5-hostname", "127.0.0.1:9050"]
        elif self.mode == ConnectionMode.PROXY:
            return ["-x", self.proxy_url]
        else:
            return []

def execute_command_with_consent(command: str) -> str:
    """Displays the command to the user and asks for explicit execution consent via /dev/tty."""
    print(f"\n{Colors.YELLOW}[Ghost AI Suggests Command]{Colors.RESET}")
    print(f"{Colors.CYAN}{command}{Colors.RESET}")
    
    try:
        with open("/dev/tty", "r") as tty:
            print(f"{Colors.YELLOW}Execute this command? (y/N): {Colors.RESET}", end="", flush=True)
            choice = tty.readline().strip().lower()
            if choice in ['y', 'yes']:
                print(f"{Colors.GREEN}[*] Executing...{Colors.RESET}")
                try:
                    # Execute shell command. This uses shell=True, which is intended here since
                    # the user explicitly approves the raw bash string.
                    result = subprocess.run(command, shell=True, capture_output=True, text=True)
                    output = result.stdout
                    if result.stderr:
                        output += "\n[stderr]\n" + result.stderr
                    print(f"{Colors.GREEN}[*] Done. Exit code: {result.returncode}{Colors.RESET}")
                    return output if output else "[No Output]"
                except Exception as e:
                    return f"[Execution Error]: {str(e)}"
            else:
                print(f"{Colors.RED}[!] Skipped by user.{Colors.RESET}")
                return "[User Denied Execution]"
    except OSError:
        return "[Error: Cannot prompt user for consent (no tty)]"

def query_llm_via_curl(messages: list, api_key: str, curl_args: list, model: str = "llama3-70b-8192") -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = [
        "-H", "Content-Type: application/json",
        "-H", f"Authorization: Bearer {api_key}"
    ]
    
    payload = {
        "model": model,
        "messages": messages
    }
    
    cmd = ["curl", "-s", "-X", "POST", url] + curl_args + headers + ["-d", json.dumps(payload)]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        response_json = json.loads(result.stdout)
        
        if "choices" in response_json:
            return response_json["choices"][0]["message"]["content"]
        else:
            return f"Error in response: {result.stdout}"
    except Exception as e:
        return f"Request failed: {str(e)}"

def extract_commands(response_text: str) -> list:
    """Extracts bash commands from markdown blocks in the LLM response."""
    pattern = r"```(?:bash|sh)\n(.*?)\n```"
    return [match.strip() for match in re.findall(pattern, response_text, re.DOTALL)]

def main():
    api_key = os.environ.get("GHOST_API_KEY")
    if not api_key:
        print(f"{Colors.RED}Error: GHOST_API_KEY environment variable not set.{Colors.RESET}", file=sys.stderr)
        sys.exit(1)
        
    # Read stdin context before we do connection probing (so it blocks until piped input is done)
    if not sys.stdin.isatty():
        context = sys.stdin.read().strip()
    else:
        print(f"{Colors.RED}Error: Ghost AI expects input via stdin. Try: echo 'sysinfo' | python3 scripts/ghost-agent.py{Colors.RESET}", file=sys.stderr)
        sys.exit(1)
        
    if not context:
        print(f"{Colors.RED}Error: Empty input provided.{Colors.RESET}", file=sys.stderr)
        sys.exit(1)
        
    # Phase 1: Communication Layer
    conn_mgr = ConnectivityManager()
    conn_mgr.establish_connection()
    
    print(f"\n{Colors.GREEN}[+] Agent Loop Started [{conn_mgr.mode} MODE]{Colors.RESET}", file=sys.stderr)
    
    system_prompt = (
        "You are Ghost AI, an amnesic, anonymous terminal assistant running inside Kali Linux.\n"
        "You have direct access to the user's terminal via a REPL loop.\n"
        "If you need to execute a command to gather information or perform an action, provide the exact Linux command wrapped in a ```bash ... ``` block.\n"
        "Provide ONLY ONE command block at a time. The user will review it, execute it, and provide the output back to you.\n"
        "Do NOT write scripts unless explicitly asked, prefer one-liner commands."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context}
    ]
    
    # Phase 2: Agent Loop (Max 10 iterations to prevent runaway loops)
    for iteration in range(10):
        print(f"{Colors.CYAN}--> Waiting for Ghost AI (Iteration {iteration+1}/10)...{Colors.RESET}", file=sys.stderr)
        response = query_llm_via_curl(messages, api_key, conn_mgr.get_curl_args())
        
        print(f"\n{Colors.CYAN}[Ghost AI]{Colors.RESET}\n{response}")
        messages.append({"role": "assistant", "content": response})
        
        commands = extract_commands(response)
        if not commands:
            # If no command is suggested, the agent is either done or just talking.
            break
            
        for cmd in commands:
            output = execute_command_with_consent(cmd)
            messages.append({
                "role": "user", 
                "content": f"Output of `{cmd}`:\n```\n{output}\n```\nAnalyze the output and decide the next step. If your task is complete, just reply with plain text and NO bash blocks."
            })
            
    print(f"\n{Colors.GREEN}[+] Agent Loop Finished.{Colors.RESET}", file=sys.stderr)

if __name__ == "__main__":
    main()
