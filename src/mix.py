"""
mix.py
------
Har bir segment uchun yaratilgan o'zbekcha audioni:
  1. Kerak bo'lsa original segment davomiyligiga moslab TEZLASHTIRADI
     (ffmpeg atempo). Sekinlashtirmaydi — tabiiy ovoz saqlanadi.
  2. To'g'ri timestamp'ga joylab, yagona audio yo'lakka birlashtiradi
  3. Original video audiosini almashtirib (yoki pasaytirib), yakuniy
     videoni chiqaradi

MUHIM: ffmpeg xatolari endi yashirilmaydi (stderr xabarga qo'shiladi),
va dublyaj audiosi butunlay jim bo'lsa, RuntimeError ko'tariladi —
ovozsiz video jimgina yaratilmaydi.
"""

import subprocess
from pathlib import Path

from pydub import AudioSegment

from config import TEMP_DIR, OUTPUT_DIR

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Tezlashtirish chegarasi (1.0 = o'zgarishsiz). Undan ortig'i tabiiy eshitilmaydi.
MAX_SPEEDUP = 1.5
# Shu farqdan kichik bo'lsa tezlashtirmaymiz
SPEEDUP_TOLERANCE = 1.05


def _run_ffmpeg(cmd: list[str]):
    """ffmpeg ni ishga tushiradi; xato bo'lsa, haqiqiy sababni ko'rsatadi."""
    try:
        subprocess.run(
            cmd, check=True, capture_output=True, creationflags=_NO_WINDOW
        )
    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg topilmadi. ffmpeg\\bin papkasi Windows PATH'ida ekanini "
            "tekshiring (README 4-qadam)."
        )
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg xatosi:\n{err[-1500:]}")


def _adjust_speed(audio_path: Path, target_duration_sec: float, index: int = 0) -> AudioSegment:
    """Audio segment uzun bo'lsa, target davomiylikka sig'ishi uchun tezlashtiradi."""
    audio = AudioSegment.from_file(audio_path)
    current = len(audio) / 1000.0

    if current <= 0 or target_duration_sec <= 0:
        return audio

    ratio = current / target_duration_sec  # >1 bo'lsa, audio slotdan uzun

    if ratio <= SPEEDUP_TOLERANCE:
        return audio  # sig'yapti (yoki qisqa) — tegmaymiz

    ratio = min(ratio, MAX_SPEEDUP)

    tmp_in = TEMP_DIR / f"tmp_speed_in_{index}.wav"
    tmp_out = TEMP_DIR / f"tmp_speed_out_{index}.wav"
    audio.export(tmp_in, format="wav")

    try:
        _run_ffmpeg([
            "ffmpeg", "-y", "-i", str(tmp_in),
            "-filter:a", f"atempo={ratio:.4f}",
            str(tmp_out),
        ])
        return AudioSegment.from_file(tmp_out)
    finally:
        for p in (tmp_in, tmp_out):
            try:
                p.unlink()
            except OSError:
                pass


def build_dubbed_audio(segments: list[dict], total_duration_sec: float, progress_cb=None) -> Path:
    """
    Barcha segmentlarni yagona audio yo'lakka joylaydi.
    Segmentlar orasidagi bo'sh joylar jim qoladi.
    """
    print("Audio segmentlar birlashtirilmoqda...")
    timeline = AudioSegment.silent(duration=int(total_duration_sec * 1000))

    used = 0
    total = max(len(segments), 1)

    for idx, seg in enumerate(segments, 1):
        if progress_cb:
            progress_cb(idx / total)

        audio_path = seg.get("audio_path")
        if not audio_path or not Path(audio_path).exists():
            continue  # TTS xato bergan segment — jim qoldiriladi

        target_dur = seg["end"] - seg["start"]
        adjusted = _adjust_speed(Path(audio_path), target_dur, idx)
        timeline = timeline.overlay(adjusted, position=int(seg["start"] * 1000))
        used += 1

    if used == 0:
        raise RuntimeError(
            "Birorta ham dublyaj audio segmenti topilmadi — video ovozsiz bo'lib "
            "qolardi. temp/tts_segments/ papkasini va TTS xatolarini tekshiring."
        )

    # Himoya: yakuniy audio butunlay jim emasligini tekshiramiz
    if timeline.max_dBFS == float("-inf"):
        raise RuntimeError("Yakuniy dublyaj audiosi butunlay jim chiqdi.")

    out_path = TEMP_DIR / "dubbed_audio.wav"
    timeline.export(out_path, format="wav")
    print(f"✅ Yagona dublyaj audiosi tayyor: {out_path} "
          f"({used}/{len(segments)} segment ishlatildi)")
    return out_path


def merge_with_video(
    original_video_path: str,
    dubbed_audio_path: Path,
    output_filename: str = "dublyaj_natija.mp4",
    keep_original_audio_volume: float = 0.0,  # 0.0 = original ovoz butunlay o'chadi
    output_dir=None,
) -> Path:
    """
    Yakuniy videoni yaratadi: original video + yangi o'zbekcha audio.
    keep_original_audio_volume: 0.0–1.0 (masalan 0.1 — fon ovozini biroz qoldirish)
    """
    out_dir = Path(output_dir or OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / output_filename

    if keep_original_audio_volume > 0:
        filter_complex = (
            f"[0:a]volume={keep_original_audio_volume}[orig];"
            f"[1:a]volume=1.0[dub];"
            f"[orig][dub]amix=inputs=2:duration=first:normalize=0[aout]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", str(original_video_path),
            "-i", str(dubbed_audio_path),
            "-filter_complex", filter_complex,
            "-map", "0:v:0", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            str(out_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(original_video_path),
            "-i", str(dubbed_audio_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(out_path),
        ]

    _run_ffmpeg(cmd)

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError(f"Yakuniy video yaratilmadi: {out_path}")

    print(f"✅ Yakuniy video tayyor: {out_path}")
    return out_path
