#!/usr/bin/env python3
import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path


REQUIRED = [
    "brief.md", "source-ledger.json", "story-architecture.json", "hook-ledger.json",
    "script-tagged.md", "script.md", "narration.txt", "storyboard.json",
    "asset-ledger.json", "subtitles/narration.srt", "outputs/final-video.mp4"
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a historical casefile video project and write qc-report.md.")
    parser.add_argument("project_directory")
    args = parser.parse_args()
    root = Path(args.project_directory).expanduser().resolve()
    missing = [rel for rel in REQUIRED if not (root / rel).exists() or (root / rel).stat().st_size == 0]
    video = root / "outputs/final-video.mp4"
    probe = {}
    if video.exists():
        result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)], text=True, capture_output=True, check=True)
        probe = json.loads(result.stdout)
    streams = probe.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), {})
    astream = next((s for s in streams if s.get("codec_type") == "audio"), {})
    duration = float(probe.get("format", {}).get("duration", 0) or 0)
    width, height = int(vstream.get("width", 0) or 0), int(vstream.get("height", 0) or 0)
    checks = {
        "required_files_present": not missing,
        "duration_20_to_30_minutes": 1200 <= duration <= 1800,
        "vertical_9_16": bool(width and height and abs(width / height - 9 / 16) < 0.01),
        "has_video_stream": bool(vstream),
        "has_audio_stream": bool(astream),
        "source_ledger_nonempty": False,
        "asset_ledger_nonempty": False,
        "semantic_storyboard_nonempty": False,
        "semantic_fields_complete": False,
        "exact_files_used_once": False,
        "external_visual_families_used_once": False,
        "image_phrase_triggers_match": False,
        "context_disclosures_complete": False,
        "external_sources_traceable": False,
    }
    try:
        checks["source_ledger_nonempty"] = bool(json.loads((root / "source-ledger.json").read_text(encoding="utf-8")).get("sources"))
        asset_ledger = json.loads((root / "asset-ledger.json").read_text(encoding="utf-8"))
        assets = asset_ledger.get("assets", [])
        checks["asset_ledger_nonempty"] = bool(assets)
        assets_by_id = {asset.get("id"): asset for asset in assets if asset.get("id")}
        storyboard = json.loads((root / "storyboard.json").read_text(encoding="utf-8"))
        scenes = storyboard.get("scenes", [])
        checks["semantic_storyboard_nonempty"] = bool(scenes)
        required_semantic = {"narration_summary", "visual_goal", "visual_mode", "visual_family", "match_level", "match_reason", "trigger_terms"}
        checks["semantic_fields_complete"] = bool(scenes) and all(required_semantic.issubset(scene) for scene in scenes)
        paths = [scene.get("image", "") for scene in scenes if scene.get("image")]
        path_counts = Counter(paths)
        checks["exact_files_used_once"] = bool(paths) and max(path_counts.values(), default=0) <= 1
        external_families = [
            scene.get("visual_family", "") for scene in scenes
            if scene.get("image") and str(scene.get("match_level", "")).startswith(("A_", "B_"))
        ]
        family_counts = Counter(family for family in external_families if family)
        checks["external_visual_families_used_once"] = max(family_counts.values(), default=0) <= 1
        checks["image_phrase_triggers_match"] = all(
            any(term and term in scene.get("narration_summary", "") for term in scene.get("trigger_terms", []))
            for scene in scenes if scene.get("image")
        )
        checks["context_disclosures_complete"] = all(
            any(term in scene.get("source_note", "") for term in ("不是", "不当作", "not "))
            for scene in scenes if scene.get("match_level") in {"B_CONTEXT", "B_LATER_IMAGE"}
        )
        external_scenes = [scene for scene in scenes if str(scene.get("match_level", "")).startswith(("A_", "B_"))]
        checks["external_sources_traceable"] = all(
            scene.get("rights_id") in assets_by_id
            and bool(assets_by_id[scene.get("rights_id")].get("source_url") or assets_by_id[scene.get("rights_id")].get("source_page"))
            and bool(assets_by_id[scene.get("rights_id")].get("license"))
            for scene in external_scenes
        )
    except Exception:
        pass
    overall = all(checks.values())
    report = [
        "# 质检报告", "", f"- 总体状态：{'PASS' if overall else 'NEEDS_REVIEW'}",
        f"- 实际时长：{duration:.3f}秒（{duration/60:.2f}分钟）",
        f"- 分辨率：{width}×{height}", f"- 视频编码：{vstream.get('codec_name', '')}",
        f"- 音频编码：{astream.get('codec_name', '')}", f"- 音频采样率：{astream.get('sample_rate', '')}",
        "", "## 自动检查"
    ]
    report.extend(f"- [{'x' if ok else ' '}] {name}" for name, ok in checks.items())
    if missing:
        report += ["", "## 缺失文件", *[f"- {x}" for x in missing]]
    report += ["", "## 人工检查", "- [ ] 开场、章节边界、高潮、结尾抽帧无黑帧或错误时代元素", "- [ ] 每张实体图片都在口播真正说到触发短语时才出现", "- [ ] 相同人物/器物/地点没有通过换文件形成视觉家族重复", "- [ ] 背景文物已说明不是本案原件，后世人物像已说明并非写生", "- [ ] 字幕安全区、断句和专名已复核", "- [ ] 旁白无明显长静音、削波或突变", "- [ ] 史实、引文、数字和争议说法已人工复核", "- [ ] 所有外部素材的授权或公版状态可追溯", "", "## 已修复问题", "- 待填写", ""]
    (root / "qc-report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"overall": overall, "checks": checks, "missing": missing, "duration": duration, "resolution": [width, height]}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
