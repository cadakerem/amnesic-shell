#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phantom Agent v2.1
Anonim Linux Terminal AI Agent
"""
import sys as _sys
# Kali (UTF-8) ve Windows (CP1254) uyumu icin stdout'u UTF-8'e zorla
if hasattr(_sys.stdout, "reconfigure"):
    try:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os, re, sys, json, getpass, subprocess, urllib.request, urllib.error
from shutil import get_terminal_size

# ─────────────────────────────────────────────────────────────
#  AYARLAR
# ─────────────────────────────────────────────────────────────

AGENT_NAME     = "Phantom"
VERSION        = "2.1"
MAX_HISTORY    = 30
TOOL_TIMEOUT   = 30
MAX_TOOL_LOOPS = 6

# OVHcloud — tamamen anonim, key gerektirmez
OVH_URL   = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions"
OVH_MODEL = "Meta-Llama-3_3-70B-Instruct"

# Groq — hizli, ucretsiz tier, key gerekir
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# ANSI renkler
C_RESET = "\033[0m"
C_USER  = "\033[94m"
C_AGENT = "\033[92m"
C_TOOL  = "\033[93m"
C_WARN  = "\033[33m"
C_ERROR = "\033[91m"
C_DIM   = "\033[90m"
C_BOLD  = "\033[1m"
C_CYAN  = "\033[96m"

# ─────────────────────────────────────────────────────────────
#  SISTEM PROMPT
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Phantom, a powerful, privacy-focused AI agent running in a Linux terminal.
Help the user with any task using the tools available.

== TOOL CALL FORMAT ==
Output EXACTLY this XML when you need a tool:

<tool>
<name>TOOL_NAME</name>
<input>TOOL_INPUT</input>
</tool>

Multiple tools per response are fine — they run sequentially.
After all results arrive, write your final answer.

== TOOLS ==

bash         — Run any bash/shell command.
               Input: the command string.
               Warn before destructive ops (rm -rf, dd, mkfs, etc.)
               Eg: <tool><name>bash</name><input>df -h && free -h</input></tool>

file_read    — Read a file.
               Input: path (supports ~)
               Eg: <tool><name>file_read</name><input>/etc/os-release</input></tool>

file_write   — Write/overwrite a file (creates missing dirs).
               Input: PATH|||CONTENT  (||| is the separator)
               Eg: <tool><name>file_write</name><input>/tmp/check.sh|||#!/bin/bash
ifconfig</input></tool>

file_delete  — Delete a file permanently.
               Input: path
               Eg: <tool><name>file_delete</name><input>/tmp/check.sh</input></tool>

file_list    — List a directory.
               Input: directory path (. = current)
               Eg: <tool><name>file_list</name><input>/home/kali</input></tool>

fetch_url    — Fetch text content from a URL.
               Input: full URL
               Eg: <tool><name>fetch_url</name><input>https://ifconfig.me</input></tool>

== RULES ==
1. Reply in the user's language (likely Turkish).
2. Be concise but thorough.
3. Warn before any destructive command.
4. Never suggest creating accounts or sharing personal data.
5. Context: Kali Linux, privacy/anonymity is important to the user.
"""

# ─────────────────────────────────────────────────────────────
#  ARAÇLAR
# ─────────────────────────────────────────────────────────────

def tool_bash(cmd: str) -> str:
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=TOOL_TIMEOUT, executable="/bin/bash"
        )
        out = (r.stdout or "").rstrip()
        err = (r.stderr or "").rstrip()
        combined = out + ("\n[stderr]: " + err if err else "")
        return combined.strip() or "(Komut tamamlandi, cikti yok.)"
    except subprocess.TimeoutExpired:
        return f"[HATA]: Komut {TOOL_TIMEOUT}s icinde tamamlanamadi."
    except FileNotFoundError:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=TOOL_TIMEOUT)
            out = (r.stdout or "") + (r.stderr or "")
            return out.strip() or "(cikti yok)"
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
            c = c[:6000] + f"\n[... toplam {len(c)} karakter, kisaltildi]"
        return c or "(Bos dosya)"
    except Exception as e:
        return f"[HATA]: {e}"

def tool_file_write(inp: str) -> str:
    if "|||" not in inp:
        return "[HATA]: Kullanimformat -> YOL|||ICERIK"
    path, content = inp.split("|||", 1)
    path = os.path.expanduser(path.strip())
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[OK] '{path}' yazildi ({len(content)} karakter)"
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
                    sz = _fmt_size(os.path.getsize(full))
                    lines.append(f"  [F] {e}  ({sz})")
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
            url,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            c = r.read().decode("utf-8", errors="replace")
        c = re.sub(r"<[^>]+>", " ", c)
        c = re.sub(r"\s{2,}", " ", c).strip()
        return (c[:4000] + "\n[... kisaltildi]") if len(c) > 4000 else c
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
    "bash": tool_bash,
    "file_read": tool_file_read,
    "file_write": tool_file_write,
    "file_delete": tool_file_delete,
    "file_list": tool_file_list,
    "fetch_url": tool_fetch_url,
}

# ─────────────────────────────────────────────────────────────
#  API KATMANI — OVHcloud + Groq fallback
# ─────────────────────────────────────────────────────────────

class PhantomAPI:
    """
    API durumu makinesi:
      OVH_OK     → OVHcloud calisıyor, onu kullan
      OVH_LIMIT  → OVH rate-limit yedi, Groq'a gec
      GROQ_OK    → Groq calisıyor
      GROQ_LIMIT → Groq da limit/hata, kullaniciya uyar
      DEAD       → Her ikisi de calismıyor
    """

    def __init__(self, groq_key: str | None = None):
        self.groq_key  = groq_key
        self.ovh_ok    = True   # OVHcloud hala kullanılabilir mi
        self.groq_ok   = bool(groq_key)  # Groq key var mi
        self._last_warn = ""    # Ayni uyariyi tekrar gosterme

    # ── Ana cagri ───────────────────────────────────────────

    def call(self, messages: list) -> str:
        """Mesaj listesini gondererek cevap al. Hic carpmaz."""

        # 1) OVHcloud dene
        if self.ovh_ok:
            result, err_type = self._post(
                OVH_URL, OVH_MODEL, messages, headers={}
            )
            if err_type == "ok":
                return result
            elif err_type == "rate_limit":
                self.ovh_ok = False
                self._warn(
                    "OVHcloud rate-limit doldu (2 req/dk).",
                    "Groq'a geciliyor..." if self.groq_key else "Bekleniyor veya Groq key ekle."
                )
            else:
                # Gecici hata — yine de OVH'yi kapatma, sadece uyar
                self._warn(f"OVHcloud hatasi: {result[:80]}", "Groq deneniyor..." if self.groq_key else "")

        # 2) Groq dene (key varsa)
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
                    "Groq rate-limit doldu veya gunluk kota bitti.",
                    "Kota yenilenene kadar (gunluk) sadece OVHcloud kullanilacak."
                )
                # OVH'yi tekrar ac (belki limiti gecti)
                self.ovh_ok = True
                return self._dead_response()
            elif err_type == "auth":
                self.groq_ok = False
                self._warn("Groq key gecersiz veya suresi dolmus.", "Yeni key icin: console.groq.com")
                return self._dead_response()
            else:
                self._warn(f"Groq hatasi: {result[:80]}", "")
                return self._dead_response()

        # 3) Her sey basarisiz
        return self._dead_response()

    # ── Durum sorgu ─────────────────────────────────────────

    def status_str(self) -> str:
        ovh  = f"{C_AGENT}Aktif{C_RESET}" if self.ovh_ok  else f"{C_ERROR}Limit{C_RESET}"
        groq_s = (
            f"{C_AGENT}Aktif{C_RESET}" if (self.groq_key and self.groq_ok)
            else (f"{C_ERROR}Limit/Hata{C_RESET}" if self.groq_key else f"{C_DIM}Key yok{C_RESET}")
        )
        return f"OVHcloud: {ovh}  |  Groq: {groq_s}"

    def set_groq_key(self, key: str):
        self.groq_key = key.strip()
        self.groq_ok  = bool(self.groq_key)

    # ── Icsel ───────────────────────────────────────────────

    def _post(self, url: str, model: str, messages: list, headers: dict) -> tuple:
        """
        Donus: (icerik_veya_hata_str, tip)
        tip : "ok" | "rate_limit" | "auth" | "error"
        """
        payload = json.dumps(
            {
                "model": model,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                "max_tokens": 1500,
                "temperature": 0.65,
            },
            ensure_ascii=False,
        ).encode("utf-8")

        all_headers = {"Content-Type": "application/json"}
        all_headers.update(headers)

        req = urllib.request.Request(url, data=payload, headers=all_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"].strip()
                return content, "ok"
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
        key = msg
        if key == self._last_warn:
            return
        self._last_warn = key
        print(f"\n{C_WARN}  ⚠  {msg}{C_RESET}")
        if hint:
            print(f"{C_DIM}     → {hint}{C_RESET}")

    def _dead_response(self) -> str:
        lines = [
            f"\n{C_ERROR}╔══ API UYARISI ══════════════════════════════╗{C_RESET}",
            f"{C_ERROR}║{C_RESET} Simdilik hicbir API yanit veremiyor.         {C_ERROR}║{C_RESET}",
        ]
        if not self.groq_key:
            lines.append(f"{C_ERROR}║{C_RESET} {C_WARN}Groq key ekle:{C_RESET} 'groq-key YOUR_KEY' yaz.    {C_ERROR}║{C_RESET}")
        else:
            lines.append(f"{C_ERROR}║{C_RESET} {C_DIM}Birkaç dakika bekleyip tekrar dene.{C_RESET}          {C_ERROR}║{C_RESET}")
        lines.append(f"{C_ERROR}╚══════════════════════════════════════════════╝{C_RESET}")
        # Direkt ekrana yaz; bu bir "cevap" degil, sistem mesaji
        for l in lines:
            print(l)
        return "__DEAD__"  # Konusma gecmisine ekleme

# ─────────────────────────────────────────────────────────────
#  ARAÇ PARSER
# ─────────────────────────────────────────────────────────────

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

def banner():
    w = min(get_terminal_size().columns, 66)
    ln = "═" * (w - 2)
    print(f"""
{C_CYAN}╔{ln}╗
║{"  👻  PHANTOM AGENT  v" + VERSION + "  👻".center(w - 2)}║
║{"Anonim · Hesapsiz · Linux Terminal AI Agent".center(w - 2)}║
╚{ln}╝{C_RESET}""")

def hr():
    w = min(get_terminal_size().columns, 66)
    print(f"{C_DIM}{'─' * w}{C_RESET}")

def help_msg(api: "PhantomAPI"):
    print(f"""
{C_BOLD}API Durumu:{C_RESET}
  {api.status_str()}

{C_BOLD}Dahili Komutlar:{C_RESET}
  groq-key KEY   Groq API key'ini gir (calistirirken degistirilebilir)
  status         API ve oturum durumu
  clear          Ekrani temizle
  reset          Konusma gecmisini sil
  help / ?       Bu yardim
  exit           Cikis

{C_BOLD}Agent Yetenekleri:{C_RESET}
  • Bash: "ag kartim nedir?", "kurulu python paketleri?"
  • Dosya: "su dosyayi oku", "scan.sh olustur ve icine nmap komutu yaz"
  • Liste: "/home/kali altindakiler neler?"
  • URL  : "https://ifconfig.me adresini cek"
  • Hafiza: Onceki mesajlari hatirlıyor (RAM, kapanista siliniyor)
""")

def setup_screen() -> str | None:
    """
    Baslangic key giris ekrani.
    Kullanici bos birakabilir (anonim mod).
    Donus: groq_key veya None
    """
    w = min(get_terminal_size().columns, 66)
    ln = "─" * (w - 2)
    print(f"""
{C_CYAN}╔{ln}╗
║{"  GROQ API KEY KURULUMU".center(w - 2)}║
╚{ln}╝{C_RESET}

  {C_BOLD}Birincil API:{C_RESET} OVHcloud (anonim, key yok, Llama 3.3 70B)
  {C_BOLD}Fallback API:{C_RESET} Groq     (hizli, ucretsiz tier, key gerekir)

  OVHcloud rate-limit dolunca ({C_WARN}2 req/dk{C_RESET}) Groq'a gecer.
  Groq key'in yoksa sadece OVHcloud kullanilir.

  {C_DIM}Groq ucretsiz key alma: console.groq.com (sadece e-posta){C_RESET}
""")

    try:
        raw = input(f"  Groq key gir (yoksa bos birak, ENTER): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raw = ""

    if raw:
        print(f"  {C_AGENT}✓ Groq key kaydedildi.{C_RESET}\n")
    else:
        print(f"  {C_DIM}→ Anonim mod. Sadece OVHcloud kullanilacak.{C_RESET}\n")

    return raw or None

# ─────────────────────────────────────────────────────────────
#  ANA DÖNGÜ
# ─────────────────────────────────────────────────────────────

def main():
    # Arguman parse (stdlib, argparse yok)
    args = sys.argv[1:]
    cli_key = None
    skip_setup = False

    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)
    if "--key" in args:
        idx = args.index("--key")
        try:
            cli_key = args[idx + 1]
            skip_setup = True
        except IndexError:
            print("Kullanim: python3 agent.py --key GROQ_KEY")
            sys.exit(1)
    if "--no-setup" in args:
        skip_setup = True

    # Banner
    banner()

    # Key kurulum ekrani (CLI'dan verilmemisse)
    if not skip_setup:
        groq_key = setup_screen()
    else:
        groq_key = cli_key

    # API nesnesi
    api = PhantomAPI(groq_key=groq_key)

    mode = "OVHcloud(anonim) + Groq(fallback)" if groq_key else "OVHcloud Anonim"
    print(f"{C_DIM}  Mod: {mode}{C_RESET}")
    print(f"{C_DIM}  Yardim icin: help  |  Cikis: exit{C_RESET}\n")

    conversation: list[dict] = []

    while True:
        # ── Girdi ──────────────────────────────────────────
        try:
            raw = input(f"\n{C_USER}[Sen]{C_RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n{C_DIM}👻 Phantom kapandi. Hafiza temizlendi.{C_RESET}\n")
            sys.exit(0)

        if not raw:
            continue

        cmd_low = raw.lower()

        # ── Dahili komutlar ────────────────────────────────

        if cmd_low in ("exit", "quit", "cikis", "bye", "q"):
            print(f"\n{C_DIM}👻 Phantom kapandi. Hafiza temizlendi.{C_RESET}\n")
            sys.exit(0)

        if cmd_low in ("clear", "cls", "temizle"):
            os.system("clear" if os.name != "nt" else "cls")
            banner()
            continue

        if cmd_low in ("reset", "sifirla"):
            conversation.clear()
            print(f"{C_DIM}  ↺ Konusma gecmisi temizlendi.{C_RESET}")
            continue

        if cmd_low in ("help", "yardim", "?"):
            help_msg(api)
            continue

        if cmd_low == "status":
            print(f"\n  {api.status_str()}")
            print(f"  Konusma turu : {len(conversation) // 2}")
            print(f"  Max gecmis   : {MAX_HISTORY}")
            continue

        # Groq key calistirirken degistirme: "groq-key gsk_xxx"
        if cmd_low.startswith("groq-key"):
            parts = raw.split(maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                api.set_groq_key(parts[1].strip())
                api.groq_ok = True   # Eski limiti sifirla
                print(f"  {C_AGENT}✓ Groq key guncellendi.{C_RESET}")
            else:
                print(f"  {C_WARN}Kullanim: groq-key YOUR_KEY{C_RESET}")
            continue

        # ── Konusma gecmisi limiti ─────────────────────────
        if len(conversation) > MAX_HISTORY:
            conversation = conversation[-MAX_HISTORY:]

        conversation.append({"role": "user", "content": raw})

        # ── ReAct Dongusu ─────────────────────────────────
        print(f"\n{C_DIM}  ▸ Dusunuyor...{C_RESET}", end="", flush=True)

        for _ in range(MAX_TOOL_LOOPS):
            response = api.call(conversation)

            # API tamamen oldu — konusma gecmisine ekleme, kullaniciya dondur
            if response == "__DEAD__":
                # Son kullanici mesajini gecmisten cikar (tutarsiz konusma olmasin)
                if conversation and conversation[-1]["role"] == "user":
                    conversation.pop()
                break

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
                    "content": (
                        f"Arac sonuclari:\n{tool_out}\n\n"
                        "Bu sonuclara gore kullaniciya Turkce ve ozlu cevap ver."
                    ),
                })
                print(f"\n{C_DIM}  ▸ Sonuc degerlendiriliyor...{C_RESET}", end="", flush=True)
        else:
            print(f"\n{C_AGENT}[{AGENT_NAME}]{C_RESET} {C_WARN}(Maksimum arac dongusune ulasildi.){C_RESET}\n")

if __name__ == "__main__":
    main()