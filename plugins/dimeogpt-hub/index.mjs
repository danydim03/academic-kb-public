/**
 * DIMEOGPT Hub Plugin - Server Entry Point
 * File: ~/.pi-web/plugins/dimeogpt-hub/index.mjs
 *
 * Capabilities:
 * - REST GET /plugins-api/dimeogpt-hub/export?format=markdown|json
 * - REST GET /plugins-api/dimeogpt-hub/tokens
 * - Safe lifecycle management via host.effect()
 * - Zero modification of core npm packages
 */

import { definePlugin } from "./sdk/index.mjs";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

/**
 * Extracts plain text or formatted representation from diverse message content blocks.
 * Supports string content, text blocks, thinking blocks, and tool calls.
 *
 * @param {string|Array<any>|any} content
 * @returns {string}
 */
function extractMessageContent(content) {
  if (typeof content === "string") {
    return content;
  }
  if (!Array.isArray(content)) {
    if (content && typeof content === "object") {
      return content.text || content.thinking || JSON.stringify(content);
    }
    return "";
  }
  return content
    .map((block) => {
      if (typeof block === "string") return block;
      if (!block || typeof block !== "object") return "";
      if (block.type === "text" && typeof block.text === "string") {
        return block.text;
      }
      if (block.type === "thinking" && typeof block.thinking === "string") {
        return `> **[Thinking]**\n> ${block.thinking.replace(/\n/g, "\n> ")}`;
      }
      if (block.type === "toolCall") {
        const args = block.argumentsText || (block.arguments ? JSON.stringify(block.arguments) : "");
        return `\`\`\`tool-call\n// Tool: ${block.name || "unknown"}\n${args}\n\`\`\``;
      }
      if (typeof block.text === "string") {
        return block.text;
      }
      return "";
    })
    .filter(Boolean)
    .join("\n\n");
}

/**
 * Formats conversation snapshot into GitHub Flavored Markdown transcript.
 *
 * @param {object|null} conv
 * @returns {string}
 */
function formatTranscriptMarkdown(conv) {
  if (!conv) {
    return "# DIMEOGPT Transcript\n\n*(No active conversation found)*\n";
  }

  const title = conv.title || "Untitled Conversation";
  const model = conv.model || "Unknown Model";
  const convId = conv.conversationId || "unknown";
  const timestamp = conv.at ? new Date(conv.at).toISOString() : new Date().toISOString();
  const messages = Array.isArray(conv.messages) ? conv.messages : [];

  const lines = [
    `# ${title}`,
    "",
    `- **Conversation ID**: \`${convId}\``,
    `- **Model**: \`${model}\``,
    `- **Exported At**: ${timestamp}`,
    `- **Total Messages**: ${messages.length}`,
  ];

  if (conv.stats) {
    const tokens = conv.stats.tokens || {};
    const total = Number(tokens.total ?? 0);
    const input = Number(tokens.input ?? 0);
    const output = Number(tokens.output ?? 0);
    const cost = Number(conv.stats.cost ?? 0.0);
    lines.push(`- **Token Usage**: ${total} total (${input} prompt + ${output} completion) | **Estimated Cost**: $${cost.toFixed(4)}`);
  }

  lines.push("", "---", "");

  if (messages.length === 0) {
    lines.push("*(No messages in transcript)*\n");
    return lines.join("\n");
  }

  for (const msg of messages) {
    const role = String(msg.role ?? "message").toLowerCase();
    let roleLabel = "Message";
    if (role === "user") roleLabel = "User";
    else if (role === "assistant") roleLabel = `Assistant (${msg.model || model})`;
    else if (role === "toolresult") roleLabel = "Tool Result";
    else if (role === "system") roleLabel = "System";
    else roleLabel = role.charAt(0).toUpperCase() + role.slice(1);

    const timeStr = msg.timestamp ? ` *[${new Date(msg.timestamp).toLocaleTimeString()}]*` : "";
    lines.push(`### ${roleLabel}${timeStr}`, "");

    const text = extractMessageContent(msg.content);
    lines.push(text || "*(empty message)*", "");
  }

  return lines.join("\n");
}

/**
 * Formats conversation snapshot into JSON payload.
 *
 * @param {object|null} conv
 * @returns {object}
 */
function formatTranscriptJson(conv) {
  if (!conv) {
    return {
      conversationId: null,
      title: "No active conversation",
      model: null,
      messages: [],
      stats: {
        tokens: { input: 0, output: 0, total: 0 },
        cost: 0.0,
      },
    };
  }

  const stats = conv.stats || {};
  const tokens = stats.tokens || {};

  return {
    conversationId: conv.conversationId ?? null,
    sessionId: conv.sessionId ?? null,
    title: conv.title ?? "Untitled Conversation",
    model: conv.model ?? null,
    at: conv.at ?? null,
    stats: {
      tokens: {
        input: Number(tokens.input ?? 0),
        output: Number(tokens.output ?? 0),
        total: Number(tokens.total ?? 0),
      },
      cost: Number(stats.cost ?? 0.0),
    },
    messages: (Array.isArray(conv.messages) ? conv.messages : []).map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      timestamp: m.timestamp,
      model: m.model,
      provider: m.provider,
      stopReason: m.stopReason,
    })),
  };
}

/**
 * Extracts turn-specific token usage and cost for the most recent assistant response.
 * Uses sessionFile if accessible, or scans recent session JSONL files, falling back to conv.stats.
 *
 * @param {object|null} conv
 * @returns {object}
 */
function extractLastTurnUsage(conv) {
  const EUR_RATE = 0.92;
  let sessionFile = conv?.sessionFile;

  if (!sessionFile || !fs.existsSync(sessionFile)) {
    try {
      const baseDir = path.join(os.homedir(), ".pi", "agent", "sessions");
      if (fs.existsSync(baseDir)) {
        const subdirs = fs.readdirSync(baseDir, { withFileTypes: true });
        let latestFile = null;
        let latestMtime = 0;
        for (const dirent of subdirs) {
          if (dirent.isDirectory()) {
            const dirPath = `${baseDir}/${dirent.name}`;
            const files = fs.readdirSync(dirPath);
            for (const file of files) {
              if (file.endsWith(".jsonl")) {
                const fullPath = `${dirPath}/${file}`;
                const stat = fs.statSync(fullPath);
                if (stat.mtimeMs > latestMtime) {
                  latestMtime = stat.mtimeMs;
                  latestFile = fullPath;
                }
              }
            }
          }
        }
        if (latestFile) sessionFile = latestFile;
      }
    } catch {}
  }

  if (sessionFile && fs.existsSync(sessionFile)) {
    try {
      const content = fs.readFileSync(sessionFile, "utf-8");
      const lines = content.trim().split("\n");
      for (let i = lines.length - 1; i >= 0; i--) {
        const line = lines[i].trim();
        if (!line) continue;
        const entry = JSON.parse(line);
        const msg = entry.message || entry;
        if (msg.role === "assistant" && msg.usage) {
          const u = msg.usage;
          const costUSD = Number(u.cost?.total ?? 0);
          const costEUR = costUSD * EUR_RATE;
          const inTok = Number(u.input ?? 0);
          const outTok = Number(u.output ?? 0);
          const cacheRead = Number(u.cacheRead ?? 0);
          const cacheWrite = Number(u.cacheWrite ?? 0);
          const reasoning = Number(u.reasoning ?? 0);
          const totalTok = Number(u.totalTokens ?? (inTok + outTok));
          const turnTokens = inTok + outTok;

          return {
            source: "sessionFile",
            model: msg.model || conv?.model || "AI Model",
            tokens: {
              input: inTok,
              output: outTok,
              cacheRead,
              cacheWrite,
              reasoning,
              turnTokens,
              total: totalTok,
            },
            costUSD,
            costEUR,
            timestamp: msg.timestamp || entry.timestamp || Date.now(),
          };
        }
      }
    } catch (err) {
      // Fallback below
    }
  }

  // Fallback to conversation stats
  const stats = conv?.stats;
  const costUSD = Number(stats?.cost ?? 0.0);
  const inTok = Number(stats?.tokens?.input ?? 0);
  const outTok = Number(stats?.tokens?.output ?? 0);
  const totalTok = Number(stats?.tokens?.total ?? (inTok + outTok));

  return {
    source: "convStats",
    model: conv?.model || "AI Model",
    tokens: {
      input: inTok,
      output: outTok,
      cacheRead: Number(stats?.tokens?.cacheRead ?? 0),
      cacheWrite: Number(stats?.tokens?.cacheWrite ?? 0),
      reasoning: 0,
      turnTokens: inTok + outTok,
      total: totalTok,
    },
    costUSD,
    costEUR: costUSD * EUR_RATE,
    timestamp: Date.now(),
  };
}

export default definePlugin({
  async activate(host) {
    host.log("info", "DIMEOGPT Hub plugin activating...");

    // Mount GET /plugins-api/dimeogpt-hub/export
    host.route("GET", "/export", (req, res) => {
      try {
        const rawFormat = (req.query?.format ?? "").toString().trim().toLowerCase();
        let format = rawFormat;
        if (format === "md") format = "markdown";

        if (format !== "markdown" && format !== "json") {
          res.setHeader("Content-Type", "application/json; charset=utf-8");
          res.status(400).json({
            error: `Invalid or missing format parameter: '${rawFormat}'. Supported formats: markdown, json`,
          });
          return;
        }

        const conv = host.getActiveConversation?.() ?? null;

        if (format === "markdown") {
          const markdown = formatTranscriptMarkdown(conv);
          res.setHeader("Content-Type", "text/markdown; charset=utf-8");
          res.status(200).send(markdown);
        } else {
          const jsonPayload = formatTranscriptJson(conv);
          res.setHeader("Content-Type", "application/json; charset=utf-8");
          res.status(200).json(jsonPayload);
        }
      } catch (err) {
        host.log("error", `Failed handling /export request: ${err.message}`);
        if (!res.headersSent) {
          res.setHeader("Content-Type", "application/json; charset=utf-8");
          res.status(500).json({ error: "Internal server error exporting transcript" });
        }
      }
    });

    // Mount GET /plugins-api/dimeogpt-hub/tokens
    host.route("GET", "/tokens", (req, res) => {
      try {
        const conv = host.getActiveConversation?.() ?? null;
        const stats = conv?.stats;
        const EUR_RATE = 0.92;

        const sessionTokens = {
          input: Number(stats?.tokens?.input ?? 0),
          output: Number(stats?.tokens?.output ?? 0),
          cacheRead: Number(stats?.tokens?.cacheRead ?? 0),
          cacheWrite: Number(stats?.tokens?.cacheWrite ?? 0),
          total: Number(stats?.tokens?.total ?? 0),
        };
        const sessionCostUSD = Number(stats?.cost ?? 0.0);
        const sessionCostEUR = sessionCostUSD * EUR_RATE;

        const lastTurn = extractLastTurnUsage(conv);

        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.status(200).json({
          model: lastTurn.model || conv?.model || "default",
          eurRate: EUR_RATE,
          lastResponse: {
            model: lastTurn.model,
            tokens: lastTurn.tokens,
            costUSD: lastTurn.costUSD,
            costEUR: lastTurn.costEUR,
            timestamp: lastTurn.timestamp,
          },
          cumulative: {
            tokens: sessionTokens,
            costUSD: sessionCostUSD,
            costEUR: sessionCostEUR,
          },
          // Direct backward-compatibility fields:
          tokens: lastTurn.tokens,
          cost: lastTurn.costUSD,
          costEUR: lastTurn.costEUR,
        });
      } catch (err) {
        host.log("error", `Failed handling /tokens request: ${err.message}`);
        if (!res.headersSent) {
          res.setHeader("Content-Type", "application/json; charset=utf-8");
          res.status(200).json({
            model: "default",
            eurRate: 0.92,
            lastResponse: {
              model: "default",
              tokens: { input: 0, output: 0, total: 0, turnTokens: 0, cacheRead: 0, cacheWrite: 0, reasoning: 0 },
              costUSD: 0.0,
              costEUR: 0.0,
              timestamp: Date.now(),
            },
            cumulative: {
              tokens: { input: 0, output: 0, total: 0, cacheRead: 0, cacheWrite: 0 },
              costUSD: 0.0,
              costEUR: 0.0,
            },
            tokens: { input: 0, output: 0, total: 0 },
            cost: 0.0,
            costEUR: 0.0,
          });
        }
      }
    });

    // Mount GET /plugins-api/dimeogpt-hub/logo
    host.route("GET", "/logo", (req, res) => {
      try {
        const pluginDir = path.dirname(new URL(import.meta.url).pathname);
        const localLogo = path.join(pluginDir, "client", "dimeogpt_logo.png");
        const themeLogo = path.join(os.homedir(), ".pi-web", "themes", "dimeogpt_logo.png");
        const logoPath = fs.existsSync(localLogo) ? localLogo : themeLogo;
        if (fs.existsSync(logoPath)) {
          const buffer = fs.readFileSync(logoPath);
          res.setHeader("Content-Type", "image/png");
          res.setHeader("Cache-Control", "public, max-age=86400");
          res.status(200).send(buffer);
        } else {
          res.status(404).send("Logo not found");
        }
      } catch (err) {
        res.status(500).send("Error serving logo");
      }
    });

    // Mount GET /plugins-api/dimeogpt-hub/welcome-banner-1
    host.route("GET", "/welcome-banner-1", (req, res) => {
      try {
        const pluginDir = path.dirname(new URL(import.meta.url).pathname);
        const localBanner = path.join(pluginDir, "client", "welcome_banner_1.png");
        const themeBanner = path.join(os.homedir(), ".pi-web", "themes", "welcome_banner_1.png");
        const p = fs.existsSync(localBanner) ? localBanner : themeBanner;
        if (fs.existsSync(p)) {
          res.setHeader("Content-Type", "image/png");
          res.setHeader("Cache-Control", "public, max-age=86400");
          res.status(200).send(fs.readFileSync(p));
        } else {
          res.status(404).send("Banner not found");
        }
      } catch (err) {
        res.status(500).send("Error serving banner");
      }
    });

    // Mount GET /plugins-api/dimeogpt-hub/welcome-banner-2
    host.route("GET", "/welcome-banner-2", (req, res) => {
      try {
        const pluginDir = path.dirname(new URL(import.meta.url).pathname);
        const localBanner = path.join(pluginDir, "client", "welcome_banner_2.png");
        const themeBanner = path.join(os.homedir(), ".pi-web", "themes", "welcome_banner_2.png");
        const p = fs.existsSync(localBanner) ? localBanner : themeBanner;
        if (fs.existsSync(p)) {
          res.setHeader("Content-Type", "image/png");
          res.setHeader("Cache-Control", "public, max-age=86400");
          res.status(200).send(fs.readFileSync(p));
        } else {
          res.status(404).send("Banner not found");
        }
      } catch (err) {
        res.status(500).send("Error serving banner");
      }
    });

    // Register lifecycle unwinding effect via host.effect()
    host.effect("dimeogpt-hub:lifecycle", () => {
      host.log("info", "DIMEOGPT Hub lifecycle unwinding completed.");
    });

    host.log("info", "DIMEOGPT Hub plugin successfully activated.");
  },

  async deactivate() {
    // Explicit clean shutdown hook
  },
});
