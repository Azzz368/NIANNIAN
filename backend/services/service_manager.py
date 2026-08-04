# backend/services/service_manager.py
# 统一出口 —— routers 只允许从这里 import。
# 通过 backend/services/__init__.py 已经将项目根加入 sys.path，
# 因此可以直接复用根目录下的 llm_client / skill_loader 等模块。
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import bunny_storage, gate_manager, material_context, session_store  # noqa: F401  触发 backend.services.__init__ 注入 sys.path

# ── 从项目根模块导入业务函数（共享同一份代码）─────────────────────────────
from llm_client import (  # type: ignore
    PRIMARY_CLIENT,
    TEXT_MODEL,
    TEXT_FALLBACK_MODEL,
    DIALOGUE_MODEL,
    call_skill,
    call_memorial_chat,
    call_freeform,
    call_structured,
    describe_image,
    transcribe_audio,
    build_scene_prompts,
    generate_image_tokenstar,
    generate_video_tokenstar_kling_omni_image,
)
from skill_loader import load_skill  # type: ignore
from core import storage as core_storage  # type: ignore

ROOT_DIR    = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR  = ROOT_DIR / "skills"
ASSET_DIR   = ROOT_DIR / "asset"
OUTPUTS_DIR = ROOT_DIR / "backend" / "outputs"
UPLOADS_DIR = OUTPUTS_DIR / "uploads"
FINAL_DIR   = OUTPUTS_DIR / "final_cuts"

for _d in (OUTPUTS_DIR, UPLOADS_DIR, FINAL_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── 【测试阶段临时限制】分镜数量上限 ──────────────────────────────────────
# 每次生成视频耗时较长（Kling 单条约 3~6 分钟），测试阶段先限制分镜数量，
# 避免一次跑太多耗费时间/额度。正式发布前把这个值改成 None（不限制）即可。
TESTING_MAX_SCENES: Optional[int] = 6


def indent_markdown_paragraphs(text: str, indent: str = "　　") -> str:
    """将 Markdown 文本中每个自然段首行前加上指定缩进。"""
    import re

    if not text:
        return text

    parts = re.split(r'(\n\s*\n)', text)
    output = []
    for part in parts:
        if re.fullmatch(r'\n\s*\n', part):
            output.append(part)
            continue

        stripped = part.lstrip('\n')
        if not stripped.strip():
            output.append(part)
            continue

        first_line = stripped.splitlines()[0]
        if re.match(r'^(#{1,6}\s|>\s|[-*+]\s|\d+\.\s|```|\s*$)', first_line):
            output.append(part)
            continue

        output.append(re.sub(r'^([ \t]*)(?=\S)', r'\1' + indent, part, count=1, flags=re.MULTILINE))

    return ''.join(output)


def normalize_bio_asset(asset: dict) -> dict:
    """Normalize asset metadata for biography payload."""
    return {
        "asset_id": asset.get("asset_id") or asset.get("saved_as") or asset.get("filename") or "",
        "filename": asset.get("filename") or asset.get("saved_as") or "",
        "kind": asset.get("kind") or (asset.get("mime", "").split("/")[0] if asset.get("mime") else ""),
        "description": asset.get("description") or asset.get("summary") or "",
        "summary": asset.get("summary") or asset.get("description") or "",
        "tags": asset.get("tags", []),
        "url": asset.get("url") or asset.get("asset_url") or "",
        "period": asset.get("period") or asset.get("time_period") or "",
        "usable_for": asset.get("usable_for", []),
    }


def get_biography_assets(s: dict) -> List[dict]:
    """Collect asset metadata from session and memorial storage for biography generation."""
    assets: List[dict] = []
    seen: set[str] = set()
    form = s.get("form_data", {}) or {}
    # 新版传记页面会显式传入资料库勾选的照片；空列表代表本次不使用图片。
    # 字段缺省时保持旧流程兼容：仍自动带入所有已有素材。
    has_selection = "selected_asset_ids" in form
    selected_ids = {
        str(asset_id) for asset_id in (form.get("selected_asset_ids") or [])
        if asset_id
    }

    def include(asset: dict) -> bool:
        asset_id = str(asset.get("asset_id") or asset.get("saved_as") or asset.get("filename") or "")
        return not has_selection or asset_id in selected_ids

    for asset in s.get("assets", []) or []:
        norm = normalize_bio_asset(asset)
        if include(asset) and norm["url"] and norm["asset_id"] not in seen:
            assets.append(norm)
            seen.add(norm["asset_id"])

    user_id = form.get("user_id")
    memorial_id = form.get("memorial_id")
    if user_id and memorial_id:
        try:
            stored_assets = core_storage.list_assets(user_id, memorial_id)
            for asset in stored_assets:
                norm = normalize_bio_asset(asset)
                if include(asset) and norm["url"] and norm["asset_id"] not in seen:
                    assets.append(norm)
                    seen.add(norm["asset_id"])
        except Exception:
            pass

    return assets


# ── 测试数据 ───────────────────────────────────────────────────────────────
TEST_DATA: Dict[str, Any] = {
    "deceased_name": "陈文斌",
    "deceased_gender": "男",
    "birth_date": "1948年10月15日",
    "death_date": "2025年4月8日",
    "occupation": "退休工程师（原上海机床厂车间主任、某机械制造公司技术部经理）",
    "ceremony_date": "2025年4月15日",
    "ceremony_venue": "上海市黄浦区殡仪馆思源厅",
    "total_duration_sec": 300,
    "speaker_name": "陈明",
    "speaker_relation": "儿子",
    "speaker_style": "深情克制，儒雅温暖，感恩回望，不过度煽情",
    "style_preference": "warm_nostalgia",
    "family_memory_text": (
        "父亲是一个话不多但做什么都认真到底的人。青年时戴黑框眼镜，穿蓝色中山装，"
        "眼神里总有一种让人安心的笃定。退休后每天清晨和母亲去公园打太极拳，风雨无阻，"
        "说「动起来才有精气神」。他爱好书法多年，书法作品多次在社区展览中获奖；"
        "还坚持集邮，把每一枚邮票都仔细收进册子，说「小小方寸，装着大世界」。"
        "2020年起成为社区志愿者，帮邻里修电器、疏通水管、调解纠纷，从不推辞，"
        "说「退休了更要做点有用的事」。\n\n"
        "事迹一：1968年响应上山下乡号召赴安徽阜阳插队，十年知青岁月中学会种地、木工、电工，"
        "1978年高考恢复以优异成绩考上上海工业大学机械工程系，是全公社唯一考上大学的知青。\n"
        "事迹二：1990年担任上海机床厂车间主任，带领团队攻克多项技术难关，"
        "1985年起连续多年被评为厂级先进工作者，同事们都叫他「陈工」。\n"
        "事迹三：1975年在安徽阜阳与母亲李秀英举办简朴婚礼，相伴五十年从未分离，"
        "2025年迎来金婚纪念。\n"
        "事迹四：孙女陈雨桐高考前，父亲每天为她备好夜宵放在书桌旁，从不打扰，"
        "只在门缝里静静看一眼，说「孩子努力，我们陪着就够了」。"
    ),
    "last_wishes": "希望家人身体健康、和和睦睦，盼孙女陈雨桐学业顺遂。",
}


# ── Pipeline 步骤映射（与根目录 pipeline_runner.py 对齐）────────────────────
MV_FILES = {
    "MV01": "MV01-interview.md",
    "MV02": "MV02-validation.md",
    "MV03": "MV04-bible-lock.md",
    "MV04": "MV03-storyboard.md",
    "MV05": "MV05-avatar-render.md",
    "MV06": "MV06-final-cut.md",
}


def run_pipeline_step(sid: str, mv_id: str) -> Dict[str, Any]:
    """运行单个 pipeline 步骤（轻量版，供 FastAPI 调用）"""
    import time as _t
    s = session_store.require(sid)
    gate = s["gate"]

    if mv_id not in MV_FILES:
        return {"error": True, "message": f"unknown step: {mv_id}"}

    if not gate_manager.can_run(gate, mv_id):
        return {"error": True, "message": f"gate not open: {mv_id} 需要前置步骤完成"}

    gate_manager.set_running(gate, mv_id)
    s["pipeline_state"][mv_id] = {"status": "running", "duration_sec": None, "error": None}
    t0 = _t.time()

    try:
        skill_path = SKILLS_DIR / MV_FILES[mv_id]
        system_prompt = load_skill(str(skill_path))

        # 所有 MV 步骤共享同一个人物上下文。它把资料库、Agent 对话、
        # 当前访谈和结构化素材清单真正接入视频生成链路。
        memorial_ctx = material_context.build_memorial_context(s)
        payload: Dict[str, Any] = {
            "form_data": s["form_data"],
            "mv_outputs": s["mv_outputs"],
            "chat_history": memorial_ctx.get("session_chat_history", []),
            "agent_conversation_history": memorial_ctx.get("agent_conversation_history", []),
            "assets": memorial_ctx.get("assets", []),
            "memorial_context": memorial_ctx,
        }
        result = call_skill(mv_id, system_prompt, payload)
        elapsed = round(_t.time() - t0, 2)

        if isinstance(result, dict) and result.get("error"):
            gate_manager.reject(gate, mv_id, {})
            s["pipeline_state"][mv_id] = {
                "status": "error", "duration_sec": elapsed, "error": result.get("message", "unknown")
            }
            return {"error": True, "step": mv_id, "message": result.get("message")}

        # 【测试阶段临时限制】MV04 分镜生成后，把分镜数量截断到 TESTING_MAX_SCENES，
        # 避免测试时一次生成太多图片/视频。正式发布前把 TESTING_MAX_SCENES 改为 None 即可恢复。
        if mv_id == "MV04" and TESTING_MAX_SCENES is not None and isinstance(result, dict):
            sc = result.get("scenes")
            if isinstance(sc, list) and len(sc) > TESTING_MAX_SCENES:
                result["scenes"] = sc[:TESTING_MAX_SCENES]
            elif isinstance(sc, dict) and len(sc) > TESTING_MAX_SCENES:
                keys = sorted(sc.keys())[:TESTING_MAX_SCENES]
                result["scenes"] = {k: sc[k] for k in keys}
            sb = result.get("storyboard")
            if isinstance(sb, list) and len(sb) > TESTING_MAX_SCENES:
                result["storyboard"] = sb[:TESTING_MAX_SCENES]

        if mv_id == "MV04" and isinstance(result, dict):
            result = material_context.attach_assets_to_storyboard(
                result,
                memorial_ctx,
            )

        s["mv_outputs"][mv_id] = result
        gate_manager.approve(gate, mv_id)
        s["pipeline_state"][mv_id] = {"status": "approved", "duration_sec": elapsed, "error": None}

        # 持久化到 outputs/
        try:
            import json as _json
            out_path = OUTPUTS_DIR / f"{sid}_{mv_id.lower()}.json"
            out_path.write_text(_json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

        return {"ok": True, "step": mv_id, "duration_sec": elapsed, "result": result}

    except Exception as exc:
        elapsed = round(_t.time() - t0, 2)
        gate_manager.reject(gate, mv_id, {})
        s["pipeline_state"][mv_id] = {"status": "error", "duration_sec": elapsed, "error": str(exc)}
        return {"error": True, "step": mv_id, "message": str(exc)}


# ── 深度搜索（302.ai perplexity/sonar-pro → Tavily → 知识库）────────────────
_SEARCH_MODELS = ["perplexity/sonar-pro", "perplexity/sonar", "gpt-4o-search-preview",
                  "web-search-pro", "moonshot-v1-128k-search"]

_DEEP_SEARCH_SYSTEM = """你是念念追思影像制作助手，具备联网实时搜索能力。
用户想了解某位人物的生平资料，以便制作追思影像。请联网搜索后，**严格按以下 JSON 格式输出，不加任何解释或 Markdown**：

{
  "organized": "用温暖自然的中文整理，包含：\\n### 一、基本信息\\n全名、生卒年月、主要职业/身份、籍贯。\\n\\n### 二、人生经历亮点\\n按时间顺序列出3-6个重要节点。\\n\\n### 三、性格与精神遗产\\n性格、价值观、主要贡献（100字以内）。\\n\\n### 四、适合追思影像的素材线索\\n2-4个最具画面感的场景或情感记忆点。",
  "name": "姓名",
  "gender": "男 或 女 或 不便告知",
  "birth_date": "XXXX年X月X日 或 XXXX年 或 空",
  "death_date": "XXXX年X月X日 或 XXXX年 或 空（健在则填空）",
  "occupation": "主要职业或身份",
  "locations": ["出生地或主要居住地，最多3个"],
  "personality_keywords": ["性格关键词，最多5个"],
  "quotes": ["代表性金句，原文，最多5条；没有则空数组"],
  "objects": ["代表性物件，最多5个；没有则空数组"],
  "core_memories": [
    {"title": "记忆标题（10字以内）", "content": "具体描述（60-100字）"}
  ]
}

信息不足的字段：字符串填空字符串，数组填空数组。若无公开资料请在 organized 里如实说明。"""

_FILL_SYSTEM = """根据已整理的人物资料，提取以下字段，严格输出 JSON，不加任何解释：
{
  "deceased_name": "姓名",
  "deceased_gender": "男 或 女 或 不便告知",
  "birth_date": "XXXX年X月X日 或 XXXX年 或 空",
  "death_date": "XXXX年X月X日 或 XXXX年 或 空（健在则填空）",
  "occupation": "主要职业或身份",
  "locations": ["出生地或主要居住地，数组，最多3个"],
  "personality_keywords": ["性格关键词，数组，最多5个"],
  "quotes": ["代表性金句或名言，原文，数组，最多5条；没有则空数组"],
  "objects": ["代表性物件或标志性事物，数组，最多5个；没有则空数组"],
  "core_memories": [
    {"title": "记忆标题", "content": "具体描述，80-150字"}
  ],
  "family_memory_text": "以家属或后辈视角写的温暖回忆叙述，200-350字"
}
信息不足的字段：字符串填空字符串，数组填空数组。"""


def _parse_deep_search_json(raw: str) -> Dict[str, Any]:
    """
    解析 deep_search 返回的 JSON（可能包裹在 ```json``` 代码块里）。
    优先提取完整 JSON 对象；若解析失败则把整段文字当 organized 字段返回。
    """
    import json as _j, re as _r
    text = raw.strip()
    # 去掉可能的代码块包裹
    m = _r.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, _r.S)
    if m:
        text = m.group(1)
    else:
        # 取第一个 { 到最后一个 }
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e > s:
            text = text[s:e + 1]
    try:
        data = _j.loads(text)
        if isinstance(data, dict) and data.get("organized"):
            return data
    except Exception:
        pass
    # 解析失败：整段文字当叙述文本
    return {"organized": raw.strip()}


def deep_search(query: str, extra: str = "") -> Dict[str, Any]:
    """
    优先 DashScope qwen-max/qwen-plus（enable_search 真实联网），
    失败则尝试 302.ai 搜索模型，最终降级到 302.ai 知识库。
    返回结构：{"organized": "...", "name": "...", "quotes": [...], "core_memories": [...], ...}
    """
    import os as _os
    try:
        research_system = load_skill(str(SKILLS_DIR / "BIO00-public-figure-research.md"))
    except Exception:
        research_system = _DEEP_SEARCH_SYSTEM
    user_msg = f"请帮我搜索并整理关于以下人物的生平资料：{query}"
    if extra.strip():
        user_msg += f"\n\n补充背景：{extra.strip()}"

    def _try_parse(content: str, model: str, fallback: bool) -> Dict[str, Any]:
        parsed = _parse_deep_search_json(content)
        parsed["model"] = model
        parsed["fallback"] = fallback
        return parsed

    # ── 1) 首选：DashScope（enable_search 真实联网）──
    ds_key = _os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if ds_key:
        try:
            from openai import OpenAI as _OpenAI
            region = _os.environ.get("DASHSCOPE_REGION", "").strip().lower()
            ds_base = (
                "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
                if region == "intl"
                else "https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            _ds = _OpenAI(api_key=ds_key, base_url=ds_base)
            for ds_model in ["qwen-max", "qwen-plus"]:
                try:
                    resp = _ds.chat.completions.create(
                        model=ds_model,
                        messages=[
                            {"role": "system", "content": research_system},
                            {"role": "user",   "content": user_msg},
                        ],
                        extra_body={"enable_search": True},
                        temperature=0.4,
                        max_tokens=4500,
                    )
                    content = (resp.choices[0].message.content or "").strip()
                    if content:
                        return _try_parse(content, f"{ds_model}（联网）", False)
                except Exception as _e:
                    print(f"[deep_search] DashScope {ds_model} failed: {_e}")
        except Exception as e:
            print(f"[deep_search] DashScope init failed: {e}")
    else:
        print("[deep_search] DASHSCOPE_API_KEY not set, skipping")

    # ── 2) 次选：302.ai 搜索模型系列 ──
    for model in _SEARCH_MODELS:
        try:
            resp = PRIMARY_CLIENT.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": research_system},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.4,
                max_tokens=4500,
            )
            content = (resp.choices[0].message.content or "").strip()
            if content:
                return _try_parse(content, model, False)
        except Exception:
            continue

    # ── 3) 降级：302.ai 知识库 ──
    kb_system = research_system + (
        "\n\n当前无法联网。请只依据已有知识作答，并在 organized 和 family_memory_text 中"
        "明确提示信息可能有更新，不能声称已经检索或核验来源。"
    )
    for m in [TEXT_MODEL, TEXT_FALLBACK_MODEL]:
        try:
            resp = PRIMARY_CLIENT.chat.completions.create(
                model=m,
                messages=[
                    {"role": "system", "content": kb_system},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.5,
                max_tokens=4500,
            )
            content = (resp.choices[0].message.content or "").strip()
            if content:
                return _try_parse(content, f"{m}（知识库）", True)
        except Exception:
            continue

    return {"organized": "抱歉，AI 服务暂时不可用，请稍后重试。", "model": "(失败)", "fallback": True}


def deep_search_extract_fields(organized: str, query: str) -> Dict[str, Any]:
    """
    兼容旧调用：deep_search 现在已经一次性返回结构化字段，
    此函数仅作为保留接口，直接返回空（字段已在 deep_search 结果里）。
    """
    return {}



# ── 念念 AI 对话（intake step3）────────────────────────────────────────────
_MEMORIAL_SYSTEM = (
    "你是「念念 AI」，一位温柔体贴的追思影像制作助手，帮助家属把对亲人的记忆整理成珍贵的追思影像。"
    "说话像温暖的长者朋友，用口语化自然流畅的中文，语气轻柔有耐心。"
    "每次回复 120-200 字，用自然段落，可用换行分段。"
    "第一次回复：先温暖开场感谢家属分享，然后自然总结已了解的信息（约 40 字，不要用字段名称），"
    "温柔指出 1-2 个可以补充的地方，用一句鼓励的话结尾。"
    "后续回复：先肯定补充的信息，信息充分时主动说可以开始制作了。"
    "绝对不要输出 JSON、技术参数、星号格式。"
)


def memorial_greeting(form_data: Dict[str, Any]) -> str:
    """生成念念 AI 开场白"""
    summary = _form_summary_for_ai(form_data)
    msgs = [{"role": "user", "content": f"以下是家属填写的信息，请你温暖开场：\n{summary}"}]
    return call_memorial_chat(_MEMORIAL_SYSTEM, msgs)


def memorial_reply(form_data: Dict[str, Any], history: List[Dict[str, str]]) -> str:
    """念念 AI 多轮回复"""
    summary = _form_summary_for_ai(form_data)
    seeded = [{"role": "user", "content": f"家属背景信息：\n{summary}"}] + history
    return call_memorial_chat(_MEMORIAL_SYSTEM, seeded)


# ── 数字人对话（独立于追思影像建档流程）────────────────────────────────────
# 用户上传聊天记录 → 风格分析 → 人设融合 → 与"逝者"对话
import csv as _csv
import io as _io
import json as _json2
import re as _re2


def parse_chat_file(file_bytes: bytes, filename: str, target: str) -> List[Dict[str, Any]]:
    """解析微信聊天记录（CSV/JSON/TXT）→ 消息列表"""
    messages: List[Dict[str, Any]] = []
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    target = (target or "").strip()

    if ext == "csv":
        text = file_bytes.decode("utf-8-sig", errors="replace")
        reader = _csv.DictReader(_io.StringIO(text))
        for row in reader:
            sender    = row.get("StrTalker") or row.get("sender") or row.get("NickName", "")
            is_sender = str(row.get("IsSender", "0"))
            msg_type  = str(row.get("Type", "1"))
            content   = row.get("StrContent") or row.get("content", "")
            if is_sender == "0" and msg_type == "1" and (not target or target in sender) and content.strip():
                messages.append({"sender": sender, "content": content.strip()})
    elif ext == "json":
        try:
            data = _json2.loads(file_bytes.decode("utf-8", errors="replace"))
        except Exception:
            data = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = (data.get("messages") or data.get("msg") or
                     data.get("records") or data.get("data") or [])
            if not items:
                for v in data.values():
                    if isinstance(v, list) and v:
                        items = v
                        break
        else:
            items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            sender  = (item.get("sender") or item.get("from") or item.get("NickName")
                       or item.get("talker") or item.get("StrTalker") or "")
            content = (item.get("content") or item.get("text") or item.get("StrContent")
                       or item.get("msg") or "")
            is_sender = str(item.get("IsSender", item.get("isSender", "")))
            msg_type  = str(item.get("Type", item.get("type", "1")))
            if is_sender == "1":
                continue
            if is_sender == "0" and msg_type not in ("1", ""):
                continue
            content = str(content).strip()
            if not content:
                continue
            if not target or target in sender:
                messages.append({"sender": sender, "content": content})
    elif ext == "txt":
        text = file_bytes.decode("utf-8", errors="replace")
        pattern = _re2.compile(
            r'(?:\[([^\]]+)\]\s+)?([^\n:：\(]+)[：:\(]\s*([^\n]+(?:\n(?!\[|\d{4})[^\n]+)*)',
            _re2.MULTILINE,
        )
        for m in pattern.finditer(text):
            sender  = m.group(2).strip()
            content = m.group(3).strip()
            if (not target or target in sender) and content:
                messages.append({"sender": sender, "content": content})
    return messages


def analyze_chat_style(messages: List[Dict[str, Any]], target_name: str, role_desc: str = "") -> Dict[str, Any]:
    """调用 WECHAT01 skill 分析风格"""
    skill_path = SKILLS_DIR / "WECHAT01-style-analysis.md"
    if not skill_path.exists():
        return {"error": True, "message": "WECHAT01 skill 文件缺失"}
    sample = messages[-300:] if len(messages) > 300 else messages
    sample_text = "\n".join(m["content"] for m in sample)
    payload: Dict[str, Any] = {
        "target_name": target_name or "目标人物",
        "messages": sample_text,
        "message_count": len(messages),
    }
    if role_desc.strip():
        payload["role_description"] = role_desc.strip()
    prompt = load_skill(str(skill_path))
    return call_skill("WECHAT01", prompt, payload)


def merge_persona(dna: Dict[str, Any], current_override: str, new_input: str) -> str:
    """智能融合人设描述（沿用 Streamlit 端实现）"""
    dna_summary = (
        f"语气基调: {dna.get('tone', '')}, "
        f"常用口头禅: {'、'.join(dna.get('speech_patterns', [])[:5])}, "
        f"常聊话题: {'、'.join(dna.get('typical_topics', [])[:3])}, "
        f"幽默程度: {dna.get('humor_level', 3)}/5, "
        f"回应风格: {dna.get('response_style', '')}"
    )
    merge_prompt = (
        f"你是一个角色人设管理助手。用户正在为数字人动态调整人设描述。\n\n"
        f"【已有角色 DNA 摘要】\n{dna_summary}\n\n"
        f"【当前角色背景描述】\n{current_override if current_override.strip() else '（暂无）'}\n\n"
        f"【用户新增/修改内容】\n{new_input}\n\n"
        f"请智能融合：保留有用旧设定，以新内容优先，去除矛盾重复，"
        f"用自然流畅中文描述，不超过250字。"
        f"直接返回融合后文本，不要任何解释或前缀。"
    )
    try:
        result = call_memorial_chat(
            system_prompt="你是角色人设管理助手，只返回融合结果文本，不解释。",
            messages=[{"role": "user", "content": merge_prompt}],
            model=DIALOGUE_MODEL,
        )
        return (result or "").strip()
    except Exception:
        return (current_override + "\n\n[新增] " + new_input).strip()


def build_persona_system_prompt(dna: Dict[str, Any], name: str, extra_desc: str = "") -> str:
    speech_patterns = "、".join(dna.get("speech_patterns", [])[:10])
    signatures = "\n".join(f"  - {p}" for p in dna.get("signature_phrases", []))
    topics    = "、".join(dna.get("typical_topics", [])[:5])
    emo_words = "、".join(dna.get("emotional_words", [])[:8])
    habits    = dna.get("special_habits", "")
    extra_section = f"\n【角色背景补充】\n{extra_desc}\n" if extra_desc.strip() else ""
    return (
        f"你现在扮演一个真实存在过的人：{name}。\n\n"
        f"你的任务是完全以 {name} 的口吻和风格与用户对话，让用户感受到 TA 仍然在陪伴着自己。"
        f"{extra_section}\n"
        f"【{name} 的语言风格特征】\n"
        f"- 常用词/口头禅：{speech_patterns}\n"
        f"- 句子长度风格：{dna.get('avg_sentence_length', '中等')}\n"
        f"- 情感基调：{dna.get('tone', '温和')}\n"
        f"- 幽默程度：{dna.get('humor_level', 3)}/5\n"
        f"- 常聊话题：{topics}\n"
        f"- 常用情感词：{emo_words}\n"
        f"- 特殊语言习惯：{habits}\n"
        f"- 标志性句式：\n{signatures}\n"
        f"- 回应风格：{dna.get('response_style', '自然随和')}\n\n"
        f"【角色扮演守则】\n"
        f"1. 始终保持角色，不要说「我是AI」或打破扮演\n"
        f"2. 回复长度符合 TA 原本的风格\n"
        f"3. 适当使用口头禅和标志性句式，但不要每句都重复\n"
        f"4. 语气温暖真实，像真正的对话而不是朗诵\n"
        f"5. 如果用户问到不知道的事，以 {name} 的性格自然回应\n"
        f"6. 每次回复后可自然地反问或延续话题\n"
        f"7. 不使用 Markdown 格式符号，保持口语化\n"
        f"8. 每次回复控制在1-4句话，除非用户要求详细"
    )


def dialogue_reply(dna: Dict[str, Any], name: str, override: str, history: List[Dict[str, str]]) -> str:
    """数字人对话回复"""
    sys_prompt = build_persona_system_prompt(dna, name or "TA", override or "")
    return call_memorial_chat(
        system_prompt=sys_prompt,
        messages=history[-20:],
        model=DIALOGUE_MODEL,
    )


def _form_summary_for_ai(form_data: Dict[str, Any]) -> str:
    name = form_data.get("deceased_name", "")
    rel  = form_data.get("speaker_relation", "")
    birth = form_data.get("birth_date", "")
    death = form_data.get("death_date", "")
    occ  = form_data.get("occupation", "")
    mem  = form_data.get("family_memory_text", "")
    wish = form_data.get("last_wishes", "")
    parts = []
    if name: parts.append(f"亲人姓名：{name}")
    if rel:  parts.append(f"发言人是逝者的{rel}")
    if birth:parts.append(f"出生：{birth}")
    if death:parts.append(f"逝世：{death}")
    elif birth: parts.append("目前在世")
    if occ:  parts.append(f"职业/身份：{occ}")
    if mem:  parts.append(f"家庭回忆：{mem[:300]}")
    if wish: parts.append(f"心愿/寄语：{wish[:150]}")
    return "\n".join(parts) if parts else "（家属尚未填写详细信息）"


# ── 影像预告（preview）：用大白话讲解流程 ──────────────────────────────────
_PREVIEW_SYS = (
    "你是一位亲切的追思影像讲解员，帮助家属提前了解即将制作的影片内容。"
    "请根据下面提供的逝者信息，用最通俗的大白话（就像面对面和家里老人讲话一样），"
    "把这部追思影像的大致流程讲清楚：先是什么，然后是什么，最后是什么。"
    "语气温柔、耐心，像邻居奶奶聊天一样自然。\n"
    "格式要求：\n"
    "- 用三段结构，每段 2-4 句话\n"
    "- 不要用专业词汇，不要说'分镜'、'AI生成'、'模型'这类词\n"
    "- 每段开头加上序号表情：①②③\n"
    "- 总长度控制在 150-220 字"
)


def memorial_preview(form_data: Dict[str, Any], mv01_result: Optional[Dict[str, Any]] = None) -> str:
    """根据表单 + MV01 输出生成大白话流程讲解"""
    import json as _json
    if mv01_result:
        info = _json.dumps(mv01_result, ensure_ascii=False, indent=2)
    else:
        info = _form_summary_for_ai(form_data)
    prompt = f"以下是逝者和家属的信息：\n\n{info}\n\n请用大白话帮家属讲讲这部影片的流程。"
    try:
        return call_memorial_chat(_PREVIEW_SYS, [{"role": "user", "content": prompt}])
    except Exception as e:
        return f"① 我们会先用您填写的内容整理出一份完整的故事大纲。\n② 接着会确定影像的整体氛围、主角的样子，让画面更贴近 TA。\n③ 最后会一帧一帧把回忆做成可以播放的影片。\n\n（系统提示：预览生成遇到问题：{e}）"


# ── MV 步骤后大白话总结 ───────────────────────────────────────────────────
_MV01_SUMMARY_SYS = (
    "你是念念追思影像制作助手，帮家属用最温柔口语化的中文描述影像制作进展。"
    "收到 JSON 数据后，用 80-120 字的自然语言告诉家属：我们了解了哪些信息，"
    "影像会呈现什么样的感觉。不要出现任何技术词汇、字段名、JSON。语气温暖贴心。"
    "只输出一段话，不要分点、不要标题。"
)
_MV03_SUMMARY_SYS = (
    "你是念念追思影像制作助手。根据影像三要素 JSON，用最温柔自然的中文，"
    "用 80-120 字告诉家属：我们为这部影像确定了什么样的基调、主角形象和画面氛围。"
    "不要出现任何 JSON、字段名或技术词汇。语气温暖，像在讲述一个美好的计划。"
    "必须使用 JSON 中真实的人物姓名，绝对不得使用任何无关的示例名称。只输出一段话，不要分点。"
)


def _safe_mv_summary(sys_prompt: str, payload: Dict[str, Any], fallback: str) -> str:
    import json as _json
    try:
        return call_freeform(sys_prompt, _json.dumps(payload, ensure_ascii=False))
    except Exception:
        return fallback


def run_pipeline_chain(sid: str) -> Dict[str, Any]:
    """串行执行 MV01 → MV02 → MV03，并附带两段大白话总结气泡。
    复刻 archive/streamlit/pages/pipeline.py 的 run_pipeline() 逻辑。"""
    s = session_store.require(sid)
    bubbles: List[Dict[str, str]] = []   # [{role:'ai', content}]
    errors: List[Dict[str, str]] = []

    # ── MV01（若已运行就直接读取）───────────────────────────────
    mv01_out = s["mv_outputs"].get("MV01")
    if not mv01_out:
        r = run_pipeline_step(sid, "MV01")
        if r.get("error"):
            errors.append({"step": "MV01", "message": r.get("message", "未知错误")})
            return {"ok": False, "bubbles": bubbles, "errors": errors,
                    "scenes": [], "mv03": {}}
        mv01_out = r["result"]

    # 气泡①：MV01 摘要
    bubbles.append({
        "role": "ai",
        "content": _safe_mv_summary(_MV01_SUMMARY_SYS, mv01_out,
                                    "我们已经把您讲述的内容整理好了，影像将围绕这些珍贵的记忆展开。"),
    })

    # ── MV02 静默运行 ────────────────────────────────────────
    if not s["mv_outputs"].get("MV02"):
        run_pipeline_step(sid, "MV02")

    # ── MV03 三要素锁定 ──────────────────────────────────────
    mv03_out = s["mv_outputs"].get("MV03")
    if not mv03_out:
        r = run_pipeline_step(sid, "MV03")
        if r.get("error"):
            errors.append({"step": "MV03", "message": r.get("message", "未知错误")})
            return {"ok": False, "bubbles": bubbles, "errors": errors,
                    "scenes": [], "mv03": {}}
        mv03_out = r["result"]

    # 气泡②：MV03 三要素总结（注入真实姓名防止 LLM 误用）
    summary_payload = dict(mv03_out) if isinstance(mv03_out, dict) else {"raw": mv03_out}
    summary_payload["_current_deceased_name"] = s["form_data"].get("deceased_name", "")
    bubbles.append({
        "role": "ai",
        "content": _safe_mv_summary(_MV03_SUMMARY_SYS, summary_payload,
                                    "影像的基调、主角形象和画面氛围都已确定，接下来就可以进入分镜制作。"),
    })

    # 收集分镜（若 MV03 输出包含）
    scenes: List[Dict[str, Any]] = []
    if isinstance(mv03_out, dict):
        sc = mv03_out.get("scenes")
        if isinstance(sc, list):
            scenes = [x for x in sc if isinstance(x, dict)]
        elif isinstance(sc, dict):
            scenes = [sc[k] for k in sorted(sc.keys()) if isinstance(sc[k], dict)]

    return {
        "ok": True,
        "bubbles":  bubbles,
        "errors":   errors,
        "scenes":   scenes,
        "mv03":     mv03_out,
    }


# ── 分镜场景：单镜图片/视频生成 ─────────────────────────────────────────
def _get_scenes_from_mv04(mv04_out: Any) -> List[Dict[str, Any]]:
    if not isinstance(mv04_out, dict):
        return []
    sc = mv04_out.get("scenes")
    if isinstance(sc, list):
        return [x for x in sc if isinstance(x, dict)]
    if isinstance(sc, dict):
        return [sc[k] for k in sorted(sc.keys()) if isinstance(sc[k], dict)]
    sb = mv04_out.get("storyboard")
    if isinstance(sb, list):
        return [x for x in sb if isinstance(x, dict)]
    return []


def _contains_chinese_text(value: Any) -> bool:
    """Return whether a value contains at least one CJK character."""
    import re

    return bool(re.search(r"[\u4e00-\u9fff]", str(value or "")))


def localize_scene_texts(sid: str) -> List[Dict[str, Any]]:
    """Translate legacy English scene display fields to Chinese once and cache them.

    Image/video prompts remain English for model quality. This function only changes
    user-facing fields such as description and narration in the persisted MV04 result.
    """
    session = session_store.require(sid)
    scenes = _get_scenes_from_mv04(session["mv_outputs"].get("MV04"))
    candidates: List[Dict[str, Any]] = []
    candidate_fields: Dict[int, set[str]] = {}
    for index, scene in enumerate(scenes):
        fields: Dict[str, str] = {}
        for key in ("description", "scene_desc", "visual", "narration", "voiceover", "subtitle"):
            value = scene.get(key)
            if isinstance(value, str) and value.strip() and not _contains_chinese_text(value):
                fields[key] = value.strip()
        if fields:
            candidates.append({"index": index, "fields": fields})
            candidate_fields[index] = set(fields)
    if not candidates:
        return scenes

    result = call_structured(
        "你是影视分镜本地化编辑。把输入 JSON 中每个 fields 的英文内容翻译为自然、简洁的简体中文。"
        "只翻译用户界面展示文案，不要改写事实，不要添加解释。严格返回 JSON："
        '{"items":[{"index":0,"fields":{"description":"中文"}}]}。',
        json.dumps({"items": candidates}, ensure_ascii=False),
    )
    translated = result.get("items", []) if isinstance(result, dict) else []
    if not isinstance(translated, list):
        return scenes
    for item in translated:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        fields = item.get("fields")
        if not isinstance(index, int) or index not in candidate_fields or not isinstance(fields, dict):
            continue
        for key, value in fields.items():
            if key in candidate_fields[index] and isinstance(value, str) and value.strip():
                scenes[index][key] = value.strip()
    return scenes


def get_characters(sid: str) -> Dict[str, Any]:
    """返回角色档案：主角（逝者）+ 配角列表（来自 MV03 character_bible）"""
    s = session_store.require(sid)
    form = s.get("form_data", {})
    mv03 = s["mv_outputs"].get("MV03") or {}
    bible = mv03.get("character_bible", {}) if isinstance(mv03, dict) else {}
    dna   = bible.get("character_dna", {}) if isinstance(bible, dict) else {}

    main_name = (
        bible.get("display_name")
        or form.get("deceased_name")
        or bible.get("character_id")
        or "主角"
    )
    main_desc_parts: List[str] = []
    if dna.get("facial_features"):  main_desc_parts.append(f"面部：{dna['facial_features']}")
    if dna.get("body_features"):    main_desc_parts.append(f"体型：{dna['body_features']}")
    if dna.get("clothing_style"):   main_desc_parts.append(f"服装：{dna['clothing_style']}")
    if dna.get("mannerisms"):       main_desc_parts.append(f"神态：{dna['mannerisms']}")
    if not main_desc_parts and form.get("occupation"):
        main_desc_parts.append(form["occupation"])

    main_role = {
        "name": main_name,
        "role_label": f"主角 · 逝者（{form.get('speaker_relation','至亲')}）" if form.get("speaker_relation") else "主角 · 逝者",
        "description": "；".join(main_desc_parts) or "（暂无详细外貌描述）",
        "photo_url": form.get("main_reference_photo_url") or "",
        "reference_asset_id": form.get("main_reference_asset_id") or "",
    }

    # 配角：优先 MV03 supporting_cast，其次 cast_roles
    cast_raw = []
    if isinstance(mv03, dict):
        cast_raw = mv03.get("supporting_cast") or mv03.get("cast_roles") or []
    supporting: List[Dict[str, Any]] = []
    if isinstance(cast_raw, list):
        for c in cast_raw:
            if not isinstance(c, dict): continue
            supporting.append({
                "name":        c.get("name") or c.get("display_name") or "未命名",
                "role_label":  c.get("role_label") or c.get("relation") or "配角",
                "description": c.get("description") or c.get("desc") or "",
                "photo_url":   c.get("photo_url") or "",
            })

    return {"main": main_role, "supporting": supporting}


def _public_scene_frame_url(
    sid: str,
    scene_idx: int,
    image_b64: str,
    public_base_url: str = "",
) -> str:
    """Persist a generated frame and return a safe public HTTPS URL when available."""
    import base64 as _base64
    import hashlib as _hashlib
    import ipaddress as _ipaddress
    from urllib.parse import quote as _quote, urlparse as _urlparse

    base = (public_base_url or "").strip().rstrip("/")
    try:
        parsed = _urlparse(base)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host or host == "localhost" or host.endswith(".local"):
            return ""
        try:
            ip = _ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return ""
        except ValueError:
            pass

        image_bytes = _base64.b64decode(image_b64, validate=True)
        digest = _hashlib.sha256(image_bytes).hexdigest()[:16]
        safe_sid = "".join(ch for ch in sid if ch.isalnum())[:40] or "session"
        filename = f"{safe_sid}_scene_{scene_idx:03d}_{digest}.png"
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        frame_path = UPLOADS_DIR / filename
        if not frame_path.exists():
            frame_path.write_bytes(image_bytes)
        return f"{base}/api/assets/file/{_quote(filename)}"
    except Exception as exc:
        print(f"[scene-frame] public frame cache failed: {exc}")
        return ""


def gen_scene_image(
    sid: str,
    scene_idx: int,
    ref_b64: str = "",
    public_base_url: str = "",
) -> Dict[str, Any]:
    """为单个分镜生成图片。首帧图统一使用 TokenStar gpt-image-2。"""
    s = session_store.require(sid)
    mv04 = s["mv_outputs"].get("MV04")
    mv03 = s["mv_outputs"].get("MV03")
    scenes = _get_scenes_from_mv04(mv04)
    if scene_idx < 0 or scene_idx >= len(scenes):
        return {"error": True, "message": f"无效的分镜索引 {scene_idx}"}
    scene = scenes[scene_idx]
    # 重新生成时清除旧的画面和视频缓存，避免前端仍显示旧图而误以为按钮无效。
    scene.pop("_image_data_url", None)
    scene.pop("_image_public_url", None)
    scene.pop("_video_url", None)

    # 真实素材只作为图生图的参考底图，不再直接把原始照片当成分镜画面使用。
    # 前端每个分镜都可以独立挑选参考图（ref_b64）；若用户未选择，则在分镜绑定的
    # source_asset_ids 中取第一张图片作为默认参考，仍然会调用生图模型重新生成画面。
    form = s.get("form_data", {}) or {}
    user_id = form.get("user_id", "")
    memorial_id = form.get("memorial_id", "")
    source_asset_id = ""
    reference_b64 = ref_b64 or ""

    if not reference_b64:
        source_ids = scene.get("source_asset_ids") or []
        if user_id and memorial_id and source_ids:
            try:
                import base64 as _base64

                stored_assets = core_storage.list_assets(user_id, memorial_id)
                by_id = {
                    asset.get("asset_id"): asset
                    for asset in stored_assets
                    if asset.get("kind") == "image"
                }
                source_asset = next(
                    (by_id.get(asset_id) for asset_id in source_ids if by_id.get(asset_id)),
                    None,
                )
                if source_asset:
                    source_path = (
                        core_storage.memorial_dir(user_id, memorial_id)
                        / "assets"
                        / source_asset.get("stored_name", "")
                    )
                    reference_b64 = _base64.b64encode(source_path.read_bytes()).decode("ascii")
                    source_asset_id = source_asset.get("asset_id") or ""
            except Exception as exc:
                print(f"[scene-image] load real asset as reference failed: {exc}")

    # 构造图片 prompt：优先 build_scene_prompts，失败则用 description 兜底
    try:
        prompts = build_scene_prompts(scene, character_bible=mv03 if isinstance(mv03, dict) else None)
        image_prompt = prompts.get("image_prompt") or scene.get("prompt_start") or scene.get("description") or ""
    except Exception:
        image_prompt = scene.get("prompt_start") or scene.get("description") or scene.get("visual") or str(scene)

    if not image_prompt:
        return {"error": True, "message": "无法构造图片 prompt"}

    b64, err = generate_image_tokenstar(image_prompt, reference_b64=reference_b64 or None)
    if not b64:
        return {"error": True, "message": err or "图片生成失败"}

    data_url = f"data:image/png;base64,{b64}"
    public_url = _public_scene_frame_url(
        sid,
        scene_idx,
        b64,
        public_base_url=public_base_url,
    )
    # 缓存到 scene
    scene["_image_data_url"] = data_url
    scene["_image_prompt"]   = image_prompt
    scene["_image_source_asset_id"] = source_asset_id
    scene["_image_reused"] = False
    if public_url:
        scene["_image_public_url"] = public_url
    return {
        "url": data_url,
        "public_url": public_url,
        "source_asset_id": source_asset_id,
        "reused": False,
    }


def gen_scene_video(
    sid: str,
    scene_idx: int,
    image_url: str = "",
    public_base_url: str = "",
) -> Dict[str, Any]:
    """为单个分镜生成视频。image_url 可为 data URL 或 https URL。"""
    s = session_store.require(sid)
    mv04 = s["mv_outputs"].get("MV04")
    mv03 = s["mv_outputs"].get("MV03")
    scenes = _get_scenes_from_mv04(mv04)
    if scene_idx < 0 or scene_idx >= len(scenes):
        return {"error": True, "message": f"无效的分镜索引 {scene_idx}"}
    scene = scenes[scene_idx]

    # 生产环境优先使用当前服务托管的稳定 HTTPS 首帧，避免依赖临时图床。
    # 对于升级前已生成的 base64 首帧，在首次生成视频时补写公开缓存。
    public_image_url = scene.get("_image_public_url", "")
    raw_image_url = image_url or scene.get("_image_data_url", "")
    if not public_image_url and isinstance(raw_image_url, str) and raw_image_url.startswith("data:"):
        try:
            image_b64 = raw_image_url.split(",", 1)[1]
            public_image_url = _public_scene_frame_url(
                sid,
                scene_idx,
                image_b64,
                public_base_url=public_base_url,
            )
            if public_image_url:
                scene["_image_public_url"] = public_image_url
        except Exception:
            public_image_url = ""
    # Omni 只接受公网 HTTPS 图片。若当前服务未配置 PUBLIC_BASE_URL，
    # _public_scene_frame_url 可能只是 http://localhost/...；此时保留 data URL，
    # 让 Kling Omni 调用层上传到临时公网图床，而不是把不可访问的本地地址交给 TokenStar。
    image_url = public_image_url if str(public_image_url).startswith("https://") else raw_image_url
    if not image_url:
        return {"error": True, "message": "请先生成首帧图片"}

    # Bunny 是制作台首选的公网图片中转：把 AI 首帧稳定地存到 Bunny Pull Zone，
    # 再将 CDN HTTPS URL 交给 TokenStar。未配置 Bunny 或上传失败时保留 data URL，
    # 由下层兼容图床处理，但会在诊断信息中明确显示实际通道。
    bunny_reference_url = ""
    bunny_storage_key = ""
    if bunny_storage.is_configured() and isinstance(raw_image_url, str) and raw_image_url.startswith("data:"):
        try:
            import base64 as _base64

            header, encoded = raw_image_url.split(",", 1)
            mime = header.split(":", 1)[1].split(";", 1)[0]
            extension = mime.split("/")[-1] if "/" in mime else "png"
            bunny_result = bunny_storage.upload_bytes(
                _base64.b64decode(encoded),
                bunny_storage.scene_frame_path(sid, scene_idx, extension),
                mime,
            )
            bunny_reference_url = str(bunny_result["cdn_url"])
            bunny_storage_key = str(bunny_result["storage_key"])
            image_url = bunny_reference_url
            scene["_image_public_url"] = bunny_reference_url
            scene["_image_bunny_storage_key"] = bunny_storage_key
        except Exception as exc:
            print(f"[scene-video] Bunny 首帧中转失败，回退兼容图床：{exc}")

    # 视频 prompt
    try:
        prompts = build_scene_prompts(scene, character_bible=mv03 if isinstance(mv03, dict) else None)
        video_prompt = prompts.get("video_prompt") or scene.get("prompt_video") or scene.get("description") or ""
    except Exception:
        video_prompt = scene.get("prompt_video") or scene.get("description") or ""

    if not video_prompt:
        video_prompt = "电影感长镜头，温暖怀旧的追思氛围，缓慢推进，自然光。"

    debug: Dict[str, Any] = {
        "provider": "TokenStar Kling v3 Omni · 图片参考模式",
        "prompt": video_prompt,
        "reference_image": (
            image_url if str(image_url).startswith("https://")
            else "data URL（将自动上传为临时公网 HTTPS 图片）"
        ),
        "reference_transport": "bunny_cdn" if bunny_reference_url else "provider_fallback_upload",
        "bunny_storage_key": bunny_storage_key,
        "public_base_url_configured": bool(os.environ.get("PUBLIC_BASE_URL", "").strip()),
    }

    # 统一调用 TokenStar Kling v3 Omni「图片参考模式」（旧版 Action API），
    # 不回退到 302.ai 或旧可灵官方接口。分镜首帧图作为唯一参考图传入。
    res = generate_video_tokenstar_kling_omni_image(
        prompt=video_prompt,
        image_urls=[image_url],
        duration=5,
        poll=True,
        # 最多等待 5 分钟；超过该窗口明确返回失败状态，避免
        # 前端永久停留在“生成中”。供应商任务仍可用 task_id 后续查询。
        max_wait=300,
    )
    debug["task_id"] = res.get("task_id", "")
    debug["source"] = res.get("source", "")
    if res.get("error"):
        debug["error"] = res.get("error")
        scene["_video_debug"] = debug
        return {"error": True, "message": res.get("error"), "debug": debug}
    url = res.get("url")
    if not url:
        debug["error"] = f"视频未返回 URL：{res}"
        scene["_video_debug"] = debug
        return {"error": True, "message": debug["error"], "debug": debug}
    scene["_video_url"] = url
    debug["status"] = "succeeded"
    scene["_video_debug"] = debug

    # 逐镜接口不经过 run_pipeline_step；全部视频生成后主动完成 MV05 门控，
    # 避免界面已完成渲染而服务端仍显示 pending。
    if scenes and all(item.get("_video_url") for item in scenes):
        gate_manager.approve(s["gate"], "MV05")
        s["pipeline_state"]["MV05"] = {
            "status": "approved", "duration_sec": None, "error": None,
        }
    return {"url": url, "debug": debug}


def _ffmpeg_bin() -> str:
    """FFmpeg 可执行文件路径：优先读取 FFMPEG_PATH 环境变量，否则回退到 PATH 中的 ffmpeg。"""
    return os.environ.get("FFMPEG_PATH", "ffmpeg").strip() or "ffmpeg"


def merge_scene_videos(sid: str, scene_indices: Optional[List[int]] = None) -> Dict[str, Any]:
    """把各分镜已生成的短视频（scene["_video_url"]）按顺序用 ffmpeg 拼接为一条完整成片。

    依赖服务器已安装 ffmpeg：优先读取 FFMPEG_PATH 环境变量指定的可执行文件路径，
    未设置则默认调用 PATH 中的 `ffmpeg`（Render 部署见 render.yaml 的 buildCommand）。
    """
    import base64
    import shutil
    import subprocess
    import tempfile

    import requests as _requests

    s = session_store.require(sid)
    mv04 = s["mv_outputs"].get("MV04")
    scenes = _get_scenes_from_mv04(mv04)
    if not scenes:
        return {"error": True, "message": "分镜尚未生成，请先完成分镜制作"}

    idxs = scene_indices if scene_indices is not None else list(range(len(scenes)))
    urls: List[str] = []
    for i in idxs:
        if 0 <= i < len(scenes):
            u = scenes[i].get("_video_url")
            if u:
                urls.append(u)
    if not urls:
        return {"error": True, "message": "没有任何分镜已生成视频，请先完成分镜视频渲染"}

    ffmpeg_bin = _ffmpeg_bin()
    if not (shutil.which(ffmpeg_bin) or os.path.isfile(ffmpeg_bin)):
        return {
            "error": True,
            "message": f"未检测到 ffmpeg（{ffmpeg_bin}）。请在部署环境中安装 ffmpeg，"
                        f"或设置环境变量 FFMPEG_PATH 指向其可执行文件路径。",
        }

    tmp_dir = Path(tempfile.mkdtemp(prefix="nn_finalcut_"))
    try:
        clip_paths: List[Path] = []
        for i, url in enumerate(urls):
            dest = tmp_dir / f"clip_{i:03d}.mp4"
            try:
                if url.startswith("data:"):
                    _, b64data = url.split(",", 1)
                    dest.write_bytes(base64.b64decode(b64data))
                else:
                    r = _requests.get(url, timeout=120, stream=True)
                    r.raise_for_status()
                    with open(dest, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1024 * 64):
                            if chunk:
                                f.write(chunk)
            except Exception as e:
                return {"error": True, "message": f"下载第 {i+1} 个分镜视频失败：{e}"}
            clip_paths.append(dest)

        # ── 统一转码为同一分辨率/帧率/编码，避免 concat demuxer 因参数不一致而失败 ──
        norm_paths: List[Path] = []
        for i, p in enumerate(clip_paths):
            np_ = tmp_dir / f"norm_{i:03d}.mp4"
            cmd = [
                ffmpeg_bin, "-y", "-i", str(p),
                "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
                       "pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=25",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-ar", "44100", "-ac", "2",
                str(np_),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if proc.returncode != 0 or not np_.exists():
                return {"error": True, "message": f"片段 {i+1} 转码失败：{proc.stderr[-500:]}"}
            norm_paths.append(np_)

        concat_list = tmp_dir / "concat_list.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for p in norm_paths:
                f.write(f"file '{p.as_posix()}'\n")

        output_name = f"final_cut_{sid}_{int(time.time())}.mp4"
        output_path = FINAL_DIR / output_name
        cmd = [
            ffmpeg_bin, "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list), "-c", "copy", str(output_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0 or not output_path.exists():
            return {"error": True, "message": f"拼接失败：{proc.stderr[-500:]}"}

        s["final_cut_path"] = str(output_path)
        gate_manager.approve(s["gate"], "MV06")
        s["pipeline_state"]["MV06"] = {
            "status": "approved", "duration_sec": None, "error": None,
        }
        return {
            "url": f"/api/pipeline/final-cut/{sid}/file",
            "filename": output_name,
            "clip_count": len(urls),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── 人物传记生成 Pipeline（BIO01~BIO05）────────────────────────────────
BIO_FILES = {
    "BIO01": "BIO01-media-extract.md",
    "BIO02": "BIO02-info-audit.md",
    "BIO03": "BIO03-timeline-rebuild.md",
    "BIO04": "BIO04-biography-writer.md",
    "BIO05": "BIO05-quality-review.md",
    "BIO06": "BIO06-layout-css.md",
}
BIO_ORDER = ["BIO01", "BIO02", "BIO03", "BIO04", "BIO05", "BIO06"]


def run_bio_step(sid: str, bio_step_id: str) -> Dict[str, Any]:
    """执行单个传记生成步骤（BIO01~BIO06）"""
    import time as _t
    
    if bio_step_id not in BIO_FILES:
        return {"error": True, "message": f"unknown step: {bio_step_id}"}
    
    s = session_store.require(sid)
    bio_state = s["bio_state"]
    control = bio_state.setdefault("control", {"paused": False, "canceled": False})
    if control.get("canceled"):
        return {"error": True, "step": bio_step_id, "message": "已取消"}
    if control.get("paused"):
        return {"error": True, "step": bio_step_id, "message": "已暂停"}
    
    # 检查前置依赖
    step_idx = BIO_ORDER.index(bio_step_id)
    for prev_step in BIO_ORDER[:step_idx]:
        if bio_state["step_status"].get(prev_step) != "approved":
            return {"error": True, "message": f"{bio_step_id} 需要前置步骤 {prev_step} 完成"}
    
    # 标记为运行中
    bio_state["step_status"][bio_step_id] = "running"
    print(f"[biography] run_bio_step start session={sid} step={bio_step_id}")
    t0 = _t.time()
    
    try:
        skill_path = SKILLS_DIR / BIO_FILES[bio_step_id]
        system_prompt = load_skill(str(skill_path))
        
        # 为各步骤构建输入 payload
        if bio_step_id == "BIO01":
            payload = {
                "form_data": s["form_data"],
                "assets": get_biography_assets(s),
            }
        elif bio_step_id == "BIO02":
            payload = {
                "extracted_chunks": bio_state.get("extracted_chunks", []),
            }
        elif bio_step_id == "BIO03":
            payload = {
                "usable_chunks": bio_state.get("usable_chunks", []),
                "form_data": s["form_data"],
            }
        elif bio_step_id == "BIO04":
            payload = {
                "form_data": s["form_data"],
                "usable_chunks": bio_state.get("usable_chunks", []),
                "timeline": bio_state.get("timeline", []),
                "assets": get_biography_assets(s),
            }
        elif bio_step_id == "BIO05":
            payload = {
                "biography_draft": bio_state.get("bio_draft", ""),
                "form_data": s["form_data"],
                "usable_chunks": bio_state.get("usable_chunks", []),
                "timeline": bio_state.get("timeline", []),
                "assets": get_biography_assets(s),
            }
        elif bio_step_id == "BIO06":
            payload = {
                "biography_md": bio_state.get("bio_final", ""),
                "form_data": s["form_data"],
                "render_target": "web",
                "assets": get_biography_assets(s),
            }
        else:
            return {"error": True, "message": f"unsupported step: {bio_step_id}"}
        
        # 调用 Skill
        result = call_skill(bio_step_id, system_prompt, payload)
        elapsed = round(_t.time() - t0, 2)
        
        if isinstance(result, dict) and result.get("error"):
            bio_state["step_status"][bio_step_id] = "error"
            bio_state["last_error"] = result.get("message", "unknown")
            return {"error": True, "step": bio_step_id, "message": result.get("message")}
        
        # 如果在执行过程中已取消，则不保存结果
        if bio_state.get("control", {}).get("canceled") or bio_state["step_status"].get(bio_step_id) == "cancelled":
            bio_state["step_status"][bio_step_id] = "cancelled"
            bio_state["last_error"] = "已取消"
            return {"error": True, "step": bio_step_id, "message": "已取消"}

        # 更新 bio_state，存储步骤输出
        if bio_step_id == "BIO01":
            bio_state["extracted_chunks"] = result.get("extracted_chunks", [])
        elif bio_step_id == "BIO02":
            bio_state["usable_chunks"] = result.get("usable_chunks", [])
            bio_state["info_gaps"] = result.get("info_gaps", [])
            form = s.get("form_data", {}) or {}
            user_id = form.get("user_id")
            memorial_id = form.get("memorial_id")
            if user_id and memorial_id:
                note = form.get("family_memory_text", "") or result.get("summary", "") or ""
                try:
                    core_storage.add_dossier_memory(user_id, memorial_id, "Step2 回忆", note, tags=["biography", "step2"])
                except Exception as _ex:
                    print(f"[biography] failed to save step2 memory: {_ex}")
            form = s.get("form_data", {}) or {}
            user_id = form.get("user_id")
            memorial_id = form.get("memorial_id")
            if user_id and memorial_id:
                note = form.get("family_memory_text", "") or result.get("summary", "") or ""
                try:
                    core_storage.add_dossier_memory(user_id, memorial_id, "Step2 回忆", note, tags=["biography", "step2"])
                except Exception as _ex:
                    print(f"[biography] failed to save step2 memory: {_ex}")
        elif bio_step_id == "BIO03":
            bio_state["timeline"] = result.get("timeline", [])
        elif bio_step_id == "BIO04":
            bio_draft = result.get("biography_markdown", "")
            bio_state["bio_draft"] = indent_markdown_paragraphs(bio_draft)
            bio_state["bio_json"] = result.get("biography_json", {})
            form = s.get("form_data", {}) or {}
            user_id = form.get("user_id")
            memorial_id = form.get("memorial_id")
            if user_id and memorial_id and bio_draft:
                try:
                    core_storage.add_dossier_memory(user_id, memorial_id, "传记草稿", bio_draft[:1000], tags=["biography", "draft"])
                except Exception as _ex:
                    print(f"[biography] failed to save draft memory: {_ex}")
        elif bio_step_id == "BIO05":
            bio_final = result.get("biography_final", "")
            bio_state["bio_final"] = indent_markdown_paragraphs(bio_final)
            bio_state["bio_json"] = result.get("biography_json", {})
            bio_state["quality_assessment"] = result.get("quality_assessment", {})
        elif bio_step_id == "BIO06":
            bio_state["bio_css"] = result.get("bio_css", "")
            bio_state["bio_layout_notes"] = result.get("layout_notes", [])
        
        bio_state["step_status"][bio_step_id] = "approved"
        
        # 持久化：不再写入 backend/outputs，改为写入对应 memorial 目录
        try:
            import json as _json
            form = s.get("form_data", {}) or {}
            user_id = form.get("user_id")
            memorial_id = form.get("memorial_id")
            if user_id and memorial_id:
                md_dir = core_storage.memorial_dir(user_id, memorial_id)
                md_dir.mkdir(parents=True, exist_ok=True)
                out_path = md_dir / f"biography_{bio_step_id.lower()}.json"
                out_path.write_text(_json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"[biography] wrote step result to {out_path}")
        except Exception as _ex:
            print(f"[biography] failed to save step json after {bio_step_id}: {_ex}")

        # BIO05/BIO06 完成后写入用户 memorial 目录
        if bio_step_id in ("BIO05", "BIO06"):
            try:
                form = s.get("form_data", {}) or {}
                user_id = form.get("user_id")
                memorial_id = form.get("memorial_id")
                md_dir = None
                if user_id and memorial_id:
                    md_dir = core_storage.memorial_dir(user_id, memorial_id)
                    md_dir.mkdir(parents=True, exist_ok=True)
                if bio_step_id == "BIO05":
                    bio_md = bio_state.get("bio_final", "")
                    if bio_md and md_dir is not None:
                        (md_dir / "biography.md").write_text(bio_md, encoding="utf-8")
                        print(f"[biography] wrote final markdown to {md_dir / 'biography.md'}")
                if bio_step_id == "BIO06":
                    bio_css = bio_state.get("bio_css", "")
                    if bio_css and md_dir is not None:
                        (md_dir / "biography.css").write_text(bio_css, encoding="utf-8")
                        print(f"[biography] wrote bio css to {md_dir / 'biography.css'}")
            except Exception as _ex:
                print(f"[biography] failed to save bio artifacts after {bio_step_id}: {_ex}")

        print(f"[biography] run_bio_step finished session={sid} step={bio_step_id} duration={elapsed}s error={result.get('error', False)}")
        return {
            "ok": True,
            "step": bio_step_id,
            "duration_sec": elapsed,
            "result": result,
        }
    
    except Exception as exc:
        elapsed = round(_t.time() - t0, 2)
        bio_state["step_status"][bio_step_id] = "error"
        bio_state["last_error"] = str(exc)
        print(f"[biography] run_bio_step failed session={sid} step={bio_step_id} error={exc}")
        return {"error": True, "step": bio_step_id, "message": str(exc)}


def run_bio_chain(sid: str) -> Dict[str, Any]:
    """串行执行 BIO01→BIO06，返回最终传记与排版结果"""
    print(f"[biography] run_bio_chain start session={sid}")
    results = {}
    for bio_step_id in BIO_ORDER:
        res = run_bio_step(sid, bio_step_id)
        results[bio_step_id] = res
        if res.get("error"):
            print(f"[biography] run_bio_chain failed session={sid} failed_step={bio_step_id} message={res.get('message')}")
            return {
                "error": True,
                "failed_step": bio_step_id,
                "message": res.get("message"),
                "results": results,
            }
    
    s = session_store.require(sid)
    print(f"[biography] run_bio_chain completed session={sid}")
    # 将最终传记与排版样式写入 data/users/{user_id}/memorials/{memorial_id}/
    try:
        bio_md = s["bio_state"].get("bio_final", "")
        bio_css = s["bio_state"].get("bio_css", "")
        form = s.get("form_data", {}) or {}
        user_id = form.get("user_id")
        memorial_id = form.get("memorial_id")
        if user_id and memorial_id:
            try:
                md_dir = core_storage.memorial_dir(user_id, memorial_id)
                md_dir.mkdir(parents=True, exist_ok=True)
                if bio_md:
                    (md_dir / "biography.md").write_text(bio_md, encoding="utf-8")
                if bio_css:
                    (md_dir / "biography.css").write_text(bio_css, encoding="utf-8")
                print(f"[biography] wrote final artifacts to {md_dir}")
            except Exception as _ex:
                print(f"[biography] failed to write final biography artifacts to user folder: {_ex}")
    except Exception:
        pass
    return {
        "ok": True,
        "message": "传记生成完成",
        "results": results,
        "biography_final": s["bio_state"].get("bio_final", ""),
        "bio_css": s["bio_state"].get("bio_css", ""),
        "biography_json": s["bio_state"].get("bio_json", {}),
    }


def get_biography_result(sid: str) -> Dict[str, Any]:
    """获取当前 session 的传记最终输出"""
    s = session_store.require(sid)
    bio_state = s["bio_state"]
    
    if bio_state["step_status"].get("BIO05") != "approved":
        return {
            "error": True,
            "message": "传记还未生成完成",
            "step_status": bio_state["step_status"],
        }
    
    return {
        "ok": True,
        "biography_final": bio_state.get("bio_final", ""),
        "bio_css": bio_state.get("bio_css", ""),
        "biography_json": bio_state.get("bio_json", {}),
        "quality_assessment": bio_state.get("quality_assessment", {}),
        "info_gaps": bio_state.get("info_gaps", []),
        "timeline": bio_state.get("timeline", []),
    }

