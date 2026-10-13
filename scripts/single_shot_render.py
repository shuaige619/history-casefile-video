#!/usr/bin/env python3
"""Deterministic local independent-shot assembly, no model/network calls."""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from single_shot_assets import local, manifest, probe, sha, save, validate, json_sha

ROOT = Path.cwd()
PLAN = ROOT / "production.json"
FPS, W, H = 30, 1920, 1080
FONT = ""
FONT_SHA = ""
CACHE = ROOT / ".build/single-shot-cache"
OUT = ROOT / "outputs"
TERMS = ()
FONT_SIZE, CAP_Y, CAP_H, MAX_WIDTH = 52, 850, 230, 1607


def configure(project):
    global ROOT, PLAN, FPS, W, H, FONT, FONT_SHA, CACHE, OUT, TERMS, FONT_SIZE, CAP_Y, CAP_H, MAX_WIDTH
    ROOT = Path(project).resolve()
    PLAN = ROOT / "production.json"
    data = manifest(ROOT)
    m = data["meta"]
    FPS, W, H = m["fps"], m["width"], m["height"]
    if min(FPS, W, H) <= 0 or W % 2 or H % 2:
        raise ValueError("Invalid output geometry")
    font = m.get("fontPath") or os.environ.get("CASEFILE_FONT", "")
    candidates = [Path(font)] if font else [
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")]
    FONT = str(next((p if p.is_absolute() else ROOT / p for p in candidates
                     if (p if p.is_absolute() else ROOT / p).is_file()), ""))
    if not FONT:
        raise ValueError("Set meta.fontPath or CASEFILE_FONT to an installed, usable Chinese font")
    FONT_SHA = sha(FONT)
    CACHE, OUT = ROOT / ".build/single-shot-cache", ROOT / "outputs"
    TERMS = tuple(data.get("protectedTerms", [])) + ("因为", "所以", "但是", "没有", "不会", "不能", "不等于", "针对")
    landscape = W > H
    FONT_SIZE = m.get("captionFontSize", round(H * 52 / (1080 if landscape else 1920)))
    CAP_Y = m.get("captionY", round(H * (850 / 1080 if landscape else 1620 / 1920)))
    CAP_H, MAX_WIDTH = H - CAP_Y, round(W * .837)
    if not 0 < CAP_Y < H or FONT_SIZE < 8 or CAP_H < FONT_SIZE * 3:
        raise ValueError("Invalid caption safe-area configuration")
    caption_lines.cache_clear()
    return data


def run(args):
    result = __import__("subprocess").run([str(a) for a in args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:])
    return result.stdout


def caption_groups(captions):
    groups = []
    for original in captions:
        cue = {**original, "originalCueIds": [original["id"]]}
        if groups:
            p = groups[-1]
            if (p.get("paragraph") == cue.get("paragraph") and len(p["text"] + cue["text"]) <= 32
                and cue["startFrame"] - p["endFrame"] <= round(FPS * .12)
                and not re.search(r'[，。！？；：!?;:]([”」])?$', p["text"])):
                p["text"] += cue["text"]
                p["endFrame"] = cue["endFrame"]
                p["originalCueIds"] += cue["originalCueIds"]
                continue
        groups.append(cue)
    assert "".join(g["text"] for g in groups) == "".join(c["text"] for c in captions)
    return groups


@lru_cache(maxsize=2048)
def caption_lines(text):
    font = ImageFont.truetype(FONT, FONT_SIZE)
    if font.getlength(text) <= MAX_WIDTH:
        return (text,)
    forbidden = {i for word in TERMS if word for match in re.finditer(re.escape(word), text)
                 for i in range(match.start() + 1, match.end())}
    candidates = []
    for split in range(1, len(text)):
        left, right = text[:split], text[split:]
        if split in forbidden or right[0] in "，。！？；：、”」" or left[-1] in "“「":
            continue
        lw, rw = font.getlength(left), font.getlength(right)
        if max(lw, rw) > MAX_WIDTH:
            continue
        short = min(len(left.strip()), len(right.strip()))
        penalty = abs(lw - rw) + max(0, 5 - short) * FONT_SIZE * 4
        if left[-1] in "，；：。！？、”」":
            penalty -= FONT_SIZE * 4
        candidates.append((penalty, left, right))
    if not candidates:
        raise ValueError("Caption cannot fit two lines without splitting protected terms: " + text)
    _, left, right = min(candidates)
    assert left + right == text
    return left, right


def atomic_png(canvas, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".png", delete=False) as handle:
        temp = Path(handle.name)
    canvas.save(temp, format="PNG")
    os.replace(temp, path)


def caption_png(text):
    lines = caption_lines(text)
    config = [text, FONT, FONT_SHA, FONT_SIZE, W, CAP_H, MAX_WIDTH, TERMS, "single-caption-v1"]
    path = CACHE / "captions" / (json_sha(config)[:20] + ".png")
    if path.exists():
        return path
    canvas = Image.new("RGBA", (W, CAP_H))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT, FONT_SIZE)
    spacing = round(FONT_SIZE * 1.346)
    top = round(CAP_H * .673) - spacing * len(lines)
    width = max(font.getlength(line) for line in lines) + round(FONT_SIZE * .92)
    bottom = min(CAP_H - 2, round(CAP_H * .727))
    draw.rectangle(((W - width) / 2, top - round(FONT_SIZE * .23), (W + width) / 2, bottom), fill=(18, 14, 10, 224))
    for i, line in enumerate(lines):
        draw.text(((W - font.getlength(line)) / 2, top + i * spacing), line, font=font,
                  fill=(255, 250, 240, 255), anchor="lt")
    atomic_png(canvas, path)
    return path


def annotation_png(label):
    path = CACHE / "annotations" / (json_sha([label, FONT, FONT_SHA])[:20] + ".png")
    if path.exists():
        return path
    size = label.get("fontSize", round(H * .075))
    font = ImageFont.truetype(FONT, size)
    lines = list(label["text"]) if label.get("vertical") else [label["text"]]
    gap = round(size / 6)
    canvas = Image.new("RGBA", (round(max(font.getlength(line) for line in lines)) + 24,
                               len(lines) * size + (len(lines) - 1) * gap + 24))
    draw = ImageDraw.Draw(canvas)
    for i, line in enumerate(lines):
        draw.text((12, 12 + i * (size + gap)), line, font=font, anchor="lt",
                  fill=tuple(label.get("color", [73, 52, 38, 255])))
    atomic_png(canvas, path)
    return path


def make_jobs(data, start, end):
    captions = caption_groups(data["captions"])
    jobs = []
    for s in data["shots"]:
        if s["endFrame"] <= start or s["startFrame"] >= end:
            continue
        v = s.get("video")
        use_video = bool(v and v.get("review") == "accepted")
        a, b = max(start, s["startFrame"]), min(end, s["endFrame"])
        rate = v["duration"] / ((s["endFrame"] - s["startFrame"]) / FPS) if use_video else 1.
        job = {"id": s["id"], "startFrame": a, "endFrame": b, "asset": v["asset"] if use_video else s["asset"],
               "video": use_video, "rate": rate, "trimFrames": a - s["startFrame"],
               "captions": [{**c, "from": max(a, c["startFrame"]) - a, "to": min(b, c["endFrame"]) - a}
                            for c in captions if c["startFrame"] < b and c["endFrame"] > a]}
        labels = []
        for label in s.get("labels", []):
            lo, hi = s["startFrame"] + label["startOffsetFrames"], s["startFrame"] + label["endOffsetFrames"]
            if not s["startFrame"] <= lo < hi <= s["endFrame"] or use_video:
                raise ValueError("Invalid or untracked prop-label clock: " + s["id"])
            if lo < b and hi > a:
                labels.append({**label, "from": max(a, lo) - a, "to": min(b, hi) - a})
        if labels:
            job["labels"] = labels
        jobs.append(job)
    if sum(j["endFrame"] - j["startFrame"] for j in jobs) != end - start:
        raise ValueError("Incomplete render interval")
    return jobs, captions


def render_one(job):
    source = local(ROOT, job["asset"])
    frames = job["endFrame"] - job["startFrame"]
    fingerprint = [job, sha(source), FONT_SHA, FPS, W, H, FONT_SIZE, CAP_Y, TERMS, "single-render-v1"]
    target = CACHE / (job["id"] + "-" + json_sha(fingerprint)[:16] + ".mp4")
    CACHE.mkdir(parents=True, exist_ok=True)
    if target.exists():
        try:
            v = next(s for s in probe(target)["streams"] if s["codec_type"] == "video")
            if (int(v.get("nb_frames", 0)), v["width"], v["height"]) == (frames, W, H):
                return {**job, "file": str(target), "cached": True}
        except (ValueError, KeyError, StopIteration, __import__("subprocess").CalledProcessError):
            pass
        target.rename(target.with_name(target.stem + ".invalid-" + str(time.time_ns()) + ".mp4"))
    pending = target.with_name(target.stem + ".partial-" + str(os.getpid()) + ".mp4")
    args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    if job["video"]:
        if job["trimFrames"]:
            args += ["-ss", str(job["trimFrames"] / FPS * job["rate"])]
    else:
        args += ["-loop", "1", "-framerate", str(FPS)]
    args += ["-i", str(source)]
    for c in job["captions"]:
        args += ["-loop", "1", "-framerate", str(FPS), "-i", str(caption_png(c["text"]))]
    for label in job.get("labels", []):
        args += ["-loop", "1", "-framerate", str(FPS), "-i", str(annotation_png(label))]
    filters = [f'[0:v]setpts=(PTS-STARTPTS)/{job["rate"]:.9f},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,'
               f'crop={W}:{H},fps={FPS},setsar=1,format=yuv420p,setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709[base]']
    current = "base"
    for index, c in enumerate(job["captions"], 1):
        out = "cap" + str(index)
        filters.append(f"[{current}][{index}:v]overlay=0:{CAP_Y}:enable='gte(n,{c['from']})*lt(n,{c['to']})':format=auto[{out}]")
        current = out
    for index, label in enumerate(job.get("labels", []), len(job["captions"]) + 1):
        out = "label" + str(index)
        filters.append(f"[{current}][{index}:v]overlay={label['x']}:{label['y']}:enable='gte(n,{label['from']})*lt(n,{label['to']})':format=auto[{out}]")
        current = out
    filters.append(f"[{current}]format=yuv420p[final]")
    args += ["-filter_complex", ";".join(filters), "-filter_complex_threads", "1", "-map", "[final]",
             "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-threads", "2",
             "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
             "-video_track_timescale", "15360", str(pending)]
    run(args)
    v = next(s for s in probe(pending)["streams"] if s["codec_type"] == "video")
    if int(v.get("nb_frames", 0)) != frames:
        raise ValueError("Shot frame count mismatch: " + job["id"])
    os.replace(pending, target)
    return {**job, "file": str(target), "cached": False}


def srt_time(frame):
    ms = round(frame / FPS * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("project"); ap.add_argument("--name", default="final-video.mp4")
    ap.add_argument("--from-frame", type=int, default=0); ap.add_argument("--until-frame", type=int)
    ap.add_argument("--workers", type=int, default=4); ap.add_argument("--prepare-only", action="store_true")
    ap.add_argument("--draft", action="store_true", help="Local still preview while video approval/results are pending; never final")
    a = ap.parse_args()
    data = configure(a.project)
    start, end = a.from_frame, a.until_frame or data["meta"]["durationFrames"]
    if not 0 <= start < end <= data["meta"]["durationFrames"]:
        raise ValueError("Invalid render interval")
    validate(ROOT, allow_static_draft=a.draft, until_frame=end)
    jobs, captions = make_jobs(data, start, end)
    report = {"status": "prepared", "startFrame": start, "endFrame": end, "seconds": (end - start) / FPS,
              "fps": FPS, "width": W, "height": H, "shots": len(jobs), "sourcePlanSha256": json_sha(data),
              "sourceAudioSha256": data["meta"]["audioSha256"], "audioTempo": 1.0, "draft": a.draft,
              "fullTimelineCovered": start == 0 and end == data["meta"]["durationFrames"],
              "fullFilmComplete": False, "visualQC": "pending", "jobs": jobs}
    if a.prepare_only:
        print(json.dumps({k: v for k, v in report.items() if k != "jobs"}, ensure_ascii=False))
        return
    if Path(a.name).name != a.name or not a.name.endswith(".mp4"):
        raise ValueError("Use a simple .mp4 output name")
    target = OUT / a.name
    if target.exists():
        raise ValueError("Output already exists; choose a new versioned name")
    OUT.mkdir(parents=True, exist_ok=True)
    done = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(a.workers, 4))) as pool:
        for future in concurrent.futures.as_completed([pool.submit(render_one, job) for job in jobs]):
            done.append(future.result())
            print(f"Finished {len(done)}/{len(jobs)} shots", flush=True)
    done.sort(key=lambda j: j["startFrame"])
    concat = OUT / (target.stem + ".ffconcat")
    concat.write_text("ffconcat version 1.0\n" + "".join("file '" + j["file"].replace("'", "'\\''") + "'\n"
                                                       "duration " + f"{(j['endFrame'] - j['startFrame']) / FPS:.12f}" + "\n" for j in done), encoding="utf-8")
    pending = target.with_name(target.stem + ".partial-" + str(os.getpid()) + ".mp4")
    run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", concat,
         "-ss", f"{start / FPS:.9f}", "-i", local(ROOT, data["meta"]["audio"]),
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-t", f"{(end - start) / FPS:.9f}", "-movflags", "+faststart", pending])
    info = probe(pending)
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    if int(vs.get("nb_frames", 0)) != end - start or abs(float(info["format"]["duration"]) - (end - start) / FPS) > .1:
        raise ValueError("Output frame count/duration mismatch")
    os.replace(pending, target)
    srt = []
    for c in captions:
        if c["startFrame"] < end and c["endFrame"] > start:
            srt.append(f"{len(srt)+1}\n{srt_time(max(start,c['startFrame'])-start)} --> {srt_time(min(end,c['endFrame'])-start)}\n{c['text']}\n")
    target.with_suffix(".srt").write_text("\n".join(srt), encoding="utf-8")
    report.update(status="rendered-pending-qc", output=str(target), outputSha256=sha(target), jobs=done, probe=info)
    save(target.with_name(target.stem + "-report.json"), report)
    print(json.dumps({k: v for k, v in report.items() if k not in ("jobs", "probe")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
