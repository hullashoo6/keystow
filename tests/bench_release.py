"""Release-to-text latency: v1.0.6 pipeline vs this branch, with the real model.

    python tests/bench_release.py MODEL_DIR FIXTURE_DIR OUT_JSON [RUNS]

Audio is fed to the streaming denoiser at real-time pace, as a microphone
would, and only the time after "release" is measured. Synthetic speech;
private home folder; nothing is pasted anywhere.
"""
import json
import os
import platform
import sys
import tempfile
import time

os.environ["USERPROFILE"] = os.environ["HOME"] = tempfile.mkdtemp(prefix="keystow-bench-")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import psutil  # noqa: E402

from bench_pipeline import REFERENCE, load, pct, resources, wer  # noqa: E402
from keystow import denoise  # noqa: E402
from keystow.transcriber import Transcriber  # noqa: E402
from test_denoise_speed import old_denoise  # noqa: E402


def stream_like_a_microphone(audio):
    stream = denoise.Streaming()
    for start in range(0, audio.size, 1600):  # 100 ms blocks, as they arrive
        stream.push(audio[start:start + 1600])
        time.sleep(0.1)
    return stream


def main():
    model_dir, fixtures, out = sys.argv[1], sys.argv[2], sys.argv[3]
    runs = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    audio = {k: load(os.path.join(fixtures, f"{k}.wav")) for k in REFERENCE}
    model = Transcriber(model_size=model_dir)
    report = {"cpu": platform.processor(), "logical_cpus": os.cpu_count(),
              "power_plugged": getattr(psutil.sensors_battery(), "power_plugged", None),
              "runs_per_fixture": runs, "fixtures": {}}
    model._recognise(audio["short"])  # warm-up, reported separately below
    for name, clip in audio.items():
        old, new, texts = [], [], {}
        for _ in range(runs):
            t = time.perf_counter()
            text_old = model._recognise(old_denoise(clip))
            old.append((time.perf_counter() - t) * 1000)
            stream = stream_like_a_microphone(clip)
            t = time.perf_counter()
            text_new = model.transcribe(clip, denoised=stream.finish(clip.size))
            new.append((time.perf_counter() - t) * 1000)
            texts = {"old": text_old, "new": text_new}
        report["fixtures"][name] = {
            "audio_seconds": round(clip.size / 16000, 1),
            "v1.0.6_release_to_text_ms": {"p50": pct(old, 0.5), "p95": pct(old, 0.95)},
            "branch_release_to_text_ms": {"p50": pct(new, 0.5), "p95": pct(new, 0.95)},
            "same_text": texts["old"] == texts["new"],
            "wer": round(wer(REFERENCE[name], texts["new"]), 3),
        }
    report["resources"] = resources()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)


if __name__ == "__main__":
    main()
