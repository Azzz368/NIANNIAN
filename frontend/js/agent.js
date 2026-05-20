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

    setLiveStatus('正在连接 Qwen-Omni-Realtime...', true);
    var wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var ws = new WebSocket(wsProto + '//' + location.host + '/api/agent/realtime');
    state.ws = ws;

    ws.onopen = function(){
      setLiveStatus('已连接，请开始说话...', true);
      setStatus('实时对话中');
      if (btn) btn.classList.add('live');
      try {
        ws.send(JSON.stringify({
          type: 'response.create',
          response: { modalities: ['audio','text'], instructions: '用一句温柔的话开场，问候用户、并询问 ta 想聊谁。' }
        }));
      } catch(e){}
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
    if (t === 'conversation.item.input_audio_transcription.completed' && msg.transcript) {
      appendBubble('user', msg.transcript);
      return;
    }
    if (t === 'input_audio_buffer.speech_started') { setLiveStatus('听到你了，正在听...', true); return; }
    if (t === 'input_audio_buffer.speech_stopped') { setLiveStatus('念念正在思考...', true); return; }
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
    if (t === 'response.audio.delta' && msg.delta) {
      try {
        var i16 = base64ToInt16(msg.delta);
        var f32 = int16ToFloat32(i16);
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
    if (t === 'response.audio.done') { setLiveStatus('请继续说话...', true); return; }
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
    if (state.playCtx)  { try { state.playCtx.close();  } catch(e){} state.playCtx  = null; }
    if (state.ws) { try { state.ws.close(); } catch(e){} state.ws = null; }
    state.liveAiBubble = null; state.liveAiText = ''; state.liveUserBubble = null;
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
    var icon = '📄';
    if (/^image\//.test(file.type)) icon = '🖼';
    else if (/^audio\//.test(file.type)) icon = '🎵';
    else if (/^video\//.test(file.type)) icon = '🎬';
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
      appendBubble('user', '📎 我上传了：' + pendingFile.name + (desc ? '\n' + desc : ''));
      appendBubble('ai', '我把这份资料收下了。' + (tags ? '我读到了：' + tags + '。' : '') + ' 这些内容已经存进 Ta 的资料库里了，我们继续聊。');
      showToast('📎 已加入资料库 · 自动打标签' + (tags ? '：' + tags : ''), 3200);
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
      var hi = name && name !== 'Ta' ? '你好，我想和你聊聊 ' + name : '你好，我想制作一部追思影像';
      if (state.mode === 'text') sendMessage(hi);
    }, 600);
  }

  // ─── 初始化 ─────────────────────────────────────────────────────
  function init(){
    var inp = $('agentInput');
    if (!inp) return;

    renderTopnav();
    loadMemorials();

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
        if (state.mode === 'text') sendMessage('你好，我想制作一部追思影像');
      }, 800);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
