// frontend/js/studio.js — 分镜制作台
const { apiGet, apiPost, getSessionId, toast, esc } = window.NN;

const state = {
  sid: getSessionId(),
  scenes: [],        // [{id, time, description, narration, image_url, video_url, image_status, video_status}]
  mv03: null,
  mv04: null,
};

const $ = id => document.getElementById(id);
const show = id => $(id).classList.remove('hidden');
const hide = id => $(id).classList.add('hidden');

function setPill(step, status) {
  const p = document.querySelector(`.studio-pill[data-step="${step}"]`);
  if (!p) return;
  p.classList.remove('active', 'done');
  if (status) p.classList.add(status);
}

function setThink(on, label) {
  $('genThink').classList.toggle('hidden', !on);
  if (on && label) $('genThinkLabel').textContent = label;
}

// ───── 角色档案展示（从 MV03 输出读取）─────
function renderCharSummary() {
  const box = $('charSummary');
  const mv03 = state.mv03 || {};
  if (!mv03 || !Object.keys(mv03).length) {
    box.innerHTML = `<div class="text-muted">尚未读取到角色档案，请先完成方案确认台。</div>`;
    return;
  }

  // 收集主角和配角
  const protagonist = mv03.protagonist || mv03.main_character || mv03.主角 || null;
  const supporting = mv03.supporting_characters || mv03.supporting || mv03.配角 || [];
  const tone = mv03.tone || mv03.基调 || mv03.style || '';
  const atmosphere = mv03.atmosphere || mv03.画面氛围 || mv03.visual_style || '';

  let html = '';
  if (tone) html += `<div class="char-meta" style="margin-bottom:8px;"><b>基调：</b>${esc(typeof tone === 'string' ? tone : JSON.stringify(tone))}</div>`;
  if (atmosphere) html += `<div class="char-meta" style="margin-bottom:12px;"><b>画面氛围：</b>${esc(typeof atmosphere === 'string' ? atmosphere : JSON.stringify(atmosphere))}</div>`;

  html += `<div class="char-grid">`;
  const chars = [];
  if (protagonist) chars.push({ ...protagonist, _role: '主角' });
  const supArr = Array.isArray(supporting) ? supporting : (supporting && typeof supporting === 'object' ? Object.values(supporting) : []);
  supArr.forEach(c => chars.push({ ...c, _role: '配角' }));

  if (!chars.length) {
    html += `<div class="text-muted">（无角色信息）</div>`;
  } else {
    chars.forEach(c => {
      const name = c.name || c.姓名 || '未命名';
      const role = c._role || '';
      const desc = c.description || c.appearance || c.外貌 || c.形象 || '';
      html += `<div class="char-card">
        <div class="char-name">${esc(name)} <span style="font-size:.7rem;color:var(--gold);">· ${esc(role)}</span></div>
        ${desc ? `<div class="char-meta">${esc(typeof desc === 'string' ? desc : JSON.stringify(desc))}</div>` : ''}
      </div>`;
    });
  }
  html += `</div>`;
  box.innerHTML = html;
}

// ───── 分镜卡片渲染 ─────
function renderScenes() {
  const list = $('sceneList');
  list.innerHTML = '';
  if (!state.scenes.length) {
    list.innerHTML = `<div class="text-muted">（暂无分镜）</div>`;
    return;
  }
  state.scenes.forEach((sc, i) => {
    const id = sc.id || sc.scene_id || `S${String(i + 1).padStart(2, '0')}`;
    const time = sc.time || sc.duration || '';
    const desc = sc.description || sc.scene_desc || sc.prompt_global || sc.visual || '';
    const narr = sc.narration || sc.voiceover || sc.subtitle || '';
    const imgStatus = sc._img_status || 'idle';
    const vidStatus = sc._vid_status || 'idle';
    const imgBadge =
      imgStatus === 'done' ? '<span class="badge badge-done">✓ 已生成</span>' :
      imgStatus === 'run'  ? '<span class="badge badge-run">⏳ 生成中</span>' :
      imgStatus === 'err'  ? '<span class="badge badge-err">✗ 失败</span>' :
      '<span class="badge badge-idle">未生成</span>';
    const vidBadge =
      vidStatus === 'done' ? '<span class="badge badge-done">✓ 已生成</span>' :
      vidStatus === 'run'  ? '<span class="badge badge-run">⏳ 生成中</span>' :
      vidStatus === 'err'  ? '<span class="badge badge-err">✗ 失败</span>' :
      '<span class="badge badge-idle">未生成</span>';

    const imgHtml = sc._img_url
      ? `<div class="media-slot has-media"><img src="${esc(sc._img_url)}" alt="scene image"></div>`
      : `<div class="media-slot">🖼 画面图片<br/>${imgBadge}</div>`;
    const vidHtml = sc._vid_url
      ? `<div class="media-slot has-media"><video controls src="${esc(sc._vid_url)}"></video></div>`
      : `<div class="media-slot">🎬 短视频<br/>${vidBadge}</div>`;

    list.insertAdjacentHTML('beforeend', `
      <div class="scene-row" data-idx="${i}">
        <div class="scene-head">
          <div><span class="scene-num">${i + 1}</span><span class="scene-id">${esc(id)}</span></div>
          <div class="scene-meta">${time ? `⏱ ${esc(time)}` : ''}</div>
        </div>
        ${desc ? `<div class="scene-desc">${esc(desc)}</div>` : ''}
        ${narr ? `<div class="scene-narr">🎙 ${esc(narr)}</div>` : ''}
        <div class="scene-media">${imgHtml}${vidHtml}</div>
        <div class="scene-actions">
          <button class="btn" data-act="img" data-idx="${i}" ${imgStatus === 'run' ? 'disabled' : ''}>${sc._img_url ? '重新生成图片' : '生成图片'}</button>
          <button class="btn" data-act="vid" data-idx="${i}" ${vidStatus === 'run' || !sc._img_url ? 'disabled' : ''}>${sc._vid_url ? '重新生成视频' : '生成视频'}</button>
        </div>
      </div>
    `);
  });

  // 绑定按钮
  list.querySelectorAll('button[data-act]').forEach(btn => {
    btn.onclick = () => {
      const idx = +btn.dataset.idx;
      const act = btn.dataset.act;
      if (act === 'img') genSceneImage(idx);
      else if (act === 'vid') genSceneVideo(idx);
    };
  });
}

// ───── 生成 MV04 分镜 ─────
async function genScenes() {
  hide('phaseError');
  setPill('MV04', 'active');
  setThink(true, '念念正在编排分镜（约 30 秒）...');
  $('btnGenScenes').disabled = true;
  try {
    const res = await apiPost(`/pipeline/run/MV04/${state.sid}`, {});
    if (res.error) throw new Error(res.message || 'MV04 失败');
    state.mv04 = res.result;
    // 提取 scenes
    let scenes = [];
    if (Array.isArray(res.result.scenes)) scenes = res.result.scenes;
    else if (res.result.scenes && typeof res.result.scenes === 'object') {
      scenes = Object.keys(res.result.scenes).sort().map(k => res.result.scenes[k]);
    } else if (Array.isArray(res.result.storyboard)) scenes = res.result.storyboard;
    state.scenes = scenes.filter(x => x && typeof x === 'object');
    setPill('MV04', 'done');
    setThink(false);
    hide('phaseGenScenes');
    show('phaseScenes');
    renderScenes();
  } catch (e) {
    setThink(false);
    setPill('MV04', '');
    $('btnGenScenes').disabled = false;
    $('errorOutput').textContent = e.message || String(e);
    show('phaseError');
  }
}

// ───── 单镜图片生成 ─────
async function genSceneImage(idx) {
  const sc = state.scenes[idx];
  if (!sc) return;
  sc._img_status = 'run';
  renderScenes();
  setPill('MV05', 'active');
  try {
    const res = await apiPost(`/pipeline/scene/image/${state.sid}/${idx}`, {});
    if (res.error) throw new Error(res.message || '图片生成失败');
    sc._img_url = res.url || res.image_url;
    sc._img_status = 'done';
  } catch (e) {
    sc._img_status = 'err';
    toast('图片生成失败：' + e.message);
  } finally {
    renderScenes();
    if (state.scenes.every(s => s._img_url)) setPill('MV05', 'done');
  }
}

// ───── 单镜视频生成 ─────
async function genSceneVideo(idx) {
  const sc = state.scenes[idx];
  if (!sc || !sc._img_url) { toast('请先生成图片'); return; }
  sc._vid_status = 'run';
  renderScenes();
  try {
    const res = await apiPost(`/pipeline/scene/video/${state.sid}/${idx}`, {
      image_url: sc._img_url,
    });
    if (res.error) throw new Error(res.message || '视频生成失败');
    sc._vid_url = res.url || res.video_url;
    sc._vid_status = 'done';
  } catch (e) {
    sc._vid_status = 'err';
    toast('视频生成失败：' + e.message);
  } finally {
    renderScenes();
  }
}

// ───── 最终合成 MV06 ─────
async function finalCut() {
  const btn = $('btnFinalCut');
  const old = btn.textContent;
  btn.disabled = true; btn.textContent = '合成中...';
  setPill('MV06', 'active');
  try {
    const res = await apiPost(`/pipeline/run/MV06/${state.sid}`, {});
    if (res.error) throw new Error(res.message || 'MV06 失败');
    setPill('MV06', 'done');
    const url = (res.result && (res.result.final_video_url || res.result.url)) || '';
    $('finalOutput').innerHTML = url
      ? `<video controls style="width:100%;border-radius:10px;" src="${esc(url)}"></video>
         <div style="margin-top:8px;"><a class="btn btn-primary" href="${esc(url)}" download>下载影像</a></div>`
      : `<pre style="background:var(--surf2);padding:10px;border-radius:8px;font-size:.78rem;overflow-x:auto;">${esc(JSON.stringify(res.result, null, 2))}</pre>`;
    show('phaseFinal');
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
  } catch (e) {
    setPill('MV06', '');
    $('errorOutput').textContent = e.message || String(e);
    show('phaseError');
  } finally {
    btn.disabled = false; btn.textContent = old;
  }
}

// ───── 启动 ─────
async function bootstrap() {
  if (!state.sid) {
    toast('请先完成前期访谈');
    setTimeout(() => location.href = 'memorial.html', 1500);
    return;
  }
  // 读取已有 MV03（角色档案）
  try {
    const r = await apiGet(`/pipeline/output/${state.sid}/MV03`);
    state.mv03 = r.result;
    renderCharSummary();
  } catch {
    $('charSummary').innerHTML = `<div class="text-muted" style="color:var(--red);">未找到角色档案，请先在「方案确认台」完成前期流程。</div>`;
  }
  // 若已有 MV04 输出，直接跳过生成阶段
  try {
    const r = await apiGet(`/pipeline/output/${state.sid}/MV04`);
    state.mv04 = r.result;
    let scenes = Array.isArray(r.result.scenes) ? r.result.scenes :
                 (Array.isArray(r.result.storyboard) ? r.result.storyboard : []);
    state.scenes = scenes.filter(x => x && typeof x === 'object');
    if (state.scenes.length) {
      setPill('MV04', 'done');
      hide('phaseGenScenes');
      show('phaseScenes');
      renderScenes();
    }
  } catch { /* 没生成过则保持初始 UI */ }
}

document.addEventListener('DOMContentLoaded', () => {
  bootstrap();
  $('btnGenScenes').onclick = genScenes;
  $('btnFinalCut').onclick = finalCut;
});
