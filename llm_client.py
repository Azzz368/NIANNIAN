"""
念念 LLM 客户端 — 接入 302.ai 统一网关 + 可灵官方 API
任务与模型映射：
  文本结构化分析（家属访谈 / MV01-06）: claude-sonnet-4-6  →（失败自动回退）→ gpt-5.4
  图像内容理解（describe_image）       : gemini-2.0-pro-image-preview
  图像生成（generate_image_302）        : gemini-2.0-pro-image-preview
  视频生成（generate_video_kling）      : 优先可灵官方直连（kling-v3，首帧模式）
                                         → 自动回退 302.ai（m2v_26_image2video_5s）
  语音转写（transcribe_audio）          : whisper-1
配置项（填写 .env 文件）：
  AI302_API_KEY          = sk-xxxxxxxxxxxx       ← 必填，图文/视频 302.ai 备用均使用
  AI302_TEXT_MODEL       = claude-sonnet-4-6
  AI302_TEXT_FALLBACK    = gpt-5.4
  AI302_VISION_MODEL     = gemini-2.0-pro-image-preview
  AI302_IMAGE_GEN_MODEL  = gemini-2.0-pro-image-preview
  AI302_AUDIO_MODEL      = whisper-1
  KLING_ACCESS_KEY_ID    = （可灵官方 AccessKey ID，留空则自动走 302.ai 备用）
  KLING_ACCESS_KEY_SECRET= （可灵官方 AccessKey Secret，留空则自动走 302.ai 备用）
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

load_dotenv()

# ── 302.ai 网关 ───────────────────────────────────────────────────────────────
_302_BASE_URL = "https://api.302.ai/v1"
_302_API_KEY  = os.getenv("AI302_API_KEY", "sk-填写您的302.ai密钥")

# ── 各任务专属模型 ─────────────────────────────────────────────────────────────
# 文本分析：主力 Claude，自动回退到 GPT-5.4
TEXT_MODEL          = os.getenv("AI302_TEXT_MODEL",      "claude-sonnet-4-6")
TEXT_FALLBACK_MODEL = os.getenv("AI302_TEXT_FALLBACK",   "gpt-5.4")

# 分镜制作（MV04）专属：gpt-4o（速度快、结构化能力强）
STORYBOARD_MODEL    = os.getenv("AI302_STORYBOARD_MODEL", "gpt-4o")

# 数字人对话 & 人设融合（速度优先）
DIALOGUE_MODEL      = os.getenv("AI302_DIALOGUE_MODEL",  "doubao-Seed-2-0-lite")

# 图像 / 视频 / 音频（固定模型，不回退）
VISION_MODEL        = os.getenv("AI302_VISION_MODEL",       "gemini-2.5-flash")
IMAGE_GEN_MODEL     = os.getenv("AI302_IMAGE_GEN_MODEL",    "google/nano-banana/text-to-image")
IMAGE_GEN_FALLBACK  = os.getenv("AI302_IMAGE_GEN_FALLBACK", "gpt-4o-image-generation")
VIDEO_GEN_MODEL     = os.getenv("AI302_VIDEO_GEN_MODEL",    "kling-v1-5-pro")
AUDIO_MODEL         = os.getenv("AI302_AUDIO_MODEL",        "whisper-1")

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
      1. claude-sonnet-4-6  （主力）
      2. gpt-5.4            （自动回退）
      3. 本地 LLM           （可选）
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
      1. gpt-4o  （速度快、结构化稳定）
      2. gpt-5.4 （备用）
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
                    max_tokens=600,
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
                    max_tokens=600,
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
) -> Dict[str, Any]:
    """
    根据分镜 + 三要素，用 gpt-4o 同时生成：
      - image_prompt : 英文，首帧图片，严格锁定角色 DNA（中国老年男性外貌）
      - video_prompt : 中文，可灵首帧生视频，含镜头运动/情绪/氛围
    返回 {"image_prompt": "...", "video_prompt": "..."}
    """
    # 提取角色 DNA 描述
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

    # 从 scene_library 匹配场景说明（优先用 scene_ref，再 fallback 到 scene_id）
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

    system_prompt = (
        "你是专业的追思影像 Prompt 工程师，擅长将中文分镜描述转化为高质量 AI 生成 Prompt。\n\n"
        "任务：根据提供的分镜信息和角色DNA，同时输出两条 Prompt：\n\n"
        "1. image_prompt（英文）：\n"
        "   - 必须将角色DNA翻译并嵌入，精准锁定外貌（例如：elderly Chinese man, 75 years old, silver-white hair combed back neatly, silver rectangular glasses...）\n"
        "   - 禁止出现任何与DNA不符的外貌描述（如：American, Western, blonde, etc.）\n"
        "   - 包含场景光线、构图、情绪基调\n"
        "   - 风格后缀：photorealistic, cinematic still, 8K, warm golden hour lighting\n\n"
        "2. video_prompt（中文）：\n"
        "   - 镜头运动（推镜/拉镜/横移/固定等）\n"
        "   - 人物动作与表情细节\n"
        "   - 环境光线变化\n"
        "   - 情感基调与节奏\n"
        "   - 时长约5-6秒的画面感\n\n"
        "严格按以下 JSON 返回，不要包含任何其他文字：\n"
        '{"image_prompt": "...", "video_prompt": "..."}'
    )

    user_payload = {
        "scene": scene,
        "character_dna（必须锚定）": dna_text,
        "scene_environment_descriptor（必须融入背景）": scene_lib_desc or "（未提供场景描述）",
    }

    result = call_storyboard(system_prompt, json.dumps(user_payload, ensure_ascii=False))
    if result.get("error") or not result.get("image_prompt"):
        # 降级：使用原始 mj_prompt
        fallback_img = scene.get("mj_prompt") or scene.get("description") or ""
        fallback_vid = scene.get("description") or ""
        return {"image_prompt": fallback_img, "video_prompt": fallback_vid, "_fallback": True}
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


def generate_image_302_ref(prompt: str, reference_b64: str) -> tuple:
    """
    有参考照片时的图生图：使用 gemini-3-pro-image-preview（多模态输入）。
    通过 302.ai 统一网关调用，传入参考图 + 文字 Prompt，让模型在画面中保留人物形象。
    返回 (b64_string, None) 成功；(None, error_message) 失败。
    """
    import logging as _log_ref
    _log_r = _log_ref.getLogger("llm_client.image_ref")

    try:
        ref_data_url = f"data:image/png;base64,{reference_b64}"
        full_prompt = (
            f"请严格保留参考图中人物的面部特征、年龄、肤色和外貌，将其作为画面主角。"
            f"生成一幅电影感的追思纪念场景：{prompt}。"
            f"风格：电影质感、暖色调、16:9 构图。"
        )
        resp = PRIMARY_CLIENT.chat.completions.create(
            model="gemini-3-pro-image-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_prompt},
                        {"type": "image_url", "image_url": {"url": ref_data_url}},
                    ],
                }
            ],
            stream=False,
        )
        # gemini-3-pro-image-preview 在 content 里返回 image 块
        for part in (resp.choices[0].message.content or []):
            if isinstance(part, dict) and part.get("type") == "image_url":
                url = part.get("image_url", {}).get("url", "")
                if url.startswith("data:"):
                    b64 = url.split(",", 1)[-1]
                    return b64, None
        # 也可能直接在 b64_json 字段
        if hasattr(resp.choices[0].message, "content") and isinstance(resp.choices[0].message.content, str):
            # 文字回复，说明模型没有输出图片
            return None, f"gemini-3-pro-image-preview 未返回图片（可能 prompt 被拒绝）"
        return None, "gemini-3-pro-image-preview 返回结构未识别"
    except Exception as exc:
        _log_r.warning(f"[generate_image_302_ref] 失败：{exc}")
        return None, str(exc)


def generate_image_302(prompt: str, reference_b64: Optional[str] = None) -> tuple:
    """
    生成图像主入口。
    · 有参考照片 → 优先用 gemini-3-pro-image-preview（图生图，保留人物形象）
                   失败则降级至 gpt-4o images.edit
                   再失败则降级至无参考图普通生成
    · 无参考照片 → nano-banana（Wavespeed）→ 失败则 gpt-4o-image-generation
    返回 (b64_string, None) 成功；(None, error_message) 失败。
    """
    import logging as _log_img
    _log_i = _log_img.getLogger("llm_client.image")

    # ── 有参考照片：先走 gemini-3-pro-image-preview 图生图 ──────────────────
    if reference_b64:
        b64, err = generate_image_302_ref(prompt, reference_b64)
        if b64:
            _log_i.info("[image] gemini-3-pro-image-preview 图生图成功")
            return b64, None
        _log_i.warning(f"[image] gemini-3-pro-image-preview 失败（{err}），降级至 gpt-4o images.edit")

        # 降级：gpt-4o images.edit
        _ref_edit_error: Optional[str] = None
        try:
            import io as _io
            import base64 as _b64
            from PIL import Image as _PILImg

            raw = _b64.b64decode(reference_b64)
            pil = _PILImg.open(_io.BytesIO(raw)).convert("RGBA")
            pil.thumbnail((1024, 1024), _PILImg.LANCZOS)
            buf = _io.BytesIO()
            pil.save(buf, format="PNG")
            buf.seek(0)
            buf.name = "reference.png"

            edit_prompt = (
                f"Use the person in the reference image as the main character. "
                f"Keep the character's face, age, skin tone, and appearance IDENTICAL to the reference photo. "
                f"Generate a new cinematic memorial scene: {prompt}"
            )
            resp = PRIMARY_CLIENT.images.edit(
                model=IMAGE_GEN_FALLBACK,
                image=buf,
                prompt=edit_prompt,
                size="1024x1024",
                response_format="b64_json",
                n=1,
            )
            b64 = resp.data[0].b64_json if resp.data else None
            if b64:
                _log_i.info("[image] gpt-4o images.edit 成功")
                return b64, None
            _ref_edit_error = "images.edit 返回空数据"
        except Exception as exc:
            _ref_edit_error = str(exc)
            _log_i.warning(f"[image] gpt-4o images.edit 失败（{exc}），降级为普通生成")
        # 两级参考图生成均失败 → 继续普通生成（不中断流程）

    # ── 无参考图（或参考图生成失败）：主力 nano-banana ──────────────────────────
    if "/" in IMAGE_GEN_MODEL:
        b64, err = _generate_image_wavespeed(prompt, IMAGE_GEN_MODEL)
        if b64:
            return b64, None
        fallback_err_prefix = f"[nano-banana 失败：{err}] → 尝试备用模型…"
    else:
        fallback_err_prefix = ""

    # 备用：gpt-4o-image-generation（标准 OpenAI images.generate）
    try:
        resp = PRIMARY_CLIENT.images.generate(
            model=IMAGE_GEN_FALLBACK,
            prompt=prompt,
            size="1024x1024",
            response_format="b64_json",
            n=1,
        )
        b64 = resp.data[0].b64_json if resp.data else None
        if b64:
            return b64, None
        return None, fallback_err_prefix + "备用模型返回空数据"
    except Exception as exc:
        return None, fallback_err_prefix + str(exc)


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

_KLING_OFFICIAL_BASE   = "https://api-singapore.klingai.com"
_KLING_ACCESS_KEY_ID     = os.getenv("KLING_ACCESS_KEY_ID", "")
_KLING_ACCESS_KEY_SECRET = os.getenv("KLING_ACCESS_KEY_SECRET", "")


def _upload_image_to_public(img_bytes: bytes, ext: str = "png") -> Optional[str]:
    """
    将图片字节上传到图床，返回公开 HTTPS URL。
    链路：tmpfiles.org（48h）→ litterbox.catbox.moe（1h）→ None
    可灵官方 API image 字段只接受 HTTPS URL，不接受 base64。
    """
    import logging as _logging
    _log = _logging.getLogger("llm_client.upload")

    # ── 方案1: tmpfiles.org ──────────────────────────────────────────────────
    try:
        r = _requests.post(
            "https://tmpfiles.org/api/v1/upload",
            files={"file": (f"frame.{ext}", img_bytes, f"image/{ext}")},
            timeout=30,
        )
        if r.status_code == 200:
            page_url = r.json().get("data", {}).get("url", "")
            if page_url:
                direct_url = page_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                _log.info(f"[upload] tmpfiles.org 成功: {direct_url}")
                return direct_url
        _log.warning(f"[upload] tmpfiles.org 失败 status={r.status_code}: {r.text[:200]}")
    except Exception as e:
        _log.warning(f"[upload] tmpfiles.org 异常: {e}")

    # ── 方案2: litterbox.catbox.moe（1小时有效）─────────────────────────────
    try:
        r = _requests.post(
            "https://litterbox.catbox.moe/resources/internals/api.php",
            data={"reqtype": "fileupload", "time": "1h"},
            files={"fileToUpload": (f"frame.{ext}", img_bytes, f"image/{ext}")},
            timeout=30,
        )
        if r.status_code == 200 and r.text.strip().startswith("https://"):
            url = r.text.strip()
            _log.info(f"[upload] litterbox 成功: {url}")
            return url
        _log.warning(f"[upload] litterbox 失败 status={r.status_code}: {r.text[:200]}")
    except Exception as e:
        _log.warning(f"[upload] litterbox 异常: {e}")

    _log.error("[upload] 所有图床均失败")
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


def generate_video_kling(
    prompt: str,
    image_url: Optional[str] = None,   # base64 data URL 或 HTTPS URL（首帧图）
    image_tail_url: Optional[str] = None,  # 尾帧图（可选，kling-v2-6 支持）
    negative_prompt: str = "",
    duration: int = 5,
    mode: str = "pro",
    aspect_ratio: str = "16:9",
    sound: str = "off",
    poll: bool = True,
    max_wait: int = 600,
) -> Dict[str, Any]:
    """
    调用可灵官方 API（kling-v3）生成视频。
    若 KLING_ACCESS_KEY_ID / SECRET 未配置，或官方 API 调用失败，
    自动 fallback 到 302.ai（m2v_26_image2video_5s）。

    image_url      : 首帧图，base64 data URL 或 HTTPS URL。
    image_tail_url : 尾帧图（可选），同格式。
    poll           : True 时轮询等待完成并返回视频 URL；False 立即返回 task_id。
    返回:
      成功 → {"url": "https://...", "task_id": "...", "source": "kling"|"302ai"}
      排队 → {"task_id": "...", "status": ..., "source": ...}
      失败 → {"error": "..."}
    """
    import logging as _logv
    _log_v = _logv.getLogger("llm_client.video")

    # ── 1. 若未配置可灵官方 key，直接走 302.ai ───────────────────────────────
    if not _KLING_ACCESS_KEY_ID or not _KLING_ACCESS_KEY_SECRET:
        _log_v.info("[video] 可灵官方 key 未配置，直接使用 302.ai 备用接口")
        return generate_video_302ai_i2v(
            prompt=prompt,
            image_b64_or_url=image_url,
            duration=duration,
            poll=poll,
            max_wait=max_wait,
        )

    # ── 2. 尝试可灵官方 API ──────────────────────────────────────────────────
    try:
        token = _kling_jwt()
    except Exception as e:
        _log_v.warning(f"[video] JWT 生成失败，fallback 到 302.ai：{e}")
        return generate_video_302ai_i2v(
            prompt=prompt, image_b64_or_url=image_url,
            duration=duration, poll=poll, max_wait=max_wait,
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # 构建请求体（kling-v3 接口规范）
    body: Dict[str, Any] = {
        "model_name": "kling-v3",
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "duration": str(duration),       # "5" 或 "10"
        "mode": mode,                    # "std" 或 "pro"
        "aspect_ratio": aspect_ratio,
        "sound": sound,                  # "on" / "off"
        "callback_url": "",
        "external_task_id": "",
    }

    def _resolve_image(raw_url: str) -> Optional[str]:
        """base64 data URL → 图床 HTTPS URL；HTTPS URL 直接返回；失败返回 None"""
        if raw_url.startswith("data:"):
            try:
                header_part, b64_part = raw_url.split(",", 1)
                mime = header_part.split(":")[1].split(";")[0]
                ext  = mime.split("/")[-1] if "/" in mime else "png"
                img_bytes = base64.b64decode(b64_part)
                return _upload_image_to_public(img_bytes, ext)
            except Exception as _e:
                _log_v.warning(f"[video] base64 解析失败：{_e}")
                return None
        return raw_url  # 已是 HTTPS URL

    # 首帧图
    if image_url:
        public_image = _resolve_image(image_url)
        if not public_image:
            _log_v.warning("[video] 首帧图处理失败，fallback 到 302.ai")
            return generate_video_302ai_i2v(
                prompt=prompt, image_b64_or_url=image_url,
                duration=duration, poll=poll, max_wait=max_wait,
            )
        body["image"] = public_image

    # 尾帧图（可选）
    if image_tail_url:
        public_tail = _resolve_image(image_tail_url)
        if public_tail:
            body["image_tail"] = public_tail
        else:
            _log_v.warning("[video] 尾帧图处理失败，忽略 image_tail 字段继续提交")

    submit_url = f"{_KLING_OFFICIAL_BASE}/v1/videos/image2video"
    try:
        r = _requests.post(submit_url, headers=headers, json=body, timeout=60)
        try:
            resp_data = r.json()
        except Exception:
            _log_v.warning(f"[video] 官方 API 响应非 JSON，fallback 到 302.ai")
            return generate_video_302ai_i2v(
                prompt=prompt, image_b64_or_url=image_url,
                duration=duration, poll=poll, max_wait=max_wait,
            )
    except Exception as e:
        _log_v.warning(f"[video] 官方 API 请求异常，fallback 到 302.ai：{e}")
        return generate_video_302ai_i2v(
            prompt=prompt, image_b64_or_url=image_url,
            duration=duration, poll=poll, max_wait=max_wait,
        )

    # 官方响应：{"code":0, "message":"SUCCEED", "data":{"task_id":"...", "task_status":"submitted"}}
    if resp_data.get("code", -1) != 0:
        _log_v.warning(f"[video] 官方 API 提交失败 code={resp_data.get('code')}，fallback 到 302.ai")
        return generate_video_302ai_i2v(
            prompt=prompt, image_b64_or_url=image_url,
            duration=duration, poll=poll, max_wait=max_wait,
        )

    task_id = resp_data.get("data", {}).get("task_id", "")
    if not task_id:
        _log_v.warning(f"[video] 官方 API 未返回 task_id，fallback 到 302.ai")
        return generate_video_302ai_i2v(
            prompt=prompt, image_b64_or_url=image_url,
            duration=duration, poll=poll, max_wait=max_wait,
        )

    if not poll:
        return {"task_id": task_id, "status": "submitted", "source": "kling", "debug_body": body}

    # ── 轮询等待完成 ──────────────────────────────────────────────────────────
    poll_url  = f"{_KLING_OFFICIAL_BASE}/v1/videos/image2video/{task_id}"
    elapsed   = 0
    interval  = 10
    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval
        try:
            token = _kling_jwt()
            pr = _requests.get(
                poll_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=20,
            )
            pd = pr.json()
            if pd.get("code", -1) != 0:
                return {"error": f"查询失败：{pd.get('message','')}", "task_id": task_id}

            task_data   = pd.get("data", {})
            task_status = task_data.get("task_status", "")

            if task_status == "succeed":
                # 视频 URL：data.task_result.videos[0].url
                videos = task_data.get("task_result", {}).get("videos", [])
                video_url = videos[0].get("url", "") if videos else ""
                if video_url:
                    return {"url": video_url, "task_id": task_id, "source": "kling"}
                return {"error": "任务完成但未返回视频 URL", "task_id": task_id, "source": "kling"}

            elif task_status == "failed":
                reason = task_data.get("task_status_msg", "未知原因")
                return {"error": f"任务失败：{reason}", "task_id": task_id, "source": "kling"}

            # submitted / processing → 继续等待
        except Exception:
            pass

    return {"task_id": task_id, "status": "processing", "source": "kling",
            "error": f"等待超时（{max_wait}s），可手动轮询 task_id={task_id}"}


# 兼容旧调用名（studio.py 等地方仍用 generate_video_302）
generate_video_302 = generate_video_kling



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
