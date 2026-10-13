#!/usr/bin/env python3
"""Offline behavioral tests. Synthetic local fixtures; no model/API calls."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image, ImageDraw
import single_shot_assets as assets
import single_shot_render as render

HERE = Path(__file__).resolve().parent


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="history-skill-test-")
        self.root = Path(self.temp.name)
        assets.init(self.root, "离线测试主题")
        data = assets.manifest(self.root)
        data["meta"].update(width=360, height=640, minimumImagePixels=[180, 320],
                            minimumVideoPixels=[180, 320], audio="assets/audio/narration.wav", quality="test-only")
        data["protectedTerms"] = ["历史事件", "改变主意", "后面的结果"]
        data["captions"] = [
            {"id": 1, "paragraph": 1, "startFrame": 0, "endFrame": 50, "text": "今天讲的是一个历史事件。"},
            {"id": 2, "paragraph": 1, "startFrame": 60, "endFrame": 110, "text": "问题来了，他为什么改变主意？"},
            {"id": 3, "paragraph": 2, "startFrame": 130, "endFrame": 220, "text": "看清这一步，就能明白后面的结果。"}]
        data["shots"] = []
        for index, (start, end, cue_ids) in enumerate([(0, 120, [1, 2]), (120, 240, [3])], 1):
            data["shots"].append({"id": f"SC{index:03d}", "startFrame": start, "endFrame": end,
                "cueIds": cue_ids, "narration": "".join(c["text"] for c in data["captions"] if c["id"] in cue_ids),
                "visualGoal": "Local synthetic test only", "matchReason": "Technical test pattern, not an editorial asset",
                "artDirection": "Synthetic geometry", "layout": "single-full-frame", "imageReview": "pending", "video": None})
        assets.save(self.root / "production.json", data)
        (self.root / "narration.txt").write_text("".join(c["text"] for c in data["captions"]), encoding="utf-8")
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "anoisesrc=duration=8:sample_rate=48000:amplitude=0.08:seed=43",
                        "-ac", "1", "-c:a", "pcm_s16le", str(self.root / "assets/audio/narration.wav")], check=True)
        assets.freeze(self.root)
        self.sources = []
        for index, color in enumerate([(225, 214, 191), (207, 222, 227)], 1):
            path = self.root / f"fixture-{index}.png"
            canvas = Image.new("RGB", (360, 640), color)
            draw = ImageDraw.Draw(canvas)
            draw.rectangle((40, 70, 180 + index * 25, 320), fill=(35 + index * 30, 60, 80))
            canvas.save(path)
            self.sources.append(path)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda x: assets.register(self.root, f"SC{x+1:03d}", self.sources[x], "image",
                      "accepted", "Synthetic local fixture, technical QA only", "local-render"), range(2)))

    def tearDown(self):
        self.temp.cleanup()

    def plan_video(self):
        data = assets.manifest(self.root)
        data["shots"][0]["videoPlan"] = {"provider": "test-no-network", "model": "mock",
            "prompt": "one bounded action", "durationSeconds": 5, "resolution": "360x640"}
        assets.save(self.root / "production.json", data)
        assets.draft_batch(self.root, "VB001", ["SC001"])

    def simulate_approval(self):
        ledger = assets.read(self.root / "video-approvals.json")
        ledger["batches"][0].update(status="approved", userConfirmation={
            "text": "SIMULATED unit-test approval only; never submit a real job",
            "source": "isolated offline test fixture"})
        assets.save(self.root / "video-approvals.json", ledger)

    def cli(self, script, *args, expected=0):
        result = subprocess.run([sys.executable, str(HERE / script), str(self.root), *map(str, args)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_parallel_registration_and_non_destructive_init(self):
        self.assertEqual(assets.validate(self.root)["shots"], 2)
        before = (self.root / "production.json").read_bytes()
        assets.init(self.root, "Do not overwrite")
        self.assertEqual(before, (self.root / "production.json").read_bytes())

    def test_duplicate_and_changed_asset_are_rejected(self):
        with self.assertRaises(ValueError):
            assets.register(self.root, "SC002", self.sources[0], "image", "accepted", "duplicate", "local-render")
        data = assets.manifest(self.root)
        data["shots"][0]["asset"] = data["shots"][1]["asset"]
        assets.save(self.root / "production.json", data)
        with self.assertRaises(ValueError):
            assets.validate(self.root)

    def test_changed_caption_baseline_is_rejected(self):
        data = assets.manifest(self.root)
        data["captions"][0]["text"] += "改"
        assets.save(self.root / "production.json", data)
        with self.assertRaises(ValueError):
            assets.validate(self.root)

    def test_grid_and_timeline_gap_are_rejected(self):
        original = assets.manifest(self.root)
        for field, value in [("layout", "four-panel-grid"), ("startFrame", 1)]:
            data = copy.deepcopy(original)
            data["shots"][0][field] = value
            assets.save(self.root / "production.json", data)
            with self.assertRaises(ValueError):
                assets.validate(self.root)

    def test_video_requires_current_explicit_batch(self):
        self.plan_video()
        shot = assets.manifest(self.root)["shots"][0]
        with self.assertRaises(ValueError):
            assets.check_approval(self.root, shot, "VB001")
        self.simulate_approval()
        self.assertEqual(assets.check_approval(self.root, shot, "VB001")["id"], "SC001")
        for field, value in [("model", "another-model"), ("prompt", "another-action"), ("durationSeconds", 8), ("seed", 123)]:
            changed = copy.deepcopy(shot)
            changed["videoPlan"][field] = value
            with self.assertRaises(ValueError):
                assets.check_approval(self.root, changed, "VB001")
        with self.assertRaises(ValueError):
            assets.check_approval(self.root, shot, "previous-project-batch")
        with self.assertRaises(ValueError):
            assets.validate(self.root)
        self.assertTrue(assets.validate(self.root, allow_static_draft=True)["staticDraft"])
        image_path = assets.local(self.root, shot["asset"])
        Image.new("RGB", (360, 640), (180, 180, 180)).save(image_path)
        with self.assertRaises(ValueError):
            assets.check_approval(self.root, shot, "VB001")

    def test_unknown_submission_and_retry_limit_are_rejected(self):
        self.plan_video()
        self.simulate_approval()
        for status in ("unknown", "submitting", "running", "failed", "completed"):
            ledger = assets.read(self.root / "video-approvals.json")
            ledger["batches"][0]["jobs"][0]["attempts"] = [{"status": status, "id": "offline-test"}]
            assets.save(self.root / "video-approvals.json", ledger)
            with self.assertRaises(ValueError):
                assets.check_approval(self.root, assets.manifest(self.root)["shots"][0], "VB001")

    def test_render_captions_waveform_and_negative_controls(self):
        self.cli("single_shot_render.py", "--name", "test.mp4")
        report = assets.read(self.root / "outputs/test-report.json")
        self.assertFalse(report["fullFilmComplete"])
        self.assertEqual(int(next(s for s in report["probe"]["streams"] if s["codec_type"] == "video")["nb_frames"]), 240)
        self.cli("single_shot_caption_qc.py", "outputs/test.mp4")
        self.cli("single_shot_audio_qc.py", "outputs/test.mp4")
        self.cli("single_shot_audio_qc.py", "outputs/test.mp4", "--reference-offset", 1,
                 "--output", self.root / "negative-audio.json", expected=2)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=0xddd3bc:s=360x640:r=30:d=8", "-i", str(self.root / "assets/audio/narration.wav"),
                        "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                        "-t", "8", str(self.root / "outputs/no-captions.mp4")], check=True)
        self.cli("single_shot_caption_qc.py", "outputs/no-captions.mp4", expected=2)
        Path(report["jobs"][0]["file"]).write_bytes(b"intentionally interrupted cache fixture")
        self.cli("single_shot_render.py", "--name", "test-recovered.mp4")
        self.assertTrue(list((self.root / ".build/single-shot-cache").glob("*.invalid-*.mp4")))

    def test_caption_wrap_preserves_terms_and_text(self):
        render.configure(self.root)
        text = "问题来了，他为什么改变主意，后面的结果又如何？"
        lines = render.caption_lines(text)
        self.assertEqual("".join(lines), text)
        split = len(lines[0])
        for word in ["改变主意", "后面的结果"]:
            position = text.index(word)
            self.assertFalse(position < split < position + len(word))


if __name__ == "__main__":
    unittest.main(verbosity=2)
