// frontend/js/agent.js — 念念智能体聊天 · 语音输入 + Qwen音频输出
(function () {
  'use strict';

  // ─── 状态 ────────────────────────────────────────────────────────────────
  const state = {
    history: [],          // [{role, content}]
    isThinking: false,
    isRecording: false,
    mediaRecorder: null,
    recognition: null,    // SpeechRecognition
    voiceMode: false,     // 是否开启语音输出
    hasGreeted: false,
  };

  // ─── DOM 工具 ─────────────────────────────────────────────────────────────
  const $ = id => document.getElementById(id);

  // ─── 发送请求（SSE 流式）─────────────────────────────────────────────────
  async function sendMessage(text, voiceOut = false) {
    if (!text.trim() || state.isThinking) return;
    state.isThinking = true;
    setInputLock(true);

    appendBubble('user', text);
    state.history.push({ role: 'user', content: text });

    const thinkEl = showThinkBubble();
    let fullText = '';
    let aiEl = null;

    try {
      const resp = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history: state.history.slice(-30), voice_out: voiceOut }),
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

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
          if (!line.startsWith('data:')) continue;
          const raw = line.slice(5).trim();
          if (raw === '[DONE]') break;

          try {
            const evt = JSON.parse(raw);
            if (evt.type === 'text') {
              fullText += evt.delta;
              if (!aiEl) {
                thinkEl.remove();
                aiEl = appendBubble('ai', '');
              }
              aiEl.querySelector('.bubble-text').textContent = fullText;
              scrollBottom();
            } else if (evt.type === 'audio' && evt.data) {
              playBase64Wav(evt.data);
            } else if (evt.type === 'error') {
              appendBubble('ai', '抱歉，念念暂时无法回应，请稍后再试。');
            }
          } catch (_) {}
        }
      }
    } catch (e) {
      thinkEl.remove();
      appendBubble('ai', '网络连接有些不稳定，请稍候再试。');
    }

    if (fullText) state.history.push({ role: 'assistant', content: fullText });
    state.isThinking = false;
    setInputLock(false);
    scrollBottom();
  }

  // ─── 气泡渲染 ─────────────────────────────────────────────────────────────
  function appendBubble(role, text) {
    const list = $('agentMessages');
    const wrap = document.createElement('div');
    wrap.className = `msg-row ${role === 'user' ? 'msg-user' : 'msg-ai'}`;

    if (role === 'ai') {
      wrap.innerHTML = `
        <div class="msg-avatar"><div class="agent-orb">念</div></div>
        <div class="bubble bubble-ai"><span class="bubble-text">${escHtml(text)}</span></div>`;
    } else {
      wrap.innerHTML = `
        <div class="bubble bubble-user"><span class="bubble-text">${escHtml(text)}</span></div>`;
    }

    list.appendChild(wrap);
    scrollBottom();
    return wrap;
  }

  function showThinkBubble() {
    const list = $('agentMessages');
    const wrap = document.createElement('div');
    wrap.className = 'msg-row msg-ai';
    wrap.innerHTML = `
      <div class="msg-avatar"><div class="agent-orb">念</div></div>
      <div class="bubble bubble-ai bubble-think">
        <span class="think-dots"><span></span><span></span><span></span></span>
      </div>`;
    list.appendChild(wrap);
    scrollBottom();
    return wrap;
  }

  function scrollBottom() {
    const list = $('agentMessages');
    list.scrollTop = list.scrollHeight;
  }

  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>');
  }

  function setInputLock(lock) {
    const inp = $('agentInput');
    const btn = $('agentSend');
    if (inp) inp.disabled = lock;
    if (btn) btn.disabled = lock;
  }

  // ─── 音频播放 ─────────────────────────────────────────────────────────────
  function playBase64Wav(b64) {
    try {
      const binary = atob(b64);
      const buf = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) buf[i] = binary.charCodeAt(i);
      const blob = new Blob([buf], { type: 'audio/wav' });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.play();
      audio.onended = () => URL.revokeObjectURL(url);
    } catch (e) { console.warn('audio play failed', e); }
  }

  // ─── 语音输入（Web Speech API）────────────────────────────────────────────
  function initSpeechRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return null;
    const rec = new SR();
    rec.lang = 'zh-CN';
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    return rec;
  }

  function toggleVoiceInput() {
    const btn = $('agentVoice');
    if (!state.recognition) {
      state.recognition = initSpeechRecognition();
    }
    if (!state.recognition) {
      alert('您的浏览器不支持语音输入，请使用 Chrome 或 Edge');
      return;
    }

    if (state.isRecording) {
      state.recognition.stop();
      state.isRecording = false;
      btn.classList.remove('recording');
      btn.title = '语音输入';
      return;
    }

    state.isRecording = true;
    btn.classList.add('recording');
    btn.title = '点击停止录音';

    state.recognition.onresult = (e) => {
      const text = e.results[0][0].transcript;
      $('agentInput').value = text;
      state.isRecording = false;
      btn.classList.remove('recording');
      sendMessage(text, state.voiceMode);
      $('agentInput').value = '';
    };

    state.recognition.onerror = () => {
      state.isRecording = false;
      btn.classList.remove('recording');
    };

    state.recognition.onend = () => {
      state.isRecording = false;
      btn.classList.remove('recording');
    };

    state.recognition.start();
  }

  // ─── 初始化 ───────────────────────────────────────────────────────────────
  function init() {
    const inp = $('agentInput');
    const sendBtn = $('agentSend');
    const voiceBtn = $('agentVoice');
    const voiceToggle = $('agentVoiceToggle');

    if (!inp) return;

    // 语音模式切换
    if (voiceToggle) {
      voiceToggle.addEventListener('change', () => {
        state.voiceMode = voiceToggle.checked;
      });
    }

    // 发送
    sendBtn.addEventListener('click', () => {
      const t = inp.value.trim();
      if (!t) return;
      inp.value = '';
      sendMessage(t, state.voiceMode);
    });

    inp.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendBtn.click();
      }
    });

    // 语音按钮
    if (voiceBtn) voiceBtn.addEventListener('click', toggleVoiceInput);

    // 首条问候（延迟 600ms 营造自然感）
    if (!state.hasGreeted) {
      state.hasGreeted = true;
      setTimeout(() => {
        sendMessage('你好，请帮我开始建档', false);
      }, 600);
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
