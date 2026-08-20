/**
 * SciCalc – script.js
 *
 * Responsibilities:
 *  - Build / maintain the expression string
 *  - Send expression to the FastAPI backend via fetch()
 *  - Display results and handle errors
 *  - Manage calculation history (load, render, delete)
 *  - Theme (dark / light) persistence via localStorage
 *  - Keyboard input
 *  - DEG / RAD mode toggle
 *  - Copy result to clipboard
 */

"use strict";

// ═══════════════════════════════════════════════════════════════════════════
// 1. CONFIG
// ═══════════════════════════════════════════════════════════════════════════

// ── API base URL ──────────────────────────────────────────────────────────
// Automatically uses localhost when running locally,
// and your Render backend URL when deployed on Vercel/Netlify.
// TO DEPLOY: replace the render URL below with your actual Render service URL.
const RENDER_API = "https://scicalc-api.onrender.com/api";
const LOCAL_API  = "http://127.0.0.1:8001/api";
const API_BASE   = (location.hostname === "localhost" || location.hostname === "127.0.0.1")
  ? LOCAL_API
  : RENDER_API;

// ═══════════════════════════════════════════════════════════════════════════
// 2. STATE
// ═══════════════════════════════════════════════════════════════════════════

const state = {
  expression: "",     // raw expression string shown to the user
  result: "0",        // last computed result (string)
  mode: "DEG",        // "DEG" or "RAD"
  historyOpen: false, // whether the history panel is visible
  calculating: false, // prevent double-submit
  justCalculated: false, // true after = or voice → next input starts fresh
};

// ═══════════════════════════════════════════════════════════════════════════
// 3. DOM REFERENCES
// ═══════════════════════════════════════════════════════════════════════════

const dom = {
  expressionDisplay: document.getElementById("expression-display"),
  resultDisplay:     document.getElementById("result-display"),
  statusMsg:         document.getElementById("status-msg"),
  modeBadge:         document.getElementById("mode-badge"),
  btnDeg:            document.getElementById("btn-deg"),
  btnRad:            document.getElementById("btn-rad"),
  btnAc:             document.getElementById("btn-ac"),
  btnDel:            document.getElementById("btn-del"),
  btnEquals:         document.getElementById("btn-equals"),
  btnCopy:           document.getElementById("btn-copy"),
  btnTheme:          document.getElementById("btn-theme"),
  btnHistoryToggle:  document.getElementById("btn-history-toggle"),
  btnHistoryClose:   document.getElementById("btn-history-close"),
  btnClearHistory:   document.getElementById("btn-clear-history"),
  historyPanel:      document.getElementById("history-panel"),
  historyOverlay:    document.getElementById("history-overlay"),
  historyList:       document.getElementById("history-list"),
  toast:             document.getElementById("toast"),
  htmlRoot:          document.documentElement,
};

// ═══════════════════════════════════════════════════════════════════════════
// 4. THEME
// ═══════════════════════════════════════════════════════════════════════════

function initTheme() {
  const saved = localStorage.getItem("scicalc-theme") || "dark";
  dom.htmlRoot.setAttribute("data-theme", saved);
}

function toggleTheme() {
  const current = dom.htmlRoot.getAttribute("data-theme");
  const next = current === "dark" ? "light" : "dark";
  dom.htmlRoot.setAttribute("data-theme", next);
  localStorage.setItem("scicalc-theme", next);
}

// ═══════════════════════════════════════════════════════════════════════════
// 5. DISPLAY HELPERS
// ═══════════════════════════════════════════════════════════════════════════

function renderExpression() {
  dom.expressionDisplay.textContent = state.expression || "";
}

function renderResult(value) {
  dom.resultDisplay.textContent = value;
  // Trigger pop animation
  dom.resultDisplay.classList.remove("pop");
  // Force reflow so the animation re-triggers
  void dom.resultDisplay.offsetWidth;
  dom.resultDisplay.classList.add("pop");
}

function setStatus(msg, type = "") {
  dom.statusMsg.textContent = msg;
  dom.statusMsg.className = "status-msg" + (type ? ` ${type}` : "");
}

function clearStatus() {
  dom.statusMsg.textContent = "";
  dom.statusMsg.className = "status-msg";
}

// ═══════════════════════════════════════════════════════════════════════════
// 6. EXPRESSION BUILDING
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Insert a value at the end of the current expression.
 * Smart spacing: add a space before/after function names for readability
 * but not for operators or numbers.
 */
function insertValue(value) {
  // After a completed calculation (= or voice), next input starts fresh —
  // UNLESS the user presses an operator (then they want to continue with result)
  if (state.justCalculated) {
    const isOperator = ["+", "-", "×", "÷", "%", "**", "^"].includes(value);
    if (isOperator) {
      // Continue: use the last result as the left operand
      state.expression = state.result + value;
    } else if (value === "+/-") {
      // Negate the result
      state.expression = state.result.startsWith("-")
        ? state.result.slice(1)
        : "-" + state.result;
    } else {
      // Number, function, paren → start completely fresh
      state.expression = value;
    }
    state.justCalculated = false;
    clearStatus();
    renderExpression();
    return;
  }

  if (value === "+/-") {
    if (state.expression === "") return;
    if (state.expression.startsWith("-")) {
      state.expression = state.expression.slice(1);
    } else {
      state.expression = "-" + state.expression;
    }
  } else {
    state.expression += value;
  }
  clearStatus();
  renderExpression();
}

function clearAll() {
  state.expression = "";
  state.result = "0";
  state.justCalculated = false;
  renderExpression();
  renderResult("0");
  clearStatus();
}

function deleteLast() {
  // If just calculated, DEL clears the result and starts fresh
  if (state.justCalculated) {
    state.expression = "";
    state.justCalculated = false;
    renderExpression();
    clearStatus();
    return;
  }
  // If the expression ends with a multi-char function token, remove the whole token
  const funcMatch = state.expression.match(/[a-z]+\($/i);
  if (funcMatch) {
    state.expression = state.expression.slice(0, -funcMatch[0].length);
  } else {
    state.expression = state.expression.slice(0, -1);
  }
  renderExpression();
  clearStatus();
}

// ═══════════════════════════════════════════════════════════════════════════
// 7. MODE TOGGLE
// ═══════════════════════════════════════════════════════════════════════════

function setMode(mode) {
  state.mode = mode;
  dom.modeBadge.textContent = mode;
  dom.btnDeg.classList.toggle("active", mode === "DEG");
  dom.btnRad.classList.toggle("active", mode === "RAD");
  dom.btnDeg.setAttribute("aria-pressed", String(mode === "DEG"));
  dom.btnRad.setAttribute("aria-pressed", String(mode === "RAD"));
}

// ═══════════════════════════════════════════════════════════════════════════
// 8. API CALLS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * POST /api/calculate
 */
async function apiCalculate(expression, mode) {
  const response = await fetch(`${API_BASE}/calculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expression, mode }),
  });

  if (!response.ok) {
    // Try to parse a FastAPI error detail
    let detail = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch (_) { /* ignore */ }
    throw new Error(detail);
  }

  return response.json(); // { expression, result, mode }
}

/**
 * GET /api/history
 */
async function apiFetchHistory() {
  const response = await fetch(`${API_BASE}/history?limit=100`);
  if (!response.ok) throw new Error("Failed to load history");
  return response.json(); // { calculations: [...], total }
}

/**
 * DELETE /api/history/{id}
 */
async function apiDeleteHistoryItem(id) {
  const response = await fetch(`${API_BASE}/history/${id}`, { method: "DELETE" });
  if (!response.ok) throw new Error("Failed to delete item");
  return response.json();
}

/**
 * DELETE /api/history
 */
async function apiClearHistory() {
  const response = await fetch(`${API_BASE}/history`, { method: "DELETE" });
  if (!response.ok) throw new Error("Failed to clear history");
  return response.json();
}

// ═══════════════════════════════════════════════════════════════════════════
// 9. CALCULATE
// ═══════════════════════════════════════════════════════════════════════════

async function calculate() {
  if (state.calculating) return;
  const expr = state.expression.trim();

  if (!expr) {
    setStatus("Enter an expression first", "error");
    return;
  }

  state.calculating = true;
  setStatus("Calculating…");

  try {
    const data = await apiCalculate(expr, state.mode);

    // Format the result nicely
    const formatted = formatResult(data.result);
    state.result = formatted;
    renderResult(formatted);
    setStatus("", "success");
    state.justCalculated = true; // next input starts fresh

    // Reload history if panel is open
    if (state.historyOpen) {
      loadHistory();
    }
  } catch (err) {
    const msg = err.message || "Calculation error";
    setStatus(msg, "error");
    renderResult("Error");
  } finally {
    state.calculating = false;
  }
}

/**
 * Format a number for display — trim unnecessary trailing zeros,
 * use exponential notation for very large / small numbers.
 */
function formatResult(num) {
  if (Number.isInteger(num) && Math.abs(num) < 1e15) {
    return String(num);
  }
  // Avoid excessive decimal places
  const str = parseFloat(num.toPrecision(12)).toString();
  return str;
}

// ═══════════════════════════════════════════════════════════════════════════
// 10. HISTORY
// ═══════════════════════════════════════════════════════════════════════════

async function loadHistory() {
  dom.historyList.innerHTML = '<p class="history-empty">Loading…</p>';

  try {
    const data = await apiFetchHistory();
    renderHistory(data.calculations);
  } catch (err) {
    dom.historyList.innerHTML =
      '<p class="history-empty" style="color:var(--c-danger)">Could not load history.<br>Is the backend running?</p>';
  }
}

function renderHistory(calculations) {
  if (!calculations || calculations.length === 0) {
    dom.historyList.innerHTML = '<p class="history-empty">No calculations yet.</p>';
    return;
  }

  dom.historyList.innerHTML = "";
  calculations.forEach((calc) => {
    const item = buildHistoryItem(calc);
    dom.historyList.appendChild(item);
  });
}

function buildHistoryItem(calc) {
  const article = document.createElement("article");
  article.className = "history-item";
  article.setAttribute("role", "listitem");
  article.setAttribute("tabindex", "0");
  article.setAttribute("aria-label", `${calc.expression} equals ${calc.result}`);

  const timeStr = formatDateTime(calc.created_at);
  const resultFormatted = formatResult(calc.result);

  article.innerHTML = `
    <div class="history-item-top">
      <span class="history-expr">${escapeHtml(calc.expression)}</span>
      <button
        class="history-delete-btn"
        data-id="${escapeHtml(calc._id || calc.id)}"
        title="Delete this calculation"
        aria-label="Delete calculation ${escapeHtml(calc.expression)}"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6"  y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
    <div class="history-result">${escapeHtml(resultFormatted)}</div>
    <div class="history-meta">
      <span class="history-mode">${escapeHtml(calc.mode)}</span>
      <span class="history-time">${timeStr}</span>
    </div>
  `;

  // Click on item body (not delete button) → load into calculator
  article.addEventListener("click", (e) => {
    if (e.target.closest(".history-delete-btn")) return;
    state.expression = calc.expression;
    renderExpression();
    renderResult(resultFormatted);
    state.result = resultFormatted;
    closeHistory();
    showToast("Expression loaded", "success");
  });

  // Enter key for accessibility
  article.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      article.click();
    }
  });

  // Delete button
  const deleteBtn = article.querySelector(".history-delete-btn");
  deleteBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    const id = deleteBtn.dataset.id;
    try {
      await apiDeleteHistoryItem(id);
      article.style.transition = "opacity 0.2s, transform 0.2s";
      article.style.opacity = "0";
      article.style.transform = "translateX(12px)";
      setTimeout(() => article.remove(), 220);

      // Show empty state if last item
      if (dom.historyList.querySelectorAll(".history-item").length <= 1) {
        setTimeout(() => {
          dom.historyList.innerHTML = '<p class="history-empty">No calculations yet.</p>';
        }, 230);
      }
      showToast("Deleted", "success");
    } catch (err) {
      showToast("Delete failed", "error");
    }
  });

  return article;
}

function openHistory() {
  state.historyOpen = true;
  dom.historyPanel.classList.add("open");
  dom.historyPanel.setAttribute("aria-hidden", "false");
  dom.historyOverlay.classList.add("visible");
  dom.historyOverlay.setAttribute("aria-hidden", "false");
  loadHistory();
}

function closeHistory() {
  state.historyOpen = false;
  dom.historyPanel.classList.remove("open");
  dom.historyPanel.setAttribute("aria-hidden", "true");
  dom.historyOverlay.classList.remove("visible");
  dom.historyOverlay.setAttribute("aria-hidden", "true");
}

// ═══════════════════════════════════════════════════════════════════════════
// 11. COPY RESULT
// ═══════════════════════════════════════════════════════════════════════════

async function copyResult() {
  const text = dom.resultDisplay.textContent;
  if (!text || text === "0" || text === "Error") {
    showToast("Nothing to copy", "error");
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    showToast("Result copied!", "success");
  } catch (_) {
    // Fallback for browsers that block clipboard without HTTPS
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    showToast("Result copied!", "success");
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 12. TOAST
// ═══════════════════════════════════════════════════════════════════════════

let toastTimer = null;

function showToast(message, type = "") {
  clearTimeout(toastTimer);
  dom.toast.textContent = message;
  dom.toast.className = "toast show" + (type ? ` ${type}` : "");
  toastTimer = setTimeout(() => {
    dom.toast.classList.remove("show");
  }, 2200);
}

// ═══════════════════════════════════════════════════════════════════════════
// 13. KEYBOARD SUPPORT
// ═══════════════════════════════════════════════════════════════════════════

function handleKeyboard(e) {
  // Don't intercept keyboard shortcuts while typing in another input
  if (e.target !== document.body && e.target.tagName !== "BUTTON") return;

  switch (e.key) {
    case "0": case "1": case "2": case "3": case "4":
    case "5": case "6": case "7": case "8": case "9":
      insertValue(e.key);
      break;

    case "+": insertValue("+"); break;
    case "-": insertValue("-"); break;
    case "*": insertValue("×"); break;  // we store × and the backend normalises
    case "/":
      e.preventDefault();               // prevent browser quick-find
      insertValue("÷");
      break;
    case "%": insertValue("%"); break;
    case ".": insertValue("."); break;
    case "(": insertValue("("); break;
    case ")": insertValue(")"); break;
    case "^": insertValue("**"); break;

    case "Enter":
      e.preventDefault();
      calculate();
      break;
    case "Escape":
      clearAll();
      break;
    case "Backspace":
      e.preventDefault();
      deleteLast();
      break;

    default:
      break;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 14. BUTTON CLICK HANDLER
// ═══════════════════════════════════════════════════════════════════════════

function handleButtonClick(e) {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;

  const action = btn.dataset.action;
  const value  = btn.dataset.value;

  switch (action) {
    case "insert":
      insertValue(value);
      break;
    case "calculate":
      calculate();
      break;
    default:
      break;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 15. UTILITIES
// ═══════════════════════════════════════════════════════════════════════════

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatDateTime(isoString) {
  if (!isoString) return "";
  try {
    const date = new Date(isoString);
    return date.toLocaleString(undefined, {
      month: "short",
      day:   "numeric",
      hour:  "2-digit",
      minute:"2-digit",
    });
  } catch (_) {
    return isoString;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 16. EVENT LISTENERS
// ═══════════════════════════════════════════════════════════════════════════

function bindEvents() {
  // Button grid
  document.querySelector(".button-grid").addEventListener("click", handleButtonClick);

  // AC / DEL
  dom.btnAc.addEventListener("click",  clearAll);
  dom.btnDel.addEventListener("click", deleteLast);

  // Mode
  dom.btnDeg.addEventListener("click", () => setMode("DEG"));
  dom.btnRad.addEventListener("click", () => setMode("RAD"));

  // Copy
  dom.btnCopy.addEventListener("click", copyResult);

  // Theme
  dom.btnTheme.addEventListener("click", toggleTheme);

  // History
  dom.btnHistoryToggle.addEventListener("click", () => {
    state.historyOpen ? closeHistory() : openHistory();
  });
  dom.btnHistoryClose.addEventListener("click", closeHistory);
  dom.historyOverlay.addEventListener("click",  closeHistory);

  // Clear history
  dom.btnClearHistory.addEventListener("click", async () => {
    if (!confirm("Clear all calculation history?")) return;
    try {
      await apiClearHistory();
      dom.historyList.innerHTML = '<p class="history-empty">No calculations yet.</p>';
      showToast("History cleared", "success");
    } catch (err) {
      showToast("Failed to clear history", "error");
    }
  });

  // Keyboard
  document.addEventListener("keydown", handleKeyboard);
}

// ═══════════════════════════════════════════════════════════════════════════
// 17. INIT
// ═══════════════════════════════════════════════════════════════════════════

function init() {
  initTheme();
  bindEvents();
  setMode("DEG");
  renderExpression();
  renderResult("0");
}

init();

// ═══════════════════════════════════════════════════════════════════════════
// ██╗   ██╗ ██████╗ ██╗ ██████╗███████╗     █████╗  ██████╗ ███████╗███╗   ██╗████████╗
// ██║   ██║██╔═══██╗██║██╔════╝██╔════╝    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
// ██║   ██║██║   ██║██║██║     █████╗      ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║
// ╚██╗ ██╔╝██║   ██║██║██║     ██╔══╝      ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║
//  ╚████╔╝ ╚██████╔╝██║╚██████╗███████╗    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
//   ╚═══╝   ╚═════╝ ╚═╝ ╚═════╝╚══════╝    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝
// All code below is ADDITIVE. Existing calculator functions above are untouched.
// ═══════════════════════════════════════════════════════════════════════════

/* ─────────────────────────────────────────────────────────────────────────
   VOICE AGENT — Section 18
   Functions:
     startVoiceRecognition()
     stopVoiceRecognition()
     processVoiceCommand(transcript)
     displayVoiceResult(data)
     speakResult(text)
     updateVoiceUI(state)
     sendVoiceChip(command)
   ───────────────────────────────────────────────────────────────────────── */

// ── Voice DOM refs (grabbed lazily after DOM is ready) ────────────────────
const vDom = {
  get card()         { return document.getElementById("voice-card"); },
  get btnMic()       { return document.getElementById("btn-mic"); },
  get btnOutput()    { return document.getElementById("btn-voice-output"); },
  get statusEl()     { return document.getElementById("voice-status"); },
  get waveEl()       { return document.getElementById("voice-wave"); },
  get resultArea()   { return document.getElementById("voice-result-area"); },
  get micIcon()      { return document.querySelector(".mic-icon"); },
  get stopIcon()     { return document.querySelector(".stop-icon"); },
};

// ── Voice state ───────────────────────────────────────────────────────────
const voiceState = {
  recognition:  null,       // SpeechRecognition instance
  listening:    false,
  supported:    false,
  outputOn:     true,       // TTS enabled?
  sessionId:    _genSessionId(),
  lang:         "en-IN",    // default language
};

function _genSessionId() {
  return "vs_" + Math.random().toString(36).slice(2, 10);
}

// ── Persist voice output preference ──────────────────────────────────────
function _loadVoicePrefs() {
  const saved = localStorage.getItem("scicalc-voice-output");
  voiceState.outputOn = saved === null ? true : saved === "true";
  _updateOutputBtn();
}

function _updateOutputBtn() {
  const btn = vDom.btnOutput;
  if (!btn) return;
  btn.classList.toggle("active", voiceState.outputOn);
  btn.setAttribute("aria-pressed", String(voiceState.outputOn));
  btn.title = voiceState.outputOn ? "Voice response ON — click to mute" : "Voice response OFF — click to enable";
}

// ── Speech Recognition setup ──────────────────────────────────────────────
function initSpeechRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    voiceState.supported = false;
    _showUnsupportedMessage();
    return;
  }

  voiceState.supported = true;
  const recognition = new SR();
  recognition.lang        = voiceState.lang;
  recognition.continuous  = false;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    voiceState.listening = true;
    updateVoiceUI("listening");
  };

  recognition.onresult = (event) => {
    let interim = "";
    let final   = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const t = event.results[i][0].transcript;
      if (event.results[i].isFinal) final += t;
      else interim += t;
    }
    // Show interim in status
    if (interim) {
      vDom.statusEl.textContent = `"${interim}"`;
    }
    if (final.trim()) {
      processVoiceCommand(final.trim());
    }
  };

  recognition.onerror = (event) => {
    voiceState.listening = false;
    const msgs = {
      "not-allowed":   "Microphone access denied. Please allow microphone permission.",
      "no-speech":     "No speech detected. Please try again.",
      "audio-capture": "No microphone found.",
      "network":       "Network error. Check your connection.",
      "aborted":       null,   // user stopped — not an error
    };
    const msg = msgs[event.error];
    if (msg) {
      updateVoiceUI("error", msg);
      _appendErrorCard(msg);
    } else {
      updateVoiceUI("idle");
    }
  };

  recognition.onend = () => {
    voiceState.listening = false;
    // If we're still showing "listening" (e.g. silence timeout), go idle
    if (vDom.statusEl && vDom.statusEl.classList.contains("listening")) {
      updateVoiceUI("idle");
    }
  };

  voiceState.recognition = recognition;
}

function _showUnsupportedMessage() {
  const area = vDom.resultArea;
  if (!area) return;
  area.innerHTML = `
    <p class="voice-unsupported">
      ⚠️ Voice recognition is not supported in this browser.<br>
      Please use Chrome, Edge, or Safari.
    </p>`;
  const btn = vDom.btnMic;
  if (btn) {
    btn.disabled = true;
    btn.style.opacity = "0.4";
    btn.title = "Voice recognition not supported";
  }
}

// ── UI state machine ─────────────────────────────────────────────────────
/**
 * updateVoiceUI(stateName, message?)
 * States: "idle" | "listening" | "processing" | "success" | "error"
 */
function updateVoiceUI(uiState, message) {
  const btn    = vDom.btnMic;
  const status = vDom.statusEl;
  const wave   = vDom.waveEl;
  const micSvg = vDom.micIcon;
  const stopSvg= vDom.stopIcon;
  if (!btn || !status) return;

  // Reset all state classes on button
  btn.classList.remove("listening", "processing", "success", "error");
  status.classList.remove("idle", "listening", "processing", "success", "error");
  wave.classList.remove("active");

  // Show stop icon while listening, mic otherwise
  if (micSvg)  micSvg.style.display  = uiState === "listening" ? "none" : "";
  if (stopSvg) stopSvg.style.display = uiState === "listening" ? ""     : "none";

  const labels = {
    idle:       "Tap to Speak",
    listening:  "🔴 Listening...",
    processing: "⏳ Processing...",
    success:    "✓ Done",
    error:      "⚠️ " + (message || "Couldn't understand"),
  };

  btn.classList.add(uiState);
  status.classList.add(uiState);
  status.textContent = message || labels[uiState] || "";
  btn.setAttribute("aria-label", labels[uiState] || "Voice");

  if (uiState === "listening") wave.classList.add("active");

  // Auto-reset success/error back to idle after a moment
  if (uiState === "success" || uiState === "error") {
    setTimeout(() => updateVoiceUI("idle"), 2800);
  }
}

// ── Start / stop recognition ──────────────────────────────────────────────
function startVoiceRecognition() {
  if (!voiceState.supported) {
    showToast("Voice recognition not supported in this browser", "error");
    return;
  }
  if (voiceState.listening) {
    stopVoiceRecognition();
    return;
  }
  try {
    voiceState.recognition.start();
  } catch (e) {
    // Recognition already started — abort and restart
    voiceState.recognition.abort();
    setTimeout(() => voiceState.recognition.start(), 200);
  }
}

function stopVoiceRecognition() {
  if (voiceState.recognition) {
    voiceState.recognition.stop();
  }
  voiceState.listening = false;
  updateVoiceUI("idle");
}

// ── Send command to backend ───────────────────────────────────────────────
async function processVoiceCommand(transcript) {
  if (!transcript || !transcript.trim()) return;

  updateVoiceUI("processing");

  // Clear previous error cards so they don't pile up
  if (vDom.resultArea) {
    vDom.resultArea.querySelectorAll(".error-card").forEach(el => el.remove());
  }

  try {
    const response = await fetch(`${API_BASE}/voice/command`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        command:    transcript,
        mode:       state.mode,
        session_id: voiceState.sessionId,
      }),
    });

    if (!response.ok) {
      let detail = `Error ${response.status}`;
      try { detail = (await response.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }

    const data = await response.json();
    displayVoiceResult(data);

    // ── Push result into the main calculator display ──────────────────
    state.expression     = data.expression;
    state.result         = formatResult(data.result);
    state.justCalculated = true;   // next button press starts fresh
    renderExpression();
    renderResult(state.result);
    clearStatus();

    // Flash the calc display so the user sees voice populated it
    _flashCalcDisplay();

    // ── Reload history if open ────────────────────────────────────────
    if (state.historyOpen) loadHistory();

    // ── Speak result ──────────────────────────────────────────────────
    if (voiceState.outputOn) speakResult(data.spoken_response);

    updateVoiceUI("success");

  } catch (err) {
    const msg = err.message || "Could not process voice command";
    updateVoiceUI("error", msg);
    _appendErrorCard(msg);
    showToast(msg, "error");
  }
}

// ── Display voice result in the voice card ────────────────────────────────
function displayVoiceResult(data) {
  const area = vDom.resultArea;
  if (!area) return;

  const card = document.createElement("div");
  card.className = "voice-result-card";
  card.innerHTML = `
    <div class="voice-transcript">${escapeHtml(data.transcript)}</div>
    <div class="voice-expr-line">${escapeHtml(data.expression)}</div>
    <div class="voice-result-value">${escapeHtml(formatResult(data.result))}</div>
  `;

  // Prepend so newest is on top
  area.insertBefore(card, area.firstChild);

  // Keep only last 8 results visible to avoid overflow
  const cards = area.querySelectorAll(".voice-result-card");
  if (cards.length > 8) cards[cards.length - 1].remove();
}

function _appendErrorCard(message) {
  const area = vDom.resultArea;
  if (!area) return;
  const card = document.createElement("div");
  card.className = "voice-result-card error-card";
  card.innerHTML = `<div class="voice-error-msg">⚠️ ${escapeHtml(message)}</div>`;
  area.insertBefore(card, area.firstChild);
}

// ── Text-to-Speech ────────────────────────────────────────────────────────
function speakResult(text) {
  if (!text || !window.speechSynthesis) return;
  // Cancel any current utterance
  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang  = voiceState.lang;
  utter.rate  = 1.0;
  utter.pitch = 1.0;
  window.speechSynthesis.speak(utter);
}

// ── Voice chip clicks ─────────────────────────────────────────────────────
function sendVoiceChip(command) {
  if (!voiceState.supported) {
    // Even if mic is unsupported, still send the chip command to backend
    updateVoiceUI("processing");
    processVoiceCommand(command);
    return;
  }
  // Show the command as if spoken, then process
  vDom.statusEl.textContent = `"${command}"`;
  processVoiceCommand(command);
}

// ── History item — extend buildHistoryItem to show voice badge ────────────
// Monkey-patch: wrap the original function to add voice metadata rendering.
const _origBuildHistoryItem = buildHistoryItem;

buildHistoryItem = function(calc) {                // eslint-disable-line no-func-assign
  const article = _origBuildHistoryItem(calc);

  // Inject input-type badge next to the mode badge
  const metaRow = article.querySelector(".history-meta");
  if (metaRow) {
    const inputType = calc.input_type || "manual";
    const badge = document.createElement("span");
    badge.className = `history-input-badge ${inputType}`;
    badge.textContent = inputType === "voice" ? "🎙️ Voice" : "🧮 Manual";
    metaRow.insertBefore(badge, metaRow.firstChild);

    // If voice — show transcript below expr
    if (inputType === "voice" && calc.transcript) {
      const exprEl = article.querySelector(".history-expr");
      if (exprEl) {
        const tr = document.createElement("div");
        tr.className = "history-voice-transcript";
        tr.textContent = calc.transcript;
        exprEl.parentNode.insertBefore(tr, exprEl.nextSibling);
      }
    }
  }

  return article;
};

// ── Bind voice events ─────────────────────────────────────────────────────
function bindVoiceEvents() {
  // Mic button
  const btnMic = vDom.btnMic;
  if (btnMic) {
    btnMic.addEventListener("click", () => {
      if (voiceState.listening) stopVoiceRecognition();
      else startVoiceRecognition();
    });
  }

  // Voice output toggle
  const btnOut = vDom.btnOutput;
  if (btnOut) {
    btnOut.addEventListener("click", () => {
      voiceState.outputOn = !voiceState.outputOn;
      localStorage.setItem("scicalc-voice-output", String(voiceState.outputOn));
      _updateOutputBtn();
      showToast(`Voice response ${voiceState.outputOn ? "ON" : "OFF"}`, "success");
      if (!voiceState.outputOn) window.speechSynthesis?.cancel();
    });
  }

  // Voice chips
  document.querySelectorAll(".voice-chip").forEach((chip) => {
    chip.addEventListener("click", () => sendVoiceChip(chip.dataset.cmd));
  });

  // Keyboard shortcut: Space on the mic button
  if (btnMic) {
    btnMic.addEventListener("keydown", (e) => {
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault();
        btnMic.click();
      }
    });
  }
}

// ── Init voice agent ──────────────────────────────────────────────────────
function initVoiceAgent() {
  _loadVoicePrefs();
  initSpeechRecognition();
  bindVoiceEvents();
  updateVoiceUI("idle");
}

// Call after the main init() has already run
initVoiceAgent();
