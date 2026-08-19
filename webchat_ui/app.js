/**
 * DULUS WEBCHAT — app.js
 * Manager-09: GUI & WebChat Engineer
 *
 * Features:
 *  - Real-time SSE streaming with smooth token rendering
 *  - Markdown rendering via marked.js
 *  - Code syntax highlighting via highlight.js + copy buttons
 *  - File upload (drag/drop + button)
 *  - Conversation export (MD, JSON, PDF/print)
 *  - Keyboard shortcuts + Ctrl+K command palette
 *  - Theme system (dark/light/system)
 *  - WCAG 2.1 AA accessibility
 *  - Voice input (Web Speech API)
 *  - Session management (CRUD + search + rename)
 *  - Toast notifications
 *  - Context menu
 *  - Auto-resize textarea
 *  - Typing indicator
 */

// ============================================================
// CONFIG & CONSTANTS
// ============================================================
const ACTIVE_KEY            = 'dulus_active_session';
const SIDEBAR_COLLAPSED_KEY = 'dulus_sidebar_collapsed';
const THEME_KEY             = 'dulus-theme';
const THEME_MODE_KEY        = 'dulus-theme-mode';
const DEFAULT_SESSION_ID    = 'default';
const POLL_INTERVAL_MS      = 5000;

// ============================================================
// STATE
// ============================================================
let sessions        = [];
let activeSessionId = DEFAULT_SESSION_ID;
let ctxTargetId     = null;
let isMobile        = window.innerWidth < 768;
let renamingId      = null;
let isStreaming     = false;
let activeChatRunId = null;
let activeChatAbortController = null;
let stopRequested   = false;
let attachedFiles   = [];
let recognition     = null;
let isRecording     = false;
let cmdItems        = [];
let cmdActiveIdx    = -1;
let currentTheme    = 'dark';

// ============================================================
// DOM REFS — grabbed once after DOMContentLoaded
// ============================================================
let $log, $inp, $sendBtn, $stopBtn, $typingIndicator,
    $emptyState, $sidebar, $sessionList, $searchInput,
    $toastContainer, $ctxMenu, $cmdPalette, $cmdSearch,
    $cmdList, $dropOverlay, $filePreview, $fileInput,
    $attachBtn, $voiceBtn, $charCount, $statusDot,
    $statusText, $themeToggle, $themeSelect, $exportModal, $personaSelect;

// ============================================================
// MARKED.JS CONFIG
// ============================================================
function initMarked() {
  if (typeof marked === 'undefined') return;
  marked.setOptions({
    breaks: true,
    gfm: true,
  });
  // Custom renderer: wrap code blocks in our styled wrapper
  const renderer = new marked.Renderer();
  renderer.code = function(code, language) {
    const lang = language || 'text';
    const escaped = escapeHtml(code);
    const id = 'cb-' + Math.random().toString(36).slice(2, 8);
    return `
<div class="code-block-wrapper" id="${id}">
  <div class="code-block-header">
    <span class="code-lang-label">${lang}</span>
    <button class="code-copy-btn" onclick="copyCode('${id}')" aria-label="Copy code">Copy</button>
  </div>
  <pre><code class="hljs language-${lang}">${hljs ? hljs.highlightAuto(code, lang !== 'text' ? [lang] : undefined).value : escaped}</code></pre>
</div>`;
  };
  marked.setOptions({ renderer });
}

// ============================================================
// INIT
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
  $log            = document.getElementById('log');
  $inp            = document.getElementById('inp');
  $sendBtn        = document.getElementById('sendBtn');
  $stopBtn        = document.getElementById('stopBtn');
  $typingIndicator = document.getElementById('typingIndicator');
  $emptyState     = document.getElementById('emptyState');
  $sidebar        = document.getElementById('sidebar');
  $sessionList    = document.getElementById('sessionList');
  $searchInput    = document.getElementById('searchInput');
  $toastContainer = document.getElementById('toastContainer');
  $ctxMenu        = document.getElementById('ctxMenu');
  $cmdPalette     = document.getElementById('cmdPalette');
  $cmdSearch      = document.getElementById('cmdSearch');
  $cmdList        = document.getElementById('cmdList');
  $dropOverlay    = document.getElementById('dropOverlay');
  $filePreview    = document.getElementById('filePreview');
  $fileInput      = document.getElementById('fileInput');
  $attachBtn      = document.getElementById('attachBtn');
  $voiceBtn       = document.getElementById('voiceBtn');
  $charCount      = document.getElementById('charCount');
  $statusDot      = document.getElementById('statusDot');
  $statusText     = document.getElementById('statusText');
  $themeToggle    = document.getElementById('themeToggle');
  $themeSelect    = document.getElementById('themeSelect');
  $exportModal    = document.getElementById('exportModal');
  $personaSelect  = document.getElementById('personaSelect');

  initMarked();
  initTheme();
  loadThemes();
  initSidebar();
  initInput();
  initVoice();
  initDragDrop();
  initKeyboardShortcuts();
  buildCmdItems();
  loadSessions();
  syncWithServer();
  setInterval(syncWithServer, POLL_INTERVAL_MS);

  // ARIA live region for screen readers
  const liveRegion = document.createElement('div');
  liveRegion.setAttribute('aria-live', 'polite');
  liveRegion.setAttribute('aria-atomic', 'false');
  liveRegion.className = 'sr-only';
  liveRegion.id = 'liveRegion';
  document.body.appendChild(liveRegion);
});

// ============================================================
// THEME SYSTEM
// ============================================================
function initTheme() {
  const saved = localStorage.getItem(THEME_MODE_KEY) || 'dark';
  applyThemeMode(saved);
  if ($themeToggle) {
    $themeToggle.addEventListener('click', cycleTheme);
  }
  // Also sync server theme
  const serverTheme = localStorage.getItem(THEME_KEY) || 'dulus';
  fetchServerTheme(serverTheme);
}

function applyThemeMode(mode) {
  currentTheme = mode;
  localStorage.setItem(THEME_MODE_KEY, mode);
  document.body.classList.remove('light', 'dark');
  if (mode === 'light') {
    document.body.classList.add('light');
  } else if (mode === 'system') {
    if (window.matchMedia('(prefers-color-scheme: light)').matches) {
      document.body.classList.add('light');
    }
  }
  updateThemeIcon();
}

function cycleTheme() {
  const modes = ['dark', 'light', 'system'];
  const idx = modes.indexOf(currentTheme);
  const next = modes[(idx + 1) % modes.length];
  applyThemeMode(next);
  showToast(`Theme: ${next}`, 'info');
}

function updateThemeIcon() {
  if (!$themeToggle) return;
  const icons = {
    dark: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`,
    light: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`,
    system: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`,
  };
  $themeToggle.innerHTML = icons[currentTheme] || icons.dark;
  $themeToggle.title = `Theme: ${currentTheme} (click to cycle)`;
}

async function fetchServerTheme(name) {
  try {
    const res = await fetch(`/api/themes/${encodeURIComponent(name)}/css`);
    const css = await res.text();
    if (css) {
      let el = document.getElementById('dynamic-theme');
      if (!el) { el = document.createElement('style'); el.id = 'dynamic-theme'; document.head.appendChild(el); }
      el.textContent = css;
      localStorage.setItem(THEME_KEY, name);
      if ($themeSelect) $themeSelect.value = name;
    }
  } catch (_) {}
}

async function loadThemes() {
  if (!$themeSelect) return;
  try {
    const res = await fetch('/api/themes');
    if (!res.ok) throw new Error('Failed to load themes');
    const data = await res.json();
    const themes = data.themes || {};
    const saved = localStorage.getItem(THEME_KEY) || 'dulus';

    $themeSelect.innerHTML = '<option value="">Theme</option>';
    Object.keys(themes).forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      if (name === saved) opt.selected = true;
      $themeSelect.appendChild(opt);
    });

    $themeSelect.addEventListener('change', (e) => {
      const name = e.target.value;
      if (name) fetchServerTheme(name);
    });
  } catch (_) {
    $themeSelect.innerHTML = '<option value="">Theme</option>';
  }
}

// ============================================================
// UTILS
// ============================================================
function escapeHtml(t) {
  const d = document.createElement('div');
  d.textContent = t;
  return d.innerHTML;
}

function genId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

function formatTime(ts) {
  const d = new Date(ts);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function renderMarkdown(text) {
  if (typeof marked === 'undefined') return escapeHtml(text).replace(/\n/g, '<br>');
  try { return marked.parse(text); }
  catch (_) { return escapeHtml(text).replace(/\n/g, '<br>'); }
}

function setStatus(text, state) {
  if (!$statusDot || !$statusText) return;
  $statusDot.className = 'status-dot' + (state ? ` ${state}` : '');
  $statusText.textContent = text;
}

function announceToScreenReader(msg) {
  const lr = document.getElementById('liveRegion');
  if (lr) { lr.textContent = ''; setTimeout(() => lr.textContent = msg, 50); }
}

// ============================================================
// TOAST NOTIFICATIONS
// ============================================================
const TOAST_ICONS = {
  success: `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
  error:   `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
  info:    `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
  warning: `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
};

function showToast(message, type = 'info', duration = 3500) {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.setAttribute('role', 'alert');
  t.innerHTML = (TOAST_ICONS[type] || TOAST_ICONS.info) +
    `<span class="toast-text">${escapeHtml(message)}</span>`;
  $toastContainer.appendChild(t);
  setTimeout(() => {
    t.classList.add('exiting');
    setTimeout(() => t.remove(), 260);
  }, duration);
}

// ============================================================
// SIDEBAR
// ============================================================
function initSidebar() {
  const collapsed = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
  if (collapsed === '1') $sidebar.classList.add('collapsed');

  document.getElementById('sidebarOverlay')?.addEventListener('click', closeMobileSidebar);

  window.addEventListener('resize', () => {
    const nowMobile = window.innerWidth < 768;
    if (nowMobile !== isMobile) {
      isMobile = nowMobile;
      if (!isMobile) closeMobileSidebar();
    }
  });
}

function toggleSidebar() {
  if (isMobile) {
    $sidebar.classList.contains('open') ? closeMobileSidebar() : openMobileSidebar();
  } else {
    $sidebar.classList.toggle('collapsed');
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, $sidebar.classList.contains('collapsed') ? '1' : '0');
  }
}

function openMobileSidebar() {
  $sidebar.classList.add('open');
  document.getElementById('sidebarOverlay')?.classList.add('open');
}

function closeMobileSidebar() {
  $sidebar.classList.remove('open');
  document.getElementById('sidebarOverlay')?.classList.remove('open');
}

// ============================================================
// SESSION MANAGEMENT
// ============================================================
function loadSessions() {
  fetch('/api/sessions')
    .then(r => r.ok ? r.json() : [])
    .then(data => {
      if (data && data.length) {
        sessions = data.map(s => ({
          id: s.id,
          title: s.title || 'Chat',
          timestamp: s.saved_at ? new Date(s.saved_at).getTime() : Date.now(),
          messages: s.messages || [],
        }));
        const saved = localStorage.getItem(ACTIVE_KEY);
        activeSessionId = (saved && sessions.some(s => s.id === saved)) ? saved : sessions[0].id;
      } else {
        sessions = [{ id: DEFAULT_SESSION_ID, title: 'Chat', timestamp: Date.now(), messages: [] }];
        activeSessionId = DEFAULT_SESSION_ID;
      }
      renderSessions();
      selectSession(activeSessionId, false);
    })
    .catch(() => {
      sessions = [{ id: DEFAULT_SESSION_ID, title: 'Chat', timestamp: Date.now(), messages: [] }];
      activeSessionId = DEFAULT_SESSION_ID;
      renderSessions();
      showEmptyState();
    });
}

function saveActive() {
  localStorage.setItem(ACTIVE_KEY, activeSessionId);
}

function getActiveSession() {
  return sessions.find(s => s.id === activeSessionId) || sessions[0];
}

function renderSessions() {
  const q = $searchInput?.value.toLowerCase() || '';
  const filtered = sessions.filter(s => !q || s.title.toLowerCase().includes(q));

  if (!filtered.length) {
    $sessionList.innerHTML = '<div style="padding:20px;text-align:center;color:var(--dim);font-size:11px">No chats found</div>';
    return;
  }

  // Group by date
  const today = new Date().toDateString();
  const yesterday = new Date(Date.now() - 86400000).toDateString();
  const groups = { Today: [], Yesterday: [], Earlier: [] };
  filtered.forEach(s => {
    const d = new Date(s.timestamp).toDateString();
    if (d === today) groups.Today.push(s);
    else if (d === yesterday) groups.Yesterday.push(s);
    else groups.Earlier.push(s);
  });

  let html = '';
  for (const [label, items] of Object.entries(groups)) {
    if (!items.length) continue;
    html += `<div class="session-group-label">${label}</div>`;
    items.forEach(s => {
      html += renderSessionItem(s);
    });
  }
  $sessionList.innerHTML = html;

  if (renamingId) {
    const inp = document.getElementById(`rename-${renamingId}`);
    if (inp) { inp.focus(); inp.select(); }
  }
}

function renderSessionItem(s) {
  const isActive   = s.id === activeSessionId;
  const isRenaming = s.id === renamingId;
  const msgCount   = s.messages ? s.messages.length : 0;

  if (isRenaming) {
    return `<div class="session-item active renaming" data-id="${s.id}">
      <div class="session-icon" aria-hidden="true">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      </div>
      <input class="session-rename-input" value="${escapeHtml(s.title)}"
        id="rename-${s.id}"
        onkeydown="renameKey(event,'${s.id}')"
        onblur="finishRename('${s.id}')"
        aria-label="Rename chat">
    </div>`;
  }

  return `<div class="session-item ${isActive ? 'active' : ''}" data-id="${s.id}"
    onclick="selectSession('${s.id}')"
    oncontextmenu="showCtx(event,'${s.id}')"
    role="button" tabindex="0"
    aria-label="${escapeHtml(s.title)}, ${msgCount} messages"
    aria-selected="${isActive}"
    onkeydown="if(event.key==='Enter'||event.key===' ')selectSession('${s.id}')">
    <div class="session-icon" aria-hidden="true">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
    </div>
    <div class="session-info">
      <div class="session-title">${escapeHtml(s.title)}</div>
      <div class="session-time">${formatTime(s.timestamp)}</div>
    </div>
    <div class="session-actions" onclick="event.stopPropagation()">
      <button onclick="startRename('${s.id}')" title="Rename" aria-label="Rename chat">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
      </button>
      <button onclick="deleteSession('${s.id}')" title="Delete" aria-label="Delete chat">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
      </button>
    </div>
  </div>`;
}

async function selectSession(id, fetchHistory = true) {
  activeSessionId = id;
  saveActive();
  renderSessions();

  const s = getActiveSession();
  if (!s) return;

  clearLog();
  if (s.messages && s.messages.length) {
    hideEmptyState();
    s.messages.forEach(m => {
      if (m.role === 'user') addUserMessage(m.content, false);
      else if (m.role === 'assistant') {
        const text = typeof m.content === 'string' ? m.content :
          (Array.isArray(m.content) ? (m.content.find(c => c.type === 'text') || {}).text || '' : '');
        if (text) addAssistantMessage(text, false);
      }
    });
  } else {
    showEmptyState();
  }

  closeMobileSidebar();

  if (fetchHistory) {
    try {
      await fetch('/api/session/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: s.messages || [] }),
      });
    } catch (_) {}
  }
}

function newChat() {
  // ── Analytics: session_created ──
  mpTrack('session_created', { source: 'webchat' });
  fetch('/clear', { method: 'POST' }).then(() => {
    const ns = { id: genId(), title: 'New Chat', timestamp: Date.now(), messages: [] };
    sessions.unshift(ns);
    activeSessionId = ns.id;
    saveActive();
    clearLog();
    renderSessions();
    closeMobileSidebar();
    showEmptyState();
    showToast('New chat started', 'success');
    fetch('/api/session/load', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: [], session_id: ns.id }),
    }).catch(() => {});
  });
}

function startRename(id) { renamingId = id; renderSessions(); }

function finishRename(id) {
  const el = document.getElementById(`rename-${id}`);
  if (el && el.value.trim()) {
    const s = sessions.find(x => x.id === id);
    if (s) s.title = el.value.trim();
  }
  renamingId = null;
  renderSessions();
}

function renameKey(e, id) {
  if (e.key === 'Enter') { e.preventDefault(); finishRename(id); }
  else if (e.key === 'Escape') { renamingId = null; renderSessions(); }
}

function filterSessions() { renderSessions(); }

function deleteSession(id) {
  const s = sessions.find(x => x.id === id);
  if (!s) return;
  if (!confirm(`Delete "${s.title}"?`)) return;
  fetch(`/api/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' }).catch(() => {});
  sessions = sessions.filter(x => x.id !== id);
  if (!sessions.length) {
    sessions.push({ id: genId(), title: 'Chat', timestamp: Date.now(), messages: [] });
  }
  if (activeSessionId === id) activeSessionId = sessions[0].id;
  saveActive();
  selectSession(activeSessionId);
  renderSessions();
  showToast('Chat deleted', 'info');
}

function refreshSessions() {
  loadSessions();
  showToast('Chats refreshed', 'success');
}

// ============================================================
// CONTEXT MENU
// ============================================================
function showCtx(e, id) {
  e.preventDefault();
  ctxTargetId = id;
  $ctxMenu.style.display = 'block';
  let x = e.clientX, y = e.clientY;
  if (x + 160 > window.innerWidth) x = window.innerWidth - 165;
  if (y + 90 > window.innerHeight) y = window.innerHeight - 95;
  $ctxMenu.style.left = x + 'px';
  $ctxMenu.style.top  = y + 'px';
}
function hideCtx() { $ctxMenu.style.display = 'none'; ctxTargetId = null; }
function ctxRename() { if (ctxTargetId) startRename(ctxTargetId); hideCtx(); }
function ctxDelete()  { if (ctxTargetId) deleteSession(ctxTargetId); hideCtx(); }
document.addEventListener('click', e => { if (!e.target.closest('#ctxMenu')) hideCtx(); });

// ============================================================
// CHAT LOG
// ============================================================
let _currentAssistantEl = null;
let _currentAssistantText = '';
let _currentToolContainer = null;
let _followStreamingOutput = true;
let _autoScrollFrame = null;
let _lastChatTouchY = null;

function clearLog() {
  $log.innerHTML = '';
  _currentAssistantEl   = null;
  _currentAssistantText = '';
  _currentToolContainer = null;
  _followStreamingOutput = true;
  _lastChatTouchY = null;
  if (_autoScrollFrame !== null) {
    cancelAnimationFrame(_autoScrollFrame);
    _autoScrollFrame = null;
  }
}

function showEmptyState() {
  if ($emptyState) $emptyState.style.display = 'flex';
}

function hideEmptyState() {
  if ($emptyState) $emptyState.style.display = 'none';
}

function isNearChatBottom(threshold = 140) {
  return $log.scrollHeight - $log.scrollTop - $log.clientHeight <= threshold;
}

function scrollToBottom(force = false) {
  if (force) _followStreamingOutput = true;
  if (!_followStreamingOutput || _autoScrollFrame !== null) return;

  // Markdown and tool blocks can change height substantially in one chunk.
  // Scroll after layout so streaming never outruns the viewport.
  _autoScrollFrame = requestAnimationFrame(() => {
    _autoScrollFrame = null;
    if (_followStreamingOutput) {
      $log.scrollTop = $log.scrollHeight;
    }
  });
}

function addUserMessage(text, animate = true) {
  hideEmptyState();
  _currentAssistantEl = null;
  _currentToolContainer = null;
  const el = document.createElement('div');
  el.className = 'msg user' + (animate ? '' : '');
  el.setAttribute('role', 'article');
  el.setAttribute('aria-label', 'You');
  if (!animate) el.style.animation = 'none';
  const content = document.createElement('div');
  content.className = 'msg-content';
  content.textContent = text;
  el.appendChild(content);
  $log.appendChild(el);
  scrollToBottom(true);
  return el;
}

function ensureAssistantEl() {
  if (!_currentAssistantEl) {
    _currentAssistantEl = document.createElement('div');
    _currentAssistantEl.className = 'msg assistant streaming';
    _currentAssistantEl.setAttribute('role', 'article');
    _currentAssistantEl.setAttribute('aria-label', 'Dulus');

    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.innerHTML = `<div class="msg-avatar-icon">🦅</div><span>Dulus</span>`;

    const content = document.createElement('div');
    content.className = 'msg-content';
    content.id = 'current-assistant-content';

    _currentAssistantEl.appendChild(avatar);
    _currentAssistantEl.appendChild(content);
    $log.appendChild(_currentAssistantEl);
    _currentAssistantText = '';
  }
  return _currentAssistantEl;
}

function appendStreamText(chunk) {
  hideEmptyState();
  ensureAssistantEl();
  _currentAssistantText += chunk;
  // Update rendered markdown in real-time
  const contentEl = _currentAssistantEl.querySelector('.msg-content');
  if (contentEl) {
    contentEl.innerHTML = renderMarkdown(_currentAssistantText);
    applyHljs(contentEl);
  }
  scrollToBottom();
}

function addAssistantMessage(text, animate = true) {
  hideEmptyState();
  const el = document.createElement('div');
  el.className = 'msg assistant';
  el.setAttribute('role', 'article');
  el.setAttribute('aria-label', 'Dulus');
  if (!animate) el.style.animation = 'none';

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.innerHTML = `<div class="msg-avatar-icon">🦅</div><span>Dulus</span>`;

  const content = document.createElement('div');
  content.className = 'msg-content';
  content.innerHTML = renderMarkdown(text);
  applyHljs(content);

  el.appendChild(avatar);
  el.appendChild(content);
  $log.appendChild(el);
  scrollToBottom();
  announceToScreenReader('Dulus responded');
  return el;
}

function finalizeAssistant(meta) {
  if (!_currentAssistantEl) return;
  _currentAssistantEl.classList.remove('streaming');

  if (meta && (meta.in || meta.out)) {
    const metaEl = document.createElement('div');
    metaEl.className = 'msg-meta';
    let html = `<span class="meta-pill">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
      in ${meta.in} · out ${meta.out}
    </span>`;
    if (meta.cache_read) {
      html += `<span class="meta-pill cache-hit">cache hit: ${meta.cache_read}</span>`;
    }
    if (meta.cache_write) {
      html += `<span class="meta-pill">cached: ${meta.cache_write}</span>`;
    }
    metaEl.innerHTML = html;
    _currentAssistantEl.appendChild(metaEl);
  }
  // ── Analytics: response_received ──
  mpTrack('response_received', {
    session_id: activeSessionId,
    tokens_in: meta?.in || 0,
    tokens_out: meta?.out || 0,
    cache_hit: !!meta?.cache_read,
  });
  _currentAssistantEl = null;
  _currentAssistantText = '';
  _currentToolContainer = null;
  scrollToBottom();
}

function appendThinking(text) {
  ensureAssistantEl();
  let block = _currentAssistantEl.querySelector('.think-block');
  if (!block) {
    block = document.createElement('div');
    block.className = 'think-block';
    block.innerHTML = `<div class="think-block-toggle" onclick="this.nextElementSibling.classList.toggle('visible')" aria-expanded="false">
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      thinking
    </div>
    <div class="think-block-body visible"><pre></pre></div>`;
    _currentAssistantEl.appendChild(block);
  }
  const pre = block.querySelector('pre');
  if (pre) pre.textContent += text;
  scrollToBottom();
}

function appendToolCall(name, inputs) {
  ensureAssistantEl();
  const tc = document.createElement('div');
  tc.className = 'tool-call';
  tc.setAttribute('role', 'status');
  tc.dataset.tool = name;
  tc.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
    <span class="tool-call-name">${escapeHtml(name)}</span>
    <span class="tool-call-status running" aria-label="running">running</span>`;
  _currentAssistantEl.appendChild(tc);
  scrollToBottom();
  return tc;
}

function updateToolCall(name, result, permitted) {
  if (!_currentAssistantEl) return;
  const tc = _currentAssistantEl.querySelector(`.tool-call[data-tool="${CSS.escape(name)}"]`);
  if (tc) {
    const statusEl = tc.querySelector('.tool-call-status');
    if (statusEl) {
      statusEl.className = 'tool-call-status done';
      statusEl.textContent = permitted ? 'done' : 'denied';
    }
  }
  if (result && result.length > 2) {
    const res = document.createElement('div');
    res.className = 'tool-result';
    res.textContent = result.slice(0, 1200) + (result.length > 1200 ? '...' : '');
    _currentAssistantEl.appendChild(res);
  }
  scrollToBottom();
}

function showPermissionBanner(id, desc) {
  ensureAssistantEl();
  const b = document.createElement('div');
  b.className = 'perm-banner';
  b.setAttribute('role', 'alertdialog');
  b.setAttribute('aria-label', 'Permission required');
  b.innerHTML = `
    <svg class="perm-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
    <span class="perm-text">${escapeHtml(desc)}</span>
    <div class="perm-actions">
      <button class="perm-btn" onclick="grantPermission('${id}',false);this.closest('.perm-banner').remove()">Deny</button>
      <button class="perm-btn approve" onclick="grantPermission('${id}',true);this.closest('.perm-banner').remove()">Allow</button>
    </div>`;
  _currentAssistantEl.appendChild(b);
  scrollToBottom();
  announceToScreenReader('Permission required: ' + desc);
}

async function grantPermission(id, granted) {
  await fetch('/permission', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, granted }),
  });
}

// ── AskUserQuestion banner (same UX as the permission banner) ──────────
function showQuestionBanner(id, questionText, options, allowFreetext) {
  ensureAssistantEl();
  const b = document.createElement('div');
  b.className = 'question-banner';
  b.setAttribute('role', 'alertdialog');
  b.setAttribute('aria-label', 'Question from agent');

  const head = document.createElement('div');
  head.className = 'question-head';
  head.innerHTML = `
    <svg class="question-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
    <span class="question-text">${escapeHtml(questionText)}</span>`;
  b.appendChild(head);

  const done = (answer) => {
    answerQuestion(id, answer);
    // Replace banner with a compact "answered" note
    const note = document.createElement('div');
    note.className = 'question-answered';
    note.textContent = '✅ ' + answer;
    b.replaceWith(note);
  };

  if (Array.isArray(options) && options.length) {
    const optWrap = document.createElement('div');
    optWrap.className = 'question-options';
    options.forEach((opt) => {
      const label = typeof opt === 'string' ? opt : (opt.label || '');
      const desc = typeof opt === 'object' && opt.description ? opt.description : '';
      const btn = document.createElement('button');
      btn.className = 'question-opt-btn';
      btn.innerHTML = `<span class="question-opt-label">${escapeHtml(label)}</span>` +
        (desc ? `<span class="question-opt-desc">${escapeHtml(desc)}</span>` : '');
      btn.onclick = () => done(label);
      optWrap.appendChild(btn);
    });
    b.appendChild(optWrap);
  }

  if (allowFreetext !== false) {
    const ftWrap = document.createElement('div');
    ftWrap.className = 'question-freetext';
    const inp = document.createElement('input');
    inp.type = 'text';
    inp.placeholder = 'Or type your answer…';
    inp.className = 'question-input';
    const sendBtn = document.createElement('button');
    sendBtn.className = 'question-send-btn';
    sendBtn.textContent = 'Send';
    const submit = () => {
      const v = inp.value.trim();
      if (v) done(v);
    };
    sendBtn.onclick = submit;
    inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit(); });
    ftWrap.appendChild(inp);
    ftWrap.appendChild(sendBtn);
    b.appendChild(ftWrap);
    setTimeout(() => inp.focus(), 50);
  }

  _currentAssistantEl.appendChild(b);
  scrollToBottom();
  announceToScreenReader('Question from agent: ' + questionText);
}

async function answerQuestion(id, answer) {
  await fetch('/question', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, answer }),
  });
}

// ============================================================
// HIGHLIGHT.JS HELPERS
// ============================================================
function applyHljs(container) {
  if (typeof hljs === 'undefined') return;
  container.querySelectorAll('pre code').forEach(block => {
    // Only if not already highlighted
    if (!block.dataset.highlighted) {
      hljs.highlightElement(block);
      block.dataset.highlighted = '1';
    }
  });
}

function copyCode(wrapperId) {
  const wrapper = document.getElementById(wrapperId);
  if (!wrapper) return;
  const code = wrapper.querySelector('code');
  if (!code) return;
  navigator.clipboard.writeText(code.textContent).then(() => {
    const btn = wrapper.querySelector('.code-copy-btn');
    if (btn) {
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
    }
  }).catch(() => showToast('Copy failed', 'error'));
}

// ============================================================
// SEND MESSAGE
// ============================================================
function setStreamingControls(active) {
  $sendBtn.disabled = active;
  $log.classList.toggle('streaming-active', active);
  if (!$stopBtn) return;
  $stopBtn.hidden = !active;
  $stopBtn.disabled = !active;
  const label = $stopBtn.querySelector('span');
  if (label) label.textContent = 'Stop';
}

function markAssistantStopped() {
  hideTypingIndicator();
  if (_currentAssistantEl) {
    const metaEl = document.createElement('div');
    metaEl.className = 'msg-meta';
    metaEl.innerHTML = '<span class="meta-pill">Stopped by user</span>';
    _currentAssistantEl.appendChild(metaEl);
    finalizeAssistant(null);
  }
  setStatus('Stopped', '');
}

async function stopMessage() {
  if (!isStreaming || !activeChatRunId || stopRequested) return;
  stopRequested = true;
  if ($stopBtn) {
    $stopBtn.disabled = true;
    const label = $stopBtn.querySelector('span');
    if (label) label.textContent = 'Stopping...';
  }

  try {
    await fetch('/chat/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_id: activeChatRunId }),
    });
  } catch (_) {
    // The local AbortController still stops rendering immediately. The
    // backend event is best-effort if the server disappears mid-turn.
  } finally {
    activeChatAbortController?.abort();
    markAssistantStopped();
    showToast('Generation stopped', 'success');
  }
}

async function sendMessage() {
  const text = $inp.value.trim();
  if (!text && !attachedFiles.length) return;
  if (isStreaming) return;

  hideEmptyState();
  addUserMessage(text);

  // ── Analytics: message_sent ──
  mpTrack('message_sent', {
    session_id: activeSessionId,
    char_count: text.length,
    has_files: attachedFiles.length > 0,
    file_count: attachedFiles.length,
    voice_input: isRecording,
  });

  // Update session
  const s = getActiveSession();
  if (s) {
    if (!s.messages) s.messages = [];
    s.messages.push({ role: 'user', content: text });
    if (s.title === 'Chat' || s.title === 'New Chat') {
      s.title = text.slice(0, 38) + (text.length > 38 ? '…' : '');
    }
    s.timestamp = Date.now();
    renderSessions();
  }

  $inp.value = '';
  resetTextareaHeight();
  clearFilePreview();
  activeChatRunId = (window.crypto && crypto.randomUUID)
    ? crypto.randomUUID()
    : `chat-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  activeChatAbortController = new AbortController();
  stopRequested = false;
  setStreamingControls(true);
  isStreaming = true;
  setStatus('Thinking…', 'thinking');
  showTypingIndicator();

  try {
    const resp = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, run_id: activeChatRunId }),
      signal: activeChatAbortController.signal,
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    hideTypingIndicator();
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        let d;
        try { d = JSON.parse(line.slice(6)); } catch (_) { continue; }
        handleStreamEvent(d);
      }
    }
  } catch (err) {
    if (stopRequested && err.name === 'AbortError') return;
    hideTypingIndicator();
    const errEl = document.createElement('div');
    errEl.className = 'msg assistant err';
    errEl.innerHTML = `<div class="msg-content">[network error] ${escapeHtml(err.message)}</div>`;
    $log.appendChild(errEl);
    scrollToBottom();
    setStatus('Error', 'error');
    showToast('Connection error: ' + err.message, 'error');
  } finally {
    isStreaming = false;
    setStreamingControls(false);
    activeChatAbortController = null;
    activeChatRunId = null;
    stopRequested = false;
    $inp.focus();
    // Persist session
    fetch('/api/sessions/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: activeSessionId }),
    }).catch(() => {});
  }
}

function handleStreamEvent(d) {
  switch (d.type) {
    case 'text':
      appendStreamText(d.text);
      break;
    case 'thinking':
      appendThinking(d.text);
      break;
    case 'tool_start':
      appendToolCall(d.name, d.inputs);
      // ── Analytics: tool_used ──
      mpTrack('tool_used', { tool_name: d.name, session_id: activeSessionId });
      break;
    case 'tool_end':
      updateToolCall(d.name, d.result, d.permitted);
      break;
    case 'permission':
      showPermissionBanner(d.id, d.description);
      break;
    case 'question':
      showQuestionBanner(d.id, d.question, d.options, d.allow_freetext);
      break;
    case 'turn_done':
      finalizeAssistant({ in: d.in, out: d.out, cache_read: d.cache_read, cache_write: d.cache_write });
      setStatus('Ready', '');
      syncMessages();
      break;
    case 'stopped':
      stopRequested = true;
      markAssistantStopped();
      break;
    case 'error':
      appendStreamText('\n[error] ' + (d.message || 'Unknown error'));
      setStatus('Error', 'error');
      break;
  }
}

// ============================================================
// TYPING INDICATOR
// ============================================================
function showTypingIndicator() {
  if ($typingIndicator) $typingIndicator.classList.add('visible');
  scrollToBottom();
}
function hideTypingIndicator() {
  if ($typingIndicator) $typingIndicator.classList.remove('visible');
}

// ============================================================
// INPUT HANDLING
// ============================================================
function initInput() {
  // Auto-resize textarea
  $inp.addEventListener('input', () => {
    $inp.style.height = 'auto';
    $inp.style.height = Math.min($inp.scrollHeight, 200) + 'px';
    updateCharCount();
  });

  $inp.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  $sendBtn.addEventListener('click', sendMessage);
  $stopBtn?.addEventListener('click', stopMessage);

  // Growing/re-rendering Markdown can move scrollTop by itself, so only an
  // explicit upward gesture disables follow mode.
  $log.addEventListener('wheel', (event) => {
    if (event.deltaY < 0) _followStreamingOutput = false;
  }, { passive: true });

  $log.addEventListener('touchstart', (event) => {
    _lastChatTouchY = event.touches[0]?.clientY ?? null;
  }, { passive: true });

  $log.addEventListener('touchmove', (event) => {
    const nextY = event.touches[0]?.clientY;
    if (_lastChatTouchY !== null && nextY > _lastChatTouchY + 3) {
      _followStreamingOutput = false;
    }
    _lastChatTouchY = nextY ?? null;
  }, { passive: true });

  // Reaching the bottom manually re-enables live following.
  $log.addEventListener('scroll', () => {
    if (isNearChatBottom()) _followStreamingOutput = true;
  }, { passive: true });

  if ($attachBtn) {
    $attachBtn.addEventListener('click', () => $fileInput?.click());
  }

  if ($fileInput) {
    $fileInput.addEventListener('change', e => {
      handleFiles(e.target.files);
      $fileInput.value = '';
    });
  }
}

function resetTextareaHeight() {
  $inp.style.height = '';
  updateCharCount();
}

function updateCharCount() {
  if (!$charCount) return;
  const len = $inp.value.length;
  $charCount.textContent = len > 0 ? `${len}` : '';
  $charCount.className = len > 4000 ? 'warn' : '';
}

// ============================================================
// FILE HANDLING
// ============================================================
function initDragDrop() {
  document.addEventListener('dragenter', e => {
    if (e.dataTransfer.types.includes('Files')) {
      $dropOverlay?.classList.add('active');
    }
  });
  document.addEventListener('dragleave', e => {
    if (!e.relatedTarget || e.relatedTarget === document.documentElement) {
      $dropOverlay?.classList.remove('active');
    }
  });
  document.addEventListener('dragover', e => e.preventDefault());
  document.addEventListener('drop', e => {
    e.preventDefault();
    $dropOverlay?.classList.remove('active');
    if (e.dataTransfer.files.length) {
      handleFiles(e.dataTransfer.files);
    }
  });
}

function handleFiles(fileList) {
  Array.from(fileList).forEach(file => {
    if (attachedFiles.some(f => f.name === file.name)) return;
    attachedFiles.push(file);
  });
  renderFilePreview();
}

function renderFilePreview() {
  if (!$filePreview) return;
  $filePreview.innerHTML = '';
  attachedFiles.forEach((f, i) => {
    const chip = document.createElement('div');
    chip.className = 'file-chip';
    chip.innerHTML = `
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      <span>${escapeHtml(f.name)}</span>
      <button class="file-chip-remove" onclick="removeFile(${i})" aria-label="Remove ${escapeHtml(f.name)}">×</button>`;
    $filePreview.appendChild(chip);
  });
}

function removeFile(idx) {
  attachedFiles.splice(idx, 1);
  renderFilePreview();
}

function clearFilePreview() {
  attachedFiles = [];
  if ($filePreview) $filePreview.innerHTML = '';
}

// ============================================================
// VOICE INPUT
// ============================================================
function initVoice() {
  if (!$voiceBtn) return;
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    $voiceBtn.style.display = 'none';
    return;
  }
  $voiceBtn.addEventListener('click', toggleVoice);
}

function toggleVoice() {
  if (isRecording) {
    recognition?.stop();
    isRecording = false;
    $voiceBtn?.classList.remove('recording');
    $voiceBtn.title = 'Start voice input';
    return;
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = navigator.language || 'en-US';

  const originalValue = $inp.value;
  let interimText = '';

  recognition.onresult = e => {
    interimText = '';
    let final = '';
    for (const result of e.results) {
      if (result.isFinal) final += result[0].transcript;
      else interimText += result[0].transcript;
    }
    $inp.value = originalValue + final + interimText;
    $inp.style.height = 'auto';
    $inp.style.height = Math.min($inp.scrollHeight, 200) + 'px';
  };

  recognition.onend = () => {
    isRecording = false;
    $voiceBtn?.classList.remove('recording');
    $voiceBtn.title = 'Start voice input';
    $inp.value = $inp.value.trimEnd();
  };

  recognition.onerror = e => {
    showToast('Voice error: ' + e.error, 'error');
    isRecording = false;
    $voiceBtn?.classList.remove('recording');
  };

  recognition.start();
  isRecording = true;
  $voiceBtn?.classList.add('recording');
  $voiceBtn.title = 'Stop recording';
  mpTrack('voice_used', { session_id: activeSessionId });
  showToast('Listening…', 'info', 2000);
}

// ============================================================
// EXPORT
// ============================================================
function openExportModal() {
  if ($exportModal) $exportModal.classList.add('open');
}

function closeExportModal() {
  if ($exportModal) $exportModal.classList.remove('open');
  $exportModal?.addEventListener('click', e => {
    if (e.target === $exportModal) closeExportModal();
  });
}

function exportAsMarkdown() {
  const s = getActiveSession();
  if (!s || !s.messages?.length) { showToast('No messages to export', 'warning'); return; }
  let md = `# ${s.title}\n\n_Exported from Dulus WebChat — ${new Date().toLocaleString()}_\n\n---\n\n`;
  s.messages.forEach(m => {
    if (m.role === 'user') md += `**You:** ${m.content}\n\n`;
    else if (m.role === 'assistant') {
      const text = typeof m.content === 'string' ? m.content :
        (Array.isArray(m.content) ? (m.content.find(c => c.type === 'text') || {}).text || '' : '');
      md += `**Dulus:** ${text}\n\n`;
    }
  });
  downloadText(md, `${s.title || 'chat'}.md`, 'text/markdown');
  mpTrack('export_done', { format: 'markdown', session_id: activeSessionId });
  closeExportModal();
  showToast('Exported as Markdown', 'success');
}

function exportAsJSON() {
  const s = getActiveSession();
  if (!s) return;
  const data = JSON.stringify({ session: s, exported_at: new Date().toISOString() }, null, 2);
  downloadText(data, `${s.title || 'chat'}.json`, 'application/json');
  mpTrack('export_done', { format: 'json', session_id: activeSessionId });
  closeExportModal();
  showToast('Exported as JSON', 'success');
}

function exportAsPDF() {
  mpTrack('export_done', { format: 'pdf', session_id: activeSessionId });
  closeExportModal();
  window.print();
}

function downloadText(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url  = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ============================================================
// KEYBOARD SHORTCUTS + COMMAND PALETTE
// ============================================================
function buildCmdItems() {
  cmdItems = [
    { group: 'Chat', name: 'New Chat',          desc: 'Start a fresh conversation', key: 'Ctrl+Shift+N', icon: '+',   action: newChat },
    { group: 'Chat', name: 'Clear Chat',        desc: 'Clear current messages',    key: 'Ctrl+L',       icon: '⌫',  action: clearChat },
    { group: 'Chat', name: 'Focus Input',       desc: 'Jump to message input',     key: 'Ctrl+/',       icon: '✎',  action: () => $inp?.focus() },
    { group: 'View', name: 'Toggle Sidebar',    desc: 'Collapse or expand sidebar',key: 'Ctrl+B',       icon: '⊞',  action: toggleSidebar },
    { group: 'View', name: 'Toggle Theme',      desc: 'Cycle dark/light/system',   key: 'Ctrl+T',       icon: '◑',  action: cycleTheme },
    { group: 'Chat', name: 'Export Chat',       desc: 'Download chat transcript',  key: 'Ctrl+E',       icon: '⬇', action: openExportModal },
    { group: 'Chat', name: 'Voice Input',       desc: 'Start voice recording',     key: 'Ctrl+M',       icon: '🎙', action: toggleVoice },
    { group: 'Nav',  name: 'Go to Roundtable',  desc: 'Open Mesa Redonda',         key: '',             icon: '⬡',  action: () => window.location.href = '/roundtable' },
    { group: 'Nav',  name: 'Go to Dashboard',   desc: 'Open Task Manager',         key: '',             icon: '✔',  action: () => window.location.href = '/dashboard' },
    { group: 'Chat', name: 'Refresh Sessions',  desc: 'Reload chat history',       key: 'Ctrl+R',       icon: '↻',  action: refreshSessions },
  ];
}

function initKeyboardShortcuts() {
  document.addEventListener('keydown', e => {
    // Ctrl+K or Cmd+K — command palette
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      toggleCmdPalette();
      return;
    }
    // Escape — close modals
    if (e.key === 'Escape') {
      closeCmdPalette();
      closeExportModal();
      hideCtx();
      return;
    }
    // Skip shortcuts when typing in inputs (except designated combos)
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'N') { e.preventDefault(); newChat(); }
    if ((e.ctrlKey || e.metaKey) && e.key === 'b') { e.preventDefault(); toggleSidebar(); }
    if ((e.ctrlKey || e.metaKey) && e.key === 'l') { e.preventDefault(); clearChat(); }
    if ((e.ctrlKey || e.metaKey) && e.key === 'e') { e.preventDefault(); openExportModal(); }
    if ((e.ctrlKey || e.metaKey) && e.key === '/') { e.preventDefault(); $inp?.focus(); }
    if ((e.ctrlKey || e.metaKey) && e.key === 't') { e.preventDefault(); cycleTheme(); }
    if ((e.ctrlKey || e.metaKey) && e.key === 'm') { e.preventDefault(); toggleVoice(); }
  });

  // Command palette navigation
  document.addEventListener('keydown', e => {
    if ($cmdPalette?.classList.contains('open')) {
      if (e.key === 'ArrowDown') { e.preventDefault(); moveCmdIdx(1); }
      if (e.key === 'ArrowUp')   { e.preventDefault(); moveCmdIdx(-1); }
      if (e.key === 'Enter')     { e.preventDefault(); activateCmd(); }
    }
  });
}

function toggleCmdPalette() {
  if ($cmdPalette?.classList.contains('open')) closeCmdPalette();
  else openCmdPalette();
}

function openCmdPalette() {
  $cmdPalette?.classList.add('open');
  $cmdSearch?.focus();
  renderCmdList('');
  cmdActiveIdx = -1;
}

function closeCmdPalette() {
  $cmdPalette?.classList.remove('open');
  if ($cmdSearch) $cmdSearch.value = '';
}

$cmdPalette?.addEventListener('click', e => {
  if (e.target === $cmdPalette) closeCmdPalette();
});

function onCmdSearch(q) {
  renderCmdList(q.toLowerCase());
  cmdActiveIdx = -1;
}

function renderCmdList(q) {
  if (!$cmdList) return;
  const filtered = q ? cmdItems.filter(c => c.name.toLowerCase().includes(q) || c.desc.toLowerCase().includes(q)) : cmdItems;
  if (!filtered.length) {
    $cmdList.innerHTML = '<div style="padding:20px;text-align:center;color:var(--dim);font-size:12px">No commands found</div>';
    return;
  }
  const groups = {};
  filtered.forEach(c => { if (!groups[c.group]) groups[c.group] = []; groups[c.group].push(c); });
  let html = '';
  Object.entries(groups).forEach(([group, items]) => {
    html += `<div class="cmd-group-label">${group}</div>`;
    items.forEach((c, i) => {
      const kbds = c.key ? c.key.split('+').map(k => `<span class="kbd">${k}</span>`).join('') : '';
      html += `<div class="cmd-item" onclick="runCmd('${c.name}')" data-idx="${i}" role="menuitem" tabindex="-1">
        <div class="cmd-item-icon" aria-hidden="true">${c.icon}</div>
        <div class="cmd-item-text">
          <div class="cmd-item-name">${escapeHtml(c.name)}</div>
          <div class="cmd-item-desc">${escapeHtml(c.desc)}</div>
        </div>
        <div class="cmd-item-kbd">${kbds}</div>
      </div>`;
    });
  });
  $cmdList.innerHTML = html;
}

function moveCmdIdx(delta) {
  const items = $cmdList?.querySelectorAll('.cmd-item');
  if (!items?.length) return;
  if (cmdActiveIdx >= 0) items[cmdActiveIdx]?.classList.remove('active');
  cmdActiveIdx = Math.max(0, Math.min(items.length - 1, cmdActiveIdx + delta));
  items[cmdActiveIdx]?.classList.add('active');
  items[cmdActiveIdx]?.scrollIntoView({ block: 'nearest' });
}

function activateCmd() {
  const items = $cmdList?.querySelectorAll('.cmd-item');
  if (cmdActiveIdx >= 0 && items?.[cmdActiveIdx]) {
    items[cmdActiveIdx].click();
  }
}

function runCmd(name) {
  const cmd = cmdItems.find(c => c.name === name);
  if (cmd) { cmd.action(); closeCmdPalette(); }
}

// ============================================================
// CLEAR CHAT
// ============================================================
async function clearChat() {
  await fetch('/clear', { method: 'POST' });
  clearLog();
  const s = getActiveSession();
  if (s) { s.messages = []; s.timestamp = Date.now(); }
  showEmptyState();
  showToast('Chat cleared', 'info');
}

// ============================================================
// SERVER SYNC
// ============================================================
async function syncWithServer() {
  if (isStreaming) return;
  try {
    const [histRes, personaRes] = await Promise.allSettled([
      fetch('/api/chat/history'),
      fetch('/api/personas'),
    ]);

    if (histRes.status === 'fulfilled' && histRes.value.ok) {
      const data = await histRes.value.json();
      syncMessages(data.messages);
    }

    if (personaRes.status === 'fulfilled' && personaRes.value.ok) {
      const data = await personaRes.value.json();
      updatePersonaSelect(data);
    }
  } catch (_) {}
}

function syncMessages(serverMsgs) {
  if (!serverMsgs) return;
  const s = getActiveSession();
  if (!s) return;
  const localCount = s.messages?.length || 0;
  if (serverMsgs.length > localCount) {
    s.messages = serverMsgs;
    s.timestamp = Date.now();
    if (s.title === 'Chat' || s.title === 'New Chat') {
      const firstUser = serverMsgs.find(m => m.role === 'user');
      if (firstUser?.content) {
        const text = typeof firstUser.content === 'string' ? firstUser.content : '';
        if (text) s.title = text.slice(0, 38) + (text.length > 38 ? '…' : '');
      }
    }
    renderSessions();
  }
}

function updatePersonaSelect(data) {
  if (!$personaSelect || !data?.personas) return;
  const active = Object.keys(data.active || {});
  $personaSelect.innerHTML = data.personas.map(p =>
    `<option value="${escapeHtml(p.name)}" ${active.includes(p.name) ? 'selected' : ''}>${escapeHtml(p.name)} (${escapeHtml(p.role)})</option>`
  ).join('');
  $personaSelect.onchange = async e => {
    await fetch('/api/personas/activate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: e.target.value }),
    });
    showToast(`Persona: ${e.target.value}`, 'info');
  };
}

// ============================================================
// EMPTY STATE QUICK PROMPTS
// ============================================================
function sendPrompt(text) {
  if ($inp) { $inp.value = text; $inp.focus(); }
}

// ============================================================
// EXPOSE GLOBALS (called from HTML onclick)
// ============================================================
window.toggleSidebar    = toggleSidebar;
window.newChat          = newChat;
window.refreshSessions  = refreshSessions;
window.clearChat        = clearChat;
window.filterSessions   = filterSessions;
window.selectSession    = selectSession;
window.startRename      = startRename;
window.finishRename     = finishRename;
window.renameKey        = renameKey;
window.deleteSession    = deleteSession;
window.showCtx          = showCtx;
window.ctxRename        = ctxRename;
window.ctxDelete        = ctxDelete;
window.sendMessage      = sendMessage;
window.grantPermission  = grantPermission;
window.copyCode         = copyCode;
window.openExportModal  = openExportModal;
window.closeExportModal = closeExportModal;
window.exportAsMarkdown = exportAsMarkdown;
window.exportAsJSON     = exportAsJSON;
window.exportAsPDF      = exportAsPDF;
window.onCmdSearch      = onCmdSearch;
window.runCmd           = runCmd;
window.sendPrompt       = sendPrompt;
window.toggleVoice      = toggleVoice;
window.cycleTheme       = cycleTheme;
window.removeFile       = removeFile;
