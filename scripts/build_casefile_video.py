#!/usr/bin/env python3
import argparse
import json
import re
import shlex
import subprocess
from pathlib import Path


def run(command: list[str]) -> None:
    print("RUN", " ".join(shlex.quote(x) for x in command), flush=True)
    subprocess.run(command, check=True)


def probe_duration(path: Path) -> float:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ], check=True, text=True, capture_output=True)
    return float(result.stdout.strip())


def has_ffmpeg_filter(name: str) -> bool:
    result = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], text=True, capture_output=True, check=True)
    return any(line.split()[1:2] == [name] for line in result.stdout.splitlines() if len(line.split()) > 1)


def escaped_subtitle_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def parse_time(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, milliseconds = rest.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000


def parse_srt(path: Path) -> dict[int, dict]:
    pattern = re.compile(
        r"(?ms)^(\d+)\n(\d\d:\d\d:\d\d,\d{3}) --> (\d\d:\d\d:\d\d,\d{3})\n(.*?)(?=\n\n|\Z)"
    )
    cues = {}
    for match in pattern.finditer(path.read_text(encoding="utf-8").strip()):
        index = int(match.group(1))
        cues[index] = {
            "start": parse_time(match.group(2)),
            "end": parse_time(match.group(3)),
            "text": " ".join(line.strip() for line in match.group(4).splitlines()).strip(),
        }
    if not cues:
        raise SystemExit(f"No subtitle cues parsed from {path}")
    return cues


def wrap_caption(draw, text: str, font, max_width: int) -> list[str]:
    lines = []
    current = ""
    for char in text:
        candidate = current + char
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > 2 or (len(lines) == 2 and len(lines[1]) <= 3):
        midpoint = (len(text) + 1) // 2
        candidates = [i for i, char in enumerate(text) if char in "，；：、" and len(text) * 0.28 <= i <= len(text) * 0.72]
        split = min(candidates, key=lambda i: abs(i - midpoint), default=midpoint - 1) + 1
        lines = [text[:split], text[split:]]
    return [line for line in lines if line]


def render_caption(path: Path, text: str, video_width: int, video_height: int) -> tuple[int, int]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise SystemExit(
            "FFmpeg lacks libass and Pillow is unavailable. Run this builder with a Python environment containing Pillow; "
            "a soft subtitle track alone is not an acceptable publishable fallback."
        ) from exc
    caption_width = round(video_width * 0.89)
    caption_height = round(video_height * 0.14)
    canvas = Image.new("RGBA", (caption_width, caption_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas, "RGBA")
    font_path = "/System/Library/Fonts/STHeiti Medium.ttc"
    caption_font = ImageFont.truetype(font_path, size=max(28, round(video_width * 0.057)))
    lines = wrap_caption(draw, text, caption_font, round(caption_width * 0.88))
    line_text = "\n".join(lines)
    spacing = max(8, round(video_width * 0.014))
    bbox = draw.multiline_textbbox((0, 0), line_text, font=caption_font, spacing=spacing, align="center", stroke_width=2)
    text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    box_width = min(caption_width - 12, text_width + round(video_width * 0.08))
    box_height = min(caption_height - 10, text_height + round(video_width * 0.052))
    left = (caption_width - box_width) // 2
    top = (caption_height - box_height) // 2
    draw.rounded_rectangle(
        (left, top, left + box_width, top + box_height),
        radius=max(12, round(video_width * 0.025)), fill=(10, 9, 8, 190),
        outline=(255, 244, 220, 40), width=2,
    )
    draw.multiline_text(
        (caption_width // 2, caption_height // 2), line_text, font=caption_font,
        fill=(255, 252, 244, 255), anchor="mm", align="center", spacing=spacing,
        stroke_width=max(2, round(video_width * 0.004)), stroke_fill=(0, 0, 0, 230),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)
    return caption_width, caption_height


def motion_filter(motion: str, width: int, height: int, fps: int, seconds: float) -> str:
    frames = max(1, round(seconds * fps))
    base = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
    if motion == "static":
        return f"{base},fps={fps},format=yuv420p"
    if motion == "zoom_out":
        z = "if(eq(on,0),1.10,max(1.0,zoom-0.00035))"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    elif motion == "pan_left":
        z = "1.08"
        x = f"(iw-iw/zoom)*(1-on/{frames})"
        y = "ih/2-(ih/zoom/2)"
    elif motion == "pan_right":
        z = "1.08"
        x = f"(iw-iw/zoom)*(on/{frames})"
        y = "ih/2-(ih/zoom/2)"
    else:
        z = "min(zoom+0.00035,1.10)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    return f"{base},zoompan=z='{z}':x='{x}':y='{y}':d=1:s={width}x{height}:fps={fps},format=yuv420p"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a narrated 9:16 historical casefile pilot from storyboard images.")
    parser.add_argument("project_directory")
    parser.add_argument("--preset", default="veryfast")
    parser.add_argument("--crf", type=int, default=22)
    parser.add_argument("--no-subtitles", action="store_true")
    parser.add_argument("--allow-cycle-diagnostic", action="store_true", help="Explicitly allow scene cycling for a non-reviewable diagnostic draft.")
    args = parser.parse_args()

    root = Path(args.project_directory).expanduser().resolve()
    manifest = json.loads((root / "storyboard.json").read_text(encoding="utf-8"))
    resolution = manifest.get("resolution", {})
    width = int(resolution.get("width", 1080))
    height = int(resolution.get("height", 1920))
    fps = int(resolution.get("fps", 30))
    scenes = manifest.get("scenes", [])
    if not scenes:
        raise SystemExit("storyboard.json contains no scenes")

    semantic_required = {"narration_summary", "visual_goal", "visual_mode", "visual_family", "match_level", "match_reason", "trigger_terms"}
    incomplete_semantics = [scene.get("id", f"scene-{index + 1}") for index, scene in enumerate(scenes) if not semantic_required.issubset(scene)]
    if incomplete_semantics:
        raise SystemExit(f"Semantic storyboard fields are required; incomplete scenes: {', '.join(incomplete_semantics[:8])}")
    image_paths = [scene.get("image", "") for scene in scenes if scene.get("image")]
    repeated_paths = sorted({path for path in image_paths if image_paths.count(path) > 1})
    if repeated_paths and not args.allow_cycle_diagnostic:
        raise SystemExit(f"Reviewed builds cannot reuse image/video files: {', '.join(repeated_paths[:8])}")
    external_families = [
        scene.get("visual_family", "") for scene in scenes
        if scene.get("image") and str(scene.get("match_level", "")).startswith(("A_", "B_"))
    ]
    repeated_families = sorted({family for family in external_families if family and external_families.count(family) > 1})
    if repeated_families and not args.allow_cycle_diagnostic:
        raise SystemExit(f"Reviewed builds cannot repeat external visual families: {', '.join(repeated_families[:8])}")
    phrase_failures = [
        scene.get("id", "") for scene in scenes
        if scene.get("image")
        and not any(term and term in scene.get("narration_summary", "") for term in scene.get("trigger_terms", []))
    ]
    if phrase_failures:
        raise SystemExit(f"Image scenes must match an exact spoken trigger phrase: {', '.join(phrase_failures[:8])}")
    disclosure_failures = [
        scene.get("id", "") for scene in scenes
        if scene.get("match_level") in {"B_CONTEXT", "B_LATER_IMAGE"}
        and not any(term in scene.get("source_note", "") for term in ("不是", "不当作", "not "))
    ]
    if disclosure_failures:
        raise SystemExit(f"Context/later-image scenes need a clear disclosure: {', '.join(disclosure_failures[:8])}")

    narration = root / manifest.get("narration", "assets/audio/narration.aiff")
    if not narration.exists():
        raise SystemExit(f"Missing narration: {narration}")
    audio_duration = probe_duration(narration)

    build = root / ".build"
    clip_dir = build / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)
    subtitle = root / manifest.get("subtitles", "subtitles/narration.srt")
    native_subtitles = bool(subtitle.exists() and not args.no_subtitles and has_ffmpeg_filter("subtitles"))
    pillow_subtitles = bool(subtitle.exists() and not args.no_subtitles and not native_subtitles)
    cues: dict[int, dict] = {}
    caption_dir = build / "captions"
    caption_width = caption_height = 0
    if pillow_subtitles:
        required_fields = {"start_seconds", "end_seconds", "subtitle_cues", "narration_summary"}
        incomplete = [scene.get("id", f"scene-{index+1}") for index, scene in enumerate(scenes) if not required_fields.issubset(scene)]
        if incomplete:
            raise SystemExit(
                "FFmpeg lacks libass. Pillow caption fallback requires semantic storyboard fields "
                f"{sorted(required_fields)}; incomplete scenes: {', '.join(incomplete[:8])}"
            )
        cues = parse_srt(subtitle)
        assigned = [cue_id for scene in scenes for cue_id in scene["subtitle_cues"]]
        if len(assigned) != len(set(assigned)) or set(assigned) != set(cues):
            missing = sorted(set(cues) - set(assigned))
            duplicates = sorted(cue_id for cue_id in set(assigned) if assigned.count(cue_id) > 1)
            raise SystemExit(f"Subtitle cue coverage must be exact; missing={missing[:10]} duplicates={duplicates[:10]}")
        for cue_id, cue in cues.items():
            caption_width, caption_height = render_caption(caption_dir / f"{cue_id:04d}.png", cue["text"], width, height)

    rendered: list[tuple[Path, float]] = []
    for index, scene in enumerate(scenes, 1):
        image = root / scene["image"]
        if not image.exists():
            raise SystemExit(f"Missing scene image: {image}")
        seconds = float(scene.get("duration_seconds", 12.0))
        motion = scene.get("motion", ["zoom_in", "zoom_out", "pan_left", "pan_right"][index % 4])
        clip = clip_dir / f"scene-{index:03d}.mp4"
        vf = motion_filter(motion, width, height, fps, seconds)
        if pillow_subtitles:
            scene_start = float(scene["start_seconds"])
            scene_end = float(scene["end_seconds"])
            scene_cues = [cues[cue_id] | {"id": cue_id} for cue_id in scene["subtitle_cues"]]
            for cue in scene_cues:
                if cue["start"] < scene_start - 0.002 or cue["end"] > scene_end + 0.002:
                    raise SystemExit(f"Subtitle cue {cue['id']} falls outside scene {scene.get('id', index)}")
            command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-stats", "-y", "-loop", "1", "-framerate", str(fps), "-i", str(image)]
            for cue in scene_cues:
                command += ["-loop", "1", "-framerate", str(fps), "-i", str(caption_dir / f"{cue['id']:04d}.png")]
            chains = [f"[0:v]{vf}[bg]"]
            previous = "bg"
            overlay_x = (width - caption_width) // 2
            overlay_y = round(height * 0.723)
            for input_index, cue in enumerate(scene_cues, 1):
                output_label = f"v{input_index}"
                relative_start = max(0.0, cue["start"] - scene_start)
                relative_end = min(seconds, cue["end"] - scene_start)
                chains.append(
                    f"[{previous}][{input_index}:v]overlay=x={overlay_x}:y={overlay_y}:"
                    f"enable='between(t,{relative_start:.3f},{relative_end:.3f})'[{output_label}]"
                )
                previous = output_label
            command += [
                "-filter_complex", ";".join(chains), "-map", f"[{previous}]", "-t", f"{seconds:.3f}",
                "-an", "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
                "-pix_fmt", "yuv420p", str(clip),
            ]
            run(command)
        else:
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-stats", "-y", "-loop", "1", "-framerate", str(fps), "-i", str(image), "-t", f"{seconds:.3f}", "-vf", vf, "-an", "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf), "-pix_fmt", "yuv420p", str(clip)])
        rendered.append((clip, seconds))

    visual_duration = sum(seconds for _, seconds in rendered)
    if not args.allow_cycle_diagnostic and abs(visual_duration - audio_duration) > 0.15:
        raise SystemExit(
            f"Reviewed builds require exact visual coverage; storyboard={visual_duration:.3f}s narration={audio_duration:.3f}s. "
            "Fix scene timing instead of cycling assets."
        )
    sequence: list[Path] = [clip for clip, _ in rendered]
    if args.allow_cycle_diagnostic and visual_duration < audio_duration:
        accumulated = visual_duration
        while accumulated < audio_duration:
            for clip, seconds in rendered:
                sequence.append(clip)
                accumulated += seconds
                if accumulated >= audio_duration:
                    break

    concat_file = build / "concat.txt"
    lines = []
    for path in sequence:
        escaped = str(path).replace("'", "'\\''")
        lines.append(f"file '{escaped}'\n")
    concat_file.write_text("".join(lines), encoding="utf-8")
    visuals = build / "visuals.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-stats", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(visuals)])

    output = root / "outputs" / "final-video.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    vf = []
    subtitle_input = []
    subtitle_output = []
    if native_subtitles:
        style = "FontName=PingFang SC,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H90000000,BorderStyle=3,Outline=1,Shadow=0,MarginV=90,Alignment=2"
        vf = ["-vf", f"subtitles='{escaped_subtitle_path(subtitle)}':force_style='{style}'"]
    elif pillow_subtitles:
        subtitle_input = ["-i", str(subtitle)]
        subtitle_output = ["-map", "2:0", "-c:s", "mov_text", "-metadata:s:s:0", "language=zho", "-disposition:s:0", "default"]
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-stats", "-y", "-i", str(visuals), "-i", str(narration), *subtitle_input, *vf,
        "-filter:a", "loudnorm=I=-16:TP=-3:LRA=11", "-map", "0:v:0", "-map", "1:a:0",
        *subtitle_output,
        "-t", f"{audio_duration:.3f}", "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)
    ])
    print(output)


if __name__ == "__main__":
    main()
