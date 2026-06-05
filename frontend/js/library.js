// library.js — 资料库前端
(function () {
  'use strict';
  if (!NianAuth.requireAuth()) return;

  var state = { memorials: [], currentId: null, dossier: null, meta: null, assets: [] };
  var assetState = { selectMode: false, selected: new Set() };

  function $(id) { return document.getElementById(id); }

  // 顶部用户信息
  (function () {
    var u = NianAuth.getUser() || {};
    $('libUser').innerHTML = (u.display_name || u.email || '访客') + (u.is_owner ? ' · 主人' : '') +
      ' <span class="logout">退出</span>';
    $('libUser').querySelector('.logout').onclick = function () { NianAuth.logout(); };
  })();

  // ── 列表 ──
  async function loadMemorials() {
    var r = await NianAuth.fetch('/api/memorials');
    var d = await r.json();
    state.memorials = d.memorials || [];
    renderList();
    var activeId = NianAuth.getActiveMemorialId() || (state.memorials[0] && state.memorials[0].memorial_id);
    if (activeId) selectMemorial(activeId);
  }

  function renderList() {
    var ul = $('memList'); ul.innerHTML = '';
    state.memorials.forEach(function (m) {
      var li = document.createElement('li');
      li.innerHTML = '<div class="n">' + escapeHtml(m.name) + '</div><div class="r">' + escapeHtml(m.relation || '—') + '</div>';
      if (m.memorial_id === state.currentId) li.classList.add('active');
      li.onclick = function () { selectMemorial(m.memorial_id); };
      ul.appendChild(li);
    });
  }

  async function selectMemorial(mid) {
    state.currentId = mid;
    NianAuth.setActiveMemorialId(mid);
    renderList();
    var r = await NianAuth.fetch('/api/memorials/' + mid);
    var d = await r.json();
    state.meta = d.meta; state.dossier = d.dossier || {}; state.assets = d.assets || [];
    renderDetail();
  }

  function renderDetail() {
    $('emptyHint').style.display = 'none';
    $('detailBody').style.display = 'block';
    $('dName').textContent = state.meta.name || '未命名';
    $('dRelation').textContent = state.meta.relation || '';
    $('dIntent').textContent = intentLabel(state.meta.product_intent || (state.dossier.product_intent && state.dossier.product_intent.primary)) || '方向未定';
    $('dUpdated').textContent = '更新于 ' + (state.meta.updated_at || '').replace('T', ' ');
    bindDossierToInputs();
    renderMemories();
    renderAssets();
    loadConversations();
    $('quotesArea').value = (state.dossier.quotes || []).join('\n');
    $('objectsArea').value = (state.dossier.objects || []).join('\n');
  }

  function intentLabel(v) {
    return ({ video: '追思影像', biography: '个人传记', digital_human: '数字人' })[v] || '';
  }

  // ── 数据绑定 ──
  function getByPath(o, path) {
    var parts = path.split('.'), cur = o;
    for (var i = 0; i < parts.length; i++) { if (cur == null) return ''; cur = cur[parts[i]]; }
    return cur == null ? '' : cur;
  }
  function setByPath(o, path, val) {
    var parts = path.split('.'), cur = o;
    for (var i = 0; i < parts.length - 1; i++) { if (!cur[parts[i]] || typeof cur[parts[i]] !== 'object') cur[parts[i]] = {}; cur = cur[parts[i]]; }
    cur[parts[parts.length - 1]] = val;
  }
  function bindDossierToInputs() {
    document.querySelectorAll('[data-bind]').forEach(function (el) {
      var v = getByPath(state.dossier, el.dataset.bind);
      if (Array.isArray(v)) v = v.join(', ');
      if (v === true) v = 'true';
      if (v === false) v = 'false';
      el.value = v == null ? '' : v;
    });
  }
  function readInputsToDossier() {
    document.querySelectorAll('[data-bind]').forEach(function (el) {
      var path = el.dataset.bind; var raw = el.value;
      // 数组字段
      if (/(locations|keywords|habits|catchphrases)$/.test(path)) {
        var arr = raw.split(/[\n,，]/).map(function (s) { return s.trim(); }).filter(Boolean);
        setByPath(state.dossier, path, arr);
      } else if (path.indexOf('permissions.') === 0) {
        setByPath(state.dossier, path, raw === '' ? null : raw === 'true');
      } else {
        setByPath(state.dossier, path, raw);
      }
    });
    // 记忆
    var memories = [];
    document.querySelectorAll('#memoriesList li').forEach(function (li) {
      memories.push({
        title: li.querySelector('.title-input').value,
        content: li.querySelector('.body-input').value,
        tags: [],
      });
    });
    state.dossier.memories = memories;
    state.dossier.quotes = $('quotesArea').value.split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
    state.dossier.objects = $('objectsArea').value.split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
  }

  // ── 记忆卡片 ──
  function renderMemories() {
    var ul = $('memoriesList'); ul.innerHTML = '';
    (state.dossier.memories || []).forEach(function (m, idx) {
      ul.appendChild(buildMemCard(m, idx));
    });
  }
  function buildMemCard(m, idx) {
    var li = document.createElement('li');
    li.innerHTML =
      '<button class="del">删除</button>' +
      '<input class="title-input" value="' + escapeAttr(m.title || '') + '" placeholder="记忆标题">' +
      '<textarea class="body-input" placeholder="记忆内容...">' + escapeHtml(m.content || '') + '</textarea>';
    li.querySelector('.del').onclick = function () { li.remove(); };
    return li;
  }
  $('btnAddMem').addEventListener('click', function () {
    $('memoriesList').appendChild(buildMemCard({}, 0));
  });

  // ── 素材 ──
  function renderAssets() {
    // 声音工坊入口：附带当前 memorial_id，并展示统计
    var entry = $('voiceStudioEntry');
    if (entry && state.currentId) {
      entry.href = '/static/voice_studio.html?mid=' + encodeURIComponent(state.currentId);
      var audioCount = (state.assets || []).filter(function (a) { return a.kind === 'audio'; }).length;
      var voiceMeta = $('voiceStudioMeta');
      if (voiceMeta) voiceMeta.textContent = audioCount + ' 个音频样本 · 点击进入工坊管理克隆';
    }
    var ul = $('assetsList'); ul.innerHTML = '';
    if (!state.assets.length) {
      ul.innerHTML = '<li style="grid-column:1/-1;color:#8a7654;padding:30px;text-align:center">还没有素材。在聊天页上传后，文件会出现在这里。</li>';
      return;
    }
    state.assets.forEach(function (a) {
      var li = document.createElement('li');
      li.className = 'asset-item';
      li.dataset.assetId = a.asset_id;
      var isSelected = assetState.selected.has(a.asset_id);
      if (isSelected) li.classList.add('selected');

      // 资产 URL 必须带 token（img/audio 不会发 Authorization header）
      var tok = (window.NianAuth && NianAuth.getToken && NianAuth.getToken()) || '';
      var aUrl = a.url + (a.url.indexOf('?') >= 0 ? '&' : '?') + 'token=' + encodeURIComponent(tok);
      var thumb = (a.kind === 'image') ? '<img src="' + aUrl + '" alt="">' : iconForKind(a.kind);
      var tags = (a.tags || []).map(function (t) { return '<span>' + escapeHtml(t) + '</span>'; }).join('');
      li.innerHTML =
        '<div class="asset-select"><input type="checkbox" class="asset-checkbox"' + (isSelected ? ' checked' : '') + '></div>' +
        '<div class="asset-thumb">' + thumb + '</div>' +
        '<div class="asset-name">' + escapeHtml(a.filename || '') + '</div>' +
        '<div class="asset-desc">' + escapeHtml(a.description || a.summary || '') + '</div>' +
        '<div class="asset-tags">' + tags + '</div>';

      var checkbox = li.querySelector('.asset-checkbox');
      checkbox.addEventListener('change', function () {
        if (checkbox.checked) assetState.selected.add(a.asset_id);
        else assetState.selected.delete(a.asset_id);
        li.classList.toggle('selected', checkbox.checked);
        updateAssetActionButton();
      });

      li.addEventListener('click', function (e) {
        if (!assetState.selectMode) return;
        if (e.target === checkbox) return;
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event('change'));
      });

      ul.appendChild(li);
    });
    ul.classList.toggle('select-mode', assetState.selectMode);
    updateAssetActionButton();
  }

  function updateAssetActionButton() {
    var btn = $('btnAssetMode');
    btn.classList.remove('primary', 'danger');
    if (!assetState.selectMode) {
      btn.textContent = '选择';
      btn.classList.add('primary');
    } else if (assetState.selected.size > 0) {
      btn.textContent = '删除';
      btn.classList.add('danger');
    } else {
      btn.textContent = '取消';
      btn.classList.add('primary');
    }
  }

  function setAssetSelectMode(enabled) {
    assetState.selectMode = enabled;
    if (!enabled) assetState.selected.clear();
    renderAssets();
  }

  async function deleteSelectedAssets() {
    if (!state.currentId) return;
    var ids = Array.from(assetState.selected);
    if (!ids.length) return;
    if (!confirm('确认删除选中的素材？此操作不可恢复。')) return;

    for (var i = 0; i < ids.length; i++) {
      var aid = ids[i];
      await NianAuth.fetch('/api/memorials/' + state.currentId + '/assets/' + encodeURIComponent(aid), { method: 'DELETE' });
    }
    assetState.selected.clear();
    assetState.selectMode = false;
    await selectMemorial(state.currentId);
  }

  $('btnAssetMode').addEventListener('click', function () {
    if (!assetState.selectMode) {
      setAssetSelectMode(true);
      return;
    }
    if (assetState.selected.size === 0) {
      setAssetSelectMode(false);
      return;
    }
    deleteSelectedAssets();
  });
  function iconForKind(k) {
    return ({ image: '🖼', audio: '🎵', video: '🎬', document: '📄' })[k] || '📦';
  }

  // ── 对话 ──
  async function loadConversations() {
    try {
      var r = await NianAuth.fetch('/api/memorials/' + state.currentId + '/conversations?limit=300');
      var d = await r.json();
      var box = $('convList');
      if (!d.conversations || !d.conversations.length) {
        box.innerHTML = '<div style="color:#8a7654;text-align:center;padding:30px">还没有对话记录。</div>';
        return;
      }
      box.innerHTML = d.conversations.map(function (c) {
        var role = c.role === 'user' ? '我' : '念念';
        return '<div class="conv-row ' + (c.role === 'user' ? 'user' : '') + '">' +
          '<div class="role">' + role + '</div>' +
          '<div><div class="content">' + escapeHtml(c.content || '') + '</div>' +
          '<div class="ts">' + (c.ts || '') + '</div></div>' +
          '</div>';
      }).join('');
    } catch (e) { console.warn(e); }
  }

  // ── 生成传记 ──
  var bioState = { sid: null, polling: false };

  var btnStartBio = $('btnStartBio');
  if (btnStartBio) {
    btnStartBio.addEventListener('click', async function () {
      if (!state.currentId) { alert('请先选择一位纪念对象'); return; }
      readInputsToDossier();
      try {
        $('bioControl').style.display = 'none';
        $('bioProgress').style.display = 'block';
        $('bioResult').style.display = 'none';
        $('bioProgressLabel').textContent = '正在初始化...';
        $('bioProgressBar').style.width = '0%';

        var user = NianAuth.getUser() || {};
        var r = await NianAuth.fetch('/api/biography/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            sid: null, // 创建新的 session
            form_data: Object.assign({
              user_id: user.user_id || null,
              memorial_id: state.currentId || null,
            }, {
              deceased_name: state.dossier.subject?.name || '',
              relation: state.meta.relation || '',
              birth_date: state.dossier.subject?.birth || '',
              death_date: state.dossier.subject?.passing || '',
              location: (state.dossier.subject?.locations || []).join(', '),
              occupation: state.dossier.subject?.occupation || '',
              personality: state.dossier.personality || {},
              visual_traits: state.dossier.visual_traits || {},
              voice_traits: state.dossier.voice_traits || {},
              memories: state.dossier.memories || [],
              quotes: state.dossier.quotes || [],
              objects: state.dossier.objects || []
            })
          })
        });
        var d = await r.json();
        console.log('[bio] start response', d);
        bioState.sid = d.session_id;

        // 按步骤执行并在每步期间轮询状态，以便前端显示实时进度
        var BIO_STEPS = ['BIO01', 'BIO02', 'BIO03', 'BIO04', 'BIO05'];
        var STEP_LABELS = {
          'BIO01': '素材信息提取',
          'BIO02': '信息审核与去重',
          'BIO03': '时间线重建',
          'BIO04': '生成传记草稿',
          'BIO05': '质量评审与润色'
        };

        var total = BIO_STEPS.length;
        var completed = 0;

        // 开始轮询（会在后台并行查询 /status）
        bioState.polling = true;
        pollBioStatus();

        for (var i = 0; i < BIO_STEPS.length; i++) {
          var step = BIO_STEPS[i];
          $('bioProgressLabel').textContent = STEP_LABELS[step] + '（正在执行...）';
          console.log('[bio] sending step request', { sid: bioState.sid, step: step });

          // 发起单步请求（后端会执行并更新 session 状态）
          var stepRes = await NianAuth.fetch('/api/biography/step/' + step, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sid: bioState.sid })
          });
          console.log('[bio] step response status', stepRes.status, 'step', step);
          var stepData = await stepRes.json();
          console.log('[bio] step response body', stepData);
          if (!stepRes.ok || stepData.error) {
            bioState.polling = false;
            $('bioProgress').style.display = 'none';
            $('bioControl').style.display = 'block';
            throw new Error(stepData.message || ('步骤 ' + step + ' 执行失败'));
          }

          // 该步骤已完成
          completed += 1;
          var prog = completed / total;
          $('bioProgressBar').style.width = (prog * 100) + '%';
          $('bioProgressLabel').textContent = STEP_LABELS[step] + '（已完成） ' + Math.round(prog * 100) + '%';

          // 等待短暂时间，确保状态已落盘并被轮询读取
          await new Promise(function (res) { setTimeout(res, 300); });
        }

        // 全部完成
        bioState.polling = false;
        showBioResult();
      } catch (e) {
        $('bioControl').style.display = 'block';
        $('bioProgress').style.display = 'none';
        alert('启动失败：' + e.message);
      }
    });
  }

  function pollBioStatus() {
    if (!bioState.polling) return;
    NianAuth.fetch('/api/biography/status/' + bioState.sid)
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var progress = typeof d.progress === 'number' ? d.progress : 0;
        var rawStep = d.current_step || '';
        var STEP_LABELS = {
          'BIO01': '素材信息提取',
          'BIO02': '信息审核与去重',
          'BIO03': '时间线重建',
          'BIO04': '生成传记草稿',
          'BIO05': '质量评审与润色'
        };
        var stepLabel = STEP_LABELS[rawStep] || rawStep || '处理中';
        $('bioProgressLabel').textContent = stepLabel + ' (' + Math.round(progress * 100) + '%)';
        $('bioProgressBar').style.width = (progress * 100) + '%';

        if (d.status === 'completed' || d.status === 'failed') {
          if (d.status === 'failed') {
            bioState.polling = false;
            $('bioProgress').style.display = 'none';
            $('bioControl').style.display = 'block';
            alert('生成失败：' + (d.error || '未知错误'));
            return;
          }
          bioState.polling = false;
          showBioResult();
        } else {
          setTimeout(pollBioStatus, 2000);
        }
      })
      .catch(function (e) {
        console.warn('轮询失败：', e);
        if (bioState.polling) setTimeout(pollBioStatus, 3000);
      });
  }

  async function showBioResult() {
    try {
      var r = await NianAuth.fetch('/api/biography/result/' + bioState.sid);
      var d = await r.json();
      $('bioProgress').style.display = 'none';
      $('bioResult').style.display = 'block';
      var bioText = d.biography_final || d.biography_markdown || '（无内容）';

      // 简单的 Markdown -> HTML 转换（保留段落与换行），再直接渲染为 HTML
      function mdToHtml(txt) {
        if (!txt) return '';
        var lines = txt.split('\n');
        var html = '';
        var para = [];

        function flushParagraph() {
          if (!para.length) return;
          html += '<p>' + para.join('<br>') + '</p>';
          para = [];
        }

        function pushText(line) {
          para.push(escapeHtml(line));
        }

        lines.forEach(function (line) {
          var headingMatch = line.match(/^\s*#{1,6}\s*(.*)$/);
          if (headingMatch && headingMatch[1].trim()) {
            flushParagraph();
            html += '<h2 class="bio-title">' + escapeHtml(headingMatch[1].trim()) + '</h2>';
            return;
          }
          if (/^\s*$/.test(line)) {
            flushParagraph();
            return;
          }

          var imageMatch = line.match(/^\s*!\[([^\]]*)\]\(([^)]+)\)\s*$/);
          if (imageMatch) {
            flushParagraph();
            var rawAlt = imageMatch[1].trim();
            var imgAlt = escapeHtml(rawAlt || '');
            var imgSrc = escapeHtml(imageMatch[2].trim());
            html += '<div class="bio-image"><img src="' + imgSrc + '" alt="' + imgAlt + '"></div>';
            if (rawAlt) {
              html += '<div class="bio-image-caption">' + imgAlt + '</div>';
            }
            return;
          }

          pushText(line);
        });
        flushParagraph();
        return html;
      }

      $('bioContent').innerHTML = '<div class="bio-html">' +
        mdToHtml(bioText) + '</div>';
      bioState.finalContent = bioText;
    } catch (e) {
      alert('获取结果失败：' + e.message);
      $('bioProgress').style.display = 'none';
      $('bioControl').style.display = 'block';
    }
  }

  var btnCancelBio = $('btnCancelBio');
  if (btnCancelBio) {
    btnCancelBio.addEventListener('click', function () {
      bioState.polling = false;
      $('bioProgress').style.display = 'none';
      $('bioControl').style.display = 'block';
    });
  }

  var btnDownloadBio = $('btnDownloadBio');
  if (btnDownloadBio) {
    btnDownloadBio.addEventListener('click', function () {
      if (!bioState.finalContent) { alert('没有可下载的内容'); return; }
      var name = state.dossier.subject?.name || '传记';
      var text = name + ' 的个人传记\n\n' + bioState.finalContent;
      var blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = name + '_传记.md';
      a.click();
      URL.revokeObjectURL(url);
    });
  }

  var btnNewBio = $('btnNewBio');
  if (btnNewBio) {
    btnNewBio.addEventListener('click', function () {
      bioState.sid = null;
      bioState.finalContent = null;
      $('bioResult').style.display = 'none';
      $('bioControl').style.display = 'block';
      if (btnStartBio) btnStartBio.click();
    });
  }

  // ── 对话 ──
  async function loadConversations() {
    try {
      var r = await NianAuth.fetch('/api/memorials/' + state.currentId + '/conversations?limit=300');
      var d = await r.json();
      var box = $('convList');
      if (!d.conversations || !d.conversations.length) {
        box.innerHTML = '<div style="color:#8a7654;text-align:center;padding:30px">还没有对话记录。</div>';
        return;
      }
      box.innerHTML = d.conversations.map(function (c) {
        var role = c.role === 'user' ? '我' : '念念';
        return '<div class="conv-row ' + (c.role === 'user' ? 'user' : '') + '">' +
          '<div class="role">' + role + '</div>' +
          '<div><div class="content">' + escapeHtml(c.content || '') + '</div>' +
          '<div class="ts">' + (c.ts || '') + '</div></div>' +
          '</div>';
      }).join('');
    } catch (e) { console.warn(e); }
  }

  // ── tabs ──
  document.querySelectorAll('.tab').forEach(function (t) {
    t.addEventListener('click', function () {
      document.querySelectorAll('.tab').forEach(function (x) { x.classList.remove('active') });
      document.querySelectorAll('.pane').forEach(function (x) { x.classList.remove('active') });
      t.classList.add('active');
      document.querySelector('[data-pane="' + t.dataset.tab + '"]').classList.add('active');
    });
  });

  // ── 保存 ──
  $('btnSave').addEventListener('click', async function () {
    readInputsToDossier();
    try {
      var r = await NianAuth.fetch('/api/memorials/' + state.currentId + '/dossier', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dossier: state.dossier })
      });
      var d = await r.json();
      state.dossier = d.dossier;
      // 同步 product_intent 到 meta
      var pi = (state.dossier.product_intent || {}).primary;
      if (pi !== undefined) {
        await NianAuth.fetch('/api/memorials/' + state.currentId, {
          method: 'PATCH', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ product_intent: pi })
        });
      }
      $('btnSave').textContent = '已保存 ✓';
      setTimeout(function () { $('btnSave').textContent = '保存修改'; }, 1500);
      loadMemorials();
    } catch (e) { alert('保存失败：' + e.message); }
  });

  // ── 删除 ──
  $('btnDelete').addEventListener('click', async function () {
    if (!confirm('确认删除该纪念对象？所有对话、资料、文件将一并删除。')) return;
    await NianAuth.fetch('/api/memorials/' + state.currentId, { method: 'DELETE' });
    state.currentId = null;
    NianAuth.setActiveMemorialId('');
    $('detailBody').style.display = 'none';
    $('emptyHint').style.display = 'block';
    loadMemorials();
  });

  // ── 新建 ──
  $('btnNew').addEventListener('click', function () { $('newModal').classList.add('show'); });
  $('newCancel').addEventListener('click', function () { $('newModal').classList.remove('show'); });
  $('newCreate').addEventListener('click', async function () {
    var name = $('newName').value.trim();
    if (!name) { alert('请填写名字'); return; }
    var r = await NianAuth.fetch('/api/memorials', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, relation: $('newRelation').value.trim(), note: $('newNote').value.trim() })
    });
    var d = await r.json();
    $('newModal').classList.remove('show');
    $('newName').value = ''; $('newRelation').value = ''; $('newNote').value = '';
    await loadMemorials();
    selectMemorial(d.memorial.memorial_id);
  });

  // 工具
  function escapeHtml(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function escapeAttr(s) { return escapeHtml(s).replace(/"/g, '&quot;'); }

  loadMemorials();
})();
