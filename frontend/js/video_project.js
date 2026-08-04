(function () {
  'use strict';

  if (!window.NianAuth || !window.NianAuth.requireAuth()) return;
  var params = new URLSearchParams(location.search);
  var memorialId = params.get('memorial_id') || '';
  var projectId = params.get('project_id') || '';
  var embedded = params.get('embedded') === '1';
  var project = null;
  var pollTimer = null;
  var blobUrls = new Map();

  function $(id) { return document.getElementById(id); }
  if (embedded) {
    document.body.classList.add('embedded-workspace');
    var header = document.querySelector('.topbar');
    if (header) header.hidden = true;
  }
  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function toast(message) {
    var el = $('toast');
    el.textContent = message;
    el.classList.add('show');
    clearTimeout(el._timer);
    el._timer = setTimeout(function () { el.classList.remove('show'); }, 2600);
  }
  async function request(path, options) {
    var response = await window.NianAuth.fetch(path, options || {});
    var type = response.headers.get('content-type') || '';
    var data = type.indexOf('application/json') >= 0 ? await response.json() : await response.text();
    if (!response.ok) {
      var detail = data && data.detail;
      if (detail && typeof detail === 'object') detail = detail.message || JSON.stringify(detail);
      throw new Error(detail || data || ('HTTP ' + response.status));
    }
    return data;
  }
  function basePath() {
    return '/api/video-projects/' + encodeURIComponent(memorialId) + '/' + encodeURIComponent(projectId);
  }
  function statusText(value) {
    return {
      pending: '待生成', generating: '生成中', needs_review: '待确认',
      approved: '已确认', failed: '生成失败'
    }[value] || value || '未开始';
  }
  function renderStatusText(value) {
    return {idle: '等待镜头', rendering: '正在合成', completed: '合成完成', failed: '合成失败', stale: '脚本已变化'}[value] || value;
  }

  async function protectedMedia(url, element, cacheKey) {
    var key = cacheKey || url;
    try {
      if (!blobUrls.has(key)) {
        var response = await window.NianAuth.fetch(url);
        if (!response.ok) throw new Error('素材读取失败');
        blobUrls.set(key, URL.createObjectURL(await response.blob()));
      }
      element.src = blobUrls.get(key);
    } catch (error) {
      var placeholder = document.createElement('div');
      placeholder.className = 'media-placeholder';
      placeholder.textContent = error.message || '素材无法读取';
      element.replaceWith(placeholder);
    }
  }

  function mediaBlock(label, tag, url, cacheKey) {
    var block = document.createElement('div');
    block.className = 'preview-block';
    var caption = document.createElement('div');
    caption.className = 'preview-label';
    caption.textContent = label;
    var media = document.createElement(tag);
    if (tag === 'video') {
      media.controls = true;
      media.playsInline = true;
      media.preload = 'metadata';
    }
    block.appendChild(caption);
    block.appendChild(media);
    protectedMedia(url, media, cacheKey);
    return block;
  }

  function buildClipCard(clip) {
    var card = document.createElement('article');
    card.className = 'clip-card';
    card.dataset.clipId = clip.clip_id;

    var mediaColumn = document.createElement('div');
    mediaColumn.className = 'media-column';
    var frame = document.createElement('div');
    frame.className = 'media-frame';
    var sourceTag = clip.asset_kind === 'video' ? 'video' : 'img';
    frame.appendChild(mediaBlock('真实素材', sourceTag, clip.source_url, 'source:' + clip.asset_id));
    if (clip.preview_url && clip.render_mode === 'image_to_video') {
      frame.appendChild(mediaBlock(
        '生成预览', 'video', clip.preview_url,
        'preview:' + clip.clip_id + ':' + clip.prompt_revision + ':' + clip.attempts
      ));
    }
    var meta = document.createElement('div');
    meta.className = 'media-meta';
    meta.innerHTML = '<span>' + esc(clip.asset_filename) + '</span><span>' + esc(clip.asset_id) + '</span>';
    mediaColumn.appendChild(frame);
    mediaColumn.appendChild(meta);

    var body = document.createElement('div');
    body.className = 'clip-body';
    var isImage = clip.asset_kind === 'image';
    body.innerHTML =
      '<div class="clip-heading"><div><div class="clip-index">SHOT ' + String(clip.order + 1).padStart(2, '0') +
      ' · ' + esc(clip.start_sec) + '—' + esc(clip.end_sec) + ' 秒</div><h3>' + esc(clip.narrative_role || '未命名镜头') +
      '</h3></div><span class="clip-status ' + esc(clip.status) + '">' + esc(statusText(clip.status)) + '</span></div>' +
      '<div class="facts">' +
      '<div class="fact"><span>旁白</span><strong>' + esc(clip.narration || '无') + '</strong></div>' +
      '<div class="fact"><span>字幕</span><strong>' + esc(clip.subtitle || '无') + '</strong></div>' +
      '<div class="fact"><span>事实依据</span><strong>' + esc(clip.fact_basis || '导演脚本') + '</strong></div>' +
      '<div class="fact"><span>转场</span><strong>' + esc((clip.transition && clip.transition.type) || 'cut') +
      ' · ' + esc((clip.transition && clip.transition.duration_sec) || 0) + ' 秒</strong></div>' +
      '<div class="fact"><span>生成服务</span><strong>' +
      esc(clip.asset_kind === 'image'
        ? ((clip.generation_provider || 'TokenStar') + ' · ' + (clip.provider_model || 'Seedance 素材快速模型'))
        : '真实视频直接使用') + '</strong></div>' +
      '<div class="fact"><span>任务状态</span><strong>' +
      esc(clip.asset_kind === 'image'
        ? ((clip.provider_status || 'pending') + (clip.task_id ? ' · ' + clip.task_id : ''))
        : 'ready') + '</strong></div></div>' +
      '<label class="prompt-label"><span>Agent 动态化 Prompt</span><span>版本 ' + esc(clip.prompt_revision || 1) + '</span></label>' +
      '<textarea class="prompt-editor" maxlength="2000" ' + (isImage ? '' : 'disabled') + '>' + esc(clip.motion_prompt || '真实视频直接使用，不调用动态化模型。') + '</textarea>' +
      (clip.error ? '<div class="clip-error">' + esc(clip.error) + '</div>' : '') +
      '<div class="clip-actions"></div>';

    var actions = body.querySelector('.clip-actions');
    var editor = body.querySelector('.prompt-editor');
    function button(text, className, handler, disabled) {
      var value = document.createElement('button');
      value.type = 'button';
      value.textContent = text;
      if (className) value.className = className;
      value.disabled = !!disabled;
      value.addEventListener('click', handler);
      actions.appendChild(value);
    }
    if (isImage) {
      button('保存 Prompt', 'secondary', async function () {
        await act(async function () {
          project = await request(basePath() + '/clips/' + encodeURIComponent(clip.clip_id) + '/prompt', {
            method: 'PATCH', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({motion_prompt: editor.value})
          });
          toast('Prompt 已保存，旧结果已标记为失效');
        });
      }, clip.status === 'generating');
      button(
        clip.status === 'failed' || clip.status === 'needs_review' || clip.status === 'approved' ? '重新生成' : '运行生成视频',
        'primary',
        async function () {
          await act(async function () {
            if (editor.value.trim() !== clip.motion_prompt) {
              await request(basePath() + '/clips/' + encodeURIComponent(clip.clip_id) + '/prompt', {
                method: 'PATCH', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({motion_prompt: editor.value})
              });
            }
            await request(basePath() + '/clips/' + encodeURIComponent(clip.clip_id) + '/generate', {method: 'POST'});
            toast('镜头已进入生成队列');
          });
        },
        clip.status === 'generating'
      );
      button('保留静态画面', 'secondary', async function () {
        if (!confirm('该镜头将使用克制的缓慢推拉效果，不再等待 AI 动态化。确定吗？')) return;
        await act(async function () {
          project = await request(basePath() + '/clips/' + encodeURIComponent(clip.clip_id) + '/fallback', {method: 'POST'});
          toast('已使用静态画面降级');
        });
      }, clip.status === 'generating');
    }
    if (clip.status === 'needs_review') {
      button('确认使用此镜头', 'primary', async function () {
        await act(async function () {
          project = await request(basePath() + '/clips/' + encodeURIComponent(clip.clip_id) + '/approve', {method: 'POST'});
          toast('镜头已确认');
        });
      });
    }

    card.appendChild(mediaColumn);
    card.appendChild(body);
    return card;
  }

  function render() {
    if (!project) return;
    $('loadingPanel').hidden = true;
    $('projectIdentity').textContent = '项目 ' + projectId + ' · 人物资料库 ' + memorialId;
    var total = project.progress ? project.progress.total : 0;
    var approved = project.progress ? project.progress.approved : 0;
    $('progressText').textContent = approved + ' / ' + total;
    $('progressBar').style.width = (total ? Math.round(approved / total * 100) : 0) + '%';
    $('projectStatus').textContent = renderStatusText(project.render_status || project.manifest_status);
    $('projectStatus').className = 'status-pill ' + (project.render_status === 'completed' ? 'ok' : (project.render_status === 'failed' || project.script_stale ? 'bad' : ''));

    var message = '每个镜头都绑定当前人物的真实素材。请逐项检查 Prompt 与生成结果。';
    if (project.script_stale) message = '导演脚本已被修改，本项目已锁定。请返回确认新版本并重新解析。';
    else if (project.manifest_status === 'compiling') message = '执行导演正在读取脚本和素材，生成逐镜头 Prompt。';
    else if (project.render_status === 'rendering') message = 'FFmpeg 正在按确认脚本合成画面、字幕与可用音轨。';
    else if (project.render_status === 'completed') message = '最终视频已经生成，并保留了完整 FFmpeg 执行记录。';
    else if (project.manifest_error) message = project.manifest_error;
    $('projectMessage').textContent = message;

    var warnings = (project.warnings || []).slice();
    if (project.render_error) warnings.unshift(project.render_error);
    $('warningPanel').hidden = warnings.length === 0;
    $('warningPanel').innerHTML = warnings.map(function (item) { return '<div>· ' + esc(item) + '</div>'; }).join('');

    var list = $('clipList');
    list.innerHTML = '';
    (project.clips || []).forEach(function (clip) { list.appendChild(buildClipCard(clip)); });

    $('renderButton').disabled = !project.can_render;
    $('renderButton').textContent = project.render_status === 'rendering' ? '合成中…' : (project.render_status === 'completed' ? '重新合成' : '一键合成');
    $('renderHint').textContent = project.can_render
      ? '镜头已全部确认，将使用受控 FFmpeg 参数按脚本顺序合成。'
      : (project.script_stale ? '脚本版本已变化，不能使用旧镜头直接合成。' : '还需确认 ' + Math.max(0, total - approved) + ' 个镜头。');
    $('retryCompile').hidden = !(project.manifest_status === 'failed' || project.manifest_status === 'stale');
    $('finalPanel').hidden = !project.final_url;
    if (project.final_url) protectedMedia(project.final_url, $('finalVideo'), 'final:' + project.updated_at);
    updatePolling();
  }

  async function act(fn) {
    try {
      await fn();
      // 每次写操作后都读取服务端真值。生成接口只返回 202/任务号，若继续
      // 渲染旧 project，镜头仍会停在 pending，轮询也永远不会启动。
      project = await request(basePath());
      render();
    } catch (error) {
      toast(error.message || String(error));
      await refresh(false);
    }
  }

  async function compile(force) {
    $('loadingPanel').hidden = false;
    $('loadingPanel').textContent = '执行导演正在读取已确认脚本和真实素材，生成逐镜头 Prompt…';
    try {
      project = await request(basePath() + '/compile', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({force: !!force})
      });
      render();
    } catch (error) {
      $('loadingPanel').textContent = '脚本解析失败：' + (error.message || error);
      toast(error.message || String(error));
      await refresh(false);
    }
  }

  async function refresh(compileIfMissing) {
    try {
      project = await request(basePath());
      if (compileIfMissing && project.script_status === 'approved' && (project.manifest_status === 'missing' || project.manifest_status === 'stale')) {
        await compile(project.manifest_status === 'stale');
        return;
      }
      render();
    } catch (error) {
      $('loadingPanel').textContent = error.message || String(error);
    }
  }

  function updatePolling() {
    var active = project && (project.render_status === 'rendering' || (project.clips || []).some(function (clip) { return clip.status === 'generating'; }));
    if (active && !pollTimer) {
      pollTimer = setInterval(function () { refresh(false); }, 4000);
    } else if (!active && pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  $('renderButton').addEventListener('click', function () {
    act(async function () {
      await request(basePath() + '/render', {method: 'POST'});
      toast('最终合成已开始');
      project = await request(basePath());
    });
  });
  $('retryCompile').addEventListener('click', function () { compile(true); });
  $('downloadLog').addEventListener('click', async function () {
    try {
      var response = await window.NianAuth.fetch(basePath() + '/render-manifest');
      if (!response.ok) throw new Error('执行记录下载失败');
      var url = URL.createObjectURL(await response.blob());
      var link = document.createElement('a');
      link.href = url; link.download = projectId + '_render_manifest.json';
      document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    } catch (error) { toast(error.message || String(error)); }
  });
  window.addEventListener('beforeunload', function () {
    blobUrls.forEach(function (url) { URL.revokeObjectURL(url); });
  });

  if (!memorialId || !projectId) {
    $('loadingPanel').textContent = '缺少 memorial_id 或 project_id，请从导演脚本面板进入。';
    return;
  }
  refresh(true);
})();
