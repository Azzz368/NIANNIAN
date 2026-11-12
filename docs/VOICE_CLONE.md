# 声音工坊：QwenCloud 克隆与试听

本实现按 Mindverse 的 `VOICE_CLONE_REPRODUCTION.md` 对齐协议；未进行真实付费服务验证。

## 配置

在本机环境配置 QwenCloud 账户的密钥，不要将密钥提交到仓库：

```dotenv
QWEN_API_KEY=<QwenCloud API key>
QWEN_DASHSCOPE_BASE_URL=https://maas.qwencloudapi.com/api/v1
# 可省略，由 HTTP host 推导。
QWEN_TTS_WEBSOCKET_URL=wss://maas.qwencloudapi.com/api-ws/v1/inference
```

`QWEN_API_KEY` 是本项目新增的可选隔离配置。未设置时，使用复现文档中的 `DASHSCOPE_API_KEY`，但它必须是匹配 QwenCloud 的密钥，而不是阿里云 DashScope 密钥。其他聊天、ASR、预制音色路径仍使用原有 DashScope 配置。

注册与合成须使用同一平台和账户，固定模型为 `qwen-audio-3.0-tts-plus`。HTTP/WSS 配置拒绝 `aliyuncs.com`。音色记录保存账户与 HTTP 端点的不可逆指纹，切换密钥会要求切回原配置或重新克隆。

样本优先使用已成功同步的 Bunny HTTPS CDN URL。否则需将 `PUBLIC_BASE_URL` 配置为当前后端可公开访问的 HTTPS 域名；本地开发可使用 HTTPS 隧道。后端生成仅限当前样本、15 分钟有效的签名 URL，不暴露登录 token。请设置强随机 `JWT_SECRET`。不要为此将整个存储桶公开。

## 调用

1. 在声音工坊选择一个本人拥有授权的音频样本，勾选声音所有者授权。
2. `POST /api/memorials/{mid}/voice/clone`：`{"sample_ids":["<asset-id>"],"consent_confirmed":true,"language":"zh"}`。语言可省略。
3. 后端校验 WAV/MP3/M4A MIME 与 1 byte 至 10 MiB 大小，通过 `voice-enrollment` / `create_voice` 注册 HTTPS 样本，然后以 `query_voice` 等待 `OK`。应用不探测采样率、声道或时长，也不将 WebM 改 MIME 冒充 WAV；请先真实转码。
4. `POST /api/memorials/{mid}/voice/preview`：`{"text":"你好，这是试听。","use_clone":true}`。可选 `language`、`instruction`，语言代码支持 `zh/en/de/it/pt/es/ja/ko/fr/ru`。默认沿用克隆语言，未指定时自动识别。
5. 合成使用 Bearer 认证的后端 WebSocket：`run-task` → 等待 `task-started` → `continue-task` → `finish-task`。收到 `task-finished` 且二进制音频非空才返回 `audio/mpeg`。输出 MP3 / 24000 Hz，不是 WAV。

所有配置、克隆、试听接口继续校验当前用户对纪念对象的访问权限；签名样本下载仅在有效签名范围内免登录。

试听文本去空格后为 1–600 个 Unicode 字符，过长报错，不再静默截断。instruction 限 100 个加权字符，基本 CJK 汉字计二。现有情绪选项映射为 instruction；语速、音调、音量仍仅保存为参数，本协议未新增未经文档验证的供应商参数。

## 恢复与限制

- 旧 `qwen3-tts-vc-2026-01-22`、CosyVoice、Mock 音色不能直接用于 Plus；需在对应 QwenCloud 账户重新克隆。
- 不再以 Mock 或预制音色掩盖克隆失败。`use_clone=false` 仍显式调用独立的原有预制音色路径。
- 注册成功立即保存音色 ID；查询超时或失败保留它。可通过“合成并试听”重新查询就绪状态，不必重复付费克隆。确定 `UNDEPLOYED` 时应检查授权/录音并按平台要求重试。
- 上游注册成功但本地保存失败时，接口返回 `VOICE_PERSISTENCE_FAILED` 和音色 ID；请保留 ID 并修复存储后人工恢复，不要再次注册同一声音。
- 注册 HTTP 超时 20 秒；最多 45 秒/45 次查询，单次查询最多 10 秒。WebSocket 握手 20 秒、整体合成 120 秒、音频上限 32 MiB；部署网关超时需相应放宽。
- 诊断接口 `GET /api/memorials/{mid}/voice/diagnose` 检查配置和首个样本的 HTTPS 可访问性，不触发付费注册或合成。该检查不等于验证了供应商侧可达性或账户权限。
- 本次不改数字人对话链路，也不向其他模型传递新的 Plus 音色；需要跨功能复用时须单独确认模型兼容性。

## 本地验证

```bash
python -m unittest discover -s tests -p 'test*voice*.py' -v
```

测试模拟注册和 WebSocket 消息，不使用真实密钥或发起付费请求。