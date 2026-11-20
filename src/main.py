"""
main.py
-------
Butun dublyaj pipeline'ini ishga tushiradi:
  video -> transkript -> tarjima -> TTS -> mixing -> tayyor video

ISHLATISH:
  venv faollashtirilgan holda, src/ papkasida turib:
    python main.py "input/video_nomi.mp4"
"""

import sys
import json

import config

from transcribe import transcribe_video
from translate import translate_segments
from tts import synthesize_all
from mix import build_dubbed_audio, merge_with_video

from pydub.utils import mediainfo


def ask_voice_gender() -> str:
    """Foydalanuvchidan dublyaj ovozi turini so'raydi."""
    while True:
        answer = input(
            "\nDublyaj qaysi ovozda bo'lsin?\n"
            "  1 - Erkak ovozi (uz-UZ-SardorNeural)\n"
            "  2 - Ayol ovozi  (uz-UZ-MadinaNeural)\n"
            "Tanlovingiz (1/2): "
        ).strip()

        if answer in ("1", "erkak", "male"):
            return "male"
        if answer in ("2", "ayol", "female"):
            return "female"

        print("⚠ Noto'g'ri tanlov. Iltimos 1 yoki 2 kiriting.")


def run_pipeline(video_path: str, voice_gender: str):
    print(f"\n{'='*60}")
    print(f"DUBLYAJ BOSHLANDI: {video_path}")
    print(f"Tanlangan ovoz: {'Erkak' if voice_gender == 'male' else 'Ayol'}")
    print(f"{'='*60}\n")

    # 1) ASR + timestamp + diarization
    segments = transcribe_video(video_path, voice_gender=voice_gender)

    # 2) Tarjima (kontekstli, yaxlit)
    segments = translate_segments(segments)

    # 3) TTS
    segments = synthesize_all(segments)

    # 4) Video umumiy davomiyligini olish
    info = mediainfo(video_path)
    total_duration = float(info["duration"])

    # 5) Audio segmentlarni birlashtirish
    dubbed_audio_path = build_dubbed_audio(segments, total_duration)

    # 6) Video bilan birlashtirish
    final_path = merge_with_video(video_path, dubbed_audio_path)

    print(f"\n{'='*60}")
    print(f"TAYYOR! Natija: {final_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Ishlatish: python main.py \"input/video_nomi.mp4\"")
        sys.exit(1)

    gender = ask_voice_gender()
    run_pipeline(sys.argv[1], gender)