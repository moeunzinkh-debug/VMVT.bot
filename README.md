<div align="center">

# 🤖 VMVT.bot

**Telegram Bot សម្រាប់ទាញយកវីដេអូ TikTok ដោយគ្មាន Watermark**

គាំទ្រតំណខ្លី `vt.tiktok.com` និង `vm.tiktok.com` · គុណភាព HD · ឥតគិតថ្លៃ ១០០%

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-v22-2CA5E0?logo=telegram&logoColor=white)
![Render](https://img.shields.io/badge/Render-Free%20Plan-46E3B7?logo=render&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

---

## 📋 ទិដ្ឋភាពទូទៅ (Overview)

Bot នេះត្រូវបានរចនាឡើងដើម្បីទាញយកវីដេអូ TikTok ជាប្រភេទ **Drama Short** និងវីដេអូខ្លីៗផ្សេងទៀត។
អ្នកប្រើគ្រាន់តែផ្ញើតំណ TikTok ទៅ Bot ប៉ុណ្ណោះ ហើយ Bot នឹងផ្ញើវីដេអូគ្មាន Watermark ត្រឡប់មកវិញ។

```
អ្នកប្រើ ──► ផ្ញើតំណ TikTok ──► VMVT.bot ──► TikWM API / yt-dlp ──► វីដេអូគ្មាន Watermark ──► Telegram
```

### ✨ លក្ខណៈពិសេស (Features)

- ✅ ទាញយកវីដេអូ **គ្មាន Watermark**
- ✅ គាំទ្រតំណខ្លី `vt.tiktok.com` និង `vm.tiktok.com` (ពង្រីកដោយស្វ័យប្រវត្តិ)
- ✅ គាំទ្រតំណពេញលេញ `www.tiktok.com` និង `m.tiktok.com`
- ✅ គុណភាព **HD** (ប្រសិនបើមាន)
- ✅ បណ្ដុំរូបភាព / **Slideshow** ត្រូវបានផ្ញើជា Media Group
- ✅ ឥតគិតថ្លៃ ១០០%
- ✅ ដំណើរការលើ **Render Free Plan**
- ✅ មិនត្រូវការគណនី TikTok
- ✅ ឃ្លាំងសម្ងាត់ `file_id` → វីដេអូដដែលត្រូវបានផ្ញើភ្លាមៗ (មិនចាំបាច់ទាញយកម្តងទៀត)
- ✅ ការកំណត់អត្រាសំណើ (rate limit) ក្នុងម្នាក់ៗ ដើម្បីការពារ Spam
- ✅ ទាញយកជា **stream ទៅថាស** (RAM ទាប ស័ក្តិសមសម្រាប់ ៥១២ MB)

---

## 🏗️ រចនាសម្ព័ន្ធគម្រោង (Project Structure)

```
VMVT.bot/
├── bot/                          # កូដស្នូល
│   ├── __main__.py               # ចំណុចចូល (python -m bot)
│   ├── serve.py                  # ចំណុចចូលសម្រាប់តែ health server
│   ├── app.py                    # Application factory + bootstrap/teardown
│   ├── config.py                 # អថេរបរិស្ថាន (Settings dataclass)
│   ├── constants.py              # សោរ bot_data និងមីនុយពាក្យបញ្ជា
│   ├── logging_setup.py          # ការកំណត់ log
│   ├── texts.py                  # អត្ថបទទាំងអស់ជាភាសាខ្មែរ
│   ├── http_server.py            # aiohttp: /healthz, /, /stats, /webhook
│   ├── handlers/
│   │   ├── commands.py           # /start /help /about /ping /stats
│   │   └── links.py              # ដំណើរការតំណ TikTok (ស្នូល)
│   ├── services/
│   │   ├── tiktok.py             # វិភាគ URL, ពង្រីកតំណខ្លី
│   │   ├── downloader.py         # សម្របសម្រួល providers + ទាញយក
│   │   ├── cache.py              # TTL cache & Media cache (file_id)
│   │   ├── rate_limit.py         # Sliding-window rate limiter
│   │   └── providers/
│   │       ├── base.py           # MediaResult + ProviderError
│   │       ├── tikwm.py          # TikWM API (HD, គ្មាន watermark)
│   │       └── ytdlp.py          # yt-dlp (fallback)
│   └── utils/
│       └── formatting.py         # ទំហំ រយៈពេល caption HTML
├── tests/                        # ៧៦ តេស្ត (pytest, គ្មាន network)
├── render.yaml                   # Render Blueprint (free plan)
├── Procfile                      # web: python -m bot
├── runtime.txt                   # python-3.11.9
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

---

## 🚀 ចាប់ផ្តើមលឿន (Quick Start)

### ១. បង្កើត Bot ជាមួយ [@BotFather](https://t.me/BotFather)

```
/newbot  →  ដាក់ឈ្មោះ  →  ទទួលបាន BOT_TOKEN
```

### ២. ដំឡើងនិងដំណើរការក្នុងម៉ាស៊ីនផ្ទាល់

```bash
git clone https://github.com/moeunzinkh-debug/VMVT.bot.git
cd VMVT.bot

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # ដាក់ BOT_TOKEN របស់អ្នកនៅទីនេះ
export BOT_TOKEN="123456:AAF..."

python -m bot                      # ដំណើរការ
```

បន្ទាប់មកបើក Telegram ហើយផ្ញើតំណ TikTok ទៅ Bot របស់អ្នក 🎉

> សាកល្បង server តែឯង (គ្មាន token ក៏បាន)៖ `python -m bot.serve`
> រួចបើក <http://localhost:8080/healthz>

---

## ☁️ ដាក់ដំណើរការលើ Render (Deploy)

### វិធីទី ១ — Blueprint (ងាយបំផុត)

1. Push កូដទៅ GitHub
2. ចូល [Render Dashboard](https://dashboard.render.com) → **New → Blueprint**
3. ជ្រើស repository នេះ → Render អាន `render.yaml` ដោយស្វ័យប្រវត្តិ
4. បញ្ចូល `BOT_TOKEN` នៅពេលត្រូវបានសួរ → **Apply**

### វិធីទី ២ — ដោយដៃ

| វាល | តម្លៃ |
|---|---|
| Environment | `Python 3` |
| Build Command | `pip install --upgrade pip && pip install -r requirements.txt` |
| Start Command | `python -m bot` |
| Instance Type | `Free` |
| Health Check Path | `/healthz` |

Environment variables ដែលត្រូវការ៖ `BOT_TOKEN` (សម្ងាត់) ។

### ⏰ រក្សា Free Plan ឱ្យនៅដែន

Render Free "ដេក" បន្ទាប់ពីគ្មានសកម្មភាព ១៥ នាទី។
ដើម្បីឱ្យ Bot ដំណើរការ ២៤/៧ សូមបង្កើត Cron Job (ឧ. [cron-job.org](https://cron-job.org) ឬ UptimeRobot)
ដែលហៅ `https://<service>.onrender.com/healthz` រៀងរាល់ ១០ នាទីម្តង។

> 💡 `/healthz` ត្រូវបានបម្រើដោយ server ដូចគ្នានឹង Bot ដែរ ដូច្នេះវាប្រើតែ **មួយ port** ប៉ុណ្ណោះ។

### 🔁 Webhook ជំនួស Polling (ស្រេចចិត្ត)

```bash
MODE=webhook
WEBHOOK_URL=https://vmvt-bot.onrender.com
WEBHOOK_SECRET=some-random-string
```

---

## ⚙️ អថេរបរិស្ថាន (Environment Variables)

| អថេរ | លំនាំដើម | បរិយាយ |
|---|---|---|
| `BOT_TOKEN` | — | **ត្រូវការ** — token ពី @BotFather |
| `MODE` | `polling` | `polling` ឬ `webhook` |
| `WEBHOOK_URL` | — | URL សាធារណៈ (ត្រូវការសម្រាប់ webhook) |
| `WEBHOOK_PATH` | `/webhook` | ផ្លូវដែល Telegram POST updates |
| `WEBHOOK_SECRET` | — | តម្លៃ `X-Telegram-Bot-Api-Secret-Token` |
| `PORT` | `8080` | Port សម្រាប់ health server (Render កំណត់ដោយខ្លួនឯង) |
| `HOST` | `0.0.0.0` | អាសយដ្ឋានស្តាប់ |
| `MAX_UPLOAD_MB` | `48` | ទំហំអតិបរមាសម្រាប់ផ្ទុកឡើង (Telegram: ៥០ MB) |
| `DOWNLOAD_TIMEOUT` | `180` | ពេលកំណត់ទាញយក (វិនាទី) |
| `CONNECT_TIMEOUT` | `15` | ពេលកំណត់ភ្ជាប់ (វិនាទី) |
| `MAX_LINKS_PER_MESSAGE` | `3` | តំណអតិបរមាក្នុងសារមួយ |
| `TIKWM_ENABLED` | `true` | បើក/បិទ provider TikWM |
| `YTDLP_ENABLED` | `true` | បើក/បិទ provider yt-dlp |
| `TIKWM_API_URL` | `https://www.tikwm.com/api/` | ចំណុចបញ្ចប់ API |
| `RATE_LIMIT_PER_MIN` | `8` | ចំនួនតំណអតិបរមាក្នុងមួយនាទី / អ្នកប្រើ |
| `MEDIA_CACHE_TTL` | `21600` | រយៈពេលរក្សា `file_id` (វិនាទី) |
| `RESOLVE_CACHE_TTL` | `600` | រយៈពេលរក្សាលទ្ធផល resolve (វិនាទី) |
| `ADMIN_IDS` | — | Telegram user id(s) អាចប្រើ `/stats` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## 💬 របៀបប្រើ (Usage)

| ពាក្យបញ្ជា | បរិយាយ |
|---|---|
| `/start` | សារស្វាគមន៍ |
| `/help` | របៀបប្រើប្រាស់ |
| `/about` | អំពី Bot |
| `/ping` | ពិនិត្យស្ថានភាព & uptime |
| `/stats` | ស្ថិតិ (សម្រាប់ admin) |

**គ្រាន់តែផ្ញើតំណ** — គ្មានពាក្យបញ្ជាក៏បាន៖

```
https://vm.tiktok.com/ZMhvzrfeR/
https://vt.tiktok.com/ZSjxxxxx/
https://www.tiktok.com/@khmer.drama/video/7123456789012345678
```

Bot ឆ្លើយតបជាមួយវីដេអូគ្មាន Watermark + caption (ចំណងជើង អ្នកនិពន្ធ រយៈពេល គុណភាព)
និងប៊ូតុងតភ្ជាប់ទៅវីដេអូដើម និង profile អ្នកនិពន្ធ។

---

## 🧩 របៀបដំណើរការ (How it Works)

1. **ទាញយកតំណ** — `bot/services/tiktok.py` ស្វែងរកតំណ TikTok ក្នុងសារ ឬ caption,
   បន្ថែម `https://` បើខ្វះ កាត់សញ្ញាចុចចោល និងលុបតំណស្ទួន។
2. **ពង្រីកតំណខ្លី** — `vm.`/`vt.` ត្រូវបានដេញតាម redirect ដើម្បីយក `video_id` ពិត
   (បើបរាជ័យ នៅតែប្រើតំណខ្លីដដែល)។
3. **Resolve** — ប្រើ providers តាមលំដាប់អាទិភាព៖
   - **TikWM** → `hdplay` (HD គ្មាន watermark) → `play` → `wmplay`
   - **yt-dlp** → ជ្រើស format គ្មាន watermark ដែលមានគុណភាពខ្ពស់បំផុត
4. **ទាញយក** — stream ទៅឯកសារបណ្ដោះអាសន្នដោយកំណត់ទំហំ (`MAX_UPLOAD_MB`) ។
5. **ផ្ញើ** — upload ទៅ Telegram, រក្សាទុក `file_id` ក្នុង cache ។
6. **Fallback** — បើ URL CDN ផុតកំណត់ ឬទាញយកមិនបាន → yt-dlp ទាញយកពីតំណដើម រួច bot upload វីដេអូចូលក្នុងឆាត។ បើវីដេអូធំពេក ឬបរាជ័យទាំងអស់ នឹងប្រាប់កំហុសជំនួសការផ្ញើតំណក្រៅ។

---

## 🧪 តេស្ត (Tests)

```bash
pip install -r requirements-dev.txt
pytest -q          # ៧៦ តេស្ត គ្មាន network ត្រូវការ
ruff check .       # lint
```

តេស្តគ្របដណ្ដប់៖ ការវិភាគ URL, ពង្រីកតំណខ្លី, TikWM parsing (video + slideshow + កំហុស),
yt-dlp format selection, ទាញយក (size limit, content-type, HTTP errors), cache, rate limiter,
caption building, handler flow (happy path, cache hit, rate limit, oversized, slideshow),
health/webhook HTTP server និង config parsing។

---

## 🛠️ ដោះស្រាយបញ្ហា (Troubleshooting)

| បញ្ហា | ដំណោះស្រាយ |
|---|---|
| `BOT_TOKEN is not set` | ដាក់ token ក្នុង `.env` ឬ Environment Variables របស់ Render |
| `Conflict: terminated by other getUpdates` | មាន ២ instance កំពុងដំណើរការ — បិទមួយ ឬប្តូរ `MODE=webhook` |
| Bot មិនឆ្លើយតប (Render Free) | Service បាន "ដេក" — បន្ថែម cron job ទៅ `/healthz` |
| `រកមិនឃើញវីដេអូនេះទេ` | វីដេអូឯកជន/ត្រូវបានលុប ឬតំណមិនត្រឹមត្រូវ |
| `វីដេអូធំពេក` | ទំហំលើសកំណត់ upload របស់ Telegram — bot មិនផ្ញើតំណក្រៅទេ; សូមសាកល្បងវីដេអូតូចជាងនេះ |
| TikWM rate limit | Bot ប្តូរទៅ yt-dlp ដោយស្វ័យប្រវត្តិ; ឬដំឡើង `yt-dlp` |
| Port binding failed | កំណត់ `PORT` ឱ្យត្រូវនឹង platform (Render កំណត់ដោយខ្លួនឯង) |

---

## 🤝 ចូលរួមចំណែក (Contributing)

```bash
git checkout -b feature/my-idea
make test lint
# push + បើក Pull Request
```

ការរួមចំណែកត្រូវបានស្វាគមន៍ — ជាពិសេស provider ថ្មីៗ ភាសាថ្មីៗ
និងការធ្វើឱ្យប្រសើរឡើងនូវគុណភាពវីដេអូ។

---

## ⚖️ អាជ្ញាបណ្ណ (License)

[MIT](LICENSE) — សេរីសម្រាប់ការប្រើប្រាស់ផ្ទាល់ខ្លួន និងពាណិជ្ជកម្ម។
សូមគោរពសិទ្ធិអ្នកនិពន្ធនៃវីដេអូដែលអ្នកទាញយក។
