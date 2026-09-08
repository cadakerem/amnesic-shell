import sys
import os
import json
import urllib.request
import urllib.error

# We can use requests if available, but to be strictly dependency-free (std lib only as per amnesic-shell original design),
# urllib doesn't support SOCKS out of the box without PySocks or subprocess.
# Wait, "Python 3 standart kütüphanesi dışında bağımlılığı yoktur." was for the original.
# The new doc says "Python (requests) veya saf Bash (curl/jq) kullanılarak yazılacak."
# Let's write a version that can use 'curl' via subprocess with torsocks, OR requests via socks if available,
# to ensure it works in any environment without installing extra pip packages if possible.

import subprocess

def query_llm_via_curl(prompt: str, api_key: str, model: str = "llama3-70b-8192") -> str:
    """
    Makes a request to Groq API using 'torsocks curl' or standard 'curl' with a SOCKS proxy.
    This guarantees no Python dependencies like requests/PySocks are strictly required.
    """
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = [
        "-H", "Content-Type: application/json",
        "-H", f"Authorization: Bearer {api_key}"
    ]
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are Ghost AI, a completely amnesic and anonymous assistant."},
            {"role": "user", "content": prompt}
        ]
    }
    
    # We use subprocess to call curl over torsocks
    # curl --socks5-hostname 127.0.0.1:9050 is an alternative to torsocks.
    cmd = [
        "curl", 
        "--socks5-hostname", "127.0.0.1:9050", # Route DNS and TCP through Tor
        "-s", # Silent
        "-X", "POST",
        url
    ] + headers + [
        "-d", json.dumps(payload)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        response_json = json.loads(result.stdout)
        
        if "choices" in response_json:
            return response_json["choices"][0]["message"]["content"]
        else:
            return f"Error in response: {result.stdout}"
    except subprocess.CalledProcessError as e:
        return f"Request failed: {e}\nOutput: {e.output}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"

def main():
    # 1. API Key is injected via environment variables (never written to disk)
    api_key = os.environ.get("GHOST_API_KEY")
    if not api_key:
        print("Error: GHOST_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)
        
    # 2. In-memory context bridge: read everything from stdin
    # This allows piping a file's content directly into the agent
    # e.g., cat sensitive.txt | python3 ghost-agent.py
    if not sys.stdin.isatty():
        context = sys.stdin.read().strip()
    else:
        print("Error: Ghost AI expects input via stdin (e.g., echo 'hello' | python3 ghost-agent.py)", file=sys.stderr)
        sys.exit(1)
        
    if not context:
        print("Error: Empty input provided.", file=sys.stderr)
        sys.exit(1)
        
    # 3. Query the LLM over Tor
    response = query_llm_via_curl(context, api_key)
    
    # 4. Output the result
    print(response)

if __name__ == "__main__":
    main()
