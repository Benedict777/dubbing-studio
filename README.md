# Dubbing Studio / Dublyaj studiyasi

English first, Uzbek below / Avval inglizcha, pastda o'zbekcha.

---

# English

Dubs a video into Uzbek:
video → speech recognition (Whisper) → translation (Groq) → Uzbek voice (edge-tts) → new video.

## Requirements

- Windows 10/11
- NVIDIA GPU (for CPU only, see Troubleshooting)
- Internet connection
- Free accounts: [Groq](https://console.groq.com/keys) (API key) and [Hugging Face](https://huggingface.co/settings/tokens) (token, optional, for speaker separation)

## Setup

**1. Place the project.** Put the folder at `D:\dublyaj_loyiha\`. (Any drive works; models and temp files are stored inside the project folder.)

**2. Install Python 3.11** from https://www.python.org/downloads/. Tick "Add Python to PATH" during install.

**3. Create the virtual environment.** Open `cmd`:

```cmd
D:
cd D:\dublyaj_loyiha
python -m venv venv
venv\Scripts\activate
```

`(venv)` should appear at the start of the line.

**4. Install FFmpeg.**
1. Download "release full" from https://www.gyan.dev/ffmpeg/builds/ and unzip it.
2. Rename the folder to `ffmpeg` and put it in `D:\dublyaj_loyiha\` (so `D:\dublyaj_loyiha\ffmpeg\bin\ffmpeg.exe` exists).
3. Add `D:\dublyaj_loyiha\ffmpeg\bin` to the system **Path** (Windows search → "Edit the system environment variables" → Environment Variables → Path → New).
4. Open a new `cmd` and run `ffmpeg -version`. It must print a version.

**5. Install libraries** (venv active, inside `D:\dublyaj_loyiha`):

```cmd
pip install -r requirements.txt
```

This takes a while (torch is large).

**6. Create the `.env` file** in `D:\dublyaj_loyiha\` with:

```
GROQ_API_KEY=your_groq_key
HF_TOKEN=your_huggingface_token
```

- `GROQ_API_KEY` is required (translation). You can also enter it later in the app.
- `HF_TOKEN` is optional. Without it, all speech is treated as one speaker. If the diarization model asks for access, open its page on huggingface.co and accept the terms.

## Run

Double-click **`start.bat`**. In the window:

1. Choose or drag in a video.
2. (Optional) choose the output folder. Default: `D:\Dublyaj_output`.
3. Choose a male or female voice.
4. Check the Groq API key (field 4). Press **Update** to save a new key; the app checks it immediately.
5. Press **Start dubbing**.

The first run downloads AI models (several GB) and is slow. The result is saved as `<video name>_uz.mp4`.

The app checks the Groq key and model **before** processing starts, so you do not wait for nothing.

Command line (optional), from `D:\dublyaj_loyiha\src`:

```cmd
python main.py "C:\Videos\video.mp4"
python continue_from_translation.py "C:\Videos\video.mp4"
```

The second command skips transcription and translation and reuses `temp/translated.json`.

## Troubleshooting

Detailed errors are in `temp/gui.log`. To see errors live, run `start_debug.bat` instead of `start.bat`.

| Message / problem | What to do |
|---|---|
| **Groq API key not entered** | Enter the key in field 4 of the window and press Update. |
| **Groq API key does not work** (invalid, expired, revoked) | Create a new key at https://console.groq.com/keys and enter it in field 4. |
| **Groq MODEL does not work** (removed or no access) | Models change often. The message shows the models available to you. You can also check the list at https://console.groq.com/docs/models or by running `python test_groq.py` in `src`. Pick one and add `GROQ_MODEL=model_name` to `.env`, or edit `GROQ_MODELS` in `translate.py`. **Restart the app.** |
| **Groq rate limit reached** | Wait a few minutes, or use another key. See https://console.groq.com/settings/limits. |
| **Cannot reach Groq server** | Check your internet, VPN, or firewall, then try again. |
| `ffmpeg not found` | Redo step 4. Make sure `ffmpeg\bin` is in Path, then reopen the app (or restart the PC). |
| TTS error `403` / TTS failed | Run `pip install -U edge-tts` (venv active). Check your internet. |
| Translation looks like English | Groq failed and Google Translate was rate-limited. Fix the Groq problem above and run again. |
| CUDA / GPU error | No NVIDIA GPU or drivers? In `src/config.py` set `DEVICE = "cpu"` and `COMPUTE_TYPE = "int8"`. It will be slower. |
| Model download timeout (Hugging Face) | Just run again, the download resumes. |
| Wrong number of speakers | Edit `MIN_SPEAKERS` / `MAX_SPEAKERS` in `src/config.py`. |
| `torchcodec` warning in the log | Harmless. Ignore it. |

## Folders

```
dublyaj_loyiha\
├── venv\        Python libraries
├── ffmpeg\      FFmpeg
├── models\      downloaded AI models
├── temp\        transcript, translation, audio pieces, gui.log
├── src\         code
├── .env         your keys
└── start.bat    start the app
```

---

# O'zbekcha

Videoni o'zbek tiliga dublyaj qiladi:
video → nutqni matnga o'girish (Whisper) → tarjima (Groq) → o'zbekcha ovoz (edge-tts) → yangi video.

## Talablar

- Windows 10/11
- NVIDIA videokarta (faqat protsessor uchun "Xatolarni tuzatish" bo'limiga qarang)
- Internet
- Bepul akkauntlar: [Groq](https://console.groq.com/keys) (API kalit) va [Hugging Face](https://huggingface.co/settings/tokens) (token, ixtiyoriy, spikerlarni ajratish uchun)

## O'rnatish

**1. Loyihani joylashtiring.** Papkani `D:\dublyaj_loyiha\` ga qo'ying. (Boshqa disk ham bo'ladi; modellar va vaqtinchalik fayllar loyiha papkasi ichida saqlanadi.)

**2. Python 3.11 o'rnating:** https://www.python.org/downloads/. O'rnatishda "Add Python to PATH" ni belgilang.

**3. Virtual environment yarating.** `cmd` oching:

```cmd
D:
cd D:\dublyaj_loyiha
python -m venv venv
venv\Scripts\activate
```

Qator boshida `(venv)` yozuvi chiqishi kerak.

**4. FFmpeg o'rnating.**
1. https://www.gyan.dev/ffmpeg/builds/ dan "release full" ni yuklab, arxivdan chiqaring.
2. Papka nomini `ffmpeg` qilib, `D:\dublyaj_loyiha\` ichiga qo'ying (`D:\dublyaj_loyiha\ffmpeg\bin\ffmpeg.exe` bo'lishi kerak).
3. `D:\dublyaj_loyiha\ffmpeg\bin` ni tizim **Path** ga qo'shing (Windows qidiruvi → "Edit the system environment variables" → Environment Variables → Path → New).
4. Yangi `cmd` ochib `ffmpeg -version` yozing. Versiya chiqishi kerak.

**5. Kutubxonalarni o'rnating** (venv faol, `D:\dublyaj_loyiha` ichida):

```cmd
pip install -r requirements.txt
```

Biroz vaqt oladi (torch katta).

**6. `.env` faylini yarating** (`D:\dublyaj_loyiha\` ichida):

```
GROQ_API_KEY=sizning_groq_kalitingiz
HF_TOKEN=sizning_huggingface_tokeningiz
```

- `GROQ_API_KEY` majburiy (tarjima uchun). Uni keyinroq dasturning o'zida ham kiritish mumkin.
- `HF_TOKEN` ixtiyoriy. Usiz barcha nutq bitta spiker deb olinadi. Diarization modeli ruxsat so'rasa, huggingface.co dagi model sahifasini ochib shartlarni qabul qiling.

## Ishga tushirish

**`start.bat`** ni ikki marta bosing. Oynada:

1. Videoni tanlang yoki sudrab tashlang.
2. (Ixtiyoriy) natija papkasini tanlang. Standart: `D:\Dublyaj_output`.
3. Erkak yoki ayol ovozini tanlang.
4. Groq API kalitini tekshiring (4-maydon). Yangi kalit uchun **Yangilash** ni bosing; dastur uni darrov tekshiradi.
5. **Dublyajni boshlash** ni bosing.

Birinchi ishga tushirishda AI modellar yuklanadi (bir necha GB), shuning uchun sekin bo'ladi. Natija `<video nomi>_uz.mp4` nomi bilan saqlanadi.

Dastur Groq kaliti va modelini ishlov **boshlanishidan oldin** tekshiradi, shuning uchun bekorga kutmaysiz.

Buyruq qatori orqali (ixtiyoriy), `D:\dublyaj_loyiha\src` ichidan:

```cmd
python main.py "C:\Videos\video.mp4"
python continue_from_translation.py "C:\Videos\video.mp4"
```

Ikkinchi buyruq matnga o'girish va tarjimani o'tkazib yuboradi, `temp/translated.json` dan foydalanadi.

## Xatolarni tuzatish

Batafsil xatolar `temp/gui.log` da. Xatolarni jonli ko'rish uchun `start.bat` o'rniga `start_debug.bat` ni ishga tushiring.

| Xabar / muammo | Nima qilish kerak |
|---|---|
| **Groq API kaliti kiritilmagan** | Oynadagi 4-maydonga kalitni kiriting va Yangilash ni bosing. |
| **Groq API kaliti ishlamayapti** (noto'g'ri, muddati o'tgan, bekor qilingan) | https://console.groq.com/keys dan yangi kalit yarating va 4-maydonga kiriting. |
| **Groq MODELI ishlamayapti** (o'chirilgan yoki ruxsat yo'q) | Modellar tez-tez o'zgaradi. Xabarda sizga mavjud modellar ro'yxati chiqadi. Ro'yxatni https://console.groq.com/docs/models sahifasidan yoki `src` papkasida `python test_groq.py` orqali ham ko'rishingiz mumkin. Bittasini tanlab, `.env` ga `GROQ_MODEL=model_nomi` deb yozing yoki `translate.py` dagi `GROQ_MODELS` ni o'zgartiring. **Dasturni qayta oching.** |
| **Groq so'rovlar limiti tugagan** | Bir necha daqiqa kuting yoki boshqa kalit ishlating. Limitlar: https://console.groq.com/settings/limits. |
| **Groq serveriga ulanib bo'lmadi** | Internet, VPN yoki firewall ni tekshiring va qayta urining. |
| `ffmpeg topilmadi` | 4-qadamni qayta bajaring. `ffmpeg\bin` Path da ekanini tekshirib, dasturni qayta oching (yoki kompyuterni qayta yoqing). |
| TTS xatosi `403` / TTS ishlamadi | venv faol holda `pip install -U edge-tts` ni bajaring. Internetni tekshiring. |
| Tarjima inglizcha chiqdi | Groq xato bergan va Google Translate ham limitga tushgan. Yuqoridagi Groq muammosini tuzatib, qayta ishga tushiring. |
| CUDA / GPU xatosi | NVIDIA videokarta yoki drayver yo'qmi? `src/config.py` da `DEVICE = "cpu"` va `COMPUTE_TYPE = "int8"` qiling. Sekinroq ishlaydi. |
| Model yuklashda vaqt tugadi (Hugging Face) | Qayta ishga tushiring, yuklash davom etadi. |
| Spikerlar soni noto'g'ri | `src/config.py` da `MIN_SPEAKERS` / `MAX_SPEAKERS` ni o'zgartiring. |
| Logda `torchcodec` ogohlantirishi | Zararsiz. E'tibor bermang. |

## Papkalar

```
dublyaj_loyiha\
├── venv\        Python kutubxonalari
├── ffmpeg\      FFmpeg
├── models\      yuklangan AI modellar
├── temp\        transkript, tarjima, audio bo'laklar, gui.log
├── src\         kodlar
├── .env         sizning kalitlaringiz
└── start.bat    dasturni ishga tushirish
```
