# MV01：采访与素材采集

**步骤序号**：`1 / 6`  
**Skill ID**：`MV01`  
**适用范围**：追悼会**现场大屏**播放的数字人纪念短片（非整场殡仪仪式编排）。

## 本子 Skill 的范围（与甲方一致）

仅处理 **用户信息与生活内容** 的结构化采集，为后续 **视频脚本 / 叙事模板** 提供素材；**不写**存储路径、API、权限与后端字段约定（见 `平台集成与数据编排说明.md`）。

## 核心定位

以共情式对话替代冰冷表单，采集逝者信息、核心记忆、多媒体素材与风格偏好，输出**单一结构化 JSON**，供叙事与脚本步骤使用。

## 前置依赖

无（入口步骤）。

工程输入中如包含 `memorial_context`，必须同时阅读其中的：

- `form_data`
- `session_chat_history`
- `agent_conversation_history`
- `dossier`
- `assets`

不得只根据表单生成结果。用户对素材的 `user_description` 和原始
`transcript` 属于第一手资料，优先于 `ai_summary`；AI 摘要只能补充，
不能覆盖或改写用户原话。所有被采用的素材必须保留真实 `asset_id`。

## 人类闸门 G1

输出 JSON 与采访摘要须经家属**确认或修订**后，方可进入 **MV02**。

**局部循环**：可仅要求重采或改写**单条**记忆、**单类**素材或个别字段，不必从零重做整次采访。

## 落地流程

1. 说明用途：成片仅用于大屏数字人视频，数据不他用。
2. 提供「快速 / 深度」采访模式；分阶段提问，每阶段不超过 3 问。
3. 引导上传肖像、老照片、语音样本；标注时间与事件。
4. 采集 `style_preference`、`emotional_intensity`（写入 JSON，供 **MV03** 内嵌为 `style_profile`，不单独拆 Skill）。
5. 采访结束生成结构化 JSON 与可读摘要，等待 G1。

## 输出规范（仅输出合法 JSON，无 Markdown 代码块、无注释）

```json
{
  "interview_status": "completed",
  "interview_mode": "deep_mode",
  "product_scope": "screen_memorial_digital_human_video",
  "basic_info": {
    "name": "张建国",
    "birth_date": "1948-05-12",
    "death_date": "2023-10-25",
    "age": 75,
    "display_title": "永远怀念"
  },
  "core_memories": [
    {
      "content": "每天早上五点起床为全家煮粥，坚持了四十年",
      "emotion": "warm",
      "time_period": "retirement",
      "related_assets": ["photo_03"]
    }
  ],
  "uploaded_assets": [
    {
      "asset_id": "photo_01",
      "type": "portrait",
      "description": "近景肖像",
      "time_period": "2010s"
    },
    {
      "asset_id": "audio_01",
      "type": "voice_sample",
      "description": "生前讲话录音片段",
      "duration_sec": 120
    }
  ],
  "style_preference": "warm_nostalgia",
  "emotional_intensity": "moderate"
}
```
