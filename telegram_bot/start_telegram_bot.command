#!/bin/bash
# ==============================================================================
# DIMEOGPT Telegram Bot — Avvio rapido (macOS)
# ==============================================================================
# Doppio click su questo file per avviare il bot Telegram.
# Prerequisiti:
#   1. File .env configurato nella stessa directory (vedi .env.example)
#   2. Virtual environment Python del progetto academic-kb
#   3. Knowledge Graph Neo4j attivo (opzionale, si può usare fallback API)
# ==============================================================================

# Vai nella directory dello script
cd "$(dirname "$0")"

echo "🤖 DIMEOGPT Telegram Bot"
echo "━━━━━━━━━━━━━━━━━━━━━━━"

# Cerca il virtual environment del progetto parent
VENV_PATH="../.venv"
if [ -d "$VENV_PATH" ]; then
    echo "📦 Attivo virtual environment: $VENV_PATH"
    source "$VENV_PATH/bin/activate"
else
    echo "⚠️  Virtual environment non trovato in $VENV_PATH"
    echo "   Uso il Python di sistema."
fi

# Carica le variabili d'ambiente dal .env locale
if [ -f ".env" ]; then
    echo "🔧 Carico variabili da .env"
    set -a
    source .env
    set +a
else
    echo "❌ File .env non trovato!"
    echo "   Copia .env.example in .env e configura il token del bot."
    echo ""
    read -p "Premi Invio per uscire..."
    exit 1
fi

# Carica anche le env vars del progetto parent (per Neo4j, embeddings, ecc.)
PARENT_ENV="../.env"
if [ -f "$PARENT_ENV" ]; then
    echo "🔧 Carico variabili da $PARENT_ENV (KG config)"
    set -a
    source "$PARENT_ENV"
    set +a
    # Ripristina il token Telegram (il .env locale ha priorità)
    if [ -f ".env" ]; then
        set -a
        source .env
        set +a
    fi
fi

# Verifica che il token sia configurato
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo ""
    echo "❌ TELEGRAM_BOT_TOKEN non configurato!"
    echo "   Imposta il token nel file .env"
    echo ""
    read -p "Premi Invio per uscire..."
    exit 1
fi

echo "🚀 Avvio bot..."
echo ""

# Avvia il bot dal package (dalla directory parent per gli import)
cd ..
python -m telegram_bot.bot

echo ""
echo "🛑 Bot terminato."
read -p "Premi Invio per chiudere..."
