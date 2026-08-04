"""Deterministic FFmpeg compiler for approved NianNian video projects."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import storage


class RenderError(RuntimeError):
    def __init__(self, message: str, render_manifest: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.render_manifest = render_manifest or {}


_DIMENSIONS = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (1080, 1080)}
_XFADE = {
    "cut": "fade", "fade": "fade", "dissolve": "dissolve",
    "wipeleft": "wipeleft", "wiperight": "wiperight",
    "smoothleft": "smoothleft", "smoothright": "smoothright",
}


def _ffmpeg() -> str:
    return os.getenv("FFMPEG_PATH", "ffmpeg").strip() or "ffmpeg"


def _ffprobe() -> str:
    configured = os.getenv("FFPROBE_PATH", "").strip()
    if configured:
        return configured
    ffmpeg = Path(_ffmpeg())
    if ffmpeg.name.lower().startswith("ffmpeg"):
        sibling = ffmpeg.with_name("ffprobe" + ffmpeg.suffix)
        if sibling.exists():
            return str(sibling)
    return "ffprobe"


def _asset_paths(user_id: str, memorial_id: str) -> Dict[str, Tuple[Dict[str, Any], Path]]:
    root = (storage.memorial_dir(user_id, memorial_id) / "assets").resolve()
    result: Dict[str, Tuple[Dict[str, Any], Path]] = {}
    for asset in storage.list_assets(user_id, memorial_id):
        asset_id = str(asset.get("asset_id") or "")
        path = (root / str(asset.get("stored_name") or "")).resolve()
        if asset_id and root in path.parents and path.is_file():
            result[asset_id] = (asset, path)
    return result


def _within(root: Path, relative: str) -> Path:
    resolved_root = root.resolve()
    path = (resolved_root / relative).resolve()
    if resolved_root not in path.parents or not path.is_file():
        raise RenderError("生成镜头文件不存在或路径越界")
    return path


def _recorded_run(command: List[str], cwd: Path, records: List[Dict[str, Any]], timeout: int = 600) -> None:
    started = time.monotonic()
    record: Dict[str, Any] = {"argv": [str(item) for item in command], "status": "running"}
    records.append(record)
    try:
        process = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except Exception as exc:
        record.update({"status": "failed", "duration_sec": round(time.monotonic() - started, 3), "stderr": str(exc)})
        raise RenderError(f"FFmpeg 执行异常：{exc}") from exc
    record.update({
        "status": "completed" if process.returncode == 0 else "failed",
        "returncode": process.returncode,
        "duration_sec": round(time.monotonic() - started, 3),
        "stderr": (process.stderr or "")[-2000:],
    })
    if process.returncode != 0:
        raise RenderError(f"FFmpeg 执行失败：{(process.stderr or '')[-800:]}")


def _has_audio(path: Path, work_dir: Path, records: List[Dict[str, Any]]) -> bool:
    command = [
        _ffprobe(), "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_type", "-of", "json", str(path),
    ]
    started = time.monotonic()
    record: Dict[str, Any] = {"argv": command, "status": "running"}
    records.append(record)
    try:
        process = subprocess.run(command, cwd=str(work_dir), capture_output=True, text=True, timeout=30, shell=False)
        record.update({
            "status": "completed" if process.returncode == 0 else "failed",
            "returncode": process.returncode,
            "duration_sec": round(time.monotonic() - started, 3),
            "stderr": (process.stderr or "")[-500:],
        })
        if process.returncode != 0:
            return False
        data = json.loads(process.stdout or "{}")
        return bool(data.get("streams"))
    except Exception as exc:
        record.update({"status": "failed", "duration_sec": round(time.monotonic() - started, 3), "stderr": str(exc)})
        return False


def _srt_time(seconds: float) -> str:
    millis = max(0, int(round(seconds * 1000)))
    hours, remain = divmod(millis, 3_600_000)
    minutes, remain = divmod(remain, 60_000)
    secs, ms = divmod(remain, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _write_subtitles(path: Path, clips: List[Dict[str, Any]]) -> bool:
    blocks: List[str] = []
    for clip in clips:
        text = str(clip.get("subtitle") or clip.get("narration") or "").strip()
        if not text:
            continue
        text = text.replace("-->", "—").replace("\x00", "")
        blocks.append(
            f"{len(blocks) + 1}\n{_srt_time(float(clip['start_sec']))} --> {_srt_time(float(clip['end_sec']))}\n{text}\n"
        )
    if not blocks:
        return False
    path.write_text("\n".join(blocks), encoding="utf-8")
    return True


def _transition(clip: Dict[str, Any]) -> Tuple[str, float]:
    raw = clip.get("transition") or {}
    kind = str(raw.get("type") or "cut")
    if kind not in _XFADE:
        raise RenderError(f"渲染清单包含未允许的转场：{kind}")
    duration = float(raw.get("duration_sec") or (0.04 if kind == "cut" else 0.6))
    duration = max(0.04, min(1.5, duration, float(clip.get("duration_sec") or 1) / 2))
    return _XFADE[kind], round(duration, 3)


def _scale_filter(width: int, height: int) -> str:
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
    )


def render_project(
    user_id: str,
    memorial_id: str,
    project_dir: Path,
    manifest: Dict[str, Any],
) -> Dict[str, Any]:
    clips = manifest.get("clips") or []
    if not clips or any(clip.get("status") != "approved" for clip in clips):
        raise RenderError("所有镜头确认后才能合成")
    ffmpeg_bin = _ffmpeg()
    if not (shutil.which(ffmpeg_bin) or Path(ffmpeg_bin).is_file()):
        raise RenderError(f"未检测到 FFmpeg：{ffmpeg_bin}")

    width, height = _DIMENSIONS.get(str(manifest.get("aspect_ratio")), _DIMENSIONS["16:9"])
    fps = int(manifest.get("fps") or 25)
    if fps not in (24, 25, 30):
        fps = 25
    assets = _asset_paths(user_id, memorial_id)
    work_dir = project_dir / "render_work" / ("run_" + uuid.uuid4().hex[:12])
    output_dir = project_dir / "outputs"
    work_dir.mkdir(parents=True, exist_ok=False)
    output_dir.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, Any]] = []
    warnings: List[str] = []
    render_manifest: Dict[str, Any] = {
        "schema_version": 1,
        "status": "running",
        "project_id": manifest.get("project_id"),
        "memorial_id": memorial_id,
        "script_sha256": manifest.get("script_sha256"),
        "aspect_ratio": manifest.get("aspect_ratio"),
        "fps": fps,
        "commands": records,
        "warnings": warnings,
        "started_at": storage.now_iso(),
    }
    try:
        normalized: List[Path] = []
        for index, clip in enumerate(clips):
            asset_id = str(clip.get("asset_id") or "")
            if asset_id not in assets:
                raise RenderError(f"镜头素材已不存在或不属于当前人物：{asset_id}")
            asset, source_asset_path = assets[asset_id]
            duration = float(clip.get("duration_sec") or 0)
            if duration <= 0:
                raise RenderError(f"镜头时长无效：{clip.get('clip_id')}")
            outgoing = _transition(clip)[1] if index < len(clips) - 1 else 0.0
            prepared_duration = round(duration + outgoing, 3)
            output = work_dir / f"norm_{index:03d}.mp4"
            mode = clip.get("render_mode")
            if mode == "image_to_video":
                source = _within(project_dir, str(clip.get("video_path") or ""))
                vf = f"{_scale_filter(width, height)},fps={fps},tpad=stop_mode=clone:stop_duration={prepared_duration},trim=duration={prepared_duration},setpts=PTS-STARTPTS,format=yuv420p"
                command = [ffmpeg_bin, "-y", "-i", str(source), "-vf", vf, "-an", "-t", str(prepared_duration), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(output)]
            elif mode == "static":
                frames = max(1, int(math.ceil(prepared_duration * fps)))
                vf = (
                    f"{_scale_filter(width, height)},"
                    f"zoompan=z='min(zoom+0.00035,1.04)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps={fps},"
                    f"trim=duration={prepared_duration},setpts=PTS-STARTPTS,format=yuv420p"
                )
                command = [ffmpeg_bin, "-y", "-loop", "1", "-i", str(source_asset_path), "-vf", vf, "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(output)]
            elif mode == "source_video" and asset.get("kind") == "video":
                vf = f"{_scale_filter(width, height)},fps={fps},tpad=stop_mode=clone:stop_duration={prepared_duration},trim=duration={prepared_duration},setpts=PTS-STARTPTS,format=yuv420p"
                command = [ffmpeg_bin, "-y", "-i", str(source_asset_path), "-vf", vf, "-an", "-t", str(prepared_duration), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(output)]
            else:
                raise RenderError(f"镜头渲染模式无效：{mode}")
            _recorded_run(command, work_dir, records)
            if not output.is_file():
                raise RenderError(f"镜头标准化未生成文件：{clip.get('clip_id')}")
            normalized.append(output)

        timeline = work_dir / "timeline.mp4"
        if len(normalized) == 1:
            _recorded_run([ffmpeg_bin, "-y", "-i", str(normalized[0]), "-map", "0:v:0", "-an", "-c:v", "copy", str(timeline)], work_dir, records)
        else:
            command: List[str] = [ffmpeg_bin, "-y"]
            for path in normalized:
                command.extend(["-i", str(path)])
            filters = [f"[{index}:v]settb=AVTB,setpts=PTS-STARTPTS[v{index}]" for index in range(len(normalized))]
            previous = "v0"
            offset = float(clips[0]["duration_sec"])
            for index in range(1, len(normalized)):
                transition, seconds = _transition(clips[index - 1])
                label = f"x{index}"
                filters.append(f"[{previous}][v{index}]xfade=transition={transition}:duration={seconds}:offset={round(offset, 3)}[{label}]")
                previous = label
                offset += float(clips[index]["duration_sec"])
            command.extend(["-filter_complex", ";".join(filters), "-map", f"[{previous}]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(timeline)])
            _recorded_run(command, work_dir, records)

        total_duration = round(sum(float(clip["duration_sec"]) for clip in clips), 3)
        subtitle_path = work_dir / "subtitles.srt"
        has_subtitles = _write_subtitles(subtitle_path, clips)
        audio_events: List[Dict[str, Any]] = []
        bgm_ranges: Dict[str, List[float]] = {}
        for clip in clips:
            start = float(clip["start_sec"])
            duration = float(clip["duration_sec"])
            source_id = str(clip.get("asset_id") or "")
            if clip.get("use_source_audio") and clip.get("asset_kind") == "video":
                source_path = assets[source_id][1]
                if _has_audio(source_path, work_dir, records):
                    audio_events.append({"path": source_path, "start": start, "duration": duration, "volume": 0.9, "loop": False, "role": "source"})
                else:
                    warnings.append(f"{clip.get('clip_id')} 的真实视频没有可用原声音轨")
            for field, volume, role in (
                ("narration_audio_asset_id", 1.0, "narration"),
                ("original_audio_asset_id", 0.9, "original"),
            ):
                audio_id = str(clip.get(field) or "")
                if not audio_id:
                    continue
                entry = assets.get(audio_id)
                if not entry or entry[0].get("kind") != "audio":
                    raise RenderError(f"镜头音频不属于当前人物或类型错误：{audio_id}")
                audio_events.append({"path": entry[1], "start": start, "duration": duration, "volume": volume, "loop": False, "role": role})
            bgm_id = str(clip.get("bgm_audio_asset_id") or "")
            if bgm_id:
                entry = assets.get(bgm_id)
                if not entry or entry[0].get("kind") != "audio":
                    raise RenderError(f"镜头配乐不属于当前人物或类型错误：{bgm_id}")
                span = bgm_ranges.setdefault(bgm_id, [start, start + duration])
                span[0] = min(span[0], start)
                span[1] = max(span[1], start + duration)

        for bgm_id, span in bgm_ranges.items():
            audio_events.append({
                "path": assets[bgm_id][1],
                "start": span[0],
                "duration": round(span[1] - span[0], 3),
                "volume": 0.18,
                "loop": True,
                "role": "bgm",
            })

        final_name = f"final_{int(time.time())}_{uuid.uuid4().hex[:6]}.mp4"
        final_path = output_dir / final_name
        final_command: List[str] = [ffmpeg_bin, "-y", "-i", str(timeline)]
        for event in audio_events:
            if event["loop"]:
                final_command.extend(["-stream_loop", "-1"])
            final_command.extend(["-i", str(event["path"])])

        filters: List[str] = []
        video_map = "0:v:0"
        if has_subtitles:
            filters.append("[0:v]subtitles=subtitles.srt:force_style='FontName=Noto Sans CJK SC,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H66000000,BorderStyle=1,Outline=2,MarginV=36'[vout]")
            video_map = "[vout]"

        audio_map = ""
        if audio_events:
            audio_labels: List[str] = []
            for index, event in enumerate(audio_events, start=1):
                label = f"a{index}"
                delay = max(0, int(round(event["start"] * 1000)))
                filters.append(
                    f"[{index}:a]atrim=duration={event['duration']},asetpts=PTS-STARTPTS,"
                    f"volume={event['volume']},adelay={delay}:all=1[{label}]"
                )
                audio_labels.append(f"[{label}]")
            filters.append(
                "".join(audio_labels)
                + f"amix=inputs={len(audio_labels)}:duration=longest:dropout_transition=2,apad,atrim=duration={total_duration}[aout]"
            )
            audio_map = "[aout]"
        else:
            final_command.extend(["-f", "lavfi", "-t", str(total_duration), "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])
            audio_map = "1:a:0"
            if any(str(clip.get("narration") or "").strip() for clip in clips):
                warnings.append("脚本包含文字旁白，但未绑定旁白音频；本次将旁白文字作为字幕呈现")

        if filters:
            final_command.extend(["-filter_complex", ";".join(filters)])
        final_command.extend([
            "-map", video_map, "-map", audio_map, "-t", str(total_duration),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-movflags", "+faststart",
            str(final_path),
        ])
        _recorded_run(final_command, work_dir, records, timeout=900)
        if not final_path.is_file() or final_path.stat().st_size == 0:
            raise RenderError("FFmpeg 未生成最终视频")

        render_manifest.update({
            "status": "completed",
            "finished_at": storage.now_iso(),
            "output": str(final_path.relative_to(project_dir)).replace("\\", "/"),
            "clip_count": len(clips),
            "duration_sec": total_duration,
        })
        return {"relative_output": render_manifest["output"], "render_manifest": render_manifest}
    except Exception as exc:
        render_manifest.update({"status": "failed", "finished_at": storage.now_iso(), "error": str(exc)})
        if isinstance(exc, RenderError):
            exc.render_manifest = render_manifest
            raise
        raise RenderError(str(exc), render_manifest) from exc
    finally:
        # The exact commands and final output are persisted separately. Temporary
        # normalized clips are safe to remove and never include original assets.
        shutil.rmtree(work_dir, ignore_errors=True)
