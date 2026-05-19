// frontend/js/api.js — 统一 API 调用封装（IIFE 隔离，避免污染全局）
(function () {
  const API_BASE = (() => {
    // 生产（Render/任意域名）：直接用同源 /api
    // 本地开发 file:// 协议：指向本地 8000
    if (window.location.protocol === 'file:') return 'http://localhost:8000/api';
    return `${window.location.origin}/api`;
  })();

  async function apiGet(path) {
    const res = await fetch(`${API_BASE}${path}`);
    if (!res.ok) throw new Error(`GET ${path} → ${res.status} ${await res.text()}`);
    return res.json();
  }

  async function apiPost(path, body) {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) throw new Error(`POST ${path} → ${res.status} ${await res.text()}`);
    return res.json();
  }

  async function apiUpload(path, formData) {
    const res = await fetch(`${API_BASE}${path}`, { method: 'POST', body: formData });
    if (!res.ok) throw new Error(`UPLOAD ${path} → ${res.status} ${await res.text()}`);
    return res.json();
  }

  const NS = 'niannian.';
  function getSessionId() { return localStorage.getItem(NS + 'session_id') || ''; }
  function setSessionId(sid) { if (sid) localStorage.setItem(NS + 'session_id', sid); }
  function clearSession() { localStorage.removeItem(NS + 'session_id'); }

  function toast(msg, ms = 2400) {
    let t = document.querySelector('.toast');
    if (!t) { t = document.createElement('div'); t.className = 'toast'; document.body.appendChild(t); }
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(t._h);
    t._h = setTimeout(() => t.classList.remove('show'), ms);
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  window.NN = { apiGet, apiPost, apiUpload, getSessionId, setSessionId, clearSession, toast, esc, API_BASE };
})();
