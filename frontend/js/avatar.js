// frontend/js/avatar.js — 可灵官方数字人测试页
(function () {
  const { apiGet, apiPost, esc } = window.NN;
  const state = { image: '', audio: '', taskId: '', timer: null, terminal: false };
  const $ = id => document.getElementById(id);

  function setStatus(message, kind) {
    const el = $('avatarStatus');
    el.textContent = message;
    el.className = `avatar-status${kind ? ` ${kind}` : ''}`;
  }

  function stopPolling() {
    if (state.timer) window.clearInterval(state.timer);
    state.timer = null;
  }

  function rawBase64(file, maxBytes) {
    if (!file) return Promise.reject(new Error('请选择文件'));
    if (file.size > maxBytes) return Promise.reject(new Error(`${file.name} 超过允许大小`));
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const value = String(reader.result || '');
        const comma = value.indexOf(',');
        if (comma < 0) return reject(new Error('文件读取失败'));
        resolve(value.slice(comma + 1));
      };
      reader.onerror = () => reject(new Error('文件读取失败'));
      reader.readAsDataURL(file);
    });
  }

  function setVideo(url, watermarkUrl) {
    const video = $('avatarVideo');
    const download = $('avatarDownload');
    if (!url) return;
    video.src = url;
    video.classList.add('show');
    download.innerHTML = `<a class="btn btn-primary" href="${esc(url)}" target="_blank" download="kling-avatar.mp4">下载数字人视频</a>` +
      (watermarkUrl ? ` <a class="btn btn-ghost" href="${esc(watermarkUrl)}" target="_blank">查看水印版本</a>` : '');
  }

  async function refreshTask() {
    if (!state.taskId) return;
    try {
      const result = await apiGet(`/avatar/tasks/${encodeURIComponent(state.taskId)}`);
      const status = String(result.status || '').toLowerCase();
      $('avatarTaskMeta').textContent = `task_id: ${result.task_id}${result.duration ? ` · ${result.duration}s` : ''}`;
      if (status === 'succeed') {
        state.terminal = true;
        stopPolling();
        setStatus('数字人视频已生成，可直接预览或下载。', 'ok');
        setVideo(result.video_url, result.watermark_url);
      } else if (status === 'failed') {
        state.terminal = true;
        stopPolling();
        setStatus(`任务失败：${result.message || '可灵官方未提供具体原因'}`, 'error');
      } else {
        state.terminal = false;
        setStatus(`任务${status || '处理中'}，正在每 10 秒查询一次…`);
      }
    } catch (error) {
      setStatus(`查询任务失败：${error.message || error}`, 'error');
    }
  }

  async function createTask() {
    if (!state.image || !state.audio) {
      setStatus('请先选择人物参考图和驱动音频。', 'error');
      return;
    }
    const button = $('btnCreateAvatar');
    button.disabled = true;
    stopPolling();
    state.terminal = false;
    $('avatarVideo').classList.remove('show');
    $('avatarDownload').innerHTML = '';
    $('avatarTaskMeta').textContent = '';
    setStatus('正在提交可灵官方数字人任务…');
    try {
      const result = await apiPost('/avatar/tasks', {
        image: state.image,
        sound_file: state.audio,
        prompt: $('avatarPrompt').value.trim(),
        mode: $('avatarMode').value,
        watermark_enabled: $('avatarWatermark').checked,
      });
      state.taskId = result.task_id;
      $('avatarTaskMeta').textContent = `task_id: ${state.taskId}`;
      setStatus(`任务已提交（${result.status || 'submitted'}），正在查询生成进度…`);
      await refreshTask();
      if (state.taskId && !state.terminal && state.timer === null) {
        state.timer = window.setInterval(refreshTask, 10000);
      }
    } catch (error) {
      setStatus(`创建失败：${error.message || error}`, 'error');
    } finally {
      button.disabled = false;
    }
  }

  async function checkConfig() {
    try {
      const info = await apiGet('/avatar/health');
      const el = $('configHint');
      if (info.configured) {
        el.textContent = '可灵官方数字人 API 已配置，可以提交测试任务。';
        el.className = 'avatar-status ok';
      } else {
        el.textContent = '服务端尚未配置 KLING_API_KEY。请在 .env.local 或部署环境变量中填写官方可灵 API Key 后再测试。';
        el.className = 'avatar-status error';
      }
    } catch (error) {
      $('configHint').textContent = `无法检查服务配置：${error.message || error}`;
      $('configHint').className = 'avatar-status error';
    }
  }

  $('avatarImage').addEventListener('change', async event => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    try {
      state.image = await rawBase64(file, 10 * 1024 * 1024);
      $('imagePicked').textContent = `已选择：${file.name}`;
      $('imagePreview').src = URL.createObjectURL(file);
      $('imagePreview').classList.add('show');
    } catch (error) {
      state.image = '';
      $('imagePicked').textContent = error.message || String(error);
      setStatus(error.message || String(error), 'error');
    }
  });

  $('avatarAudio').addEventListener('change', async event => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    try {
      state.audio = await rawBase64(file, 5 * 1024 * 1024);
      $('audioPicked').textContent = `已选择：${file.name}`;
    } catch (error) {
      state.audio = '';
      $('audioPicked').textContent = error.message || String(error);
      setStatus(error.message || String(error), 'error');
    }
  });

  $('btnCreateAvatar').addEventListener('click', createTask);
  window.addEventListener('beforeunload', stopPolling);
  checkConfig();
})();
