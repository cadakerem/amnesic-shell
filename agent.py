#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║                  👻  PHANTOM AGENT  v2.0                    ║
║         Anonim · Hesapsız · Linux Terminal AI Agent         ║
╚══════════════════════════════════════════════════════════════╝

Kullanim:
  python3 agent.py                  # Anonim mod (OVHcloud)
  python3 agent.py --key YOUR_KEY   # Groq ile hizli mod
  python3 agent.py --help           # Yardim

Ozellikler:
  - Birincil: OVHcloud AI (tamamen anonim, key/login yok)
  - Fallback : Groq API (e-posta ile alinabilen ucretsiz key)
  - Bash komutu calistirma
  - Dosya olusturma / okuma / silme / listeleme
  - URL'den icerik cekme
  - Cok turlu konusma gecmisi (RAM'de, kapanista siliniyor)
  - Tek dosya, sifir bagimlilik (sadece Python 3.8+ stdlib)
"""

import os, re, sys, json, time, subprocess, urllib.request, urllib.error
from shutil import get_terminal_size

# ─────────────────────────────────────────────────────────────
#  AYARLAR
# ─────────────────────────────────────────────────────────────

AGENT_NAME    = "Phantom"
VERSION       = "2.0"
MAX_HISTORY   = 30         # RAM'deki max konusma turu
TOOL_TIMEOUT  = 30         # Bash timeout (saniye)
MAX_TOOL_LOOPS = 6         # Sonsuz dongu korumasi

# ─── API Saglayicilari ─────────────────────────────────────

# 1) OVHcloud – Tamamen anonim, key gerektirmez
OVH_URL   = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions"
OVH_MODEL = "Meta-Llama-3_3-70B-Instruct"

# 2) Groq – Ucretsiz, hizli, key gerektirir (isteye bagli)
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# ─── Renkler ─────────────────────────────────────────────

C_RESET  = "\033[0m"
C_USER   = "\033[94m"   # Mavi
C_AGENT  = "\033[92m"   # Yesil
C_TOOL   = "\033[93m"   # Sari
C_ERROR  = "\033[91m"   # Kirmizi
C_DIM    = "\033[90m"   # Gri
C_BOLD   = "\033[1m"


# ─────────────────────────────────────────────────────────────
#  SISTEM PROMPT
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Phantom, a powerful, privacy-focused AI agent running in a Linux terminal.
You help the user with any task by using available tools.

== HOW TO CALL TOOLS ==
When a task requires running a command, reading/writing a file, or fetching a URL, output EXACTLY:

<tool>
<name>TOOL_NAME</name>
<input>TOOL_INPUT</input>
</tool>

You may call multiple tools in one response; they run sequentially.
After receiving all tool results, write your final answer clearly.

== TOOLS ==

bash
  Run any bash shell command.
  Input : The command string.
  Use   : Checking system info, running scripts, installing packages, etc.
  Note  : For dangerous commands (rm -rf, dd, format) warn the user first.
  Eg    : <tool><name>bash</name><input>uname -a && free -h</input></tool>

file_read
  Read a file and return its content.
  Input : Absolute or ~ path.
  Eg    : <tool><name>file_read</name><input>/etc/os-release</input></tool>

file_write
  Write (overwrite) content to a file. Creates missing parent dirs.
  Input : PATH|||CONTENT  (||| separates the path from the content)
  Eg    : <tool><name>file_write</name><input>/tmp/scan.sh|||#!/bin/bash
nmap -sV 192.168.1.0/24</input></tool>

file_delete
  Permanently delete a file.
  Input : File path.
  Eg    : <tool><name>file_delete</name><input>/tmp/scan.sh</input></tool>

file_list
  List the contents of a directory.
  Input : Directory path (use . for current directory).
  Eg    : <tool><name>file_list</name><input>/home/kali</input></tool>

fetch_url
  Fetch the text/HTML content of a URL.
  Input : Full URL.
  Eg    : <tool><name>fetch_url</name><input>https://ifconfig.me</input></tool>

== RULES ==
1. Always answer in the same language as the user (likely Turkish).
2. Be concise but complete.
3. Warn before destructive operations.
4. You run on Kali Linux. The user values privacy and anonymity.
5. Never suggest creating online accounts or entering personal info.
"""


# ─────────────────────────────────────────────────────────────
#  ARAÇLAR (TOOLS)
# ─────────────────────────────────────────────────────────────

def tool_bash(cmd: str) -> str:
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=TOOL_TIMEOUT, executable="/bin/bash"
        )
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if err:
            out += ("\n" if out else "") + f"[stderr]: {err}"
        return out or "(Komut tamamlandi, cikti yok.)"
    except subprocess.TimeoutExpired:
        return f"[HATA]: {TOOL_TIMEOUT}s timeout."
    except FileNotFoundError:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=TOOL_TIMEOUT)
            return (r.stdout + r.stderr).strip()
        except Exception as e:
            return f"[HATA]: {e}"
    except Exception as e:
        return f"[HATA]: {e}"


def tool_file_read(path: str) -> str:
    try:
        p = os.path.expanduser(path.strip())
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            c = f.read()
        if len(c) > 6000:
            c = c[:6000] + f"\n\n[... {len(c)} karakter toplam, kisaltildi]"
        return c or "(Bos dosya)"
    except Exception as e:
        return f"[HATA]: {e}"


def tool_file_write(inp: str) -> str:
    if "|||" not in inp:
        return "[HATA]: Kullan -> YOLU|||ICERIK"
    path, content = inp.split("|||", 1)
    path = os.path.expanduser(path.strip())
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[OK] '{path}' olusturuldu ({len(content)} karakter)"
    except Exception as e:
        return f"[HATA]: {e}"


def tool_file_delete(path: str) -> str:
    path = os.path.expanduser(path.strip())
    try:
        os.remove(path)
        return f"[OK] '{path}' silindi."
    except Exception as e:
        return f"[HATA]: {e}"


def tool_file_list(path: str) -> str:
    path = os.path.expanduser(path.strip()) or "."
    try:
        entries = sorted(os.listdir(path))
        lines = []
        for e in entries:
            full = os.path.join(path, e)
            if os.path.isdir(full):
                lines.append(f"  [D] {e}/")
            else:
                try:
                    sz = os.path.getsize(full)
                    lines.append(f"  [F] {e}  ({_fmt_size(sz)})")
                except OSError:
                    lines.append(f"  [F] {e}")
        return "\n".join(lines) or "(Bos dizin)"
    except Exception as e:
        return f"[HATA]: {e}"


def tool_fetch_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            c = r.read().decode("utf-8", errors="replace")
        c = re.sub(r"<[^>]+>", " ", c)
        c = re.sub(r"\s{2,}", " ", c).strip()
        if len(c) > 4000:
            c = c[:4000] + "\n[... kisaltildi]"
        return c
    except urllib.error.HTTPError as e:
        return f"[HTTP {e.code}]: {e.reason}"
    except Exception as e:
        return f"[HATA]: {e}"


def _fmt_size(n: int) -> str:
    for u in ("B","KB","MB","GB"):
        if n < 1024: return f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}TB"


TOOLS = {
    "bash":        tool_bash,
    "file_read":   tool_file_read,
    "file_write":  tool_file_write,
    "file_delete": tool_file_delete,
    "file_list":   tool_file_list,
    "fetch_url":   tool_fetch_url,
}


# ─────────────────────────────────────────────────────────────
#  API — OVHCloud (anonim) + Groq (fallback)
# ─────────────────────────────────────────────────────────────

class PhantomAPI:
    def __init__(self, groq_key: str | None = None):
        self.groq_key = groq_key
        self._ovh_fail_count = 0

    def call(self, messages: list) -> str:
        # Birincil: OVHcloud (anonim)
        if self._ovh_fail_count < 3:
            result = self._call_ovh(messages)
            if not result.startswith("[API"):
                self._ovh_fail_count = 0
                return result
            # OVH basarisiz
            self._ovh_fail_count += 1
            print(f"\n{C_DIM}  [OVH basarisiz, fallback deneniyor...]{C_RESET}", flush=True)

        # Fallback: Groq
        if self.groq_key:
            return self._call_groq(messages)

        # Her ikisi de yok
        return "[API HATA]: OVHcloud basarisiz ve Groq key yok. --key FLAG ile key verebilirsin."

    def _post(self, url: str, payload: dict, headers: dict) -> str:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                resp = json.loads(r.read().decode("utf-8"))
                return resp["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:200]
            return f"[API HTTP {e.code}]: {body}"
        except Exception as e:
            return f"[API HATA]: {e}"

    def _call_ovh(self, messages: list) -> str:
        payload = {
            "model": OVH_MODEL,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            "max_tokens": 1500,
            "temperature": 0.65,
        }
        headers = {"Content-Type": "application/json"}
        return self._post(OVH_URL, payload, headers)

    def _call_groq(self, messages: list) -> str:
        payload = {
            "model": GROQ_MODEL,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            "max_tokens": 1500,
            "temperature": 0.65,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.groq_key}",
        }
        return self._post(GROQ_URL, payload, headers)


# ─────────────────────────────────────────────────────────────
#  ARAÇ PARSER
# ─────────────────────────────────────────────────────────────

_TOOL_RE = re.compile(
    r"<tool>\s*<name>\s*(.*?)\s*</name>\s*<input>(.*?)</input>\s*</tool>",
    re.DOTALL | re.IGNORECASE,
)

def run_tools(response: str) -> tuple:
    """(sonuclar_str, arac_cagrildi_mi)"""
    matches = _TOOL_RE.findall(response)
    if not matches:
        return "", False
    results = []
    for name, inp in matches:
        name, inp = name.strip(), inp.strip()
        print(f"\n{C_TOOL}  ⚙  {name}{C_RESET} → {inp[:90]}", flush=True)
        fn = TOOLS.get(name)
        result = fn(inp) if fn else f"[HATA]: '{name}' bilinmiyor. Gecerli: {', '.join(TOOLS)}"
        print(f"{C_DIM}  ✓  Tamamlandi{C_RESET}", flush=True)
        results.append(f"[{name} sonucu]:\n{result}")
    return "\n\n".join(results), True

def clean_response(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", _TOOL_RE.sub("", text)).strip()


# ─────────────────────────────────────────────────────────────
#  UI
# ─────────────────────────────────────────────────────────────

def banner(api_mode: str):
    w = min(get_terminal_size().columns, 64)
    line = "═" * (w - 2)
    print(f"""
╔{line}╗
║{"  👻  PHANTOM AGENT  v" + VERSION + "  👻".center(w - 2)}║
║{"Anonim · Hesapsiz · Linux Terminal AI Agent".center(w - 2)}║
║{("API: " + api_mode).center(w - 2)}║
╚{line}╝
{C_DIM}Komutlar: help | clear | reset | exit{C_RESET}
""")

def hr():
    w = min(get_terminal_size().columns, 64)
    print(f"{C_DIM}{'─' * w}{C_RESET}")

def help_msg():
    print(f"""
{C_BOLD}Dahili Komutlar:{C_RESET}
  clear / temizle    Ekrani temizle
  reset / sifirla    Konusma gecmisini sil
  status             API durumunu goster
  exit / cikis       Cikis yap

{C_BOLD}Agent Yetenekleri:{C_RESET}
  bash       → "python versiyonu nedir?", "ag baglantimi goster"
  file_read  → "su dosyayi oku: /etc/hostname"
  file_write → "scan.sh adli bir nmap scripti olustur"
  file_list  → "/home/kali dizininde ne var?"
  fetch_url  → "https://ifconfig.me adresinden IP'mi al"

{C_BOLD}Startup Parametreleri:{C_RESET}
  --key GROQ_KEY   Groq API key'i ile baslat (daha hizli)
  --help           Bu yardim mesaji
""")


# ─────────────────────────────────────────────────────────────
#  ANA DÖNGÜ
# ─────────────────────────────────────────────────────────────

def main():
    # Argüman parse (stdlib, argparse yok)
    groq_key = None
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)
    if "--key" in args:
        idx = args.index("--key")
        try:
            groq_key = args[idx + 1]
        except IndexError:
            print("Kullanim: python3 agent.py --key GROQ_KEY")
            sys.exit(1)

    api_mode = "OVHcloud (Anonim)" if not groq_key else "OVHcloud + Groq (Fallback)"
    api = PhantomAPI(groq_key=groq_key)

    banner(api_mode)

    conversation: list[dict] = []

    while True:
        try:
            raw = input(f"\n{C_USER}[Sen]{C_RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n{C_DIM}👻 Phantom kapandi. Hafiza temizlendi.{C_RESET}\n")
            sys.exit(0)

        if not raw:
            continue

        cmd = raw.lower()

        if cmd in ("exit","quit","cikis","bye","q"):
            print(f"\n{C_DIM}👻 Phantom kapandi.{C_RESET}\n")
            sys.exit(0)
        if cmd in ("clear","cls","temizle"):
            os.system("clear" if os.name != "nt" else "cls")
            banner(api_mode)
            continue
        if cmd in ("reset","sifirla"):
            conversation.clear()
            print(f"{C_DIM}  ↺ Konusma gecmisi temizlendi.{C_RESET}")
            continue
        if cmd in ("help","yardim","?"):
            help_msg()
            continue
        if cmd == "status":
            print(f"\n  API Modu  : {api_mode}")
            print(f"  Mesaj Say.: {len(conversation)}")
            print(f"  Groq Key  : {'VAR' if groq_key else 'YOK'}")
            continue

        # Geçmiş limiti
        if len(conversation) > MAX_HISTORY:
            conversation = conversation[-MAX_HISTORY:]

        conversation.append({"role": "user", "content": raw})

        print(f"\n{C_DIM}  ▸ Dusunuyor...{C_RESET}", end="", flush=True)

        # ReAct döngüsü
        for _ in range(MAX_TOOL_LOOPS):
            response = api.call(conversation)

            tool_out, had_tools = run_tools(response)

            if not had_tools:
                final = clean_response(response)
                hr()
                print(f"\n{C_AGENT}[{AGENT_NAME}]{C_RESET} {final}\n")
                conversation.append({"role": "assistant", "content": response})
                break
            else:
                conversation.append({"role": "assistant", "content": response})
                conversation.append({
                    "role": "user",
                    "content": f"Arac sonuclari:\n{tool_out}\n\nBu sonuclara gore kullaniciya Turkce ve ozlu cevap ver."
                })
                print(f"\n{C_DIM}  ▸ Sonuc degerlendiriliyor...{C_RESET}", end="", flush=True)
        else:
            print(f"\n{C_AGENT}[{AGENT_NAME}]{C_RESET} {C_ERROR}Max arac dongusune ulasildi.{C_RESET}\n")


if __name__ == "__main__":
    main()
