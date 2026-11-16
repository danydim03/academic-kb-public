"""
Formattazione delle risposte per Telegram (HTML compatibile).

Converte la risposta accademica sintetizzata da DIMEOGPT in Telegram HTML,
proteggendo i caratteri speciali (<, >, &) ed evitando crash di parsing.
Nessun header o separatore superfluo viene aggiunto: viene restituita
esclusivamente la risposta finale pulita e ben impaginata.
"""
from __future__ import annotations

import re
from typing import List

# Limite Telegram per singolo messaggio
TELEGRAM_MAX_LENGTH = 4096


def format_response(raw: str, mode_label: str = "") -> str:
    """Formatta la risposta finale DIMEOGPT per Telegram in HTML.

    - Converte Markdown (titoli, grassetti, corsivi, elenchi, codice) in HTML
    - Preserva e protegge entità HTML ed espressioni matematiche
    - Rimuove separatori ridondanti o righe vuote multiple
    """
    if not raw or not raw.strip():
        return "⚠️ Nessuna risposta elaborata dal Knowledge Graph."

    text = raw.strip()

    # 1. Rimuovi eventuali righe di separatori eccessivi (━, ─, =)
    text = re.sub(r"[━─═]{5,}", "", text)

    # 2. Converti in Telegram HTML
    text = _markdown_to_telegram_html(text)

    # 3. Comprimi newline triple in doppie
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _markdown_to_telegram_html(text: str) -> str:
    """Converte Markdown in HTML valido per Telegram."""
    # Step 1: Escape delle entità HTML primarie
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Step 2: Blocchi di codice ```...```
    def _code_block_repl(m: re.Match) -> str:
        code_content = m.group(1).strip()
        return f"<pre>{code_content}</pre>"

    text = re.sub(r"```(?:[a-zA-Z0-9_-]+)?\n?([\s\S]*?)```", _code_block_repl, text)

    # Step 3: Codice inline `...`
    text = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", text)

    # Step 4: Display math $$...$$
    text = re.sub(r"\$\$([\s\S]*?)\$\$", r"<pre>\1</pre>", text)

    # Step 5: Inline math $...$
    text = re.sub(r"\$([^\$\n]+)\$", r"<code>\1</code>", text)

    # Step 6: Titoli Markdown (# Titolo, ## Titolo, ### Titolo)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)

    # Step 7: Grassetti **testo** o __testo__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

    # Step 8: Corsivi *testo* o _testo_ (non adiacenti a tag HTML)
    text = re.sub(r"(?<![*\w])\*([^*\n]+?)\*(?![*\w])", r"<i>\1</i>", text)
    text = re.sub(r"(?<![_\w])_([^_\n]+?)_(?![_\w])", r"<i>\1</i>", text)

    # Step 9: Normalizzazione elenchi puntati (- o * a inizio riga)
    text = re.sub(r"^[ \t]*[-*]\s+", "• ", text, flags=re.MULTILINE)

    return text


def split_long_message(text: str, max_length: int = TELEGRAM_MAX_LENGTH) -> List[str]:
    """Divide un testo lungo in parti ≤ max_length preservando i confini di riga."""
    if len(text) <= max_length:
        return [text]

    chunks: List[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Cerca l'ultimo newline entro il limite
        cut_point = remaining[:max_length].rfind("\n")
        if cut_point <= max_length // 3:
            # Nessun newline comodo, taglia allo spazio
            cut_point = remaining[:max_length].rfind(" ")
            if cut_point <= max_length // 3:
                cut_point = max_length

        chunk = remaining[:cut_point].strip()
        if chunk:
            chunks.append(chunk)

        remaining = remaining[cut_point:].lstrip()

        if len(chunks) > 25:
            # Sicurezza contro loop
            chunks.append(remaining[:max_length])
            break

    return chunks
