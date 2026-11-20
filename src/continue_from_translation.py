"""
continue_from_translation.py
-----------------------------
Agar transkript va tarjima ALLAQACHON tayyor bo'lsa (temp/translated.json
mavjud bo'lsa) va faqat TTS + mixing + video birlashtirish bosqichlarini
qayta ishga tushirish kerak bo'lsa, shu skriptdan foydalaning.

Bu transcribe.py va translate.py bosqichlarini QAYTA ISHGA TUSHIRMAYDI —
vaqtni tejaydi (ASR va tarjima eng uzoq davom etadigan bosqichlar edi).

ISHLATISH (src/ papkasida turib):
    python continue_from_translation.py "input/sinov_video.mp4"

Yoki loyiha ildizida turib:
    python src/continue_from_translation.py "input/sinov_video.mp4"
"""

import sys
import json

import config
from config import TEMP_DIR

from tts import synthesize_all
from mix import build_dubbed_audio, merge_with_video

from pydub.utils import mediainfo


def run_from_translation(video_path: str):
    translated_path = TEMP_DIR / "translated.json"

    if not translated_path.exists():
        print(f"❌ Fayl topilmadi: {translated_path}")
        print("   Avval transcribe.py va translate.py orqali tarjimani yarating.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"DAVOM ETTIRILMOQDA: {video_path}")
    print(f"Manba: {translated_path}")
    print(f"{'='*60}\n")

    with open(translated_path, encoding="utf-8") as f:
        segments = json.load(f)

    print(f"✅ {len(segments)} ta segment yuklandi.")

    # 1) TTS — tarjima qilingan matnni ovozga aylantirish
    segments = synthesize_all(segments)

    # 2) Video umumiy davomiyligini olish
    info = mediainfo(video_path)
    total_duration = float(info["duration"])

    # 3) Audio segmentlarni birlashtirish
    dubbed_audio_path = build_dubbed_audio(segments, total_duration)

    # 4) Video bilan birlashtirish
    final_path = merge_with_video(video_path, dubbed_audio_path)

    print(f"\n{'='*60}")
    print(f"TAYYOR! Natija: {final_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Ishlatish: python continue_from_translation.py "input/video_nomi.mp4"')
        sys.exit(1)

    run_from_translation(sys.argv[1])