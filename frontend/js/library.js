// library.js — 资料库前端

(function () {

  'use strict';

  if (!NianAuth.requireAuth()) return;



  var state = {
    memorials: [],
    currentId: null,
    dossier: null,
    meta: null,
    assets: [],
    conversations: [],
    loadSeq: 0,
  };

  var assetState = { selectMode: false, selected: new Set() };



  function $(id) { return document.getElementById(id); }

  function setSwitchStatus(text, isError) {
    var status = $('libSwitchStatus');
    if (!status) return;
    status.textContent = text || '';
    status.style.color = isError ? '#b54a3f' : '#8a7654';
  }

  function showLibraryMessage(message, isError) {
    $('detailBody').style.display = 'none';
    $('emptyHint').style.display = 'block';
    $('emptyHint').textContent = message;
    $('emptyHint').style.color = isError ? '#b54a3f' : '#8a7654';
  }

  function resetPersonScopedState(mid) {
    state.meta = null;
    state.dossier = null;
    state.assets = [];
    state.conversations = [];
    assetState.selectMode = false;
    assetState.selected.clear();

    // An open upload description belongs to the person for whom it was opened.
    // Close it on switch so it can never be submitted into another archive.
    stopLibVoice();
    if ($('libUploadModal')) $('libUploadModal').classList.remove('show');
    libUploadPending = { file: null, kind: null, memorialId: null };

    if ($('convList')) $('convList').innerHTML = '';
    if ($('assetsGrouped')) $('assetsGrouped').innerHTML = '';
    if ($('memoriesList')) $('memoriesList').innerHTML = '';
    if (typeof bioState !== 'undefined') {
      bioState.sid = null;
      bioState.polling = false;
      bioState.finalContent = null;
    }

    var selected = state.memorials.find(function(m){ return m.memorial_id === mid; });
    showLibraryMessage(
      selected ? '正在加载「' + (selected.name || '未命名') + '」的独立资料库…' : '正在加载资料库…',
      false
    );
  }

  function renderPersonSelector() {
    var select = $('libPersonSelect');
    if (!select) return;
    select.innerHTML = '';
    if (!state.memorials.length) {
      var emptyOption = document.createElement('option');
      emptyOption.value = '';
      emptyOption.textContent = '暂无人物，请先新建';
      select.appendChild(emptyOption);
      select.disabled = true;
      return;
    }
    select.disabled = false;
    state.memorials.forEach(function(m) {
      var option = document.createElement('option');
      option.value = m.memorial_id;
      option.textContent = (m.name || '未命名') + (m.relation ? ' · ' + m.relation : '');
      select.appendChild(option);
    });
    select.value = state.currentId || '';
  }



  // 顶部用户信息

  (function () {

    var u = NianAuth.getUser() || {};

    $('libUser').innerHTML = (u.display_name || u.email || '访客') + (u.is_owner ? ' · 主人' : '') +

      ' <span class="logout">退出</span>';

    $('libUser').querySelector('.logout').onclick = function () { NianAuth.logout(); };

  })();

  var personSelect = $('libPersonSelect');
  if (personSelect) {
    personSelect.addEventListener('change', function() {
      var mid = personSelect.value;
      if (mid && mid !== state.currentId) selectMemorial(mid);
    });
  }



  // ── 列表 ──

  async function loadMemorials() {
    try {
      setSwitchStatus('加载中');
      var r = await NianAuth.fetch('/api/memorials');
      if (!r.ok) throw new Error('人物列表请求失败（HTTP ' + r.status + '）');
      var d = await r.json();
      state.memorials = Array.isArray(d.memorials) ? d.memorials : [];

      // URL ?mid= 优先，其次当前选择，再次 localStorage，最后第一个。
      var urlMid = (location.search.match(/[?&]mid=([^&]+)/) || [])[1];
      if (urlMid) urlMid = decodeURIComponent(urlMid);
      var requestedId = urlMid || state.currentId || NianAuth.getActiveMemorialId();
      var activeId = state.memorials.some(function(m){ return m.memorial_id === requestedId; })
        ? requestedId
        : (state.memorials[0] && state.memorials[0].memorial_id);

      renderList();
      renderPersonSelector();

      if (activeId) {
        await selectMemorial(activeId);
      } else {
        state.currentId = null;
        NianAuth.setActiveMemorialId('');
        renderList();
        renderPersonSelector();
        setSwitchStatus('');
        showLibraryMessage('还没有人物资料库。请点击「+ 新建」后开始填充资料。', false);
      }
    } catch (e) {
      console.error('[library] failed to load memorials', e);
      setSwitchStatus('加载失败', true);
      showLibraryMessage('资料库加载失败：' + (e.message || '请刷新后重试。'), true);
    }
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

    renderPersonSelector();

  }



  async function selectMemorial(mid) {
    if (!state.memorials.some(function(m){ return m.memorial_id === mid; })) return;
    var requestSeq = ++state.loadSeq;
    state.currentId = mid;
    NianAuth.setActiveMemorialId(mid);
    resetPersonScopedState(mid);
    setSwitchStatus('切换中');

    // 立即更新声音工坊入口链接，避免用户在 fetch 完成前点击时 mid 丢失
    var vsEntry = $('voiceStudioEntry');
    if (vsEntry) vsEntry.href = '/static/voice_studio.html?mid=' + encodeURIComponent(mid);

    renderList();
    renderPersonSelector();

    try {
      var r = await NianAuth.fetch('/api/memorials/' + encodeURIComponent(mid));
      if (!r.ok) throw new Error('人物资料请求失败（HTTP ' + r.status + '）');
      var d = await r.json();

      // Ignore a slower response from the previously selected person.
      if (requestSeq !== state.loadSeq || mid !== state.currentId) return;
      if (!d.meta) throw new Error('人物资料返回为空');

      state.meta = d.meta;
      state.dossier = d.dossier || {};
      state.assets = Array.isArray(d.assets) ? d.assets : [];

      renderDetail();
      setSwitchStatus('已切换');
      loadConversations(mid, requestSeq);
    } catch (e) {
      if (requestSeq !== state.loadSeq || mid !== state.currentId) return;
      console.error('[library] failed to load memorial', mid, e);
      setSwitchStatus('加载失败', true);
      showLibraryMessage('该人物资料库加载失败：' + (e.message || '请重试。'), true);
    }

  }



  function renderDetail() {

    $('emptyHint').style.display = 'none';

    $('detailBody').style.display = 'block';

    $('dName').textContent = state.meta.name || '未命名';
    var archiveTarget = $('archiveTarget');
    if (archiveTarget) {
      archiveTarget.textContent = '当前新增素材、对话与记忆均归档到「' + (state.meta.name || '未命名') + '」';
    }
    // 声音工坊入口携带当前 mid，跳转后不需要重新选择
    var vsEntry = $('voiceStudioEntry');
    if (vsEntry && state.currentId) vsEntry.href = '/static/voice_studio.html?mid=' + encodeURIComponent(state.currentId);
    // 更新音频样本数量标签
    var vsMeta = $('voiceStudioMeta');
    if (vsMeta) {
      var audioCount = (state.assets || []).filter(function(a){ return a.kind === 'audio'; }).length;
      vsMeta.textContent = audioCount > 0 ? audioCount + ' 个音频样本 · 点击进入声音工坊勾选' : '未克隆 · 0 个音频样本';
    }
    // 影像制作入口：带当前 mid，studio 可直接加载素材库照片作为参考图
    var studioEntry = $('studioEntry');
    if (studioEntry && state.currentId) studioEntry.href = '/static/studio.html?mid=' + encodeURIComponent(state.currentId);

    $('dRelation').textContent = state.meta.relation || '';

    $('dIntent').textContent = intentLabel(state.meta.product_intent || (state.dossier.product_intent && state.dossier.product_intent.primary)) || '方向未定';

    $('dUpdated').textContent = '更新于 ' + (state.meta.updated_at || '').replace('T', ' ');

    bindDossierToInputs();

    renderMemories();

    renderAssets();

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

  var ASSET_CATS = [
    { kind: 'audio',          label: '语音 / 音频',       icon: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>' },
    { kind: 'image',          label: '图片 / 照片',       icon: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>' },
    { kind: 'video',          label: '视频',              icon: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>' },
    { kind: 'document',       label: '文件 / 文档',       icon: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>' },
    { kind: 'text',           label: '纯文字描述 / 聊天', icon: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="17" y1="3" x2="21" y2="7"></line><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path><path d="M18 2.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L18 2.5z"></path></svg>' },
    { kind: 'other',          label: '其他',              icon: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="21 8 21 21 3 21 3 8"></polyline><rect x="1" y="3" width="22" height="5"></rect><line x1="10" y1="12" x2="14" y2="12"></line></svg>' },
  ];

  function iconForKind(k) {
    var m = ASSET_CATS.find(function(c){ return c.kind === k; });
    return m ? m.icon : ASSET_CATS[5].icon;
  }

  function renderAssets() {
    var box = $('assetsGrouped');
    if (!box) return;
    box.innerHTML = '';

    if (!state.assets.length) {
      box.innerHTML = '<div style="color:#8a7654;padding:30px;text-align:center">还没有素材。点击「+ 上传素材」添加文件，或在聊天页用 ⬆ 上传。</div>';
      return;
    }

    ASSET_CATS.forEach(function(cat) {
      var items = state.assets.filter(function(a){ return a.kind === cat.kind; });
      if (!items.length) return;

      var section = document.createElement('div');
      section.className = 'asset-category';
      var header = '<div class="asset-cat-header">' +
        '<span class="asset-cat-icon">' + cat.icon + '</span>' +
        '<span>' + cat.label + '</span>' +
        '<span class="asset-cat-count">' + items.length + ' 个</span>' +
        '</div>';
      section.innerHTML = header;

      var cardsWrap = document.createElement('div');
      cardsWrap.className = cat.kind === 'image' ? 'asset-cards-grid' : 'asset-cards-list';

      items.forEach(function(a) {
        cardsWrap.appendChild(buildAssetCard(a));
      });

      section.appendChild(cardsWrap);
      box.appendChild(section);
    });
  }

  function buildAssetCard(a) {
    var cardMemorialId = state.currentId;
    var isImage = (a.kind === 'image' && a.url);
    var card = document.createElement('div');
    card.className = 'asset-card ' + (isImage ? 'asset-card-image' : 'asset-card-file');
    card.dataset.aid = a.asset_id;

    var icon = iconForKind(a.kind);
    var tagsHtml = (a.tags || []).map(function(t){
      return '<span class="asset-card-tag">' + escapeHtml(t) + '</span>';
    }).join('');

    var analysisLabel = a.analysis_status === 'queued' ? '分析中…' :
      a.analysis_status === 'failed' ? '重试分析' :
      a.analysis_status === 'succeeded' ? '重新分析' : 'AI 分析';
    var machineSummary = a.ai_summary || a.visual_summary || '';
    var structuredMeta = [
      a.time_period ? '时间：' + a.time_period : '',
      a.event ? '事件：' + a.event : '',
      a.scene ? '场景：' + a.scene : '',
    ].filter(Boolean).join(' · ');
    var imgUrl = '';
    if (isImage) {
      var tok = (window.NianAuth && NianAuth.getToken && NianAuth.getToken()) || '';
      imgUrl = a.url + (a.url.indexOf('?')>=0?'&':'?') + 'token=' + encodeURIComponent(tok);
    }

    var checkHtml = (assetState.selectMode) ? '<div class="asset-select"><input type="checkbox" class="asset-checkbox"' + (assetState.selected.has(a.asset_id) ? ' checked' : '') + '></div>' : '';

    // 图片：缩略图放在卡片顶部，独占一行，可点击放大
    var thumbBlockHtml = isImage
      ? '<a class="asset-thumb-block" href="' + imgUrl + '" target="_blank" title="点击查看原图"><img class="asset-img-thumb" src="' + imgUrl + '" alt="' + escapeAttr(a.filename || '') + '"></a>'
      : '';

    var bodyHtml =
      '<div class="asset-card-body">' +
        '<div class="asset-card-name">' + escapeHtml(a.filename || a.asset_id) + '</div>' +
        '<div class="asset-card-desc"><span class="asset-field-label">用户描述</span><span class="asset-field-value">' + escapeHtml(a.user_description || a.description || '（未填写）') + '</span></div>' +
        (machineSummary ? '<div class="asset-card-desc asset-card-ai"><span class="asset-field-label">AI 摘要</span><span class="asset-field-value">' + escapeHtml(machineSummary) + '</span></div>' : '') +
        (structuredMeta ? '<div class="asset-card-desc asset-card-meta">' + escapeHtml(structuredMeta) + '</div>' : '') +
        (tagsHtml ? '<div class="asset-card-tags">' + tagsHtml + '</div>' : '') +
      '</div>';
    var actionsHtml =
      '<div class="asset-card-actions">' +
        '<button class="asset-action-btn asset-btn-analyze" title="重新识别人物、时间、事件、场景和视频用途；不会覆盖用户描述" data-aid="' + a.asset_id + '">' + analysisLabel + '</button>' +
        '<button class="asset-action-btn asset-btn-ask" title="带着这项素材进入 Agent，针对它继续提问" data-aid="' + a.asset_id + '">问念念</button>' +
        '<button class="asset-action-btn asset-btn-edit" title="修改用户描述和标签" data-aid="' + a.asset_id + '">编辑</button>' +
        '<button class="asset-action-btn asset-btn-del" title="删除这项素材" aria-label="删除素材" data-aid="' + a.asset_id + '">删除</button>' +
      '</div>';
    var editHtml =
      '<div class="asset-edit-area" id="edit_' + a.asset_id + '">' +
        '<input type="text" class="ae-desc" placeholder="描述" value="' + escapeAttr(a.description || '') + '">' +
        '<input type="text" class="ae-tags" placeholder="标签（逗号分隔）" value="' + escapeAttr((a.tags||[]).join(', ')) + '">' +
        '<button class="asset-edit-save" data-aid="' + a.asset_id + '">保存</button>' +
      '</div>';

    // Image cards intentionally do not use asset-card-top. That wrapper is a
    // horizontal flex row for compact file entries and can squeeze long image
    // descriptions down to their min-content width.
    card.innerHTML = isImage
      ? thumbBlockHtml + checkHtml + bodyHtml + actionsHtml + editHtml
      : '<div class="asset-card-top">' +
          checkHtml +
          '<div class="asset-card-icon">' + icon + '</div>' +
          bodyHtml +
          actionsHtml +
        '</div>' +
        editHtml;

    // 选择模式逻辑
    if (assetState.selectMode) {
      var checkbox = card.querySelector('.asset-checkbox');
      card.style.cursor = 'pointer';
      card.addEventListener('click', function(e) {
        if (e.target.closest('.asset-btn-edit') || e.target.closest('.asset-btn-del') || e.target.closest('.asset-btn-analyze') || e.target.closest('.asset-btn-ask') || e.target.closest('.asset-edit-area')) return;
        if (e.target !== checkbox) {
          checkbox.checked = !checkbox.checked;
        }
        if (checkbox.checked) assetState.selected.add(a.asset_id);
        else assetState.selected.delete(a.asset_id);
        updateAssetActionButton();
      });
    }

    // 编辑按钮
    card.querySelector('.asset-btn-edit').addEventListener('click', function() {
      var area = card.querySelector('.asset-edit-area');
      area.classList.toggle('open');
    });

    var analyzeButton = card.querySelector('.asset-btn-analyze');
    if (analyzeButton) analyzeButton.addEventListener('click', async function() {
      analyzeButton.disabled = true;
      try {
        var response = await NianAuth.fetch('/api/memorials/' + encodeURIComponent(cardMemorialId) + '/assets/' + encodeURIComponent(a.asset_id) + '/analyze', { method: 'POST' });
        if (!response.ok) throw new Error('HTTP ' + response.status);
        if (cardMemorialId !== state.currentId) return;
        a.analysis_status = 'queued';
        libToast('已加入素材分析队列，稍后刷新可查看结构化信息');
      } catch(e) {
        libToast('素材分析提交失败：' + e.message);
      } finally {
        analyzeButton.disabled = false;
      }
    });

    var askButton = card.querySelector('.asset-btn-ask');
    if (askButton) askButton.addEventListener('click', function() {
      window.location.href = '/static/index.html?memorial_id=' + encodeURIComponent(cardMemorialId) + '&asset_id=' + encodeURIComponent(a.asset_id);
    });

    // 删除按钮
    card.querySelector('.asset-btn-del').addEventListener('click', async function() {
      if (!confirm('删除这个素材？')) return;
      await NianAuth.fetch('/api/memorials/' + encodeURIComponent(cardMemorialId) + '/assets/' + encodeURIComponent(a.asset_id), { method: 'DELETE' });
      if (cardMemorialId !== state.currentId) return;
      await selectMemorial(cardMemorialId);
      libToast('已删除');
    });

    // 保存编辑
    card.querySelector('.asset-edit-save').addEventListener('click', async function() {
      var desc = card.querySelector('.ae-desc').value.trim();
      var tags = card.querySelector('.ae-tags').value.split(/[,，]/).map(function(s){return s.trim();}).filter(Boolean);
      try {
        await NianAuth.fetch('/api/memorials/' + encodeURIComponent(cardMemorialId) + '/assets/' + encodeURIComponent(a.asset_id), {
          method: 'PATCH',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ description: desc, tags: tags }),
        });
        if (cardMemorialId !== state.currentId) return;
        a.description = desc; a.tags = tags;
        renderAssets();
        libToast('已保存');
      } catch(e) { libToast('保存失败：' + e.message); }
    });

    return card;
  }

  function updateAssetActionButton() {
    var btn = $('btnAssetMode');
    if (!btn) return;
    btn.classList.remove('primary', 'danger');
    if (!assetState.selectMode) {
      btn.textContent = '选择删除';
      btn.classList.add('primary');
    } else if (assetState.selected.size > 0) {
      btn.textContent = '删除选中 (' + assetState.selected.size + ')';
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
    var targetMid = state.currentId;
    var ids = Array.from(assetState.selected);
    if (!ids.length) return;
    if (!confirm('确认删除选中的素材？此操作不可恢复。')) return;

    for (var i = 0; i < ids.length; i++) {
      var aid = ids[i];
      await NianAuth.fetch('/api/memorials/' + encodeURIComponent(targetMid) + '/assets/' + encodeURIComponent(aid), { method: 'DELETE' });
    }
    if (targetMid !== state.currentId) return;
    assetState.selected.clear();
    assetState.selectMode = false;
    await selectMemorial(targetMid);
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

  // ── Toast ──
  function libToast(msg, ms) {
    var t = $('libToast');
    if (!t) return;
    t.textContent = msg; t.classList.add('show');
    clearTimeout(t._tm);
    t._tm = setTimeout(function(){ t.classList.remove('show'); }, ms || 2400);
  }

  // ── 素材上传 ──
  var libUploadPending = { file: null, kind: null, memorialId: null };
  var libUploadInFlight = false;
  var LIB_UPLOAD_IDLE_LABEL = '上传并归档';
  var libVoiceRecorder = null;
  var libVoiceStream = null;
  var libVoiceChunks = [];
  var libVoiceBase = '';
  var libVoiceRecognition = null;
  var libVoiceFinal = '';

  function setLibVoiceStatus(text, recording) {
    var label = $('libUploadVoiceStatus');
    var button = $('libUploadVoice');
    if (label) label.textContent = text;
    if (button) button.textContent = recording ? '结束录音' : '语音输入';
  }

  function setLibUploadBusy(busy) {
    var button = $('libUploadConfirm');
    libUploadInFlight = Boolean(busy);
    if (!button) return;
    button.disabled = libUploadInFlight;
    button.textContent = libUploadInFlight ? '上传中...' : LIB_UPLOAD_IDLE_LABEL;
    button.setAttribute && button.setAttribute('aria-busy', libUploadInFlight ? 'true' : 'false');
  }

  function stopLibVoice() {
    if (libVoiceRecognition) {
      try { libVoiceRecognition.stop(); } catch(e) {}
      libVoiceRecognition = null;
    }
    if (libVoiceRecorder && libVoiceRecorder.state !== 'inactive') {
      try { libVoiceRecorder.stop(); } catch(e) {}
    }
  }

  async function toggleLibVoice() {
    if (libVoiceRecorder && libVoiceRecorder.state === 'recording') {
      stopLibVoice();
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
      setLibVoiceStatus('当前浏览器不支持录音，请手动输入', false);
      return;
    }
    try {
      libVoiceStream = await navigator.mediaDevices.getUserMedia({audio:true});
    } catch(e) {
      setLibVoiceStatus('无法使用麦克风，请检查权限后重试', false);
      return;
    }
    var textarea = $('libUploadDesc');
    libVoiceBase = textarea.value.trim();
    libVoiceFinal = '';
    libVoiceChunks = [];
    var types = ['audio/webm;codecs=opus','audio/webm','audio/ogg'];
    var mimeType = types.find(function(type){ return MediaRecorder.isTypeSupported(type); }) || '';
    libVoiceRecorder = new MediaRecorder(libVoiceStream, mimeType ? {mimeType:mimeType} : {});
    libVoiceRecorder.ondataavailable = function(event) {
      if (event.data && event.data.size) libVoiceChunks.push(event.data);
    };
    libVoiceRecorder.onstop = async function() {
      if (libVoiceStream) libVoiceStream.getTracks().forEach(function(track){ track.stop(); });
      setLibVoiceStatus('正在识别，请稍候…', false);
      var localText = libVoiceFinal.trim();
      try {
        var form = new FormData();
        var ext = mimeType.indexOf('ogg') >= 0 ? 'ogg' : 'webm';
        form.append('audio', new Blob(libVoiceChunks, {type:mimeType || 'audio/webm'}), 'photo-description.' + ext);
        var response = await fetch('/api/agent/asr', {method:'POST', body:form});
        var data = await response.json().catch(function(){ return {}; });
        var recognized = (data.text || '').trim() || localText;
        if (!response.ok || !recognized) throw new Error(data.detail || '没有识别到文字');
        textarea.value = (libVoiceBase ? libVoiceBase + '\n' : '') + recognized;
        textarea.focus();
        setLibVoiceStatus('已转成文字，请编辑确认后上传', false);
      } catch(e) {
        if (localText) {
          textarea.value = (libVoiceBase ? libVoiceBase + '\n' : '') + localText;
          textarea.focus();
          setLibVoiceStatus('服务端识别失败，已保留浏览器识别文字', false);
        } else {
          setLibVoiceStatus('识别失败，请重试或手动输入', false);
        }
      } finally {
        libVoiceRecorder = null;
        libVoiceStream = null;
        libVoiceChunks = [];
      }
    };
    libVoiceRecorder.start();

    // 与 Agent 普通麦克风一致：浏览器先实时预览，服务端 ASR 停止后校正。
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SR) {
      try {
        libVoiceRecognition = new SR();
        libVoiceRecognition.lang = 'zh-CN';
        libVoiceRecognition.continuous = true;
        libVoiceRecognition.interimResults = true;
        libVoiceRecognition.onresult = function(event) {
          var interim = '';
          for (var i = event.resultIndex; i < event.results.length; i++) {
            var text = event.results[i][0].transcript || '';
            if (event.results[i].isFinal) libVoiceFinal += text;
            else interim += text;
          }
          textarea.value = (libVoiceBase ? libVoiceBase + '\n' : '') + libVoiceFinal + interim;
        };
        libVoiceRecognition.onerror = function(event) {
          console.warn('[library voice preview]', event.error);
        };
        libVoiceRecognition.start();
      } catch(e) {
        libVoiceRecognition = null;
      }
    }
    setLibVoiceStatus('正在录音，再点一次结束', true);
  }

  (function setupLibUpload() {
    var wrapBtn  = $('btnLibUpload');
    var picker   = $('libTypePicker');
    if (!wrapBtn || !picker) return;

    function closePicker(){ picker.classList.remove('show'); }

    wrapBtn.addEventListener('click', function(e){
      e.stopPropagation();
      picker.classList.toggle('show');
    });
    document.addEventListener('click', function(e){
      var wrap = $('libUploadWrap');
      if (wrap && !wrap.contains(e.target)) closePicker();
    });

    // 每个类型按钮
    picker.querySelectorAll('.lib-type-btn').forEach(function(btn) {
      btn.addEventListener('click', function(){
        closePicker();
        var type = btn.dataset.type;
        libUploadPending.kind = type;

        if (type === 'text') {
          // 纯文字：直接弹描述弹窗，不需要文件
          libUploadPending.file = null;
          openLibUploadModal('text', null);
          return;
        }
        var inputMap = {
          audio:         'libFileAudio',
          image:         'libFileImage',
          video:         'libFileVideo',
          document_json: 'libFileDocJson',
          document_pdf:  'libFileDocPdf',
        };
        var inp = $(inputMap[type]);
        if (inp) inp.click();
      });
    });

    // 各文件 input change
    ['libFileAudio','libFileImage','libFileVideo','libFileDocJson','libFileDocPdf'].forEach(function(id){
      var inp = $(id);
      if (!inp) return;
      inp.addEventListener('change', function(){
        if (!inp.files || !inp.files[0]) return;
        libUploadPending.file = inp.files[0];
        openLibUploadModal(libUploadPending.kind, inp.files[0]);
        inp.value = '';
      });
    });

    // 弹窗取消
    var cancelBtn = $('libUploadCancel');
    if (cancelBtn) cancelBtn.addEventListener('click', function(){
      stopLibVoice();
      $('libUploadModal').classList.remove('show');
      if (!libUploadInFlight) setLibUploadBusy(false);
    });

    // 弹窗确认上传
    var confirmBtn = $('libUploadConfirm');
    if (confirmBtn) confirmBtn.addEventListener('click', doLibUpload);
    var voiceBtn = $('libUploadVoice');
    if (voiceBtn) voiceBtn.addEventListener('click', toggleLibVoice);
  })();

  function openLibUploadModal(kind, file) {
    if (!state.currentId || !state.meta) {
      libToast('请先选择并等待人物资料库加载完成');
      return;
    }
    if (libUploadInFlight) {
      libToast('上一项素材仍在上传，请稍候');
      return;
    }
    setLibUploadBusy(false);
    libUploadPending.memorialId = state.currentId;
    var titleMap = {
      audio: '上传语音 / 音频', image: '上传图片 / 照片', video: '上传视频',
      document_json: '上传聊天记录 (JSON)', document_pdf: '上传文件 (PDF/文档)',
      text: '添加纯文字描述',
    };
    $('libUploadTitle').textContent = titleMap[kind] || '上传素材';
    var uploadTarget = $('libUploadTarget');
    if (uploadTarget) {
      uploadTarget.textContent = '本次素材将归档到「' + (state.meta.name || '未命名') + '」';
    }
    var prev = $('libUploadPreview');
    if (file) {
      var icon = iconForKind(kind.split('_')[0]);
      var size = file.size > 1024*1024 ? (file.size/1024/1024).toFixed(1)+' MB' : (file.size/1024).toFixed(1)+' KB';
      prev.innerHTML = '<span style="font-size:1.6rem">' + icon + '</span><div><div style="font-weight:600">' + escapeHtml(file.name) + '</div><div style="color:#8a7654;font-size:.78rem">' + size + '</div></div>';
      prev.style.display = 'flex';
    } else {
      prev.style.display = 'none';
    }
    $('libUploadDesc').value = '';
    var voiceRow = $('libUploadVoiceRow');
    if (voiceRow) voiceRow.style.display = kind === 'image' ? 'flex' : 'none';
    setLibVoiceStatus('与聊天麦克风相同：浏览器预览，结束后精准识别', false);
    var textField = $('libTextDescField');
    if (kind === 'text') { textField.style.display = 'block'; $('libTextContent').value = ''; }
    else { textField.style.display = 'none'; }
    $('libUploadModal').classList.add('show');
    setTimeout(function(){ $('libUploadDesc').focus(); }, 100);
  }

  async function doLibUpload() {
    if (libUploadInFlight) return;
    var targetMid = libUploadPending.memorialId;
    if (!targetMid || targetMid !== state.currentId || !state.meta) {
      alert('人物资料库已经切换。为避免归档到错误人物，请重新选择素材上传。');
      $('libUploadModal').classList.remove('show');
      return;
    }
    if (libVoiceRecorder && libVoiceRecorder.state === 'recording') {
      stopLibVoice();
      setLibVoiceStatus('请等待语音转成文字，确认内容后再上传', false);
      return;
    }
    var kind = libUploadPending.kind;
    var file = libUploadPending.file;
    var desc = $('libUploadDesc').value.trim();
    var uploadedAsset = null;
    setLibUploadBusy(true);

    try {
      if (kind === 'text') {
        // 纯文字 → 构造 Blob 上传
        var content = $('libTextContent').value.trim();
        if (!content && !desc) { alert('请填写文字内容或描述'); return; }
        file = new File([content || desc], 'note_' + Date.now() + '.txt', { type: 'text/plain' });
      }
      if (!file) { alert('请选择文件'); return; }
      var form = new FormData();
      form.append('file', file);
      form.append('description', desc);
      var r = await NianAuth.fetch('/api/memorials/' + encodeURIComponent(targetMid) + '/upload', { method:'POST', body: form });
      if (!r.ok) { var ed = await r.json().catch(function(){return{};}); throw new Error(ed.detail || 'HTTP '+r.status); }
      var d = await r.json();
      uploadedAsset = d.asset || null;
      var tags = (d.asset && d.asset.tags || []).slice(0,4).join('、');
      $('libUploadModal').classList.remove('show');
      libToast('✓ 已归档' + (tags ? '，自动打标签：' + tags : ''), 3000);
      libUploadPending = { file: null, kind: null, memorialId: null };
    } catch(e) {
      libToast('上传失败：' + e.message);
    } finally {
      // Always release the button as soon as the upload request itself ends.
      // Do not tie the next upload to a full memorial reload.
      setLibUploadBusy(false);
    }

    if (uploadedAsset && targetMid === state.currentId) {
      var existingIndex = state.assets.findIndex(function(asset) {
        return asset.asset_id === uploadedAsset.asset_id;
      });
      if (existingIndex >= 0) state.assets[existingIndex] = uploadedAsset;
      else state.assets.unshift(uploadedAsset);
      renderAssets();
    }
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

  async function loadConversations(mid, requestSeq) {
    try {
      var r = await NianAuth.fetch(
        '/api/memorials/' + encodeURIComponent(mid) + '/conversations?limit=300'
      );
      if (!r.ok) throw new Error('HTTP ' + r.status);
      var d = await r.json();
      if (requestSeq !== state.loadSeq || mid !== state.currentId) return;
      state.conversations = Array.isArray(d.conversations) ? d.conversations : [];
      var box = $('convList');
      if (!state.conversations.length) {
        box.innerHTML = '<div style="color:#8a7654;text-align:center;padding:30px">还没有对话记录。</div>';
        return;
      }
      box.innerHTML = state.conversations.map(function (c) {
        var role = c.role === 'user' ? '我' : '念念';
        return '<div class="conv-row ' + (c.role === 'user' ? 'user' : '') + '">' +
          '<div class="role">' + role + '</div>' +
          '<div><div class="content">' + escapeHtml(c.content || '') + '</div>' +
          '<div class="ts">' + (c.ts || '') + '</div></div>' +
          '</div>';
      }).join('');
    } catch (e) {
      if (requestSeq !== state.loadSeq || mid !== state.currentId) return;
      console.warn('[library] conversations failed', e);
      $('convList').innerHTML = '<div style="color:#b54a3f;text-align:center;padding:30px">对话记录加载失败，请稍后重试。</div>';
    }
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
    if (!state.currentId || !state.dossier) return;
    var targetMid = state.currentId;
    var requestSeq = state.loadSeq;
    readInputsToDossier();
    var dossierPayload = JSON.parse(JSON.stringify(state.dossier));

    try {

      var r = await NianAuth.fetch('/api/memorials/' + encodeURIComponent(targetMid) + '/dossier', {

        method: 'PUT', headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({ dossier: dossierPayload })

      });
      if (!r.ok) throw new Error('HTTP ' + r.status);

      var d = await r.json();

      if (targetMid !== state.currentId || requestSeq !== state.loadSeq) return;
      state.dossier = d.dossier;

      // 同步 product_intent 到 meta

      var pi = (state.dossier.product_intent || {}).primary;

      if (pi !== undefined) {

        await NianAuth.fetch('/api/memorials/' + encodeURIComponent(targetMid), {

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
    var targetMid = state.currentId;

    await NianAuth.fetch('/api/memorials/' + encodeURIComponent(targetMid), { method: 'DELETE' });

    if (targetMid !== state.currentId) return;
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

    NianAuth.setActiveMemorialId(d.memorial.memorial_id);
    state.currentId = d.memorial.memorial_id;
    await loadMemorials();

  });



  // 工具

  function escapeHtml(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  function escapeAttr(s) { return escapeHtml(s).replace(/"/g, '&quot;'); }

  // URL 参数：?tab=assets 时自动切换到素材库 Tab
  (function applyUrlTab(){
    var m = location.search.match(/[?&]tab=([^&]+)/);
    if (!m) return;
    var tab = decodeURIComponent(m[1]);
    var tabBtn = document.querySelector('.tab[data-tab="' + tab + '"]');
    if (!tabBtn) return;
    setTimeout(function(){
      document.querySelectorAll('.tab').forEach(function(x){ x.classList.remove('active'); });
      document.querySelectorAll('.pane').forEach(function(x){ x.classList.remove('active'); });
      tabBtn.classList.add('active');
      var pane = document.querySelector('[data-pane="' + tab + '"]');
      if (pane) pane.classList.add('active');
    }, 200);
  })();

  loadMemorials();

})();

