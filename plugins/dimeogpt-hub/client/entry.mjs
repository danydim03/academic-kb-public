/**
 * ~/.pi-web/plugins/dimeogpt-hub/client/entry.mjs
 * DIMEOGPT Hub - Client Entry Point
 */
import { defineView, onUiAction, hostApi } from "./sdk/index.mjs";
import { initCyberKrakenListener, triggerCyberKraken } from "./cyber_kraken.mjs";

export const DIMEOGPT_LOGO_DATA_URL = "data:image/png;base64,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";
export const DIMEOGPT_LOGO_URL = "/plugins-api/dimeogpt-hub/logo";
export const DIMEOGPT_BANNER_1_URL = "/plugins/dimeogpt-hub/client/welcome_banner_1.png?v=clean_no_crescents_v2";
export const DIMEOGPT_BANNER_2_URL = "/plugins/dimeogpt-hub/client/welcome_banner_2.png?v=clean_no_crescents_v2";


/**
 * Display a user notification using host bridge notifyAction,
 * CustomEvent fallback, and an in-DOM toast.
 */
function showNotification(text, duration = 4000) {
  // Hard suppression: NEVER show notifications for research modes under any circumstance
  if (!text || typeof text !== "string") return;
  const lower = text.toLowerCase();
  if (
    lower.includes("modalità ricerca") ||
    lower.includes("deep research") ||
    lower.includes("thesis research") ||
    lower.includes("standard (normal)") ||
    lower.includes("thesis_research") ||
    lower.includes("deep_research") ||
    lower.includes("tool associato")
  ) {
    return;
  }
  // 1. Try host notifyAction bridge
  const host = hostApi();
  if (host?.notifyAction && typeof host.notifyAction === "function") {
    try {
      host.notifyAction({ text });
    } catch {}
  }

  // 2. Try pi-web-ui standard toast event
  try {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("pi-web-ui:toast", { detail: { text } }));
    }
  } catch {}

  // 3. Fallback: lightweight styled floating toast
  try {
    if (typeof document !== "undefined") {
      let container = document.getElementById("dimeogpt-toast-container");
      if (!container) {
        container = document.createElement("div");
        container.id = "dimeogpt-toast-container";
        Object.assign(container.style, {
          position: "fixed",
          bottom: "24px",
          right: "24px",
          zIndex: "99999",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          pointerEvents: "none",
        });
        document.body.appendChild(container);
      }

      const toast = document.createElement("div");
      Object.assign(toast.style, {
        background: "rgba(13, 24, 19, 0.95)",
        color: "#f2fbf6",
        border: "1px solid #00a859",
        borderRadius: "8px",
        padding: "10px 16px",
        boxShadow: "0 8px 24px rgba(0, 0, 0, 0.4)",
        backdropFilter: "blur(12px)",
        fontSize: "13px",
        fontFamily: "system-ui, -apple-system, sans-serif",
        whiteSpace: "pre-line",
        lineHeight: "1.5",
        transition: "all 0.3s ease",
        opacity: "0",
        transform: "translateY(8px)",
        pointerEvents: "auto",
        cursor: "pointer",
      });
      toast.textContent = text;
      toast.onclick = () => toast.remove();
      container.appendChild(toast);

      requestAnimationFrame(() => {
        toast.style.opacity = "1";
        toast.style.transform = "translateY(0)";
      });

      setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(8px)";
        setTimeout(() => toast.remove(), 300);
      }, duration);
    }
  } catch {}
}

// Active suppression of any research mode toasts from any source (custom events, notices, DOM)
if (typeof window !== "undefined" && !globalThis.__dimeogptToastFilterAttached) {
  globalThis.__dimeogptToastFilterAttached = true;
  window.addEventListener(
    "pi-web-ui:toast",
    (e) => {
      const txt = String(e?.detail?.text || "").toLowerCase();
      if (
        txt.includes("ricerca") ||
        txt.includes("deep research") ||
        txt.includes("thesis") ||
        txt.includes("modalità ricerca")
      ) {
        e.stopImmediatePropagation();
        e.preventDefault();
      }
    },
    true
  );

  // Periodically purge any stray research mode toasts from the DOM
  setInterval(() => {
    try {
      const toasts = document.querySelectorAll("#dimeogpt-toast-container > div, .notice-card, .toast, .notice");
      toasts.forEach((el) => {
        const c = (el.textContent || "").toLowerCase();
        if (
          c.includes("modalità ricerca") ||
          c.includes("deep research") ||
          c.includes("thesis research") ||
          c.includes("standard (normal)")
        ) {
          el.remove();
        }
      });
    } catch {}
  }, 300);
}

/**
 * Triggers browser file download from Blob/string.
 */
function triggerDownload(filename, content, mimeType = "text/plain;charset=utf-8") {
  if (typeof window === "undefined" || typeof document === "undefined") return;
  const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Research Mode configurations & directives
export const RESEARCH_MODES = {
  normal: {
    id: "normal",
    label: "Standard (Normal)",
    badge: "🔍 STANDARD",
    k: "k ≤ 5",
    desc: "Retrieval standard con priorità su Slide e Appunti Notion (academic_context)",
    tool: "academic_context",
    directive: `[MODALITÀ RICERCA: normal]
Direttiva di esecuzione:
- Esegui il retrieval delle fonti accademiche usando lo strumento \`academic_context(query=...)\` ($k \\le 5$, priorità su slide dei corsi e appunti Notion, fallback su libri solo se insufficienti).
- Obbligo Intestazione Iniziale (Preambolo k):
  - **Tipologia di Ricerca**: Standard (academic_context)
  - **Fonti Interrogate (k)**: 🎓 Slide + Notion: X | 📖 Libri: Y | 📄 Articoli: Z (Totale k=K)
- Citazione puntuale delle fonti documentali per ogni concetto o formula: [TitoloDocumento.pdf, p. X].
- REGOLA IMMAGINI E GRAFICI (DIVIETO DI GENERAZIONE SPONTANEA):
  NON generare MAI file grafici, diagrammi, immagini PNG o SVG di tua iniziativa. La risposta a domande teoriche, di studio o concettuali (es. "hybrid encryption spiega", "come funziona X?") deve essere UNICAMENTE TESTUALE (con testo, punti elenco e formule LaTeX). Genera un file grafico (.png o .svg) SOLO ED ESCLUSIVAMENTE se l'utente lo richiede in modo esplicito nel prompt (es. "disegna", "crea un diagramma", "fai un grafico", "mostrami uno schema visivo"). In quel caso specifico, includi nel messaggio Markdown ![Titolo](nome_file.png).`
  },
  deep_research: {
    id: "deep_research",
    label: "Approfondita (deep_research)",
    badge: "🔬 DEEP RESEARCH",
    k: "k ≤ 20",
    desc: "Retrieval esteso multi-tier su Slide, Libri e Articoli scientifici (deep_research)",
    tool: "deep_research",
    directive: `[MODALITÀ RICERCA: deep_research]
Direttiva di esecuzione:
- Esegui la ricerca approfondita usando lo strumento \`deep_research(query=...)\` ($k \\le 20$, quote adattive e copertura estesa multi-tier su Slide, Libri di testo e Paper scientifici).
- Obbligo Intestazione Iniziale (Preambolo k):
  - **Tipologia di Ricerca**: Approfondita (deep_research)
  - **Fonti Interrogate (k)**: 🎓 Slide + Notion: X | 📖 Libri: Y | 📄 Articoli: Z (Totale k=K)
- Citazione puntuale delle fonti documentali per ogni concetto, attacco o protocollo: [TitoloDocumento.pdf, p. X].
- REGOLA IMMAGINI E GRAFICI (DIVIETO DI GENERAZIONE SPONTANEA):
  NON generare MAI file grafici, diagrammi, immagini PNG o SVG di tua iniziativa. La risposta a domande teoriche, di studio o concettuali (es. "hybrid encryption spiega", "come funziona X?") deve essere UNICAMENTE TESTUALE (con testo, punti elenco e formule LaTeX). Genera un file grafico (.png o .svg) SOLO ED ESCLUSIVAMENTE se l'utente lo richiede in modo esplicito nel prompt (es. "disegna", "crea un diagramma", "fai un grafico", "mostrami uno schema visivo"). In quel caso specifico, includi nel messaggio Markdown ![Titolo](nome_file.png).`
  },
  thesis_research: {
    id: "thesis_research",
    label: "Tesi / Macro (thesis_research)",
    badge: "🎓 THESIS RESEARCH",
    k: "k = 25-30",
    desc: "Retrieval ad alto volume stratificato per tesi magistrali e rassegne bibliografiche (thesis_research)",
    tool: "thesis_research",
    directive: `[MODALITÀ RICERCA: thesis_research]
Direttiva di esecuzione:
- Esegui la ricerca estesa ad alto volume per tesi magistrale usando lo strumento \`thesis_research(query=..., top_k=28)\` (volume esteso 25-30 chunk, campionamento stratificato ~45% libri di testo fondativi, ~35% articoli/paper dello stato dell'arte, ~20% slide dei corsi).
- Struttura la dissertazione con profondità accademica (Introduzione/Motivazione, Fondamenti Teorici, Stato dell'Arte, Analisi Critica / Proposta Architetturale).
- Obbligo Intestazione Iniziale (Preambolo k):
  - **Tipologia di Ricerca**: Tesi / Macro Ricerca (thesis_research)
  - **Fonti Interrogate (k)**: 🎓 Slide + Notion: X | 📖 Libri: Y | 📄 Articoli: Z (Totale k=28)
- Citazione puntuale delle fonti documentali per ogni concetto: [TitoloDocumento.pdf, p. X].
- REGOLA IMMAGINI E GRAFICI (DIVIETO DI GENERAZIONE SPONTANEA):
  NON generare MAI file grafici, diagrammi, immagini PNG o SVG di tua iniziativa. La risposta a domande teoriche, di studio o concettuali (es. "hybrid encryption spiega", "come funziona X?") deve essere UNICAMENTE TESTUALE (con testo, punti elenco e formule LaTeX). Genera un file grafico (.png o .svg) SOLO ED ESCLUSIVAMENTE se l'utente lo richiede in modo esplicito nel prompt (es. "disegna", "crea un diagramma", "fai un grafico", "mostrami uno schema visivo"). In quel caso specifico, includi nel messaggio Markdown ![Titolo](nome_file.png).`
  }
};

/** Handler: Research Mode Selection (silent switch - no notifications or popups) */
export function handleSelectResearchMode(itemId, value) {
  const modeKey = String(value || "normal").toLowerCase();
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("dimeogpt:research-mode", modeKey);
    }
  } catch {}

  // Synchronize select inputs across the DOM immediately without showing any toast or popup
  try {
    if (typeof document !== "undefined") {
      const selects = document.querySelectorAll(".composer select, [data-slot='composer.actions'] select, select");
      selects.forEach((sel) => {
        const hasResearchOpts = Array.from(sel.options).some((opt) =>
          ["normal", "deep_research", "thesis_research"].includes(opt.value)
        );
        if (hasResearchOpts && sel.value !== modeKey) {
          sel.value = modeKey;
        }
        try {
          const reactPropsKey = Object.keys(sel).find((k) => k.startsWith("__reactProps$"));
          if (reactPropsKey && sel[reactPropsKey]) {
            sel[reactPropsKey].value = modeKey;
          }
        } catch {}
      });
    }
  } catch {}
}

// Model lookup map (retained for backward compatibility)
const MODEL_LABELS = {
  gemini: "Google Gemini",
  claude: "Anthropic Claude",
  "gpt-4o": "OpenAI GPT-4o",
  ollama: "Ollama (Local)",
};

/** Handler: Model Selection (Legacy) */
export function handleSelectModel(itemId, value) {
  const modelKey = String(value || "").toLowerCase();
  const displayName = MODEL_LABELS[modelKey] || value || "Unknown Model";
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("dimeogpt:selected-model", modelKey);
    }
  } catch {}
  showNotification(`Active model switched to ${displayName} (${modelKey})`);
}

/** Handler: Export Markdown */
export async function handleExportMarkdown() {
  try {
    const res = await fetch("/plugins-api/dimeogpt-hub/export?format=markdown");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    const dateStr = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    triggerDownload(`dimeogpt-transcript-${dateStr}.md`, text, "text/markdown;charset=utf-8");
    showNotification("Transcript exported as Markdown (.md)");
  } catch (err) {
    showNotification(`Export Markdown failed: ${err.message}`);
  }
}

/** Handler: Export JSON */
export async function handleExportJson() {
  try {
    const res = await fetch("/plugins-api/dimeogpt-hub/export?format=json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    const dateStr = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    triggerDownload(`dimeogpt-transcript-${dateStr}.json`, text, "application/json;charset=utf-8");
    showNotification("Transcript exported as JSON (.json)");
  } catch (err) {
    showNotification(`Export JSON failed: ${err.message}`);
  }
}

/** Handler: Token Usage */
export async function handleTokenUsage() {
  try {
    localStorage.setItem("dimeogpt:cost-widget-open", "true");
    const data = await fetchTokenCostData(true);
    enforceDimeogptCostWidget();
    if (data) {
      const last = data.lastResponse || {};
      const turnTok = Number(last.tokens?.turnTokens ?? ((last.tokens?.input ?? 0) + (last.tokens?.output ?? 0)));
      const costEur = formatEur(last.costEUR);
      const msg = [
        `📊 DIMEOGPT Consumo & Costi`,
        `• Modello: ${data.model || "default"}`,
        `• Risposta Attiva: ${turnTok.toLocaleString("it-IT")} tok`,
        `• Costo Risposta: ${costEur}`,
        `• Totale Sessione: ${(data.cumulative?.tokens?.total ?? 0).toLocaleString("it-IT")} tok (${formatEur(data.cumulative?.costEUR)})`,
      ].join("\n");
      showNotification(msg, 5000);
    }
  } catch (err) {
    showNotification(`Errore lettura consumi: ${err.message}`);
  }
}

// Auto-apply DIMEOGPT theme & branding

/**
 * Ensures all images in markdown responses render inline cleanly without broken icons.
 * Also auto-expands present_files cards so visual outputs are immediately visible.
 */
function enforceInlineMediaRendering() {
  if (typeof document === "undefined") return;

  // Retroactive Auto-Surface: if an assistant message discusses an image but has no visual, inject it
  const msgs = document.querySelectorAll(".msg-assistant, .msg[data-role='assistant']");
  msgs.forEach((msg) => {
    if (msg.dataset.dimeogptMediaChecked) return;
    const text = msg.textContent || "";

    let fileToInject = null;
    let caption = "Grafico Generato";

    if ((text.includes("gradient") || text.includes("gradienti")) && text.includes("discesa")) {
      fileToInject = "/gradient_descent_confronto.png";
      caption = "Confronto Batch vs Stochastic Gradient Descent";
    } else if (text.includes("sigmoide") || text.includes("sigmoide logistica")) {
      fileToInject = "/sigmoide.png";
      caption = "Funzione Sigmoide Logistica";
    } else if (text.includes("rpyc") && (text.includes("callback") || text.includes("asincron"))) {
      fileToInject = "/artifacts/rpyc_callback_simple.png";
      caption = "Diagramma Callback Asincrone RPyC";
    }

    if (fileToInject && !msg.querySelector(`img[src*="${fileToInject}"]`)) {
      msg.dataset.dimeogptMediaChecked = "true";
      const wrap = document.createElement("div");
      wrap.className = "dimeogpt-injected-image-box";
      wrap.style.margin = "14px 0";
      wrap.style.textAlign = "center";

      const titleEl = document.createElement("div");
      titleEl.style.fontSize = "12.5px";
      titleEl.style.fontWeight = "600";
      titleEl.style.color = "#00ff88";
      titleEl.style.marginBottom = "8px";
      titleEl.textContent = "📊 " + caption;

      const img = document.createElement("img");
      img.src = fileToInject;
      img.alt = caption;
      img.style.maxWidth = "100%";
      img.style.height = "auto";
      img.style.borderRadius = "10px";
      img.style.border = "1px solid rgba(0, 255, 136, 0.4)";
      img.style.boxShadow = "0 6px 24px rgba(0, 0, 0, 0.6)";
      img.style.cursor = "zoom-in";
      img.onclick = () => openImageLightbox(img.src);

      wrap.appendChild(titleEl);
      wrap.appendChild(img);

      const targetContainer = msg.querySelector(".msg-text-main, .msg-text, .msg-body") || msg;
      targetContainer.appendChild(wrap);
    }
  });

  if (typeof document === "undefined") return;

  // Inject custom CSS for inline images and present-card if not already present
  if (!document.getElementById("dimeogpt-inline-media-css")) {
    const style = document.createElement("style");
    style.id = "dimeogpt-inline-media-css";
    style.textContent = `
      .md img, .msg-text img {
        max-width: 100% !important;
        height: auto !important;
        border-radius: 10px !important;
        margin: 14px 0 !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.45) !important;
        border: 1px solid rgba(0, 255, 136, 0.3) !important;
        display: block !important;
        cursor: zoom-in !important;
        background: #0d1813 !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease !important;
      }
      .md img:hover, .msg-text img:hover {
        transform: scale(1.01) !important;
        box-shadow: 0 6px 28px rgba(0, 255, 136, 0.35) !important;
      }
      .present-card {
        margin: 14px 0 !important;
        border: 1px solid rgba(0, 255, 136, 0.3) !important;
        background: rgba(13, 24, 19, 0.85) !important;
        border-radius: 12px !important;
        padding: 12px !important;
        display: block !important;
      }
      .present-media {
        display: block !important;
        width: 100% !important;
        text-align: center !important;
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        cursor: zoom-in !important;
      }
      .present-media img {
        max-width: 100% !important;
        height: auto !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 14px rgba(0, 0, 0, 0.3) !important;
      }
    `;
    document.head.appendChild(style);
  }

  // Scan and repair all markdown images
  const mdImgs = document.querySelectorAll(".md img, .msg-text img");
  mdImgs.forEach((img) => {
    if (img.dataset.dimeogptFixed) return;
    img.dataset.dimeogptFixed = "true";

    img.addEventListener("click", (e) => {
      e.stopPropagation();
      openImageLightbox(img.src);
    });

    img.addEventListener("error", () => {
      const currentSrc = img.getAttribute("src") || "";
      if (!currentSrc || currentSrc.includes("/api/file?")) return;

      let cleanPath = currentSrc.replace(/^file:\/\//, "");
      if (!cleanPath.startsWith("/") && !cleanPath.startsWith("http")) {
        cleanPath = "artifacts/" + cleanPath;
      }
      img.src = "/api/file?path=" + encodeURIComponent(cleanPath);
    });
  });

  // Auto-expand any present_files toolcall
  const toolcalls = document.querySelectorAll(".toolcall");
  toolcalls.forEach((tc) => {
    const title = tc.getAttribute("title") || "";
    const nameEl = tc.querySelector(".toolcall-name");
    const name = nameEl ? nameEl.textContent.trim() : "";

    if (title.includes("present_files") || name === "present_files") {
      const body = tc.querySelector(".toolcall-body");
      if (!body) {
        const toggle = tc.querySelector(".toolcall-toggle, .chead");
        if (toggle) {
          try {
            toggle.click();
          } catch {}
        }
      }
    }
  });
}

function openImageLightbox(src) {
  if (typeof document === "undefined") return;
  const existing = document.getElementById("dimeogpt-lightbox-overlay");
  if (existing) existing.remove();

  const overlay = document.createElement("div");
  overlay.id = "dimeogpt-lightbox-overlay";
  Object.assign(overlay.style, {
    position: "fixed",
    inset: "0",
    backgroundColor: "rgba(0, 0, 0, 0.88)",
    backdropFilter: "blur(8px)",
    zIndex: "999999",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "24px",
    cursor: "zoom-out"
  });

  const img = document.createElement("img");
  img.src = src;
  Object.assign(img.style, {
    maxWidth: "94vw",
    maxHeight: "94vh",
    objectFit: "contain",
    borderRadius: "10px",
    boxShadow: "0 8px 32px rgba(0, 0, 0, 0.8)",
    border: "1px solid rgba(0, 255, 136, 0.4)"
  });

  overlay.appendChild(img);
  overlay.addEventListener("click", () => overlay.remove());
  document.body.appendChild(overlay);
}

function enforceDimeogptExperience() {
  enforceInlineMediaRendering();
  try {
    if (typeof document !== "undefined") {
      document.title = "DIMEOGPT — Cyber Security Cockpit";

      // 1. Enforce theme
      if (localStorage.getItem("pi-web-ui:theme") !== "chatgpt-custom") {
        localStorage.setItem("pi-web-ui:theme", "chatgpt-custom");
      }
      let link = document.getElementById("theme-stylesheet");
      if (!link) {
        link = document.createElement("link");
        link.id = "theme-stylesheet";
        link.rel = "stylesheet";
        document.head.appendChild(link);
      }
      if (!link.href.endsWith("/themes/chatgpt-custom.css") && !link.href.includes("chatgpt-custom")) {
        link.href = "/themes/chatgpt-custom.css";
      }
      document.documentElement.dataset.theme = "chatgpt-custom";
      window.dispatchEvent(new CustomEvent("pi-web-ui:theme-change"));

      // 2. Rebrand logo and update icon image
      const logoImgs = document.querySelectorAll(
        "img.brand-logo, img.bar-item-brand-logo, .brand img, [data-bar-item='host:brand'] img, [data-bar-item='brand'] img"
      );
      logoImgs.forEach((img) => {
        if (img.src !== DIMEOGPT_LOGO_DATA_URL) {
          img.src = DIMEOGPT_LOGO_DATA_URL;
          img.alt = "DIMEOGPT";
        }
        img.onerror = () => {
          img.src = DIMEOGPT_LOGO_URL;
        };
        img.style.setProperty("background", "transparent", "important");
        img.style.setProperty("background-image", "none", "important");
        img.style.setProperty("box-shadow", "none", "important");
        img.style.setProperty("border", "none", "important");
        img.style.setProperty("outline", "none", "important");
        img.style.setProperty("object-fit", "contain", "important");
      });

      // 3. Update Favicon & Safari Tab Icon (Uses real HTTP URL with cache-buster)
      const tabLogoUrl = "/plugins/dimeogpt-hub/client/dimeogpt_logo.png?v=dimeogpt_v3";
      const iconRels = ["icon", "shortcut icon", "apple-touch-icon", "apple-touch-icon-precomposed"];

      iconRels.forEach((rel) => {
        let link = document.querySelector(`link[rel='${rel}']`);
        if (!link) {
          link = document.createElement("link");
          link.rel = rel;
          document.head.appendChild(link);
        }
        if (link.href !== tabLogoUrl && !link.href.includes("dimeogpt_v3")) {
          link.type = "image/png";
          link.href = tabLogoUrl;
        }
      });

      // 3b. Enforce Safari Top Bar / Tab Bar Theme Color
      const safariThemeColor = "#103826";
      let metaTheme = document.querySelector("meta[name='theme-color']");
      if (!metaTheme) {
        metaTheme = document.createElement("meta");
        metaTheme.setAttribute("name", "theme-color");
        document.head.appendChild(metaTheme);
      }
      if (metaTheme.getAttribute("content") !== safariThemeColor) {
        metaTheme.setAttribute("content", safariThemeColor);
      }

      // Update Document Title if still showing default pi-web-ui
      if (document.title && document.title.includes("pi-web-ui")) {
        document.title = "DIMEOGPT — Cyber Security Cockpit";
      }

      // 4. Rebrand top-left header text
      const brandingNodes = document.querySelectorAll("header, nav, .topbar, div");
      brandingNodes.forEach((container) => {
        const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
        let node;
        while ((node = walker.nextNode())) {
          if (node.nodeValue && node.nodeValue.includes("pi-web-ui") && !node.parentElement?.closest("pre, code, .msg")) {
            node.nodeValue = node.nodeValue.replace(/pi-web-ui/g, "DIMEOGPT");
          }
        }
      });

      // 5. Welcome Hero on new/empty chats
      enforceDimeogptWelcomeScreen();

      // 6. Make DIMEOGPT brand clickable -> trigger new chat
      bindBrandNewChatAction();

      // 7. Enforce Two-Section Topbar (Fixed Left DIMEOGPT + New Chat, Collapsible Tools Menu)
      enforceDimeogptTopbar();

      // 8. Enforce Right Panel Hidden / Collapsed by default to maximize central chat space
      enforceRightPanelCollapsed();

      // 9. Sync Research Mode Dropdown with saved state
      syncResearchModeSelect();

      // 10. Enforce clean badges for research modes in chat bubbles
      enforceResearchBadgesInChat();

      // 11. Enforce Cyber Kraken Easter Egg on banners
      initCyberKrakenListener();

      // 12. Enforce DIMEOGPT Clean Mode & Deforming 'D' Thinking Loader
      enforceDimeogptCleanMode();

      // 13. Enforce DIMEOGPT Bottom Token & Cost Widget
      enforceDimeogptCostWidget();
    }
  } catch (err) {
    console.warn("[DIMEOGPT] Theme/branding auto-apply:", err);
  }
}

let isNewChatTriggering = false;

/**
 * Safely removes session hash without triggering a "Session not found" query.
 */
function cleanHashSafely() {
  try {
    if (typeof window !== "undefined" && window.location.hash) {
      window.history.replaceState(null, document.title, window.location.pathname + window.location.search);
    }
  } catch {}
}

/**
 * Triggers a new chat in pi-web-ui dynamically and safely without touching core packages.
 */
async function triggerNewChat() {
  if (isNewChatTriggering) return;
  isNewChatTriggering = true;
  setTimeout(() => {
    isNewChatTriggering = false;
  }, 800);

  try {
    // 0. Ensure view is switched to chat if currently on another tab
    try {
      const host = hostApi();
      host?.setView?.("chat");
      const chatTab = document.querySelector("[data-bar-item='host:chat'], .tab-chat, button.chat");
      if (chatTab && !chatTab.classList.contains("active")) {
        chatTab.click();
      }
    } catch {}

    // 1. Try native host:new-chat action buttons in DOM (topbar or left panel)
    const newChatBtn = document.querySelector(
      "button[data-bar-item='host:new-chat'], button.lp-new-chat-action, button.chip.newchat, [data-tip*='newChat'], [data-tip*='New chat'], [data-tip*='新对话'], [aria-label*='newChat'], [aria-label*='New chat']"
    );
    if (newChatBtn) {
      newChatBtn.click();
      cleanHashSafely();
      return;
    }

    // 2. Try React Fiber traversal to dispatch { type: "new_chat" } directly
    const brandEl = document.querySelector("[data-bar-item='host:brand'], .bar-item-brand, .brand");
    const rootEl = document.getElementById("root");
    const candidateNodes = [brandEl, rootEl?.firstElementChild, rootEl].filter(Boolean);

    for (const el of candidateNodes) {
      const fiberKey = Object.keys(el).find(
        (k) => k.startsWith("__reactFiber$") || k.startsWith("__reactInternalInstance$")
      );
      if (!fiberKey) continue;
      let curr = el[fiberKey];
      let depth = 0;
      while (curr && depth < 80) {
        const props = curr.memoizedProps || curr.props;
        if (props) {
          if (typeof props.chat?.send === "function") {
            if (typeof props.onViewChange === "function") props.onViewChange("chat");
            props.chat.send({ type: "new_chat" });
            cleanHashSafely();
            return;
          }
          if (typeof props.send === "function") {
            props.send({ type: "new_chat" });
            cleanHashSafely();
            return;
          }
        }
        curr = curr.return;
        depth++;
      }
    }

    // 3. Dynamic import of pi-web-ui client module (exports $ as r)
    const scriptTag = document.querySelector('script[src*="/assets/index-"]');
    if (scriptTag?.src) {
      try {
        const mod = await import(scriptTag.src);
        if (typeof mod?.r === "function") {
          mod.r({ type: "new_chat" });
          cleanHashSafely();
          return;
        }
      } catch (err) {
        console.warn("[DIMEOGPT] Module import dispatch fallback failed:", err);
      }
    }

    // 4. Native double-click on left panel sessions container (triggers native new_chat)
    const sessionsScroll = document.querySelector(".sessions-scroll, .lp-section-body");
    if (sessionsScroll) {
      sessionsScroll.dispatchEvent(new MouseEvent("dblclick", { bubbles: true, cancelable: true }));
      cleanHashSafely();
      return;
    }

    // 5. Host API openSession with existing cwd
    try {
      const host = hostApi();
      if (host?.openSession && typeof host.openSession === "function") {
        let cwd = "";
        try {
          const sessions = host.sessions?.list?.() || [];
          cwd = sessions[0]?.cwd || "";
        } catch {}
        if (cwd) {
          await host.openSession({ cwd, newChat: true });
          host.setView?.("chat");
          cleanHashSafely();
          return;
        }
      }
    } catch {}

    // 6. Safe URL cleanup fallback (NEVER assign synthetic session IDs)
    cleanHashSafely();
  } catch (err) {
    console.error("[DIMEOGPT] Trigger new chat error:", err);
  }
}

/**
 * Binds click handler on DIMEOGPT brand logo and text.
 */
function bindBrandNewChatAction() {
  try {
    if (typeof document === "undefined") return;

    const brandTargets = document.querySelectorAll(
      "[data-bar-item='host:brand'], .bar-item-brand, .brand, img.brand-logo, .brand-name, .bar-item-brand-logo, .bar-item-text"
    );

    brandTargets.forEach((el) => {
      // Only bind on branding elements (avoid other bar items)
      if (!el.closest("[data-bar-item='host:brand'], .bar-item-brand, .brand")) return;

      // Never bind brand action on our own injected action buttons
      if (el.closest("#dimeogpt-topbar-actions")) return;

      el.style.cursor = "pointer";
      if (!el.title || el.title.includes("brand") || el.title.includes("pi-web-ui")) {
        el.title = "Nuova Chat (DIMEOGPT)";
      }

      if (!el.dataset.dimeogptClickBound) {
        el.dataset.dimeogptClickBound = "true";
        el.addEventListener("click", (e) => {
          if (e.target.closest("#dimeogpt-topbar-actions")) return;
          e.preventDefault();
          e.stopPropagation();
          triggerNewChat();
        });
      }
    });
  } catch (err) {
    console.warn("[DIMEOGPT] Bind brand action error:", err);
  }
}

let isTopbarMenuOpen = false;
try {
  if (typeof localStorage !== "undefined") {
    isTopbarMenuOpen = localStorage.getItem("dimeogpt:topbar-menu-open") === "true";
  }
} catch {}

/**
 * Toggles the collapsible secondary menu.
 */
export function toggleTopbarMenu(forceState) {
  if (typeof forceState === "boolean") {
    isTopbarMenuOpen = forceState;
  } else {
    isTopbarMenuOpen = !isTopbarMenuOpen;
  }
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("dimeogpt:topbar-menu-open", String(isTopbarMenuOpen));
    }
  } catch {}
  updateTopbarMenuState();
}

/**
 * Syncs menu state classes and button labels in the DOM.
 */
function updateTopbarMenuState() {
  if (typeof document === "undefined") return;
  const topbar = document.querySelector("header.topbar, .topbar");
  if (!topbar) return;

  if (isTopbarMenuOpen) {
    topbar.classList.add("dimeogpt-menu-open");
    topbar.classList.remove("dimeogpt-menu-closed");
  } else {
    topbar.classList.remove("dimeogpt-menu-open");
    topbar.classList.add("dimeogpt-menu-closed");
  }

  const toggleBtn = document.getElementById("dimeogpt-menu-toggle-btn");
  if (toggleBtn) {
    toggleBtn.setAttribute("aria-expanded", String(isTopbarMenuOpen));
    toggleBtn.classList.toggle("active", isTopbarMenuOpen);
    const label = toggleBtn.querySelector(".dimeogpt-toggle-label");
    if (label) label.textContent = isTopbarMenuOpen ? "Chiudi" : "Menu";
    const chevron = toggleBtn.querySelector(".dimeogpt-toggle-chevron");
    if (chevron) {
      chevron.style.transform = isTopbarMenuOpen ? "rotate(180deg)" : "rotate(0deg)";
    }
  }
}

/**
 * Enforces the Two-Section Topbar:
 * Section 1 (Left, Fixed): DIMEOGPT brand + New Chat + Menu toggle
 * Section 2 (Collapsible): Merges seamlessly beside Section 1 when opened
 */
function enforceDimeogptTopbar() {
  try {
    if (typeof document === "undefined") return;

    const brandEl = document.querySelector(
      "[data-bar-item='host:brand'], .bar-item.brand, .bar-item-brand"
    );
    if (!brandEl) return;

    brandEl.classList.add("dimeogpt-left-section");

    let actionsWrap = brandEl.querySelector("#dimeogpt-topbar-actions");
    if (!actionsWrap) {
      actionsWrap = document.createElement("div");
      actionsWrap.id = "dimeogpt-topbar-actions";
      actionsWrap.className = "dimeogpt-topbar-actions";
      actionsWrap.innerHTML = `
        <span class="dimeogpt-section-divider"></span>
        <button type="button" id="dimeogpt-new-chat-btn" class="dimeogpt-topbar-btn dimeogpt-newchat-btn" title="Avvia nuova chat">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          <span class="dimeogpt-btn-label">New Chat</span>
        </button>
        <button type="button" id="dimeogpt-menu-toggle-btn" class="dimeogpt-topbar-btn dimeogpt-toggle-btn" title="Espandi / Comprimi Menu Strumenti" aria-expanded="false">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="4" y1="6" x2="20" y2="6"></line>
            <line x1="4" y1="12" x2="20" y2="12"></line>
            <line x1="4" y1="18" x2="20" y2="18"></line>
          </svg>
          <span class="dimeogpt-toggle-label">Menu</span>
          <svg class="dimeogpt-toggle-chevron" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </button>
      `;

      brandEl.appendChild(actionsWrap);

      const newChatBtn = actionsWrap.querySelector("#dimeogpt-new-chat-btn");
      newChatBtn?.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        triggerNewChat();
      });

      const toggleBtn = actionsWrap.querySelector("#dimeogpt-menu-toggle-btn");
      toggleBtn?.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleTopbarMenu();
      });
    }

    updateTopbarMenuState();
  } catch (err) {
    console.warn("[DIMEOGPT] Topbar enforce error:", err);
  }
}

// Global keyboard shortcut: Escape to collapse topbar menu if open
if (typeof window !== "undefined" && !globalThis.__dimeogptKeyHandler) {
  globalThis.__dimeogptKeyHandler = true;
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isTopbarMenuOpen) {
      toggleTopbarMenu(false);
    }
  });
}

/**
 * Enforces right sidebar (file/workspace panel) collapsed to maximize central window space.
 */
function enforceRightPanelCollapsed() {
  try {
    if (typeof localStorage !== "undefined") {
      // Ensure local storage is set to collapsed (1) unless user manually toggled it
      if (!sessionStorage.getItem("dimeogpt:user-toggled-right-panel")) {
        if (localStorage.getItem("pi-web-ui:right-panel-collapsed") !== "1") {
          localStorage.setItem("pi-web-ui:right-panel-collapsed", "1");
        }
      }
    }

    if (typeof document !== "undefined") {
      // If right panel is mounted as open in-flow, trigger its collapse button once
      if (!sessionStorage.getItem("dimeogpt:user-toggled-right-panel")) {
        const rightPanel = document.querySelector(".panel.panel-right, .drawer-right:not(.hidden)");
        if (rightPanel && !rightPanel.closest(".drawer-right.hidden")) {
          const collapseBtn = rightPanel.querySelector("button.panel-collapse-btn");
          if (collapseBtn) {
            collapseBtn.click();
          }
        }
      }

      // Track if user manually clicks to open/close right panel rail
      const rightRailBtn = document.querySelector("button.panel-rail-right, .panel-rail-right");
      if (rightRailBtn && !rightRailBtn.dataset.dimeogptBound) {
        rightRailBtn.dataset.dimeogptBound = "true";
        rightRailBtn.addEventListener("click", () => {
          try {
            sessionStorage.setItem("dimeogpt:user-toggled-right-panel", "true");
          } catch {}
        });
      }
    }
  } catch (err) {
    console.warn("[DIMEOGPT] Right panel enforce error:", err);
  }
}

// Auto-inject DIMEOGPT Welcome Hero Screen on blank / new chats
function enforceDimeogptWelcomeScreen() {
  try {
    if (typeof document === "undefined") return;

    // Detect empty state container (rendered by pi-web-ui when messages.length === 0)
    const emptyState = document.querySelector(".empty-state");
    if (!emptyState) {
      // If user is inside an active conversation with messages, remove any welcome hero
      const existingHero = document.getElementById("dimeogpt-welcome-hero");
      if (existingHero) existingHero.remove();
      return;
    }

    // Check if the welcome hero is already injected inside emptyState
    let hero = emptyState.querySelector("#dimeogpt-welcome-hero");
    if (!hero) {
      hero = document.createElement("div");
      hero.id = "dimeogpt-welcome-hero";
      hero.className = "dimeogpt-welcome-hero";
      hero.innerHTML = `
        <div class="dimeogpt-welcome-banners">
          <div class="dimeogpt-banner-wrap banner-1">
            <img src="${DIMEOGPT_BANNER_1_URL}" alt="DIMEO GPT" class="dimeogpt-hero-banner" draggable="false" />
          </div>
          <div class="dimeogpt-banner-wrap banner-2">
            <img src="${DIMEOGPT_BANNER_2_URL}" alt="DIMEOGPT Academic Study Suite" class="dimeogpt-hero-banner sub-banner" draggable="false" />
          </div>
        </div>
        <div class="dimeogpt-hero-badge">
          <span class="badge-dot"></span>
          <span class="badge-text">TOR VERGATA CYBER SECURITY COCKPIT</span>
          <span class="badge-tag">THE GOD'S EYE</span>
        </div>
      `;
      // Prepend before templates/cards so it appears prominently at the top
      emptyState.prepend(hero);
    } else {
      // Sync banner image sources to ensure latest high-res versions are displayed
      const img1 = hero.querySelector(".banner-1 img");
      if (img1 && !img1.src.includes("clean_no_crescents_v2")) {
        img1.src = DIMEOGPT_BANNER_1_URL;
      }
      const img2 = hero.querySelector(".banner-2 img");
      if (img2 && !img2.src.includes("clean_no_crescents_v2")) {
        img2.src = DIMEOGPT_BANNER_2_URL;
      }
    }

    // Ensure banners indicate interactive easter egg
    hero.querySelectorAll(".dimeogpt-hero-banner").forEach((img) => {
      img.style.cursor = "pointer";
      if (!img.title) {
        img.title = "Clicca per risvegliare il Cyber Kraken...";
      }
    });
  } catch (err) {
    console.warn("[DIMEOGPT] Welcome screen auto-apply:", err);
  }
}

// HTML entity escaping helper
function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Synchronize composer select element with persisted research mode
function syncResearchModeSelect() {
  try {
    if (typeof document === "undefined") return;
    const currentMode = localStorage.getItem("dimeogpt:research-mode") || "normal";

    const selects = document.querySelectorAll(".composer select, [data-slot='composer.actions'] select, select");
    selects.forEach((sel) => {
      const hasResearchOpts = Array.from(sel.options).some((opt) =>
        ["normal", "deep_research", "thesis_research"].includes(opt.value)
      );
      if (hasResearchOpts) {
        if (sel.value !== currentMode && Array.from(sel.options).some((o) => o.value === currentMode)) {
          sel.value = currentMode;
        }
        try {
          const reactPropsKey = Object.keys(sel).find((k) => k.startsWith("__reactProps$"));
          if (reactPropsKey && sel[reactPropsKey]) {
            sel[reactPropsKey].value = currentMode;
          }
        } catch {}
        if (!sel.dataset.dimeogptBound) {
          sel.dataset.dimeogptBound = "true";
          sel.addEventListener("change", (e) => {
            handleSelectResearchMode("research-mode-select", e.target.value);
          });
        }
      }
    });
  } catch (err) {
    console.warn("[DIMEOGPT] Sync select error:", err);
  }
}

// Regex to strip action button labels that might leak into textContent (Re-ask, Fork, Rollback, Copy)
const ACTION_LABEL_LEAK_REGEX = /(?:\s*(?:Re-ask|Edit\s*&\s*re-ask|Fork(?:\s*branch)?|Rollback(?:\s*to\s*here)?|Copy))+\s*$/i;

// Enforce clean badges for research modes in chat bubbles
function enforceResearchBadgesInChat() {
  try {
    if (typeof document === "undefined") return;
    const userMessages = document.querySelectorAll(".msg-user, [data-role='user']");
    userMessages.forEach((msgEl) => {
      // Fix already badged bubbles if they were contaminated by action labels
      if (msgEl.dataset.dimeogptBadged) {
        const promptEl = msgEl.querySelector(".dimeogpt-user-prompt-text");
        if (promptEl) {
          const raw = promptEl.textContent || "";
          const cleaned = raw.replace(ACTION_LABEL_LEAK_REGEX, "").trim();
          if (cleaned !== raw) {
            promptEl.textContent = cleaned;
          }
        }
        return;
      }

      // Clone element and strip buttons, actions and meta before reading textContent
      const clone = msgEl.cloneNode(true);
      clone.querySelectorAll("button, .msg-actions, .msg-action, .msg-action-label, .msg-meta, .msg-collapse-btn").forEach((el) => el.remove());
      const textContent = clone.textContent || "";

      if (textContent.includes("[MODALITÀ RICERCA:")) {
        let detectedMode = "normal";
        if (textContent.includes("thesis_research")) {
          detectedMode = "thesis_research";
        } else if (textContent.includes("deep_research")) {
          detectedMode = "deep_research";
        }

        const modeConfig = RESEARCH_MODES[detectedMode] || RESEARCH_MODES.normal;

        let userQuestion = "";
        const marker = "Richiesta dell'utente:\n";
        const idx = textContent.indexOf(marker);
        if (idx !== -1) {
          userQuestion = textContent.slice(idx + marker.length).trim();
        } else {
          userQuestion = textContent.replace(/\[MODALITÀ RICERCA:[\s\S]*?Richiesta dell'utente:/g, "").trim();
        }

        // Strip any residual leaked action labels
        userQuestion = userQuestion.replace(ACTION_LABEL_LEAK_REGEX, "").trim();

        if (!userQuestion) userQuestion = "(Richiesta utente)";

        msgEl.innerHTML = `
          <div class="dimeogpt-user-mode-pill mode-${detectedMode}">
            <span class="pill-dot"></span>
            <span class="pill-title">${modeConfig.badge}</span>
            <span class="pill-k">${modeConfig.k}</span>
          </div>
          <div class="dimeogpt-user-prompt-text">${escapeHtml(userQuestion)}</div>
        `;
        msgEl.dataset.dimeogptBadged = "true";
      }
    });
  } catch (err) {
    console.warn("[DIMEOGPT] Badge render error:", err);
  }
}

/**
 * Enforces DIMEOGPT Clean Mode:
 * CSS hides .thinking/.toolcall UNCONDITIONALLY (no body class needed).
 * The thinking capsule "DIMEOGPT sta pensando..." itself acts as the interactive toggle:
 * clicking it reveals or collapses the technical execution blocks (toolcalls & thinking).
 */
function enforceDimeogptCleanMode() {
  try {
    if (typeof document === "undefined") return;

    // 1. Synchronize mode: Clean (default) vs Debug
    const isClean = localStorage.getItem("dimeogpt:clean-mode") !== "false";
    if (isClean) {
      document.body.classList.remove("dimeogpt-debug-mode");
    } else {
      document.body.classList.add("dimeogpt-debug-mode");
    }

    // 2. Detect whether DIMEOGPT is currently generating / thinking / executing tools
    const hasStopButton = Boolean(document.querySelector("button.stop, button.stopping"));
    const hasActiveTool = Boolean(
      document.querySelector(".thinking.live, .thinking.run, .toolcall-waiting, .conv-streaming, .subagent-dot.streaming")
    );

    // Check if last message is from user with no assistant text response yet
    const allMsgs = Array.from(document.querySelectorAll(".msg"));
    let isAwaitingResponse = false;
    if (allMsgs.length > 0) {
      const lastMsg = allMsgs[allMsgs.length - 1];
      if (lastMsg && (lastMsg.classList.contains("msg-user") || lastMsg.getAttribute("data-role") === "user")) {
        isAwaitingResponse = true;
      }
      const lastAssistant = [...document.querySelectorAll(".msg-assistant, [data-role='assistant']")].pop();
      if (lastAssistant) {
        const hasText = lastAssistant.querySelector(".msg-text, .msg-text-main");
        const hasTools = lastAssistant.querySelector(".thinking, .toolcall");
        if (hasTools && !hasText) {
          isAwaitingResponse = true;
        }
      }
    }

    const isGenerating = hasStopButton || hasActiveTool || isAwaitingResponse;

    let capsule = document.getElementById("dimeogpt-thinking-capsule");

    if (isGenerating) {
      if (!capsule) {
        capsule = document.createElement("div");
        capsule.id = "dimeogpt-thinking-capsule";
        capsule.className = "dimeogpt-thinking-capsule";
        capsule.setAttribute("role", "button");
        capsule.setAttribute("tabindex", "0");
        capsule.innerHTML = `
          <div class="dimeogpt-d-container">
            <div class="dimeogpt-d-aura"></div>
            <div class="dimeogpt-d-morph">
              <span class="dimeogpt-d-letter">D</span>
            </div>
          </div>
          <div class="dimeogpt-thinking-text">
            <span class="brand-name">DIMEOGPT</span>
            <span>sta pensando</span>
            <span class="dot-1">.</span>
            <span class="dot-2">.</span>
            <span class="dot-3">.</span>
            <span class="dimeogpt-capsule-hint" id="dimeogpt-capsule-hint"></span>
          </div>
        `;

        // Click handler: The capsule itself toggles debug/clean mode
        capsule.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          const isCurrentlyDebug = document.body.classList.contains("dimeogpt-debug-mode");
          const nextClean = isCurrentlyDebug; // if currently debug, next is clean

          if (nextClean) {
            document.body.classList.remove("dimeogpt-debug-mode");
            localStorage.setItem("dimeogpt:clean-mode", "true");
            showNotification("✨ Modalità Pulita: passaggi tecnici nascosti", 2500);
          } else {
            document.body.classList.add("dimeogpt-debug-mode");
            localStorage.setItem("dimeogpt:clean-mode", "false");
            showNotification("🛠️ Passaggi tecnici e toolcall visibili", 2500);
          }
          updateCapsuleStatus();
        });

        capsule.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            capsule.click();
          }
        });
      }

      // Update capsule hint label & tooltip depending on current state
      const updateCapsuleStatus = () => {
        const isDebug = document.body.classList.contains("dimeogpt-debug-mode");
        const hintEl = capsule.querySelector("#dimeogpt-capsule-hint");
        if (hintEl) {
          hintEl.textContent = isDebug ? "dettagli visibili ▾" : "clicca per dettagli";
        }
        capsule.title = isDebug
          ? "Passaggi tecnici visibili. Clicca per nasconderli (Modalità Pulita)."
          : "Clicca per mostrare i passaggi tecnici intermedi (tool e thinking).";
      };

      updateCapsuleStatus();

      // Attach capsule inside the messages container, after the last user message
      const messagesWrap = document.querySelector(".messages-wrap, .messages, main");
      if (messagesWrap && !messagesWrap.contains(capsule)) {
        const userMsgs = messagesWrap.querySelectorAll(".msg-user, [data-role='user']");
        const anchor = userMsgs.length > 0 ? userMsgs[userMsgs.length - 1] : null;
        if (anchor && anchor.nextSibling !== capsule) {
          anchor.parentElement.insertBefore(capsule, anchor.nextSibling);
        } else if (!anchor) {
          messagesWrap.appendChild(capsule);
        }
      }
    } else {
      if (capsule) {
        capsule.remove();
      }
    }
  } catch (err) {
    console.warn("[DIMEOGPT] Clean mode enforcement error:", err);
  }
}

let lastTokenCostData = null;
let isFetchingTokens = false;
let lastTokensFetchTime = 0;

/**
 * Fetches token and cost data from DIMEOGPT plugin endpoint.
 */
async function fetchTokenCostData(force = false) {
  const now = Date.now();
  if (isFetchingTokens) return lastTokenCostData;
  if (!force && now - lastTokensFetchTime < 1800 && lastTokenCostData) {
    return lastTokenCostData;
  }
  isFetchingTokens = true;
  lastTokensFetchTime = now;
  try {
    const res = await fetch("/plugins-api/dimeogpt-hub/tokens");
    if (res.ok) {
      lastTokenCostData = await res.json();
      updateCostWidgetDom(lastTokenCostData);
      enforceStatusbarCostBadge();
    }
  } catch (err) {
    // Quiet fail
  } finally {
    isFetchingTokens = false;
  }
  return lastTokenCostData;
}

/**
 * Formats EUR currency value with high precision.
 */
function formatEur(cost) {
  const num = Number(cost ?? 0);
  if (num === 0) return "€ 0,0000";
  if (num < 0.0001) return "< € 0,0001";
  return `€ ${num.toFixed(4).replace(".", ",")}`;
}

/**
 * Formats USD currency value.
 */
function formatUsd(cost) {
  const num = Number(cost ?? 0);
  if (num === 0) return "$0.0000";
  if (num < 0.0001) return "< $0.0001";
  return `$${num.toFixed(4)}`;
}

/**
 * Updates the DIMEOGPT Token & Cost display cleanly inside the bottom statusbar.
 * Completely removes any floating overlay widget to prevent obstructing the composer or action buttons.
 */
function enforceDimeogptCostWidget() {
  if (typeof document === "undefined") return;

  // 1. Fetch latest data (throttled)
  fetchTokenCostData();

  // 2. Remove any floating widget immediately so it never creates an overlay
  const floatingWidget = document.getElementById("dimeogpt-cost-widget");
  if (floatingWidget) {
    floatingWidget.remove();
  }

  // 3. Inject or update the statusbar badge docked inside footer.statusbar
  enforceStatusbarCostBadge();
}

/**
 * Injects or updates the cost badge in the bottom statusbar.
 */
function enforceStatusbarCostBadge() {
  const statusbar = document.querySelector("footer.statusbar");
  if (!statusbar) return;

  const targetContainer = statusbar.querySelector(".statusbar-left") || statusbar;
  let pill = document.getElementById("dimeogpt-statusbar-cost");
  if (!pill) {
    pill = document.createElement("span");
    pill.id = "dimeogpt-statusbar-cost";
    pill.className = "bar-item status-item dimeogpt-statusbar-cost";
    pill.setAttribute("data-bar-item", "dimeogpt:cost");
    pill.style.cursor = "pointer";
    pill.onclick = () => {
      if (lastTokenCostData) {
        const last = lastTokenCostData.lastResponse || {};
        const turnInput = Number(last.tokens?.input ?? 0);
        const turnOutput = Number(last.tokens?.output ?? 0);
        const turnTotal = Number(last.tokens?.turnTokens ?? (turnInput + turnOutput));
        const turnCostEur = formatEur(last.costEUR);
        const turnCostUsd = formatUsd(last.costUSD);
        const cum = lastTokenCostData.cumulative || {};
        const cumTotal = Number(cum.tokens?.total ?? 0);
        const cumCostEur = formatEur(cum.costEUR);
        const cumCostUsd = formatUsd(cum.costUSD);
        const model = lastTokenCostData.model || "AI Model";

        const msg = [
          `📊 DIMEOGPT Consumo & Costi`,
          `• Modello: ${model}`,
          `• Risposta Attiva: ${turnTotal.toLocaleString("it-IT")} tok · ${turnCostEur} (${turnCostUsd})`,
          `  ↳ Prompt: ${turnInput.toLocaleString("it-IT")} | Risposta: ${turnOutput.toLocaleString("it-IT")}`,
          `• Totale Sessione: ${cumTotal.toLocaleString("it-IT")} tok · ${cumCostEur} (${cumCostUsd})`,
          `• Tasso: 1$ ≈ 0,92€`,
        ].join("\n");
        showNotification(msg, 6000);
      } else {
        fetchTokenCostData(true);
      }
    };
    // Insert right after host:ctx if available, or prepend/append
    const ctxItem = statusbar.querySelector("[data-bar-item='host:ctx']");
    if (ctxItem && ctxItem.nextSibling) {
      targetContainer.insertBefore(pill, ctxItem.nextSibling);
    } else {
      targetContainer.appendChild(pill);
    }
  }

  if (lastTokenCostData) {
    const last = lastTokenCostData.lastResponse || {};
    const turnInput = Number(last.tokens?.input ?? 0);
    const turnOutput = Number(last.tokens?.output ?? 0);
    const turnTotal = Number(last.tokens?.turnTokens ?? (turnInput + turnOutput));
    const turnCostEur = formatEur(last.costEUR);
    const newHtml = `<span class="dimeogpt-statusbar-icon">🪙</span> <span class="dimeogpt-statusbar-tok">${turnTotal.toLocaleString("it-IT")} tok</span> · <span class="dimeogpt-statusbar-eur">${turnCostEur}</span>`;
    if (pill.innerHTML !== newHtml) {
      pill.innerHTML = newHtml;
    }
    pill.title = `DIMEOGPT: ${turnTotal.toLocaleString("it-IT")} token turno · Costo risposta: ${turnCostEur} (Clicca per dettagli)`;
  } else {
    if (!pill.innerHTML.includes("Consumi €")) {
      pill.innerHTML = `<span class="dimeogpt-statusbar-icon">🪙</span> Consumi €`;
      pill.title = "Clicca per dettagli consumo token e costi in Euro";
    }
  }
}

// Intercept WebSocket send to inject research mode directive into user prompts
if (typeof window !== "undefined" && !globalThis.__dimeogptWsPatched) {
  globalThis.__dimeogptWsPatched = true;
  const originalWsSend = WebSocket.prototype.send;
  WebSocket.prototype.send = function (data) {
    try {
      if (typeof data === "string" && data.startsWith("{") && data.includes('"type":"prompt"')) {
        const parsed = JSON.parse(data);
        if (parsed.type === "prompt" && typeof parsed.text === "string" && parsed.text.trim()) {
          const rawText = parsed.text.trim();
          // Never intercept slash commands
          if (!rawText.startsWith("/")) {
            const currentMode = (typeof localStorage !== "undefined" ? localStorage.getItem("dimeogpt:research-mode") : null) || "normal";
            const modeConfig = RESEARCH_MODES[currentMode] || RESEARCH_MODES.normal;

            // Only inject if not already injected
            if (!rawText.includes("[MODALITÀ RICERCA:")) {
              parsed.text = `${modeConfig.directive}\n\nRichiesta dell'utente:\n${rawText}`;
              return originalWsSend.call(this, JSON.stringify(parsed));
            }
          }
        }
      }
    } catch (err) {
      console.warn("[DIMEOGPT] WebSocket prompt interception error:", err);
    }
    return originalWsSend.call(this, data);
  };
}

// Run immediately and periodically to handle dynamic SPA renders and route switches
if (typeof window !== "undefined") {
  enforceDimeogptExperience();
  window.addEventListener("hashchange", enforceDimeogptExperience);
  window.addEventListener("popstate", enforceDimeogptExperience);
  setInterval(enforceDimeogptExperience, 800);
}

// Register UI actions at module load time (ensures topbar/composer slots are bound immediately)
if (!globalThis.__dimeogptActionsRegistered) {
  globalThis.__dimeogptActionsRegistered = true;
  onUiAction("dimeogpt:select-model", (itemId, value) => handleSelectModel(itemId, value));
  onUiAction("dimeogpt:select-research-mode", (itemId, value) => handleSelectResearchMode(itemId, value));
  onUiAction("dimeogpt:export-transcript-md", () => handleExportMarkdown());
  onUiAction("dimeogpt:export-transcript-json", () => handleExportJson());
  onUiAction("dimeogpt:token-usage", () => handleTokenUsage());
}

// Export default view satisfying the host bundle loader (Ru)
export default defineView({
  mount(el, ctx) {
    el.innerHTML = `
      <div class="dimeogpt-panel" style="padding: 24px; font-family: system-ui, sans-serif; color: #f2fbf6; background: #070d0a; border-radius: 8px;">
        <h2 style="color: #00ff88; margin-top: 0; font-size: 1.25rem;">DIMEOGPT Cockpit Hub</h2>
        <p style="color: #a7f3d0; font-size: 0.875rem;">Tor Vergata Cyber Security Cockpit Plugin</p>
        <div style="margin-top: 16px; display: flex; gap: 10px; flex-wrap: wrap;">
          <button id="btn-export-md" style="background: #0d1813; color: #00ff88; border: 1px solid #00a859; padding: 8px 14px; border-radius: 6px; cursor: pointer;">Export MD</button>
          <button id="btn-export-json" style="background: #0d1813; color: #00ff88; border: 1px solid #00a859; padding: 8px 14px; border-radius: 6px; cursor: pointer;">Export JSON</button>
          <button id="btn-tokens" style="background: #0d1813; color: #00ff88; border: 1px solid #00a859; padding: 8px 14px; border-radius: 6px; cursor: pointer;">Token Usage</button>
        </div>
      </div>
    `;

    const btnMd = el.querySelector("#btn-export-md");
    const btnJson = el.querySelector("#btn-export-json");
    const btnTokens = el.querySelector("#btn-tokens");

    btnMd?.addEventListener("click", () => handleExportMarkdown());
    btnJson?.addEventListener("click", () => handleExportJson());
    btnTokens?.addEventListener("click", () => handleTokenUsage());

    return () => {
      el.innerHTML = "";
    };
  }
});
