#!/usr/bin/env bash

# Spostati nella cartella del progetto
cd "$(dirname "$0")"

echo "=========================================================="
echo "🚀 AVVIO ACADEMIC KB 3D GRAPH - ACCELERATORE M1 TURBO"
echo "=========================================================="

PORT=8000

# 1. Controlla se il server è già attivo, altrimenti avvialo
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Server già attivo su http://127.0.0.1:$PORT"
else
    echo "⚡ Avvio server Study Engine in background..."
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    fi
    python run_api.py > /dev/null 2>&1 &
    SERVER_PID=$!
    echo "⏳ Attendo avvio porta $PORT..."
    sleep 2
fi

echo "🏎️  Lancio istanza dedicata di Google Chrome (GPU Metal nativa M1)..."

# Rimuovi eventuali lock orfani della sessione precedente
rm -f /tmp/chrome_turbo_m1/Singleton* 2>/dev/null || true

TIMESTAMP=$(date +%s)
URL="http://127.0.0.1:$PORT/graph_3d.html?v=$TIMESTAMP"

# Usa un profilo isolato dedicato (/tmp/chrome_turbo_m1) in modo che macOS
# crei un PROCESSO SEPARATO con i flag Metal attivi al 100%, anche se Chrome è già aperto!
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --user-data-dir="/tmp/chrome_turbo_m1" \
  --use-angle=metal \
  --ignore-gpu-blocklist \
  --enable-gpu-rasterization \
  --enable-zero-copy \
  --enable-webgpu \
  --enable-features=Vulkan,Metal \
  --disable-background-timer-throttling \
  --disable-renderer-backgrounding \
  --no-first-run \
  --no-default-browser-check \
  --high-dpi-support=1 \
  --app="$URL" > /dev/null 2>&1 &

CHROME_PID=$!

if [ ! -z "$CHROME_PID" ]; then
    renice -10 -p $CHROME_PID >/dev/null 2>&1 || true
fi

echo "=========================================================="
echo "🟢 Finestra Grafo 3D Turbo avviata con acceleratore hardware!"
echo "=========================================================="
