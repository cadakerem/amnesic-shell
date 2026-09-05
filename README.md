# Phantom Agent

> Anonim, hesapsız, Linux terminalinde çalışan AI agent.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Dependencies](https://img.shields.io/badge/Dependencies-None%20(stdlib%20only)-brightgreen)

## Ne Yapar?

Phantom Agent; **hiçbir hesap açmadan, hiçbir API anahtarı girmeden** Kali Linux terminalinde çalışan, gerçek Linux araçlarını kullanabilen bir yapay zeka asistanıdır.

- 🔒 **Tamamen anonim** — Pollinations.ai API kullanır (kayıt/login yok)
- 🐧 **Gerçek Linux araçları** — Bash komutu çalıştırır, dosya oluşturur/okur/siler
- 🌐 **İnternete erişir** — URL'den içerik çekebilir
- 🧠 **Hafızası var** — Çok turlu konuşma, önceki mesajları hatırlar
- 💀 **İz bırakmaz** — Tüm konuşma geçmişi RAM'de yaşar, kapanışta silinir
- 📦 **Bağımlılıksız** — Sadece Python 3 stdlib (pip gerekmez)
- 🔌 **Taşınabilir** — USB DEPO'dan tek dosyayla çalışır

---

## Hızlı Başlangıç

```bash
python3 agent.py
```

Kali USB'den çalıştırmak için:
```bash
# DEPO bölümüne kopyala
cp agent.py /run/media/kali/DEPO/

# Her oturumda:
python3 /run/media/kali/DEPO/agent.py
```

---

## Yetenekler (Araçlar)

| Araç | Ne Yapar | Örnek |
|------|----------|-------|
| `bash` | Linux komutu çalıştırır | "Python versiyonu nedir?" |
| `file_read` | Dosya içeriğini okur | "şu dosyayı oku ve özetle" |
| `file_write` | Dosya oluşturur/yazar | "bir bash script yaz ve kaydet" |
| `file_delete` | Dosya siler | "temp dosyasını sil" |
| `file_list` | Dizin listeler | "/home/kali ne var?" |
| `fetch_url` | URL'den içerik çeker | "şu siteyi özetle" |

---

## Mimari: ReAct Döngüsü

```
[Kullanıcı Girişi]
       ↓
[Pollinations.ai API]  ← Ücretsiz, kayıtsız
       ↓
[Tool çağrısı var mı?]
   ├── Evet → [Aracı Çalıştır] → [Sonucu API'ye Geri Gönder] → ↑ (tekrar)
   └── Hayır → [Final Cevabı Ekrana Yaz]
```

---

## Proje Yapısı

```
phantom-agent/
└── agent.py    ← Tek dosya, her şey burada
```

---

## Gizlilik Notu

Pollinations.ai isteklerine `"private": true` parametresi gönderilir (log kaydını devre dışı bırakır). Buna rağmen uç sunucunun Tor çıkış IP'sini görebileceğini unutma. Gerçek anlamda sıfır iz için Kali USB + Anonsurf + bu agent kombinasyonunu kullan.

---

## Lisans

MIT
