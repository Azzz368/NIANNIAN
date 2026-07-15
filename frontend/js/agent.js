// agent.js — 念念智能体
// 文字模式：
//   - 输入 → /api/agent/chat (SSE) 流式回复，不朗读
//   - 按住麦克风键 = 录音；松开 = 停止 + 上传 DashScope Paraformer 精准识别
//   - 录音过程中：浏览器 webkitSpeechRecognition 实时本地预览，填充到输入框
// 实时语音模式：
//   - WS /api/agent/realtime → Qwen-Omni-Realtime（双向 PCM16）
(function () {
  'use strict';

  var state = {
    mode: 'text',
    history: [],
    isThinking: false,
    // 文字模式 录音
    isRecording: false,
    mediaRecorder: null,
    audioChunks: [],
    sr: null,                  // SpeechRecognition 实例（本地预览）
    srPreview: '',             // 本地实时预览文本
    srBaseText: '',            // 按下录音前输入框已有的文本（保留）
    // 实时模式
    ws: null,
    audioCtx: null,
    micStream: null,
    micNode: null,
    procNode: null,
    playCtx: null,
    playTime: 0,
    activeAudioSources: [],    // 当前正在播放/已排队的 AI 语音 AudioBufferSourceNode，用于被打断时立即停止
    liveAiBubble: null,
    liveAiText: '',
    liveUserBubble: null,
    hasGreeted: false,
  };

  function $(id){ return document.getElementById(id); }

  function escHtml(s){
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');
  }
  function scrollBottom(){ var l=$('agentMessages'); if (l) l.scrollTop = l.scrollHeight; }

  function showToast(msg, ms){
    var t = $('dossierToast'); if (!t) return;
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(t._tm);
    t._tm = setTimeout(function(){ t.classList.remove('show'); }, ms || 2800);
  }
  function setInputLock(lock){
    var inp = $('agentInput'), btn = $('agentSend');
    if (inp) inp.disabled = lock;
    if (btn) btn.disabled = lock;
  }
  function setStatus(t){ var el = $('agentStatus'); if (el) el.textContent = t; }
  function setLiveStatus(t, show){
    var bar = $('liveStatus'), txt = $('liveStatusText');
    if (txt) txt.textContent = t;
    if (bar) bar.classList.toggle('show', !!show);
  }

  function appendBubble(role, text){
    if(document.getElementById('immersiveChat')) {
      if(role === 'user') document.getElementById('immersiveUserText').textContent = text;
      else document.getElementById('immersiveAiText').textContent = text;
    }

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

  // ─── 文字模式：SSE（不朗读）─────────────────────────────────────
  async function sendMessage(text){
    if (!text || !text.trim() || state.isThinking) return;
    state.isThinking = true; setInputLock(true);
    appendBubble('user', text);
    state.history.push({ role:'user', content: text });

    var thinkEl = showThinkBubble();
    var fullText = ''; var aiEl = null;

    try {
      var headers = {'Content-Type':'application/json'};
      var tok = window.NianAuth && window.NianAuth.getToken();
      if (tok) headers['Authorization'] = 'Bearer ' + tok;
      var mid = window.NianAuth && window.NianAuth.getActiveMemorialId();
      var resp = await fetch('/api/agent/chat', {
        method:'POST',
        headers: headers,
        body: JSON.stringify({ message: text, history: state.history.slice(-30), memorial_id: mid || null })
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
              // 同步更新光球沉浸式文字区域
              var _imAi = document.getElementById('immersiveAiText');
              if (_imAi) _imAi.textContent = fullText;
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

    if (fullText) state.history.push({ role:'assistant', content: fullText });
    state.isThinking = false; setInputLock(false); scrollBottom();
  }

  // ─── 图片上传并分析（主界面 + 号按钮）────────────────────────────
  async function sendImageMessage(file) {
    if (!file || state.isThinking) return;
    state.isThinking = true;

    appendBubble('user', '[图片] ' + file.name);
    state.history.push({ role: 'user', content: '[图片：' + file.name + ']' });

    var thinkEl = showThinkBubble();
    var fullText = ''; var aiEl = null;

    // Step 1: 上传到当前对象资料库
    var mid = window.NianAuth && window.NianAuth.getActiveMemorialId ? window.NianAuth.getActiveMemorialId() : null;
    if (mid && window.NianAuth && window.NianAuth.isAuthed()) {
      try {
        var fd = new FormData();
        fd.append('file', file);
        fd.append('description', '');
        var ur = await window.NianAuth.fetch('/api/memorials/' + encodeURIComponent(mid) + '/upload', { method: 'POST', body: fd });
        if (ur.ok) {
          var ud = await ur.json();
          var utags = ((ud.asset || {}).tags || []).slice(0, 4).join('、');
          showToast('已入资料库' + (utags ? '：' + utags : ''), 2800);
        }
      } catch(e) { console.warn('[img-lib] upload failed:', e); }
    }

    // Step 2: 发给 Qwen VL 分析（念念做视觉回应）
    try {
      var headers = {};
      var tok = window.NianAuth && window.NianAuth.getToken ? window.NianAuth.getToken() : null;
      if (tok) headers['Authorization'] = 'Bearer ' + tok;

      var form = new FormData();
      form.append('image', file);
      form.append('history', JSON.stringify(state.history.slice(-20)));
      if (mid) form.append('memorial_id', mid);

      var resp = await fetch('/api/agent/image-chat', { method: 'POST', headers: headers, body: form });
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
        for (var ii = 0; ii < lines.length; ii++) {
          var ln = lines[ii];
          if (!ln.startsWith('data:')) continue;
          var rw = ln.slice(5).trim();
          if (rw === '[DONE]') break;
          try {
            var ev = JSON.parse(rw);
            if (ev.type === 'text') {
              fullText += ev.delta;
              if (!aiEl) { thinkEl.remove(); aiEl = appendBubble('ai', ''); }
              aiEl.querySelector('.bubble-text').textContent = fullText;
              var _imAi2 = document.getElementById('immersiveAiText');
              if (_imAi2) _imAi2.textContent = fullText;
              scrollBottom();
            }
          } catch(e) {}
        }
      }
    } catch(e) {
      thinkEl.remove();
      appendBubble('ai', '图片分析失败：' + e.message);
    }

    if (fullText) state.history.push({ role: 'assistant', content: fullText });
    state.isThinking = false;
    setInputLock(false);
    scrollBottom();
  }

  // ─── 文字模式：按住录音 ────────────────────────────────────────
  function getSR(){
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return null;
    var sr = new SR();
    sr.lang = 'zh-CN';
    sr.continuous = true;
    sr.interimResults = true;
    return sr;
  }

  async function startHoldRecording(){
    if (state.isRecording || state.isThinking) return;
    var btn = $('agentVoice'); var inp = $('agentInput');
    if (!inp) return;

    state.srBaseText = inp.value || '';
    state.srPreview = '';

    // 请求麦克风
    var stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch(e) {
      alert('无法获取麦克风权限，请在浏览器设置中允许麦克风访问。');
      return;
    }

    // ── MediaRecorder（用于最终精准识别）──
    state.audioChunks = [];
    var mimeTypes = ['audio/webm;codecs=opus','audio/webm','audio/ogg','audio/wav'];
    var mimeType = mimeTypes.find(function(t){ return MediaRecorder.isTypeSupported(t); }) || '';
    var mr = new MediaRecorder(stream, mimeType ? { mimeType: mimeType } : {});
    mr.ondataavailable = function(e){ if (e.data && e.data.size > 0) state.audioChunks.push(e.data); };
    mr.onstop = async function(){
      stream.getTracks().forEach(function(t){ t.stop(); });
      state.isRecording = false;
      if (btn) { btn.classList.remove('recording'); btn.title = '按住说话'; }
      inp.classList.remove('is-listening');
      if (inp) inp.placeholder = '正在精准识别...';

      var ext = mimeType.includes('ogg') ? 'ogg' : mimeType.includes('wav') ? 'wav' : 'webm';
      var blob = new Blob(state.audioChunks, { type: mimeType || 'audio/webm' });
      try {
        var form = new FormData();
        form.append('audio', blob, 'rec.' + ext);
        var res = await fetch('/api/agent/asr', { method:'POST', body: form });
        if (!res.ok) throw new Error('ASR ' + res.status);
        var data = await res.json();
        var final = (data.text || '').trim();
        if (final) {
          // 用精准结果替换本地预览文本
          inp.value = (state.srBaseText ? state.srBaseText + ' ' : '') + final;
          inp.focus();
          // 把光标放末尾
          try { inp.setSelectionRange(inp.value.length, inp.value.length); } catch(e){}
        }
        inp.placeholder = '跟念念说说 Ta 的故事...';
      } catch(err){
        console.error(err);
        inp.placeholder = '识别失败，可手动输入';
        setTimeout(function(){ inp.placeholder = '跟念念说说 Ta 的故事...'; }, 2500);
      }
    };
    state.mediaRecorder = mr;
    mr.start();

    // ── webkitSpeechRecognition（用于实时预览）──
    var sr = getSR();
    if (sr) {
      sr.onresult = function(ev){
        var interim = '', finalT = '';
        for (var i = ev.resultIndex; i < ev.results.length; i++) {
          var r = ev.results[i];
          if (r.isFinal) finalT += r[0].transcript;
          else interim += r[0].transcript;
        }
        // 累加 final + 当前 interim
        state.srPreview = (state.srPreview + finalT).trim();
        var preview = state.srPreview + (interim ? (state.srPreview ? ' ' : '') + interim : '');
        inp.value = (state.srBaseText ? state.srBaseText + ' ' : '') + preview;
      };
      sr.onerror = function(e){ console.warn('[SR] error', e.error); };
      sr.onend = function(){};
      try { sr.start(); } catch(e){ console.warn('[SR] start', e); }
      state.sr = sr;
    } else {
      // 浏览器不支持 → 仅显示提示
      inp.placeholder = '聆听中...（无实时预览）';
    }

    state.isRecording = true;
    if (btn) { btn.classList.add('recording'); btn.title = '松开发送录音'; }
    inp.classList.add('is-listening');
  }

  function stopHoldRecording(){
    if (!state.isRecording) return;
    // 先停 SR（避免再触发 onresult 覆盖最终结果）
    if (state.sr) { try { state.sr.stop(); } catch(e){} state.sr = null; }
    state.srPreview = '';
    // 再停录音，触发 onstop → DashScope Paraformer 精准识别
    if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
      try { state.mediaRecorder.stop(); } catch(e){}
    }
  }

  // ─── 实时模式：PCM 工具 ─────────────────────────────────────────
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
    var bin = ''; var CHUNK = 0x8000;
    for (var i=0; i<u8.length; i+=CHUNK) bin += String.fromCharCode.apply(null, u8.subarray(i, i+CHUNK));
    return btoa(bin);
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
    var AudioCtx = window.AudioContext || window.webkitAudioContext;
    try { state.audioCtx = new AudioCtx({ sampleRate: 16000 }); } catch(e) { state.audioCtx = new AudioCtx(); }
    var srcRate = state.audioCtx.sampleRate;
    var needResample = srcRate !== 16000;
    try { state.playCtx = new AudioCtx({ sampleRate: 24000 }); } catch(e) { state.playCtx = new AudioCtx(); }
    state.playTime = 0;
    state.activeAudioSources = [];

    // AnalyserNode 实时跟踪 AI 输出音量（驱动光晕动效）
    try {
      state.playAnalyser = state.playCtx.createAnalyser();
      state.playAnalyser.fftSize = 1024;
      state.playAnalyser.smoothingTimeConstant = 0.3;
      state.playAnalyser.connect(state.playCtx.destination);
      state._volBuf = new Float32Array(state.playAnalyser.fftSize);
      if (!state._volRAF) {
        var sampleVol = function(){
          if (!state.playAnalyser) { state._volRAF = null; return; }
          try {
            state.playAnalyser.getFloatTimeDomainData(state._volBuf);
            var _s = 0, _n = state._volBuf.length;
            for (var _i=0; _i<_n; _i++) _s += state._volBuf[_i] * state._volBuf[_i];
            window.aiActiveVolume = Math.sqrt(_s / _n);
          } catch(e){}
          state._volRAF = requestAnimationFrame(sampleVol);
        };
        state._volRAF = requestAnimationFrame(sampleVol);
      }
    } catch(e) { console.warn('[analyser] init failed', e); }

    setLiveStatus('正在连接 Qwen-Omni-Realtime...', true);
    var wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var qs = [];
    try {
      var mid = (window.NianAuth && NianAuth.getActiveMemorialId && NianAuth.getActiveMemorialId()) || '';
      var tok = (window.NianAuth && NianAuth.getToken && NianAuth.getToken()) || '';
      if (mid) qs.push('mid=' + encodeURIComponent(mid));
      if (tok) qs.push('token=' + encodeURIComponent(tok));
    } catch(e){}
    var wsUrl = wsProto + '//' + location.host + '/api/agent/realtime' + (qs.length ? '?' + qs.join('&') : '');
    var ws = new WebSocket(wsUrl);
    state.ws = ws;

    // ─── 停止检测 state（服务端 VAD 只负责快速切分音频，不自动生成回复；
    //      是否说话、说什么由客户端的"缓冲"逻辑决定，避免用户中途停顿就被 AI 打断）─
    state.committing = false;
    state.fadeActive = false;
    state.aiSpeaking = false; window.aiActiveVolume=0;
    state.manualCommitPending = false;  // 是否正等待"我说完了/手动提交"触发的完整回答
    state.fillerCount = 0;              // 本轮已发出的简短回声反馈次数（嗯/然后呢…）
    state.maxFillers = 2;                // 最多连续回声反馈次数，超过后直接给完整回答
    state.fillerTimer = null;           // 检测到停顿后，等一小段时间再决定是否回声
    state.finalTimer = null;            // 兜底：即使用户没说"我说完了"，沉默太久也要给完整回答
    state.lastUserText = '';            // 最近一段用户转写文本，用于判断是否邀请点评
    var FILLER_DELAY_MIN_MS = 1500;     // 停顿超过此区间下限（随机取值）→ 认为用户可能只是短暂停顿
    var FILLER_DELAY_MAX_MS = 2500;     // 停顿超过此区间上限，尽快回一句简短反馈，避免冷场太久
    var FINAL_SILENCE_MIN_MS = 5000;    // 停顿超过此区间（随机取值，且没再开口）→ 直接给完整回答
    var FINAL_SILENCE_MAX_MS = 8000;
    var INVITE_OPINION_RE = /你觉得呢|你说呢|你说.{0,3}是吧|你说对吧|你怎么看|你看呢|对不对|是不是|你说是不|你说好不好|你说好吗/i;
    var FILLER_PHRASES = ['嗯', '然后呢', '然后？', '接着呢？', '我在听', '哦？'];
    function randomBetween(min, max){ return min + Math.random() * (max - min); }

    function stopAiPlayback(){
      // 用户一开口就立即打断 AI：停掉所有已排队/正在播放的语音片段，并让上游取消当前回答，
      // 这样不需要按住/关闭麦克风按钮，效果跟真人对话中被打断一样自然。
      state.activeAudioSources.forEach(function(src){
        try { src.onended = null; src.stop(0); } catch(e){}
      });
      state.activeAudioSources.length = 0;
      state.playTime = state.playCtx ? state.playCtx.currentTime : 0;
      state.aiSpeaking = false; window.aiActiveVolume = 0;
      if (state.liveAiText) state.history.push({ role:'assistant', content: state.liveAiText });
      state.liveAiBubble = null; state.liveAiText = '';
      try { ws.send(JSON.stringify({ type: 'response.cancel' })); } catch(e){}
    }

    function liveWaveEl(){ return document.querySelector('.live-wave, #liveWave, .agent-live-wave'); }
    function startFade(){
      if (state.fadeActive) return;
      state.fadeActive = true;
      var el = liveWaveEl(); if (el) el.classList.add('fading');
    }
    function clearFade(){
      state.fadeActive = false;
      var el = liveWaveEl(); if (el) el.classList.remove('fading');
    }
    function clearFillerTimer(){ if (state.fillerTimer) { clearTimeout(state.fillerTimer); state.fillerTimer = null; } }
    function clearFinalTimer(){ if (state.finalTimer) { clearTimeout(state.finalTimer); state.finalTimer = null; } }
    function sendResponseCreate(instructionsOverride){
      var resp = { modalities: ['audio','text'] };
      if (instructionsOverride) resp.instructions = instructionsOverride;
      try { ws.send(JSON.stringify({ type: 'response.create', response: resp })); } catch(e){}
    }
    function sendFillerResponse(){
      state.fillerCount++;
      var invited = state.lastUserText && INVITE_OPINION_RE.test(state.lastUserText);
      if (invited) {
        // 用户明确邀请点评/认同（"你觉得呢"/"你说是吧"之类）→ 给一句真诚的简短评价，而不是干巴巴的回声词
        setLiveStatus('念念给你一点小小的回应…', true);
        sendResponseCreate(
          '用户刚才的话里在邀请你给出看法或认同（比如说了"你觉得呢/你说是吧"之类）。' +
          '请像朋友随口聊天一样，用一句非常简短、真诚的口语化反应表达你的想法或认同，' +
          '不超过 15 个字，说完就停，不要展开长篇分析，也不要再提新问题。'
        );
      } else {
        // 默认：只是短暂停顿，随机挑一个简短的倾听词，避免每次都说同一句显得机械
        var phrase = FILLER_PHRASES[Math.floor(Math.random() * FILLER_PHRASES.length)];
        setLiveStatus('念念先应一声，继续听你说…', true);
        sendResponseCreate(
          '用户可能话还没说完，只是短暂停顿。请只用一个非常简短的口头回应词回应，' +
          '就说"' + phrase + '"这个词（或换成同类的"嗯/然后呢/然后？/接着呢？/我在听/哦？"之一），不超过 6 个字。' +
          '绝对不要开始正式回答、不要总结、不要评价、不要提新问题，说完这一个词就停。'
        );
      }
    }
    function commitTurn(reason, alsoCommitBuffer){
      if (state.committing) return;
      state.committing = true;
      state.manualCommitPending = true;
      clearFade(); clearFillerTimer(); clearFinalTimer();
      state.fillerCount = 0;
      setLiveStatus('已提交（' + reason + '），念念正在思考...', true);
      // alsoCommitBuffer=false 用于"长时间沉默"兜底：此时用户早已停止说话，
      // 当前录音缓冲区通常已被服务端自动提交过（是空的），再提交一次可能报错，
      // 所以只发 response.create，直接对已有的对话内容生成完整回答。
      if (alsoCommitBuffer !== false) {
        try { ws.send(JSON.stringify({ type: 'input_audio_buffer.commit' })); } catch(e){}
      } else {
        state.manualCommitPending = false;  // 没有发起真正的 commit，不必等待 committed 回调
      }
      sendResponseCreate();
      setTimeout(function(){ state.committing = false; }, 1500);
    }
    function scheduleBufferWindow(){
      // 服务端已自动提交了一段用户语音（VAD 检测到短暂停顿），先不急着让 AI 长篇回应，
      // 给用户一个继续说下去的窗口（1.5~2.5 秒随机，尽快回应但不打断）；
      // 超时后回声反馈，再等 5~8 秒（随机）仍无动静才给完整回答。
      clearFillerTimer(); clearFinalTimer();
      state.fillerTimer = setTimeout(function(){
        if (state.fillerCount < state.maxFillers) {
          sendFillerResponse();
        }
      }, randomBetween(FILLER_DELAY_MIN_MS, FILLER_DELAY_MAX_MS));
      state.finalTimer = setTimeout(function(){
        commitTurn('长时间沉默', false);
      }, randomBetween(FINAL_SILENCE_MIN_MS, FINAL_SILENCE_MAX_MS));
    }
    function scheduleBufferWindowIfIdle(){
      // 麦克风阵列环境音会让服务端 VAD 频繁误判"用户在说话"，导致 speech_started/committed
      // 反复触发。如果倒计时已经在跑，说明我们已经在等一段"有效文字"，不要被噪音打断重置，
      // 否则永远等不到反馈/兜底触发。只有当前没有任何倒计时在跑时才开始新一轮等待。
      if (!state.fillerTimer && !state.finalTimer) scheduleBufferWindow();
    }
    state._commitTurn = commitTurn;  // 暴露给 handleUpstreamEvent 关键词检测
    state._scheduleBufferWindow = scheduleBufferWindowIfIdle;
    state._restartBufferWindow = scheduleBufferWindow;
    state._clearBufferTimers = function(){ clearFillerTimer(); clearFinalTimer(); };
    state._stopAiPlayback = stopAiPlayback;

    ws.onopen = function(){
      setLiveStatus('已连接，请开始说话…', true);
      setStatus('实时对话中');
      if (btn) btn.classList.add('live');

      // 仅当本次会话历史为空时才主动问候；之后重连不再重复自我介绍
      var firstTime = !state.history || state.history.length === 0;
      if (firstTime) {
        try {
          ws.send(JSON.stringify({
            type: 'response.create',
            response: { modalities: ['audio','text'], instructions: '用一句温柔的话开场，问候用户，邀请 ta 慢慢说。不要自我介绍是谁。' }
          }));
        } catch(e){}
      }

      var source = state.audioCtx.createMediaStreamSource(stream);
      var proc = state.audioCtx.createScriptProcessor(4096, 1, 1);
      proc.onaudioprocess = function(e){
        if (!state.ws || state.ws.readyState !== 1) return;
        var input = e.inputBuffer.getChannelData(0);
        var pcm;
        if (needResample) {
          var ratio = srcRate / 16000;
          var outLen = Math.floor(input.length / ratio);
          var rs = new Float32Array(outLen);
          for (var j=0; j<outLen; j++) rs[j] = input[Math.floor(j * ratio)];
          pcm = floatTo16BitPCM(rs);
        } else pcm = floatTo16BitPCM(input);
        try { state.ws.send(JSON.stringify({ type:'input_audio_buffer.append', audio: int16ToBase64(pcm) })); } catch(e){}
      };
      source.connect(proc);
      var mute = state.audioCtx.createGain();
      mute.gain.value = 0;
      proc.connect(mute).connect(state.audioCtx.destination);
      state.micNode = source; state.procNode = proc;
    };

    ws.onmessage = function(ev){ var m; try { m = JSON.parse(ev.data); } catch(e){ return; } handleUpstreamEvent(m); };
    ws.onerror = function(e){ console.error('[ws] error', e); setLiveStatus('连接出错', true); };
    ws.onclose = function(){
      cleanupLive();
      setLiveStatus('连接已关闭', false);
      setStatus('在线 · 随时倾听');
      if (btn) btn.classList.remove('live');
      if (state.mode === 'live') switchMode('text', true);
    };
  }

  function handleUpstreamEvent(msg){
    var t = msg.type || '';
    if (t === 'conversation.item.input_audio_transcription.completed') {
      var text = (msg.transcript || '').trim();
      if (text) {
        // 识别到真正有效的文字 → 用户确实在说话，重新给一段完整的等待窗口
        appendBubble('user', text);
        state.lastUserText = text;
        try { state._restartBufferWindow && state._restartBufferWindow(); } catch(e){}
        // 关键词触发立即提交（防止用户说完了但还没到兜底时间）
        if (/我说完了|说完了|讲完了|说完啦|讲完啦|就这样|就这样吧|先这样|先这样吧|先说这些|先说到这|就先这样|这样就行|这样就好|好了就这样|暂时就这样|over|done/i.test(text)) {
          try { state._commitTurn && state._commitTurn('关键词「说完了」'); } catch(e){}
        }
      }
      // text 为空：说明这段被 VAD 切分出来的音频没有识别出任何有效文字（多半是麦克风阵列拾取的
      // 环境噪音），不当作"用户还在说话"，不重置倒计时，让 scheduleBufferWindowIfIdle 继续计时。
      return;
    }
    // 服务端 VAD：用户开始/停止说话 → 同步 UI 渐弱动画
    if (t === 'input_audio_buffer.speech_started') {
      // 用户一开口，不管手上有没有按住麦克风按钮，只要 AI 正在说话就立即打断它，
      // 像真人对话一样：你说话，对方马上停下来听你说。
      if (state.aiSpeaking || state.activeAudioSources.length) {
        try { state._stopAiPlayback && state._stopAiPlayback(); } catch(e){}
      }
      if (typeof clearFade === 'function') {} // no-op
      var el1 = document.querySelector('.live-wave'); if (el1) el1.classList.remove('fading');
      // 注意：不在这里清除回声/兜底倒计时——麦克风阵列的环境音会让 VAD 频繁误判"开始说话"，
      // 真正的重置只在收到有效识别文字（input_audio_transcription.completed 且非空）时才发生。
      setLiveStatus('听到你了，慢慢说…', true);
      return;
    }
    if (t === 'input_audio_buffer.speech_stopped') {
      // 服务端检测到停顿：先别急着回应，给用户一个继续说下去的窗口
      var el2 = document.querySelector('.live-wave'); if (el2) el2.classList.add('fading');
      setLiveStatus('正在等你继续…', true);
      return;
    }
    if (t === 'input_audio_buffer.committed') {
      var el3 = document.querySelector('.live-wave'); if (el3) el3.classList.remove('fading');
      if (state.manualCommitPending) {
        // 手动提交（"我说完了"关键词 / 长时间沉默兜底）→ 已在 commitTurn 里发出完整回答请求
        state.manualCommitPending = false;
        setLiveStatus('念念正在思考...', true);
      } else {
        // 服务端自动切分提交的一段音频，可能只是用户的短暂停顿，也可能是噪音误触发。
        // 只有当前没有倒计时在跑时才开始新一轮等待，避免噪音反复把倒计时推后。
        try { state._scheduleBufferWindow && state._scheduleBufferWindow(); } catch(e){}
      }
      return;
    }
    if (t === 'response.audio_transcript.delta' && msg.delta) {
      if (!state.liveAiBubble) { state.liveAiBubble = appendBubble('ai', ''); state.liveAiText = ''; }
      state.liveAiText += msg.delta;
      
    state.liveAiBubble.querySelector('.bubble-text').textContent = state.liveAiText;
    if(document.getElementById('immersiveAiText')) {
      document.getElementById('immersiveAiText').textContent = state.liveAiText;
    }

      scrollBottom();
      return;
    }
    if (t === 'response.audio_transcript.done') {
      if (state.liveAiText) state.history.push({ role:'assistant', content: state.liveAiText });
      state.liveAiBubble = null; state.liveAiText = '';
      return;
    }
    if (t === 'response.audio.delta' && msg.delta) {
      state.aiSpeaking = true;
      try {
        var i16 = base64ToInt16(msg.delta);
        var f32 = int16ToFloat32(i16);
        var sum=0; for(var _i=0; _i<f32.length; _i++) sum+=f32[_i]*f32[_i]; window.aiActiveVolume=Math.sqrt(sum/f32.length); var buf = state.playCtx.createBuffer(1, f32.length, 24000);
        buf.copyToChannel(f32, 0);
        var src = state.playCtx.createBufferSource();
        src.buffer = buf; src.connect(state.playAnalyser || state.playCtx.destination);
        var now = state.playCtx.currentTime;
        var startAt = Math.max(state.playTime, now + 0.02);
        state.activeAudioSources.push(src);
        src.onended = function(){
          var idx = state.activeAudioSources.indexOf(src);
          if (idx !== -1) state.activeAudioSources.splice(idx, 1);
        };
        src.start(startAt);
        state.playTime = startAt + buf.duration;
      } catch(e) { console.warn('[play] failed', e); }
      setLiveStatus('念念在说话...', true);
      return;
    }
    if (t === 'response.audio.done') {
      state.aiSpeaking = false;
      setLiveStatus('请继续说话…（说完后说「我说完了」即可）', true);
      return;
    }
    if (t === 'session.created' || t === 'session.updated') { console.log('[ws]', t); return; }
    if (t === 'error') {
      console.error('[ws] error', msg);
      setLiveStatus('上游错误：' + (msg.error && msg.error.message || msg.message || '未知'), true);
    }
  }

  function cleanupLive(){
    if (state.micStream) { state.micStream.getTracks().forEach(function(t){ t.stop(); }); state.micStream = null; }
    if (state.procNode) { try { state.procNode.disconnect(); } catch(e){} state.procNode = null; }
    if (state.micNode)  { try { state.micNode.disconnect();  } catch(e){} state.micNode  = null; }
    if (state.audioCtx) { try { state.audioCtx.close(); } catch(e){} state.audioCtx = null; }
    if (state._volRAF) { cancelAnimationFrame(state._volRAF); state._volRAF = null; }
    state.activeAudioSources.forEach(function(src){ try { src.onended = null; src.stop(0); } catch(e){} });
    state.activeAudioSources.length = 0;
    if (state.playAnalyser) { try { state.playAnalyser.disconnect(); } catch(e){} state.playAnalyser = null; }
    if (state.playCtx)  { try { state.playCtx.close();  } catch(e){} state.playCtx  = null; }
    if (state.ws) { try { state.ws.close(); } catch(e){} state.ws = null; }
    if (state._clearBufferTimers) { try { state._clearBufferTimers(); } catch(e){} }
    state._commitTurn = null; state._scheduleBufferWindow = null; state._restartBufferWindow = null; state._clearBufferTimers = null; state._stopAiPlayback = null;
    state.liveAiBubble = null; state.liveAiText = ''; state.liveUserBubble = null; state.lastUserText = ''; window.aiActiveVolume=0;
  }
  function stopLiveMode(){
    cleanupLive();
    setLiveStatus('', false);
    var btn = $('agentVoice'); if (btn) btn.classList.remove('live');
    setStatus('在线 · 随时倾听');
  }

  function switchMode(mode, silent){
    if (state.mode === mode) return;
    var prev = state.mode;
    state.mode = mode;
    var bT = $('modeText'), bL = $('modeLive');
    if (bT) bT.classList.toggle('active', mode === 'text');
    if (bL) bL.classList.toggle('active', mode === 'live');
    if (prev === 'live') stopLiveMode();
    if (prev === 'text' && state.isRecording) stopHoldRecording();
    if (mode === 'live') startLiveMode();
    else if (!silent) { setLiveStatus('', false); setStatus('在线 · 随时倾听'); }
  }

  // ─── 顶部账号条 ─────────────────────────────────────────────────
  function renderTopnav(){
    var bar = $('topnavBar'); if (!bar) return;
    var u = window.NianAuth && window.NianAuth.getUser();
    if (u) {
      var who = u.display_name || u.email || (u.user_id === 'owner' ? '主理人' : '用户');
      var ownerTag = u.is_owner ? ' <b>·OWNER</b>' : '';
      bar.innerHTML =
        '<span class="who">你好，<b>' + escHtml(who) + '</b>' + ownerTag + '</span>' +
        '<a href="/static/library.html" title="我的资料库">资料库</a>' +
        '<button id="logoutBtn" type="button">退出</button>';
      var lb = $('logoutBtn');
      if (lb) lb.addEventListener('click', function(){ window.NianAuth.logout(); });
    } else {
      bar.innerHTML =
        '<a href="/static/login.html">登录</a>' +
        '<a href="/static/login.html#code" style="background:linear-gradient(135deg,#C4964A,#E8C57A);color:#fff;border:none">访问码</a>';
    }
  }

  // ─── 纪念对象选择 ───────────────────────────────────────────────
  var memorials = [];
  async function loadMemorials(){
    if (!window.NianAuth || !window.NianAuth.isAuthed()) return;
    try {
      var r = await window.NianAuth.fetch('/api/memorials');
      if (!r.ok) return;
      var data = await r.json();
      memorials = data.memorials || [];
      var bar = $('activeMemBar'); if (bar) bar.style.display = 'flex';
      var sel = $('memSelect'); if (!sel) return;
      sel.innerHTML = '';
      if (memorials.length === 0) {
        // 自动创建一个默认对象
        var m = await createMemorial('Ta');
        if (m) { memorials = [m]; }
      }
      for (var i=0; i<memorials.length; i++) {
        var m = memorials[i];
        var opt = document.createElement('option');
        opt.value = m.memorial_id;
        opt.textContent = (m.name || '未命名') + (m.relation ? ' · ' + m.relation : '');
        sel.appendChild(opt);
      }
      var cur = window.NianAuth.getActiveMemorialId();
      if (!cur || !memorials.some(function(x){ return x.memorial_id === cur; })) {
        cur = memorials[0].memorial_id;
        window.NianAuth.setActiveMemorialId(cur);
      }
      sel.value = cur;
      sel.addEventListener('change', function(){
        window.NianAuth.setActiveMemorialId(sel.value);
        state.history = []; // 切换对象 → 清空上下文
        $('agentMessages').innerHTML = '';
        showToast('已切换到 ' + sel.options[sel.selectedIndex].text, 1800);
        triggerGreet();
      });
      refreshPanelPersons();
    } catch(e){ console.warn('[memorials] load', e); }
  }

  async function createMemorial(name){
    try {
      var r = await window.NianAuth.fetch('/api/memorials', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ name: name, relation:'', note:'' })
      });
      if (!r.ok) return null;
      var d = await r.json();
      return d.memorial;
    } catch(e){ return null; }
  }

  // ─── 文件上传 ───────────────────────────────────────────────────
  var pendingFile = null;
  function openUploadModal(file){
    pendingFile = file;
    var prev = $('uploadPreview');
    var icon = '[文件]';
    if (/^image\//.test(file.type)) icon = '[图片]';
    else if (/^audio\//.test(file.type)) icon = '[音频]';
    else if (/^video\//.test(file.type)) icon = '[视频]';
    var size = (file.size/1024).toFixed(1) + ' KB';
    if (file.size > 1024*1024) size = (file.size/1024/1024).toFixed(1) + ' MB';
    prev.innerHTML = '<span class="ic">' + icon + '</span><div><div style="font-weight:600">' + escHtml(file.name) + '</div><div style="color:#8a7654;font-size:.78rem">' + size + '</div></div>';
    $('uploadDesc').value = '';
    $('uploadModal').classList.add('show');
    setTimeout(function(){ $('uploadDesc').focus(); }, 100);
  }
  function closeUploadModal(){
    $('uploadModal').classList.remove('show');
    pendingFile = null;
    var fi = $('agentFileInput'); if (fi) fi.value = '';
  }
  async function confirmUpload(){
    if (!pendingFile) return;
    if (!window.NianAuth || !window.NianAuth.isAuthed()) {
      alert('请先登录后再上传文件'); closeUploadModal(); return;
    }
    var mid = window.NianAuth.getActiveMemorialId();
    if (!mid) { alert('请先选择或创建一个纪念对象'); return; }
    var desc = $('uploadDesc').value.trim();
    var btn = $('uploadConfirm'); btn.disabled = true; btn.textContent = '上传中...';
    try {
      var form = new FormData();
      form.append('file', pendingFile);
      form.append('description', desc);
      var r = await window.NianAuth.fetch('/api/memorials/' + mid + '/upload', { method:'POST', body: form });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      var d = await r.json();
      var asset = d.asset || {};
      var tags = (asset.tags || []).slice(0,4).join('、');
      appendBubble('user', '我上传了：' + pendingFile.name + (desc ? '\n' + desc : ''));
      appendBubble('ai', '我把这份资料收下了。' + (tags ? '我读到了：' + tags + '。' : '') + ' 这些内容已经存进 Ta 的资料库里了，我们继续聊。');
      showToast('已加入资料库 · 自动打标签' + (tags ? '：' + tags : ''), 3200);
      closeUploadModal();
    } catch(e){
      console.error(e);
      alert('上传失败：' + e.message);
      btn.disabled = false; btn.textContent = '上传';
    }
  }

  // ─── 新建纪念对象 ───────────────────────────────────────────────
  function openNewMemModal(){
    $('newMemName').value = '';
    $('newMemModal').classList.add('show');
    setTimeout(function(){ $('newMemName').focus(); }, 100);
  }
  function closeNewMemModal(){ $('newMemModal').classList.remove('show'); }
  async function confirmNewMem(){
    var name = $('newMemName').value.trim();
    if (!name) { alert('请填写称呼'); return; }
    var btn = $('newMemConfirm'); btn.disabled = true; btn.textContent = '创建中...';
    try {
      var m = await createMemorial(name);
      if (!m) throw new Error('创建失败');
      memorials.push(m);
      var sel = $('memSelect');
      var opt = document.createElement('option');
      opt.value = m.memorial_id; opt.textContent = m.name;
      sel.appendChild(opt);
      sel.value = m.memorial_id;
      window.NianAuth.setActiveMemorialId(m.memorial_id);
      state.history = [];
      $('agentMessages').innerHTML = '';
      closeNewMemModal();
      showToast('已建立「' + m.name + '」的档案，开始聊吧', 2400);
      triggerGreet();
    } catch(e){
      alert(e.message);
    } finally {
      btn.disabled = false; btn.textContent = '创建';
    }
  }

  function triggerGreet(){
    if (state.mode !== 'text') return;
    setTimeout(function(){
      var sel = $('memSelect');
      var name = (sel && sel.options[sel.selectedIndex]) ? sel.options[sel.selectedIndex].text.split(' · ')[0] : '';
      var hi = name && name !== 'Ta' ? '你好，我想和你聊聊 ' + name : '你好，今天有什么想聊的吗？';
      if (state.mode === 'text') sendMessage(hi);
    }, 600);
  }

  // ─── 初始化 ─────────────────────────────────────────────────────
  function init(){
    var inp = $('agentInput');
    if (!inp) return;

    renderTopnav();
    loadMemorials();

    var agentSendBtn = $('agentSend');
    if (agentSendBtn) agentSendBtn.addEventListener('click', function(){
      var t = inp.value.trim();
      if (!t) return;
      inp.value = '';
      sendMessage(t);
    });
    inp.addEventListener('keydown', function(e){
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('agentSend').click(); }
    });

    var vBtn = $('agentVoice');
    if (vBtn) {
      // 实时模式下点击 = 退出实时
      vBtn.addEventListener('click', function(e){
        if (state.mode === 'live') { e.preventDefault(); switchMode('text'); }
      });
      // 文字模式下：按住开始 / 松开停止
      function startHold(e){
        if (state.mode !== 'text') return;
        e.preventDefault();
        startHoldRecording();
      }
      function endHold(e){
        if (state.mode !== 'text') return;
        if (state.isRecording) { e.preventDefault(); stopHoldRecording(); }
      }
      vBtn.addEventListener('mousedown', startHold);
      vBtn.addEventListener('touchstart', startHold, { passive: false });
      vBtn.addEventListener('mouseup', endHold);
      vBtn.addEventListener('mouseleave', endHold);
      vBtn.addEventListener('touchend', endHold);
      vBtn.addEventListener('touchcancel', endHold);
      // 防止拖动选中
      vBtn.addEventListener('contextmenu', function(e){ e.preventDefault(); });
    }

    // 上传按钮
    var uBtn = $('agentUpload'), fInp = $('agentFileInput');
    if (uBtn && fInp) {
      uBtn.addEventListener('click', function(){
        if (!window.NianAuth || !window.NianAuth.isAuthed()) {
          if (confirm('上传文件需要先登录。是否前往登录？')) location.href = '/static/login.html';
          return;
        }
        fInp.click();
      });
      fInp.addEventListener('change', function(){
        if (fInp.files && fInp.files[0]) openUploadModal(fInp.files[0]);
      });
    }

    // 主界面光球聊天框右侧 + 号上传按钮 → 类型选择气泡
    var immUploadBtn  = $('immersiveUploadBtn');
    var immTypePicker = $('immTypePicker');
    var immImageInput = $('immersiveImageInput');
    var immAudioInput = $('immersiveAudioInput');

    function closeImmPicker(){ if (immTypePicker) immTypePicker.classList.remove('show'); }

    if (immUploadBtn && immTypePicker) {
      immUploadBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        if (!window.NianAuth || !window.NianAuth.isAuthed()) {
          if (confirm('上传文件需要先登录，是否前往登录？')) location.href = '/static/login.html';
          return;
        }
        immTypePicker.classList.toggle('show');
      });
      // 点外部关闭
      document.addEventListener('click', function(e){
        if (!$('immUploadWrap').contains(e.target)) closeImmPicker();
      });
    }
    // 选择「语音」
    var immPickAudio = $('immPickAudio');
    if (immPickAudio && immAudioInput) {
      immPickAudio.addEventListener('click', function(){
        closeImmPicker();
        immAudioInput.click();
      });
      immAudioInput.addEventListener('change', function(){
        if (immAudioInput.files && immAudioInput.files[0]) {
          openUploadModal(immAudioInput.files[0]);
          immAudioInput.value = '';
        }
      });
    }
    // 选择「图片」
    var immPickImage = $('immPickImage');
    if (immPickImage && immImageInput) {
      immPickImage.addEventListener('click', function(){
        closeImmPicker();
        immImageInput.click();
      });
      immImageInput.addEventListener('change', function() {
        if (immImageInput.files && immImageInput.files[0]) {
          openUploadModal(immImageInput.files[0]);
          immImageInput.value = '';
        }
      });
    }
    var uc = $('uploadCancel'), uok = $('uploadConfirm');
    if (uc)  uc.addEventListener('click', closeUploadModal);
    if (uok) uok.addEventListener('click', confirmUpload);

    // 新建对象
    var nmBtn = $('newMemBtn');
    if (nmBtn) nmBtn.addEventListener('click', openNewMemModal);
    var nmC = $('newMemCancel'), nmOK = $('newMemConfirm');
    if (nmC)  nmC.addEventListener('click', closeNewMemModal);
    if (nmOK) nmOK.addEventListener('click', confirmNewMem);
    var nmInput = $('newMemName');
    if (nmInput) nmInput.addEventListener('keydown', function(e){
      if (e.key === 'Enter') { e.preventDefault(); confirmNewMem(); }
    });

    var mT = $('modeText'), mL = $('modeLive');
    if (mT) mT.addEventListener('click', function(){ switchMode('text'); });
    if (mL) mL.addEventListener('click', function(){ switchMode('live'); });

    // 文字模式自动问候
    if (!state.hasGreeted) {
      state.hasGreeted = true;
      setTimeout(function(){
        if (state.mode === 'text') sendMessage('你好，今天有什么想聊的吗？');
      }, 800);
    }

    // ChatGPT 默认对话按钮
    var chatBtn = document.getElementById('defaultChatBtn');
    if (chatBtn) {
        chatBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            if(!AgentSession.isConnected) {
                console.log("Connect via default chat button");
                startSession();
            } else {
                AgentSession.ws.close();
            }
        });
    }
    
    // Add enter key and click handler for immersive text input
    var immersiveTextInput = document.getElementById('immersiveTextInput');
    var immersiveSendBtn = document.getElementById('immersiveSendBtn');

    function sendImmersiveText() {
      if (!immersiveTextInput) return;
      var text = immersiveTextInput.value.trim();
      if (!text) return;
      immersiveTextInput.value = '';
      sendMessage(text);
    }

    if (immersiveSendBtn) {
        immersiveSendBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            sendImmersiveText();
        });
    }

    if (immersiveTextInput) {
        immersiveTextInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendImmersiveText();
            }
        });
    }

    // 录音状态重置
    var origPlaceholder = inp.placeholder || '';
    var resetRecordingState = function(){
      state.isRecording = false;
      if (vBtn) { vBtn.classList.remove('recording'); vBtn.title = '按住说话'; }
      inp.classList.remove('is-listening');
      inp.placeholder = origPlaceholder;
    };
    // 处理页面离开/刷新
    window.addEventListener('beforeunload', function(){
      if (state.mode === 'live') stopLiveMode();
      else if (state.isRecording) stopHoldRecording();
    });
    initSessionPanel();
  }


  // ─── Session Panel ──────────────────────────────────────────────

  function refreshPanelHistory() {
    var hist = document.getElementById('sessionHistory');
    if (!hist) return;
    hist.innerHTML = '';
    if (!state.history || state.history.length === 0) {
      hist.innerHTML = '<div class="session-history-empty">' + '\u6682\u65e0\u5bf9\u8bdd\u8bb0\u5f55' + '</div>';
      return;
    }
    state.history.slice(-30).forEach(function(m) {
      var d = document.createElement('div');
      d.className = 'session-history-msg ' + (m.role === 'user' ? 'user' : 'ai');
      var txt = (m.content || '').replace(/<[^>]+>/g, '');
      if (txt.length > 160) txt = txt.slice(0, 160) + '...';
      d.textContent = txt;
      hist.appendChild(d);
    });
    hist.scrollTop = hist.scrollHeight;
  }

  function refreshPanelPersons() {
    var sel = document.getElementById('sessionMemSelect');
    if (!sel) return;
    var cur = window.NianAuth && window.NianAuth.getActiveMemorialId ? window.NianAuth.getActiveMemorialId() : null;
    sel.innerHTML = '';
    if (!memorials || !memorials.length) {
      var opt = document.createElement('option');
      opt.textContent = '\u6682\u65e0\u4eba\u7269';
      sel.appendChild(opt);
      return;
    }
    memorials.forEach(function(m) {
      var opt = document.createElement('option');
      opt.value = m.memorial_id;
      opt.textContent = (m.name || '\u672a\u547d\u540d') + (m.relation ? ' \u00b7 ' + m.relation : '');
      sel.appendChild(opt);
    });
    if (cur) sel.value = cur;
  }

  function initSessionPanel() {
    var panel = document.getElementById('sessionPanel');
    var openBtn = document.getElementById('immersiveSessionBtn');
    var closeBtn = document.getElementById('sessionPanelClose');
    if (!panel || !openBtn) return;

    function openPanel() {
      panel.classList.add('open');
      refreshPanelHistory();
      refreshPanelPersons();
    }
    function closePanel() { panel.classList.remove('open'); }

    openBtn.addEventListener('click', function(e) { e.stopPropagation(); openPanel(); });
    if (closeBtn) closeBtn.addEventListener('click', closePanel);
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' && panel.classList.contains('open')) closePanel();
    });
    document.addEventListener('click', function(e) {
      if (panel.classList.contains('open') && !panel.contains(e.target) && !openBtn.contains(e.target)) closePanel();
    });

    // Person switch
    var spSel = document.getElementById('sessionMemSelect');
    if (spSel) {
      spSel.addEventListener('change', function() {
        var mid = spSel.value;
        if (window.NianAuth && window.NianAuth.setActiveMemorialId) window.NianAuth.setActiveMemorialId(mid);
        var mainSel = document.getElementById('memSelect');
        if (mainSel) mainSel.value = mid;
        state.history = [];
        var msgs = document.getElementById('agentMessages'); if (msgs) msgs.innerHTML = '';
        showToast('\u5df2\u5207\u6362\u5230 ' + (spSel.options[spSel.selectedIndex] ? spSel.options[spSel.selectedIndex].text : ''), 1800);
        triggerGreet();
      });
    }

    // New person
    var spNewBtn = document.getElementById('sessionNewMemBtn');
    if (spNewBtn) spNewBtn.addEventListener('click', function() { closePanel(); openNewMemModal(); });

    // Deep search
    var dsBtn = document.getElementById('sessionSearchBtn');
    var dsInput = document.getElementById('sessionSearchInput');
    var dsExtra = document.getElementById('sessionSearchExtra');
    var dsResult = document.getElementById('sessionSearchResult');

    function doDeepSearch() {
      if (!dsInput) return;
      var q = dsInput.value.trim();
      if (!q) { showToast('\u8bf7\u8f93\u5165\u8981\u641c\u7d22\u7684\u4eba\u7269\u59d3\u540d', 1800); return; }
      var ex = dsExtra ? dsExtra.value.trim() : '';
      if (dsBtn) dsBtn.disabled = true;
      if (dsResult) {
        dsResult.className = 'session-search-result show';
        dsResult.innerHTML = '<div class="session-search-thinking"><span>...</span><span>\u8054\u7f51\u641c\u7d22\u4e2d\uff0c\u7ea6\u952e15\u79d2...</span></div>';
      }
      var headers = { 'Content-Type': 'application/json' };
      var tok = window.NianAuth && window.NianAuth.getToken ? window.NianAuth.getToken() : null;
      if (tok) headers['Authorization'] = 'Bearer ' + tok;
      fetch('/api/intake/deep-search', {
        method: 'POST', headers: headers,
        body: JSON.stringify({ query: q, extra: ex, session_id: null })
      }).then(function(r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(function(data) {
        if (dsBtn) dsBtn.disabled = false;
        var text = (data.organized || data.result || '\u672a\u83b7\u53d6\u5230\u7ed3\u679c').trim();
        if (!dsResult) return;
        dsResult.innerHTML = '';
        dsResult.className = 'session-search-result show';
        var p = document.createElement('p');
        p.style.cssText = 'margin:0;white-space:pre-wrap;font-size:.81rem;color:#3a2f22;line-height:1.7';
        p.textContent = text.length > 600 ? text.slice(0, 600) + '...' : text;
        dsResult.appendChild(p);
        var applyBtn = document.createElement('button');
        applyBtn.textContent = '\u53d1\u9001\u7ed9\u5ff5\u5ff5\u53c2\u8003';
        applyBtn.style.cssText = 'margin-top:10px;padding:7px 0;background:linear-gradient(135deg,#C4964A,#E8C57A);border:none;border-radius:7px;color:#fff;font-size:.82rem;cursor:pointer;width:100%;font-family:inherit';
        applyBtn.addEventListener('click', function() {
          var summary = '\u4ee5\u4e0b\u662f\u5173\u4e8e\u300c' + q + '\u300d\u7684\u80cc\u666f\u8d44\u6599\uff0c\u8bf7\u53c2\u8003\uff1a\n' + text.slice(0, 500);
          sendMessage(summary);
          showToast('\u5df2\u5c06\u641c\u7d22\u8d44\u6599\u53d1\u9001\u7ed9\u5ff5\u5ff5', 2000);
          closePanel();
        });
        dsResult.appendChild(applyBtn);
      }).catch(function(e) {
        if (dsBtn) dsBtn.disabled = false;
        if (dsResult) dsResult.innerHTML = '<p style="color:#c0392b;font-size:.82rem;margin:0">\u641c\u7d22\u5931\u8d25\uff1a' + String(e.message || e) + '</p>';
      });
    }

    if (dsBtn) dsBtn.addEventListener('click', doDeepSearch);
    if (dsInput) dsInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') { e.preventDefault(); doDeepSearch(); }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  // 暴露 sendMessage 给外部 IIFE（会话面板深度搜索发送）
  window._nianSendMessage = function(text) { sendMessage(text); };
})();

// ── Session Panel 独立初始化
(function() {
  function bindSessionPanel() {
    var panel = document.getElementById('sessionPanel');
    var openBtn = document.getElementById('immersiveSessionBtn');
    var closeBtn = document.getElementById('sessionPanelClose');
    if (!panel || !openBtn) { console.warn('[sessionPanel] 元素缺失'); return; }

    function openPanel() { panel.classList.add('open'); }
    function closePanel() { panel.classList.remove('open'); }

    openBtn.addEventListener('click', function(e) { e.stopPropagation(); openPanel(); });
    if (closeBtn) closeBtn.addEventListener('click', closePanel);
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') closePanel();
    });
    document.addEventListener('click', function(e) {
      if (panel.classList.contains('open') && !panel.contains(e.target) && !openBtn.contains(e.target)) closePanel();
    });

    // 人物切换
    var spSel = document.getElementById('sessionMemSelect');
    if (spSel) {
      spSel.addEventListener('change', function() {
        var mid = spSel.value;
        if (window.NianAuth && window.NianAuth.setActiveMemorialId) window.NianAuth.setActiveMemorialId(mid);
        var mainSel = document.getElementById('memSelect');
        if (mainSel) mainSel.value = mid;
        var msgs = document.getElementById('agentMessages'); if (msgs) msgs.innerHTML = '';
      });
    }

    // 深度搜索
    var dsBtn = document.getElementById('sessionSearchBtn');
    var dsInput = document.getElementById('sessionSearchInput');
    var dsExtra = document.getElementById('sessionSearchExtra');
    var dsResult = document.getElementById('sessionSearchResult');

    function doSearch() {
      if (!dsInput) return;
      var q = dsInput.value.trim();
      if (!q) { alert('\u8bf7\u8f93\u5165\u8981\u641c\u7d22\u7684\u4eba\u7269\u59d3\u540d'); return; }
      var ex = dsExtra ? dsExtra.value.trim() : '';
      if (dsBtn) dsBtn.disabled = true;
      if (dsResult) {
        dsResult.className = 'session-search-result show';
        dsResult.innerHTML = '<div class="session-search-thinking"><span>...</span><span>\u8054\u7f51\u641c\u7d22\u4e2d\uff0c\u7ea6\u952e15\u79d2...</span></div>';
      }
      var headers = { 'Content-Type': 'application/json' };
      var tok = window.NianAuth && window.NianAuth.getToken ? window.NianAuth.getToken() : null;
      if (tok) headers['Authorization'] = 'Bearer ' + tok;
      // 获取当前人物的 memorial_id 和 user_id
      var mid = window.NianAuth && window.NianAuth.getActiveMemorialId ? window.NianAuth.getActiveMemorialId() : null;
      var spSel2 = document.getElementById('sessionMemSelect');
      if (!mid && spSel2) mid = spSel2.value || null;
      var userInfo = window.NianAuth && window.NianAuth.getUser ? window.NianAuth.getUser() : null;
      var uid = userInfo ? (userInfo.user_id || userInfo.id || null) : null;
      fetch('/api/intake/deep-search', {
        method: 'POST', headers: headers,
        body: JSON.stringify({ query: q, extra: ex, session_id: null, memorial_id: mid || null, user_id: uid || null })
      }).then(function(r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(function(data) {
        if (dsBtn) dsBtn.disabled = false;
        var text = (data.organized || data.result || '\u672a\u83b7\u53d6\u5230\u7ed3\u679c').trim();
        if (!dsResult) return;
        dsResult.innerHTML = '';
        dsResult.className = 'session-search-result show';
        // 来源标签
        if (data.model) {
          var tag = document.createElement('div');
          tag.style.cssText = 'font-size:.72rem;margin-bottom:8px;padding:2px 8px;border-radius:10px;display:inline-block;'
            + (data.fallback
              ? 'background:rgba(180,140,60,.15);color:#8a6820;'
              : 'background:rgba(60,160,100,.15);color:#2a7a50;');
          tag.textContent = data.fallback ? '\u77e5\u8bc6\u5e93' : '\u8054\u7f51\u641c\u7d22\uff08' + data.model + '\uff09';
          dsResult.appendChild(tag);
        }
        // 归档提示
        if (data.dossier_updated) {
          var archiveNote = document.createElement('div');
          archiveNote.style.cssText = 'font-size:.72rem;margin-bottom:8px;margin-left:4px;color:#5a9a72;display:inline-block;margin-left:6px;';
          archiveNote.textContent = '\u5df2\u5f52\u6863\u5e76\u540c\u6b65\u5230\u8d44\u6599\u5e93';
          dsResult.appendChild(archiveNote);
          dsResult.appendChild(document.createElement('br'));
        }
        // 提取字段速览
        if (data.fields && Object.keys(data.fields).length > 0) {
          var f = data.fields;
          var chips = [];
          if (f.deceased_name) chips.push(f.deceased_name);
          if (f.birth_date) chips.push(f.birth_date);
          if (f.occupation) chips.push(f.occupation);
          if (f.quotes && f.quotes.length) chips.push(f.quotes.length + '\u6761\u91d1\u53e5');
          if (f.objects && f.objects.length) chips.push(f.objects.length + '\u4ef6\u7269\u54c1');
          if (f.core_memories && f.core_memories.length) chips.push(f.core_memories.length + '\u6761\u6838\u5fc3\u8bb0\u5fc6');
          if (chips.length) {
            var chipRow = document.createElement('div');
            chipRow.style.cssText = 'display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px;';
            chips.forEach(function(c) {
              var ch = document.createElement('span');
              ch.style.cssText = 'background:rgba(90,120,80,.1);color:#3a5a30;font-size:.7rem;padding:1px 7px;border-radius:8px;';
              ch.textContent = c;
              chipRow.appendChild(ch);
            });
            dsResult.appendChild(chipRow);
          }
        }
        // 全文展示（可滚动，不截断）
        var scrollBox = document.createElement('div');
        scrollBox.style.cssText = 'max-height:260px;overflow-y:auto;margin-bottom:6px;padding-right:4px;';
        var p = document.createElement('p');
        p.style.cssText = 'margin:0;white-space:pre-wrap;font-size:.81rem;color:#3a2f22;line-height:1.7';
        p.textContent = text;
        scrollBox.appendChild(p);
        dsResult.appendChild(scrollBox);
        var applyBtn = document.createElement('button');
        applyBtn.textContent = '\u53d1\u9001\u7ed9\u5ff5\u5ff5\u53c2\u8003';
        applyBtn.style.cssText = 'margin-top:10px;padding:7px 0;background:linear-gradient(135deg,#C4964A,#E8C57A);border:none;border-radius:7px;color:#fff;font-size:.82rem;cursor:pointer;width:100%;font-family:inherit';
        applyBtn.addEventListener('click', function() {
          var summary = '\u4ee5\u4e0b\u662f\u5173\u4e8e\u300c' + q + '\u300d\u7684\u80cc\u666f\u8d44\u6599\uff0c\u8bf7\u53c2\u8003\uff1a\n' + text.slice(0, 800);
          var agentInp = document.getElementById('agentInput');
          var agentSend = document.getElementById('agentSend');
          if (agentInp && agentSend) {
            agentInp.value = summary;
            agentSend.click();
          } else if (window._nianSendMessage) {
            window._nianSendMessage(summary);
          }
          closePanel();
        });
        dsResult.appendChild(applyBtn);
      }).catch(function(e) {
        if (dsBtn) dsBtn.disabled = false;
        if (dsResult) dsResult.innerHTML = '<p style="color:#c0392b;font-size:.82rem;margin:0">\u641c\u7d22\u5931\u8d25\uff1a' + String(e.message || e) + '</p>';
      });
    }

    if (dsBtn) dsBtn.addEventListener('click', doSearch);
    if (dsInput) dsInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') { e.preventDefault(); doSearch(); }
    });

    // ── 上传素材到当前人物资料库 ──
    var upZone  = document.getElementById('sessionUploadZone');
    var upInput = document.getElementById('sessionUploadInput');
    var upList  = document.getElementById('sessionUploadList');

    function _getActiveMid() {
      var mid = spSel && spSel.value;
      if (!mid && window.NianAuth && window.NianAuth.getActiveMemorialId) {
        mid = window.NianAuth.getActiveMemorialId();
      }
      if (!mid) {
        var mainSel = document.getElementById('memSelect');
        if (mainSel) mid = mainSel.value;
      }
      return mid;
    }

    function _uploadOne(mid, file) {
      var item = document.createElement('div');
      item.className = 'session-upload-item';
      var safeName = file.name.length > 32 ? file.name.slice(0, 30) + '…' : file.name;
      item.innerHTML = '<span class="upload-name" title="' + file.name.replace(/"/g, '&quot;') + '">' + safeName + '</span><span class="upload-status">上传中…</span>';
      if (upList) upList.prepend(item);
      var statusEl = item.querySelector('.upload-status');

      var fd = new FormData();
      fd.append('file', file);
      fd.append('description', '');

      var headers = {};
      var tok = window.NianAuth && window.NianAuth.getToken ? window.NianAuth.getToken() : null;
      if (tok) headers['Authorization'] = 'Bearer ' + tok;

      fetch('/api/memorials/' + encodeURIComponent(mid) + '/upload', {
        method: 'POST', headers: headers, body: fd
      }).then(function(r) {
        if (!r.ok) return r.text().then(function(t) { throw new Error('HTTP ' + r.status + ' ' + t.slice(0, 80)); });
        return r.json();
      }).then(function(data) {
        item.classList.add('success');
        if (statusEl) statusEl.textContent = '✓ 已入库';
      }).catch(function(e) {
        item.classList.add('error');
        if (statusEl) statusEl.textContent = '✗ ' + (e.message || '失败').slice(0, 28);
      });
    }

    function _handleFiles(files) {
      var mid = _getActiveMid();
      if (!mid) { alert('请先在上方选择或新建一个人物'); return; }
      if (!files || !files.length) return;
      Array.prototype.forEach.call(files, function(f) { _uploadOne(mid, f); });
    }

    if (upZone && upInput) {
      upZone.addEventListener('click', function() {
        var mid = _getActiveMid();
        if (!mid) { alert('请先在上方选择或新建一个人物'); return; }
        upInput.click();
      });
      upInput.addEventListener('change', function() {
        _handleFiles(upInput.files);
        upInput.value = '';
      });
      // 拖拽上传
      ['dragenter', 'dragover'].forEach(function(ev) {
        upZone.addEventListener(ev, function(e) {
          e.preventDefault(); e.stopPropagation();
          upZone.classList.add('dragover');
        });
      });
      ['dragleave', 'drop'].forEach(function(ev) {
        upZone.addEventListener(ev, function(e) {
          e.preventDefault(); e.stopPropagation();
          upZone.classList.remove('dragover');
        });
      });
      upZone.addEventListener('drop', function(e) {
        if (e.dataTransfer && e.dataTransfer.files) _handleFiles(e.dataTransfer.files);
      });
    }

    console.log('[sessionPanel] \u72ec\u7acb\u521d\u59cb\u5316\u5b8c\u6210\u2705');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindSessionPanel);
  else bindSessionPanel();
})();

// 沉浸式语音按钮：仅做 DOM 层桥接，复用现有 modeLive / agentVoice 逻辑
(function(){
  function bind(){
    var immersiveBtn = document.getElementById('immersiveVoiceBtn');
    if (!immersiveBtn) return;
    var aiText = document.getElementById('immersiveAiText');
    var isLive = false;
    immersiveBtn.addEventListener('click', function(){
      var modeLive = document.getElementById('modeLive');
      var modeText = document.getElementById('modeText');
      if (!isLive) {
        if (modeLive) modeLive.click();
        immersiveBtn.classList.add('recording');
        if (aiText) aiText.textContent = '念念正在倾听…';
        isLive = true;
      } else {
        if (modeText) modeText.click();
        immersiveBtn.classList.remove('recording');
        if (aiText) aiText.textContent = '已结束。再次点击重新开始。';
        isLive = false;
      }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind);
  else bind();
})();

