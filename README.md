# CodeAssistant

macbookair_4 ning shaxsiy AI tizimi — FastAPI backend + React (Dark Glass) UI.
**Lokal `5code` modeli** yoki tekin cloud model bilan ishlaydi va **jonli sayt
(artifact)** yasay oladi.

| Qism | Port | Manzil |
| --- | --- | --- |
| Backend (FastAPI) | **1221** | <http://127.0.0.1:1221/docs> |
| Frontend (React + Vite) | **1991** | <http://localhost:1991> |
| Terminal | — | `5code` |

## Nima qila oladi

| Imkoniyat | Tavsif |
| --- | --- |
| **`5code` — lokal model** | Terminalda ham, saytda ham. Internetsiz, maxfiy, tekin |
| **React UI** | Vite + React Router · login, signup, modellar, chat, admin |
| **Tekin cloud AI** | Gemini free tier · Groq · OpenRouter · Claude |
| **Artifact** | AI to'liq HTML sayt yasaydi → o'ng panelda jonli ko'rinadi, versiyalanadi |
| **Streaming chat** | Javob token-token oqib keladi (SSE), fikrlash jarayoni ham ko'rinadi |
| **Suhbatlar tarixi** | SQLite'da saqlanadi, istalgan vaqtda davom ettirish mumkin |
| **Signup** | Ochiq ro'yxatdan o'tish — yangi hisob `user` roli bilan |
| **Multi-user** | `admin` va `user` rollari, har biri o'z suhbat/saytlarini ko'radi |
| **ai_in_pc** | Kompyuter ruxsati — terminal, fayl o'qish/yozish. Faqat admin beradi |
| **Xavfsizlik** | Tool gate + path sandbox + xavfli buyruqqa tasdiq + artifact CSP sandbox |

---

## AI provider tanlash

`.env` dagi `AI_PROVIDER` bitta qatorni almashtirasiz — qolgani o'zi ishlaydi.

| Provider | Narx | Kalit olish | Tavsif |
| --- | --- | --- | --- |
| **`gemini`** (default) | **tekin** | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | `gemini-3.5-flash` — free tier'dagi eng kuchli coding/agentic model, 1M kontekst. Kredit karta kerak emas |
| `openai` → Groq | **tekin** | [console.groq.com/keys](https://console.groq.com/keys) | Eng tez (LPU), `llama-3.3-70b-versatile` |
| `openai` → OpenRouter | **tekin** | [openrouter.ai/keys](https://openrouter.ai/keys) | O'nlab model, `:free` suffiksli variantlar |
| `openai` → Ollama | **tekin** | kerak emas | To'liq lokal, internetsiz. `OPENAI_BASE_URL=http://localhost:11434/v1` |
| `anthropic` | pullik | [console.anthropic.com](https://console.anthropic.com) | Claude Opus 5 — eng kuchli, adaptive thinking bilan |

**Har foydalanuvchi o'zi tanlaydi.** Saytdagi **Modellar** sahifasida lokal va
cloud modellar ro'yxati chiqadi; tanlov shu foydalanuvchi hisobiga bog'lanadi
(`ai_provider` / `ai_model`). Tanlanmasa — serverdagi `AI_PROVIDER` ishlatiladi.

```bash
# Tekin variant (tavsiya):
AI_PROVIDER=gemini
GEMINI_API_KEY=AIza...

# yoki Groq:
AI_PROVIDER=openai
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_API_KEY=gsk_...
OPENAI_MODEL=llama-3.3-70b-versatile
```

> Providerlar bir xil ichki formatdan foydalanadi — suhbat o'rtasida
> almashtirsangiz ham eski tarix ishlashda davom etadi.

---

## Artifact — jonli sayt yasash

Chatda shunchaki so'rang:

> «Menga fotograf uchun portfolio sayt yasab ber, dark tema, animatsiyalar bilan»

AI `create_artifact` tool'ini chaqiradi → **o'ng panelda jonli sayt ochiladi**.

- **Ko'rinish / Kod** tab'lari
- ↻ yangilash · ↗ yangi oynada ochish · ⤓ `.html` yuklab olish
- «Buni ko'kroq qil» desangiz — `update_artifact` yangi versiya yasaydi (`v2`, `v3`…)
- Chap menyu → **◫ Saytlarim** — barcha saytlar galereyasi, jonli preview bilan

**Xavfsizlik.** Artifact HTML'i model tomonidan yaratiladi, unga ishonib
bo'lmaydi. Shuning uchun u `Content-Security-Policy: sandbox` bilan
uzatiladi va `<iframe sandbox>` ichida ochiladi — `allow-same-origin`siz.
Ya'ni artifact bizning `localStorage`, cookie yoki DOM'imizga **umuman kira
olmaydi**. URL taxmin qilib bo'lmaydigan tasodifiy token (`/a/{token}`),
chunki iframe Bearer header yubora olmaydi.

---

## Tez ishga tushirish

```bash
cp .env.example .env
./run.sh              # backend 1221 + frontend 1991
```

So'ng brauzerda: <http://localhost:1991>

Birinchi kirish: `.env` dagi `ADMIN_PASSWORD` bilan. Bo'sh qoldirsangiz —
server birinchi ishga tushganda tasodifiy parol yaratadi va **logga bir marta**
chiqaradi (o'sha yerdan nusxa oling).
Yoki **Ro'yxatdan o'ting** — yangi hisob oddiy `user` roli bilan yaratiladi.

### Boshqa rejimlar

```bash
./run.sh api      # faqat backend (1221)
./run.sh web      # faqat frontend (1991)
./run.sh build    # React'ni yig'ib, bitta portda (1221) beradi
```

---

## `5code` — lokal model

Terminalda ham, saytda ham ishlaydigan shaxsiy kod modeli.
Asos: **qwen2.5-coder:14b** (~9GB) — 16GB RAM uchun eng yaxshi balans.

### O'rnatish

```bash
ollama pull qwen2.5-coder:14b   # ~9GB, bir marta
./ollama/install.sh             # 5code buyrug'ini o'rnatadi
```

`install.sh` sudo talab qilmaydi: skript `~/.local/bin` ga qo'yiladi va
kerak bo'lsa `PATH` ga o'zi qo'shiladi.

### Ishlatish

```bash
5code                              # interaktiv suhbat
5code "python da fayl o'qish"      # bir martalik savol
cat main.py | 5code "shuni tushuntir"
5code --web                        # web interfeysni ochish
5code --update                     # Modelfile o'zgarsa qayta yig'ish
5code --status                     # holat tekshiruvi
```

Model xulqi `ollama/Modelfile` da: o'zbek tili, kod sifati talablari,
UI animatsiya qoidalari, xavfsizlik ogohlantirishlari. O'zgartirgach
`5code --update` deysiz.

> **Ollama akkaunti kerak emas** — model butunlay lokal yaratiladi. Faqat uni
> ollama.com ga *publish* qilmoqchi bo'lsangiz `ollama login` qilasiz.

### Docker orqali

```bash
cp .env.example .env
docker compose up --build
```

> Docker ichida `ai_in_pc` buyruqlari **konteyner** ichida bajariladi —
> host kompyuterga tegmaydi. Host bilan ishlash kerak bo'lsa `./run.sh` ishlating.

---

## Xavfsizlik modeli

`ai_in_pc` tool'lari uch qatlam bilan himoyalangan:

1. **Ruxsat gate'i** — `ai_in_pc=False` bo'lsa tool'lar modelga umuman berilmaydi.
2. **Path sandbox** — barcha fayl amallari `WORKSPACE_ROOT` ichida qulflangan;
   `../` orqali chiqishga urinish `ToolError` bilan rad etiladi.
3. **Tasdiqlash** — `rm`, `sudo`, `dd`, `kill`, `curl | sh`, `DROP TABLE` va
   shunga o'xshash buyruqlar `confirmed=true` bo'lmasa bajarilmaydi. Model avval
   foydalanuvchidan og'zaki tasdiq so'raydi.

Artifact tool'lari (`create_artifact` / `update_artifact`) kompyuterga
tegmaydi — ular `ai_in_pc` ruxsatisiz ham ishlaydi.

Qo'shimcha: shell buyruqlari `SHELL_TIMEOUT_SECONDS` (default 60s) dan oshsa
majburan to'xtatiladi, chiqish hajmi cheklangan.

---

## API

| Method | Endpoint | Tavsif |
| --- | --- | --- |
| `POST` | `/api/auth/login` | Login → JWT token |
| `GET` | `/api/auth/me` | Joriy foydalanuvchi |
| `GET` | `/api/users` | Foydalanuvchilar (admin) |
| `POST` | `/api/users` | Yangi foydalanuvchi (admin) |
| `PATCH` | `/api/users/{id}` | Rol / `ai_in_pc` / parol / bloklash (admin) |
| `DELETE` | `/api/users/{id}` | O'chirish (admin) |
| `GET` | `/api/conversations` | Suhbatlar ro'yxati |
| `POST` | `/api/conversations` | Yangi suhbat |
| `GET` | `/api/conversations/{id}/messages` | Xabarlar tarixi |
| `DELETE` | `/api/conversations/{id}` | Suhbatni o'chirish |
| `POST` | `/api/chat` | Xabar yuborish → SSE oqim |
| `GET` | `/api/artifacts` | Saytlar ro'yxati |
| `GET` | `/api/artifacts/{id}` | Bitta sayt (HTML kodi bilan) |
| `DELETE` | `/api/artifacts/{id}` | Saytni o'chirish |
| `GET` | `/a/{token}` | Saytning jonli HTML ko'rinishi (sandbox) |
| `POST` | `/api/auth/register` | Ro'yxatdan o'tish → JWT token |
| `GET` | `/api/models` | Mavjud modellar (lokal + cloud) |
| `PUT` | `/api/models/selection` | Model tanlash (foydalanuvchi uchun) |
| `POST` | `/api/users/ai-in-pc/all?enabled=true` | Hammaga ai_in_pc (admin) |
| `GET` | `/api/health` | Tizim holati + joriy provider |

Interaktiv hujjat: <http://127.0.0.1:8000/docs>

### SSE hodisalari (`POST /api/chat`)

```
{"type":"start",    "conversation_id": 1}
{"type":"thinking", "text": "..."}
{"type":"text",     "text": "..."}
{"type":"tool_use", "id":"call_1","name":"create_artifact","input":{...}}
{"type":"artifact", "id":1,"token":"...","title":"Portfolio","version":1}
{"type":"tool_result","id":"call_1","name":"create_artifact","content":"...","is_error":false}
{"type":"error",    "message":"..."}
{"type":"done",     "conversation_id": 1}
```

---

## Loyiha tuzilishi

```
app/
├── main.py          # FastAPI ilovasi, lifespan, admin seed
├── config.py        # Sozlamalar (.env)
├── database.py      # SQLAlchemy async engine
├── models.py        # User, Conversation, Message, Artifact
├── schemas.py       # Pydantic sxemalari
├── security.py      # bcrypt + JWT
├── deps.py          # Auth dependency'lari
├── ai/
│   ├── client.py    # Tool-calling sikli + oqim hodisalari
│   ├── tools.py     # ai_in_pc + artifact tool'lari
│   └── providers/   # Provider abstraksiyasi
│       ├── base.py              # Kanonik format + Provider interfeysi
│       ├── gemini_provider.py   # Gemini REST (tekin)
│       ├── openai_compat.py     # Groq / OpenRouter / Ollama
│       └── anthropic_provider.py# Claude
└── routers/
    ├── auth.py · users.py · chat.py · artifacts.py
web/                 # React frontend (Vite)
├── vite.config.js   # port 1991, /api va /a → 1221 proxy
└── src/
    ├── api.js       # fetch qatlami + SSE oqim o'quvchi
    ├── markdown.js  # yengil markdown renderer
    ├── context/     # AuthContext (login, signup, toast)
    ├── components/  # Shell, Message, ArtifactPanel, Toasts
    └── pages/       # Login, Signup, Chat, Models, Gallery, Admin
ollama/
├── Modelfile        # 5code modeli ta'rifi
├── 5code            # terminal buyrug'i
└── install.sh       # o'rnatuvchi
tests/               # 60 ta test
```

### Yangi provider qo'shish

`Provider` klassidan meros olib, `stream_turn()` ni yozing va registrga
qo'shing — qolgan hamma narsa (tool sikli, artifactlar, tarix) o'zgarmaydi.

---

## Testlar

```bash
.venv/bin/python -m pytest      # 60 test
.venv/bin/ruff check app tests  # lint
```

AI API mock qilingan — testlar uchun kalit kerak emas.

---

## Sozlamalar (`.env`)

| O'zgaruvchi | Default | Tavsif |
| --- | --- | --- |
| `AI_PROVIDER` | `gemini` | `gemini` / `openai` / `anthropic` |
| `GEMINI_API_KEY` | — | Tekin kalit (aistudio.google.com/apikey) |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Free tier'dagi eng kuchli model |
| `OPENAI_BASE_URL` | Groq | OpenAI-mos xizmat manzili |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | — | Groq / OpenRouter / Ollama uchun |
| `ANTHROPIC_API_KEY` | — | Claude (ixtiyoriy, pullik) |
| `SECRET_KEY` | — | JWT kaliti — production'da albatta o'zgartiring |
| `WORKSPACE_ROOT` | `./workspace` | ai_in_pc sandbox papkasi |
| `SHELL_TIMEOUT_SECONDS` | `60` | Shell buyrug'i limiti |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `macbookair_4` / *(bo'sh)* | Birinchi admin. Parol bo'sh bo'lsa tasodifiy yaratiladi |
| `BACKEND_PORT` / `FRONTEND_PORT` | `1221` / `1991` | Portlar |
| `ALLOW_SIGNUP` | `true` | `false` bo'lsa — faqat admin user yaratadi |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | `localhost:11434` / `5code` | Lokal model |

---

## Production uchun eslatma

- `SECRET_KEY` ni albatta almashtiring:
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `ADMIN_PASSWORD` ni birinchi kirishdan keyin o'zgartiring.
- HTTPS orqasiga qo'ying (nginx/caddy) — JWT token oddiy HTTP'da xavfli.
- SQLite bir serverga yetarli; ko'p instans kerak bo'lsa PostgreSQL'ga o'ting
  (`DATABASE_URL` ni almashtirish kifoya, `asyncpg` qo'shib).
- Artifactlar `/a/{token}` orqali **autentifikatsiyasiz** ochiladi (iframe
  cheklovi). Token 128-bit tasodifiy, lekin havolani ulashsangiz — sayt
  ko'rinadi. Maxfiy ma'lumot bo'lgan artifact yasamang.
