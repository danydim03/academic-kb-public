#!/usr/bin/env bash
# Script rapido di sincronizzazione per la cartella MAGISTRALE
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "Ambiente virtuale non trovato in $DIR/.venv! Eseguo il setup..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e . reportlab
else
    source .venv/bin/activate
fi

python scripts/sync_magistrale.py "$@"
