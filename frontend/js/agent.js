// agent.js — 念念智能体
// 双模式：
//   1) 文字模式：POST /api/agent/chat SSE 流式 + 浏览器 speechSynthesis 朗读
//   2) 实时语音模式：WS /api/agent/realtime → Qwen-Omni-Realtime（PCM16 双向流）
(function () {
  'use strict';

  // ─── 状态 ─────────────────────────────────────────────────────────
  var state = {
    mode: 'text',            // 'text' | 'live'
    history: [],
    isThinking: false,
    // 文字模式
    isRecording: false,
    mediaRecorder: null,
    audioChunks: [],
    synth: window.speechSynthesis || null,
    voices: [],
    // 实时模式
    ws: null,
    audioCtx: null,
    micStream: null,
    micNode: null,
    procNode: null,
    playCtx: null,
    playTime: 0,
    liveAiBubble: null,
    liveAiText: '',
    liveUserBubble: null,
    hasGreeted: false,
  };

  function $(id){ return document.getElementById(id); }

  // ─── 工具 ────────────────────────────────────────────────────────
  function escHtml(s){
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');
  }
  function scrollBottom(){
    var list = $('agentMessages');
    if (list) list.scrollTop = list.scrollHeight;
  }
  function setInputLock(lock){
    var inp = $('agentInput'), btn = $('agentSend');
    if (inp) inp.disabled = lock;
    if (btn) btn.disabled = lock;
  }
  function setStatus(text){
    var el = $('agentStatus');
    if (el) el.textContent = text;
  }
  function setLiveStatus(text, show){
    var bar = $('liveStatus'), t = $('liveStatusText');
    if (t) t.textContent = text;
    if (bar) bar.classList.toggle('show', !!show);
  }

  // ─── 气泡 ────────────────────────────────────────────────────────
  function appendBubble(role, text){
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
  function showThinkBubble(){
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

  // ─── 浏览器 TTS（文字模式用）────────────────────────────────────
  function loadVoices(){
    if (!state.synth) return;
    state.voices = state.synth.getVoices();
    if (!state.voices.length) {
      state.synth.onvoiceschanged = function(){ state.voices = state.synth.getVoices(); };
    }
  }
  function pickChineseVoice(){
    var langs = ['zh-CN','zh_CN','zh-TW','zh'];
    for (var i=0; i<langs.length; i++) {
      var v = state.voices.find(function(v){ return v.lang && v.lang.startsWith(langs[i]); });
      if (v) return v;
    }
    return state.voices[0] || null;
  }
  function speak(text){
    if (state.mode === 'live') return;           // 实时模式由 Qwen 出声
    if (!state.synth) return;
    state.synth.cancel();
    var utt = new SpeechSynthesisUtterance(text);
    utt.lang = 'zh-CN'; utt.rate = 0.95; utt.pitch = 1.05;
    var voice = pickChineseVoice();
    if (voice) utt.voice = voice;
    state.synth.speak(utt);
  }

  // ─── 文字模式：SSE 发送 ──────────────────────────────────────────
  async function sendMessage(text){
    if (!text || !text.trim() || state.isThinking) return;
    state.isThinking = true; setInputLock(true);
    appendBubble('user', text);
    state.history.push({ role:'user', content: text });

    var thinkEl = showThinkBubble();
    var fullText = ''; var aiEl = null;

    try {
      var resp = await fetch('/api/agent/chat', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ message: text, history: state.history.slice(-30) })
      });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);

      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buf = '';
      while (true) {
        var rr = await reader.read();
        if (rr.done) break;
        buf += decoder.decode(rr.value, { stream: true });
        var lines = buf.split('\n');
        buf = lines.pop() || '';
        for (var i=0; i<lines.length; i++) {
          var line = lines[i];
          if (!line.startsWith('data:')) continue;
          var raw = line.slice(5).trim();
          if (raw === '[DONE]') break;
          try {
            var evt = JSON.parse(raw);
            if (evt.type === 'text') {
              fullText += evt.delta;
              if (!aiEl) { thinkEl.remove(); aiEl = appendBubble('ai', ''); }
              aiEl.querySelector('.bubble-text').textContent = fullText;
              scrollBottom();
            } else if (evt.type === 'error') {
              thinkEl.remove(); appendBubble('ai', '抱歉，念念暂时无法回应。');
            }
          } catch(e){}
        }
      }
    } catch(e){
      thinkEl.remove(); appendBubble('ai', '网络连接不稳定，请稍候再试。');
    }

    if (fullText) {
      state.history.push({ role:'assistant', content: fullText });
      speak(fullText);
    }
    state.isThinking = false; setInputLock(false); scrollBottom();
  }

  // ─── 文字模式：单次录音 → /api/agent/asr ────────────────────────
  async function toggleVoiceInput(){
    var btn = $('agentVoice');
    if (state.isRecording) {
      if (state.mediaRecorder) state.mediaRecorder.stop();
      return;
    }
    var stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch(e) {
      alert('无法获取麦克风权限，请在浏览器设置中允许麦克风访问。');
      return;
    }
    state.audioChunks = [];
    var mimeTypes = ['audio/webm;codecs=opus','audio/webm','audio/ogg','audio/wav'];
    var mimeType = mimeTypes.find(function(t){ return MediaRecorder.isTypeSupported(t); }) || '';
    state.mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType: mimeType } : {});
    state.mediaRecorder.ondataavailable = function(e){
      if (e.data && e.data.size > 0) state.audioChunks.push(e.data);
    };
    state.mediaRecorder.onstop = async function(){
      state.isRecording = false;
      if (btn) { btn.classList.remove('recording'); btn.title = '语音输入'; }
      stream.getTracks().forEach(function(t){ t.stop(); });
      var ext = mimeType.includes('ogg') ? 'ogg' : mimeType.includes('wav') ? 'wav' : 'webm';
      var blob = new Blob(state.audioChunks, { type: mimeType || 'audio/webm' });
      var inp = $('agentInput');
      if (inp) inp.placeholder = '正在识别...';
      try {
        var form = new FormData();
        form.append('audio', blob, 'rec.' + ext);
        var res = await fetch('/api/agent/asr', { method:'POST', body: form });
        if (!res.ok) throw new Error('ASR ' + res.status);
        var data = await res.json();
        var txt = (data.text || '').trim();
        if (txt) sendMessage(txt);
        else if (inp) { inp.placeholder = '未识别到内容，请重试'; setTimeout(function(){ inp.placeholder='跟念念说说 Ta 的故事...'; }, 2000); }
      } catch(err){
        console.error(err);
        if (inp) { inp.placeholder = '识别失败，请手动输入'; setTimeout(function(){ inp.placeholder='跟念念说说 Ta 的故事...'; }, 2500); }
      }
    };
    state.isRecording = true;
    if (btn) { btn.classList.add('recording'); btn.title = '点击停止录音'; }
    state.mediaRecorder.start();
  }

  // ─── 实时模式：PCM 编解码工具 ───────────────────────────────────
  function floatTo16BitPCM(input){
    var out = new Int16Array(input.length);
    for (var i=0; i<input.length; i++) {
      var s = Math.max(-1, Math.min(1, input[i]));
      out[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return out;
  }
  function int16ToBase64(int16){
    var u8 = new Uint8Array(int16.buffer);
    var binary = '';
    var CHUNK = 0x8000;
    for (var i=0; i<u8.length; i+=CHUNK) {
      binary += String.fromCharCode.apply(null, u8.subarray(i, i+CHUNK));
    }
    return btoa(binary);
  }
  function base64ToInt16(b64){
    var bin = atob(b64);
    var u8 = new Uint8Array(bin.length);
    for (var i=0; i<bin.length; i++) u8[i] = bin.charCodeAt(i);
    return new Int16Array(u8.buffer, u8.byteOffset, u8.byteLength / 2);
  }
  function int16ToFloat32(int16){
    var f32 = new Float32Array(int16.length);
    for (var i=0; i<int16.length; i++) f32[i] = int16[i] / 32768;
    return f32;
  }

  // ─── 实时模式：启动 WebSocket + 麦克风采集 + 上游播放 ─────────
  async function startLiveMode(){
    var btn = $('agentVoice');
    setLiveStatus('正在请求麦克风...', true);

    var stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount:1, echoCancellation:true, noiseSuppression:true, autoGainControl:true }
      });
    } catch(e) {
      setLiveStatus('麦克风权限被拒绝', true);
      setTimeout(function(){ switchMode('text'); }, 1500);
      return;
    }
    state.micStream = stream;

    // 输入音频 16kHz；浏览器可能不接受任意采样率，回退到 48000 再降采样
    var AudioCtx = window.AudioContext || window.webkitAudioContext;
    try { state.audioCtx = new AudioCtx({ sampleRate: 16000 }); }
    catch(e) { state.audioCtx = new AudioCtx(); }
    var srcRate = state.audioCtx.sampleRate;
    var needResample = srcRate !== 16000;

    // 输出音频独立上下文 24kHz
    try { state.playCtx = new AudioCtx({ sampleRate: 24000 }); }
    catch(e) { state.playCtx = new AudioCtx(); }
    state.playTime = 0;

    // ── WebSocket 连接 ──
    setLiveStatus('正在连接 Qwen-Omni-Realtime...', true);
    var wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var ws = new WebSocket(wsProto + '//' + location.host + '/api/agent/realtime');
    state.ws = ws;

    ws.onopen = function(){
      setLiveStatus('已连接，请开始说话...', true);
      setStatus('实时对话中');
      if (btn) btn.classList.add('live');

      // 开场打招呼（让 AI 主动说一句）
      try {
        ws.send(JSON.stringify({
          type: 'response.create',
          response: { modalities: ['audio','text'], instructions: '用一句温柔的话开场，问候用户、并询问 ta 想聊谁。' }
        }));
      } catch(e){}

      // 启动麦克风采集
      var source = state.audioCtx.createMediaStreamSource(stream);
      var proc = state.audioCtx.createScriptProcessor(4096, 1, 1);
      proc.onaudioprocess = function(e){
        if (!state.ws || state.ws.readyState !== 1) return;
        var input = e.inputBuffer.getChannelData(0);
        var pcm;
        if (needResample) {
          var ratio = srcRate / 16000;
          var outLen = Math.floor(input.length / ratio);
          var resampled = new Float32Array(outLen);
          for (var j=0; j<outLen; j++) resampled[j] = input[Math.floor(j * ratio)];
          pcm = floatTo16BitPCM(resampled);
        } else {
          pcm = floatTo16BitPCM(input);
        }
        var b64 = int16ToBase64(pcm);
        try {
          state.ws.send(JSON.stringify({ type:'input_audio_buffer.append', audio: b64 }));
        } catch(e){}
      };
      source.connect(proc);
      proc.connect(state.audioCtx.destination);
      state.micNode = source; state.procNode = proc;
      // 静音回放（接到 destination 必须发声会导致回环；上面 destination 是为了触发处理）
      // 改用 gain=0 路由：
      try {
        proc.disconnect(state.audioCtx.destination);
        var mute = state.audioCtx.createGain();
        mute.gain.value = 0;
        proc.connect(mute).connect(state.audioCtx.destination);
      } catch(e){}
    };

    ws.onmessage = function(ev){
      var msg;
      try { msg = JSON.parse(ev.data); } catch(e){ return; }
      handleUpstreamEvent(msg);
    };

    ws.onerror = function(e){
      console.error('[ws] error', e);
      setLiveStatus('连接出错', true);
    };

    ws.onclose = function(){
      cleanupLive();
      setLiveStatus('连接已关闭', false);
      setStatus('在线 · 随时倾听');
      if (btn) btn.classList.remove('live');
      // 自动切回文字模式
      if (state.mode === 'live') switchMode('text', /*silent*/ true);
    };
  }

  function handleUpstreamEvent(msg){
    var t = msg.type || '';
    // 用户语音 -> 文字
    if (t === 'conversation.item.input_audio_transcription.completed' && msg.transcript) {
      if (!state.liveUserBubble) state.liveUserBubble = appendBubble('user', msg.transcript);
      else state.liveUserBubble.querySelector('.bubble-text').textContent = msg.transcript;
      state.liveUserBubble = null;
      return;
    }
    if (t === 'input_audio_buffer.speech_started') {
      setLiveStatus('听到你了，正在听...', true);
      return;
    }
    if (t === 'input_audio_buffer.speech_stopped') {
      setLiveStatus('念念正在思考...', true);
      return;
    }
    // AI 文字流
    if (t === 'response.audio_transcript.delta' && msg.delta) {
      if (!state.liveAiBubble) { state.liveAiBubble = appendBubble('ai', ''); state.liveAiText = ''; }
      state.liveAiText += msg.delta;
      state.liveAiBubble.querySelector('.bubble-text').textContent = state.liveAiText;
      scrollBottom();
      return;
    }
    if (t === 'response.audio_transcript.done') {
      if (state.liveAiText) state.history.push({ role:'assistant', content: state.liveAiText });
      state.liveAiBubble = null; state.liveAiText = '';
      return;
    }
    // AI 音频流 → 立即播放
    if (t === 'response.audio.delta' && msg.delta) {
      try {
        var int16 = base64ToInt16(msg.delta);
        var f32 = int16ToFloat32(int16);
        var buf = state.playCtx.createBuffer(1, f32.length, 24000);
        buf.copyToChannel(f32, 0);
        var src = state.playCtx.createBufferSource();
        src.buffer = buf; src.connect(state.playCtx.destination);
        var now = state.playCtx.currentTime;
        var startAt = Math.max(state.playTime, now + 0.02);
        src.start(startAt);
        state.playTime = startAt + buf.duration;
      } catch(e) { console.warn('[play] failed', e); }
      setLiveStatus('念念在说话...', true);
      return;
    }
    if (t === 'response.audio.done') {
      setLiveStatus('请继续说话...', true);
      return;
    }
    if (t === 'session.created' || t === 'session.updated') {
      console.log('[ws]', t);
      return;
    }
    if (t === 'error') {
      console.error('[ws] error event', msg);
      setLiveStatus('上游错误：' + (msg.error && msg.error.message || msg.message || '未知'), true);
    }
  }

  function cleanupLive(){
    if (state.micStream) { state.micStream.getTracks().forEach(function(t){ t.stop(); }); state.micStream = null; }
    if (state.procNode) { try { state.procNode.disconnect(); } catch(e){} state.procNode = null; }
    if (state.micNode)  { try { state.micNode.disconnect();  } catch(e){} state.micNode  = null; }
    if (state.audioCtx) { try { state.audioCtx.close(); } catch(e){} state.audioCtx = null; }
    if (state.playCtx)  { try { state.playCtx.close();  } catch(e){} state.playCtx  = null; }
    if (state.ws) { try { state.ws.close(); } catch(e){} state.ws = null; }
    state.liveAiBubble = null; state.liveAiText = ''; state.liveUserBubble = null;
  }

  function stopLiveMode(){
    cleanupLive();
    setLiveStatus('', false);
    var btn = $('agentVoice');
    if (btn) btn.classList.remove('live');
    setStatus('在线 · 随时倾听');
  }

  // ─── 模式切换 ────────────────────────────────────────────────────
  function switchMode(mode, silent){
    if (state.mode === mode) return;
    var prev = state.mode;
    state.mode = mode;
    var btnT = $('modeText'), btnL = $('modeLive');
    if (btnT) btnT.classList.toggle('active', mode === 'text');
    if (btnL) btnL.classList.toggle('active', mode === 'live');

    if (prev === 'live') stopLiveMode();
    if (state.synth) state.synth.cancel();

    if (mode === 'live') {
      startLiveMode();
    } else if (!silent) {
      setLiveStatus('', false);
      setStatus('在线 · 随时倾听');
    }
  }

  // ─── 初始化 ─────────────────────────────────────────────────────
  function init(){
    var inp = $('agentInput');
    if (!inp) return;
    loadVoices();

    $('agentSend').addEventListener('click', function(){
      var t = inp.value.trim();
      if (!t) return;
      inp.value = '';
      sendMessage(t);
    });
    inp.addEventListener('keydown', function(e){
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('agentSend').click(); }
    });
    var vBtn = $('agentVoice');
    if (vBtn) vBtn.addEventListener('click', function(){
      if (state.mode === 'live') {
        // 实时模式下点击麦克风按钮 = 退出实时
        switchMode('text');
      } else {
        toggleVoiceInput();
      }
    });

    var mT = $('modeText'), mL = $('modeLive');
    if (mT) mT.addEventListener('click', function(){ switchMode('text'); });
    if (mL) mL.addEventListener('click', function(){ switchMode('live'); });

    // 文字模式自动问候（实时模式由后端触发开场）
    if (!state.hasGreeted) {
      state.hasGreeted = true;
      setTimeout(function(){
        if (state.mode === 'text') sendMessage('你好，我想制作一部追思影像');
      }, 800);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
