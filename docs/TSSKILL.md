---
name: tokenstar-codex-gateway
description: Configure AI agents, Codex, Claude Code, OpenClaw, OpenAI-compatible clients, and media workflows to use TokenStar Gateway. Use when a user asks about TokenStar API integration, Base URLs, API key handling, text/image/video generation, asset upload, callbacks, model choice, Codex provider config, Claude Code variables, or troubleshooting TokenStar Gateway requests.
---

# TokenStar API and Gateway Agent Guide

<!-- skill-version: 2026-07-09 18:30:00 +0800 -->

Use this skill as the AI-readable compressed version of the TokenStar public docs. The user should not need to scan https://tokenstar.world/console/doc manually before an agent can start an integration. Keep examples minimal, preserve protocol facts, and check the public docs for live changes before claiming a preview or hidden capability is available.

## Safety Rules

- Never write a real API key into this skill file.
- Prefer `TOKENSTAR_API_KEY` for TokenStar-specific configs and `ANTHROPIC_API_KEY` only where Claude Code requires that variable name.
- Do not overwrite a user's global `OPENAI_API_KEY` with a TokenStar key unless the target client cannot use a custom env var and the user explicitly wants an isolated shell.
- Keep placeholders like `${TOKENSTAR_API_KEY}` in examples. If a user provides a key for a local shell, use it only in that shell/session and do not save it back into generated files.
- Do not print, log, persist, or add API keys to URLs, localStorage, sessionStorage, cookies, or generated files.
- If a website offers a separate runtime config snippet with a real key, treat it as separate from `SKILL.md` and warn before copying or storing it.

## Gateway URLs

- TokenStar Gateway root: `https://api.tokenstar.world`
- OpenAI-compatible and Codex Base URL: `https://api.tokenstar.world/v1`
- Claude Code `ANTHROPIC_BASE_URL`: `https://api.tokenstar.world`
- OpenAI-compatible clients usually need `/v1` in the Base URL.
- Claude Code uses the gateway root and must not append `/v1` to `ANTHROPIC_BASE_URL`.

## Agent Task Selector

- User wants a normal chat/text API or OpenAI SDK compatibility: use Chat Completions with `POST /v1/chat/completions` and `Authorization: Bearer ${TOKENSTAR_API_KEY}`.
- User wants Codex custom provider or OpenAI Responses semantics: use Responses with `POST /v1/responses`, `base_url = "<gateway>/v1"`, and `wire_api = "responses"`.
- User wants Claude Code: set `ANTHROPIC_BASE_URL` to the gateway root without `/v1`; set `ANTHROPIC_API_KEY`; add `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`.
- User wants image generation/editing: use gpt-image endpoints for `/v1/images/generations` and `/v1/images/edits`; use Gemini-compatible image models with `generateContent` when that model family is requested.
- User wants Seedance video without a reference person: create `POST /v1/video/generations`, save `id` or `task_id`, then query `GET /v1/video/generations/{task_id}`.
- User wants Seedance reference-person video: list/reuse asset groups and assets first, then reference cached assets in video content as `asset://<Id>`.
- User wants Kling text-to-video: create `POST /v1/videos/text2video`, save `data.task_id`, then query `GET /v1/videos/text2video/{task_id}`.
- User wants Kling image-to-video or subject consistency: create `POST /v1/videos/image2video`; use top-level `image`; use `element_list[].element_id` only after `DescribeAigcElement` reports `Status=succeed`.
- User wants Kling Omni video edit: create `POST /v1/videos/omni-video` with `video_list[].video_url`; add `element_list[].element_id` only for ready subject elements.
- User wants Kling motion control: create `POST /v1/videos/motion-control` with `image_url`, `video_url`, `prompt`, and `character_orientation`; query `GET /v1/videos/motion-control/{task_id}`.
- Legacy Kling /v1/video/generations + X-TC-Action docs are only for existing integrations, migration, and historical troubleshooting: https://tokenstar.world/console/doc/kling-legacy.
- User wants callbacks: pass an HTTPS `callback_url` only when that video API explicitly supports it. Current Kling `/v1/videos/*` docs do not publicly provide or recommend relying on `callback_url`; poll by task ID instead. If TokenStar provides a documented callback signature or shared-secret mechanism, verify it before trusting the payload; otherwise reconcile by querying the task status endpoint. Return HTTP 2xx and process callbacks idempotently by task ID.
- User wants high-volume traffic: follow the 429 section; do not invent per-account QPS or video concurrency numbers.
- If model support, pricing, or release status is uncertain, stop and check https://tokenstar.world/console/models or https://tokenstar.world/console/doc before inventing capabilities.

## Models

- Verified as of 2026-07-09. Live-check https://tokenstar.world/console/doc and https://tokenstar.world/console/models before executing requests or promising a model is still available.
- Recommended defaults: `gpt-5.4`, `qwen3.7-plus`, `claude-sonnet-4-6-thinking`.
- Built-in model IDs visible in the docs: `kimi-k2.5`, `qwen3.7-plus`, `qwen3.5-flash`, `qwen3-coder-plus`, `MiniMax-M2.5`, `glm-5`, `gemini-3.1-pro-preview`, `gemini-3.1-flash-lite-preview`, `gpt-5.4`, `gpt-5.4-mini`, `claude-sonnet-4-6-thinking`, `claude-opus-4-6-thinking`.
- Use text-capable models for chat and Responses. Use image-capable models for multimodal prompts. Do not invent model IDs.
- Runnable examples in this skill are limited to verified endpoint paths: `/v1/chat/completions`, `/v1/responses`.
- Treat preview or hidden capabilities as unavailable unless the current public docs or TokenStar support explicitly confirm access.

## Model Discovery

- Canonical human-readable model page: https://tokenstar.world/console/models. Use it to confirm model IDs, input modalities, context windows, pricing, and release status.
- If current TokenStar docs confirm that the OpenAI-compatible model list endpoint is enabled, fetch it with:

```bash
curl -sS "https://api.tokenstar.world/v1/models" \
  -H "Authorization: Bearer ${TOKENSTAR_API_KEY}" \
  -H "Accept: application/json"
```

- Treat `GET /v1/models` as a live-check helper only when the current docs confirm it; otherwise use the Model Plaza URL above and do not invent endpoint support.
- Before executing, prefer a live model check over hardcoded model memory. If a model is absent, renamed, preview-only, or hidden, stop and ask the user to pick an available model.

## Model Capability Quick Table

| Model | Family | Input | Image input | Long video | Context window | Max output tokens | Max resolution |
| --- | --- | --- | --- | --- | ---: | ---: | --- |
| kimi-k2.5 | Kimi | text+image | yes | no / not a video model | 262144 | 32768 | n/a |
| qwen3.7-plus | Qwen | text+image | yes | no / not a video model | 200000 | 32768 | n/a |
| qwen3.5-flash | Qwen | text+image | yes | no / not a video model | 200000 | 32768 | n/a |
| qwen3-coder-plus | Qwen | text | no | no / not a video model | 200000 | 32768 | n/a |
| MiniMax-M2.5 | MiniMax | text | no | no / not a video model | 196608 | 32768 | n/a |
| glm-5 | GLM | text | no | no / not a video model | 202752 | 32768 | n/a |
| gemini-3.1-pro-preview | Gemini | text+image | yes | no / not a video model | 200000 | 32768 | n/a |
| gemini-3.1-flash-lite-preview | Gemini | text+image | yes | no / not a video model | 200000 | 32768 | n/a |
| gpt-5.4 | GPT | text+image | yes | no / not a video model | 200000 | 32768 | n/a |
| gpt-5.4-mini | GPT | text+image | yes | no / not a video model | 200000 | 32768 | n/a |
| claude-sonnet-4-6-thinking | Claude | text+image | yes | no / not a video model | 200000 | 32768 | n/a |
| claude-opus-4-6-thinking | Claude | text+image | yes | no / not a video model | 200000 | 32768 | n/a |
| gpt-image-2 | Image | text+image | yes for edits | no | n/a | n/a | 1024x1024, 2048x2048 common sizes |
| gemini-3-pro-image-preview | Gemini-compatible image | text+image | yes | no | live-check docs/models | live-check docs/models | imageSize 2K example |
| gemini-3.1-flash-image-preview | Gemini-compatible image | text+image | yes | no | live-check docs/models | live-check docs/models | imageSize 2K example |
| gemini-2.5-flash-image | Gemini-compatible image | text+image | yes | no | live-check docs/models | live-check docs/models | live-check docs/models |
| seedance-2.0 / seedance-2.0-fast | Seedance video | text plus optional media assets | via asset reference | not documented here; live-check docs/support | n/a | n/a | example uses 720p, duration 5 or 8s |
| seedance-2.0-asset / seedance-2.0-asset-fast | Seedance asset video | text+asset://<Id> | via asset://<Id> | not documented here; live-check docs/support | n/a | n/a | example uses 720p, duration 5s |
| kling-v2-6 / kling-v3 | Kling video | text, image URL, or motion reference video | yes for image-to-video and motion-control | not documented here; live-check docs/support | n/a | n/a | current paths: /v1/videos/text2video, image2video, motion-control |
| kling-v3-omni | Kling Omni video edit | video URL plus optional element_list | yes | not documented here; live-check docs/support | n/a | n/a | current path: /v1/videos/omni-video |

- The table is for quick routing. For exact pricing, availability, maximum resolution, accepted aspect ratios, durations, and long-video support, live-check the docs/model page before creating jobs.

## Rate Limits and 429 Handling

- This Skill intentionally does not hardcode account concurrency, video job concurrency, or requests-per-second numbers unless TokenStar publishes them in current docs or account settings.
- On HTTP 429 with `daily_quota_exceeded` or `rate_limit_exceeded`, read `Retry-After` if present and wait at least that long before retrying.
- Without `Retry-After`, use exponential backoff with jitter, for example 1s, 2s, 4s, 8s, then cap and slow down the queue.
- Queue video jobs instead of firing many async creates at once. Start conservatively, reduce concurrency after any 429, and increase only after sustained success.
- Poll async video tasks every 5-10 seconds instead of tight-loop polling. Share one poller per task ID and stop polling at terminal states.
- Make create calls idempotent at the application layer: store the local request key, TokenStar task ID, `GroupId`, asset ID, or `ElementId` before retrying so a retry does not duplicate expensive work.
- For sustained production traffic, ask TokenStar support or account settings for the current per-account QPS, concurrent video job limit, and quota reset policy.

## Text APIs

### Chat Completions

- Status: verified. Live-check docs/models before execution.
- Request: POST /v1/chat/completions; protocol: OpenAI Chat Completions; mode: Sync.
- Purpose: Call the OpenAI-compatible chat API with a platform API key.
- Auth: Authorization: Bearer <API_KEY>; Content-Type: application/json.
- Key parameters: model required: Built-in model ID; messages required: OpenAI-compatible message array; stream optional: Whether to return an SSE-style stream; max_tokens / temperature / top_p optional: Compatible parameters passed through to the upstream model.
- Response shape: Response example; inspect `choices[]`, `message.content`, and `usage` for Chat Completions responses.
- Notes: Use this API for clients that support OpenAI Chat Completions. Only verified built-in models should be used in runnable examples.

Minimal Chat Completions:

```bash
curl -sS "https://api.tokenstar.world/v1/chat/completions" \
  -H "Authorization: Bearer ${TOKENSTAR_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.7-plus",
    "messages": [
      {"role": "user", "content": "Reply only OK"}
    ]
  }'
```

### Responses API

- Status: verified. Live-check docs/models before execution.
- Request: POST /v1/responses; protocol: OpenAI Responses; mode: Sync.
- Purpose: Call the OpenAI Responses-compatible API, suitable for Codex custom providers.
- Auth: Authorization: Bearer <API_KEY>; Content-Type: application/json.
- Key parameters: model required: Built-in model ID; input required: Text input or Responses-compatible input array; stream optional: Whether to stream the response.
- Notes: OpenAI-compatible clients should use a Base URL ending in /v1. Codex custom providers can use wire_api = "responses".

Minimal Responses API:

```bash
curl -sS "https://api.tokenstar.world/v1/responses" \
  -H "Authorization: Bearer ${TOKENSTAR_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.4",
    "input": "Reply only OK"
  }'
```

### Claude Messages

- Status: preview. Do not present as generally available unless TokenStar confirms access.
- Request: POST /v1/messages; protocol: Anthropic Messages; mode: Sync.
- Purpose: Call Claude models through the Anthropic Messages protocol.
- Auth: x-api-key: <API_KEY>; anthropic-version: 2023-06-01.
- Key parameters: model required: Claude-compatible model ID; messages required: Anthropic-compatible messages; max_tokens required: Maximum output tokens.
- Notes: The Claude Code Base URL uses the gateway root and must not include /v1. This module remains preview unless the backend contract is verified.
- Runnable example intentionally omitted until this API shape is verified for general access.

## Codex Provider

Write the provider in `~/.codex/config.toml` or the user-selected Codex config file:

```toml
model = "gpt-5.4"
model_provider = "tokenstar"

[model_providers.tokenstar]
name = "TokenStar Gateway"
base_url = "https://api.tokenstar.world/v1"
wire_api = "responses"
env_key = "TOKENSTAR_API_KEY"
```

Then start Codex with:

```bash
export TOKENSTAR_API_KEY="<your-tokenstar-api-key>"
codex
```

If the installed Codex version does not support a custom `env_key`, use `OPENAI_API_KEY` only inside an isolated shell or subshell:

```bash
(
  export TOKENSTAR_API_KEY="<your-tokenstar-api-key>"
  export OPENAI_API_KEY="$TOKENSTAR_API_KEY"
  codex
)
```

## Claude Code

Use the TokenStar Gateway root for `ANTHROPIC_BASE_URL`:

```bash
export ANTHROPIC_API_KEY="${TOKENSTAR_API_KEY}"
export ANTHROPIC_BASE_URL="https://api.tokenstar.world"
export CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1
export ANTHROPIC_MODEL="claude-sonnet-4-6-thinking"
claude
```

If Claude Code fails with beta-flag or Bedrock-style validation errors, keep `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` and check the FAQ.

## OpenClaw

- Use OpenAI-compatible providers with `baseUrl` set to the OpenAI Base URL ending in `/v1`.
- Store keys in environment variables such as `TOKENSTAR_API_KEY`; do not inline real keys in shared config.
- For Anthropic-compatible providers, use the gateway root as the Base URL.

## Remote Media URL Safety

- When an API field says the URL must be downloadable by the upstream service, use a public HTTPS URL that does not require cookies, browser login, VPN, private headers, or temporary local network access.
- Do not send `localhost`, `127.0.0.1`, `0.0.0.0`, private IP ranges, link-local addresses, cloud metadata addresses such as `169.254.169.254`, or unauthorized private resources.
- Do not use URLs that redirect to private networks or metadata services. TokenStar should reject private IPs and redirects to private networks; treat any bypass as a security issue.
- Prefer uploading local files through the documented multipart asset/image endpoints instead of exposing private URLs.

## Image Generation APIs

Image APIs usually return synchronously. Read image data from the response field for each model family.

### gpt-image

- Status: verified. Live-check docs/models before execution.
- Path/action: POST /v1/images/generations · POST /v1/images/edits.
- Result location: data[].b64_json.
- Rules: Applicable model: gpt-image-2. Image generation uses JSON requests. Image edits and masked inpainting use multipart/form-data to upload image and optionally mask. Common sizes include 1024x1024 and 2048x2048. Pass output formats within the model-supported range.

Minimal Image generation:

```bash
curl -sS -X POST "https://api.tokenstar.world/v1/images/generations" \
  -H "Authorization: Bearer ${TOKENSTAR_API_KEY}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "model": "gpt-image-2",
    "prompt": "A small clean five-point star icon, centered on a white background.",
    "n": 1,
    "size": "2048x2048",
    "quality": "low",
    "output_format": "png"
  }' > response.json
```

- To save a `b64_json` image response, first save the JSON body as `response.json`, then decode it:

```bash
jq -r '.data[0].b64_json' response.json | base64 --decode > output.png
# macOS:
jq -r '.data[0].b64_json' response.json | base64 -D > output.png
```

### Gemini-compatible image models

- Status: verified. Live-check docs/models before execution.
- Path/action: POST /v1beta/models/{model}:generateContent.
- Result location: candidates[].content.parts[].inlineData.
- Rules: Applicable models: gemini-3-pro-image-preview, gemini-3.1-flash-image-preview, and gemini-2.5-flash-image. parts may contain both text and images. Iterate through parts to find inlineData.

Minimal Gemini-compatible image request example:

```bash
curl -sS -X POST "https://api.tokenstar.world/v1beta/models/gemini-3.1-flash-image-preview:generateContent" \
  -H "Authorization: Bearer ${TOKENSTAR_API_KEY}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "contents": [{
      "role": "user",
      "parts": [{"text": "Create a clean 2K square image of a red five-point star centered on a white background."}]
    }],
    "generationConfig": {
      "responseModalities": ["TEXT", "IMAGE"],
      "imageConfig": {"aspectRatio": "1:1", "imageSize": "2K"}
    }
  }'
```

## Seedance video generation

After creating a Seedance task, poll by task ID until it reaches a terminal state, or pass callback_url for status callbacks.

### No-reference-person video generation

- Status: verified. Live-check docs/models before execution.
- Path/action: POST /v1/video/generations · GET /v1/video/generations/{task_id}.
- Result location: result_url.
- Rules: The no-reference-person entry uses seedance-2.0 or seedance-2.0-fast. After task creation, store the returned id or task_id and poll the query API for results.

Minimal Create a no-reference-person task:

```bash
curl -sS -X POST "https://api.tokenstar.world/v1/video/generations" \
  -H "Authorization: Bearer ${TOKENSTAR_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "seedance-2.0-fast",
    "content": [
      {"type": "text", "text": "A cat plays piano in a sunny room with cinematic lighting"}
    ],
    "generate_audio": true,
    "ratio": "16:9",
    "duration": 8
  }'
```

### Asset groups, asset upload, and reference-person video generation

- Status: verified. Live-check docs/models before execution.
- Path/action: POST /volc/asset/CreateAssetGroup · POST /volc/asset/ListAssetGroups · POST /volc/asset/CreateAsset · POST /volc/asset/ListAssets · POST /v1/video/generations.
- Result location: asset://<Id> · result_url.
- Rules: The reference-person entry uses seedance-2.0-asset or seedance-2.0-asset-fast. Assets support images, videos, and audio. The URL field accepts normal URLs, Data URIs, or raw Base64. You can also upload local files directly with multipart/form-data. Asset group and asset query APIs can confirm GroupId, asset IDs, and asset status. Video generation requests reference assets in content with asset://<Id>. When generating video from assets, content must strictly follow the order text, image_url, video_url, audio_url. Do not reorder them, or the request may fail.

Minimal Create asset group:

```bash
curl -sS -X POST "https://api.tokenstar.world/volc/asset/CreateAssetGroup" \
  -H "Authorization: Bearer ${TOKENSTAR_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "volc-asset",
    "Name": "asset-group-test1"
  }'
```

## Kling video generation

The current Kling video API uses separate paths for text-to-video, image-to-video, Omni video edit, and motion control.

### Text-to-video

- Status: verified. Live-check docs/models before execution.
- Path/action: POST /v1/videos/text2video · GET /v1/videos/text2video/{task_id}.
- Result location: data.task_result.videos[].url.
- Rules: Applicable models: kling-v2-6 and kling-v3. Create calls return data.task_id. Query tasks with GET /v1/videos/text2video/{task_id}. Use model_name, prompt, duration, mode, aspect_ratio, and sound. Current smoke checks use mode=std. For subject consistency, avoid text-to-video and use element_list with image2video, omni-video, or motion-control.

Minimal Kling text-to-video:

```bash
curl -sS --location "https://api.tokenstar.world/v1/videos/text2video" \
  -H "Authorization: Bearer ${TOKENSTAR_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @- <<'JSON'
{
  "model_name": "kling-v3",
  "prompt": "A rabbit runs naturally across grass with a steady camera and clear image quality.",
  "duration": "5",
  "mode": "std",
  "aspect_ratio": "16:9",
  "sound": "off"
}
JSON
```

### Image-to-video and subject consistency

- Status: verified. Live-check docs/models before execution.
- Path/action: POST /v1/videos/image2video · GET /v1/videos/image2video/{task_id}.
- Result location: data.task_result.videos[].url.
- Rules: Applicable models: kling-v2-6 and kling-v3. Use the top-level image field, not image_url and not legacy Image.Url. image2video does not support aspect_ratio. Sending it returns UnknownParameter. For subject consistency, pass element_list and use the ElementId returned by CreateAigcElement as element_id. Before using element_list, call DescribeAigcElement and confirm Status=succeed. Submitting while the subject is pending may cause Element id not found.

Minimal Basic image-to-video:

```bash
curl -sS --location "https://api.tokenstar.world/v1/videos/image2video" \
  -H "Authorization: Bearer ${TOKENSTAR_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @- <<'JSON'
{
  "model_name": "kling-v3",
  "image": "https://example.com/input.jpg",
  "prompt": "Animate the image subject with subtle natural motion, a steady push-in, and clear image quality.",
  "duration": "5",
  "mode": "std",
  "sound": "off"
}
JSON
```

### Omni video edit

- Status: verified. Live-check docs/models before execution.
- Path/action: POST /v1/videos/omni-video · GET /v1/videos/omni-video/{task_id}.
- Result location: data.task_result.videos[].url.
- Rules: Applicable model: kling-v3-omni. Video edit uses video_list, and video_list[].video_url must be downloadable. For subject consistency, pass element_list with element_id. Current smoke checks cover kling-v3-omni + std + element_list.

Minimal Omni video edit:

```bash
curl -sS --location "https://api.tokenstar.world/v1/videos/omni-video" \
  -H "Authorization: Bearer ${TOKENSTAR_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @- <<'JSON'
{
  "model_name": "kling-v3-omni",
  "prompt": "Let the video subject move naturally with a smooth camera push-in.",
  "mode": "std",
  "duration": "5",
  "aspect_ratio": "16:9",
  "sound": "off",
  "video_list": [
    {
      "video_url": "https://example.com/input.mp4",
      "refer_type": "base",
      "keep_original_sound": "no"
    }
  ]
}
JSON
```

### Motion control

- Status: verified. Live-check docs/models before execution.
- Path/action: POST /v1/videos/motion-control · GET /v1/videos/motion-control/{task_id}.
- Result location: data.task_result.videos[].url.
- Rules: Basic motion control supports kling-v2-6 and kling-v3. Subject-consistency motion control supports kling-v3. Pass both image_url and video_url. video_url is the motion reference video, and image_url is the subject image. prompt and character_orientation are required. Use character_orientation=video for kling-v3 + element_list. Do not pass duration or StaticMask; they may return UnknownParameter or fail the task. kling-v2-6 + element_list is not supported and returns subject reference is not supported for model 'kling-v2-6'.

Minimal Motion control:

```bash
curl -sS --location "https://api.tokenstar.world/v1/videos/motion-control" \
  -H "Authorization: Bearer ${TOKENSTAR_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @- <<'JSON'
{
  "model_name": "kling-v3",
  "image_url": "https://example.com/input.jpg",
  "video_url": "https://example.com/motion.mp4",
  "prompt": "Animate the image subject according to the motion reference video while keeping the background stable.",
  "mode": "std",
  "keep_original_sound": "yes",
  "character_orientation": "image"
}
JSON
```

### Subject elements

- Status: verified. Live-check docs/models before execution.
- Path/action: POST /aigc/element.
- Result location: Response.ElementId.
- Rules: Use X-TC-Action to distinguish CreateAigcElement, DescribeAigcElement, and DeleteAigcElement. After creation, store ElementId and poll DescribeAigcElement until Status=succeed before using it as element_list[].element_id in the current API. Use a short Name. Overly long values return Name length is invalid. Subject reference image URLs must be downloadable by the upstream service, otherwise ImageDownloadError is returned.

Minimal Create subject element:

```bash
curl -sS --location "https://api.tokenstar.world/aigc/element" \
  -H "Authorization: Bearer ${TOKENSTAR_API_KEY}" \
  -H "Content-Type: application/json" \
  -H "X-TC-Action: CreateAigcElement" \
  --data @- <<'JSON'
{
  "Name": "demo_subject",
  "Description": "Demo subject",
  "ReferenceType": "image_refer",
  "ElementImageList": {
    "FrontalImage": "https://example.com/front.png",
    "ReferImages": [
      {
        "ImageUrl": "https://example.com/ref1.png"
      }
    ]
  },
  "Provider": ["kling"],
  "TagList": [
    {
      "TagId": "o_105"
    }
  ]
}
JSON
```

### Legacy Kling API entry

- Status: verified. Live-check docs/models before execution.
- Path/action: GET /doc/kling-legacy.
- Result location: Legacy /v1/video/generations and X-TC-Action docs.
- Rules: The legacy page is only for existing integrations, migration, and historical troubleshooting. New integrations should use the current /v1/videos/{endpoint} API in this module.

## Task status, polling, and callbacks

Video jobs are asynchronous. Pass callback_url for status changes or poll the query API.

### Async task lifecycle

- Status: verified. Live-check docs/models before execution.
- Path/action: submitted / queued / NOT_START → running / IN_PROGRESS → succeeded / SUCCESS / DONE / failed / FAILURE / FAIL.
- Result location: Seedance: result_url; current Kling API: data.task_result.videos[].url.
- Rules: Poll every 5 to 10 seconds; for the current Kling API, poll every 10 to 20 seconds. Stop after a terminal state. Use callback_url only when that video API explicitly supports it. The current Kling API does not publicly provide or recommend relying on callback_url, watermark_info, or external_task_id. Customer callbacks should return HTTP 2xx and be idempotent by task ID.

## Cache and Reuse IDs

- Cache reusable media IDs in your app database, not in this Skill file. Store source hash/URL, model/provider, created time, status, and owner/workspace scope.
- Before creating a Seedance asset group, call `ListAssetGroups` by name or metadata and reuse an existing `GroupId` when it still belongs to the same user/workspace.
- Before uploading an identical media asset, call `ListAssets` for the target `GroupId` and reuse the asset ID in `asset://<Id>` references when the asset is still valid.
- After `CreateAsset`, save the returned asset ID and use `asset://<Id>` in video `content` instead of uploading the same image, video, or audio again.
- After `CreateAigcElement`, save `ElementId`, then call `DescribeAigcElement` until `Status=succeed` before using it as `element_list[].element_id` in current Kling video APIs.
- Reuse `ElementId` for the same subject/person across Kling image-to-video, Omni, or motion-control jobs when the provider, owner, and subject definition match.
- Invalidate cached `GroupId`, asset IDs, or `ElementId` after delete calls, failed/expired status, permission changes, source asset changes, or TokenStar support guidance.

## Callback Security

- Use HTTPS callback URLs in production.
- If TokenStar provides a documented callback signature or shared-secret mechanism, verify it before trusting callback payloads.
- If no documented callback verification mechanism is configured, treat callbacks as notifications and query the task status endpoint before updating production state.
- Do not trust an unverified callback task status. Treat callbacks as notifications, then reconcile by task ID.
- Make handlers idempotent and return HTTP 2xx only after the callback was accepted for processing.

## Troubleshooting Decision Tree

- First record HTTP status, TokenStar `error.code`, `message`, `param`, and requestId if available.
- Error response shape: `{"error":{"code":"invalid_request","message":"model is required","param":"model"}}`.
- 400 invalid_request / invalid_json: Invalid request parameters or malformed JSON.
- 401 unauthorized / invalid_virtual_key: API key is missing, invalid, or expired.
- 402 subscription_inactive / subscription_expired: Subscription is inactive or expired.
- 402 quota_not_configured: No usable token quota is configured.
- 403 permission_denied: No permission to access the model or API.
- 404 not_found: Task or resource not found.
- 429 daily_quota_exceeded / rate_limit_exceeded: Quota, request rate, or concurrency limit exceeded.
- 502 upstream_unavailable / service_unavailable: Upstream model service is unavailable.
- 504 service_timeout: Service processing timed out.
- Safe environment check: never run `env | grep ...` for API keys because it prints full secret values. Use SET/EMPTY output instead:
- Expected output should look like `TOKENSTAR_API_KEY=SET` or `TOKENSTAR_API_KEY=EMPTY`, never the secret value.
- API keys are shown only as SET/EMPTY. Base URL variables are non-secret and may be printed to diagnose wrong hosts or accidental `/v1` suffixes.

```bash
for name in TOKENSTAR_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN; do
  value="${!name:-}"
  if [ -n "$value" ]; then
    printf "%s=SET\n" "$name"
  else
    printf "%s=EMPTY\n" "$name"
  fi
done

for name in OPENAI_BASE_URL ANTHROPIC_BASE_URL; do
  printf "%s=%s\n" "$name" "${!name:-EMPTY}"
done
```

- Claude Code: do not set `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` at the same time.
- If Claude Code or Bedrock-style clients fail with `invalid beta flag`, set `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`.
- If current Kling image-to-video returns `UnknownParameter` for `AspectRatio`, remove `aspect_ratio`; image2video only uses `image`, `prompt`, `duration`, `mode`, `sound`, and optional `element_list`.
- If current Kling motion-control fails with missing-field errors, pass both `image_url` and `video_url`, plus `prompt` and `character_orientation`; do not send `duration` or `StaticMask`.
- If Kling subject consistency fails with `Element id not found`, call `DescribeAigcElement` and wait for `Status=succeed` before using `element_list[].element_id`.
- If image or video URL ingestion fails with `ImageDownloadError`, provide a public HTTPS URL that the upstream service can download without private-network redirects.
- For video tasks, poll every 5-10 seconds and stop at terminal states such as succeeded/SUCCESS/DONE or failed/FAILURE/FAIL.

## Where to Look Next

- Latest full API docs: https://tokenstar.world/console/doc
- Troubleshooting and FAQ: https://tokenstar.world/console/faq
- Model list and capabilities: https://tokenstar.world/console/models
