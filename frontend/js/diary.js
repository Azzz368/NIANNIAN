const { apiUpload, toast, esc } = window.NN;

const STORAGE_KEY = 'niannian.diary.draft';
const state = {
  images: [],
  generating: false,
  deceasedName: '',   // 资料库中的纪念对象姓名
  mid: '',            // 当前 active memorial id
};

function formatToday() {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }).format(new Date());
}

function $(id) {
  return document.getElementById(id);
}

function renderDate() {
  const el = $('diaryDate');
  if (el) el.textContent = formatToday();
}

function ensureGenerateUi() {
  const actions = document.querySelector('.diary-actions');
  if (actions && !$('btnGenerateDiary')) {
    const btn = document.createElement('button');
    btn.className = 'btn btn-primary';
    btn.id = 'btnGenerateDiary';
    btn.type = 'button';
    btn.textContent = '生成日记 PDF';
    actions.appendChild(btn);
  }

  const card = document.querySelector('main .card');
  if (card && !$('diaryResult')) {
    const result = document.createElement('div');
    result.className = 'diary-note';
    result.id = 'diaryResult';
    result.style.display = 'none';
    result.style.marginTop = '16px';
    card.appendChild(result);
  }
}

function setResult(html) {
  const el = $('diaryResult');
  if (!el) return;
  el.innerHTML = html;
  el.style.display = html ? 'block' : 'none';
}

function setGenerating(next) {
  state.generating = next;
  const btn = $('btnGenerateDiary');
  if (!btn) return;
  btn.disabled = next;
  btn.textContent = next ? '正在生成...' : '生成日记 PDF';
}

function renderImagePreview() {
  const grid = $('diaryPreviewGrid');
  if (!grid) return;
  grid.innerHTML = '';
  state.images.forEach((item, index) => {
    grid.insertAdjacentHTML('beforeend', `
      <div class="diary-preview">
        <img src="${item.url}" alt="">
        <span>${esc(index + 1)}. ${esc(item.name)}</span>
      </div>
    `);
  });
}

function handleImages(files) {
  Array.from(files || []).forEach(file => {
    if (!file.type.startsWith('image/')) return;
    state.images.push({
      file,
      name: file.name,
      url: URL.createObjectURL(file),
    });
  });
  renderImagePreview();
}

function saveDraft() {
  const payload = {
    title: $('diaryTitle').value.trim(),
    text: $('diaryText').value.trim(),
    updated_at: new Date().toISOString(),
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  toast('日记草稿已保存');
}

function loadDraft() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const payload = JSON.parse(raw);
    $('diaryTitle').value = payload.title || '';
    $('diaryText').value = payload.text || '';
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function clearDraft() {
  $('diaryTitle').value = '';
  $('diaryText').value = '';
  localStorage.removeItem(STORAGE_KEY);
  state.images.forEach(item => URL.revokeObjectURL(item.url));
  state.images = [];
  const input = $('diaryImages');
  if (input) input.value = '';
  renderImagePreview();
  setResult('');
  toast('已清空');
}

function buildPdfUrl(pdfUrl) {
  if (!pdfUrl) return '';
  return new URL(pdfUrl, window.location.origin).toString();
}

async function generateDiary() {
  if (state.generating) return;

  const title = $('diaryTitle').value.trim();
  const text = $('diaryText').value.trim();
  if (!title && !text) {
    toast('请先输入标题或日记文字');
    return;
  }

  const formData = new FormData();
  formData.append('title', title || '今日记忆');
  formData.append('text', text);
  formData.append('tone', '温柔、真实、有生活感');
  if (state.deceasedName) formData.append('deceased_name', state.deceasedName);
  state.images.forEach(item => {
    formData.append('images', item.file, item.name);
  });

  setGenerating(true);
  setResult('正在调用日记生成 API，请稍等...');

  try {
    const result = await apiUpload('/diary/generate', formData);
    if (!result.ok) {
      const details = [
        result.stage ? `阶段：${esc(result.stage)}` : '',
        result.message ? `原因：${esc(result.message)}` : '',
        result.llm_error ? `模型错误：${esc(result.llm_error)}` : '',
        result.detail ? `详情：${esc(result.detail)}` : '',
      ].filter(Boolean).join('<br>');
      setResult(details || '生成失败，但后端没有返回具体原因。');
      toast(result.message || '生成失败');
      return;
    }

    const pdfUrl = buildPdfUrl(result.pdf_url);
    setResult(`
      <strong>${esc(result.title || '日记已生成')}</strong><br>
      ${esc(result.date || '')}<br>
      <a class="btn btn-primary" href="${esc(pdfUrl)}" target="_blank" download>下载 PDF</a>
    `);
    toast('日记 PDF 已生成');
  } catch (err) {
    setResult(`接口调用失败：${esc(err.message || err)}`);
    toast('接口调用失败');
  } finally {
    setGenerating(false);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  ensureGenerateUi();
  renderDate();
  loadDraft();
  loadFromLibrary();   // 从资料库加载 deceased_name
  $('diaryImages').addEventListener('change', e => handleImages(e.target.files));
  $('btnSaveDiary').addEventListener('click', saveDraft);
  $('btnClearDiary').addEventListener('click', clearDraft);
  $('btnGenerateDiary').addEventListener('click', generateDiary);
});

// 从资料库读取当前 active memorial 的 deceased_name，显示在页面并在生成时传给 API
async function loadFromLibrary() {
  if (!window.NianAuth || !NianAuth.isAuthed()) return;
  const mid = NianAuth.getActiveMemorialId();
  if (!mid) return;
  state.mid = mid;
  try {
    const resp = await NianAuth.fetch(`/api/memorials/${encodeURIComponent(mid)}`);
    if (!resp.ok) return;
    const mdata = await resp.json();
    const name = (mdata.dossier?.subject?.name) || mdata.meta?.name || '';
    if (!name) return;
    state.deceasedName = name;
    // 在页面顶部副标题处显示"为 Ta 写下今天"
    const sub = document.querySelector('.hero-sub');
    if (sub) sub.textContent = `为「${name}」写下今天的记录，让思念被温柔保存。`;
    const badge = document.querySelector('.topbar-badge');
    if (badge) badge.textContent = name;
  } catch(e) { /* 静默忽略 */ }
}
