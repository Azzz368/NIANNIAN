"""
念念 LLM 客户端 — 接入 302.ai 统一网关 + 可灵官方 API
任务与模型映射：
  文本结构化分析（家属访谈 / MV01-06）: claude-sonnet-4-6  →（失败自动回退）→ gpt-5.4
  图像内容理解（describe_image）       : gemini-2.0-pro-image-preview
  图像生成（generate_image_302）        : gemini-2.0-pro-image-preview
    视频生成（generate_video_kling）      : TokenStar Kling 图生视频（首帧模式）
  语音转写（transcribe_audio）          : whisper-1
配置项（填写 .env 文件）：
  AI302_API_KEY          = sk-xxxxxxxxxxxx       ← 必填，图文/视频 302.ai 备用均使用
  AI302_TEXT_MODEL       = gemini-2.5-flash
  AI302_TEXT_FALLBACK    = claude-sonnet-4-6
  AI302_VISION_MODEL     = gemini-2.0-pro-image-preview
  AI302_IMAGE_GEN_MODEL  = gemini-2.0-pro-image-preview
  AI302_AUDIO_MODEL      = whisper-1
    TOKENSTAR_API_KEY      = TokenStar API 密钥（影视制作台图片与视频共用）
    TOKENSTAR_KLING_MODEL  = kling-v3（可选）
  LOCAL_LLM_BASE_URL     =  （本地备用，可留空）
  LOCAL_LLM_MODEL        =
"""
import base64
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests as _requests
from dotenv import load_dotenv
from openai import OpenAI

# 始终加载项目根目录的 .env（无论从哪个子目录启动 uvicorn）
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ── 302.ai 网关 ───────────────────────────────────────────────────────────────
_302_BASE_URL = "https://api.302.ai/v1"
_302_API_KEY  = os.getenv("AI302_API_KEY", "sk-填写您的302.ai密钥")

# ── 各任务专属模型 ─────────────────────────────────────────────────────────────
# 文本分析：主力 Gemini Flash，自动回退到 Claude Sonnet
TEXT_MODEL          = os.getenv("AI302_TEXT_MODEL",      "gemini-2.5-flash")
TEXT_FALLBACK_MODEL = os.getenv("AI302_TEXT_FALLBACK",   "claude-sonnet-4-6")

# 分镜制作（MV04）专属：gemini-2.5-flash（gpt-4o/gpt-5.4 已被禁用）
STORYBOARD_MODEL    = os.getenv("AI302_STORYBOARD_MODEL", "gemini-2.5-flash")

# 数字人对话 & 人设融合（速度优先）
DIALOGUE_MODEL      = os.getenv("AI302_DIALOGUE_MODEL",  "doubao-Seed-2-0-lite")

# 图像 / 视频 / 音频（固定模型，不回退）
VISION_MODEL        = os.getenv("AI302_VISION_MODEL",       "gemini-2.5-flash")
IMAGE_GEN_MODEL     = os.getenv("AI302_IMAGE_GEN_MODEL",    "google/nano-banana/text-to-image")
IMAGE_GEN_FALLBACK  = os.getenv("AI302_IMAGE_GEN_FALLBACK", "gpt-4o-image-generation")
IMAGE_REF_MODEL     = os.getenv("AI302_IMAGE_REF_MODEL",    "gemini-3-pro-image-preview")
VIDEO_GEN_MODEL     = os.getenv("AI302_VIDEO_GEN_MODEL",    "kling-v1-5-pro")
AUDIO_MODEL         = os.getenv("AI302_AUDIO_MODEL",        "whisper-1")

# ── TokenStar 图片生成（影视制作台首帧图专用）────────────────────────────────
# 图片请求不复用 302.ai 网关：纯文生图走 /images/generations，
# 有人物参考图时走 /images/edits，以便将参考照片作为编辑输入。
TOKENSTAR_BASE_URL     = os.getenv("TOKENSTAR_BASE_URL", "https://api.tokenstar.world").rstrip("/")
TOKENSTAR_API_KEY      = os.getenv("TOKENSTAR_API_KEY", "")
TOKENSTAR_IMAGE_MODEL  = os.getenv("TOKENSTAR_IMAGE_MODEL", "gpt-image-2")
# 影视制作台优先直接请求原生 16:9 画布；后处理仍会校验输出比例，
# 以兼容网关回退为其他尺寸的情况。
TOKENSTAR_IMAGE_SOURCE_SIZE = os.getenv("TOKENSTAR_IMAGE_SOURCE_SIZE", "2048x1152")

# ── 图床（首帧图上传，用于 Kling 图生视频）──────────────────────────────────────
IMGBB_API_KEY       = os.getenv("IMGBB_API_KEY", "")

# ── 本地 LLM 备用（可选） ──────────────────────────────────────────────────────
_LOCAL_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "")
_LOCAL_API_KEY  = os.getenv("LOCAL_LLM_API_KEY",  "lm-studio")
_LOCAL_MODEL    = os.getenv("LOCAL_LLM_MODEL",    "")


def _build_client(base_url: Optional[str], api_key: Optional[str]) -> OpenAI:
    if base_url:
        return OpenAI(api_key=api_key or "none", base_url=base_url)
    return OpenAI(api_key=api_key or "none")


# 主客户端 — 302.ai（文本 + 图像 + 视频 + 音频 全走这里）
PRIMARY_CLIENT: OpenAI = _build_client(_302_BASE_URL, _302_API_KEY)

# 本地备用客户端（仅当环境变量配置时启用）
_LOCAL_CLIENT: Optional[OpenAI] = (
    _build_client(_LOCAL_BASE_URL, _LOCAL_API_KEY)
    if _LOCAL_BASE_URL and _LOCAL_MODEL
    else None
)

# 兼容旧调用
PRIMARY_MODEL = TEXT_MODEL
FALLBACK_MODELS: list = []


def _text_model_queue() -> List[Tuple[str, OpenAI]]:
    """
    文本推理优先级队列：
      1. gemini-2.5-flash  （主力）
      2. gemini-2.5-flash  （自动回退，保持同一模型重试）
      3. 本地 LLM               （可选）
    """
    q: List[Tuple[str, OpenAI]] = [
        (TEXT_MODEL, PRIMARY_CLIENT),
        (TEXT_FALLBACK_MODEL, PRIMARY_CLIENT),
    ]
    if _LOCAL_CLIENT and _LOCAL_MODEL:
        q.append((_LOCAL_MODEL, _LOCAL_CLIENT))
    return q


def _storyboard_model_queue() -> List[Tuple[str, OpenAI]]:
    """
    分镜制作（MV04）专属优先级队列：
      1. gemini-2.5-flash  （主力）
      2. gemini-2.5-flash  （备用重试）
    """
    return [
        (STORYBOARD_MODEL,    PRIMARY_CLIENT),
        (TEXT_FALLBACK_MODEL, PRIMARY_CLIENT),
    ]


# ── 旧接口兼容层 ───────────────────────────────────────────────────────────────
def _iter_model_clients():
    return _text_model_queue()


# ── 模型兼容工具 ──────────────────────────────────────────────────────────────
_JSON_MODE_UNSUPPORTED = ("claude", "gemini")


def _supports_json_mode(model_name: str) -> bool:
    """Claude / Gemini 不支持 response_format=json_object，需手动提取 JSON。"""
    lower = model_name.lower()
    return not any(lower.startswith(prefix) for prefix in _JSON_MODE_UNSUPPORTED)


def _extract_json(text: str) -> str:
    """
    从模型回复中提取 JSON 块。
    优先尝试 ```json ... ``` 代码块，其次查找首个 { 到末尾的内容。
    """
    import re
    # 匹配 ```json ... ``` 或 ``` ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.S)
    if m:
        return m.group(1)
    # 取第一个 { 到最后一个 }
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1 and end >= start:
        return text[start:end + 1]
    return text.strip()


def _json_system_hint(system_prompt: str) -> str:
    """对不支持 JSON mode 的模型，在 system prompt 末尾追加 JSON 输出要求。"""
    return (
        system_prompt.rstrip()
        + "\n\n【重要】你的回复必须是且仅是一个合法的 JSON 对象，"
        "不要包含任何 Markdown 标记、解释文字或代码块以外的内容。"
        "直接输出 JSON，不加任何前缀。"
    )


def call_skill(
    skill_name: str,
    system_prompt: str,
    user_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """调用 LLM（JSON 模式），用于 MV 技能 pipeline。
    MV04 分镜制作专用 gpt-4o，其余使用 claude-sonnet-4-6。"""
    # MV04 分镜制作强制使用 storyboard 专属队列（gpt-4o）
    model_queue = _storyboard_model_queue() if skill_name == "MV04" else _iter_model_clients()
    last_error: Optional[str] = None
    for model_name, client in model_queue:
        use_json_mode = _supports_json_mode(model_name)
        sys_content   = system_prompt if use_json_mode else _json_system_hint(system_prompt)
        for attempt in range(1, 4):
            try:
                kwargs: Dict[str, Any] = dict(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": sys_content},
                        {"role": "user",   "content": json.dumps(user_payload, ensure_ascii=False)},
                    ],
                    temperature=0.4,
                )
                if use_json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                response = client.chat.completions.create(**kwargs)
                raw = response.choices[0].message.content or "{}"
                if not use_json_mode:
                    raw = _extract_json(raw)
                return json.loads(raw)
            except Exception as exc:
                last_error = f"{model_name}: {exc}"
                if attempt < 3:
                    time.sleep(2)
    return {"error": True, "skill": skill_name, "message": last_error or "Unknown error"}


def call_memorial_chat(
    system_prompt: str,
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
) -> str:
    """
    念念 AI 对话接口：支持多轮对话历史。
    messages: [{"role": "user"|"assistant", "content": "..."}]
    model: 指定模型时直接使用，不走默认队列（如 "doubao-Seed-2-0-lite"）
    返回纯文本回复。
    """
    last_error: Optional[str] = None
    all_msgs = [{"role": "system", "content": system_prompt}] + messages

    # 指定模型时直接调用，不走队列
    if model:
        for attempt in range(1, 4):
            try:
                response = PRIMARY_CLIENT.chat.completions.create(
                    model=model,
                    messages=all_msgs,
                    temperature=0.65,
                    max_tokens=6000,
                )
                return response.choices[0].message.content or ""
            except Exception as exc:
                last_error = f"{model}: {exc}"
                if attempt < 3:
                    time.sleep(1)
        return f"（念念暂时无法回应，请稍后再试。错误：{last_error or '未知'}）"

    for model_name, client in _iter_model_clients():
        for attempt in range(1, 4):
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=all_msgs,
                    temperature=0.65,
                    max_tokens=6000,
                )
                return response.choices[0].message.content or ""
            except Exception as exc:
                last_error = f"{model_name}: {exc}"
                if attempt < 3:
                    time.sleep(2)
    return f"（念念暂时无法回应，请稍后再试。错误：{last_error or '未知'}）"


def call_freeform(system_prompt: str, user_content: str) -> str:
    """自由文本生成。使用 claude-sonnet-4-6。"""
    last_error: Optional[str] = None
    for model_name, client in _iter_model_clients():
        for attempt in range(1, 4):
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_content},
                    ],
                    temperature=0.4,
                )
                return response.choices[0].message.content or ""
            except Exception as exc:
                last_error = f"{model_name}: {exc}"
                if attempt < 3:
                    time.sleep(2)
    return f"[ERROR] {last_error or 'Unknown error'}"


def call_structured(system_prompt: str, user_content: str) -> Dict[str, Any]:
    """结构化 JSON 生成。使用 claude-sonnet-4-6。"""
    last_error: Optional[str] = None
    for model_name, client in _iter_model_clients():
        use_json_mode = _supports_json_mode(model_name)
        sys_content   = system_prompt if use_json_mode else _json_system_hint(system_prompt)
        for attempt in range(1, 4):
            try:
                kwargs: Dict[str, Any] = dict(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": sys_content},
                        {"role": "user",   "content": user_content},
                    ],
                    temperature=0.2,
                )
                if use_json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                response = client.chat.completions.create(**kwargs)
                raw = response.choices[0].message.content or "{}"
                if not use_json_mode:
                    raw = _extract_json(raw)
                return json.loads(raw)
            except Exception as exc:
                last_error = f"{model_name}: {exc}"
                if attempt < 3:
                    time.sleep(2)
    return {"error": True, "message": last_error or "Unknown error"}


def describe_image(image_bytes: bytes, filename: str) -> str:
    """图像内容理解 — 使用 gemini-2.0-pro-image-preview（通过 302.ai）。"""
    last_error: Optional[str] = None
    encoded   = base64.b64encode(image_bytes).decode("utf-8")
    ext       = filename.rsplit(".", 1)[-1].lower()
    image_url = f"data:image/{ext};base64,{encoded}"
    system_prompt = (
        "你是图像理解助手，请输出简洁的中文描述，并尽量提取图片里的文字信息。"
        "如果有清晰文字，请在描述里包含。"
    )
    for attempt in range(1, 3):
        try:
            response = PRIMARY_CLIENT.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "请描述这张图片"},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    },
                ],
                temperature=0.2,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:  # pragma: no cover
            last_error = f"{VISION_MODEL}: {exc}"
            if attempt < 2:
                time.sleep(1)
    return f"[IMAGE_PARSE_ERROR] {last_error or 'Unknown error'}"


def transcribe_audio(audio_bytes: bytes, filename: str) -> str:
    """语音转写 — 使用 whisper-1（通过 302.ai）。"""
    last_error: Optional[str] = None
    for attempt in range(1, 3):
        try:
            response = PRIMARY_CLIENT.audio.transcriptions.create(
                model=AUDIO_MODEL,
                file=(filename, audio_bytes),
            )
            return getattr(response, "text", "") or ""
        except Exception as exc:  # pragma: no cover
            last_error = f"{AUDIO_MODEL}: {exc}"
            if attempt < 2:
                time.sleep(1)
    return f"[AUDIO_PARSE_ERROR] {last_error or 'Unknown error'}"


def build_scene_prompts(
    scene: Dict[str, Any],
    character_bible: Optional[Dict[str, Any]] = None,
    scene_library: Optional[List] = None,
    cast_roles: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    根据分镜 + 三要素 + 电影角色表，用 LLM 同时生成：
      - image_prompt : 英文首帧图片 Prompt，锁定角色 DNA 并嵌入角色参考图 URL
      - video_prompt : 中文可灵视频 Prompt
    cast_roles: [{"name":"...", "role_label":"...", "description":"...", "photo_url":"..."}]
      主角（逝者）始终从 ancestor_photo_url 传入，无需在 cast_roles 里重复。
    返回 {"image_prompt": "...", "video_prompt": "...", "_cast_ref": "...（供调用方记录）"}
    """
    # `scene` 是会被前端原地补写的运行时对象，可能已经包含
    # `_image_data_url`（完整图片 Base64）和 `_video_url` 等缓存字段。
    # 绝不能直接 json.dumps(scene) 发送给 Prompt 模型，否则一次图片缓存就会
    # 膨胀为数十万 token，并在后续“重新生成”时重复计费。
    prompt_scene_fields = (
        "scene_id", "id", "scene_ref", "time", "duration", "shot_type",
        "description", "scene_desc", "visual", "voice_script", "narration",
        "asset_type", "mj_prompt", "negative_prompt", "motion", "prompt_start",
        "prompt_video",
    )
    prompt_scene: Dict[str, Any] = {}
    for field in prompt_scene_fields:
        value = scene.get(field)
        if isinstance(value, str) and value.strip():
            # 分镜文字正常远小于该上限；上限用于阻断异常长字段再次造成巨额请求。
            prompt_scene[field] = value.strip()[:4000]
        elif isinstance(value, (int, float, bool)):
            prompt_scene[field] = value

    # ── 提取角色 DNA 描述 ──────────────────────────────────────────────────────
    dna_lines = []
    if character_bible:
        cd = character_bible.get("character_dna", {})
        if cd.get("facial_features"):
            dna_lines.append(f"面部：{cd['facial_features']}")
        if cd.get("body_features"):
            dna_lines.append(f"体型：{cd['body_features']}")
        if cd.get("clothing_style"):
            dna_lines.append(f"服装：{cd['clothing_style']}")
        if cd.get("mannerisms"):
            dna_lines.append(f"习惯动作：{cd['mannerisms']}")
    dna_text = "；".join(dna_lines) if dna_lines else "（未提供角色DNA）"

    # ── 从 scene_library 匹配场景说明 ─────────────────────────────────────────
    scene_id = scene.get("scene_id", "")
    scene_ref = scene.get("scene_ref") or scene_id
    scene_lib_desc = ""
    if scene_library:
        matched = next(
            (s for s in scene_library if isinstance(s, dict) and s.get("scene_id") == scene_ref),
            None,
        )
        if matched:
            scene_lib_desc = matched.get("visual_descriptor") or matched.get("description", "")

    # ── 构造电影角色表字符串 ──────────────────────────────────────────────────
    cast_lines = []
    if cast_roles:
        for cr in cast_roles:
            _name = cr.get("name", "").strip()
            _rl   = cr.get("role_label", "").strip()
            _desc = cr.get("description", "").strip()
            _url  = cr.get("photo_url", "")
            if not _name:
                continue
            parts = []
            if _rl:
                parts.append(_rl)
            if _desc:
                parts.append(_desc)
            if _url:
                parts.append(f"参考图：{_url}")
            cast_lines.append(f"  · {_name}（{'，'.join(parts) if parts else '配角'}）")
    cast_text = "\n".join(cast_lines) if cast_lines else "（无配角）"

    system_prompt = (
        "你是专业的追思影像 Prompt 工程师，擅长将中文分镜描述转化为高质量 AI 生成 Prompt。\n\n"
        "任务：根据提供的分镜信息、角色DNA和电影角色表，同时输出两条 Prompt：\n\n"
        "1. image_prompt（英文）：\n"
        "   - 必须将主角角色DNA翻译并嵌入，精准锁定外貌\n"
        "   - 若场景中有配角出现，在 prompt 中用格式 [角色名(称谓,参考图URL)] 标注每个配角\n"
        "   - 禁止出现与DNA不符的外貌描述（如：American, Western, blonde等）\n"
        "   - 包含场景光线、构图、情绪基调\n"
        "   - 风格后缀：photorealistic, cinematic still, 8K, warm golden hour lighting\n\n"
        "2. video_prompt（中文）：\n"
        "   - 镜头运动（推镜/拉镜/横移/固定等）\n"
        "   - 人物动作与表情细节（涉及多角色时逐一描述）\n"
        "   - 环境光线变化、情感基调、时长约5-6秒的画面感\n\n"
        "严格按以下 JSON 返回，不要包含任何其他文字：\n"
        '{"image_prompt": "...", "video_prompt": "..."}'
    )

    user_payload = {
        "scene": prompt_scene,
        "主角角色DNA（必须锚定）": dna_text,
        "场景环境描述（融入背景）": scene_lib_desc or "（未提供场景描述）",
        "电影配角表（如场景涉及多人，需在prompt中标注）": cast_text,
    }

    result = call_storyboard(system_prompt, json.dumps(user_payload, ensure_ascii=False))
    if result.get("error") or not result.get("image_prompt"):
        fallback_img = scene.get("mj_prompt") or scene.get("description") or ""
        fallback_vid = scene.get("description") or ""
        return {"image_prompt": fallback_img, "video_prompt": fallback_vid, "_fallback": True}
    result["_cast_ref"] = cast_text
    return result




def _generate_image_wavespeed(prompt: str, model: str) -> tuple:
    """
    调用 302.ai Wavespeed 专属端点生成图像（nano-banana 等）。
    使用同步模式 + base64 输出，无需轮询。
    返回 (b64_string, None) 或 (None, error_msg)。
    """
    import requests as _req
    endpoint = f"https://api.302.ai/ws/api/v3/{model}"
    headers  = {
        "Authorization": f"Bearer {_302_API_KEY}",
        "Content-Type":  "application/json",
    }
    body = {
        "prompt":               prompt,
        "aspect_ratio":         "16:9",
        "output_format":        "png",
        "enable_sync_mode":     True,
        "enable_base64_output": True,
    }
    try:
        r = _req.post(endpoint, headers=headers, json=body, timeout=120)
        r.raise_for_status()
        data = r.json().get("data", {})
        outputs = data.get("outputs", [])
        if outputs and isinstance(outputs[0], str) and len(outputs[0]) > 100:
            return outputs[0], None
        # 异步模式：轮询 result
        task_id = data.get("id")
        if task_id:
            poll_url = f"https://api.302.ai/ws/api/v3/predictions/{task_id}/result"
            for _ in range(30):
                import time as _t; _t.sleep(3)
                pr = _req.get(poll_url, headers=headers, timeout=30)
                pd = pr.json().get("data", {})
                if pd.get("status") == "completed":
                    outs = pd.get("outputs", [])
                    if outs:
                        return outs[0], None
                elif pd.get("status") == "failed":
                    return None, pd.get("error", "任务失败")
            return None, "轮询超时（90s）"
        return None, f"API 返回空数据：{r.text[:200]}"
    except Exception as exc:
        return None, str(exc)


def _crop_image_b64_to_16_9(image_b64: str) -> tuple:
    """将 TokenStar 图片居中裁剪为精确 16:9，返回 PNG Base64。"""
    from io import BytesIO

    try:
        from PIL import Image, ImageOps

        image = Image.open(BytesIO(base64.b64decode(image_b64)))
        image = ImageOps.exif_transpose(image).convert("RGB")
        width, height = image.size
        if width < 16 or height < 9:
            return None, f"生成图片尺寸异常：{width}x{height}"

        target_height = min(height, (width * 9) // 16)
        target_width = (target_height * 16) // 9
        if target_width > width:
            target_width = width
            target_height = (target_width * 9) // 16

        left = (width - target_width) // 2
        # 人像影视镜头通常将脸部放在上三分之一；相比居中裁剪，向上偏移可
        # 保留头顶和面部，避免方形源图转 16:9 时先把人物头部裁掉。
        top = int((height - target_height) * 0.20)
        cropped = image.crop((left, top, left + target_width, top + target_height))
        output = BytesIO()
        cropped.save(output, format="PNG", optimize=True)
        return base64.b64encode(output.getvalue()).decode(), None
    except Exception as exc:
        return None, f"生成图片 16:9 裁剪失败：{exc}"


def _tokenstar_image_b64(response: Any) -> tuple:
    """读取 TokenStar gpt-image 响应，并统一转换为精确 16:9 PNG。"""
    try:
        payload = response.json()
        image_b64 = payload.get("data", [{}])[0].get("b64_json", "")
        if isinstance(image_b64, str) and image_b64:
            return _crop_image_b64_to_16_9(image_b64)
        return None, "TokenStar 未返回 data[0].b64_json"
    except (ValueError, AttributeError, IndexError, TypeError) as exc:
        return None, f"TokenStar 图片响应解析失败：{exc}"


def generate_image_tokenstar(prompt: str, reference_b64: Optional[str] = None) -> tuple:
    """影视制作台图片生成：使用 TokenStar `gpt-image-2`，不调用 302.ai。"""
    import logging as _log_img

    logger = _log_img.getLogger("llm_client.tokenstar_image")
    if not TOKENSTAR_API_KEY:
        return None, "未配置 TOKENSTAR_API_KEY，无法调用 TokenStar 图片生成"

    composition_rules = (
        "构图为硬性要求：横向 16:9 电影中景或全景，主角完整头部、脸部、肩膀和关键动作"
        "必须全部位于画面内；头顶至少保留 10% 的安全留白。主角位于画面中央或中央偏左的"
        "安全区域，不能贴近任何边缘。禁止裁切头顶、脸部、手臂、手部或身体关键部位；"
        "禁止极端特写、局部特写、人物出框。不要出现文字、横幅、标志、水印。"
    )
    full_prompt = (
        "请严格遵循以下分镜描述，生成一幅电影感的追思纪念场景图片。"
        f"分镜描述：{prompt}。"
        "风格要求：16:9 横向电影构图，主体和关键动作保持在画面中央安全区域，"
        "电影质感、暖色调、photorealistic, cinematic still, 8K。"
        f"{composition_rules}"
    )
    headers = {"Authorization": f"Bearer {TOKENSTAR_API_KEY}"}

    try:
        if reference_b64:
            try:
                reference_bytes = base64.b64decode(reference_b64, validate=True)
            except Exception as exc:
                return None, f"参考图 base64 解码失败：{exc}"

            full_prompt = (
                "严格保留上传参考照片中人物的面部特征、年龄、肤色和外貌，"
                "将其作为画面主角。" + full_prompt
            )
            logger.info("[tokenstar_image] 调用 gpt-image-2 图像编辑接口")
            response = _requests.post(
                f"{TOKENSTAR_BASE_URL}/v1/images/edits",
                headers=headers,
                data={
                    "model": TOKENSTAR_IMAGE_MODEL,
                    "prompt": full_prompt,
                    "n": "1",
                    "size": TOKENSTAR_IMAGE_SOURCE_SIZE,
                    "output_format": "png",
                },
                files={"image": ("reference.png", reference_bytes, "image/png")},
                timeout=180,
            )
        else:
            logger.info("[tokenstar_image] 调用 gpt-image-2 文生图接口")
            response = _requests.post(
                f"{TOKENSTAR_BASE_URL}/v1/images/generations",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "model": TOKENSTAR_IMAGE_MODEL,
                    "prompt": full_prompt,
                    "n": 1,
                    "size": TOKENSTAR_IMAGE_SOURCE_SIZE,
                    "output_format": "png",
                },
                timeout=180,
            )
        response.raise_for_status()
    except _requests.RequestException as exc:
        response_text = getattr(getattr(exc, "response", None), "text", "")
        return None, f"TokenStar 图片生成请求失败：{str(exc)} {response_text[:500]}"

    return _tokenstar_image_b64(response)


def generate_image_302_ref(prompt: str, reference_b64: str) -> tuple:
    """兼容旧调用名；实际委托 TokenStar gpt-image-2 图像编辑接口。"""
    return generate_image_tokenstar(prompt, reference_b64=reference_b64)


def _parse_gemini_image_response(resp, log_tag: str = "") -> tuple:
    """
    解析 gemini-3-pro-image-preview 经由 302.ai 网关返回的图片。
    兼容多种格式：
      A. content 列表中 type=image_url，url 以 data: 开头（base64 data URL）
      B. content 列表中 type=image_url，url 以 http 开头（HTTPS，下载）
      C. content 为字符串，含 markdown 图片 ![...](url)（302.ai 常见格式）
      D. content 为字符串，含裸 HTTPS 图片 URL
      E. 302.ai 特殊格式：content="![image]()" 但图片 base64 藏在 message
         的额外字段（通过 model_dump() 深扫找 data:image 或 base64 字段）
    返回 (b64_string, None) 或 (None, error_str)。
    """
    import re as _re
    import json as _json
    import logging as _log_pg
    _log = _log_pg.getLogger("llm_client.gemini_parse")

    try:
        msg = resp.choices[0].message
        content = msg.content
    except Exception as e:
        return None, f"读取响应 content 失败：{e}"

    # ── 格式 A/B：content 是列表（标准 multipart）────────────────────────────
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                # pydantic 对象尝试转 dict
                try:
                    part = part.model_dump() if hasattr(part, "model_dump") else vars(part)
                except Exception:
                    continue
            ptype = part.get("type", "")
            if ptype == "image_url":
                url = part.get("image_url", {}).get("url", "")
                if url.startswith("data:"):
                    _log.info(f"{log_tag} 格式A：data URL")
                    return url.split(",", 1)[-1], None
                elif url.startswith("http"):
                    b64 = _download_url_to_b64(url, log_tag)
                    if b64:
                        return b64, None
            elif ptype == "image":
                # 部分网关把图片放在 part["image"]{"url"/"data"}
                img_field = part.get("image", {})
                if isinstance(img_field, dict):
                    url = img_field.get("url", "") or img_field.get("data", "")
                    if url.startswith("data:"):
                        return url.split(",", 1)[-1], None
                    elif url.startswith("http"):
                        b64 = _download_url_to_b64(url, log_tag)
                        if b64:
                            return b64, None

    # ── 格式 C/D：content 是字符串，从中提取图片 URL ─────────────────────────
    if isinstance(content, str):
        # 格式C：markdown 图片语法 ![...](url)，要求 URL 非空
        md_matches = _re.findall(r'!\[.*?\]\((https?://[^\s)]+)\)', content)
        for url in md_matches:
            _log.info(f"{log_tag} 格式C：markdown 图片链接 {url[:60]}")
            b64 = _download_url_to_b64(url, log_tag)
            if b64:
                return b64, None

        # 格式D：裸 HTTPS URL（302.ai CDN 域名）
        url_matches = _re.findall(r'https?://\S+\.(?:png|jpg|jpeg|webp|gif)(?:\?\S*)?', content, _re.IGNORECASE)
        # 也匹配 302.ai file CDN
        url_matches += _re.findall(r'https://file\.302\.ai/\S+', content)
        seen = set()
        for url in url_matches:
            url = url.rstrip('.')
            if url in seen:
                continue
            seen.add(url)
            _log.info(f"{log_tag} 格式D：裸 URL {url[:60]}")
            b64 = _download_url_to_b64(url, log_tag)
            if b64:
                return b64, None

    # ── 格式 E：深扫 model_dump() 找藏在其他字段的图片数据 ──────────────────
    # 适用于 ![image]() 空URL 但图片实际在 message 的非标准字段中
    try:
        raw_dict = resp.model_dump() if hasattr(resp, "model_dump") else {}
    except Exception:
        raw_dict = {}
    b64, err = _deep_scan_for_image(raw_dict, log_tag)
    if b64:
        return b64, None

    # 真的只有文字
    _log.warning(f"{log_tag} 模型返回纯文字，未找到图片：{str(content)[:120]}")
    return None, f"gemini 返回文字而非图片：{str(content)[:80]}"


def _deep_scan_for_image(raw_dict: dict, log_tag: str = "") -> tuple:
    """
    深扫任意 JSON 可序列化结构（非流式 resp.model_dump() 或流式 chunk 列表），
    找藏在非标准字段里的图片数据。适用于 302.ai 网关把图片放在非标准位置的情况。
    返回 (b64_string, None) 或 (None, error_msg)。
    """
    import re as _re
    import json as _json
    import logging as _log_ds
    _log = _log_ds.getLogger("llm_client.deep_scan")

    try:
        raw_str = _json.dumps(raw_dict, ensure_ascii=False)

        # E1: 找 data:image/...;base64, 开头的 base64 串
        data_url_hits = _re.findall(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]{200,})', raw_str)
        for hit in data_url_hits:
            _log.info(f"{log_tag} 格式E1：深扫中发现 data:image base64（长度={len(hit)}）")
            return hit, None

        # E2: 找 file.302.ai 或其他 CDN URL
        cdn_hits = _re.findall(r'https://file\.302\.ai/[^"\'\\s]+', raw_str)
        cdn_hits += _re.findall(r'https?://[^"\'\\s]+\.(?:png|jpg|jpeg|webp)[^"\'\\s]*', raw_str, _re.IGNORECASE)
        seen_e = set()
        for url in cdn_hits:
            url = url.rstrip('.,\\/"\' ')
            if url in seen_e or '![image]' in url:
                continue
            seen_e.add(url)
            _log.info(f"{log_tag} 格式E2：深扫中发现 CDN URL {url[:60]}")
            b64 = _download_url_to_b64(url, log_tag)
            if b64:
                return b64, None

        # E3: 找纯 base64 字段（key 含 "image"/"b64"/"data"）
        def _scan_dict(d, depth=0):
            if depth > 8:
                return None
            if isinstance(d, dict):
                for k, v in d.items():
                    if isinstance(v, str) and len(v) > 500 and k.lower() in (
                        "b64_json", "image", "data", "base64", "content_b64", "image_data"
                    ):
                        try:
                            import base64 as _b64chk
                            _b64chk.b64decode(v[:64])  # 验证是合法 base64
                            _log.info(f"{log_tag} 格式E3：字段 {k} 中发现 base64（长度={len(v)}）")
                            return v
                        except Exception:
                            pass
                    result = _scan_dict(v, depth + 1)
                    if result:
                        return result
            elif isinstance(d, list):
                for item in d:
                    result = _scan_dict(item, depth + 1)
                    if result:
                        return result
            return None

        b64_hit = _scan_dict(raw_dict)
        if b64_hit:
            return b64_hit, None

    except Exception as _e_scan:
        _log.warning(f"{log_tag} 深扫出错：{_e_scan}")

    return None, "深扫未发现图片数据"


def _call_gemini_image_stream(messages: list, log_tag: str = "") -> tuple:
    """
    流式调用 gemini-3-pro-image-preview（经 302.ai 网关）。
    背景：302.ai 网关对该模型在 stream=false 时只返回占位符 `![image]()`，
    图片数据实际生成了（usage.completion_tokens_details.image_tokens > 0），
    但只会通过流式分片（SSE delta）逐步吐出，非流式聚合响应里会被丢弃。
    因此改用 stream=True，累积所有分片的文本与原始 chunk，再复用既有的
    markdown/裸URL/深扫解析逻辑提取图片。
    返回 (b64_string, None) 或 (None, error_msg)。
    """
    import logging as _log_s
    _log = _log_s.getLogger("llm_client.image_stream")

    full_text = ""
    raw_chunks = []
    try:
        stream = PRIMARY_CLIENT.chat.completions.create(
            model=IMAGE_REF_MODEL,
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            try:
                raw_chunks.append(chunk.model_dump() if hasattr(chunk, "model_dump") else {})
            except Exception:
                pass
            try:
                delta = chunk.choices[0].delta
                piece = getattr(delta, "content", None)
                if piece:
                    full_text += piece
            except Exception:
                continue
    except Exception as exc:
        return None, f"{IMAGE_REF_MODEL} 流式调用失败：{exc}"

    b64, err = _extract_image_from_string(full_text, log_tag)
    if b64:
        return b64, None

    b64, err = _deep_scan_for_image({"stream_chunks": raw_chunks}, log_tag)
    if b64:
        return b64, None

    _log.warning(f"{log_tag} 流式响应未找到图片：{full_text[:120]}")
    return None, f"gemini 流式返回未包含图片：{full_text[:80]}"


def _extract_image_from_string(content: str, log_tag: str = "") -> tuple:
    """从字符串 content 中提取图片：markdown 图片链接 或 裸 HTTPS URL。"""
    import re as _re
    import logging as _log_es
    _log = _log_es.getLogger("llm_client.extract_str")

    if not content:
        return None, "空内容"

    md_matches = _re.findall(r'!\[.*?\]\((https?://[^\s)]+)\)', content)
    for url in md_matches:
        _log.info(f"{log_tag} markdown 图片链接 {url[:60]}")
        b64 = _download_url_to_b64(url, log_tag)
        if b64:
            return b64, None

    url_matches = _re.findall(r'https?://\S+\.(?:png|jpg|jpeg|webp|gif)(?:\?\S*)?', content, _re.IGNORECASE)
    url_matches += _re.findall(r'https://file\.302\.ai/\S+', content)
    seen = set()
    for url in url_matches:
        url = url.rstrip('.')
        if url in seen:
            continue
        seen.add(url)
        _log.info(f"{log_tag} 裸 URL {url[:60]}")
        b64 = _download_url_to_b64(url, log_tag)
        if b64:
            return b64, None

    return None, "字符串中未找到图片链接"


def _download_url_to_b64(url: str, log_tag: str = "") -> Optional[str]:
    """下载 HTTPS 图片 URL，返回 base64 字符串；失败返回 None。"""
    import logging as _log_dl
    _log = _log_dl.getLogger("llm_client.download")
    try:
        r = _requests.get(url, timeout=30)
        if r.status_code == 200 and r.content:
            _log.info(f"{log_tag} 下载成功 {len(r.content)//1024}KB")
            return base64.b64encode(r.content).decode()
        _log.warning(f"{log_tag} 下载失败 HTTP {r.status_code}")
    except Exception as e:
        _log.warning(f"{log_tag} 下载异常：{e}")
    return None


def generate_image_302(prompt: str, reference_b64: Optional[str] = None) -> tuple:
    """兼容旧调用名；影视制作台图片生成已完全切换到 TokenStar。"""
    return generate_image_tokenstar(prompt, reference_b64=reference_b64)


# ── 视频生成（可灵官方 API，kling-v3，首帧模式）────────────────────────────
# 文档：https://www.klingai.com/document-api/apiReference/model/imageToVideo
# 鉴权：JWT（HS256），iss=AccessKeyId，exp=当前+30min
# 提交：POST https://api.klingai.com/v1/videos/image2video
# 查询：GET  https://api.klingai.com/v1/videos/image2video/{task_id}
# 状态：submitted / processing / succeed / failed
# 首帧：body.image = base64 或 HTTPS URL

# ── 302.ai 备用视频接口（Kling 2.6，图生视频 5s）────────────────────────────────
# 文档：https://doc.302.ai/386524568e0
# 提交：POST https://api.302.ai/klingai/m2v_26_image2video_5s  (multipart/form-data)
# 查询：GET  https://api.302.ai/klingai/fetch?task_id=xxx
# 状态：5=排队中 / 10=处理中 / 50=失败退款 / 99=成功
# 视频：data.works[0].resource

_302_VIDEO_I2V_URL   = "https://api.302.ai/klingai/m2v_26_image2video_5s"
_302_VIDEO_FETCH_URL = "https://api.302.ai/klingai/fetch"

# ── 可灵官方新版 API（kling-3.0-turbo，2026 起启用）──────────────────────────
# 文档：POST /image-to-video/{model}，鉴权改为单个 Bearer API Key（不再是
# AccessKeyId+Secret 签 JWT）。旧版 kling-v3 + JWT 已废弃/不再稳定，见下方
# _KLING_ACCESS_KEY_ID/_KLING_ACCESS_KEY_SECRET 仅作兼容旧配置保留。
# 提交：POST https://api-singapore.klingai.com/image-to-video/kling-3.0-turbo
# 查询：GET  https://api-singapore.klingai.com/tasks?external_task_ids={id}
# 状态：submitted / processing / succeeded / failed
_KLING_OFFICIAL_BASE   = "https://api-singapore.klingai.com"
_KLING_API_KEY          = os.getenv("KLING_API_KEY", "")
_KLING_MODEL_NAME       = os.getenv("KLING_MODEL_NAME", "kling-3.0-turbo")

# ── 可灵官方旧版 API（kling-v3 + JWT，已废弃，仅兼容保留）────────────────────
_KLING_ACCESS_KEY_ID     = os.getenv("KLING_ACCESS_KEY_ID", "")
_KLING_ACCESS_KEY_SECRET = os.getenv("KLING_ACCESS_KEY_SECRET", "")


def _verify_image_url(url: str, log: Any) -> bool:
    """校验一个图床 URL 真的能拿到图片二进制数据（Content-Type: image/*），
    而不是一个 HTML 预览页——tmpfiles.org 目前的 /dl/ 直链已经会返回网页而非文件，
    直接把这种 URL 交给可灵会报 "Image format is invalid"。"""
    try:
        r = _requests.get(url, timeout=15, stream=True)
        ctype = (r.headers.get("Content-Type") or "").lower()
        ok = r.status_code == 200 and ctype.startswith("image/")
        if not ok:
            log.warning(f"[upload] 校验失败：status={r.status_code} content-type={ctype}")
        return ok
    except Exception as e:
        log.warning(f"[upload] 校验异常：{e}")
        return False


def _upload_image_to_public(img_bytes: bytes, ext: str = "png") -> Optional[str]:
    """
    将图片字节上传到图床，返回公开 HTTPS URL。
    链路：litterbox.catbox.moe（1h，稳定返回正确 Content-Type）→ tmpfiles.org（备用，
    目前该服务的直链经常返回 HTML 预览页而非原始文件，已加校验兜底跳过）。
    可灵官方 API image/first_frame 字段只接受能直接下载出图片二进制的 HTTPS URL。
    """
    import logging as _logging
    _log = _logging.getLogger("llm_client.upload")
    mime = f"image/{ext}"

    # ── 方案1: litterbox.catbox.moe（1小时有效，Content-Type 正确）─────────
    try:
        r = _requests.post(
            "https://litterbox.catbox.moe/resources/internals/api.php",
            data={"reqtype": "fileupload", "time": "1h"},
            files={"fileToUpload": (f"frame.{ext}", img_bytes, mime)},
            timeout=30,
        )
        if r.status_code == 200 and r.text.strip().startswith("https://"):
            url = r.text.strip()
            if _verify_image_url(url, _log):
                _log.info(f"[upload] litterbox 成功: {url}")
                return url
            _log.warning(f"[upload] litterbox 返回的 URL 未通过图片校验: {url}")
        else:
            _log.warning(f"[upload] litterbox 失败 status={r.status_code}: {r.text[:200]}")
    except Exception as e:
        _log.warning(f"[upload] litterbox 异常: {e}")

    # ── 方案2: tmpfiles.org（48h，备用；目前直链有时会返回 HTML 预览页）───
    try:
        r = _requests.post(
            "https://tmpfiles.org/api/v1/upload",
            files={"file": (f"frame.{ext}", img_bytes, mime)},
            timeout=30,
        )
        if r.status_code == 200:
            page_url = r.json().get("data", {}).get("url", "")
            if page_url:
                direct_url = page_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                if _verify_image_url(direct_url, _log):
                    _log.info(f"[upload] tmpfiles.org 成功: {direct_url}")
                    return direct_url
                _log.warning(f"[upload] tmpfiles.org 返回的 URL 未通过图片校验: {direct_url}")
        else:
            _log.warning(f"[upload] tmpfiles.org 失败 status={r.status_code}: {r.text[:200]}")
    except Exception as e:
        _log.warning(f"[upload] tmpfiles.org 异常: {e}")

    _log.error("[upload] 所有图床均失败或未通过图片格式校验")
    return None


def _kling_jwt() -> str:
    """生成可灵官方 API 的 JWT Bearer Token（有效期 30 分钟）"""
    try:
        import jwt as _jwt
    except ImportError:
        raise RuntimeError("需要安装 PyJWT：pip install PyJWT")
    now = int(time.time())
    payload = {
        "iss": _KLING_ACCESS_KEY_ID,
        "exp": now + 1800,   # 30 分钟有效期
        "nbf": now - 5,      # 允许 5 秒时钟误差
    }
    return _jwt.encode(payload, _KLING_ACCESS_KEY_SECRET, algorithm="HS256")


def generate_video_302ai_i2v(
    prompt: str,
    image_b64_or_url: Optional[str] = None,   # base64 data URL 或公开 HTTPS URL
    negative_prompt: str = "",
    cfg: float = 0.5,
    duration: int = 5,
    poll: bool = True,
    max_wait: int = 600,
) -> Dict[str, Any]:
    """
    通过 302.ai 调用 Kling 2.6 图生视频（5s）。
    接口文档：https://doc.302.ai/386524568e0
    提交：POST https://api.302.ai/klingai/m2v_26_image2video_5s
    查询：GET  https://api.302.ai/klingai/fetch?task_id=xxx
    状态码：5=排队 / 10=处理中 / 50=失败 / 99=成功
    返回：
      成功 → {"url": "https://...", "task_id": "...", "source": "302ai"}
      排队 → {"task_id": "...", "status": 10, "source": "302ai"}
      失败 → {"error": "...", "source": "302ai"}
    """
    import logging as _log302
    _log302i = _log302.getLogger("llm_client.302ai_i2v")

    api_key = _302_API_KEY
    if not api_key or api_key.startswith("sk-填写"):
        return {"error": "未配置 AI302_API_KEY，无法使用 302.ai 视频接口", "source": "302ai"}

    headers = {"Authorization": f"Bearer {api_key}"}

    # 构建 multipart/form-data 请求体
    files: Dict[str, Any] = {}
    data: Dict[str, Any] = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "cfg": str(cfg),
        "duration": str(duration),
    }

    if image_b64_or_url:
        if image_b64_or_url.startswith("data:"):
            # base64 data URL → 解码为字节，作为文件上传
            try:
                header_part, b64_part = image_b64_or_url.split(",", 1)
                mime = header_part.split(":")[1].split(";")[0]
                ext = mime.split("/")[-1] if "/" in mime else "png"
                img_bytes = base64.b64decode(b64_part)
                files["image"] = (f"frame.{ext}", img_bytes, mime)
            except Exception as e:
                return {"error": f"base64 图片解析失败：{e}", "source": "302ai"}
        else:
            # 已是 HTTPS URL，直接作为文本字段传入
            data["image"] = image_b64_or_url

    try:
        r = _requests.post(
            _302_VIDEO_I2V_URL,
            headers=headers,
            files=files if files else None,
            data=data,
            timeout=60,
        )
        try:
            resp = r.json()
        except Exception:
            return {"error": f"302.ai 响应非 JSON (status={r.status_code})：{r.text[:300]}", "source": "302ai"}
    except Exception as e:
        return {"error": f"302.ai 提交请求异常：{e}", "source": "302ai"}

    if resp.get("status") != 200 or resp.get("result") != 1:
        return {"error": f"302.ai 提交失败：{resp.get('message', str(resp))}", "source": "302ai"}

    task_id = resp.get("data", {}).get("task", {}).get("id", "")
    if not task_id:
        return {"error": f"302.ai 未返回 task_id：{resp}", "source": "302ai"}

    _log302i.info(f"[302ai_i2v] 提交成功 task_id={task_id}")

    if not poll:
        return {"task_id": task_id, "status": 5, "source": "302ai"}

    # ── 轮询等待完成 ──
    elapsed = 0
    interval = 10
    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval
        try:
            pr = _requests.get(
                _302_VIDEO_FETCH_URL,
                headers=headers,
                params={"task_id": task_id},
                timeout=20,
            )
            pd = pr.json()
            cur_status = pd.get("data", {}).get("status", 5)

            if cur_status == 99:
                works = pd.get("data", {}).get("works", [])
                video_url = works[0].get("resource", "") if works else ""
                if video_url:
                    return {"url": video_url, "task_id": task_id, "status": 99, "source": "302ai"}
                return {"error": "302.ai 任务成功但未返回视频 URL", "task_id": task_id, "source": "302ai"}
            elif cur_status == 50:
                return {"error": "302.ai 任务失败（已自动退款）", "task_id": task_id, "source": "302ai"}
            # status 5(排队) / 10(处理中) → 继续等待
        except Exception:
            pass

    return {"task_id": task_id, "status": 10, "source": "302ai",
            "error": f"302.ai 等待超时（{max_wait}s），可手动查询 task_id={task_id}"}


def _resolve_video_frame_image(raw_url: str, log: Any) -> Optional[str]:
    """base64 data URL → 图床 HTTPS URL；HTTPS URL 直接返回；失败返回 None"""
    if raw_url.startswith("data:"):
        try:
            header_part, b64_part = raw_url.split(",", 1)
            mime = header_part.split(":")[1].split(";")[0]
            ext  = mime.split("/")[-1] if "/" in mime else "png"
            img_bytes = base64.b64decode(b64_part)
            return _upload_image_to_public(img_bytes, ext)
        except Exception as _e:
            log.warning(f"[video] base64 解析失败：{_e}")
            return None
    return raw_url  # 已是 HTTPS URL


def _find_video_url_in(obj: Any, depth: int = 0) -> Optional[str]:
    """
    深扫任意 JSON 结构，找形如 .mp4 的视频 URL 或字段名含 video 的字符串。
    用于可灵新版查询接口（/tasks）响应字段名未完全公开时的兜底解析。
    """
    import re as _re
    if depth > 6:
        return None
    if isinstance(obj, str):
        if _re.search(r'https?://\S+\.mp4(\?\S*)?$', obj, _re.IGNORECASE) or \
           (obj.startswith("http") and "video" in obj.lower()):
            return obj
        return None
    if isinstance(obj, dict):
        # 优先找 key 名本身暗示视频的字段
        for k in ("video_url", "url", "video", "resource", "output_url"):
            v = obj.get(k)
            if isinstance(v, str) and v.startswith("http"):
                found = _find_video_url_in(v, depth + 1)
                if found:
                    return found
        for v in obj.values():
            found = _find_video_url_in(v, depth + 1)
            if found:
                return found
        return None
    if isinstance(obj, list):
        for item in obj:
            found = _find_video_url_in(item, depth + 1)
            if found:
                return found
    return None


def _generate_video_kling_v3_jwt(
    prompt: str,
    image_url: Optional[str],
    image_tail_url: Optional[str],
    negative_prompt: str,
    duration: int,
    mode: str,
    aspect_ratio: str,
    sound: str,
    poll: bool,
    max_wait: int,
    log_v: Any,
) -> Dict[str, Any]:
    """旧版可灵官方 API（kling-v3 + JWT 鉴权）。已废弃，仅在新版 KLING_API_KEY
    未配置、但旧版 KLING_ACCESS_KEY_ID/SECRET 仍配置时作为兼容兜底使用。"""
    try:
        token = _kling_jwt()
    except Exception as e:
        log_v.warning(f"[video] JWT 生成失败，fallback 到 302.ai：{e}")
        return generate_video_302ai_i2v(
            prompt=prompt, image_b64_or_url=image_url,
            duration=duration, poll=poll, max_wait=max_wait,
        )

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body: Dict[str, Any] = {
        "model_name": "kling-v3",
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "duration": str(duration),
        "mode": mode,
        "aspect_ratio": aspect_ratio,
        "sound": sound,
        "callback_url": "",
        "external_task_id": "",
    }

    if image_url:
        public_image = _resolve_video_frame_image(image_url, log_v)
        if not public_image:
            log_v.warning("[video] 首帧图处理失败，fallback 到 302.ai")
            return generate_video_302ai_i2v(
                prompt=prompt, image_b64_or_url=image_url,
                duration=duration, poll=poll, max_wait=max_wait,
            )
        body["image"] = public_image

    if image_tail_url:
        public_tail = _resolve_video_frame_image(image_tail_url, log_v)
        if public_tail:
            body["image_tail"] = public_tail
        else:
            log_v.warning("[video] 尾帧图处理失败，忽略 image_tail 字段继续提交")

    submit_url = f"{_KLING_OFFICIAL_BASE}/v1/videos/image2video"
    try:
        r = _requests.post(submit_url, headers=headers, json=body, timeout=60)
        resp_data = r.json()
    except Exception as e:
        log_v.warning(f"[video] 旧版官方 API 请求异常，fallback 到 302.ai：{e}")
        return generate_video_302ai_i2v(
            prompt=prompt, image_b64_or_url=image_url,
            duration=duration, poll=poll, max_wait=max_wait,
        )

    if resp_data.get("code", -1) != 0:
        log_v.warning(f"[video] 旧版官方 API 提交失败 code={resp_data.get('code')}，fallback 到 302.ai")
        return generate_video_302ai_i2v(
            prompt=prompt, image_b64_or_url=image_url,
            duration=duration, poll=poll, max_wait=max_wait,
        )

    task_id = resp_data.get("data", {}).get("task_id", "")
    if not task_id:
        log_v.warning("[video] 旧版官方 API 未返回 task_id，fallback 到 302.ai")
        return generate_video_302ai_i2v(
            prompt=prompt, image_b64_or_url=image_url,
            duration=duration, poll=poll, max_wait=max_wait,
        )

    if not poll:
        return {"task_id": task_id, "status": "submitted", "source": "kling_v3_jwt"}

    poll_url = f"{_KLING_OFFICIAL_BASE}/v1/videos/image2video/{task_id}"
    elapsed, interval = 0, 10
    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval
        try:
            token = _kling_jwt()
            pr = _requests.get(poll_url, headers={"Authorization": f"Bearer {token}"}, timeout=20)
            pd = pr.json()
            if pd.get("code", -1) != 0:
                return {"error": f"查询失败：{pd.get('message','')}", "task_id": task_id}
            task_data = pd.get("data", {})
            task_status = task_data.get("task_status", "")
            if task_status == "succeed":
                videos = task_data.get("task_result", {}).get("videos", [])
                video_url = videos[0].get("url", "") if videos else ""
                if video_url:
                    return {"url": video_url, "task_id": task_id, "source": "kling_v3_jwt"}
                return {"error": "任务完成但未返回视频 URL", "task_id": task_id, "source": "kling_v3_jwt"}
            elif task_status == "failed":
                reason = task_data.get("task_status_msg", "未知原因")
                return {"error": f"任务失败：{reason}", "task_id": task_id, "source": "kling_v3_jwt"}
        except Exception:
            pass

    return {"task_id": task_id, "status": "processing", "source": "kling_v3_jwt",
            "error": f"等待超时（{max_wait}s），可手动轮询 task_id={task_id}"}


def generate_video_kling(
    prompt: str,
    image_url: Optional[str] = None,   # base64 data URL 或 HTTPS URL（首帧图）
    image_tail_url: Optional[str] = None,  # 尾帧图（当前新版 API 暂不支持，见下方说明）
    negative_prompt: str = "",
    duration: int = 5,
    mode: str = "pro",
    aspect_ratio: str = "16:9",
    sound: str = "off",
    resolution: str = "1080p",
    poll: bool = True,
    max_wait: int = 600,
) -> Dict[str, Any]:
    """
    调用可灵官方新版 API（kling-3.0-turbo，Bearer API Key 鉴权）生成视频。
    优先级：KLING_API_KEY（新版）→ KLING_ACCESS_KEY_ID/SECRET（旧版 JWT，已废弃）→ 302.ai 备用。

    image_url      : 首帧图，base64 data URL 或 HTTPS URL。
    image_tail_url : 尾帧图（新版 /image-to-video/{model} 接口文档未公开对应字段，
                     暂不支持；传入时会被忽略并记录警告，不影响首帧图生视频）。
    poll           : True 时轮询等待完成并返回视频 URL；False 立即返回 task_id。
    返回:
      成功 → {"url": "https://...", "task_id": "...", "source": "kling"|"kling_v3_jwt"|"302ai"}
      排队 → {"task_id": "...", "status": ..., "source": ...}
      失败 → {"error": "..."}
    """
    import logging as _logv
    import uuid as _uuid
    _log_v = _logv.getLogger("llm_client.video")

    # ── 1. 新版 KLING_API_KEY 未配置 → 尝试旧版 JWT，再没有则走 302.ai ────────
    if not _KLING_API_KEY:
        if _KLING_ACCESS_KEY_ID and _KLING_ACCESS_KEY_SECRET:
            _log_v.info("[video] 未配置新版 KLING_API_KEY，使用旧版 kling-v3 + JWT 兼容路径")
            return _generate_video_kling_v3_jwt(
                prompt, image_url, image_tail_url, negative_prompt,
                duration, mode, aspect_ratio, sound, poll, max_wait, _log_v,
            )
        _log_v.info("[video] 可灵官方 key 均未配置，直接使用 302.ai 备用接口")
        return generate_video_302ai_i2v(
            prompt=prompt, image_b64_or_url=image_url,
            duration=duration, poll=poll, max_wait=max_wait,
        )

    if image_tail_url:
        _log_v.warning("[video] 新版 kling-3.0-turbo 接口暂不支持尾帧图，已忽略 image_tail_url")

    headers = {
        "Authorization": f"Bearer {_KLING_API_KEY}",
        "Content-Type": "application/json",
    }

    # ── 2. 首帧图：必须是公开 HTTPS URL ───────────────────────────────────────
    public_image = _resolve_video_frame_image(image_url, _log_v) if image_url else None
    if image_url and not public_image:
        _log_v.warning("[video] 首帧图处理失败，fallback 到 302.ai")
        return generate_video_302ai_i2v(
            prompt=prompt, image_b64_or_url=image_url,
            duration=duration, poll=poll, max_wait=max_wait,
        )

    contents: List[Dict[str, Any]] = [{"type": "prompt", "text": prompt}]
    if public_image:
        contents.append({"type": "first_frame", "url": public_image})

    external_task_id = _uuid.uuid4().hex
    body: Dict[str, Any] = {
        "contents": contents,
        "settings": {
            "resolution": resolution,
            "duration": int(duration),
        },
        "options": {
            "callback_url": "",
            "external_task_id": external_task_id,
            "watermark_info": {"enabled": True},
        },
    }

    submit_url = f"{_KLING_OFFICIAL_BASE}/image-to-video/{_KLING_MODEL_NAME}"
    try:
        r = _requests.post(submit_url, headers=headers, json=body, timeout=60)
        try:
            resp_data = r.json()
        except Exception:
            _log_v.warning(f"[video] 新版官方 API 响应非 JSON（status={r.status_code}），fallback 到 302.ai")
            return generate_video_302ai_i2v(
                prompt=prompt, image_b64_or_url=image_url,
                duration=duration, poll=poll, max_wait=max_wait,
            )
    except Exception as e:
        _log_v.warning(f"[video] 新版官方 API 请求异常，fallback 到 302.ai：{e}")
        return generate_video_302ai_i2v(
            prompt=prompt, image_b64_or_url=image_url,
            duration=duration, poll=poll, max_wait=max_wait,
        )

    if resp_data.get("code", -1) != 0:
        _log_v.warning(f"[video] 新版官方 API 提交失败 code={resp_data.get('code')} "
                        f"message={resp_data.get('message')}，fallback 到 302.ai")
        return generate_video_302ai_i2v(
            prompt=prompt, image_b64_or_url=image_url,
            duration=duration, poll=poll, max_wait=max_wait,
        )

    task_id = resp_data.get("data", {}).get("id", "")
    if not task_id:
        _log_v.warning("[video] 新版官方 API 未返回 task id，fallback 到 302.ai")
        return generate_video_302ai_i2v(
            prompt=prompt, image_b64_or_url=image_url,
            duration=duration, poll=poll, max_wait=max_wait,
        )

    if not poll:
        return {"task_id": task_id, "external_task_id": external_task_id,
                "status": "submitted", "source": "kling"}

    # ── 3. 轮询：GET /tasks?external_task_ids={external_task_id} ────────────
    poll_url = f"{_KLING_OFFICIAL_BASE}/tasks"
    elapsed, interval = 0, 10
    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval
        try:
            pr = _requests.get(
                poll_url,
                headers={"Authorization": f"Bearer {_KLING_API_KEY}"},
                params={"external_task_ids": external_task_id},
                timeout=20,
            )
            pd = pr.json()
            if pd.get("code", -1) != 0:
                continue  # 查询本身出错，稍后重试而不是直接失败（新接口偶发抖动）

            entries = pd.get("data", [])
            if isinstance(entries, dict):
                entries = [entries]
            entry = next(
                (e for e in entries if isinstance(e, dict) and
                 e.get("external_id") == external_task_id),
                entries[0] if entries else None,
            )
            if not entry:
                continue

            status = str(entry.get("status", "")).lower()
            if status in ("succeeded", "succeed", "success"):
                video_url = _find_video_url_in(entry)
                if video_url:
                    return {"url": video_url, "task_id": task_id, "source": "kling"}
                _log_v.warning(f"[video] 任务成功但未在响应中找到视频 URL：{entry}")
                return {"error": "任务成功但未返回视频 URL", "task_id": task_id, "source": "kling"}
            elif status == "failed":
                reason = entry.get("message") or entry.get("error") or "未知原因"
                return {"error": f"任务失败：{reason}", "task_id": task_id, "source": "kling"}
            # submitted / processing → 继续等待
        except Exception:
            pass

    return {"task_id": task_id, "external_task_id": external_task_id, "status": "processing",
            "source": "kling", "error": f"等待超时（{max_wait}s），可手动查询 task_id={task_id}"}


def generate_video_tokenstar_i2v(
    prompt: str,
    image_url: Optional[str] = None,
    image_tail_url: Optional[str] = None,
    negative_prompt: str = "",
    duration: int = 5,
    mode: str = "std",
    aspect_ratio: str = "16:9",
    sound: str = "on",
    resolution: str = "1080p",
    poll: bool = True,
    max_wait: int = 600,
    element_list: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """通过 TokenStar 的 Kling ``/v1/videos/image2video`` 生成首帧视频。

    TokenStar 当前接口要求顶层 ``image`` 字段，且不支持 ``aspect_ratio``。
    ``element_list`` 仅接受已由 CreateAigcElement 创建并确认 Status=succeed 的
    ``element_id``；本制作台暂未创建主体元素时不传该字段。
    """
    import logging as _logging

    log_v = _logging.getLogger("llm_client.tokenstar_i2v")
    if not TOKENSTAR_API_KEY:
        return {"error": "未配置 TOKENSTAR_API_KEY，无法调用 TokenStar 图生视频", "source": "tokenstar"}
    if not image_url:
        return {"error": "图生视频必须提供首帧图片", "source": "tokenstar"}

    public_image = _resolve_video_frame_image(image_url, log_v)
    if not public_image or not public_image.startswith("https://"):
        return {
            "error": "首帧图片无法转换为 TokenStar 可下载的公开 HTTPS 地址",
            "source": "tokenstar",
        }

    if image_tail_url:
        log_v.warning("[tokenstar_i2v] 当前图生视频接口不支持尾帧图，已忽略 image_tail_url")
    if negative_prompt:
        log_v.info("[tokenstar_i2v] 当前接口未提供 negative_prompt 字段，已忽略")
    if aspect_ratio != "16:9":
        log_v.info("[tokenstar_i2v] image2video 不支持 aspect_ratio，已忽略")
    if resolution != "1080p":
        log_v.info("[tokenstar_i2v] image2video 当前请求不传 resolution，已忽略")

    body: Dict[str, Any] = {
        "model_name": os.getenv("TOKENSTAR_KLING_MODEL", "kling-v3"),
        "image": public_image,
        "prompt": prompt,
        "duration": str(duration),
        "mode": mode,
        "sound": sound,
    }
    if element_list:
        body["element_list"] = element_list

    headers = {
        "Authorization": f"Bearer {TOKENSTAR_API_KEY}",
        "Content-Type": "application/json",
    }
    submit_url = f"{TOKENSTAR_BASE_URL}/v1/videos/image2video"
    try:
        response = _requests.post(submit_url, headers=headers, json=body, timeout=60)
        response_data = response.json()
    except Exception as exc:
        return {"error": f"TokenStar 图生视频请求异常：{exc}", "source": "tokenstar"}

    if response.status_code >= 400 or response_data.get("code", 0) not in (0, None):
        error = response_data.get("error", {}) if isinstance(response_data, dict) else {}
        message = error.get("message") or response_data.get("message") or str(response_data)
        return {"error": f"TokenStar 图生视频提交失败：{message}", "source": "tokenstar"}

    task_data = response_data.get("data", {})
    task_id = task_data.get("task_id") or task_data.get("id")
    if not task_id:
        return {"error": f"TokenStar 未返回 task_id：{response_data}", "source": "tokenstar"}
    if not poll:
        return {"task_id": task_id, "status": "submitted", "source": "tokenstar"}

    poll_url = f"{TOKENSTAR_BASE_URL}/v1/videos/image2video/{task_id}"
    elapsed, interval = 0, 10
    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval
        try:
            poll_response = _requests.get(poll_url, headers=headers, timeout=20)
            poll_data = poll_response.json()
        except Exception:
            continue

        if poll_response.status_code >= 400 or poll_data.get("code", 0) not in (0, None):
            error = poll_data.get("error", {}) if isinstance(poll_data, dict) else {}
            message = error.get("message") or poll_data.get("message") or str(poll_data)
            return {"error": f"TokenStar 图生视频查询失败：{message}", "task_id": task_id, "source": "tokenstar"}

        task_data = poll_data.get("data", {})
        status = str(task_data.get("task_status") or task_data.get("status") or "").lower()
        if status in ("succeed", "succeeded", "success", "done"):
            videos = task_data.get("task_result", {}).get("videos", [])
            video_url = videos[0].get("url", "") if videos and isinstance(videos[0], dict) else ""
            if video_url:
                return {"url": video_url, "task_id": task_id, "source": "tokenstar"}
            return {"error": "TokenStar 任务成功但未返回视频 URL", "task_id": task_id, "source": "tokenstar"}
        if status in ("failed", "failure", "fail"):
            reason = task_data.get("task_status_msg") or task_data.get("message") or "未知原因"
            return {"error": f"TokenStar 视频任务失败：{reason}", "task_id": task_id, "source": "tokenstar"}

    return {
        "error": f"TokenStar 图生视频等待超时（{max_wait}s）",
        "task_id": task_id,
        "status": "processing",
        "source": "tokenstar",
    }


# 保留既有调用名，所有新请求统一改走 TokenStar 图生视频接口。
generate_video_kling = generate_video_tokenstar_i2v
generate_video_302 = generate_video_tokenstar_i2v



# ── 分镜专用结构化调用（MV04，使用 gpt-4o） ──────────────────────────────────

def call_storyboard(system_prompt: str, user_content: str) -> Dict[str, Any]:
    """
    分镜制作专用函数，使用 gpt-4o 优先队列。
    gpt-4o 支持 JSON mode，速度更快，结构化输出更稳定。
    """
    last_error: Optional[str] = None
    for model_name, client in _storyboard_model_queue():
        use_json_mode = _supports_json_mode(model_name)
        sys_content   = system_prompt if use_json_mode else _json_system_hint(system_prompt)
        for attempt in range(1, 4):
            try:
                kwargs: Dict[str, Any] = dict(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": sys_content},
                        {"role": "user",   "content": user_content},
                    ],
                    temperature=0.3,
                )
                if use_json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                response = client.chat.completions.create(**kwargs)
                raw = response.choices[0].message.content or "{}"
                if not use_json_mode:
                    raw = _extract_json(raw)
                return json.loads(raw)
            except Exception as exc:
                last_error = f"{model_name}: {exc}"
                if attempt < 3:
                    time.sleep(1)
    return {"error": True, "message": last_error or "Unknown error"}
