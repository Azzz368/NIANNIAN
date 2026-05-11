"""
念念 LLM 客户端 — 接入 302.ai 统一网关
任务与模型映射：
  文本结构化分析（家属访谈 / MV01-06）: claude-sonnet-4-6  →（失败自动回退）→ gpt-5.4
  图像内容理解（describe_image）       : gemini-2.0-pro-image-preview
  图像生成（generate_image_302）        : gemini-2.0-pro-image-preview
  视频生成（generate_video_302）        : kling-v1-5-pro (Kling O3)
  语音转写（transcribe_audio）          : whisper-1
配置项（填写 .env 文件）：
  AI302_API_KEY          = sk-xxxxxxxxxxxx
  AI302_TEXT_MODEL       = claude-sonnet-4-6   （主力文本模型）
  AI302_TEXT_FALLBACK    = gpt-5.4             （文本模型回退）
  AI302_VISION_MODEL     = gemini-2.0-pro-image-preview
  AI302_IMAGE_GEN_MODEL  = gemini-2.0-pro-image-preview
  AI302_VIDEO_GEN_MODEL  = kling-v1-5-pro
  AI302_AUDIO_MODEL      = whisper-1
  LOCAL_LLM_BASE_URL     =                     （本地备用，可留空）
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


def generate_image_302(prompt: str, reference_b64: Optional[str] = None) -> tuple:
    """
    生成图像：先尝试 nano-banana（Wavespeed），失败则回退至 gpt-4o-image-generation。
    reference_b64 : 参考人像的 base64 字符串（PNG/JPG）。
                    若提供，将跳过 nano-banana，直接用 gpt-4o images.edit 以参考图为锚点生成，
                    确保分镜中逝者形象与参考照片一致。
    返回 (b64_string, None) 成功；(None, error_message) 失败。
    """
    # ── 有参考照片时：走 gpt-4o images.edit（角色形象锚定）────────────────────
    if reference_b64:
        try:
            import io as _io
            import base64 as _b64
            img_data = _b64.b64decode(reference_b64)
            img_file = _io.BytesIO(img_data)
            img_file.name = "reference.png"

            edit_prompt = (
                f"Use the person in the reference image as the main character. "
                f"Keep the character's face, age, and appearance IDENTICAL to the reference photo. "
                f"Generate a new cinematic scene: {prompt}"
            )
            resp = PRIMARY_CLIENT.images.edit(
                model=IMAGE_GEN_FALLBACK,   # gpt-4o-image-generation
                image=img_file,
                prompt=edit_prompt,
                size="1024x1024",
                response_format="b64_json",
                n=1,
            )
            b64 = resp.data[0].b64_json if resp.data else None
            if b64:
                return b64, None
        except Exception as exc:
            # 参考图生成失败 → 降级为无参考图生成（仍在 prompt 中保留 DNA 描述）
            pass  # fall through to normal generation

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


# ── 视频生成（302.ai Kling m2v_omni_3） ──────────────────────────────────────
# 接口文档实测：
#   提交：POST https://api.302.ai/klingai/m2v_omni_3_video
#   轮询：GET  https://api.302.ai/klingai/task/{task_id}/fetch
#   status: 5=排队中, 10=生成中, 99=已完成
#   视频 URL 在 data.works[0].resource.resource（omni3 格式）

_KLING_BASE = "https://api.302.ai/klingai"


def _upload_image_to_public(img_bytes: bytes, ext: str = "jpg") -> Optional[str]:
    """
    将图片字节上传到免费图床，返回公开 HTTPS URL。
    链路：freeimage.host → litterbox.catbox.moe → None
    注：Kling omni3 的 image 字段只接受 HTTPS URL，不接受 base64。
    """
    # ── 方案1: freeimage.host（免费，无需注册）──────────────────────────────────
    try:
        b64str = base64.b64encode(img_bytes).decode()
        r = _requests.post(
            "https://freeimage.host/api/1/upload",
            data={"key": "6d207e02198a847aa98d0a2a901485a5", "source": b64str, "format": "json"},
            timeout=30,
        )
        if r.status_code == 200:
            url = r.json().get("image", {}).get("url", "")
            if url:
                return url
    except Exception:
        pass

    # ── 方案2: litterbox.catbox.moe（临时1小时，免费）────────────────────────────
    try:
        r = _requests.post(
            "https://litterbox.catbox.moe/resources/internals/api.php",
            data={"reqtype": "fileupload", "time": "1h"},
            files={"fileToUpload": (f"frame.{ext}", img_bytes, f"image/{ext}")},
            timeout=30,
        )
        if r.status_code == 200 and r.text.strip().startswith("https://"):
            return r.text.strip()
    except Exception:
        pass

    return None


def generate_video_302(
    prompt: str,
    image_url: Optional[str] = None,
    duration: int = 5,
    poll: bool = True,
    max_wait: int = 300,
    o1_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    通过 302.ai 调用 Kling m2v_omni_3_video 生成视频。
    image_url : base64 data URL（data:image/png;base64,...）或 https URL 均可。
                - base64 data URL → 上传到免费图床获取 HTTPS URL → 以 images:[url] JSON 提交
                - https URL      → 直接以 images:[url] JSON 提交
    o1_type   : Kling omni3 功能类型。
                - 有图片时默认 "firstTail"（首帧模式，图片作为第一帧）
                - "referImage"：图片参考（风格/内容参考，不锁定首帧）
                - None + 无图片：纯文生视频
    poll      : True 时轮询等待完成并返回视频 URL；False 立即返回 task_id。
    返回:
      成功 → {"url": "https://...", "task_id": "..."}
      排队 → {"task_id": "...", "status": 5}
      失败 → {"error": "..."}
    """
    model_path    = VIDEO_GEN_MODEL.lstrip("/")
    endpoint_path = model_path.split("/")[-1] if "/" in model_path else model_path
    submit_url    = f"{_KLING_BASE}/{endpoint_path}"
    auth_headers  = {"Authorization": f"Bearer {_302_API_KEY}", "Content-Type": "application/json"}

    # 处理 image_url：
    #   - base64 data URL（data:image/...;base64,...）→ 302.ai Kling 原生支持，直接传入
    #   - https URL → 直接传入
    # Kling omni3 正确用法：image = 单个 HTTPS URL 字符串（非数组、非 base64）
    # images:[] / image_url / o1_type 均被 API 静默忽略
    public_img_url: Optional[str] = None
    if image_url:
        if image_url.startswith("data:"):
            # base64 data URL → 先上传到公共图床，获取 HTTPS URL
            try:
                header_part, b64_part = image_url.split(",", 1)
                mime = header_part.split(":")[1].split(";")[0]
                ext  = mime.split("/")[-1] if "/" in mime else "jpg"
                img_bytes = base64.b64decode(b64_part)
                public_img_url = _upload_image_to_public(img_bytes, ext)
            except Exception as e:
                return {"error": f"base64 解码失败：{e}"}
            if not public_img_url:
                return {"error": "图片上传到公共图床失败，请稍后重试"}
        else:
            public_img_url = image_url  # 已是 HTTPS URL，直接使用

    effective_aspect = "auto" if public_img_url else "16:9"

    try:
        body: Dict[str, Any] = {
            "prompt": prompt,
            "duration": duration,
            "aspect_ratio": effective_aspect,
            "mode": "pro",
        }
        if public_img_url:
            body["image"] = public_img_url  # 单个字符串，非数组

        r = _requests.post(submit_url, headers=auth_headers, json=body, timeout=60)
        r.raise_for_status()
        resp_data = r.json()
        task_id = (
            resp_data.get("data", {}).get("task", {}).get("id")
            or resp_data.get("data", {}).get("taskId")
            or resp_data.get("task_id")
            or ""
        )
        if not task_id:
            return {"error": f"提交失败，未获得 task_id：{r.text[:300]}", "debug_body": body}
    except Exception as exc:
        return {"error": f"提交请求异常：{exc}"}

    if not poll:
        return {"task_id": task_id, "status": 5, "debug_body": body}

    # 轮询等待完成
    poll_url = f"{_KLING_BASE}/task/{task_id}/fetch"
    elapsed  = 0
    interval = 10
    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval
        try:
            pr = _requests.get(poll_url, headers={"Authorization": f"Bearer {_302_API_KEY}"}, timeout=20)
            pd = pr.json().get("data", {})
            status = pd.get("status")
            if status == 99:  # 完成
                # taskWorks[0].resource.resource  OR  works[0].resource.url
                url = ""
                task_works = pd.get("taskWorks") or []
                works      = pd.get("works")     or []
                if task_works:
                    url = (task_works[0].get("resource") or {}).get("resource") or ""
                if not url and works:
                    url = (works[0].get("resource") or {}).get("url") or ""
                if url:
                    return {"url": url, "task_id": task_id}
                return {"error": "任务完成但未返回视频 URL", "task_id": task_id}
            elif status not in (5, 10, None):
                return {"error": f"任务状态异常：status={status}", "task_id": task_id}
        except Exception:
            pass  # 网络抖动，继续等待

    return {"task_id": task_id, "status": 5, "error": f"等待超时（{max_wait}s），task_id={task_id}"}




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
