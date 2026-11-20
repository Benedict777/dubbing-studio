"""
pipeline.py
-----------
Dublyaj bosqichlarini ketma-ket ishga tushiradi va har bir bosqich
haqida foiz ma'lumotini oynaga (callback orqali) yuboradi.

Groq kaliti va modeli ASR boshlanishidan OLDIN tekshiriladi — muammo
bo'lsa GroqProblem ko'tariladi va jarayon boshlanmaydi.
"""

import os

import config  # eng birinchi: model papkalari D diskka yo'naltiriladi
from pathlib import Path
from config import DEFAULT_OUTPUT_DIR, OUTPUT_DIR


class Cancelled(Exception):
    pass


# bosqich: (umumiy jarayondagi boshlanish %, tugash %)
STAGE_RANGE = {
    "transcribe": (0, 35),
    "translate": (35, 60),
    "tts": (60, 80),
    "mix": (80, 95),
    "merge": (95, 100),
}


def resolve_output_dir(selected: str | None) -> Path:
    """Tanlangan papka, bo'lmasa D:\\Dublyaj_output (bor bo'lsa qayta yaratilmaydi)."""
    target = Path(selected) if selected else DEFAULT_OUTPUT_DIR
    try:
        target.mkdir(parents=True, exist_ok=True)
        return target
    except OSError:
        # masalan D: disk yo'q bo'lsa — loyiha ichidagi output/ ga tushadi
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return OUTPUT_DIR


def _unique_name(folder: Path, stem: str) -> str:
    name = f"{stem}_uz.mp4"
    n = 2
    while (folder / name).exists():
        name = f"{stem}_uz_{n}.mp4"
        n += 1
    return name


def run_pipeline(video_path, voice_gender, output_dir, on_progress, cancel_event):
    """
    on_progress(stage_key, stage_percent, overall_percent)
    cancel_event: threading.Event — o'rnatilsa Cancelled xatosi ko'tariladi
    Qaytaradi: tayyor video yo'li (Path)
    Groq muammosi bo'lsa: translate.GroqProblem ko'tariladi
    """
    def make_cb(stage):
        lo, hi = STAGE_RANGE[stage]

        def cb(frac):
            if cancel_event.is_set():
                raise Cancelled()
            frac = max(0.0, min(1.0, float(frac)))
            on_progress(stage, frac * 100, lo + (hi - lo) * frac)
        return cb

    # og'ir kutubxonalar (whisperx, torch) faqat shu yerda import qilinadi —
    # shunda oyna darrov ochiladi
    from transcribe import transcribe_video
    from translate import translate_segments, check_groq
    from tts import synthesize_all
    from mix import build_dubbed_audio, merge_with_video
    from pydub.utils import mediainfo

    # Groq kalit/modelini ASR boshlanishidan OLDIN tekshiramiz
    if os.getenv("TRANSLATE_PROVIDER", "groq") == "groq":
        check_groq()      # muammo bo'lsa GroqProblem ko'tariladi

    out_folder = resolve_output_dir(output_dir)
    out_name = _unique_name(out_folder, Path(video_path).stem)

    cb = make_cb("transcribe")
    cb(0)
    segments = transcribe_video(video_path, voice_gender=voice_gender, progress_cb=cb)

    cb = make_cb("translate")
    cb(0)
    segments = translate_segments(segments, progress_cb=cb)

    cb = make_cb("tts")
    cb(0)
    segments = synthesize_all(segments, progress_cb=cb)

    total_duration = float(mediainfo(video_path)["duration"])

    cb = make_cb("mix")
    cb(0)
    dubbed_audio = build_dubbed_audio(segments, total_duration, progress_cb=cb)

    cb = make_cb("merge")
    cb(0)
    final_path = merge_with_video(
        video_path, dubbed_audio, output_filename=out_name, output_dir=out_folder
    )
    cb(1)
    return Path(final_path)
