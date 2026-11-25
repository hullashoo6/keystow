"""Measure where dictation time goes, and whether it grows over a long session.

Not part of the unit tests (it needs the real model and takes minutes):

    python tests/bench_pipeline.py MODEL_DIR FIXTURE_DIR [RUNS]

FIXTURE_DIR holds short.wav, medium.wav and long.wav (16 kHz mono, synthetic
speech). Uses a private home folder, so no real KeyStow settings are read.
Prints one JSON report: hardware, sample counts, and p50/p95 per stage.
"""
import json
import os
import platform
import statistics
import sys
import tempfile
import time
import wave

os.environ["USERPROFILE"] = os.environ["HOME"] = tempfile.mkdtemp(prefix="keystow-bench-")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np  # noqa: E402
import psutil  # noqa: E402

from keystow import denoise  # noqa: E402
from keystow.transcriber import Transcriber  # noqa: E402

REFERENCE = {
    "short": "Running ten minutes late.",
    "medium": "Please move the design review to Thursday afternoon and invite the whole product team.",
    "long": ("Thanks for the update on the quarterly plan. I read the draft this morning, and the budget "
             "section looks right to me, but the hiring timeline feels tight, so could we talk it through "
             "on Friday before it goes out to everyone?"),
}


def load(path):
    with wave.open(path) as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def words(s):
    return [w.strip(".,?!").lower() for w in s.split() if w.strip(".,?!")]


def wer(ref, hyp):
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        prev, d[0] = d[0], i
        for j, hw in enumerate(h, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (rw != hw))
    return d[len(h)] / max(len(r), 1)


def pct(values, q):
    values = sorted(values)
    return round(values[min(len(values) - 1, int(q * len(values)))], 1)


def resources():
    p = psutil.Process()
    info = {"rss_mb": round(p.memory_info().rss / 2**20, 1), "threads": p.num_threads()}
    if hasattr(p, "num_handles"):
        info["handles"] = p.num_handles()
    return info


def denoise_trend(audio, runs, fresh):
    """ms of denoising per second of audio, old shared state vs a fresh one each time."""
    shared = None if fresh else denoise._RnNoise()
    per_second = []
    for _ in range(runs):
        t = time.perf_counter()
        if fresh:
            engine = denoise._RnNoise()
            engine.denoise(audio)
            engine.close()
        else:
            shared.denoise(audio)
        per_second.append((time.perf_counter() - t) * 1000.0 / (audio.size / 16000))
    return {"first": round(per_second[0], 1), "p50": pct(per_second, 0.5), "p95": pct(per_second, 0.95),
            "last50_p50": pct(per_second[-50:], 0.5), "runs": runs}


def main():
    model_dir, fixtures = sys.argv[1], sys.argv[2]
    runs = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    audio = {k: load(os.path.join(fixtures, f"{k}.wav")) for k in REFERENCE}
    rng = np.random.default_rng(7)
    noisy = audio["medium"] + rng.normal(0, 0.02, audio["medium"].size).astype(np.float32)
    report = {"cpu": platform.processor(), "logical_cpus": os.cpu_count(), "python": platform.python_version(),
              "seconds": {k: round(v.size / 16000, 2) for k, v in audio.items()}}

    report["denoise_ms_per_audio_second"] = {
        "shared_state_like_v1.0.6": denoise_trend(audio["long"], 500, fresh=False),
        "fresh_state_per_recording": denoise_trend(audio["long"], 500, fresh=True),
    }

    t = time.perf_counter()
    model = Transcriber(model_size=model_dir)
    report["model_load_ms"] = round((time.perf_counter() - t) * 1000)
    report["resources_after_load"] = resources()

    timings, texts = {k: [] for k in audio}, {}
    order = list(audio) * (runs // 3 + 1)
    for i, name in enumerate(order[:runs]):
        model.transcribe(audio[name])
        timings[name].append(dict(model.last_timings))
        if i == 0:
            report["first_dictation_ms"] = {k: round(v) for k, v in model.last_timings.items()}
        texts[name] = texts.get(name) or model._recognise(audio[name])
    report["resources_after_runs"] = resources()
    report["per_fixture"] = {}
    for name, rows in timings.items():
        infer = [r["infer"] for r in rows]
        den = [r["denoise"] for r in rows]
        report["per_fixture"][name] = {
            "samples": len(rows), "infer_p50": pct(infer, 0.5), "infer_p95": pct(infer, 0.95),
            "infer_first10_p50": pct(infer[:10], 0.5), "infer_last10_p50": pct(infer[-10:], 0.5),
            "denoise_p50": pct(den, 0.5), "wer": round(wer(REFERENCE[name], texts[name]), 3)}

    # Noise suppression on vs off, on clean and on noisy speech (30 runs each).
    from keystow import settings
    compare = {}
    for label, enabled in (("suppression_on", True), ("suppression_off", False)):
        settings.set("noise_suppression", enabled)
        row = {}
        for name, clip in (("medium_clean", audio["medium"]), ("medium_noisy", noisy)):
            total = []
            for _ in range(30):
                t = time.perf_counter()
                text = model.transcribe(clip)
                total.append((time.perf_counter() - t) * 1000)
            row[name] = {"total_p50": pct(total, 0.5), "wer": round(wer(REFERENCE["medium"], text), 3)}
        compare[label] = row
    settings.set("noise_suppression", True)
    report["suppression_compare"] = compare

    # Greedy decoding (beam 1) vs the app's beam 5, same filters skipped: speed only + WER.
    beams = {}
    for beam in (5, 1):
        total, text = [], ""
        for _ in range(20):
            t = time.perf_counter()
            segs, _ = model._model.transcribe(audio["long"], language="en", beam_size=beam,
                                              condition_on_previous_text=False, vad_filter=True,
                                              vad_parameters={"min_silence_duration_ms": 500})
            text = " ".join(s.text.strip() for s in segs)
            total.append((time.perf_counter() - t) * 1000)
        beams[f"beam_{beam}"] = {"long_p50_ms": pct(total, 0.5), "wer": round(wer(REFERENCE["long"], text), 3)}
    report["beam_compare"] = beams
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
