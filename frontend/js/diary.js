const { apiUpload, toast, esc } = window.NN;

const STORAGE_KEY = 'niannian.diary.draft';
const PERSONA_STORAGE_KEY = 'niannian.diary.digital_persona';
const state = {
  images: [],
  generating: false,
  recording: false,
  mediaRecorder: null,
  audioStream: null,
  audioChunks: [],
  audioContext: null,
  sourceNode: null,
  processorNode: null,
  wavChunks: [],
  wavSampleRate: 16000,
  speechRecognition: null,
  speechText: '',
  speechInterim: '',
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

function normalizeList(value) {
  return Array.isArray(value) ? value.filter(Boolean) : [];
}

function renderPersonaItems(title, items, mapper) {
  const cleanItems = normalizeList(items).slice(0, 4);
  if (!cleanItems.length) return '';
  return `
    <div class="persona-section">
      <div class="persona-section-title">${esc(title)}</div>
      <div class="persona-chip-list">
        ${cleanItems.map(item => `<span class="persona-chip">${esc(mapper(item))}</span>`).join('')}
      </div>
    </div>
  `;
}

function savePersonaSnapshot(persona, diaryMeta) {
  if (!persona || persona.error) return;
  try {
    const history = JSON.parse(localStorage.getItem(PERSONA_STORAGE_KEY) || '[]');
    history.unshift({
      diary_id: diaryMeta.diary_id || '',
      title: diaryMeta.title || '',
      date: diaryMeta.date || '',
      created_at: new Date().toISOString(),
      persona,
    });
    localStorage.setItem(PERSONA_STORAGE_KEY, JSON.stringify(history.slice(0, 20)));
  } catch {
    localStorage.removeItem(PERSONA_STORAGE_KEY);
  }
}

function renderDigitalPersona(persona, diaryMeta = {}) {
  const card = $('digitalPersonaCard');
  if (!card) return;
  if (!persona || persona.error) {
    card.style.display = 'none';
    card.innerHTML = '';
    return;
  }

  const confidence = Number(persona.confidence || 0);
  const confidenceText = confidence > 0 ? `置信度 ${Math.round(confidence * 100)}%` : '本次提炼';
  const anchors = renderPersonaItems('记忆锚点', persona.memory_anchors, item => {
    const title = item.title || item.label || '未命名记忆';
    const importance = item.importance ? ` · ${item.importance}` : '';
    return `${title}${importance}`;
  });
  const questions = normalizeList(persona.next_questions).slice(0, 2)
    .map(question => `<p class="persona-question">· ${esc(question)}</p>`)
    .join('');

  card.innerHTML = `
    <div class="section-label">Digital Persona</div>
    <h3>数字人格提炼</h3>
    <p class="persona-summary">${esc(persona.summary || '这次日记已经沉淀为一条人格线索。')}</p>
    <div class="persona-chip-list">
      <span class="persona-chip">${esc(confidenceText)}</span>
      <span class="persona-chip">${esc(diaryMeta.date || formatToday())}</span>
    </div>
    ${renderPersonaItems('核心身份线索', persona.core_identity, item => item.label || item.description || '')}
    ${renderPersonaItems('生活语境', persona.life_context, item => item.label || item.description || '')}
    ${renderPersonaItems('情绪模式', persona.emotional_patterns, item => item.label || item.description || '')}
    ${renderPersonaItems('表达风格', persona.expression_style, item => item.label || item.description || '')}
    ${anchors}
    ${questions ? `<div class="persona-section"><div class="persona-section-title">下次可追问</div>${questions}</div>` : ''}
  `;
  card.style.display = 'block';
  savePersonaSnapshot(persona, diaryMeta);
}

function setVoiceStatus(text, active = false) {
  const el = $('diaryVoiceStatus');
  if (!el) return;
  el.textContent = text || '';
  el.classList.toggle('active', !!active);
}

function updateVoiceButton() {
  const btn = $('btnVoiceDiary');
  if (!btn) return;
  btn.disabled = state.generating;
  btn.textContent = state.recording ? '结束录音' : '语音输入';
  btn.classList.toggle('btn-primary', state.recording);
}

function setGenerating(next) {
  state.generating = next;
  const btn = $('btnGenerateDiary');
  if (!btn) return;
  btn.disabled = next;
  btn.textContent = next ? '正在生成...' : '生成日记 PDF';
  updateVoiceButton();
}

function appendDiaryText(text) {
  const clean = (text || '').trim();
  if (!clean) return;
  const textarea = $('diaryText');
  const current = textarea.value.trim();
  textarea.value = current ? `${current}\n${clean}` : clean;
  textarea.focus();
}

function encodeWav(chunks, sampleRate) {
  const sampleCount = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const buffer = new ArrayBuffer(44 + sampleCount * 2);
  const view = new DataView(buffer);
  let offset = 0;
  const writeString = value => {
    for (let i = 0; i < value.length; i += 1) {
      view.setUint8(offset + i, value.charCodeAt(i));
    }
    offset += value.length;
  };

  writeString('RIFF');
  view.setUint32(offset, 36 + sampleCount * 2, true); offset += 4;
  writeString('WAVE');
  writeString('fmt ');
  view.setUint32(offset, 16, true); offset += 4;
  view.setUint16(offset, 1, true); offset += 2;
  view.setUint16(offset, 1, true); offset += 2;
  view.setUint32(offset, sampleRate, true); offset += 4;
  view.setUint32(offset, sampleRate * 2, true); offset += 4;
  view.setUint16(offset, 2, true); offset += 2;
  view.setUint16(offset, 16, true); offset += 2;
  writeString('data');
  view.setUint32(offset, sampleCount * 2, true); offset += 4;

  chunks.forEach(chunk => {
    for (let i = 0; i < chunk.length; i += 1) {
      const sample = Math.max(-1, Math.min(1, chunk[i]));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      offset += 2;
    }
  });

  return new Blob([buffer], { type: 'audio/wav' });
}

function startLocalSpeechPreview() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return;
  try {
    const sr = new SR();
    sr.lang = 'zh-CN';
    sr.continuous = true;
    sr.interimResults = true;
    state.speechText = '';
    state.speechInterim = '';
    sr.onresult = event => {
      let finalText = '';
      let interimText = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const text = event.results[i][0].transcript || '';
        if (event.results[i].isFinal) finalText += text;
        else interimText += text;
      }
      if (finalText) state.speechText += finalText;
      state.speechInterim = interimText;
      const preview = (state.speechText + state.speechInterim).trim();
      if (preview) setVoiceStatus(`正在听：${preview}`, true);
    };
    sr.onerror = () => {};
    sr.onend = () => {};
    state.speechRecognition = sr;
    sr.start();
  } catch {
    state.speechRecognition = null;
  }
}

function stopLocalSpeechPreview() {
  if (!state.speechRecognition) return;
  try {
    state.speechRecognition.onend = null;
    state.speechRecognition.stop();
  } catch {}
  state.speechRecognition = null;
}

function getLocalSpeechText() {
  return `${state.speechText || ''}${state.speechInterim || ''}`.trim();
}

async function transcribeAudio(blob, ext) {
  const formData = new FormData();
  formData.append('audio', blob, `diary_voice.${ext || 'webm'}`);
  const resp = await fetch('/api/diary/transcribe', { method: 'POST', body: formData });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.detail || data.message || `语音识别失败：${resp.status}`);
  if (data.ok === false) throw new Error(data.detail || data.message || '语音识别失败');
  return (data.text || '').trim();
}

async function startVoiceInput() {
  if (state.generating || state.recording) return;
  if (!navigator.mediaDevices?.getUserMedia || !(window.AudioContext || window.webkitAudioContext)) {
    toast('当前浏览器不支持录音');
    setVoiceStatus('当前浏览器不支持录音，可以继续手动输入文字。');
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    const audioContext = new AudioContext();
    const sourceNode = audioContext.createMediaStreamSource(stream);
    const processorNode = audioContext.createScriptProcessor(4096, 1, 1);

    state.audioStream = stream;
    state.audioContext = audioContext;
    state.sourceNode = sourceNode;
    state.processorNode = processorNode;
    state.wavChunks = [];
    state.wavSampleRate = audioContext.sampleRate;
    state.recording = true;
    startLocalSpeechPreview();

    processorNode.onaudioprocess = event => {
      if (!state.recording) return;
      const channel = event.inputBuffer.getChannelData(0);
      state.wavChunks.push(new Float32Array(channel));
    };

    sourceNode.connect(processorNode);
    processorNode.connect(audioContext.destination);
    updateVoiceButton();
    setVoiceStatus('正在录音，再点一次结束并识别。', true);
  } catch (err) {
    state.recording = false;
    updateVoiceButton();
    setVoiceStatus('无法获取麦克风权限，请在浏览器中允许麦克风访问。');
    toast('无法获取麦克风权限');
  }
}

async function stopVoiceInput() {
  if (!state.recording) return;
  setVoiceStatus('录音结束，正在准备识别...', true);
  stopLocalSpeechPreview();
  state.recording = false;
  updateVoiceButton();

  try {
    state.processorNode?.disconnect();
    state.sourceNode?.disconnect();
  } catch {}
  state.audioStream?.getTracks().forEach(track => track.stop());
  try {
    await state.audioContext?.close();
  } catch {}

  const chunks = state.wavChunks.slice();
  const sampleRate = state.wavSampleRate || 16000;
  state.audioStream = null;
  state.audioContext = null;
  state.sourceNode = null;
  state.processorNode = null;
  state.wavChunks = [];

  if (!chunks.length) {
    setVoiceStatus('没有录到声音，可以再试一次。');
    return;
  }

  setVoiceStatus('正在识别语音...', true);
  try {
    const text = await transcribeAudio(encodeWav(chunks, sampleRate), 'wav');
    if (!text) {
      const localText = getLocalSpeechText();
      if (localText) {
        appendDiaryText(localText);
        setVoiceStatus('服务端识别为空，已使用浏览器本地识别结果。');
        toast('语音文字已加入日记');
        return;
      }
      setVoiceStatus('没有识别到文字，可以再说一次。');
      return;
    }
    appendDiaryText(text);
    setVoiceStatus('已把语音转成文字，并追加到日记内容中。');
    toast('语音文字已加入日记');
  } catch (err) {
    const localText = getLocalSpeechText();
    if (localText) {
      appendDiaryText(localText);
      setVoiceStatus('服务端语音识别失败，已使用浏览器本地识别结果。');
      toast('语音文字已加入日记');
    } else {
      setVoiceStatus(err.message || '语音识别失败');
      toast('语音识别失败');
    }
  }
}

function toggleVoiceInput() {
  if (state.recording) stopVoiceInput();
  else startVoiceInput();
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
  renderDigitalPersona(null);
  setVoiceStatus('可以直接输入文字，也可以说一段今天想记录的事。');
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
    renderDigitalPersona(result.digital_persona, {
      diary_id: result.diary_id,
      title: result.title,
      date: result.date,
    });
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
  $('btnVoiceDiary').addEventListener('click', toggleVoiceInput);
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
