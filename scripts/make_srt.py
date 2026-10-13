#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


def clean_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        stripped = re.sub(r"^[-*+]\s+", "", stripped)
        stripped = re.sub(r"^\[[FQID]\]\s*", "", stripped)
        lines.append(stripped)
    return "".join(lines)


def split_phrases(text: str, max_chars: int) -> list[str]:
    primary = [x.strip() for x in re.split(r"(?<=[。！？!?；;])", text) if x.strip()]
    result: list[str] = []
    for sentence in primary:
        if len(sentence) <= max_chars:
            result.append(sentence)
            continue
        parts = [x.strip() for x in re.split(r"(?<=[，、：:])", sentence) if x.strip()]
        buffer = ""
        for part in parts:
            if buffer and len(buffer) + len(part) > max_chars:
                result.append(buffer)
                buffer = ""
            if len(part) > max_chars:
                if buffer:
                    result.append(buffer)
                    buffer = ""
                result.extend(part[i:i + max_chars] for i in range(0, len(part), max_chars))
            else:
                buffer += part
        if buffer:
            result.append(buffer)
    return [x for x in result if x]


def stamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an approximate SRT by distributing narration text across a measured audio duration.")
    parser.add_argument("text_file")
    parser.add_argument("output_srt")
    parser.add_argument("--duration-seconds", type=float, required=True)
    parser.add_argument("--max-chars", type=int, default=18)
    parser.add_argument("--offset-seconds", type=float, default=0.0)
    args = parser.parse_args()

    text = clean_text(Path(args.text_file).read_text(encoding="utf-8"))
    phrases = split_phrases(text, args.max_chars)
    if not phrases:
        raise SystemExit("No narration text found")
    usable = args.duration_seconds - args.offset_seconds
    if usable <= 0:
        raise SystemExit("Duration must exceed offset")
    weights = [max(1, len(re.sub(r"[，。！？!?；;、：:\s]", "", p))) + (1.5 if re.search(r"[。！？!?]$", p) else 0.5) for p in phrases]
    total_weight = sum(weights)
    cursor = args.offset_seconds
    rows = []
    for index, (phrase, weight) in enumerate(zip(phrases, weights), 1):
        duration = usable * weight / total_weight
        end = args.duration_seconds if index == len(phrases) else cursor + duration
        rows.append(f"{index}\n{stamp(cursor)} --> {stamp(end)}\n{phrase}\n")
        cursor = end
    Path(args.output_srt).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_srt).write_text("\n".join(rows), encoding="utf-8")
    print(f"phrases={len(phrases)} duration={args.duration_seconds:.3f}s output={args.output_srt}")


if __name__ == "__main__":
    main()

