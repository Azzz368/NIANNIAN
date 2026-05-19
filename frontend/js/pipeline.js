// frontend/js/pipeline.js — 前期确认台（pipeline）
const { apiGet, apiPost, getSessionId, toast, esc } = window.NN;

const state = {
  sid: getSessionId(),
  scenes: [],
};

// ───── 工具 ─────
function show(id) { document.getElementById(id).classList.remove('hidden'); }
function hide(id) { document.getElementById(id).classList.add('hidden'); }

function appendAiBubble(wrapId, text, name = '念念 AI') {
  const wrap = document.getElementById(wrapId);
  wrap.insertAdjacentHTML('beforeend', `
    <div class="chat-ai">
      <div class="ai-avatar">念</div>
      <div class="ai-bubble-wrap">
        <div class="ai-name">${esc(name)}</div>
        <div class="ai-bubble">${esc(text)}</div>
      </div>
    </div>`);
  wrap.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function setPipePill(step, status) {
  // status: '' | 'active' | 'done'
  const pill = document.querySelector(`.pipe-pill[data-step="${step}"]`);
  if (!pill) return;
  pill.classList.remove('active', 'done');
  if (status) pill.classList.add(status);
}

function setThink(thinkId, on, label) {
  const el = document.getElementById(thinkId);
  if (!el) return;
  el.classList.toggle('hidden', !on);
  if (on && label) {
    const lbl = el.querySelector('.think-label');
    if (lbl) lbl.textContent = label;
  }
}

// ───── 阶段 1：Preview 大白话 ─────
async function loadPreview() {
  setThink('previewThink', true);
  try {
    const res = await apiPost(`/pipeline/preview/${state.sid}`, {});
    appendAiBubble('previewChat', res.text || '让我们一起为这部影像做好准备吧。');
  } catch (e) {
    appendAiBubble('previewChat',
      '我们会先把您说的内容整理成结构化的故事大纲，然后AI核对，最后确定影像的整体氛围和主角形象。准备好就开始吧。');
    console.error(e);
  } finally {
    setThink('previewThink', false);
  }
}

// ───── 阶段 2：运行 MV01→MV02→MV03 ─────
async function runPipeline() {
  hide('phasePreview');
  show('phasePipeline');

  // 视觉上分别点亮 active
  setPipePill('MV01', 'active');
  setThink('pipelineThink', true, '念念正在整理访谈内容（约 30 秒）...');

  try {
    const res = await apiPost(`/pipeline/run-all/${state.sid}`, {});
    setThink('pipelineThink', false);

    if (!res.ok) {
      const errMsg = (res.errors || []).map(e => `[${e.step}] ${e.message}`).join('\n') || '未知错误';
      document.getElementById('errorOutput').textContent = errMsg;
      show('phaseError');
      return;
    }

    // 标记完成
    setPipePill('MV01', 'done');
    setPipePill('MV02', 'done');
    setPipePill('MV03', 'done');

    // 渲染两条气泡
    (res.bubbles || []).forEach(b => appendAiBubble('pipelineChat', b.content));

    // 显示完成区
    setTimeout(() => show('phaseDone'), 300);
  } catch (e) {
    setThink('pipelineThink', false);
    document.getElementById('errorOutput').textContent = e.message || String(e);
    show('phaseError');
  }
}

// ───── 启动 ─────
async function bootstrap() {
  if (!state.sid) {
    toast('会话不存在，请先完成 Step 1 表单');
    setTimeout(() => location.href = 'memorial.html', 1500);
    return;
  }
  // 校验 session
  try { await apiGet(`/intake/session/${state.sid}`); }
  catch {
    toast('会话已过期，请重新填写');
    setTimeout(() => location.href = 'memorial.html', 1500);
    return;
  }
  await loadPreview();
}

document.addEventListener('DOMContentLoaded', () => {
  bootstrap();
  document.getElementById('btnStartPipeline').onclick = runPipeline;
  document.getElementById('btnRetry').onclick = () => { hide('phaseError'); runPipeline(); };
});
