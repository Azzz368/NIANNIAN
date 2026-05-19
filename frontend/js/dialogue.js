// frontend/js/dialogue.js — 数字人对话（前后端打通）
const { apiGet, apiPost, apiUpload, getSessionId, setSessionId, toast, esc } = window.NN;

const NS = 'niannian.dlg.';
const getDlgSid = () => localStorage.getItem(NS + 'sid') || '';
const setDlgSid = (sid) => { if (sid) localStorage.setItem(NS + 'sid', sid); };
const clearDlgSid = () => localStorage.removeItem(NS + 'sid');

const state = {
  sid: '',
  dna: null,
  name: '',
  override: '',
  msgCount: 0,
  history: [],
};

// ───── 视图切换 ─────
function showStepUpload() {
  document.getElementById('stepUpload').classList.remove('hidden');
  document.getElementById('stepChat').classList.add('hidden');
}
function showStepChat() {
  document.getElementById('stepUpload').classList.add('hidden');
  document.getElementById('stepChat').classList.remove('hidden');
  renderPersonaCard();
  renderDnaPanel();
  renderOverride();
  renderChat();
  if (state.history.length === 0) {
    const greeting = makeOpening();
    state.history.push({ role: 'assistant', content: greeting });
    renderChat();
  }
}

function makeOpening() {
  const phrases = (state.dna && state.dna.speech_patterns) || [];
  const first = phrases[0] || '';
  return `你来啦～${first ? first + '，' : ''}最近怎么样？`;
}

// ───── 顶部人物名片 ─────
function renderPersonaCard() {
  const dna = state.dna || {};
  const tone = dna.tone || '';
  const humor = dna.humor_level != null ? dna.humor_level : '';
  const style = dna.response_style || '';
  const patterns = (dna.speech_patterns || []).slice(0, 5);
  const tags = patterns.map(p => `<span class="persona-tag">${esc(p)}</span>`).join('');
  const initial = (state.name || '念').slice(0, 1);
  document.getElementById('personaCard').innerHTML = `
    <div class="persona-avatar">${esc(initial)}</div>
    <div style="flex:1;">
      <div class="persona-name">${esc(state.name || 'TA')}</div>
      <div class="persona-meta">${esc(tone)} · 幽默 ${esc(String(humor))}/5 · ${esc(style)}</div>
      <div style="margin-top:5px;">${tags}</div>
    </div>`;
}

// ───── 左栏：DNA 详情 ─────
function renderDnaPanel() {
  const dna = state.dna || {};
  const el = document.getElementById('dnaPanel');
  const metrics = [
    ['情感基调', dna.tone],
    ['幽默程度', dna.humor_level != null ? `${dna.humor_level} / 5` : ''],
    ['句子风格', dna.avg_sentence_length],
    ['回应风格', dna.response_style],
    ['分析置信度', dna.confidence],
    ['消息条数', state.msgCount],
  ];
  let html = metrics
    .filter(([_, v]) => v !== undefined && v !== '' && v !== null)
    .map(([k, v]) => `<div class="dna-metric"><span>${k}</span><span>${esc(String(v))}</span></div>`)
    .join('');
  const phrases = dna.signature_phrases || [];
  if (phrases.length) {
    html += `<div style="margin-top:10px;font-size:.74rem;color:var(--muted-l);">标志性句式</div>`;
    html += phrases.slice(0, 3).map(p => `<div class="phrase-box">「${esc(p)}」</div>`).join('');
  }
  el.innerHTML = html || '<div class="text-muted">暂无分析结果</div>';
}

// ───── 人设编辑器 ─────
function renderOverride() {
  const status = document.getElementById('personaStatus');
  const wrap = document.getElementById('overrideWrap');
  if (state.override && state.override.trim()) {
    status.innerHTML = `<span class="persona-status status-active">人设已生效</span>`;
    document.getElementById('currentOverride').textContent = state.override;
    wrap.classList.remove('hidden');
  } else {
    status.innerHTML = `<span class="persona-status status-default">使用默认 DNA</span>`;
    wrap.classList.add('hidden');
  }
}

// ───── 对话渲染 ─────
function renderChat() {
  const wrap = document.getElementById('dlgChatWrap');
  wrap.innerHTML = '';
  const initial = (state.name || '念').slice(0, 1);
  state.history.forEach(m => {
    if (m.role === 'assistant') {
      wrap.insertAdjacentHTML('beforeend', `
        <div class="chat-ai">
          <div class="ai-avatar">${esc(initial)}</div>
          <div class="ai-bubble-wrap">
            <div class="ai-name">${esc(state.name || 'TA')}</div>
            <div class="ai-bubble">${esc(m.content)}</div>
          </div>
        </div>`);
    } else {
      wrap.insertAdjacentHTML('beforeend', `
        <div class="user-bubble"><div class="user-bubble-inner">${esc(m.content)}</div></div>`);
    }
  });
  wrap.scrollIntoView({ block: 'end', behavior: 'smooth' });
}

function setThinking(on, label) {
  document.getElementById('dlgThink').classList.toggle('hidden', !on);
  if (label) document.getElementById('dlgThinkLabel').textContent = label;
}

// ───── API 调用 ─────
async function doAnalyze() {
  const file = document.getElementById('dlgFile').files[0];
  const name = document.getElementById('dlgName').value.trim();
  const role = document.getElementById('dlgRoleExtra').value.trim();
  if (!file) { toast('请先选择聊天记录文件'); return; }

  document.getElementById('analyzingPanel').classList.remove('hidden');
  document.getElementById('btnAnalyze').disabled = true;

  try {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('target_name', name);
    fd.append('role_desc', role);
    fd.append('session_id', state.sid || '');
    const res = await apiUpload('/dialogue/analyze', fd);
    if (res.error) {
      toast(res.message || '分析失败');
      return;
    }
    state.sid = res.session_id;
    setDlgSid(state.sid);
    state.dna = res.persona_dna;
    state.name = res.persona_name;
    state.msgCount = res.message_count;
    state.override = '';
    state.history = [];
    showStepChat();
    toast('风格档案已生成');
  } catch (e) {
    toast('分析失败：' + e.message);
  } finally {
    document.getElementById('analyzingPanel').classList.add('hidden');
    document.getElementById('btnAnalyze').disabled = false;
  }
}

async function doPersonaUpdate() {
  const inp = document.getElementById('personaInput');
  const text = inp.value.trim();
  if (!text) { toast('请输入新增/修改内容'); return; }
  document.getElementById('btnPersonaUpdate').disabled = true;
  try {
    const res = await apiPost('/dialogue/persona/update', {
      session_id: state.sid, new_input: text,
    });
    state.override = res.persona_override;
    inp.value = '';
    renderOverride();
    toast('人设已更新，下一句生效');
  } catch (e) {
    toast('更新失败：' + e.message);
  } finally {
    document.getElementById('btnPersonaUpdate').disabled = false;
  }
}

async function doPersonaClear() {
  if (!confirm('确定清空人设，恢复原始 DNA？')) return;
  try {
    await apiPost('/dialogue/persona/update', { session_id: state.sid, clear: true });
    state.override = '';
    renderOverride();
    toast('已恢复默认人设');
  } catch (e) { toast('清空失败：' + e.message); }
}

async function doSend() {
  const inp = document.getElementById('dlgInput');
  const msg = inp.value.trim();
  if (!msg) return;
  inp.value = '';
  state.history.push({ role: 'user', content: msg });
  renderChat();
  setThinking(true, `${state.name || 'TA'} 正在回复...`);
  try {
    const res = await apiPost('/dialogue/chat', { session_id: state.sid, message: msg });
    state.history = res.history;
    renderChat();
  } catch (e) {
    toast('发送失败：' + e.message);
  } finally {
    setThinking(false);
  }
}

async function doClearHist() {
  if (!confirm('确定清空当前对话？')) return;
  try {
    await apiPost('/dialogue/reset', { session_id: state.sid, clear_persona: false });
    state.history = [];
    const greeting = makeOpening();
    state.history.push({ role: 'assistant', content: greeting });
    renderChat();
  } catch (e) { toast('清空失败：' + e.message); }
}

function doReupload() {
  if (!confirm('重新上传将清空当前风格档案与对话，确定继续？')) return;
  clearDlgSid();
  state.sid = ''; state.dna = null; state.name = '';
  state.override = ''; state.msgCount = 0; state.history = [];
  showStepUpload();
  document.getElementById('dlgFile').value = '';
  document.getElementById('filePicked').textContent = '';
}

// ───── 启动：尝试恢复 ─────
async function bootstrap() {
  const sid = getDlgSid();
  if (!sid) return;
  try {
    const res = await apiGet(`/dialogue/state/${sid}`);
    if (res && res.persona_dna) {
      state.sid = sid;
      state.dna = res.persona_dna;
      state.name = res.persona_name || 'TA';
      state.override = res.persona_override || '';
      state.msgCount = res.message_count || 0;
      state.history = res.history || [];
      showStepChat();
    }
  } catch { /* session 过期则忽略 */ }
}

document.addEventListener('DOMContentLoaded', () => {
  bootstrap();
  document.getElementById('btnAnalyze').onclick = doAnalyze;
  document.getElementById('btnPersonaUpdate').onclick = doPersonaUpdate;
  document.getElementById('btnPersonaClear').onclick = doPersonaClear;
  document.getElementById('btnDlgSend').onclick = doSend;
  document.getElementById('btnDlgClearHist').onclick = doClearHist;
  document.getElementById('btnDlgReupload').onclick = doReupload;
  document.getElementById('dlgInput').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doSend(); }
  });
  document.getElementById('dlgFile').addEventListener('change', e => {
    const f = e.target.files[0];
    document.getElementById('filePicked').textContent =
      f ? `已选择：${f.name}（${(f.size / 1024).toFixed(1)} KB）` : '';
  });
});
