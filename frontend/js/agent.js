// frontend/js/agent.js — 念念智能体
// 语音输入: MediaRecorder -> /api/agent/asr (DashScope Paraformer)
// 朗读输出: 浏览器 speechSynthesis
(function () {
  'use strict';

  var state = {
    history: [],
    isThinking: false,
    isRecording: false,
    voiceMode: false,
    mediaRecorder: null,
    audioChunks: [],
    hasGreeted: false,
    synth: window.speechSynthesis || null,
    voices: []
  };

  function $(id) { return document.getElementById(id); }

  // --- 语音列表 ---
  function loadVoices() {
    if (!state.synth) return;
    state.voices = state.synth.getVoices();
    if (!state.voices.length) {
      state.synth.onvoiceschanged = function () { state.voices = state.synth.getVoices(); };
    }
  }

  function pickChineseVoice() {
    var langs = ['zh-CN', 'zh_CN', 'zh-TW', 'zh'];
    for (var i = 0; i < langs.length; i++) {
      var v = state.voices.find(function (v) { return v.lang.startsWith(langs[i]); });
      if (v) return v;
    }
    return state.voices[0] || null;
  }

  // --- 朗读 ---
  function speak(text) {
    if (!state.voiceMode || !state.synth) return;
    state.synth.cancel();
    var utt = new SpeechSynthesisUtterance(text);
    utt.lang = 'zh-CN';
    utt.rate = 0.95;
    utt.pitch = 1.05;
    var voice = pickChineseVoice();
    if (voice) utt.voice = voice;
    state.synth.speak(utt);
  }

  // --- 工具函数 ---
  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>');
  }

  function scrollBottom() {
    var list = $('agentMessages');
    if (list) list.scrollTop = list.scrollHeight;
  }

  function setInputLock(lock) {
    var inp = $('agentInput');
    var btn = $('agentSend');
    if (inp) inp.disabled = lock;
    if (btn) btn.disabled = lock;
  }

  // --- 气泡 ---
  function appendBubble(role, text) {
    var list = $('agentMessages');
    var wrap = document.createElement('div');
    wrap.className = 'msg-row ' + (role === 'user' ? 'msg-user' : 'msg-ai');
    if (role === 'ai') {
      wrap.innerHTML = '<div class="msg-avatar"><div class="agent-orb">念</div></div>' +
        '<div class="bubble bubble-ai"><span class="bubble-text">' + escHtml(text) + '</span></div>';
    } else {
      wrap.innerHTML = '<div class="bubble bubble-user"><span class="bubble-text">' + escHtml(text) + '</span></div>';
    }
    list.appendChild(wrap);
    scrollBottom();
    return wrap;
  }

  function showThinkBubble() {
    var list = $('agentMessages');
    var wrap = document.createElement('div');
    wrap.className = 'msg-row msg-ai';
    wrap.innerHTML = '<div class="msg-avatar"><div class="agent-orb">念</div></div>' +
      '<div class="bubble bubble-ai bubble-think">' +
      '<span class="think-dots"><span></span><span></span><span></span></span></div>';
    list.appendChild(wrap);
    scrollBottom();
    return wrap;
  }

  // --- SSE 发送 ---
  async function sendMessage(text) {
    if (!text || !text.trim() || state.isThinking) return;
    state.isThinking = true;
    setInputLock(true);

    appendBubble('user', text);
    state.history.push({ role: 'user', content: text });

    var thinkEl = showThinkBubble();
    var fullText = '';
    var aiEl = null;

    try {
      var resp = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history: state.history.slice(-30) })
      });

      if (!resp.ok) throw new Error('HTTP ' + resp.status);

      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buf = '';

      while (true) {
        var readResult = await reader.read();
        if (readResult.done) break;
        buf += decoder.decode(readResult.value, { stream: true });
        var lines = buf.split('\n');
        buf = lines.pop() || '';

        for (var li = 0; li < lines.length; li++) {
          var line = lines[li];
          if (!line.startsWith('data:')) continue;
          var raw = line.slice(5).trim();
          if (raw === '[DONE]') break;
          try {
            var evt = JSON.parse(raw);
            if (evt.type === 'text') {
              fullText += evt.delta;
              if (!aiEl) {
                thinkEl.remove();
                aiEl = appendBubble('ai', '');
              }
              aiEl.querySelector('.bubble-text').textContent = fullText;
              scrollBottom();
            } else if (evt.type === 'error') {
              thinkEl.remove();
              appendBubble('ai', '抱歉，念念暂时无法回应，请稍后再试。');
            }
          } catch (parseErr) { /* ignore */ }
        }
      }
    } catch (e) {
      thinkEl.remove();
      appendBubble('ai', '网络连接有些不稳定，请稍候再试。');
    }

    if (fullText) {
      state.history.push({ role: 'assistant', content: fullText });
      speak(fullText);
    }
    state.isThinking = false;
    setInputLock(false);
    scrollBottom();
  }

  // --- 语音输入 ---
  async function toggleVoiceInput() {
    var btn = $('agentVoice');

    if (state.isRecording) {
      if (state.mediaRecorder) state.mediaRecorder.stop();
      return;
    }

    var stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      alert('无法获取麦克风权限，请在浏览器设置中允许麦克风访问。');
      return;
    }

    state.audioChunks = [];
    var mimeTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg', 'audio/wav'];
    var mimeType = mimeTypes.find(function (t) { return MediaRecorder.isTypeSupported(t); }) || '';

    state.mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType: mimeType } : {});

    state.mediaRecorder.ondataavailable = function (e) {
      if (e.data && e.data.size > 0) state.audioChunks.push(e.data);
    };

    state.mediaRecorder.onstop = async function () {
      state.isRecording = false;
      if (btn) { btn.classList.remove('recording'); btn.title = '语音输入'; }
      stream.getTracks().forEach(function (t) { t.stop(); });

      var ext = mimeType.includes('ogg') ? 'ogg' : mimeType.includes('wav') ? 'wav' : 'webm';
      var blob = new Blob(state.audioChunks, { type: mimeType || 'audio/webm' });
      var inp = $('agentInput');
      if (inp) inp.placeholder = '正在识别...';

      try {
        var form = new FormData();
        form.append('audio', blob, 'rec.' + ext);
        var res = await fetch('/api/agent/asr', { method: 'POST', body: form });
        if (!res.ok) throw new Error('ASR ' + res.status);
        var data = await res.json();
        var recognized = (data.text || '').trim();
        if (recognized) {
          sendMessage(recognized);
        } else {
          if (inp) inp.placeholder = '未识别到内容，请重试';
          setTimeout(function () { if (inp) inp.placeholder = '跟念念说说 Ta 的故事...'; }, 2000);
        }
      } catch (err) {
        console.error('ASR error', err);
        if (inp) inp.placeholder = '识别失败，请手动输入';
        setTimeout(function () { if (inp) inp.placeholder = '跟念念说说 Ta 的故事...'; }, 2500);
      }
    };

    state.isRecording = true;
    if (btn) { btn.classList.add('recording'); btn.title = '点击停止录音'; }
    state.mediaRecorder.start();
  }

  // --- 初始化 ---
  function init() {
    var inp = $('agentInput');
    if (!inp) return;

    loadVoices();

    // 朗读开关
    var voiceToggle = $('agentVoiceToggle');
    if (voiceToggle) {
      voiceToggle.addEventListener('change', function () {
        state.voiceMode = voiceToggle.checked;
        if (!state.voiceMode && state.synth) state.synth.cancel();
      });
    }

    // 发送
    var sendBtn = $('agentSend');
    if (sendBtn) {
      sendBtn.addEventListener('click', function () {
        var t = inp.value.trim();
        if (!t) return;
        inp.value = '';
        sendMessage(t);
      });
    }

    // Enter
    inp.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (sendBtn) sendBtn.click();
      }
    });

    // 麦克风按钮
    var voiceBtn = $('agentVoice');
    if (voiceBtn) voiceBtn.addEventListener('click', toggleVoiceInput);

    // 自动问候
    if (!state.hasGreeted) {
      state.hasGreeted = true;
      setTimeout(function () { sendMessage('你好，我想制作一部追思影像'); }, 700);
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
