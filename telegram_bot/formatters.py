"""
Formattazione intelligente delle risposte per Telegram.

Gestisce la conversione da output DIMEOGPT → Markdown compatibile con Telegram,
il troncamento sicuro, e la suddivisione in messaggi multipli se necessario.
"""
from __future__ import annotations

import re
from typing import List

# Limite Telegram per un singolo messaggio
TELEGRAM_MAX_LENGTH = 4096


def format_response(raw: str, mode_label: str = "") -> str:
    """Formatta la risposta DIMEOGPT per Telegram.

    1. Pulisce artefatti del formato MCP
    2. Aggiunge header di modalità se specificato
    3. Converte in Markdown compatibile con Telegram (parse_mode='Markdown')
    """
    text = _clean_mcp_artifacts(raw)

    if mode_label:
        text = f"🔎 *{mode_label}*\n{'━' * 30}\n\n{text}"

    return text


def split_long_message(text: str, max_length: int = TELEGRAM_MAX_LENGTH) -> List[str]:
    """Divide un testo lungo in chunk ≤ max_length, tagliando a fine riga.

    Restituisce sempre almeno un elemento.
    """
    if len(text) <= max_length:
        return [text]

    chunks: List[str] = []
    suffix = "\n\n✂️ _...continua_"
    prefix = "📎 _...continuazione_\n\n"
    available_first = max_length - len(suffix)
    available_mid = max_length - len(suffix) - len(prefix)

    remaining = text
    is_first = True

    while remaining:
        if len(remaining) <= max_length:
            # Ultimo pezzo (o unico)
            if not is_first:
                remaining = prefix + remaining
            if len(remaining) <= max_length:
                chunks.append(remaining)
            else:
                # Edge case: prefix + remaining supera il limite
                avail = max_length - len(prefix)
                cut = _cut_at_newline(remaining[len(prefix):], avail)
                chunks.append(prefix + cut + suffix)
                remaining = remaining[len(prefix) + len(cut):]
                continue
            break

        avail = available_first if is_first else available_mid
        raw_part = remaining if is_first else remaining
        cut_text = _cut_at_newline(raw_part, avail if is_first else avail + len(prefix))

        if is_first:
            actual_cut = _cut_at_newline(remaining, avail)
            chunks.append(actual_cut + suffix)
            remaining = remaining[len(actual_cut):]
        else:
            actual_cut = _cut_at_newline(remaining, available_mid)
            chunks.append(prefix + actual_cut + suffix)
            remaining = remaining[len(actual_cut):]

        is_first = False

        # Safety: evita loop infinito
        if not remaining or len(chunks) > 20:
            break

    return chunks if chunks else [text[:max_length]]


def _cut_at_newline(text: str, max_len: int) -> str:
    """Taglia il testo a max_len cercando l'ultimo newline."""
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    last_nl = cut.rfind("\n")
    if last_nl > max_len // 2:
        return cut[:last_nl]
    return cut


def _clean_mcp_artifacts(text: str) -> str:
    """Rimuove artefatti tipici delle risposte MCP (es. separatori eccesivi, header duplicati)."""
    # Rimuove righe di soli separatori (━━━) molto lunghe
    text = re.sub(r"[━─═]{20,}", "━" * 30, text)
    # Comprime 3+ newline consecutive in 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
