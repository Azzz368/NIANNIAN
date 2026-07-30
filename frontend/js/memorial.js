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

const CHAT_CONTEXT_FIELDS = [
  'deceased_name', 'deceased_gender', 'birth_date', 'death_date', 'occupation',
  'family_memory_text', 'last_wishes', 'speaker_name', 'speaker_relation', 'speaker_style',
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

function hasChatContextChanged(previous, current) {
  return CHAT_CONTEXT_FIELDS.some(key =>
    String(previous[key] ?? '') !== String(current[key] ?? '')
  );
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
  const resetChat = state.chatHistory.length > 0 && hasChatContextChanged(state.form, f);
  state.form = { ...state.form, ...f };
  try {
    const res = await apiPost('/intake/submit', {
      session_id: getSessionId() || null,
      form_data: state.form,
      reset_chat: resetChat,
    });
    setSessionId(res.session_id);
    state.form = res.form_data;
    if (resetChat) state.chatHistory = [];
    showStep(2);
  } catch (e) { toast('保存失败：' + e.message); }
}

async function gotoStep3() {
  const f = readForm();
  if (!f.family_memory_text || f.family_memory_text.length < 20) {
    toast('请填写家庭回忆与生平故事（至少 20 字）'); return;
  }
  const resetChat = state.chatHistory.length > 0 && hasChatContextChanged(state.form, f);
  state.form = { ...state.form, ...f };
  try {
    const res = await apiPost('/intake/submit', {
      session_id: getSessionId(),
      form_data: state.form,
      reset_chat: resetChat,
    });
    setSessionId(res.session_id);
    state.form = res.form_data;
    if (resetChat) state.chatHistory = [];
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
  // 先渲染已有历史（防止从 step1/2 返回后空白）
  renderChat();
  if (state.chatHistory.length > 0) return;
  setThinking(true);
  try {
    const res = await apiPost('/chat/greeting', { session_id: getSessionId() });
    const history = res.chat_history || [];
    // 如果返回内容为空，补充默认开场白
    if (!history.length || !history[0].content) {
      state.chatHistory = [{ role: 'assistant', content: '你好，我是念念。很高兴能和你一起记录这一段珍贵的记忆。请告诉我，关于这位拆散的亲人，你最想让我知道的是什么？' }];
    } else {
      state.chatHistory = history;
    }
    renderChat();
  } catch (e) {
    toast('开场白加载失败，展示默认开场');
    // API 失败时展示默认开场，不让用户看到空白屏
    state.chatHistory = [{ role: 'assistant', content: '你好，我是念念。很高兴能和你一起记录这一段珍贵的记忆。请告诉我，关于这位珍贵的亲人，你最想让我知道的是什么？' }];
    renderChat();
  }
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
  const mid = state.form.memorial_id || (window.NianAuth && NianAuth.getActiveMemorialId()) || '';
  window.location.href = mid ? `pipeline.html?mid=${encodeURIComponent(mid)}` : 'pipeline.html';
}

// ───── 文件上传 ─────
function getActiveMemorialId() {
  return window.NianAuth && NianAuth.isAuthed() ? NianAuth.getActiveMemorialId() : '';
}

function attachLibraryIdentity() {
  if (!window.NianAuth || !NianAuth.isAuthed()) return;
  const user = NianAuth.getUser() || {};
  const memorialId = NianAuth.getActiveMemorialId() || '';
  if (user.user_id) state.form.user_id = user.user_id;
  if (memorialId) state.form.memorial_id = memorialId;
}

async function persistReferencePhoto(asset, memorialId = '') {
  state.form = {
    ...state.form,
    main_reference_asset_id: asset.asset_id || '',
    main_reference_photo_url: asset.url || '',
    memorial_id: memorialId || state.form.memorial_id || '',
  };
  const sid = getSessionId();
  if (!sid) return;
  const res = await apiPost('/intake/submit', { session_id: sid, form_data: state.form });
  state.form = res.form_data;
}

async function uploadToMemorialLibrary(mid, file) {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('description', '影视制作台上传的主角形象参考照片');
  const res = await NianAuth.fetch(`/api/memorials/${encodeURIComponent(mid)}/upload`, {
    method: 'POST', body: fd,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function handleUpload(files) {
  const sid = getSessionId();
  if (!sid) { toast('请先填写基本信息'); return; }
  const list = document.getElementById('uploadList');
  const memorialId = getActiveMemorialId();
  for (const f of files) {
    try {
      let asset;
      if (memorialId) {
        const res = await uploadToMemorialLibrary(memorialId, f);
        asset = res.asset;
      } else {
        const fd = new FormData();
        fd.append('session_id', sid);
        fd.append('period', 'default');
        fd.append('file', f);
        const res = await apiUpload('/assets/upload', fd);
        asset = res.asset;
      }

      // 最新上传的图片自动成为主角参考图；在分镜制作台仍可随时更换。
      if (f.type.startsWith('image/')) {
        await persistReferencePhoto(asset, memorialId);
      }
      if (f.type.startsWith('image/')) {
        const url = URL.createObjectURL(f);
        list.insertAdjacentHTML('beforeend', `<img class="upload-thumb" src="${url}" alt="">`);
      } else {
        list.insertAdjacentHTML('beforeend', `<div class="upload-thumb" style="display:flex;align-items:center;justify-content:center;background:var(--surf3);font-size:.7rem;color:var(--muted-l);">${esc(f.name.slice(0, 8))}</div>`);
      }
    } catch (e) { toast('上传失败：' + e.message); }
  }
  toast('上传完成，已设为主角参考图');
}

// ───── 启动时：尝试从已有 session 恢复 ─────
async function bootstrap() {
  renderSteps();
  attachLibraryIdentity();
  const sid = getSessionId();
  if (sid) {
    try {
      const res = await apiGet(`/intake/session/${sid}`);
      state.form = res.form_data || {};
      writeForm(state.form);
      state.chatHistory = res.chat_history || [];
    } catch { /* 过期则忽略 */ }
  }
  const memorialId = getActiveMemorialId();
  if (memorialId) state.form.memorial_id = memorialId;
  attachLibraryIdentity();
  // 从资料库预填：若有 active memorial，将 dossier 数据填入空字段
  await prefillFromLibrary();
}

async function prefillFromLibrary() {
  if (!window.NianAuth || !NianAuth.isAuthed()) return;
  const mid = NianAuth.getActiveMemorialId();
  if (!mid) return;
  try {
    const resp = await NianAuth.fetch(`/api/memorials/${encodeURIComponent(mid)}`);
    if (!resp.ok) return;
    const mdata = await resp.json();
    const subj = (mdata.dossier || {}).subject || {};
    const prefill = {
      deceased_name:   subj.name       || '',
      birth_date:      subj.birth      || '',
      death_date:      subj.passing    || '',
      occupation:      subj.occupation || '',
      deceased_gender: subj.gender     || '',
    };
    // 仅填入目前仍为空的字段，不覆盖用户已填内容
    FIELD_IDS.forEach(k => {
      const el = document.getElementById('f_' + k);
      if (el && !el.value && prefill[k]) el.value = prefill[k];
    });
    if (prefill.deceased_gender && !document.querySelector('input[name="gender"]:checked')) {
      const r = document.querySelector(`input[name="gender"][value="${prefill.deceased_gender}"]`);
      if (r) r.checked = true;
    }
    // 顶部提示条：告知用户数据来源
    const name = prefill.deceased_name || mdata.meta?.name || '';
    if (name) {
      const hint = document.getElementById('libPrefillHint');
      if (hint) { hint.textContent = `已从资料库「${name}」预填基础信息`; hint.style.display = 'block'; }
    }
  } catch(e) { /* 静默忽略，不影响正常填写 */ }
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
