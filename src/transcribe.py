"""
transcribe.py
-------------
Video/audio fayldan:
  - matnni (so'z darajasidagi timestamp bilan)
  - kim qachon gapirganini (diarization)
ajratib oladi.

Natija: segmentlar ro'yxati, har biri:
  {
    "start": 12.4,
    "end": 15.8,
    "speaker": "SPEAKER_00",
    "text": "Hello, how are you?",
    "gender": "male"  # foydalanuvchi tanlagan ovoz turi
  }
"""

import json
import whisperx
from config import (
    WHISPER_MODEL_SIZE, DEVICE, COMPUTE_TYPE,
    SOURCE_LANGUAGE, TEMP_DIR, MODELS_DIR,
    MIN_SPEAKERS, MAX_SPEAKERS,
)


def transcribe_video(audio_path: str, voice_gender: str = "female", progress_cb=None) -> list[dict]:
    """
    audio_path: video yoki audio faylning to'liq yo'li
    voice_gender: "male" yoki "female" — foydalanuvchi tanlagan dublyaj ovozi,
                  barcha segmentlarga shu qo'llaniladi.
    Qaytaradi: segmentlar ro'yxati (yuqoridagi formatda)
    """
    _p = progress_cb or (lambda f: None)
    _p(0.0)
    print(f"[1/3] Whisper modeli yuklanmoqda ({WHISPER_MODEL_SIZE})...")
    model = whisperx.load_model(
        WHISPER_MODEL_SIZE,
        DEVICE,
        compute_type=COMPUTE_TYPE,
        download_root=str(MODELS_DIR / "whisper"),
    )

    _p(0.10)
    print("[1/3] Audio matnga o'girilmoqda...")
    audio = whisperx.load_audio(audio_path)
    result = model.transcribe(audio, language=SOURCE_LANGUAGE)

    _p(0.60)
    print("[2/3] So'z darajasidagi timestamp aniqlanmoqda (forced alignment)...")
    align_model, metadata = whisperx.load_align_model(
        language_code=result["language"], device=DEVICE
    )
    result = whisperx.align(
        result["segments"], align_model, metadata, audio, DEVICE
    )

    _p(0.80)
    print("[3/3] Spikerlar ajratilmoqda (diarization)...")
    import os
    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        diarize_model = whisperx.diarize.DiarizationPipeline(
            token=hf_token, device=DEVICE
        )
        diarize_segments = diarize_model(
            audio,
            min_speakers=MIN_SPEAKERS,
            max_speakers=MAX_SPEAKERS,
        )
        result = whisperx.assign_word_speakers(diarize_segments, result)
    else:
        print("  ⚠ HF_TOKEN topilmadi — spiker ajratish o'tkazib yuborildi "
              "(bitta spiker deb hisoblanadi).")

    _p(1.0)
    segments = []
    for seg in result["segments"]:
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "speaker": seg.get("speaker", "SPEAKER_00"),
            "text": seg["text"].strip(),
            "gender": voice_gender,   # endi pitch orqali emas, foydalanuvchi tanlovi
        })

    out_path = TEMP_DIR / "transcript.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    print(f"✅ Transkript tayyor: {out_path}  ({len(segments)} ta segment)")
    return segments


if __name__ == "__main__":
    from config import INPUT_DIR
    files = list(INPUT_DIR.glob("*"))
    if not files:
        print("⚠ input/ papkasiga video fayl qo'ying.")
    else:
        transcribe_video(str(files[0]), voice_gender="female")