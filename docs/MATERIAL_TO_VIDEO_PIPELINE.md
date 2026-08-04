# 念念：素材驱动的视频动态化与剪辑方案

版本：v1.0
目标：把资料库中的真实图片、视频、音频和文字，转换为一份可执行的剪辑计划，并最终生成 MP4 成片。

## 1. 推荐结论

不要把所有照片都交给视频模型“自由生成”。推荐采用三级策略：

1. **真实视频直接使用**：只做裁切、调色、降噪和节奏调整。
2. **真实照片优先做低风险动态化**：
   - 多人合影、老照片、带文字的照片：使用 FFmpeg Ken Burns（缓慢推拉、平移）。
   - 单人肖像、环境照片、动作意图明确的照片：可选择 Kling 图生视频。
3. **确实没有真实画面时才 AI 生图，再做图生视频**。

图片动态化的正确顺序是：

```text
真实图片
  ├─ 适合保真动态化 → 直接把原图交给图生视频模型
  ├─ 人脸/文字容易变形 → FFmpeg 推拉平移
  └─ 没有对应画面 → AI 生图 → 人工/规则校验 → 图生视频
```

当前系统已经具备真实图片复用、TokenStar Kling 图生视频和 FFmpeg 拼接能力。下一步的重点不是再增加一个生成模型，而是增加统一的 `edit_plan.json` 和按计划执行的渲染器。

## 2. 当前代码与缺口

| 能力 | 当前实现 | 结论 |
|---|---|---|
| 分镜绑定真实素材 | `material_context.attach_assets_to_storyboard()` 写入 `source_asset_ids` | 已具备 |
| 真实图片作为首帧 | `service_manager.gen_scene_image()` 直接读取原始图片 | 已具备 |
| 图片动态化 | `service_manager.gen_scene_video()` 调用 TokenStar Kling I2V | 已具备，但固定为 5 秒 |
| 视频拼接 | `service_manager.merge_scene_videos()` 统一到 720p/25fps 后 concat | 已具备基础版 |
| 旁白、字幕、BGM、转场 | 没有统一执行清单 | 需要新增 |
| 模型失败回退 | 单镜失败后依赖用户手动重试 | 需要自动降级 |
| 15 秒叙事镜头与 5 秒模型片段对齐 | 当前未拆分 | 需要引入“剪辑片段 clip”层 |

关键设计：**MV03/MV04 的 scene 是叙事段落，最终剪辑使用的 clip 是 3–6 秒的实际画面片段。一个 scene 可以拆成多个 clip。**

## 3. 总体 Pipeline

```text
素材库 assets.json
        │
        ▼
MemorialContext
  用户描述 > 转写原文 > dossier > AI 摘要
        │
        ▼
MV03/MV04 叙事分镜 scenes
  每镜带 source_asset_ids
        │
        ▼
Edit Planner
  scene 拆成 3–6 秒 clips
  决定 direct_video / ai_i2v / ken_burns / ai_generated
        │
        ▼
edit_plan.json
        │
        ├─ Motion Renderer：照片动态化或视频生成
        ├─ Voice Renderer：旁白/TTS/原声
        ├─ Subtitle Renderer：ASS/SRT
        └─ Audio Planner：BGM、ducking、淡入淡出
        │
        ▼
FFmpeg Final Cut
  统一转码 → 转场 → 字幕 → 旁白/BGM 混音 → MP4
```

## 4. 素材到动态化方式的决策表

| 素材情况 | 默认策略 | 推荐时长 | 原因 |
|---|---|---:|---|
| 已有真实视频 | `direct_video` | 3–12 秒 | 真实性最高 |
| 单人半身/全身照，人物清晰 | `ai_i2v` | 4–5 秒 | 可产生轻微呼吸、眨眼、镜头推进 |
| 风景、院子、房间、物件 | `ai_i2v` | 4–5 秒 | 人脸风险低，动态效果自然 |
| 多人合影 | `ken_burns` | 4–8 秒 | 图生视频容易改变人数和脸 |
| 新闻截图、证书、信件、带文字照片 | `ken_burns` | 4–8 秒 | 必须保护文字内容 |
| 低清、破损、极老照片 | `ken_burns` | 4–6 秒 | 避免模型重绘身份特征 |
| 没有真实素材但描述完整 | `ai_generated_i2v` | 4–5 秒 | 先生成首帧，再动态化 |
| 没有画面且事实不充分 | `title_card` / `text_card` | 3–5 秒 | 不编造具体人物或事件 |

### 4.1 自动决策建议

素材分析阶段补充以下字段：

```json
{
  "face_count": 1,
  "has_text": false,
  "identity_sensitivity": "high",
  "motion_safety": "safe | cautious | static_only",
  "recommended_motion": "ai_i2v | ken_burns | direct_video",
  "recommended_crop": "center | face_tracking | contain"
}
```

决策规则：

```python
def choose_motion(asset):
    if asset["kind"] == "video":
        return "direct_video"
    if asset.get("has_text") or asset.get("face_count", 0) > 1:
        return "ken_burns"
    if asset.get("motion_safety") == "static_only":
        return "ken_burns"
    if asset["kind"] == "image" and (
        asset.get("face_count") == 1 or asset.get("scene")
    ):
        return "ai_i2v"
    return "ken_burns"
```

## 5. `edit_plan.json` 数据结构

`edit_plan` 是视频生成模型和 FFmpeg 之间的唯一执行合同。完整示例见
[`docs/examples/memorial_edit_plan.example.json`](examples/memorial_edit_plan.example.json)。

| 字段 | 作用 |
|---|---|
| `project` | 分辨率、帧率、画幅、目标时长 |
| `clips[]` | 实际剪辑片段，按数组顺序上时间线 |
| `parent_scene_id` | 回指 MV04 叙事分镜 |
| `source_asset_ids` | 本片段真实使用的素材 |
| `strategy` | `direct_video`、`ai_i2v`、`ken_burns`、`ai_generated_i2v`、`title_card` |
| `duration_sec` | 该 clip 的真实成片时长 |
| `motion_prompt` | 图生视频运动描述，不重新描述人物身份 |
| `fallback_strategy` | 模型失败后的自动降级方式 |
| `narration` | 旁白资源、入点和音量 |
| `subtitle` | 字幕文本和样式 |
| `transition_out` | 与下一段的转场 |
| `render_state` | queued/running/succeeded/failed/fallback |

### 5.1 时长规则

- 一个 AI 图生视频 clip：建议 4–5 秒。
- 一个叙事 scene 如果是 15 秒，应拆为 3 个约 5 秒 clip。
- 旁白不应强行与单个模型片段一一对应；旁白可以覆盖多个 clip。
- 总时长由 `edit_plan.clips[].duration_sec` 计算，不再依赖模型返回片段的自然时长。

## 6. 图片动态化实现

### 6.1 方案 A：Kling 图生视频

适用于单人肖像、环境和物件。

当前接入点：

```python
generate_video_tokenstar_i2v(
    prompt=motion_prompt,
    image_url=public_image_url,
    duration=5,
    poll=True,
    max_wait=600,
)
```

纪念素材的运动 Prompt 必须克制：

```text
Preserve the exact identity, face, clothing, background layout and object count
from the source image. Only subtle natural breathing, one gentle blink, slight
fabric movement and a very slow camera push-in. No talking, no new people, no
face redesign, no age change, no camera shake.
```

约束：

- 不要求照片人物开口说话，避免口型和身份漂移。
- 不描述用户没有确认的事件。
- 不改变人数、服装、年代、文字和标志性物件。
- 输出后保留 `source_asset_id`、模型、Prompt、任务 ID 和生成 URL。

### 6.2 方案 B：FFmpeg Ken Burns

适用于合影、老照片、文字材料，也是所有 I2V 失败时的保底。

```bash
ffmpeg -y -loop 1 -i input.jpg -t 5 \
  -vf "scale=1400:788:force_original_aspect_ratio=increase,\
crop=1280:720,\
zoompan=z='min(zoom+0.0008,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1280x720:fps=25,\
format=yuv420p" \
  -an -c:v libx264 -preset veryfast -crf 18 output.mp4
```

建议提供四个模板：

- `slow_zoom_in`
- `slow_zoom_out`
- `pan_left_to_right`
- `pan_right_to_left`

人脸位置可由视觉分析返回的 bounding box 决定 `x/y`，避免裁掉头部。

### 6.3 方案 C：AI 生图后动态化

只在 `source_asset_ids` 为空时执行：

```text
MV04 scene description
  → TokenStar gpt-image-2 生成首帧
  → 校验人物圣经、场景圣经和画幅
  → Kling I2V
  → 校验失败则回退到静态首帧 Ken Burns
```

AI 生成画面必须标记：

```json
{
  "provenance": "ai_generated",
  "source_asset_ids": [],
  "generation_model": "gpt-image-2",
  "motion_model": "kling-v3"
}
```

## 7. 执行脚本设计

建议新增三个服务模块：

```text
backend/services/edit_planner.py
backend/services/motion_renderer.py
backend/services/final_cut_renderer.py
```

### 7.1 Edit Planner

```python
def build_edit_plan(sid: str) -> dict:
    session = session_store.require(sid)
    context = material_context.build_memorial_context(session)
    scenes = get_mv04_scenes(session)

    clips = []
    for scene in scenes:
        # 15 秒叙事镜头拆成最多 5 秒的实际画面片段
        clip_count = max(1, math.ceil(scene_duration(scene) / 5))
        ranked_assets = rank_scene_assets(scene, context["assets"])
        for index in range(clip_count):
            asset = choose_asset(ranked_assets, index)
            clips.append(make_clip(scene, asset, index))

    plan = validate_duration_and_provenance(clips)
    save_json(session_output_dir(sid) / "edit_plan.json", plan)
    return plan
```

### 7.2 Motion Renderer

```python
def render_clip(clip: dict) -> Path:
    try:
        if clip["strategy"] == "direct_video":
            return normalize_real_video(clip)
        if clip["strategy"] == "ai_i2v":
            return render_kling_i2v(clip)
        if clip["strategy"] == "ai_generated_i2v":
            frame = render_ai_frame(clip)
            return render_kling_i2v({**clip, "frame": frame})
        if clip["strategy"] in ("ken_burns", "title_card"):
            return render_ffmpeg_motion(clip)
        raise ValueError("unsupported strategy")
    except Exception as exc:
        mark_failed(clip, exc)
        return render_ffmpeg_motion({
            **clip,
            "strategy": clip["fallback_strategy"],
        })
```

### 7.3 渲染队列

不要在一次 HTTP 请求内串行生成全部镜头。建议：

```text
POST /api/pipeline/edit-plan/{sid}
POST /api/pipeline/render-clips/{sid}
GET  /api/pipeline/render-status/{sid}
POST /api/pipeline/final-cut-v2/{sid}
```

每个 clip 独立记录状态，支持失败重试和断点续跑。MVP 可继续使用 FastAPI
`BackgroundTasks`；生产稳定版建议使用 Redis + RQ/Celery，避免 Render 重启后任务丢失。

## 8. FFmpeg 最终剪辑流程

### 8.1 目录

```text
outputs/projects/{sid}/
  edit_plan.json
  clips/raw/
  clips/normalized/
  audio/narration.wav
  audio/bgm.wav
  subtitles/final.ass
  final/final.mp4
  render_manifest.json
```

### 8.2 片段标准化

所有片段先统一：

```text
1280x720 或 1920x1080
25 fps
H.264 / yuv420p
AAC 48kHz stereo
固定 time_base
```

```bash
ffmpeg -y -i clip.mp4 \
  -vf "scale=1280:720:force_original_aspect_ratio=decrease,\
pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=25,format=yuv420p" \
  -c:v libx264 -preset veryfast -crf 20 \
  -c:a aac -ar 48000 -ac 2 normalized.mp4
```

### 8.3 转场

MVP 只支持两类，避免时间线计算失控：

- `cut`
- `crossfade`，默认 0.6–1.0 秒

转场时长要从总时长中扣除：

```text
final_duration = sum(clip.duration_sec) - sum(crossfade.duration_sec)
```

### 8.4 旁白、原声和 BGM

音频优先级：

```text
用户原声 > 克隆/合成旁白 > BGM
```

推荐音量：

| 音轨 | 基础音量 |
|---|---:|
| 旁白/原声 | 1.0 |
| BGM 无旁白 | 0.22–0.30 |
| BGM 有旁白 | 0.10–0.16 |
| 环境音 | 0.08–0.18 |

使用 sidechain compression 自动压低旁白下的 BGM：

```text
[bgm][narration]sidechaincompress=threshold=0.03:ratio=8[ducked]
[ducked][narration]amix=inputs=2:duration=longest
```

### 8.5 字幕

- 根据旁白时间码生成 ASS。
- 每行建议不超过 16 个汉字，最多两行。
- 安全区距底部 8%。
- 使用浅色正文、深色描边，避免遮挡脸。

最终烧录：

```bash
ffmpeg -y -i timeline.mp4 -i narration.wav -i bgm.wav \
  -filter_complex "音频混音与ducking;[v]subtitles=final.ass[vout]" \
  -map "[vout]" -map "[audio_out]" \
  -c:v libx264 -crf 18 -preset medium \
  -c:a aac -b:a 192k -movflags +faststart final.mp4
```

## 9. 自动失败回退

| 失败点 | 自动回退 |
|---|---|
| AI 生图失败 | 使用真实关联图片；仍无图片则文字卡 |
| Kling I2V 失败/超时 | 原图 Ken Burns |
| 下载模型视频失败 | 重试 2 次，之后 Ken Burns |
| 人脸/人数校验失败 | 丢弃 AI 视频，Ken Burns |
| FFmpeg 单片转码失败 | 标记 clip failed，不允许静默跳过 |
| BGM 不存在 | 无 BGM 合成，不阻塞视频 |
| 旁白失败 | 保留字幕，提示用户重试旁白 |

## 10. Studio 页面建议

每个分镜不再只显示“生成图片/生成视频”，而显示：

```text
真实素材：a_xxx.jpg
推荐方式：保真推拉 / AI 动态化 / 直接视频
预计片段：5 秒
状态：等待 / 生成中 / 已完成 / 已降级
```

允许用户单镜切换：

- 使用真实静态动态
- 使用 AI 动态化
- 使用 AI 补充画面
- 不使用此镜

最终合成前展示一张剪辑清单表，用户确认后才进入 MV06。

## 11. 推荐实施顺序

### Phase 1：可靠成片

1. 新增 `edit_plan.json`。
2. 把 15 秒 scene 拆为 3–6 秒 clips。
3. 增加 Ken Burns 保底。
4. 继续使用当前 Kling I2V。
5. FFmpeg 支持目标时长、cut/crossfade、旁白、BGM 和字幕。

### Phase 2：质量控制

1. 增加人脸数、文字和低清检测。
2. I2V 输出与原图做人物/人数一致性校验。
3. 增加单 clip 重试和断点续跑。
4. 保存 `render_manifest.json` 记录每个 asset_id 的实际使用位置。

### Phase 3：高级包装

1. 片头、片尾、姓名年份卡。
2. 2.5D 景深和轻量粒子。
3. 数字人叠加 B-roll。
4. 多画幅输出：16:9、9:16、1:1。

图形标题、字幕包装和纪念年份卡可选用 HyperFrames 生成透明或整帧图形片段，
最终仍由 FFmpeg 与真实素材、模型视频统一合成；MVP 不需要替换现有 FFmpeg 主链路。

## 12. 验收标准

- 每个成片 clip 都能追溯 `parent_scene_id` 和 `source_asset_ids`。
- 有真实素材时不得无理由生成替代人物。
- 多人合影和带文字照片默认不使用 I2V。
- I2V 失败后自动产出 Ken Burns 片段，整片不被单镜阻塞。
- 最终视频时长与计划误差不超过 0.5 秒。
- 所有片段分辨率、帧率、编码一致。
- 旁白存在时 BGM 自动 ducking。
- 字幕与旁白误差不超过 200ms。
- `render_manifest.json` 能说明每镜使用了什么素材、模型和回退策略。
