# 念念第一阶段完整技术方案

## 1. 产品定义

「念念」第一阶段不是一个简单的上传资料生成视频工具，而是一个 **纪念项目资料整理 Agent**。

它的第一目标是：

```text
通过电话式采访 + 图片/素材输入，把用户零散的记忆整理成一组可继续生产的文档资产。
```

第一阶段不急着直接生成最终成片。它应该先把“人、记忆、素材、证据、情绪、生产方向”整理清楚。

用户感受到的产品体验应该是：

```text
我只需要和念念说一说，再把照片和材料交给它。
它会像专业采访者一样理解我，整理出一份完整的纪念项目资料。
```

---

## 2. 第一阶段输入与输出

### 2.1 输入 Input

第一阶段输入主要分两类。

#### 输入一：电话沟通

这是第一阶段最重要的入口。

用户点击：

```text
念念
说一说故事
```

然后进入类似智能客服 / 电话采访的体验：

```text
念念主动提问
用户语音回答
系统转写
念念继续追问
全程生成标准化采访纪要 `interview_record`
```

电话沟通要收集：

```text
TA 是谁
用户和 TA 的关系
用户想做什么
TA 的基本身份、年代、地点、职业
TA 的性格、习惯、常说的话
用户最想保留的画面
重要事件和关系线索
用户手里有哪些材料
用户允许和不允许 AI 做什么
声音、数字人、图像生成等边界
```

#### 输入二：图片与材料输入

电话之后，用户进入材料整理阶段。

第一阶段支持用户主动上传：

```text
照片
视频
音频
微信导出聊天记录
聊天机器人历史对话
文字回忆
PDF / Word / Markdown / TXT
讣告
证书
奖状
旧信
截图
```

第一阶段先用上传方式跑通，第二阶段再做真实手机相册、微信、文件夹连接器。

### 2.2 输出 Output

第一阶段最后输出的不是单个 JSON，而是一组文档资产。

这些文档既要给用户看得懂，也要能交给后续生产系统使用。

第一阶段核心输出要按后续用途分成四组：

```text
一、共享基础资产
01_interview_record.md
02_project_brief.md
03_person_profile.md
04_asset_inventory.md
05_memory_discovery_report.md
06_deep_search_report.md
07_permission_profile.md

二、视频生产输出
08_video_story_strategy.md
09_video_script_draft.md
10_visual_asset_plan.md
11_storyboard_brief.md
12_voice_plan.md
mv01.json

三、个人传记输出
13_biography_outline.md
14_life_timeline.md
15_biography_draft.md
16_quote_bank.md
17_fact_check_list.md

四、实时对话数字人输出
18_digital_human_profile.md
19_persona_chat_prompt.md
20_speech_style_dna.md
21_memory_knowledge_base.md
22_safe_response_policy.md
23_conversation_starters.md

结构化总包
project_asset_pack.json
```

其中：

```text
interview_record
标准化采访纪要。它不只是原始通话文本，还包括事实提取、情绪线索、素材线索、待确认问题和可用于后续生产的结构化标签。

project_brief
项目简报，说明用户想做什么、给谁做、用于什么场景。

person_profile
人物档案，整理 TA 的身份、性格、关系、人生阶段、说话方式。

asset_inventory
素材清单，整理所有图片、音频、视频、文档、聊天记录。

memory_discovery_report
记忆发现报告，说明系统从材料中理解到了什么。

deep_search_report
公开搜索报告，说明公开资料、地点背景、职业背景、时代背景中有哪些可验证或待确认信息。

video_story_strategy / video_script_draft / storyboard_brief
面向视频生产，说明故事怎么讲、脚本怎么写、后续如何生成分镜。

biography_outline / life_timeline / biography_draft
面向个人传记，说明人生如何分章、时间线如何组织、正文如何起稿。

digital_human_profile / persona_chat_prompt / memory_knowledge_base
面向实时对话数字人，说明数字人如何说话、记得什么、哪些不能编造。

project_asset_pack.json
所有输出的结构化总包，供后续前端、后端、Agent 和生产 pipeline 使用。

mv01.json
从视频生产输出中转换出来，接入当前已有 MV01-MV06 影像生产线。
```

---

## 3. 第一阶段完整工作流

推荐工作流：

```text
1. 用户点击「念念 / 说一说故事」
2. 念念进入电话式采访
3. Agent 主动提问，用户语音回答
4. 系统保存原始通话，并整理为标准化 `interview_record`
5. 用户上传图片、文字、音频、视频、聊天记录
6. 系统分析素材并生成 `asset_inventory`
7. 系统基于 `interview_record` 提取 Deep Search 查询线索
8. 系统执行 Deep Search，生成 `deep_search_report`
9. 系统融合采访纪要、图片/素材分析、Deep Search，生成 `memory_discovery_report`
10. 系统生成统一追问
11. 用户确认关键事实、情绪、声音和边界
12. 系统生成面向视频、传记、数字人的完整文档资产包
13. 调用 MV01 skill 生成 mv01.json
14. 后续进入 MV02-MV06 影像生产线
```

第一阶段不是“电话采访完就结束”，而是：

```text
采访纪要确定“人和故事的初始轮廓”
图片/材料分析补充“私域证据”
Deep Search 补充“公开背景和可验证线索”
三者融合后形成故事方案、脚本、传记和数字人人设
```

---

## 4. 电话式采访设计

### 4.1 体验目标

电话式采访要像智能客服，但更温柔、更专业。

念念应该：

```text
主动开场
每次只问一个问题
先回应情绪，再追问细节
根据用户回答动态调整采访方向
不强迫用户一次说完整
不提前生成脚本或结论
```

示例：

```text
我在。我们不用一下子说完整，也不用担心顺序。
你可以先从最容易说的地方开始。

你想整理的这个人，你平时怎么称呼 TA？
```

### 4.2 采访内容

电话采访至少覆盖以下方向：

```text
1. 关系
TA 是谁？用户和 TA 是什么关系？

2. 目标
用户想做视频、专辑、数字人、纪念馆，还是先整理资料？

3. 基本信息
姓名、称呼、年代、地点、职业、单位、学校等。

4. 人物印象
性格、习惯、说话方式、常说的话。

5. 核心记忆
用户最想保留的画面或故事。

6. 关系线索
TA 最牵挂谁？和家人、朋友、同事关系如何？

7. 材料线索
用户是否有照片、音频、视频、聊天记录、文章、证书。

8. 授权边界
是否允许公开搜索、材料分析、声音克隆、数字人、图像生成。
```

### 4.3 标准化采访纪要 `interview_record`

电话过程中必须持续保存双方内容，但最终输出不能只是“逐字稿”。它要被整理成一个规定格式的 **标准化采访纪要**。

建议统一命名：

```text
产品展示名：念念采访纪要
文件名：01_interview_record.md
JSON 字段：interview_record
原始轮次字段：raw_turns
```

后续所有分析都应基于：

```text
interview_record + asset_inventory + deep_search_report
```

而不是直接基于零散聊天内容生成故事、脚本或数字人人设。

建议结构：

```json
{
  "interview_record": {
    "record_id": "interview_xxx",
    "project_id": "project_xxx",
    "subject_label": "爸爸 / 奶奶 / 我自己 / 宠物名 / 待确认",
    "interviewer": "念念",
    "interviewee": {
      "name": "用户姓名，可为空",
      "relation_to_subject": "儿子 / 女儿 / 本人 / 朋友 / 待确认"
    },
    "started_at": "2026-05-19T14:00:00",
    "ended_at": "2026-05-19T14:18:00",
    "input_mode": ["voice", "text"],
    "raw_turns": [
      {
        "turn_id": "turn_001",
        "role": "assistant",
        "content": "你想整理的这个人，你平时怎么称呼 TA？",
        "timestamp": "2026-05-19T14:00:00",
        "topic": "relationship"
      },
      {
        "turn_id": "turn_002",
        "role": "user",
        "content": "我想给我爸爸做一个纪念视频。",
        "timestamp": "2026-05-19T14:00:20",
        "input_type": "voice",
        "transcript_source": "whisper",
        "topic": "relationship"
      }
    ],
    "extracted_facts": [
      {
        "fact_id": "fact_001",
        "fact": "用户希望为父亲制作纪念视频",
        "source_turn_ids": ["turn_002"],
        "confidence": "high",
        "needs_confirmation": false
      }
    ],
    "emotion_notes": [
      {
        "emotion": "怀念、克制",
        "evidence": "用户提到父亲时强调想做纪念视频，但没有展开过度煽情内容",
        "source_turn_ids": ["turn_002"]
      }
    ],
    "story_seeds": [
      {
        "title": "沉默的父亲",
        "summary": "用户提到父亲话不多，但希望通过视频留下他的故事",
        "related_turn_ids": ["turn_002"],
        "potential_use": ["video_story_strategy", "biography_outline", "digital_human_profile"]
      }
    ],
    "material_hints": [
      {
        "type": "photo",
        "hint": "需要用户提供父亲照片或家庭合影",
        "reason": "用于人物档案、视频主视觉和分镜参考"
      }
    ],
    "permission_profile": {
      "allow_public_deep_search": null,
      "allow_private_material_analysis": null,
      "allow_voice_clone": null,
      "allow_digital_human": null,
      "allow_image_generation": null,
      "sensitive_boundaries": []
    },
    "missing_information": [
      "父亲姓名或称呼",
      "是否有照片或语音材料",
      "是否允许公开搜索"
    ],
    "next_step_suggestions": [
      "进入图片与材料上传",
      "询问是否允许 Deep Search",
      "确认最终想先做视频、传记还是数字人"
    ]
  }
}
```

### 4.4 采访纪要 Markdown 格式

`01_interview_record.md` 应该按照固定格式输出，方便用户阅读，也方便后续人工审核。

建议格式：

```markdown
# 念念采访纪要

## 1. 基本信息

- 采访对象：
- 被纪念 / 被整理的人：
- 用户与 TA 的关系：
- 采访时间：
- 输入方式：语音 / 文字 / 混合

## 2. 用户想做什么

- 用户目标：
- 使用场景：
- 希望最终产出：
- 希望整体感觉：

## 3. 关于 TA 的初步信息

- 姓名 / 称呼：
- 年代 / 年龄：
- 生活地点：
- 职业 / 身份：
- 家庭关系：
- 性格关键词：
- 常说的话：

## 4. 采访中出现的核心记忆

### 记忆 1：
- 用户原话：
- 系统理解：
- 可用于：视频 / 传记 / 数字人
- 需要确认：

## 5. 情绪与表达倾向

- 用户表达出的情绪：
- 希望保留的感觉：
- 不希望出现的表达：

## 6. 材料线索

- 可能有的照片：
- 可能有的音频：
- 可能有的视频：
- 可能有的聊天记录：
- 可能有的文档：

## 7. 授权与边界

- 是否允许公开 Deep Search：
- 是否允许分析上传材料：
- 是否允许声音克隆：
- 是否允许数字人：
- 是否允许图像生成：
- 敏感边界：

## 8. 待确认问题

1.
2.
3.

## 9. 原始通话记录

> 念念：

> 用户：
```

### 4.5 采访纪要如何参与后续生成

电话结束后，系统根据完整 `interview_record` 生成：

```text
project_brief
person_profile
search_brief
materials_hint
permissions
```

---

## 5. 图片与材料输入设计

图片与材料输入不是独立流程，而是对 `interview_record` 的补充验证。

逻辑顺序必须是：

```text
先有 interview_record，知道“要找谁、要讲什么”
再分析图片与材料，判断“这些材料能证明什么、补充什么”
再做 Deep Search，补充“公开资料和时代背景”
最后三者融合，形成视频、传记和数字人的输出
```

换句话说：

```text
interview_record = 人和故事的主线
asset_inventory = 用户提供的私域证据
deep_search_report = 公开资料与背景证据
memory_discovery_report = 三者融合后的理解结果
```

### 5.1 图片输入

图片是第一阶段最重要的素材输入之一。

用户可上传：

```text
单人肖像
家庭合影
老照片
生活场景
工作场景
证书奖状截图
旧物照片
宠物照片
旅行照片
```

图片分析要输出：

```text
图片里可能有哪些人
场景类型
时间/年代感
地点线索
人物表情和关系
是否适合作为主视觉
是否适合作为某段故事素材
是否需要用户确认人物身份、时间、地点
```

建议输出结构：

```json
{
  "asset_id": "image_001",
  "type": "image",
  "filename": "father_old_photo.jpg",
  "visual_summary": "一位年长男性坐在院子里，背景有木工作坊痕迹。",
  "people_guess": ["年长男性"],
  "scene_guess": "家庭院落 / 工作空间",
  "emotion": "温暖、怀旧",
  "usable_for": ["人物档案", "视频片头", "分镜参考"],
  "needs_user_confirmation": ["照片中的人是谁", "大概时间", "地点"]
}
```

### 5.2 文字输入

文字材料包括：

```text
用户写的回忆
讣告
纪念文章
旧信
证书
奖状
聊天机器人整理过的内容
```

文字分析要提取：

```text
人名
时间
地点
单位
事件
关系
情绪
可作为故事的片段
```

### 5.3 音频输入

音频材料包括：

```text
用户电话回答
TA 生前录音
视频中提取的人声
家属朗读
```

音频分析要输出：

```text
转写文本
说话人是谁
语速
音色
口音
情绪
是否适合声音克隆
是否需要授权确认
```

### 5.4 微信聊天记录

第一阶段不要尝试直接读取微信 App。

推荐方式：

```text
用户导出 CSV / JSON / TXT
用户上传给念念
系统解析并生成语言风格报告
```

分析输出：

```text
常用词
口头禅
说话长短
关心方式
常聊话题
关系线索
数字人语言 DNA
```

### 5.5 视频输入

视频分析要输出：

```text
关键帧
可用片段
是否有人声
是否可提取音频
视频中的人物、场景、动作
是否适合直接用于成片
```

---

## 6. 第一阶段文档资产说明

### 6.1 `01_interview_record.md`

用途：

```text
记录完整采访过程，并按规定格式提取事实、情绪、故事种子、材料线索和待确认问题。
这是所有后续理解的原始依据。
```

内容：

```text
采访时间
用户与念念的每一轮对话
语音转写内容
Agent 追问内容
已提取事实
用户情绪和表达重点
故事种子
材料线索
授权边界
待确认问题
```

### 6.2 `02_project_brief.md`

用途：

```text
说明这次项目要做什么。
```

字段：

```text
项目对象
用户关系
项目类型
使用场景
目标交付物
情绪方向
边界限制
```

### 6.3 `03_person_profile.md`

用途：

```text
形成核心人物档案。
```

内容：

```text
基本信息
身份与职业
人生阶段
人物关系
性格关键词
常说的话
代表性物件
视觉特征
声音特征
用户最想保留的印象
```

### 6.4 `04_asset_inventory.md`

用途：

```text
整理所有上传/导入材料。
```

内容：

```text
素材编号
素材类型
文件名
AI 理解摘要
可用场景
需要用户确认的问题
是否允许用于生成
```

### 6.5 `05_memory_discovery_report.md`

用途：

```text
说明系统从电话和材料里发现了什么。
```

内容：

```text
核心故事候选
关系线索
时间线线索
地点线索
情绪主题
可疑冲突
需要补充的信息
```

### 6.6 `06_follow_up_questions.md`

用途：

```text
统一向用户确认关键问题。
```

原则：

```text
不要超过 3-5 个问题
每个问题都要说明为什么重要
问题要直接影响后续生产
```

### 6.7 `07_content_plan.md`

用途：

```text
决定后续要生成什么内容。
```

内容：

```text
推荐交付物
视频方向
纪念专辑方向
数字人方向
纪念馆方向
先做什么、后做什么
```

### 6.8 `08_voice_plan.md`

用途：

```text
确定声音策略。
```

方案：

```text
原声克隆
相似旁白
家属朗读
无旁白，仅字幕和音乐
```

### 6.9 `09_production_brief.md`

用途：

```text
把前面所有资料交给生产线。
```

内容：

```text
MV01 输入摘要
视频脚本输入
分镜输入
人物/场景/道具圣经输入
数字人人设输入
声音方案输入
```

---

## 7. Agent 与 Skill 设计

### 7.1 第一阶段必须 Agent

```text
Phone Interview Agent
负责电话式采访。

Interview Record Agent
负责把电话式采访整理成标准化采访纪要和第一阶段信息。

Asset Understanding Agent
负责分析图片、文字、音频、视频、聊天记录。

Memory Discovery Agent
负责把电话与素材中的信息合并成记忆发现报告。

Follow-up Question Agent
负责生成统一追问。

Content Planning Agent
负责生成内容方案。

MV01 Adapter Agent
负责把项目资产包转成现有 MV01 skill 可用输入。
```

### 7.2 第一阶段需要调用的 Skill

当前已有：

```text
skills/INTERVIEW01-nian-chat.md
skills/MV01-interview.md
skills/WECHAT01-style-analysis.md
skills/MV02-validation.md
```

建议新增：

```text
skills/ASSET01-asset-inventory.md
skills/MEMORY01-memory-discovery.md
skills/QUESTION01-follow-up.md
skills/PLAN01-content-plan.md
skills/VOICE01-voice-plan.md
```

### 7.3 现有生产线继续使用

```text
skills/MV03-storyboard.md
skills/MV04-bible-lock.md
skills/MV05-avatar-render.md
skills/MV06-final-cut.md
skills/DIALOGUE01-persona-chat.md
```

---

## 8. 需要适配的接口

### 8.1 电话采访 LLM 接口

用途：

```text
念念主动提问、共情回应、动态追问。
```

当前封装：

```python
llm_client.call_memorial_chat()
```

### 8.2 语音转写接口

用途：

```text
用户语音回答 → 文本
```

当前封装：

```python
llm_client.transcribe_audio()
```

配置：

```env
AI302_AUDIO_MODEL=whisper-1
```

### 8.3 采访纪要结构化接口

用途：

```text
interview_record → 第一阶段结构化信息
```

当前封装：

```python
llm_client.call_structured()
```

### 8.4 图片理解接口

用途：

```text
图片 → visual_summary / people_guess / scene_guess / usable_for
```

当前封装：

```python
llm_client.describe_image()
```

### 8.5 微信记录分析接口

用途：

```text
微信导出记录 → 语言风格和关系线索
```

当前文件：

```text
pages/wechat_import.py
skills/WECHAT01-style-analysis.md
```

### 8.6 MV01 结构化接口

用途：

```text
项目资产包 → mv01.json
```

当前封装：

```python
llm_client.call_skill()
pipeline_runner.save_output("MV01", result)
```

### 8.7 Deep Search 接口

第一阶段可先预留。

后续可选：

```text
302.ai 搜索服务
Tavily
SerpAPI
Exa
Perplexity API
自建 RAG
```

---

## 9. 前端适配方案

### 9.1 首页

首页只突出一个主入口：

```text
念念
说一说故事
```

辅助入口：

```text
影像制作
数字人对话
```

### 9.2 电话采访页

页面结构：

```text
顶部：念念状态
中间：圆形电话区域
右侧或下方：通话纪要
底部：录音按钮 / 结束通话
```

核心按钮：

```text
开始通话
录音回答
结束通话并整理纪要
```

### 9.3 材料输入页

电话结束后显示：

```text
我已经知道一些关于 TA 的线索了。
接下来可以把照片和材料交给我，我会帮你整理。
```

卡片：

```text
上传照片
上传音频
上传视频
导入微信记录
导入文档
导入聊天机器人记录
```

### 9.4 统一追问页

只显示最关键问题：

```text
这张照片里的人是谁？
你更希望重点讲哪段故事？
是否允许声音克隆？
哪些内容不能出现在最终成果里？
```

### 9.5 文档输出页

展示：

```text
念念采访纪要
项目简报
人物档案
素材清单
记忆发现报告
内容方案
声音方案
生产简报
```

提供：

```text
下载全部 Markdown
下载 JSON 资产包
调用 MV01
进入影像制作
```

---

## 10. 具体操作步骤

### Step 1：运行项目

```bash
cd /Users/aigc/project/memorial-pipeline-test-unpacked
source .venv/bin/activate
streamlit run app.py
```

访问：

```text
http://localhost:8501
```

### Step 2：配置 API

检查 `.env`：

```env
AI302_API_KEY=...
AI302_TEXT_MODEL=claude-sonnet-4-6
AI302_TEXT_FALLBACK=gpt-5.4
AI302_AUDIO_MODEL=whisper-1
AI302_VISION_MODEL=gemini-2.5-flash
```

### Step 3：测试电话采访

操作：

```text
点击「念念 / 说一说故事」
进入电话式采访
念念主动提问
用户录音回答
系统转写
念念继续提问
```

验收：

```text
Agent 会主动追问
双方内容进入 interview_record.raw_turns，并在通话结束后整理成标准化采访纪要
不是单次上传音频，而是连续电话式交互
```

### Step 4：结束通话并生成第一阶段信息

点击：

```text
结束通话并整理纪要
```

验收：

```text
生成 interview_record
生成 project_brief
生成 person_profile 初稿
生成材料线索和授权边界
```

### Step 5：上传图片和材料

上传：

```text
照片
音频
文档
微信导出记录
```

验收：

```text
生成 asset_inventory
图片有 visual_summary
文档有 document_facts
音频有 transcript 或 voice_hint
聊天记录有 style_hint
```

### Step 6：生成统一追问

验收：

```text
问题不超过 3-5 个
每个问题都影响后续生产
```

### Step 7：生成文档资产

生成：

```text
01_interview_record.md
02_project_brief.md
03_person_profile.md
04_asset_inventory.md
05_memory_discovery_report.md
06_follow_up_questions.md
07_content_plan.md
08_voice_plan.md
09_production_brief.md
```

### Step 8：调用 MV01

点击：

```text
调用 MV01 Skill
```

验收：

```text
outputs/mv01.json 成功生成
```

---

## 11. 第一阶段验收标准

### 必须通过

```text
1. 用户可以点击「念念」进入电话式采访。
2. 念念会主动提问，不是用户单方面上传音频。
3. 用户语音回答可以被转写。
4. 双方完整通话内容会被保存为 `interview_record.raw_turns`，并整理成 `01_interview_record.md`。
5. 通话结束后可以整理成第一阶段信息。
6. 用户可以上传图片和材料。
7. 系统可以生成素材清单。
8. 系统可以生成一组文档资产。
9. 系统可以调用 MV01 skill 输出 mv01.json。
```

### 暂不要求

```text
1. 不要求真实扫描手机相册。
2. 不要求直接读取微信 App。
3. 不要求完整 Deep Search。
4. 不要求最终视频完全自动生成。
5. 不要求多用户账号系统。
```

---

## 12. 第二阶段方向

第一阶段跑通后，再做：

```text
真实图片理解接入 asset_inventory
微信导出记录自动分析
Deep Search 公开搜索
文档批量生成和下载
声音方案 voice_plan
内容方案 content_plan
MV02-MV06 全流程联动
```

第三阶段再做：

```text
手机相册授权
本地文件夹扫描
微信导出助手
移动端 App
后台项目管理
任务队列
对象存储
多用户权限
```

---

## 13. 结论

第一阶段的核心不是做一个“上传文件生成视频”的工具，而是做出：

```text
一个能像电话采访一样理解用户，并把电话内容和图片材料整理成完整文档资产的念念 Agent。
```

当这一步跑通后，后续视频、专辑、数字人、纪念馆都可以基于这些文档资产继续生产。

---

## 13.1 第一阶段输出必须面向后续三条生产线

第一阶段输出不能只是“整理好的资料”，而必须直接服务后续三个核心产品方向：

```text
1. 纪念视频 / 追思影像
2. 个人传记 / 人生故事文档
3. 实时对话数字人
```

也就是说，同一批电话采访和素材分析结果，要被整理成三套可继续生产的输入。

### A. 面向视频生产的输出

用于后续：

```text
MV01 → MV02 → MV03 → MV04 → MV05 → MV06
视频脚本
分镜
图像生成
视频生成
声音方案
最终剪辑
```

第一阶段要输出：

```text
video_story_strategy
视频故事主线：这支片子讲什么，从哪里开始，如何结束。

video_script_draft
视频脚本初稿：片头、章节、旁白、结尾。

visual_asset_plan
视觉素材计划：哪些照片适合片头，哪些适合回忆段，哪些适合分镜参考。

voice_plan
声音方案：原声、旁白、家属朗读、字幕音乐。

storyboard_brief
分镜输入简报：每段故事对应什么画面、情绪、素材引用。

mv01.json
进入现有 MV01-MV06 pipeline 的结构化输入。
```

视频侧最重要的是：

```text
故事主线 + 情绪节奏 + 旁白脚本 + 素材引用 + 声音方案
```

### B. 面向个人传记的输出

用于后续：

```text
个人传记
人生故事文章
纪念册正文
家族档案
长文 PDF
```

第一阶段要输出：

```text
biography_outline
传记目录：按人生阶段、关系、事件组织章节。

life_timeline
人生时间线：重要年份、地点、事件、关系变化。

chapter_briefs
章节摘要：每一章讲什么，用哪些素材和故事。

biography_draft
传记初稿：可以先生成 1000-3000 字版本，后续再扩写。

quote_bank
原话和金句库：用户采访原话、TA 常说的话、聊天记录中的代表表达。

fact_check_list
事实核对清单：哪些年份、地点、单位、关系需要确认。
```

传记侧最重要的是：

```text
时间线 + 人物关系 + 事件细节 + 原话引用 + 事实可信度
```

### C. 面向实时对话数字人的输出

用于后续：

```text
实时对话数字人
角色扮演 System Prompt
人物记忆库
语言风格模拟
对话边界控制
语音/文字交互
```

第一阶段要输出：

```text
digital_human_profile
数字人人设：TA 是谁、和用户什么关系、基本性格。

persona_chat_prompt
实时对话 System Prompt：数字人如何说话、如何回应、如何保持角色。

speech_style_dna
语言风格 DNA：常用词、句子长短、语气、幽默程度、关心方式。

memory_knowledge_base
可用于对话的记忆库：核心事件、关系、地点、物件、重要故事。

safe_response_policy
安全回应边界：不知道的事如何回答，哪些话题不能编造。

conversation_starters
开场白和主动话题：用户进入对话时，数字人如何自然开口。

voice_identity_plan
声音身份方案：是否使用原声、相似旁白、纯文字、TTS。
```

数字人侧最重要的是：

```text
人格稳定 + 语言风格 + 可回答记忆 + 不可编造边界 + 情绪回应方式
```

### 三条生产线共享的基础资产

无论后续做视频、传记还是数字人，都共享这些基础资料：

```text
interview_record
标准化采访纪要，是后续分析的第一输入。

project_brief
项目目标和用户意图。

person_profile
人物档案。

asset_inventory
素材清单。

deep_search_report
公开资料与背景搜索报告。

memory_discovery_report
记忆发现报告。

permission_profile
授权与边界。
```

第一阶段输出结构建议改成：

```json
{
  "shared_assets": {
    "interview_record": {},
    "project_brief": {},
    "person_profile": {},
    "asset_inventory": {},
    "deep_search_report": {},
    "memory_discovery_report": {},
    "permission_profile": {}
  },
  "video_outputs": {
    "video_story_strategy": {},
    "video_script_draft": {},
    "visual_asset_plan": {},
    "storyboard_brief": {},
    "voice_plan": {},
    "mv01_payload": {}
  },
  "biography_outputs": {
    "biography_outline": {},
    "life_timeline": {},
    "chapter_briefs": [],
    "biography_draft": "",
    "quote_bank": [],
    "fact_check_list": []
  },
  "digital_human_outputs": {
    "digital_human_profile": {},
    "persona_chat_prompt": "",
    "speech_style_dna": {},
    "memory_knowledge_base": [],
    "safe_response_policy": {},
    "conversation_starters": [],
    "voice_identity_plan": {}
  }
}
```

这样第一阶段结束时，系统不是只说“我整理好了资料”，而是明确告诉用户：

```text
我已经为你准备好了：
1. 可以生成视频的脚本和分镜输入
2. 可以写个人传记的章节和时间线
3. 可以创建实时对话数字人的人设、语言风格和记忆库
```

---

## 14. 电话采访 Agent 如何具体设置

这一部分是第一阶段最关键的实施细节。

电话采访不是普通聊天框，也不是用户上传一段音频。它应该被实现成一个 **持续会话 Session**。

### 14.1 会话启动

用户点击首页大圆按钮：

```text
念念
说一说故事
```

系统创建一个新的采访会话：

```json
{
  "session_id": "uuid",
  "project_id": "uuid",
  "stage": "phone_interview",
  "status": "active",
  "created_at": "ISO_TIME",
  "turns": [],
  "interview_state": {
    "current_topic": "opening",
    "covered_topics": [],
    "missing_topics": [
      "relationship",
      "project_intent",
      "basic_identity",
      "core_memory",
      "materials",
      "permissions"
    ]
  }
}
```

前端显示：

```text
念念正在听
当前问题
录音按钮
通话纪要
结束通话并整理
```

### 14.2 Agent System Prompt 设置

第一阶段使用：

```text
skills/INTERVIEW01-nian-chat.md
```

但接电话式 Agent 时，需要在运行时额外追加一段约束：

```text
【当前运行模式】
你正在进行实时电话式采访。

你必须像智能客服/专业采访者一样主动推进对话。
你不是等用户问你问题，而是你负责温柔地提问。

每一轮回复必须遵循：
1. 先回应用户刚才说的话，体现理解和共情。
2. 简短总结你听到的一个重点。
3. 只问一个新的问题。

不要一次列多个问题。
不要输出 JSON。
不要写脚本。
不要进入分镜或成片生成。
只有用户点击「结束通话并整理」后，才进入结构化总结。
```

### 14.3 每一轮电话交互怎么跑

每一轮流程：

```text
1. Agent 提出问题
2. 前端播放/展示 Agent 问题
3. 用户录音回答
4. 语音转写为文本
5. 保存用户回答到 interview_record.raw_turns
6. 将最近 N 轮通话传给 Agent
7. Agent 共情回应并提出下一个问题
8. 保存 Agent 回复到 interview_record.raw_turns
```

伪代码：

```python
def phone_turn(audio_bytes):
    transcript = transcribe_audio(audio_bytes)

    interview_record["raw_turns"].append({
        "role": "user",
        "content": transcript,
        "input_type": "voice",
        "timestamp": now()
    })

    reply = call_memorial_chat(
        system_prompt=INTERVIEW_PHONE_SYSTEM_PROMPT,
        messages=interview_record["raw_turns"][-20:]
    )

    interview_record["raw_turns"].append({
        "role": "assistant",
        "content": reply,
        "timestamp": now()
    })

    return reply
```

### 14.4 Agent 要如何决定下一问

Agent 每轮都应内部判断：

```text
已经知道什么
还缺什么
用户当前情绪如何
下一问问哪个最自然
```

建议采访主题顺序不是死板表单，而是动态优先级：

```text
1. 先确认关系：TA 是谁
2. 再确认目标：用户想做什么
3. 再收集身份：姓名、年代、地点、职业
4. 再进入记忆：最想保留的画面
5. 再问语言/习惯：常说的话、性格
6. 再问材料：照片、语音、聊天记录
7. 最后问边界：是否允许搜索、声音克隆、数字人
```

如果用户情绪强烈，Agent 应暂缓推进：

```text
我听得出来，这段记忆对你很重要。
我们可以慢一点，不用急着说完整。

如果你愿意，可以只告诉我：你现在最想保留下 TA 的哪种感觉？
```

### 14.5 通话结束条件

用户可以主动点击：

```text
结束通话并整理纪要
```

系统也可以在 Agent 判断信息足够时提示：

```text
我已经大概了解 TA 的轮廓了。
接下来我可以先帮你整理一版纪要，然后再根据照片和材料继续补充。
```

但最终必须由用户点击确认结束。

---

## 15. 电话结束后如何生成第一阶段信息

电话结束后，不是直接进入视频生成，而是进入 **纪要整理阶段**。

### 15.1 输入

输入是完整标准化采访纪要：

```json
{
  "interview_record": {
    "raw_turns": [
    {"role": "assistant", "content": "..."},
    {"role": "user", "content": "..."}
    ]
  }
}
```

### 15.2 调用 Transcript Summary Agent

使用结构化整理接口：

```python
call_structured(system_prompt, json.dumps({"interview_record": interview_record}))
```

System Prompt 要求：

```text
你是念念采访纪要整理 Agent。
请只基于电话内容整理信息，不要编造。
缺失信息留空。
输出 JSON。
```

### 15.3 输出结构

建议输出：

```json
{
  "project_brief": {
    "project_type": "memorial_video",
    "target_subject": "",
    "user_relation": "",
    "user_goal": "",
    "usage_scene": "",
    "desired_tone": ""
  },
  "person_profile_seed": {
    "name_or_nickname": "",
    "life_period": "",
    "locations": [],
    "occupation_or_identity": "",
    "personality_keywords": [],
    "signature_phrases": [],
    "important_relationships": [],
    "core_memory_candidates": []
  },
  "material_hints": {
    "photos": "",
    "audio": "",
    "video": "",
    "wechat_records": "",
    "documents": ""
  },
  "permissions": {
    "allow_public_search": null,
    "allow_private_material_analysis": null,
    "allow_voice_clone": null,
    "allow_digital_human": null,
    "allow_image_generation": null
  },
  "sensitive_boundaries": [],
  "missing_information": [],
  "suggested_next_questions": []
}
```

### 15.4 生成 Markdown 文档

系统应把 JSON 转成用户可读文档：

```text
01_interview_record.md
02_project_brief.md
03_person_profile.md
```

这一步不要等到所有材料上传后再做。电话结束后就要先生成初稿，让用户感觉“念念已经听懂了”。

---

## 16. 图片输入后如何具体处理

图片输入不能只保存文件名。它要转成可生产素材。

### 16.1 前端上传

第一阶段前端支持：

```text
拖拽上传
多图上传
手机相册选择
单张预览
批量分析按钮
```

每张图上传后生成：

```json
{
  "asset_id": "image_001",
  "source": "user_upload",
  "filename": "",
  "mime_type": "",
  "size_bytes": 0,
  "permission": {
    "can_use_for_profile": true,
    "can_use_for_generation": null,
    "needs_confirmation": true
  }
}
```

### 16.2 图片分析调用

调用：

```python
describe_image(image_bytes, filename)
```

第一阶段建议把图片理解 prompt 加强为：

```text
请分析这张纪念项目素材图。
请输出：
1. 图中可能有哪些人物
2. 场景和地点线索
3. 年代感或时间线索
4. 重要物件
5. 情绪氛围
6. 可用于哪些后续生产：人物档案 / 纪念专辑 / 视频分镜 / 主视觉 / 需确认
7. 需要用户确认的问题
```

### 16.3 图片输出结构

建议结构：

```json
{
  "asset_id": "image_001",
  "visual_summary": "",
  "people": [
    {
      "label": "person_01",
      "description": "",
      "possible_identity": "",
      "needs_confirmation": true
    }
  ],
  "scene": {
    "scene_type": "",
    "location_guess": "",
    "time_period_guess": "",
    "objects": []
  },
  "emotion": "",
  "usable_for": ["person_profile", "album", "storyboard"],
  "questions_for_user": []
}
```

### 16.4 图片如何反哺采访

图片分析后，Question Agent 不应该问一堆问题，而是合并提问：

```text
我看到这几张照片里反复出现一个院子和一位年长男性。
这是不是你刚才说的爸爸？这个院子是老家吗？
```

---

## 17. 文档输出应该怎么生成

第一阶段最终要输出一组 Markdown 文档。

### 17.0 三类证据如何合并成最终输出

所有后续输出都必须基于三类证据合并，而不是只基于电话采访或只基于图片。

```text
第一类：采访证据
来自 interview_record。
它回答：用户如何理解 TA、最想保留什么、情绪和边界是什么。

第二类：私域素材证据
来自 asset_inventory。
它回答：用户提供的照片、音频、文档、聊天记录中实际有什么。

第三类：公开资料证据
来自 deep_search_report。
它回答：公开网络、地点背景、职业背景、时代背景中有什么可验证信息。
```

三者关系：

```text
interview_record 提供主线
asset_inventory 提供素材和细节
deep_search_report 提供背景和校验
memory_discovery_report 负责融合三者
story_strategy / script / biography / digital_human_profile 都基于融合结果生成
```

合并规则：

```text
1. 用户采访原话优先保留，但不能直接当作全部事实。
2. 图片和材料能验证或补充采访内容。
3. Deep Search 只能补充公开背景和可验证事实，不能替用户编造私人经历。
4. 三者冲突时，不自动覆盖，进入 follow_up_questions。
5. 只有已确认或高置信度的信息，才能进入 video_script_draft、biography_draft 和 digital_human_profile。
```

建议生成顺序：

```text
interview_record
  ↓
asset_inventory
  ↓
deep_search_report
  ↓
memory_discovery_report
  ↓
follow_up_questions
  ↓
用户确认
  ↓
story_strategy
  ↓
video_script_draft / biography_draft / digital_human_profile
```

### 17.1 文档生成目录

建议每个项目生成一个目录：

```text
outputs/projects/{project_id}/documents/
```

目录结构：

```text
outputs/projects/{project_id}/documents/
  01_interview_record.md
  02_project_brief.md
  03_person_profile.md
  04_asset_inventory.md
  05_memory_discovery_report.md
  06_follow_up_questions.md
  07_content_plan.md
  08_voice_plan.md
  09_production_brief.md
  project_asset_pack.json
```

### 17.2 每份文档的生成方式

```text
interview_record.md
由通话轮次、事实提取、情绪线索、故事种子和待确认问题共同渲染。

project_brief.md
由 Transcript Summary Agent 生成。

person_profile.md
由标准化采访纪要 + 图片/材料分析 + Deep Search 合并生成。

asset_inventory.md
由所有素材 analysis JSON 渲染。

memory_discovery_report.md
由 Memory Discovery Agent 生成。

follow_up_questions.md
由 Question Agent 生成。

content_plan.md
由 Planning Agent 生成。

voice_plan.md
由 Voice Agent 生成。

production_brief.md
由前面所有文档汇总生成，作为 MV01-MV06 输入。
```

### 17.3 文档模板示例

`02_project_brief.md`：

```markdown
# 项目简报

## 项目对象
- 姓名/称呼：
- 用户关系：
- 当前了解程度：

## 用户目标
- 想做的内容：
- 使用场景：
- 希望表达的感觉：

## 已知材料
- 照片：
- 音频：
- 视频：
- 聊天记录：
- 文档：

## 边界与授权
- 公开搜索：
- 声音克隆：
- 数字人：
- 图像生成：
- 不希望呈现的内容：
```

`03_person_profile.md`：

```markdown
# 人物档案

## 基本信息

## 人物关系

## 性格与气质

## 常说的话 / 语言风格

## 核心记忆

## 代表性物件

## 视觉特征

## 声音特征

## 待确认信息
```

---

## 18. 第一阶段代码落地任务清单

### 18.1 必做文件

当前已有：

```text
app.py
pages/niannian_demo.py
agents/niannian_orchestrator.py
skills/INTERVIEW01-nian-chat.md
```

建议新增：

```text
agents/document_writer.py
agents/asset_understanding_agent.py
agents/question_agent.py
agents/content_plan_agent.py
agents/voice_plan_agent.py
```

### 18.2 `document_writer.py`

职责：

```text
把结构化 JSON 渲染成 Markdown 文件。
```

需要函数：

```python
def write_interview_record(project_id, interview_record): ...
def write_project_brief(project_id, project_brief): ...
def write_person_profile(project_id, person_profile): ...
def write_asset_inventory(project_id, asset_inventory): ...
def write_all_documents(project_id, asset_pack): ...
```

### 18.3 `asset_understanding_agent.py`

职责：

```text
统一分析图片、文字、音频、视频、聊天记录。
```

第一阶段至少实现：

```python
def analyze_image_asset(file): ...
def analyze_text_asset(file): ...
def analyze_audio_asset(file): ...
def analyze_chat_asset(file): ...
def build_asset_inventory(files): ...
```

### 18.4 `question_agent.py`

职责：

```text
根据标准化采访纪要、素材分析和 Deep Search，生成 3-5 个统一追问。
```

输出：

```json
{
  "questions": [
    {
      "question": "",
      "why_it_matters": "",
      "related_assets": [],
      "blocks": ["person_profile", "voice_plan"]
    }
  ]
}
```

### 18.5 `voice_plan_agent.py`

职责：

```text
根据音频素材和用户边界，生成声音方案。
```

输出：

```json
{
  "available_voice_materials": [],
  "recommended_options": [
    "voice_clone",
    "professional_narration",
    "family_reading",
    "subtitle_only"
  ],
  "default_recommendation": "",
  "requires_user_consent": true,
  "questions_for_user": []
}
```

---

## 19. 你作为操作者的执行顺序

你可以按下面顺序推进，不要同时做太多。

### 第 1 步：只确认电话 Agent

目标：

```text
念念能主动问
用户能语音答
标准化采访纪要能保存
```

不要先管图片和 MV01。

### 第 2 步：确认采访纪要转文档

目标：

```text
电话结束后生成：
01_interview_record.md
02_project_brief.md
03_person_profile.md
```

### 第 3 步：接图片输入

目标：

```text
上传 3-5 张图
每张图有视觉理解
生成 04_asset_inventory.md
```

### 第 4 步：做统一追问

目标：

```text
根据电话 + 图片，生成 3-5 个关键问题
```

### 第 5 步：生成完整文档包

目标：

```text
一次性输出 9 份 Markdown + project_asset_pack.json
```

### 第 6 步：接 MV01

目标：

```text
根据 production_brief 调用 MV01
生成 outputs/mv01.json
```

### 第 7 步：再接微信、音频、Deep Search

这些放在第一阶段后半，不要一开始就全部接。

---

## 20. 第一阶段最小可验收版本

如果要最快做一个能展示给别人看的版本，范围可以缩到：

```text
1. 电话式采访
2. 标准化采访纪要
3. 图片上传
4. 图片理解
5. 人物档案
6. 素材清单
7. 统一追问
8. 项目简报文档
9. MV01 JSON
```

也就是说，第一版不一定要做齐所有 9 份文档，但必须证明：

```text
念念能通过电话理解一个人，
并能结合图片，把这些内容整理成可生产资料。
```
