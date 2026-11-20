"""
tts.py
------
Tarjima qilingan matnni edge-tts orqali o'zbekcha ovozga aylantiradi.

Segmentlar PARALEL (cheklangan sonda) generatsiya qilinadi.

MUHIM: agar TTS hech bir segment uchun ishlamasa, dastur jim qolmaydi —
RuntimeError ko'taradi (GUI da "Xatolik" ko'rinadi), ovozsiz video chiqmaydi.

Mavjud o'zbekcha ovozlar:
  uz-UZ-MadinaNeural  — ayol ovozi
  uz-UZ-SardorNeural  — erkak ovozi
"""

import asyncio
from pathlib import Path

import edge_tts

from config import TEMP_DIR

AUDIO_SEGMENTS_DIR = TEMP_DIR / "tts_segments"
AUDIO_SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)

GENDER_VOICES = {
    "male": "uz-UZ-SardorNeural",
    "female": "uz-UZ-MadinaNeural",
}

# Bir vaqtning o'zida nechta so'rov yuborilishi (ko'p bo'lsa server rad etadi)
MAX_PARALLEL_REQUESTS = 4

# Har bir segment uchun urinishlar soni
RETRIES = 4

# Shundan kichik mp3 fayl "bo'sh/buzuq" deb hisoblanadi (bayt)
MIN_VALID_SIZE = 500


def _voice_for_gender(gender: str) -> str:
    return GENDER_VOICES.get(gender, GENDER_VOICES["female"])


def _has_speakable_text(text: str) -> bool:
    """Matnda kamida bitta harf yoki raqam bormi (faqat tinish belgilari TTS da xato beradi)."""
    return bool(text) and any(ch.isalnum() for ch in text)


async def _synthesize_one(seg: dict, index: int, semaphore: asyncio.Semaphore,
                          retries: int = RETRIES):
    text = (seg.get("tarjima") or "").strip()
    seg["audio_path"] = None
    seg.pop("tts_error", None)

    if not _has_speakable_text(text):
        return  # aytiladigan narsa yo'q — bu xato emas

    voice = _voice_for_gender(seg.get("gender", "female"))
    out_path = AUDIO_SEGMENTS_DIR / f"seg_{index:04d}.mp3"

    async with semaphore:
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                if out_path.exists():
                    out_path.unlink()
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(str(out_path))

                if out_path.exists() and out_path.stat().st_size >= MIN_VALID_SIZE:
                    seg["audio_path"] = str(out_path)
                    return
                raise RuntimeError("bo'sh yoki buzuq audio fayl yaratildi")
            except Exception as e:
                last_err = e
                if attempt < retries:
                    await asyncio.sleep(2 * attempt)

        print(f"  ⚠ Segment {index} TTS xatosi ({retries} urinishdan keyin): {last_err!r}")
        seg["tts_error"] = repr(last_err)


async def _synthesize_all_async(segments: list[dict], progress_cb=None):
    semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)
    tasks = [
        asyncio.create_task(_synthesize_one(seg, i, semaphore))
        for i, seg in enumerate(segments)
    ]

    total = len(tasks)
    done = 0
    for fut in asyncio.as_completed(tasks):
        await fut
        done += 1
        print(f"TTS: {done}/{total} tayyor", end="\r")
        if progress_cb:
            progress_cb(done / total)
    print()


def synthesize_all(segments: list[dict], progress_cb=None) -> list[dict]:
    print(f"TTS boshlandi ({len(segments)} ta segment, parallel: {MAX_PARALLEL_REQUESTS})...")
    asyncio.run(_synthesize_all_async(segments, progress_cb))

    need = [s for s in segments if _has_speakable_text((s.get("tarjima") or "").strip())]
    failed = [s for s in need if not s.get("audio_path")]

    if not need:
        raise RuntimeError(
            "Tarjima qilingan matn bo'sh — TTS uchun hech narsa yo'q. "
            "temp/translated.json dagi 'tarjima' maydonlarini tekshiring."
        )

    if len(failed) == len(need):
        err = failed[0].get("tts_error", "noma'lum xato")
        raise RuntimeError(
            f"TTS hech bir segment uchun ishlamadi. Birinchi xato: {err}. "
            f"'pip install -U edge-tts' ni bajaring va internetni tekshiring."
        )

    if failed:
        print(f"  ⚠ {len(failed)}/{len(need)} segmentda TTS muvaffaqiyatsiz "
              f"(ular jim qoladi).")

    print("✅ TTS tugadi")
    return segments


def synthesize_segment(text: str, segment_id: int, gender: str = "female") -> Path:
    """Yagona segment sinovi uchun (`python tts.py`)."""
    seg = {"tarjima": text, "gender": gender}
    asyncio.run(_synthesize_one(seg, segment_id, asyncio.Semaphore(1)))
    if not seg.get("audio_path"):
        raise RuntimeError(f"TTS ishlamadi: {seg.get('tts_error', 'noma`lum xato')}")
    return Path(seg["audio_path"])


if __name__ == "__main__":
    test_path = synthesize_segment(
        "Salom, bu sinov xabari. Dublyaj tizimi ishlayaptimi?",
        0,
        "male",
    )
    print(f"✅ Sinov audiosi yaratildi: {test_path}")
