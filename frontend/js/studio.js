// frontend/js/studio.js — 分镜制作台
const { apiGet, apiPost, getSessionId, toast, esc } = window.NN;

const state = {
  sid:            getSessionId(),
  mid:            new URLSearchParams(location.search).get('mid') || (window.NianAuth && NianAuth.getActiveMemorialId()) || '',
  scenes:         [],
  chars:          null,
  mv04:           null,
  libImages:      [],     // 素材库中的图片资产
  refB64:         '',     // 角色档案卡片当前选中的参考图 base64（仅用于展示/默认值）
  refAsset:       null,   // 角色档案卡片当前选中的资产对象
  refB64Cache:    new Map(), // asset_id -> base64，避免同一张照片重复下载
};

const $    = id => document.getElementById(id);
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

function normalizeSceneMedia(sc) {
  if (!sc || typeof sc !== 'object') return sc;
  if (!sc._img_url && sc._image_data_url) sc._img_url = sc._image_data_url;
  if (!sc._vid_url && sc._video_url) sc._vid_url = sc._video_url;
  if (sc._img_url && !sc._img_status) sc._img_status = 'done';
  if (sc._vid_url && !sc._vid_status) sc._vid_status = 'done';
  return sc;
}

// ───── 角色档案展示（含照片选择槽）─────
function renderCharSummary() {
  const box = $('charSummary');
  const c = state.chars;
  if (!c || !c.main) {
    box.innerHTML = `<div class="text-muted">尚未读取到角色档案，请先完成方案确认台。</div>`;
    return;
  }
  const main = c.main;

  // 主角照片槽
  const hasLib = state.libImages.length > 0;
  let photoHtml;
  if (state.refB64 && state.refAsset) {
    const tok = localStorage.getItem('nian_token') || '';
    const dispUrl = state.refAsset.url + (state.refAsset.url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(tok);
    photoHtml = `
      <div class="char-photo-slot has-photo" id="mainPhotoSlot" title="点击更换参考照片">
        <img src="${esc(dispUrl)}" alt="参考图">
      </div>
      <div class="char-ref-badge" style="color:var(--green);">✓ 已选参考图</div>`;
  } else if (main.photo_url) {
    const tok = localStorage.getItem('nian_token') || '';
    const dispUrl = main.photo_url + (main.photo_url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(tok);
    photoHtml = `
      <div class="char-photo-slot has-photo" id="mainPhotoSlot" title="点击更换参考照片">
        <img src="${esc(dispUrl)}" alt="主角参考图">
      </div>
      <div class="char-ref-badge" style="color:var(--green);">✓ 主角参考图</div>`;
  } else if (hasLib) {
    photoHtml = `
      <div class="char-photo-slot" id="mainPhotoSlot" title="点击选择参考照片">
        <div class="char-photo-slot-hint">点击选<br>参考图</div>
      </div>
      <div class="char-ref-badge" style="color:var(--muted-l);">未选参考图</div>`;
  } else {
    photoHtml = `
      <div class="char-photo-slot" id="mainPhotoSlot" style="cursor:default;" title="素材库暂无照片">
        <div class="char-photo-slot-hint">无照片</div>
      </div>
      <div class="char-ref-badge" style="color:var(--muted-l);">未上传照片</div>`;
  }

  let html = `<div class="char-grid">
    <div class="char-card" style="display:flex;gap:12px;align-items:flex-start;">
      <div style="flex-shrink:0;text-align:center;">
        ${photoHtml}
      </div>
      <div style="flex:1;min-width:0;">
        <div class="char-name">${esc(main.name)} <span style="font-size:.7rem;color:var(--gold);">· ${esc(main.role_label || '')}</span></div>
        ${main.description ? `<div class="char-meta">${esc(main.description)}</div>` : ''}
      </div>
    </div>`;

  (c.supporting || []).forEach(ch => {
    html += `<div class="char-card">
      <div class="char-name">${esc(ch.name)} <span style="font-size:.7rem;color:var(--gold);">· ${esc(ch.role_label || '')}</span></div>
      ${ch.description ? `<div class="char-meta">${esc(ch.description)}</div>` : ''}
    </div>`;
  });
  html += `</div>`;
  box.innerHTML = html;

  // 绑定照片槽点击
  const slot = $('mainPhotoSlot');
  if (slot && hasLib) {
    slot.onclick = openPhotoPicker;
  }
}

// ───── 照片选择器弹窗 ─────
function openPhotoPicker() {
  const overlay = $('photoPickerOverlay');
  const tok = localStorage.getItem('nian_token') || '';
  const imgs = state.libImages;

  const itemsHtml = imgs.length
    ? imgs.map((a, i) => {
        const dispUrl = a.url + (a.url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(tok);
        const isActive = state.refAsset && state.refAsset.asset_id === a.asset_id ? ' active' : '';
        return `<div class="photo-picker-item${isActive}" data-idx="${i}" title="${esc(a.filename || '')}">
          <img src="${esc(dispUrl)}" alt="${esc(a.filename || '')}" loading="lazy">
          <div class="ppi-name">${esc(a.filename || '照片' + (i + 1))}</div>
        </div>`;
      }).join('')
    : `<div class="photo-picker-empty">素材库暂无图片，请先在「素材库」上传照片</div>`;

  overlay.innerHTML = `
    <div class="photo-picker-box">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div class="photo-picker-title">选择参考照片（AI 将保留 Ta 的面貌特征）</div>
        <button style="background:none;border:none;font-size:1.4rem;cursor:pointer;color:var(--muted-l);padding:0 4px;line-height:1;" onclick="closePhotoPicker()">×</button>
      </div>
      <div class="photo-picker-grid">${itemsHtml}</div>
      <div style="margin-top:14px;display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap;">
        ${state.refB64 ? `<button class="btn" id="pickerClearBtn">清除参考图（纯文生图）</button>` : ''}
        <button class="btn btn-ghost" onclick="closePhotoPicker()">取消</button>
      </div>
    </div>`;
  overlay.style.display = 'flex';

  overlay.querySelectorAll('.photo-picker-item').forEach(el => {
    el.onclick = () => selectRefPhotoFromLib(+el.dataset.idx);
  });
  overlay.onclick = e => { if (e.target === overlay) closePhotoPicker(); };

  if (state.refB64) {
    const clearBtn = $('pickerClearBtn');
    if (clearBtn) clearBtn.onclick = () => {
      state.refB64 = '';
      state.refAsset = null;
      closePhotoPicker();
      renderCharSummary();
      toast('已清除主角参考图（各分镜仍可单独选择参考照片）');
    };
  }
}

function closePhotoPicker() {
  const o = $('photoPickerOverlay');
  if (o) o.style.display = 'none';
}

async function fetchAssetBase64(asset) {
  if (!asset || !asset.asset_id) return '';
  if (state.refB64Cache.has(asset.asset_id)) return state.refB64Cache.get(asset.asset_id);
  const tok = localStorage.getItem('nian_token') || '';
  const r = await fetch(asset.url, { headers: tok ? { 'Authorization': 'Bearer ' + tok } : {} });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const blob = await r.blob();
  const b64 = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
  state.refB64Cache.set(asset.asset_id, b64);
  return b64;
}

async function selectRefPhotoFromLib(idx) {
  const a = state.libImages[idx];
  if (!a) return;
  closePhotoPicker();
  toast('正在加载照片...');
  try {
    state.refB64 = await fetchAssetBase64(a);
    state.refAsset = a;
    renderCharSummary();
    toast('主角参考图已选：' + (a.filename || '照片') + '（各分镜仍可单独选择）');
  } catch (e) {
    state.refB64 = '';
    state.refAsset = null;
    toast('照片加载失败：' + e.message);
  }
}

// ───── 每个分镜独立的参考照片选择 ─────
function renderSceneRefBar(sc, i) {
  const tok = localStorage.getItem('nian_token') || '';
  const noneActive = !sc._refAssetId ? ' active' : '';
  const items = [`<div class="ref-photo-item${noneActive}" data-idx="${i}" data-ref="none" title="不用参考，纯文生图"><div class="ref-photo-none">不用参考<br>纯文生图</div></div>`];
  state.libImages.forEach((a, ai) => {
    const dispUrl = a.url + (a.url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(tok);
    const active = sc._refAssetId === a.asset_id ? ' active' : '';
    items.push(`<div class="ref-photo-item${active}" data-idx="${i}" data-ref="${ai}" title="${esc(a.filename || '')}"><img src="${esc(dispUrl)}" alt="${esc(a.filename || '')}" loading="lazy"></div>`);
  });
  return `<div class="ref-photo-bar scene-ref-bar">
    <div class="ref-photo-label">参考照片 · 图生图（本镜专用，可与其他分镜不同）</div>
    <div class="ref-photo-list">${items.join('')}</div>
  </div>`;
}

async function selectSceneRefPhoto(sceneIdx, libIdx) {
  const sc = state.scenes[sceneIdx];
  const asset = state.libImages[libIdx];
  if (!sc || !asset) return;
  try {
    await fetchAssetBase64(asset); // 预热缓存，生成时直接复用
    sc._refAssetId = asset.asset_id;
    renderScenes();
    toast(`分镜 ${sceneIdx + 1} 的参考照片已选：` + (asset.filename || '照片'));
  } catch (e) {
    toast('照片加载失败：' + e.message);
  }
}

function clearSceneRefPhoto(sceneIdx) {
  const sc = state.scenes[sceneIdx];
  if (!sc) return;
  sc._refAssetId = '';
  renderScenes();
}

// 若分镜绑定了真实素材（例如从资料库匹配到的照片），默认把它设为该分镜的参考图；
// 用户仍可在分镜卡片里随时更换或取消。
function initSceneRefDefaults() {
  if (!state.libImages.length) return;
  const byId = new Map(state.libImages.map(a => [a.asset_id, a]));
  state.scenes.forEach(sc => {
    if (sc._refAssetId) return;
    const sourceImg = (sc.source_assets || []).find(a => a && a.kind === 'image' && byId.has(a.asset_id));
    if (sourceImg) { sc._refAssetId = sourceImg.asset_id; return; }
    if (state.refAsset && byId.has(state.refAsset.asset_id)) sc._refAssetId = state.refAsset.asset_id;
  });
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
    const id   = sc.id || sc.scene_id || `S${String(i + 1).padStart(2, '0')}`;
    const time = sc.time || sc.duration || '';
    const desc = sc.description || sc.scene_desc || sc.prompt_global || sc.visual || '';
    const narr = sc.narration   || sc.voiceover  || sc.subtitle      || '';
    const sourceAssets = Array.isArray(sc.source_assets) ? sc.source_assets : [];
    const sourceHtml = sourceAssets.length
      ? `<div class="scene-narr" style="margin-top:8px;">
           真实素材：${sourceAssets.map(asset =>
             `<span title="${esc(asset.user_description || asset.ai_summary || '')}">${esc(asset.filename || asset.asset_id)}</span>`
           ).join('、')}
         </div>`
      : `<div class="scene-narr" style="margin-top:8px;color:var(--muted-l);">本镜暂无匹配的真实画面，将使用 AI 补充</div>`;
    const imgStatus = sc._img_status || 'idle';
    const vidStatus = sc._vid_status || 'idle';

    const imgBadge =
      imgStatus === 'done' ? '<span class="badge badge-done">已生成</span>' :
      imgStatus === 'run'  ? '<span class="badge badge-run">生成中...</span>' :
      imgStatus === 'err'  ? '<span class="badge badge-err">失败</span>' :
                              '<span class="badge badge-idle">未生成</span>';
    const vidBadge =
      vidStatus === 'done' ? '<span class="badge badge-done">已生成</span>' :
      vidStatus === 'run'  ? '<span class="badge badge-run">生成中（约 1-3 分钟）</span>' :
      vidStatus === 'err'  ? '<span class="badge badge-err">失败</span>' :
                              '<span class="badge badge-idle">未生成</span>';

    const imgHtml = sc._img_url
      ? `<div class="media-slot has-media">
           <img class="zoomable" data-idx="${i}" src="${esc(sc._img_url)}" alt="scene image">
           <div class="media-cap">${sc._image_source_asset_id ? '已参考真实素材生成 · ' : ''}点击图片放大查看</div>
         </div>`
      : `<div class="media-slot"><div class="media-cap">画面图片</div>${imgBadge}</div>`;

    const vidHtml = sc._vid_url
      ? `<div class="media-slot has-media">
           <video controls preload="metadata" src="${esc(sc._vid_url)}"></video>
           <div class="media-cap" style="margin-top:6px;">
             <a class="btn btn-sm" href="${esc(sc._vid_url)}" download="scene-${String(i + 1).padStart(2, '0')}.mp4" target="_blank">下载视频</a>
           </div>
         </div>`
      : `<div class="media-slot"><div class="media-cap">短视频</div>${vidBadge}</div>`;

    list.insertAdjacentHTML('beforeend', `
      <div class="scene-row" data-idx="${i}">
        <div class="scene-head">
          <div><span class="scene-num">${i + 1}</span><span class="scene-id">${esc(id)}</span></div>
          <div class="scene-meta">${time ? esc(time) : ''}</div>
        </div>
        ${desc ? `<div class="scene-desc">${esc(desc)}</div>` : ''}
        ${narr ? `<div class="scene-narr">${esc(narr)}</div>` : ''}
        ${sourceHtml}
        ${state.libImages.length ? renderSceneRefBar(sc, i) : ''}
        <div class="scene-media">${imgHtml}${vidHtml}</div>
        <div class="scene-actions">
          <button class="btn" data-act="img" data-idx="${i}" ${imgStatus === 'run' ? 'disabled' : ''}>${sc._img_url ? '重新生成画面' : '生成 AI 图片'}</button>
          <button class="btn" data-act="vid" data-idx="${i}" ${vidStatus === 'run' || !sc._img_url ? 'disabled' : ''}>${sc._vid_url ? '重新生成视频' : '生成视频'}</button>
        </div>
      </div>
    `);
  });

  list.querySelectorAll('button[data-act]').forEach(btn => {
    const act = btn.dataset.act;
    btn.onclick = () => {
      const idx = +btn.dataset.idx;
      if (act === 'img') genSceneImage(idx);
      else if (act === 'vid') genSceneVideo(idx);
    };
  });

  list.querySelectorAll('.scene-ref-bar [data-ref]').forEach(el => {
    el.onclick = () => {
      const idx = +el.dataset.idx;
      const ref = el.dataset.ref;
      if (ref === 'none') clearSceneRefPhoto(idx);
      else selectSceneRefPhoto(idx, +ref);
    };
  });

  list.querySelectorAll('img.zoomable').forEach(img => {
    img.onclick = () => openLightbox(img.src);
  });
}

// ───── 图片 Lightbox（点击放大）─────
function openLightbox(src) {
  let bg = $('lightbox');
  if (!bg) {
    bg = document.createElement('div');
    bg.id = 'lightbox';
    bg.className = 'lightbox';
    bg.innerHTML = `<img class="lightbox-img" alt=""><button class="lightbox-close" type="button" aria-label="关闭">×</button>`;
    document.body.appendChild(bg);
    bg.addEventListener('click', e => {
      if (e.target === bg || e.target.classList.contains('lightbox-close')) closeLightbox();
    });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });
  }
  bg.querySelector('.lightbox-img').src = src;
  bg.classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeLightbox() {
  const bg = $('lightbox');
  if (bg) bg.classList.remove('open');
  document.body.style.overflow = '';
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
    let scenes = [];
    if (Array.isArray(res.result.scenes)) scenes = res.result.scenes;
    else if (res.result.scenes && typeof res.result.scenes === 'object') {
      scenes = Object.keys(res.result.scenes).sort().map(k => res.result.scenes[k]);
    } else if (Array.isArray(res.result.storyboard)) scenes = res.result.storyboard;
    state.scenes = scenes.filter(x => x && typeof x === 'object').map(normalizeSceneMedia);
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
    const body = {};
    if (sc._refAssetId) {
      const refAsset = state.libImages.find(a => a.asset_id === sc._refAssetId);
      if (refAsset) body.ref_b64 = await fetchAssetBase64(refAsset);
    }
    const res = await apiPost(`/pipeline/scene/image/${state.sid}/${idx}`, body);
    if (res.error) throw new Error(res.message || '图片生成失败');
    sc._img_url    = res.url || res.image_url;
    sc._img_status = 'done';
    sc._image_reused = !!res.reused;
    // 用户在本镜手动选的参考图优先展示为“已参考真实素材”；否则以后端自动匹配结果为准。
    sc._image_source_asset_id = sc._refAssetId || res.source_asset_id || '';
    if (sc._image_source_asset_id) toast('已参考真实素材生成画面');
  } catch (e) {
    sc._img_status = 'err';
    toast('图片生成失败：' + e.message);
  } finally {
    renderScenes();
    if (state.scenes.length && state.scenes.every(s => s._img_url)) setPill('MV05', 'done');
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
    sc._vid_url    = res.url || res.video_url;
    sc._vid_status = 'done';
  } catch (e) {
    sc._vid_status = 'err';
    toast('视频生成失败：' + e.message);
  } finally {
    renderScenes();
  }
}

// ───── 素材库照片加载 & 参考图选择 ─────
function isImageAsset(asset) {
  return asset.kind === 'image' || /^image\//i.test(asset.mime || '') ||
    /\.(jpe?g|png|webp|gif)$/i.test(asset.filename || '');
}

async function selectPreferredReferencePhoto() {
  if (state.refB64 || !state.libImages.length) return;
  const preferredId = state.chars?.main?.reference_asset_id || '';
  const preferredUrl = state.chars?.main?.photo_url || '';
  const preferredIndex = state.libImages.findIndex(a =>
    (preferredId && a.asset_id === preferredId) || (preferredUrl && a.url === preferredUrl)
  );
  await selectRefPhotoFromLib(preferredIndex >= 0 ? preferredIndex : 0);
}

function refreshReferencePhotoUi() {
  renderCharSummary();
  initSceneRefDefaults();
  if (state.scenes.length) renderScenes();
}

async function loadLibraryAssets() {
  if (!state.mid) return;
  const tok = localStorage.getItem('nian_token') || '';
  if (!tok) return;
  try {
    const res = await fetch(`/api/memorials/${encodeURIComponent(state.mid)}`, {
      headers: { 'Authorization': 'Bearer ' + tok }
    });
    if (!res.ok) return;
    const d = await res.json();
    state.libImages = (d.assets || []).filter(isImageAsset);
    refreshReferencePhotoUi();
    await selectPreferredReferencePhoto();
  } catch(e) {
    console.warn('[studio] 加载素材库照片失败:', e);
  }
}

async function loadSessionAssets() {
  if (!state.sid) return;
  try {
    const res = await apiGet(`/assets/list/${state.sid}`);
    const sessionImages = (res.assets || [])
      .filter(isImageAsset)
      .map((asset, index) => ({ ...asset, asset_id: asset.asset_id || `session-image-${index}` }));
    if (!sessionImages.length) return;
    const knownUrls = new Set(state.libImages.map(asset => asset.url));
    state.libImages.push(...sessionImages.filter(asset => !knownUrls.has(asset.url)));
    refreshReferencePhotoUi();
    await selectPreferredReferencePhoto();
  } catch(e) {
    console.warn('[studio] 加载会话照片失败:', e);
  }
}

// ───── 最终合成 MV06（调用服务端 FFmpeg 拼接）─────
async function finalCut() {
  const btn = $('btnFinalCut');
  const old = btn.textContent;
  btn.disabled = true; btn.textContent = '合成中...';
  setPill('MV06', 'active');
  try {
    const generatedCount = state.scenes.filter(sc => sc._vid_url || sc._video_url).length;
    if (!generatedCount) throw new Error('没有可合成的分镜视频，请先生成至少一段短视频');

    const res = await apiPost(`/pipeline/final-cut/${state.sid}`, {});
    if (res.error) throw new Error(res.message || '最终影像合成失败');
    setPill('MV06', 'done');
    const url = res.url || res.final_video_url || '';
    $('finalOutput').innerHTML = url
      ? `<video controls style="width:100%;border-radius:10px;" src="${esc(url)}"></video>
         <div style="margin-top:8px;"><a class="btn btn-primary" href="${esc(url)}" download="niannian-memorial.mp4" target="_blank">下载完整影像</a></div>`
      : `<pre style="background:var(--surf2);padding:10px;border-radius:8px;font-size:.78rem;overflow-x:auto;">${esc(JSON.stringify(res, null, 2))}</pre>`;
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
  // 1. 角色档案
  try {
    state.chars = await apiGet(`/pipeline/characters/${state.sid}`);
    renderCharSummary();
  } catch {
    $('charSummary').innerHTML = `<div class="text-muted" style="color:var(--red);">未找到角色档案，请先在「方案确认台」完成前期流程。</div>`;
  }
  // 2. 已有 MV04 则直接展示
  try {
    const r = await apiGet(`/pipeline/scenes/${state.sid}`);
    if (r.ready && Array.isArray(r.scenes) && r.scenes.length) {
      state.scenes = r.scenes.map(normalizeSceneMedia);
      setPill('MV04', 'done');
      if (state.scenes.every(sc => sc._vid_url)) setPill('MV05', 'done');
      hide('phaseGenScenes');
      show('phaseScenes');
      renderScenes();
    }
  } catch { /* 没生成过则保持初始 UI */ }

  // 3. 加载素材库图片（若 URL 含 ?mid=）
  await loadLibraryAssets();
  // 未登录上传的照片保存在会话中，也同样可作为 GPT Image 图生图参考。
  await loadSessionAssets();
}

document.addEventListener('DOMContentLoaded', () => {
  bootstrap();
  $('btnGenScenes').onclick = genScenes;
  $('btnFinalCut').onclick  = finalCut;
});
