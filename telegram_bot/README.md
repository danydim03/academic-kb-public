# 🤖 DIMEOGPT Telegram Bot Bridge

Bridge Telegram per interagire con il **Knowledge Graph Accademico** (DIMEOGPT) direttamente dal tuo telefono, tablet o computer.

---

## 📌 Architettura

```
Telegram App (Desktop / Mobile)
          │  (HTTPS Long Polling)
          ▼
    telegram_bot.bot (python-telegram-bot v21)
          │
    telegram_bot.middleware (Rate Limiter & Whitelist)
          │
    telegram_bot.dimeogpt_client
    ┌─────┴─────────────────────────┐
    │                               │
    ▼ (1° scelta: zero latency)     ▼ (2° scelta: fallback)
MCP Nativo (mcp_server.server)   FastAPI Server (localhost:8000)
    │                               │
    └──────────────┬────────────────┘
                   ▼
         Neo4j Knowledge Graph
      (26.000+ Chunk Accademici)
```

---

## 🚀 Funzionalità

- **💬 Query Diretta**: Puoi scrivere qualsiasi domanda direttamente nella chat (es. `spiegami HTTP/2` o `come funziona Raft?`) e riceverai la risposta accademica.
- **🔍 Modalità di Ricerca**:
  - `/ask <domanda>` — Ricerca Standard (`academic_context`, $k=5$, mirata)
  - `/deep <domanda>` — Ricerca Approfondita (`deep_research`, multi-tier $k \approx 8\text{-}15$)
  - `/thesis <domanda>` — Ricerca Tesi/Macro (`thesis_research`, campionamento esteso $k=28$)
- **📊 Diagnostica**:
  - `/status` — Health check in tempo reale dello stato di Neo4j, conteggio nodi e corsi disponibili
  - `/help` — Guida rapida ai comandi
- **🛡️ Sicurezza & Affidabilità**:
  - **Rate Limiting**: sliding-window personalizzabile (default: 5 richieste/min per utente)
  - **Whitelist Utenti**: possibilità di restringere l'accesso a specifici Telegram User ID
  - **Auto-Chunking Telegram**: i messaggi lunghi che eccedono i 4096 caratteri vengono divisi automaticamente senza tagliare frasi o formule a metà.

---

## ⚙️ Configurazione

1. Nella cartella `telegram_bot/` è presente il template `.env.example`.
2. Crea il file `.env` (già configurato e protetto da `.gitignore`):
```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_ALLOWED_USERS=
RATE_LIMIT_MAX_REQUESTS=5
RATE_LIMIT_WINDOW_SECONDS=60
LOG_LEVEL=INFO
FASTAPI_BASE_URL=http://127.0.0.1:8000
```
> **Nota**: Se `TELEGRAM_ALLOWED_USERS` è vuoto, il bot è in **Open Mode** (puoi scrivergli dal tuo account Telegram). Se desideri renderlo privato solo per te, inserisci il tuo Telegram User ID (ottenibile scrivendo a `@userinfobot`).

---

## 💻 Come Avviare il Bot

### Metodo 1: Doppio Click (macOS Finder)
Fai doppio click sul file:
```bash
telegram_bot/start_telegram_bot.command
```
Lo script attiverà automaticamente il virtual environment del progetto, caricherà le credenziali e avvierà il bot.

### Metodo 2: Da Terminale
```bash
cd academic-kb
source .venv/bin/activate
python -m telegram_bot.bot
```

---

## 🧪 Test di Funzionamento

Una volta avviato il bot:
1. Apri Telegram e cerca **`@DIMEOGPTbot`** (oppure visita [t.me/DIMEOGPTbot](https://t.me/DIMEOGPTbot)).
2. Clicca su **Avvia** o invia `/start`.
3. Invia `/status` per verificare che sia connesso al Knowledge Graph di Tor Vergata.
4. Fai una domanda di prova:
   - `/ask spiegami il protocollo Raft`
   - `/deep differenze tra Paxos e Raft`
   - `/thesis forme bilineari e congruenza`
