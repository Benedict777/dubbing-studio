"""
config.py
---------
Loyihaning barcha sozlamalari va papka yo'llari shu yerda.
MUHIM: Bu fayl barcha model va vaqtinchalik fayllarni
loyiha papkasi ichida saqlashni ta'minlaydi —
hech narsa C diskka (foydalanuvchi profiliga) tushmaydi.
"""

import os
from pathlib import Path

# ------------------------------------------------------------
# LOYIHA ILDIZ PAPKASI (bu fayl joylashgan joydan avtomatik topiladi)
# ------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # src/ dan bir daraja yuqori

# Faqat buyruq qatori rejimi (main.py) uchun. GUI ularni ishlatmaydi va
# ular AVTOMATIK YARATILMAYDI — faqat kerak bo'lganda yaratiladi.
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"

# Ichki ishlar uchun (har doim kerak):
TEMP_DIR = PROJECT_ROOT / "temp"         # vaqtinchalik audio/matn fayllari, gui.log
MODELS_DIR = PROJECT_ROOT / "models"     # AI modellari (Whisper va h.k.) shu yerda saqlanadi

for d in (TEMP_DIR, MODELS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------
# MUHIM: Hugging Face / Torch modellarini loyiha papkasiga majburlash
# (Bu qatorlar boshqa hech narsa import qilinmasdan OLDIN ishlashi shart,
#  shuning uchun main.py va gui.py eng birinchi shu faylni import qiladi)
# ------------------------------------------------------------
os.environ["HF_HOME"] = str(MODELS_DIR / "huggingface")
os.environ["TORCH_HOME"] = str(MODELS_DIR / "torch")
os.environ["XDG_CACHE_HOME"] = str(MODELS_DIR / "cache")

# ------------------------------------------------------------
# WHISPER SOZLAMALARI
# ------------------------------------------------------------
# model o'lchami: "tiny", "base", "small", "medium", "large-v3"
# Kompyuteringiz kuchiga qarab tanlang. Boshlash uchun "medium" yetarli.
WHISPER_MODEL_SIZE = "medium"

# GPU bormi? Agar NVIDIA GPU bo'lsa "cuda", bo'lmasa "cpu" qoldiring.
DEVICE = "cuda"          # GPU yo'q bo'lsa "cpu" qiling
COMPUTE_TYPE = "float16"   # GPU uchun "float16"; CPU uchun "int8"

# Manba video qaysi tilda ekanligini bilsangiz shu yerga yozing (masalan "en", "ru")
# Bilmasangiz None qoldiring — Whisper avtomatik aniqlaydi.
SOURCE_LANGUAGE = None

# Diarization uchun: videoda nechta spiker borligini bilsangiz shu yerga yozing.
MIN_SPEAKERS = 2
MAX_SPEAKERS = 2

# ------------------------------------------------------------
# TARJIMA SOZLAMALARI
# ------------------------------------------------------------
TARGET_LANGUAGE = "uz"  # o'zbek tiliga tarjima

# ------------------------------------------------------------
# API KALITLAR (.env faylidan o'qiladi, kodga yozmang!)
# ------------------------------------------------------------
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Keyinroq TTS provayderi tanlanganda shu yerga uning kaliti ham qo'shiladi:
# TTS_API_KEY = os.getenv("TTS_API_KEY")

# ------------------------------------------------------------
# GUI: chiqish papkasi tanlanmasa shu yerga saqlanadi (avtomatik yaratiladi)
# ------------------------------------------------------------
DEFAULT_OUTPUT_DIR = Path(r"D:\Dublyaj_output")
