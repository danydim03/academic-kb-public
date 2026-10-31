#!/usr/bin/env bash

# Spostati nella cartella dove risiede questo script
cd "$(dirname "$0")"

echo "=========================================="
echo "🧠 Avvio Academic KB Study Engine Server"
echo "=========================================="

# Libera la porta 8000 se è già in uso da un vecchio server
PORT=8000
PID=$(lsof -t -i:$PORT)
if [ ! -z "$PID" ]; then
    echo "⚠️  Porta $PORT già in uso. Chiudo il vecchio server (PID: $PID)..."
    kill -9 $PID
    sleep 1
fi

echo "✅ Attivazione ambiente virtuale..."
source .venv/bin/activate

echo "✅ Avvio server in corso..."
# Avvia uvicorn
python run_api.py &
SERVER_PID=$!

# Attendi 2 secondi per dare tempo al server di avviarsi
sleep 2

echo "✅ Apertura del browser..."
open "http://127.0.0.1:8000"

echo "=========================================="
echo "🟢 Server attivo! Chiudi questa finestra del terminale per fermarlo."
echo "=========================================="

# Mantiene il terminale aperto e in ascolto sul processo del server
wait $SERVER_PID
