#!/usr/bin/env python3
"""Local manifest, immutable baselines, asset review and video-approval checks.
This module NEVER submits a generation request or contacts a remote service.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import fcntl
from functools import wraps
from pathlib import Path

SCHEMA = "history-single-v1"


def serialized(fn):
    @wraps(fn)
    def wrapped(root, *args, **kwargs):
        folder = Path(root) / ".build"
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / "manifest.lock").open("a") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            return fn(root, *args, **kwargs)
    return wrapped


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        pending = handle.name
    os.replace(pending, path)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def json_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def local(root, relative):
    path = (Path(root) / relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError("Asset path escapes project: " + relative)
    return path


def probe(path):
    return json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ]))


def manifest(root):
    data = read(Path(root) / "production.json")
    if data["meta"].get("schema") != SCHEMA:
        raise ValueError("Unsupported manifest; do not overwrite or silently migrate a legacy project")
    return data


@serialized
def init(root, title):
    root = Path(root).resolve()
    if (root / "production.json").exists():
        manifest(root)
        return {"status": "existing-project-preserved", "project": str(root)}
    if any((root / name).exists() for name in ("storyboard.json", "storyboard-v8-single.json")):
        raise ValueError("Existing legacy project detected; use its original workflow without reinitializing")
    for folder in ("assets/images", "assets/clips", "assets/audio", "subtitles", "outputs", ".build"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    meta = {"schema": SCHEMA, "title": title, "durationMode": "natural",
            "durationHintMinutes": 25, "durationFrames": 0, "fps": 30, "width": 1920, "height": 1080,
            "orientation": "landscape", "aspectRatio": "16:9",
            "audio": "assets/audio/narration.m4a", "audioTempo": 1.0, "fontPath": "",
            "minimumImagePixels": [1280, 720], "minimumVideoPixels": [1280, 720],
            "tts": {"provider": "bailian", "model": "qwen3-tts-instruct-flash", "voice": "Vincent", "voiceName": "田叔"}}
    save(root / "production.json", {"meta": meta, "protectedTerms": [], "chapters": [], "captions": [], "shots": []})
    save(root / "video-approvals.json", {"batches": []})
    for name, value in {
        "source-ledger.json": {"topic": title, "sources": [], "claims": []},
        "story-architecture.json": {"centralQuestion": "", "causalChain": [], "chapters": []},
        "hook-ledger.json": {"hooks": []},
    }.items():
        if not (root / name).exists():
            save(root / name, value)
    for name, text in {
        "brief.md": "# " + title + "\n\n自然说书时长；16:9横屏独立手绘画面；视频模型生成先取得本批明确批准。\n",
        "progress.md": "# 制作进度\n\n阶段：研究。尚未完成成片；无已批准的视频生成批次。\n",
        "narration.txt": "",
    }.items():
        if not (root / name).exists():
            (root / name).write_text(text, encoding="utf-8")
    return {"status": "initialized", "project": str(root)}


@serialized
def freeze(root):
    data = manifest(root)
    meta = data["meta"]
    audio = local(root, meta["audio"])
    audio_hash = sha(audio)
    if not data["captions"]:
        raise ValueError("Create captions from the final paced audio before freezing")
    if meta.get("audioSha256") and meta["audioSha256"] != audio_hash:
        raise ValueError("Frozen audio changed; make an explicit new version/baseline, preserving the old one")
    info = probe(audio)
    if not any(s["codec_type"] == "audio" for s in info["streams"]):
        raise ValueError("No narration audio stream")
    total = round(float(info["format"]["duration"]) * meta["fps"])
    if max(c["endFrame"] for c in data["captions"]) > total:
        raise ValueError("Captions extend beyond the measured audio")
    snapshot = "subtitles/source-captions-" + json_sha(data["captions"])[:16] + ".json"
    if meta.get("captionSource") and read(local(root, meta["captionSource"])) != data["captions"]:
        raise ValueError("Frozen captions changed; version the baseline explicitly instead of concealing changes")
    save(local(root, snapshot), data["captions"])
    meta.update(audioSha256=audio_hash, durationFrames=total, captionSource=snapshot,
                captionSourceSha256=sha(local(root, snapshot)), audioTempo=1.0)
    save(Path(root) / "production.json", data)
    return {"status": "frozen", "durationFrames": total, "audioTempo": 1.0, "captionSource": snapshot}


def video_spec(shot):
    plan = shot.get("videoPlan") or {}
    required = ("provider", "model", "prompt", "durationSeconds", "resolution")
    if any(not plan.get(k) for k in required):
        raise ValueError("Video plan is incomplete: " + shot["id"])
    return {"id": shot["id"], "provider": plan["provider"], "model": plan["model"],
            "parametersSha256": json_sha(plan),
            "promptSha256": hashlib.sha256(plan["prompt"].encode()).hexdigest(),
            "sourceImageSha256": shot["imageSource"]["sha256"],
            "durationSeconds": plan["durationSeconds"], "resolution": plan["resolution"]}


@serialized
def draft_batch(root, batch_id, shot_ids):
    data = manifest(root)
    ledger = read(Path(root) / "video-approvals.json")
    if any(b["id"] == batch_id for b in ledger["batches"]):
        raise ValueError("Batch ID already exists; do not overwrite prior approval")
    selected = [next(s for s in data["shots"] if s["id"] == sid) for sid in shot_ids]
    if len(shot_ids) != len(set(shot_ids)):
        raise ValueError("Duplicate shot IDs in batch")
    jobs = []
    for shot in selected:
        if shot.get("imageReview") != "accepted" or sha(local(root, shot["asset"])) != shot["imageSource"]["sha256"]:
            raise ValueError("Reference image has not passed review: " + shot["id"])
        jobs.append({**video_spec(shot), "maxAttempts": 1, "attempts": []})
    batch = {"id": batch_id, "status": "pending", "jobs": jobs,
             "estimatedCost": "unknown", "userConfirmation": None}
    ledger["batches"].append(batch)
    save(Path(root) / "video-approvals.json", ledger)
    return batch


def check_approval(root, shot, batch_id, for_submit=True):
    batches = read(Path(root) / "video-approvals.json")["batches"]
    batch = next((b for b in batches if b["id"] == batch_id), None)
    if not batch or batch.get("status") != "approved":
        raise ValueError("VIDEO APPROVAL REQUIRED for this batch")
    confirmation = batch.get("userConfirmation") or {}
    if not isinstance(confirmation, dict) or not confirmation.get("text") or not confirmation.get("source"):
        raise ValueError("Approval must record a real user response and its conversation source")
    spec = video_spec(shot)
    job = next((j for j in batch["jobs"] if j["id"] == shot["id"]), None)
    if not job or any(job.get(k) != value for k, value in spec.items()):
        raise ValueError("Approval does not cover these exact image/prompt/model/duration parameters")
    if sha(local(root, shot["asset"])) != spec["sourceImageSha256"]:
        raise ValueError("Reference image changed after approval")
    if for_submit:
        attempts = job.get("attempts", [])
        if any(a.get("status") in ("submitting", "unknown", "running") for a in attempts):
            raise ValueError("Submission unresolved; query the existing job, never submit again")
        if len(attempts) >= job.get("maxAttempts", 1):
            raise ValueError("Approved attempt limit reached; request a new bounded approval")
    return job


@serialized
def register(root, sid, source, kind, review, note, origin, batch_id=None):
    from PIL import Image
    data = manifest(root)
    shot = next(s for s in data["shots"] if s["id"] == sid)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", sid):
        raise ValueError("Use safe ASCII shot IDs")
    source = Path(source).resolve()
    digest = sha(source)
    if review == "accepted" and not note.strip():
        raise ValueError("Actual visual inspection note is required; generation is not acceptance")
    if kind == "image":
        with Image.open(source) as im:
            w, h = im.size
        duration = None
    else:
        info = probe(source)
        stream = next(s for s in info["streams"] if s["codec_type"] == "video")
        w, h = stream["width"], stream["height"]
        duration = float(stream.get("duration") or info["format"]["duration"])
        if origin == "generated-video":
            check_approval(root, shot, batch_id, for_submit=False)
    minimum = data["meta"]["minimumImagePixels" if kind == "image" else "minimumVideoPixels"]
    if w < minimum[0] or h < minimum[1]:
        raise ValueError("Insufficient native pixels")
    aspect_tolerance = 1e-6 if data["meta"].get("strictAssetAspectRatio") else .02
    if abs(w / h - data["meta"]["width"] / data["meta"]["height"]) > aspect_tolerance:
        raise ValueError("Source aspect ratio differs from the intended single frame")
    key = "imageSource" if kind == "image" else "video"
    if any(s["id"] != sid and (s.get(key) or {}).get("sha256") == digest for s in data["shots"]):
        raise ValueError("Identical asset already assigned to another shot")
    suffix = source.suffix.lower() if kind == "image" else ".mp4"
    rel = "assets/" + ("images/" if kind == "image" else "clips/") + sid.lower() + "-" + digest[:16] + suffix
    dest = local(root, rel)
    if dest.exists() and sha(dest) != digest:
        raise ValueError("Destination collision")
    if source != dest:
        shutil.copy2(source, dest)
    previous = shot.get(key)
    if previous and previous.get("sha256") != digest:
        shot.setdefault(key + "History", []).append(previous)
    record = dict(previous or {}) if previous and previous.get("sha256") == digest else {}
    record.update(asset=rel, sourcePath=str(source), sha256=digest, nativeWidth=w, nativeHeight=h,
                  layout="single-full-frame", review=review, reviewNotes=note, origin=origin)
    if duration is not None:
        record["duration"] = duration
    if kind == "video" and origin == "generated-video":
        record.update(approvalBatch=batch_id, sourceImageSha256=shot["imageSource"]["sha256"])
    shot[key] = record
    if kind == "image":
        shot.update(asset=rel, imageReview=review)
    save(Path(root) / "production.json", data)
    return {"id": sid, "asset": rel, "review": review}


def validate(root, allow_static_draft=False, until_frame=None):
    from PIL import Image
    data = manifest(root)
    meta = data["meta"]
    requested_end = until_frame or meta["durationFrames"]
    if not 0 < requested_end <= meta["durationFrames"]:
        raise ValueError("Invalid requested validation interval")
    if meta.get("audioTempo") != 1.0 or meta.get("durationFrames", 0) <= 0:
        raise ValueError("A measured, frozen natural-speed narration is required")
    if sha(local(root, meta["audio"])) != meta.get("audioSha256"):
        raise ValueError("Frozen narration hash mismatch")
    source = local(root, meta["captionSource"])
    if sha(source) != meta.get("captionSourceSha256") or read(source) != data["captions"]:
        raise ValueError("Original caption characters/timing changed after freezing")
    cues = data["captions"]
    ids = [c["id"] for c in cues]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate caption ID")
    last_cue = 0
    for cue in cues:
        if not cue["text"] or not 0 <= cue["startFrame"] < cue["endFrame"] <= meta["durationFrames"] or cue["startFrame"] < last_cue:
            raise ValueError("Invalid or overlapping caption clock")
        last_cue = cue["endFrame"]
    narration = Path(root) / "narration.txt"
    if "".join(narration.read_text(encoding="utf-8").splitlines()) != "".join(c["text"] for c in cues):
        raise ValueError("Caption text does not preserve narration.txt")
    used, hashes, roots, last, shot_ids = [], set(), set(), 0, set()
    for shot in data["shots"]:
        sid = shot["id"]
        if sid in shot_ids or not re.fullmatch(r"[A-Za-z0-9_-]+", sid):
            raise ValueError("Invalid or duplicate shot ID")
        shot_ids.add(sid)
        if shot["startFrame"] != last or shot["endFrame"] <= last:
            raise ValueError("Shot gap/overlap: " + sid)
        last = shot["endFrame"]
        if shot.get("layout") != "single-full-frame" or "panel" in shot:
            raise ValueError("Grid/quadrant layouts are not formal assets")
        for field in ("visualGoal", "matchReason", "artDirection"):
            if not shot.get(field, "").strip():
                raise ValueError("Missing semantic mapping " + field + ": " + sid)
        selected = [c for c in cues if c["id"] in shot["cueIds"]]
        if len(selected) != len(shot["cueIds"]) or any(c["startFrame"] < shot["startFrame"] or c["endFrame"] > shot["endFrame"] for c in selected):
            raise ValueError("Each original caption must be fully bound to one shot")
        if "".join(c["text"] for c in selected) != shot.get("narration", ""):
            raise ValueError("Shot narration does not match its exact spoken cues: " + sid)
        used += shot["cueIds"]
        if shot["startFrame"] >= requested_end:
            continue
        if shot.get("imageReview") != "accepted":
            raise ValueError("Unreviewed image: " + sid)
        if shot["asset"] != shot["imageSource"]["asset"]:
            raise ValueError("Rendered image differs from reviewed image: " + sid)
        entries = [shot["imageSource"]]
        video = shot.get("video")
        if video and video.get("review") == "accepted":
            entries.append(video)
            if shot.get("labels"):
                raise ValueError("Moving video labels require a separate tracked composition")
            if video.get("origin") == "generated-video":
                check_approval(root, shot, video.get("approvalBatch"), for_submit=False)
                if video.get("sourceImageSha256") != shot["imageSource"]["sha256"]:
                    raise ValueError("Video used a different reference image")
        elif shot.get("videoPlan") and shot.get("videoDecision") != "static-approved" and not allow_static_draft:
            raise ValueError("Promised video unresolved; ask approval or obtain a static-version decision")
        for record in entries:
            path = local(root, record["asset"])
            digest = sha(path)
            if record.get("review") != "accepted" or not record.get("reviewNotes") or digest != record.get("sha256"):
                raise ValueError("Asset missing, changed or unreviewed: " + sid)
            if record.get("layout") != "single-full-frame" or digest in hashes:
                raise ValueError("Duplicate or non-independent asset: " + sid)
            hashes.add(digest)
            source_id = record.get("derivedFromSourceId")
            if source_id and source_id in roots:
                raise ValueError("Crops/recolors of the same source cannot be reused")
            if source_id:
                roots.add(source_id)
            if record.get("origin") == "web" and (not record.get("sourcePage") or not record.get("license") or record.get("rightsStatus") != "allowed"):
                raise ValueError("External asset source/rights unverified")
            if record is shot["imageSource"]:
                with Image.open(path) as im:
                    actual = im.size
                minimum = meta["minimumImagePixels"]
            else:
                info = probe(path)
                stream = next(s for s in info["streams"] if s["codec_type"] == "video")
                actual = (stream["width"], stream["height"])
                duration = float(stream.get("duration") or info["format"]["duration"])
                if abs(duration - record["duration"]) > .001:
                    raise ValueError("Video duration differs from reviewed source")
                minimum = meta["minimumVideoPixels"]
            if actual != (record["nativeWidth"], record["nativeHeight"]):
                raise ValueError("Native dimensions changed")
            aspect_tolerance = 1e-6 if meta.get("strictAssetAspectRatio") else .02
            if actual[0] < minimum[0] or actual[1] < minimum[1] or abs(actual[0] / actual[1] - meta["width"] / meta["height"]) > aspect_tolerance:
                raise ValueError("Reviewed asset no longer meets native geometry requirements")
    if last != meta["durationFrames"] or sorted(used) != sorted(ids):
        raise ValueError("Incomplete timeline or repeated/missing original cues")
    return {"ready": True, "shots": len(data["shots"]), "uniqueAssetHashes": len(hashes),
            "durationFrames": last, "audioTempo": 1.0, "staticDraft": allow_static_draft}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    for command in ("init", "freeze", "validate", "register", "draft-video-batch", "check-video-approval"):
        p = sub.add_parser(command)
        p.add_argument("project")
        if command == "init":
            p.add_argument("--title", required=True)
        if command == "validate":
            p.add_argument("--allow-static-draft", action="store_true")
            p.add_argument("--until-frame", type=int)
        if command == "register":
            p.add_argument("--id", required=True); p.add_argument("--source", required=True)
            p.add_argument("--kind", choices=("image", "video"), required=True)
            p.add_argument("--review", choices=("pending", "accepted", "rejected"), default="pending")
            p.add_argument("--note", default=""); p.add_argument("--origin", choices=("generated-image", "generated-video", "web", "local-render"), required=True)
            p.add_argument("--batch")
        if command == "draft-video-batch":
            p.add_argument("--batch", required=True); p.add_argument("--ids", nargs="+", required=True)
        if command == "check-video-approval":
            p.add_argument("--batch", required=True); p.add_argument("--id", required=True)
    a = ap.parse_args()
    root = Path(a.project).resolve()
    if a.command == "init": result = init(root, a.title)
    elif a.command == "freeze": result = freeze(root)
    elif a.command == "validate": result = validate(root, a.allow_static_draft, a.until_frame)
    elif a.command == "register": result = register(root, a.id, a.source, a.kind, a.review, a.note, a.origin, a.batch)
    elif a.command == "draft-video-batch": result = draft_batch(root, a.batch, a.ids)
    else:
        shot = next(s for s in manifest(root)["shots"] if s["id"] == a.id)
        result = check_approval(root, shot, a.batch)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
