#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def write_new(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a historical casefile video project without overwriting existing work.")
    parser.add_argument("project_directory")
    parser.add_argument("--title", required=True)
    parser.add_argument("--duration-minutes", type=float, default=25.0)
    args = parser.parse_args()

    root = Path(args.project_directory).expanduser().resolve()
    for rel in ["assets/images", "assets/audio", "assets/clips", "subtitles", "outputs"]:
        (root / rel).mkdir(parents=True, exist_ok=True)

    target_seconds = round(args.duration_minutes * 60, 3)
    write_new(root / "brief.md", f"# {args.title}\n\n- 目标时长：{args.duration_minutes:g}分钟\n- 画幅：9:16\n- 语言：简体中文普通话\n- 受众：\n- 核心悖论：\n- 视觉方向：历史案卷式 editorial collage\n- 假设与边界：\n")
    write_new(root / "source-ledger.json", json.dumps({"topic": args.title, "checked_at": "", "sources": [], "claims": []}, ensure_ascii=False, indent=2) + "\n")
    write_new(root / "story-architecture.json", json.dumps({"primary_route": "", "secondary_route": "", "central_paradox": "", "central_question": "", "answer_or_uncertainty": "", "characters": [], "causal_chain": [], "chapters": [], "decisive_evidence_or_choice": "", "derived_thesis": ""}, ensure_ascii=False, indent=2) + "\n")
    write_new(root / "hook-ledger.json", json.dumps({"hooks": []}, ensure_ascii=False, indent=2) + "\n")
    write_new(root / "storyboard.json", json.dumps({"title": args.title, "target_duration_seconds": target_seconds, "resolution": {"width": 1080, "height": 1920, "fps": 30}, "narration": "assets/audio/narration.aiff", "subtitles": "subtitles/narration.srt", "music": "", "scenes": []}, ensure_ascii=False, indent=2) + "\n")
    write_new(root / "asset-ledger.json", json.dumps({"assets": []}, ensure_ascii=False, indent=2) + "\n")
    for rel, heading in [("script-tagged.md", "带证据标签口播稿"), ("script.md", "口播稿"), ("narration.txt", ""), ("keyframe-prompts.md", "关键帧提示词"), ("video-prompts.md", "视频提示词"), ("qc-report.md", "质检报告")]:
        write_new(root / rel, f"# {heading}\n" if heading else "")
    print(root)


if __name__ == "__main__":
    main()

