# DIMEOGPT Hub — Web Cockpit Plugin

Il plugin **DIMEOGPT Hub** estende l'interfaccia Web UI del Cockpit accademico con strumenti professionali per l'interazione LLM avanzata, il monitoraggio in tempo reale dei costi e dei consumi di token in Euro, la selezione delle modalità di ricerca accademica e l'esportazione delle sessioni.

---

## 🚀 Caratteristiche Principali

1. **Monitoraggio Token & Costo in Euro in Tempo Reale**:
   - Integrato direttamente nella **statusbar** inferiore (`footer.statusbar`).
   - Visualizza i token del singolo turno (`tok`) e la stima del costo convertita in Euro (€) con tasso ufficiale (`costUSD * 0.92`), ad esempio:
     `🪙 4.433 tok · € 0,0021`
   - **Click Interattivo con Notifica Toast**: cliccando sull'indicatore nella statusbar compare un elegante toast fluttuante con i dettagli analitici (Input tokens, Output tokens, Cache Hit, Costo turno in $ e in €, Token cumulativi dell'intera sessione).
   - **Nessun Overlay Fastidioso**: collocato in modo nativo nella barra di stato senza coprire il pulsante di invio o la casella di testo del composer.

2. **Modalità di Ricerca Accademica Dinamica**:
   - Menu di selezione rapida nel composer:
     - 🔍 **Standard (`normal`)**: retrieval bilanciato per domande di studio e chiarimenti rapidi.
     - 🔬 **Approfondita (`deep_research`)**: retrieval multilivello ad alta granularità sui concetti complessi.
     - 🎓 **Tesi / Macro (`thesis_research`)**: retrieval esteso a 25–30 chunk con incrocio bibliografico tra libri e articoli scientifici.

3. **Esportazione Sessioni di Studio**:
   - Pulsanti dedicati nella topbar per esportare la conversazione attiva in **Markdown (`.md`)** strutturato o in formato **JSON**.

4. **Tema Cyber-Green Liquid Glass**:
   - Foglio di stile ottimizzato (`themes/chatgpt-custom.css`) coordinato con l'ecosistema Academic Study Suite.

---

## 📦 Installazione e Configurazione

### 1. Copia dei File del Plugin
Copia la cartella del plugin nella directory dei plugin della tua Web UI (di norma `~/.pi-web/plugins/`):

```bash
# Crea la directory di destinazione
mkdir -p ~/.pi-web/plugins/dimeogpt-hub

# Copia i file del plugin
cp -r plugins/dimeogpt-hub/* ~/.pi-web/plugins/dimeogpt-hub/
```

### 2. Installazione del Tema CSS (Opzionale ma Consigliato)
Copia il tema custom nella cartella temi di `.pi-web`:

```bash
mkdir -p ~/.pi-web/themes
cp plugins/dimeogpt-hub/themes/chatgpt-custom.css ~/.pi-web/themes/
```

### 3. Riavvio del Servizio Web Cockpit
Riavvia il server Node.js del Cockpit per caricare il nuovo plugin e il server endpoint `/api/dimeogpt/stats`:

```bash
# Se gestito tramite processo di background / daemon
killall node || true
# oppure riavvia il server web
```

---

## 🧩 Architettura Tecnica

- `manifest.json`: specifica permessi (`ui`, `http`, `chat`, `storage`), selettore di modalità e azioni topbar.
- `index.mjs`: server-side plugin che legge in streaming i file di sessione JSONL, estrae i campi di costo e token dell'ultimo turno dell'assistente e calcola il controvalore in Euro.
- `client/entry.mjs`: client-side plugin che inietta l'indicatore `#dimeogpt-statusbar-cost`, intercetta gli stream dei messaggi e gestisce l'aggiornamento automatico e le animazioni toast.
- `client/cyber_kraken.mjs`: utility di styling e layout per l'interfaccia.
