// frontend/js/memorial.js — 追思影像建档主流程
const { apiGet, apiPost, apiUpload, getSessionId, setSessionId, toast, esc } = window.NN;

// ───── 全局状态 ─────
const state = {
  step: 1,
  form: {},
  chatHistory: [],
};

// ───── 字段映射 ─────
const FIELD_IDS = [
  'deceased_name', 'birth_date', 'death_date', 'occupation',
  'ceremony_date', 'ceremony_venue', 'total_duration_sec',
  'family_memory_text', 'last_wishes',
  'speaker_name', 'speaker_relation', 'speaker_style',
];

function readForm() {
  const f = {};
  FIELD_IDS.forEach(k => {
    const el = document.getElementById('f_' + k);
    if (el) {
      let v = el.value.trim();
      if (k === 'total_duration_sec') v = parseInt(v, 10) || 300;
      f[k] = v;
    }
  });
  const g = document.querySelector('input[name="gender"]:checked');
  f.deceased_gender = g ? g.value : '男';
  return f;
}

function writeForm(data) {
  FIELD_IDS.forEach(k => {
    const el = document.getElementById('f_' + k);
    if (el && data[k] != null) el.value = data[k];
  });
  if (data.deceased_gender) {
    const r = document.querySelector(`input[name="gender"][value="${data.deceased_gender}"]`);
    if (r) r.checked = true;
  }
}

// ───── 步骤导航 ─────
function renderSteps() {
  const steps = [['1', '基本信息'], ['2', '回忆 & 风格'], ['*', '念念 AI 对话']];
  const row = document.getElementById('stepsRow');
  row.innerHTML = '';
  steps.forEach((s, i) => {
    if (i > 0) {
      const d = document.createElement('div'); d.className = 'step-divider'; row.appendChild(d);
    }
    const p = document.createElement('div');
    p.className = 'step-pill ' + (i + 1 === state.step ? 'active' : (i + 1 < state.step ? 'done' : ''));
    p.innerHTML = `<span class="step-num">${s[0]}</span><span>${s[1]}</span>`;
    row.appendChild(p);
  });
}

function showStep(n) {
  state.step = n;
  ['step1', 'step2', 'step3'].forEach((id, i) => {
    document.getElementById(id).classList.toggle('hidden', i + 1 !== n);
  });
  renderSteps();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ───── Step 转换 ─────
async function gotoStep2() {
  const f = readForm();
  if (!f.deceased_name) { toast('请先填写逝者姓名'); return; }
  state.form = { ...state.form, ...f };
  try {
    const res = await apiPost('/intake/submit', {
      session_id: getSessionId() || null,
      form_data: state.form,
    });
    setSessionId(res.session_id);
    state.form = res.form_data;
    showStep(2);
  } catch (e) { toast('保存失败：' + e.message); }
}

async function gotoStep3() {
  const f = readForm();
  if (!f.family_memory_text || f.family_memory_text.length < 20) {
    toast('请填写家庭回忆与生平故事（至少 20 字）'); return;
  }
  state.form = { ...state.form, ...f };
  try {
    const res = await apiPost('/intake/submit', {
      session_id: getSessionId(),
      form_data: state.form,
    });
    setSessionId(res.session_id);
    state.form = res.form_data;
    showStep(3);
    // 自动获取开场白
    await fetchGreeting();
  } catch (e) { toast('保存失败：' + e.message); }
}

// ───── 测试数据 ─────
async function fillTestData() {
  const btn = document.getElementById('btnFillTest');
  const oldText = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = '正在加载...'; }
  try {
    const res = await apiGet('/intake/test-data');
    state.form = res.form_data;
    writeForm(state.form);
    // 提交以创建/更新 session
    const r = await apiPost('/intake/submit', { session_id: getSessionId() || null, form_data: state.form });
    setSessionId(r.session_id);
    toast('测试数据已填入，进入第二步');
    // 自动跳至 Step 2
    showStep(2);
  } catch (e) {
    toast('加载测试数据失败：' + e.message);
    console.error(e);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = oldText; }
  }
}

// ───── Chat ─────
function renderChat() {
  const wrap = document.getElementById('chatWrap');
  wrap.innerHTML = '';
  state.chatHistory.forEach(m => {
    if (m.role === 'assistant') {
      wrap.insertAdjacentHTML('beforeend', `
        <div class="chat-ai">
          <div class="ai-avatar">念</div>
          <div class="ai-bubble-wrap">
            <div class="ai-name">念念 AI</div>
            <div class="ai-bubble">${esc(m.content)}</div>
          </div>
        </div>`);
    } else {
      wrap.insertAdjacentHTML('beforeend', `
        <div class="user-bubble"><div class="user-bubble-inner">${esc(m.content)}</div></div>`);
    }
  });
}

function setThinking(on) {
  document.getElementById('chatThink').classList.toggle('hidden', !on);
}

async function fetchGreeting() {
  if (state.chatHistory.length > 0) return;
  setThinking(true);
  try {
    const res = await apiPost('/chat/greeting', { session_id: getSessionId() });
    state.chatHistory = res.chat_history;
    renderChat();
  } catch (e) { toast('AI 开场失败：' + e.message); }
  finally { setThinking(false); }
}

async function sendChat() {
  const inp = document.getElementById('chatInput');
  const msg = inp.value.trim();
  if (!msg) return;
  inp.value = '';
  state.chatHistory.push({ role: 'user', content: msg });
  renderChat();
  setThinking(true);
  try {
    const res = await apiPost('/chat/message', {
      session_id: getSessionId(), message: msg,
    });
    state.chatHistory = res.chat_history;
    renderChat();
  } catch (e) { toast('发送失败：' + e.message); }
  finally { setThinking(false); }
}

// ───── Pipeline ─────
async function startProduce() {
  const sid = getSessionId();
  if (!sid) { toast('请先填写信息'); return; }
  if (state.chatHistory.length < 2) {
    if (!confirm('您还没有和念念充分对话，确定要直接开始制作吗？')) return;
  }
  // 跳转到前期确认台
  window.location.href = 'pipeline.html';
}

// ───── 文件上传 ─────
async function handleUpload(files) {
  const sid = getSessionId();
  if (!sid) { toast('请先填写基本信息'); return; }
  const list = document.getElementById('uploadList');
  for (const f of files) {
    const fd = new FormData();
    fd.append('session_id', sid);
    fd.append('period', 'default');
    fd.append('file', f);
    try {
      const res = await apiUpload('/assets/upload', fd);
      if (f.type.startsWith('image/')) {
        const url = URL.createObjectURL(f);
        list.insertAdjacentHTML('beforeend', `<img class="upload-thumb" src="${url}" alt="">`);
      } else {
        list.insertAdjacentHTML('beforeend', `<div class="upload-thumb" style="display:flex;align-items:center;justify-content:center;background:var(--surf3);font-size:.7rem;color:var(--muted-l);">${esc(f.name.slice(0, 8))}</div>`);
      }
    } catch (e) { toast('上传失败：' + e.message); }
  }
  toast('上传完成');
}

// ───── 启动时：尝试从已有 session 恢复 ─────
async function bootstrap() {
  renderSteps();
  const sid = getSessionId();
  if (sid) {
    try {
      const res = await apiGet(`/intake/session/${sid}`);
      state.form = res.form_data || {};
      writeForm(state.form);
      state.chatHistory = res.chat_history || [];
    } catch { /* 过期则忽略 */ }
  }
}

// ───── 事件绑定 ─────
document.addEventListener('DOMContentLoaded', () => {
  bootstrap();
  document.getElementById('btnFillTest').onclick = fillTestData;
  document.getElementById('btnToStep2').onclick = gotoStep2;
  document.getElementById('btnToStep3').onclick = gotoStep3;
  document.getElementById('btnBackTo1').onclick = () => showStep(1);
  document.getElementById('btnBackTo2').onclick = () => showStep(2);
  document.getElementById('btnSendChat').onclick = sendChat;
  document.getElementById('chatInput').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });
  document.getElementById('btnStartProduce').onclick = startProduce;
  document.getElementById('upload_input').onchange = e => handleUpload(e.target.files);
});
