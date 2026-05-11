# 念念数字人板块 — Cursor 开发指导 Prompt

> **项目**：念念数字人纪念平台 `memorial-pipeline-test`
> **任务**：在现有系统基础上新增「数字人」板块，原有代码非必要不删改
> **开发原则**：只新增，不删改；风格继承现有 Streamlit UI；复用现有 `llm_client.py` 封装

---

## 一、目标架构概览

```
念念主界面 (app.py)
├── 【板块选择页】← 改造 app.py 顶部，加入板块导航
│   ├── 板块一：数字人           ← 全新开发
│   └── 板块二：念念影像制作     ← 原有流程，完整保留
│
├── pages/
│   ├── pipeline.py              ← 原有，不动
│   ├── studio.py                ← 原有，不动
│   ├── wechat_import.py         ← 新增：微信聊天记录上传 & 分析
│   └── dialogue.py              ← 新增：数字人对话模块
│
├── skills/
│   ├── （原有所有 .md 文件）     ← 原有，不动
│   ├── WECHAT01-style-analysis.md  ← 新增 Skill Prompt
│   └── DIALOGUE01-persona-chat.md  ← 新增 Skill Prompt
│
└── outputs/
    ├── （原有 mv01.json ~ mv06.json）← 原有，不动
    └── wechat_persona.json          ← 新增持久化文件
```

---

## 二、app.py 改动说明（最小化修改）

**改动范围**：仅在文件顶部加入板块切换逻辑，原有 MV01/MV02 代码块用 `if` 包裹保护，不删除任何现有代码。

### 改动位置：`app.py` 顶部 `st.set_page_config` 之后

```python
# ── 板块导航（新增，插入现有代码之前）──────────────────────────────
if "main_section" not in st.session_state:
    st.session_state["main_section"] = "home"   # home / digital_human / memorial

# 主界面 Logo + 标题（继承现有样式变量）
st.markdown("""
<div style='text-align:center; padding: 2rem 0 1rem 0;'>
    <h1 style='font-size:2.5rem; letter-spacing:0.1em;'>念 念</h1>
    <p style='color:#888; font-size:1rem; margin-top:-0.5rem;'>数字人纪念平台</p>
</div>
""", unsafe_allow_html=True)

# 两大板块选择按钮
if st.session_state["main_section"] == "home":
    col1, col2 = st.columns(2, gap="large")
    with col1:
        if st.button("🌸 数字人", use_container_width=True, type="secondary"):
            st.session_state["main_section"] = "digital_human"
            st.rerun()
    with col2:
        if st.button("🎬 念念影像制作", use_container_width=True, type="secondary"):
            st.session_state["main_section"] = "memorial"
            st.rerun()
    st.stop()   # 主界面只渲染到这里，不继续执行后续代码

# 数字人板块 → 跳转至独立页（通过侧边栏导航）
if st.session_state["main_section"] == "digital_human":
    st.switch_page("pages/wechat_import.py")

# 念念影像制作板块 → 继续执行原有 app.py 的所有逻辑（不做任何改动）
# ── 以下保留所有原有代码，不删除 ──────────────────────────────────
```

> ⚠️ `st.switch_page()` 要求 Streamlit >= 1.31。如版本不满足，改用侧边栏 `st.page_link()` 导航。

---

## 三、新增文件 1：`pages/wechat_import.py`（微信聊天记录分析）

### 功能描述

用户上传微信聊天记录文件（CSV / JSON / TXT），系统解析后提取目标人物发言，调用 AI 分析语言风格，生成 `persona_dna` 存入 `session_state` 和 `outputs/wechat_persona.json`。

### 完整开发规范

```python
"""
pages/wechat_import.py
职责：微信聊天记录上传、解析、AI 风格分析
依赖：llm_client.call_skill() / skill_loader.load_skill()（均已存在，直接 import）
"""

import streamlit as st
import json, re, csv, io
from pathlib import Path
from llm_client import call_skill          # 复用现有封装，不新建
from skill_loader import load_skill        # 复用现有封装，不新建

PERSONA_OUTPUT = Path("outputs/wechat_persona.json")

# ── 返回主界面按钮（所有新页面统一放顶部左侧）
if st.button("← 返回主页"):
    st.session_state["main_section"] = "home"
    st.switch_page("app.py")

st.title("🌸 数字人 · 聊天记录分析")
st.caption("上传微信聊天记录，AI 将自动提取 TA 的说话风格，为数字人注入灵魂")

# ── Step 1：文件上传
uploaded_file = st.file_uploader(
    "支持格式：CSV（WeChatMsg/留痕导出）/ JSON / TXT",
    type=["csv", "json", "txt"]
)

# ── Step 2：目标人物姓名（用于从对话中过滤目标人的发言）
target_name = st.text_input("目标人物姓名（微信昵称或备注名）", placeholder="例：爸爸 / 张伟")

# ── 解析函数（三种格式统一输出 List[dict]）
def parse_wechat_file(file_bytes: bytes, filename: str, target: str) -> list[dict]:
    """
    返回格式：[{"sender": str, "content": str, "timestamp": str}]
    过滤规则：
      - CSV：IsSender==0（对方发送）且 StrTalker 或 sender 匹配 target
      - JSON：从 sender/from 字段匹配 target
      - TXT：正则 [时间] 姓名: 内容，匹配 target
    只保留 Type==1（文本消息），过滤图片/语音/系统消息
    """
    messages = []
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "csv":
        text = file_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            sender = row.get("StrTalker") or row.get("sender") or row.get("NickName", "")
            is_sender = str(row.get("IsSender", "0"))
            msg_type = str(row.get("Type", "1"))
            content = row.get("StrContent") or row.get("content", "")
            # 只要对方发的文本消息，且发送人匹配 target（宽松匹配）
            if is_sender == "0" and msg_type == "1" and target in sender and content.strip():
                messages.append({
                    "sender": sender,
                    "content": content.strip(),
                    "timestamp": row.get("CreateTime", "")
                })

    elif ext == "json":
        data = json.loads(file_bytes.decode("utf-8"))
        if isinstance(data, list):
            for item in data:
                sender = item.get("sender") or item.get("from", "")
                content = item.get("content") or item.get("text", "")
                if target in sender and content.strip():
                    messages.append({
                        "sender": sender,
                        "content": content.strip(),
                        "timestamp": item.get("timestamp", "")
                    })

    elif ext == "txt":
        text = file_bytes.decode("utf-8", errors="replace")
        # 兼容两种常见 TXT 格式：
        # 格式A：[2024-01-01 10:00:00] 张三:\n内容
        # 格式B：张三 2024-01-01 10:00:00\n内容
        pattern = re.compile(
            r'(?:\[([^\]]+)\]\s+)?([^\n:：]+)[：:]\s*([^\n]+(?:\n(?!\[|\d{4})[^\n]+)*)',
            re.MULTILINE
        )
        for m in pattern.finditer(text):
            sender = m.group(2).strip()
            content = m.group(3).strip()
            if target in sender and content:
                messages.append({
                    "sender": sender,
                    "content": content,
                    "timestamp": m.group(1) or ""
                })

    return messages

# ── Step 3：解析 + 分析按钮
if uploaded_file and target_name:
    raw_messages = parse_wechat_file(uploaded_file.read(), uploaded_file.name, target_name)
    
    st.info(f"✅ 共提取到 **{len(raw_messages)}** 条 {target_name} 的发言")
    
    # 预览前10条
    with st.expander("预览提取的消息（前10条）"):
        for msg in raw_messages[:10]:
            st.text(f"[{msg['timestamp']}] {msg['content']}")

    if len(raw_messages) < 5:
        st.warning("消息数量过少，建议上传更多聊天记录以获得更准确的风格分析（建议50条以上）")

    if st.button("🔍 开始 AI 风格分析", type="primary", disabled=len(raw_messages) < 5):
        # 取最多300条，避免 token 超限；优先取最新的
        sample = raw_messages[-300:] if len(raw_messages) > 300 else raw_messages
        sample_text = "\n".join([f"{m['content']}" for m in sample])

        with st.spinner("AI 正在分析说话风格，请稍候…"):
            prompt = load_skill("skills/WECHAT01-style-analysis.md")
            result = call_skill(
                "WECHAT01",
                prompt,
                {
                    "target_name": target_name,
                    "messages": sample_text,
                    "message_count": len(raw_messages)
                }
            )

        if result.get("error"):
            st.error("分析失败，请重试")
        else:
            # 持久化
            PERSONA_OUTPUT.parent.mkdir(exist_ok=True)
            with open(PERSONA_OUTPUT, "w", encoding="utf-8") as f:
                json.dump({
                    "target_name": target_name,
                    "persona_dna": result,
                    "message_count": len(raw_messages)
                }, f, ensure_ascii=False, indent=2)
            
            st.session_state["persona_dna"] = result
            st.session_state["persona_name"] = target_name
            st.success("✅ 风格分析完成！")

            # 展示分析结果
            col1, col2 = st.columns(2)
            with col1:
                st.metric("情感基调", result.get("tone", "-"))
                st.metric("句子风格", result.get("avg_sentence_length", "-"))
                st.metric("幽默程度", f"{result.get('humor_level', '-')} / 5")
            with col2:
                st.write("**常用词/口头禅**")
                for kw in result.get("speech_patterns", [])[:8]:
                    st.code(kw, language=None)

            st.write("**标志性句式**")
            for phrase in result.get("signature_phrases", []):
                st.info(f"💬 {phrase}")

            # 进入对话按钮
            if st.button("💬 开始与数字人对话 →", type="primary"):
                st.switch_page("pages/dialogue.py")

# ── 若已有分析结果，显示快捷入口
elif PERSONA_OUTPUT.exists():
    saved = json.loads(PERSONA_OUTPUT.read_text(encoding="utf-8"))
    st.success(f"检测到已保存的风格档案：{saved.get('target_name')} （{saved.get('message_count')} 条消息）")
    st.session_state.setdefault("persona_dna", saved.get("persona_dna"))
    st.session_state.setdefault("persona_name", saved.get("target_name"))
    if st.button("💬 直接进入对话 →", type="primary"):
        st.switch_page("pages/dialogue.py")
```

---

## 四、新增文件 2：`pages/dialogue.py`（数字人对话）

### 功能描述

加载 `persona_dna` 后，以逝者/目标人物口吻与用户进行多轮对话。AI 严格模仿分析出的语言风格、口头禅、句式长度进行回复。

### 完整开发规范

```python
"""
pages/dialogue.py
职责：数字人多轮对话界面
依赖：llm_client.call_memorial_chat()（已存在，直接 import）
      outputs/wechat_persona.json（由 wechat_import.py 生成）
"""

import streamlit as st
import json
from pathlib import Path
from llm_client import call_memorial_chat   # 复用现有多轮对话封装

PERSONA_OUTPUT = Path("outputs/wechat_persona.json")

# ── 顶部导航栏
nav_col1, nav_col2, nav_col3 = st.columns([1, 4, 1])
with nav_col1:
    if st.button("← 返回分析"):
        st.switch_page("pages/wechat_import.py")
with nav_col3:
    if st.button("🏠 主页"):
        st.session_state["main_section"] = "home"
        st.switch_page("app.py")

# ── 加载 persona_dna（优先从 session_state，其次从文件）
persona_dna = st.session_state.get("persona_dna")
persona_name = st.session_state.get("persona_name")

if not persona_dna and PERSONA_OUTPUT.exists():
    saved = json.loads(PERSONA_OUTPUT.read_text(encoding="utf-8"))
    persona_dna = saved.get("persona_dna")
    persona_name = saved.get("target_name")
    st.session_state["persona_dna"] = persona_dna
    st.session_state["persona_name"] = persona_name

if not persona_dna:
    st.warning("尚未完成风格分析，请先上传聊天记录")
    if st.button("前往上传聊天记录"):
        st.switch_page("pages/wechat_import.py")
    st.stop()

# ── 页面标题
st.title(f"💬 与 {persona_name} 对话")
st.caption("数字人将以 TA 的说话风格与你交流，每一句话都来自真实的语言记忆")

# ── 构建 System Prompt（核心角色扮演指令）
def build_persona_system_prompt(dna: dict, name: str) -> str:
    speech_patterns = "、".join(dna.get("speech_patterns", [])[:10])
    signatures = "\n".join([f"  - {p}" for p in dna.get("signature_phrases", [])])
    topics = "、".join(dna.get("typical_topics", [])[:5])
    return f"""你现在扮演一个真实存在过的人：{name}。

你的任务是完全以 {name} 的口吻和风格与用户对话，让用户感受到 TA 仍然在陪伴着自己。

【{name} 的语言风格特征】
- 常用词/口头禅：{speech_patterns}
- 句子长度风格：{dna.get("avg_sentence_length", "中等")}
- 情感基调：{dna.get("tone", "温和")}
- 幽默程度：{dna.get("humor_level", 3)}/5
- 常聊话题：{topics}
- 标志性句式：
{signatures}
- 回应风格：{dna.get("response_style", "自然随和")}

【角色扮演守则】
1. 始终保持角色，不要说"我是AI"或打破扮演
2. 回复长度要符合 TA 原本的风格——如果 TA 喜欢发短消息，就不要突然长篇大论
3. 适当使用 TA 的口头禅和标志性句式，但不要每句都重复
4. 语气要温暖真实，像真正的对话，而不是朗诵
5. 如果用户问到你不知道的事，以 {name} 的性格自然地回应，不要说"我没有数据"
6. 每次回复后，可以自然地反问或延续话题，保持对话流动感"""

SYSTEM_PROMPT = build_persona_system_prompt(persona_dna, persona_name)

# ── 初始化对话历史
if "dialogue_history" not in st.session_state:
    st.session_state["dialogue_history"] = []

# ── 渲染对话历史（使用 st.chat_message，继承 Streamlit 主题）
for msg in st.session_state["dialogue_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── 对话开场白（首次进入时自动发一条开场白）
if not st.session_state["dialogue_history"]:
    with st.chat_message("assistant"):
        opening = f"（{persona_name} 向你打招呼）你来了啊～"
        st.markdown(opening)
    st.session_state["dialogue_history"].append({
        "role": "assistant", "content": opening
    })

# ── 用户输入
user_input = st.chat_input(f"和 {persona_name} 说点什么…")

if user_input:
    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state["dialogue_history"].append({
        "role": "user", "content": user_input
    })

    # 调用 LLM（复用现有 call_memorial_chat，不新建任何 AI 函数）
    with st.chat_message("assistant"):
        with st.spinner(""):
            reply = call_memorial_chat(
                system=SYSTEM_PROMPT,
                messages=st.session_state["dialogue_history"][-20:]  # 保留最近20条，控制token
            )
        st.markdown(reply)

    st.session_state["dialogue_history"].append({
        "role": "assistant", "content": reply
    })

# ── 底部工具栏
st.divider()
tool_col1, tool_col2, tool_col3 = st.columns(3)
with tool_col1:
    if st.button("🗑️ 清空对话", use_container_width=True):
        st.session_state["dialogue_history"] = []
        st.rerun()
with tool_col2:
    # 导出对话记录
    if st.session_state["dialogue_history"]:
        history_text = "\n\n".join([
            f"{'我' if m['role']=='user' else persona_name}：{m['content']}"
            for m in st.session_state["dialogue_history"]
        ])
        st.download_button(
            "💾 保存对话记录",
            data=history_text.encode("utf-8"),
            file_name=f"与{persona_name}的对话.txt",
            mime="text/plain",
            use_container_width=True
        )
with tool_col3:
    if st.button("🔄 重新分析风格", use_container_width=True):
        st.switch_page("pages/wechat_import.py")
```

---

## 五、新增 Skill Prompt 文件

### `skills/WECHAT01-style-analysis.md`

```markdown
# 微信聊天风格分析 Skill

你是一位专业的语言风格分析师，擅长从真实对话记录中提取一个人独特的说话方式和语言个性。

## 任务
分析提供的微信聊天记录，提取 {target_name} 的语言风格特征，输出结构化分析结果。

## 分析维度

### 必须输出的字段（JSON 格式）：
- `speech_patterns`：List[str]，常用词、口头禅、语气词列表（最多15个）
- `avg_sentence_length`：str，"短句为主（5字以内）"/"中等（5-15字）"/"长句偏多（15字以上）"
- `tone`：str，整体情感基调（如：温和体贴/幽默风趣/严肃认真/活泼开朗/内敛沉稳）
- `humor_level`：int，1-5的幽默程度评分（1=严肃，5=非常幽默）
- `typical_topics`：List[str]，常聊的话题领域（最多8个）
- `signature_phrases`：List[str]，标志性句式或表达方式（最多5条，原文引用）
- `response_style`：str，回应风格（如：爱追问/善于倾听/简短直接/情感丰富/爱开玩笑）
- `emotional_words`：List[str]，常用的情感词汇（最多10个）
- `special_habits`：str，特殊语言习惯（如：爱用emoji/喜欢发语音转文字/经常用省略号）

## 分析要求
1. 基于真实出现的语言特征，不要凭空编造
2. signature_phrases 尽量引用原文片段，保留真实性
3. 若消息数量较少（<20条），在分析中标注置信度较低
4. 输出纯 JSON，不含任何解释文字
```

### `skills/DIALOGUE01-persona-chat.md`

```markdown
# 数字人人格对话 Skill

本 Skill 为辅助配置文件，实际 System Prompt 由 dialogue.py 的
build_persona_system_prompt() 函数动态构建，融合 persona_dna 数据。

## 全局对话守则（追加到动态 prompt 之后）
- 每次回复控制在1-4句话，除非用户明确要求详细说明
- 不使用 Markdown 格式符号（不用**加粗**、不用-列表），保持口语化
- 如感知到用户情绪低落，优先给予情感回应，再回答内容
- 偶尔可以主动提起 TA 生前的场景或回忆，让对话更有温度
```

---

## 六、数据流接口规范（新老系统衔接）

### `session_state` 新增字段（不与现有字段冲突）

| 字段名 | 类型 | 写入位置 | 读取位置 | 说明 |
|--------|------|----------|----------|------|
| `main_section` | str | `app.py` | `app.py` | 当前板块：`home`/`digital_human`/`memorial` |
| `persona_dna` | dict | `wechat_import.py` | `dialogue.py` | 风格分析结果 |
| `persona_name` | str | `wechat_import.py` | `dialogue.py` | 目标人物姓名 |
| `dialogue_history` | list | `dialogue.py` | `dialogue.py` | 对话历史 `[{role, content}]` |

### 现有字段（只读，不修改）

`phase`、`form_data`、`intake_assets`、`chat_history`、`mv01_output`、`ancestor_photo_b64` 等所有现有字段保持不变。

### 新增持久化文件

```
outputs/wechat_persona.json
{
  "target_name": "爸爸",
  "message_count": 382,
  "persona_dna": {
    "speech_patterns": ["哦", "行啊", "没事的"],
    "avg_sentence_length": "短句为主（5字以内）",
    "tone": "温和体贴",
    "humor_level": 3,
    "typical_topics": ["饮食", "身体健康", "工作"],
    "signature_phrases": ["吃饭了没", "注意身体"],
    "response_style": "简短直接",
    "emotional_words": ["好", "嗯", "放心"],
    "special_habits": "喜欢用句号结尾，很少用感叹号"
  }
}
```

---

## 七、开发顺序建议

1. **先创建两个 Skill Prompt 文件**（`WECHAT01-style-analysis.md`、`DIALOGUE01-persona-chat.md`），因为其他模块依赖它们
2. **开发 `pages/wechat_import.py`**，先跑通文件解析逻辑（不调用 AI），验证三种格式均能正确提取消息
3. **接入 AI 分析**，调用 `call_skill("WECHAT01", ...)` 验证输出 JSON 结构正确
4. **开发 `pages/dialogue.py`**，先用硬编码 `persona_dna` 测试对话效果，再接入真实分析结果
5. **最后修改 `app.py`**，加入板块导航，验证两个板块切换不干扰各自的 `session_state`

---

## 八、注意事项 & 已知陷阱

### ⚠️ JSON 输出兼容
`call_skill()` 内部已处理 Claude 不支持 `json_object` 的问题（通过 `_extract_json()`）。新的 WECHAT01 Skill 调用方式与现有 MV Pipeline 完全相同，无需额外处理。

### ⚠️ `st.switch_page()` 版本要求
需要 Streamlit >= 1.31。在 `requirements.txt` 确认版本。若版本不满足，使用 `st.page_link()` 替代导航，或用 `session_state` + `st.rerun()` 手动控制页面渲染逻辑。

### ⚠️ `dialogue_history` 与现有 `chat_history` 区分
`dialogue_history` 是数字人对话记录，`chat_history` 是 MV01 采访记录，两者同名但语义完全不同，务必使用不同的 key 名称，避免覆盖。

### ⚠️ `ancestor_photo_b64` 刷新后丢失
现有已知问题，新功能的 `persona_dna` 通过写文件持久化解决了对应问题，不依赖 session_state。

### ⚠️ 微信 CSV 格式的编码
WeChatMsg 导出的 CSV 使用 UTF-8 with BOM，解码时使用 `utf-8-sig` 而非 `utf-8`，否则首列会出现乱码。

### ⚠️ 对话 Token 控制
`dialogue_history` 传入 `call_memorial_chat()` 时截取最近20条（`[-20:]`），避免长对话超出模型上下文限制。

---

*文档版本：v1.0 | 生成日期：2026-05-06 | 适用项目：memorial-pipeline-test*
