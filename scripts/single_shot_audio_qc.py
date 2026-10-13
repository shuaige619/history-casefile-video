#!/usr/bin/env python3
"""Compare the actual complete soundtrack to the approved source at its clock.

Codec-tolerant waveform comparison, not transcription or phoneme verification.
No audio file is modified by this diagnostic.
"""
import argparse
import json
import subprocess
from pathlib import Path
import numpy as np
from single_shot_assets import manifest, save

RATE = 8000


def pcm(path, offset, duration):
    result = subprocess.run([
        'ffmpeg', '-nostdin', '-v', 'error', '-ss', f'{offset:.9f}',
        '-i', str(path), '-t', f'{duration:.9f}', '-map', '0:a:0',
        '-ac', '1', '-ar', str(RATE), '-f', 'f32le', 'pipe:1',
    ], check=True, capture_output=True)
    return np.frombuffer(result.stdout, dtype='<f4')


def energy(x):
    return float(np.sum(x * x, dtype=np.float64))


def correlation(x, y):
    den = (energy(x) * energy(y)) ** .5
    return float(np.sum(x * y, dtype=np.float64) / den) if den > 1e-12 else 0.


def aligned(x, y, lag):
    if lag > 0:
        x = x[lag:]
    elif lag < 0:
        y = y[-lag:]
    size = min(len(x), len(y))
    return x[:size], y[:size]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project')
    ap.add_argument('video')
    ap.add_argument('--reference')
    ap.add_argument('--reference-offset', type=float, default=0.)
    ap.add_argument('--output')
    a = ap.parse_args()
    ROOT = Path(a.project).resolve()
    data = manifest(ROOT)
    video = (ROOT / a.video).resolve()
    reference = (ROOT / (a.reference or data['meta']['audio'])).resolve()
    info = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_format', '-of', 'json', str(video)]))
    duration = float(info['format']['duration'])
    actual = pcm(video, 0, duration)
    expected = pcm(reference, a.reference_offset, duration)
    length_delta = len(actual) - len(expected)
    if min(len(actual), len(expected)) < RATE * 3:
        raise ValueError('Insufficient decoded audio for waveform verification')
    probe_end = min(len(actual), len(expected), RATE * 20)
    probe_start = min(RATE, probe_end // 4)
    candidates = []
    for lag in range(-16, 17):
        x, y = aligned(actual[probe_start:probe_end], expected[probe_start:probe_end], lag)
        candidates.append((correlation(x, y), lag))
    _, lag = max(candidates)
    actual, expected = aligned(actual, expected, lag)
    checks = []
    for start in range(0, len(actual), RATE * 30):
        x, y = actual[start:start + RATE * 30], expected[start:start + RATE * 30]
        if len(x) < RATE // 2:
            continue
        x_rms = (energy(x) / len(x)) ** .5
        y_rms = (energy(y) / len(y)) ** .5
        corr = correlation(x, y)
        gain = x_rms / y_rms if y_rms > 1e-8 else None
        passed = (x_rms < .0002) if y_rms < .00001 else (corr >= .985 and .97 <= gain <= 1.03)
        checks.append({'startSeconds': start / RATE, 'durationSeconds': len(x) / RATE,
                       'correlation': round(corr, 7), 'rmsRatio': round(gain, 7) if gain else None,
                       'passed': bool(passed)})
    report = {
        'video': str(video), 'reference': str(reference), 'referenceOffsetSeconds': a.reference_offset,
        'method': 'Entire decoded mono 8kHz waveform, consecutive 30s blocks; one codec-tolerance global alignment limited to 2ms. Not a transcript or phoneme audit.',
        'decodedSecondsCompared': len(actual) / RATE, 'blocksChecked': len(checks),
        'globalLagSamples': lag, 'globalLagSeconds': lag / RATE,
        'decodedLengthDifferenceSeconds': length_delta / RATE,
        'minimumBlockCorrelation': min(c['correlation'] for c in checks),
        'passed': bool(checks and abs(length_delta) <= RATE * .1 and all(c['passed'] for c in checks)),
        'checks': checks,
    }
    target = Path(a.output).resolve() if a.output else video.with_name(video.stem + '-audio-qc.json')
    save(target, report)
    print(json.dumps({k: v for k, v in report.items() if k != 'checks'}, ensure_ascii=False))
    if not report['passed']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
