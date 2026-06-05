// frontend/js/deep_search.js
const { apiPost, getSessionId, setSessionId, toast, esc } = window.NN;

const state = { chat: [], result: null, lastQuery: '' };

function renderChat() {
  const wrap = document.getElementById('dsChat');
  wrap.innerHTML = '';
  state.chat.forEach(m => {
    if (m.role === 'ai') {
      wrap.insertAdjacentHTML('beforeend', `
        <div class="chat-ai">
          <div class="ai-avatar">念</div>
          <div class="ai-bubble-wrap">
            <div class="ai-name">念念 AI · 深度搜索</div>
            <div class="ai-bubble">${esc(m.content)}</div>
          </div>
        </div>`);
    } else {
      wrap.insertAdjacentHTML('beforeend', `
        <div class="user-bubble"><div class="user-bubble-inner">${esc(m.content)}</div></div>`);
    }
  });
}

function setThinking(on, label) {
  document.getElementById('dsThink').classList.toggle('hidden', !on);
  if (label) document.getElementById('dsThinkLabel').textContent = label;
}

function renderPreview(fields, model) {
  const labels = {
    deceased_name: '姓名',
    deceased_gender: '性别',
    birth_date: '出生日期',
    death_date: '逝世日期',
    occupation: '职业 / 身份',
    family_memory_text: '人生故事（节选）',
  };
  let rows = '';
  Object.keys(labels).forEach(k => {
    const v = fields[k];
    if (v) {
      const disp = v.length > 80 ? v.slice(0, 80) + '...' : v;
      rows += `<div class="preview-row"><span class="preview-label">${labels[k]}</span><span class="preview-val">${esc(disp)}</span></div>`;
    }
  });
  const html = rows
    ? `<div class="preview-card"><div class="preview-card-title">AI 提取的表单信息预览</div>${rows}
       <div class="text-muted" style="margin-top:10px;text-align:right;font-size:.72rem;">使用模型：${esc(model)}</div></div>`
    : `<div class="text-muted text-center" style="margin:14px 0;">未能提取到结构化字段，可点击「重新搜索」或补充背景后重试。</div>`;
  const el = document.getElementById('dsPreview');
  el.innerHTML = html;
  el.classList.remove('hidden');
}

async function doSearch() {
  const q = document.getElementById('dsQuery').value.trim();
  const ex = document.getElementById('dsExtra').value.trim();
  if (!q) { toast('请先输入姓名'); return; }
  state.lastQuery = q;
  state.chat.push({ role: 'user', content: `请帮我搜索：${q}` });
  renderChat();
  setThinking(true, '正在联网搜索，请稍候（约 10-20 秒）...');
  document.getElementById('dsPreview').classList.add('hidden');
  document.getElementById('dsActions').classList.add('hidden');
  try {
    const sid = getSessionId() || null;
    const res = await apiPost('/intake/deep-search', { query: q, extra: ex, session_id: sid });
    setThinking(false);
    state.chat.push({ role: 'ai', content: res.organized });
    state.result = res;
    renderChat();
    renderPreview(res.fields || {}, res.model || '');
    document.getElementById('dsActions').classList.remove('hidden');
  } catch (e) {
    setThinking(false);
    toast('搜索失败：' + e.message);
  }
}

async function applyToForm() {
  if (!state.result || !state.result.fields) { toast('暂无可填入的数据'); return; }
  const fields = state.result.fields;
  let sid = getSessionId();
  const params = new URLSearchParams(window.location.search);
  const target = params.get('target') || 'memorial';
  const redirectTo = target === 'biography' ? 'biography.html' : 'memorial.html';
  const applyEndpoint = target === 'biography' ? '/intake/apply-fields' : '/intake/apply-fields';
  try {
    const payload = { fields, target };
    window.localStorage.setItem('NN_DEEP_SEARCH_FILL', JSON.stringify(payload));
    if (!sid) {
      const r = await apiPost('/intake/submit', { form_data: fields });
      sid = r.session_id;
      setSessionId(sid);
    } else {
      try {
        await apiPost(applyEndpoint, { session_id: sid, fields });
      } catch (e) {
        if (String(e.message || '').includes('404')) {
          const r = await apiPost('/intake/submit', { session_id: sid, form_data: fields });
          sid = r.session_id || sid;
          setSessionId(sid);
        } else {
          throw e;
        }
      }
    }
    toast('已填入表单，正在跳转...');
    setTimeout(() => { window.location.href = redirectTo; }, 700);
  } catch (e) {
    toast('填入表单失败：' + e.message);
  }
}

function reset() {
  state.chat = []; state.result = null;
  renderChat();
  document.getElementById('dsPreview').classList.add('hidden');
  document.getElementById('dsActions').classList.add('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('btnDsSearch').onclick = doSearch;
  document.getElementById('btnDsFill').onclick = applyToForm;
  document.getElementById('btnDsRetry').onclick = reset;
  document.getElementById('dsQuery').addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); doSearch(); }
  });
});
