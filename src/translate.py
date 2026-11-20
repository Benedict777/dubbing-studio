"""
translate.py
------------
Har bir segmentni o'zbek tiliga tarjima qiladi.

ASOSIY USUL: Groq API (LLM asosida). Model nomi qattiq yozilmaydi:
GROQ_MODELS ro'yxatidagi birinchi ishlaydigan model ishlatiladi
(404 bo'lsa keyingisiga o'tadi). .env da GROQ_MODEL=... yozsangiz,
u birinchi sinab ko'riladi.

Segmentlar GURUH-GURUH (masalan 30 tadan) yuboriladi, va har bir guruhga
oldingi guruhning oxirgi bir nechta gapi KONTEKST sifatida qo'shiladi.

MUHIM: Groq kaliti yoki modeli ishlamasa, GroqProblem xatosi ko'tariladi
(GUI da user'ga "kalitni yoki modelni almashtiring" deb ko'rsatiladi).
check_groq() — jarayon boshlanishidan OLDIN kalit va modelni tekshiradi.

FALLBACK: Groq vaqtincha javob bermasa (format xatosi va h.k.),
deep-translator (Google Translate, kontekstsiz) ga o'tiladi. Agar u ham
butunlay ishlamasa — RuntimeError ko'tariladi.
"""

import os
import json
import time

import httpx

from config import TARGET_LANGUAGE, TEMP_DIR

# --- Guruhlash sozlamalari ---
BATCH_SIZE = 30          # bir so'rovda nechta segment tarjima qilinadi
CONTEXT_TAIL = 4         # oldingi guruhdan nechta gap kontekst sifatida qo'shiladi
MAX_RETRIES = 4
BASE_DELAY = 2.0

# Model ro'yxati: birinchisi ishlamasa (404), keyingisiga o'tadi.
GROQ_MODELS = [m for m in (
    os.getenv("GROQ_MODEL"),
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
) if m]

_active_model = None        # ishlagan model eslab qolinadi
_use_json_mode = True       # model qo'llamasa, o'chiriladi
_client = None
_client_key = None          # klient qaysi kalit bilan yaratilgani

# Tarjimani qayta tekshiradigan qo'shimcha so'rov (sifatni oshiradi,
# lekin API so'rovlarini ikki barobar ko'paytiradi).
ENABLE_PROOFREADING = True


# ==================================================================
# GROQ MUAMMOLARI
# ==================================================================

class GroqProblem(Exception):
    """Groq bilan bog'liq muammo. kind: no_key | bad_key | model | rate | network"""
    def __init__(self, kind: str, detail: str = ""):
        self.kind = kind
        self.detail = detail
        super().__init__(f"{kind}: {detail}")


def _short(e: Exception) -> str:
    return str(e).replace("\n", " ")[:300]


# ==================================================================
# GROQ KLIENTI
# ==================================================================

def _make_client():
    """Kalit o'zgargan bo'lsa (GUI da yangilangan), klient qayta yaratiladi."""
    global _client, _client_key
    key = os.getenv("GROQ_API_KEY")
    if _client is not None and key == _client_key:
        return _client
    from groq import Groq
    # IPv4 majburlanadi (IPv6 da osilib qolishning oldini oladi), vaqt chegarasi bor
    http_client = httpx.Client(
        transport=httpx.HTTPTransport(local_address="0.0.0.0"),
        timeout=90.0,
    )
    _client = Groq(api_key=key, http_client=http_client)
    _client_key = key
    return _client


def check_groq() -> str:
    """
    Groq kaliti va modelini tekshiradi. Ishlasa — ishlayotgan model nomini
    qaytaradi. Aks holda GroqProblem ko'taradi.
    """
    global _active_model
    if not os.getenv("GROQ_API_KEY"):
        raise GroqProblem("no_key")

    from groq import (
        AuthenticationError, RateLimitError, APIConnectionError, APIStatusError,
    )

    client = _make_client()
    _active_model = None

    # 1) Kalit ishlayaptimi + qaysi modellar mavjud
    try:
        available = sorted(m.id for m in client.models.list().data)
    except AuthenticationError as e:
        raise GroqProblem("bad_key", _short(e))
    except RateLimitError as e:
        raise GroqProblem("rate", _short(e))
    except APIConnectionError as e:
        raise GroqProblem("network", _short(e))
    except APIStatusError as e:
        if e.status_code in (401, 403):
            raise GroqProblem("bad_key", _short(e))
        raise GroqProblem("network", _short(e))
    except Exception as e:
        raise GroqProblem("network", _short(e))

    chat_models = [i for i in available
                   if not any(x in i.lower() for x in ("whisper", "guard", "tts", "playai"))]
    shown = "\n".join(f"  • {i}" for i in chat_models[:15])
    candidates = [m for m in GROQ_MODELS if m in available]

    if not candidates:
        raise GroqProblem(
            "model",
            f"Sinab ko'rilgan: {', '.join(GROQ_MODELS)}\nHozir mavjud modellar:\n{shown}",
        )

    # 2) Model haqiqatan javob beryaptimi (kichik sinov so'rovi)
    last_err = ""
    for model in candidates:
        try:
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=16,
            )
            _active_model = model
            return model
        except AuthenticationError as e:
            raise GroqProblem("bad_key", _short(e))
        except RateLimitError as e:
            raise GroqProblem("rate", _short(e))
        except APIConnectionError as e:
            raise GroqProblem("network", _short(e))
        except APIStatusError as e:      # 404, 400, 403 (model uchun ruxsat yo'q)...
            last_err = _short(e)
            continue

    raise GroqProblem("model", f"{last_err}\nHozir mavjud modellar:\n{shown}")


def _parse_json(raw: str) -> dict:
    """Javobdan JSON ni ajratib oladi (```json ... ``` o'ramini ham tushunadi)."""
    raw = (raw or "").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"JSON topilmadi: {raw[:200]!r}")
    return json.loads(raw[start:end + 1])


def _chat_json(prompt: str, temperature: float):
    """Groq'ga so'rov yuboradi, JSON dict qaytaradi (muvaffaqiyatsiz bo'lsa None)."""
    global _active_model, _use_json_mode
    from groq import NotFoundError, BadRequestError, AuthenticationError

    client = _make_client()
    models = [_active_model] if _active_model else GROQ_MODELS
    not_found = 0

    for model in models:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                kwargs = dict(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                )
                if _use_json_mode:
                    kwargs["response_format"] = {"type": "json_object"}

                resp = client.chat.completions.create(**kwargs)
                parsed = _parse_json(resp.choices[0].message.content)

                if _active_model != model:
                    print(f"  ✓ Groq modeli: {model}")
                _active_model = model
                return parsed

            except AuthenticationError as e:
                raise GroqProblem("bad_key", _short(e))
            except NotFoundError:
                print(f"  ⚠ Model mavjud emas: {model} — keyingisi sinaladi.")
                not_found += 1
                break
            except BadRequestError as e:
                if _use_json_mode:
                    print(f"  ⚠ JSON rejimi qo'llanmadi ({e}) — oddiy rejimda qayta uriniladi.")
                    _use_json_mode = False
                    continue
                print(f"  ⚠ {model}, urinish {attempt}/{MAX_RETRIES}: {e}")
                time.sleep(BASE_DELAY * attempt)
            except Exception as e:
                print(f"  ⚠ {model}, urinish {attempt}/{MAX_RETRIES}: {e}")
                time.sleep(BASE_DELAY * attempt)

        if _active_model:
            # ishlagan model ketma-ket xato bersa, ro'yxatni qayta ko'rib chiqamiz
            _active_model = None

    # Barcha modellar "topilmadi" desa — bu model muammosi, jimgina fallback emas
    if models and not_found == len(models):
        raise GroqProblem("model", f"Mavjud emas: {', '.join(models)}")
    return None


# ==================================================================
# PROMPTLAR
# ==================================================================

def _build_prompt(batch_texts: list[str], context_texts: list[str]) -> str:
    context_block = ""
    if context_texts:
        numbered_context = "\n".join(f"- {t}" for t in context_texts)
        context_block = (
            f"Oldingi suhbat konteksti (faqat tushunish uchun, "
            f"QAYTA TARJIMA QILMANG):\n{numbered_context}\n\n"
        )

    numbered_batch = "\n".join(f"{i+1}. {t}" for i, t in enumerate(batch_texts))

    prompt = (
        "Sen professional audiovizual tarjimonsan. Quyidagi video subtitr "
        "segmentlarini o'zbek tiliga tarjima qil.\n\n"
        f"{context_block}"
        "Tarjima qilinadigan segmentlar (har biri alohida raqamlangan):\n"
        f"{numbered_batch}\n\n"
        "QOIDALAR:\n"
        "- Tabiiy, so'zlashuv uslubidagi o'zbek tilida tarjima qil (adabiy "
        "emas, dublyaj uchun mos).\n"
        "- Kontekstni hisobga ol — bir xil ism, atama, uslub izchil bo'lsin.\n"
        "- Har bir segmentni ALOHIDA tarjima qil, lekin ma'no dialogga mos "
        "bo'lsin.\n"
        "- Faqat berilgan segmentlarni tarjima qil, kontekstni qayta yozma.\n"
        "- SO'ZMA-SO'Z tarjima qilishdan saqlan. Har gapning UMUMIY MA'NOSINI "
        "tabiiy o'zbekcha ifoda bilan yetkaz, hatto grammatik tuzilish "
        "boshqacha bo'lsa ham. Masalan, rus tilidagi \"не успел понять\" "
        "(ulgurmadi/vaqt topolmadi) kabi aspektual ma'noni \"tushunmay "
        "qoladi\" kabi tabiiy o'zbekcha konstruksiya bilan ber, so'zma-so'z "
        "\"tushunishga ulgurmadi\" deb emas.\n"
        "- Agar gap TUGALLANMAGAN bo'lsa (masalan \"…\" bilan tugasa yoki "
        "fikr uzilib qolgan bo'lsa), shu guruhdagi OLDINGI VA KEYINGI "
        "gaplarni o'qib, nazarda tutilgan ma'noni tushunishga harakat qil "
        "va tarjimani ham xuddi shunday tabiiy uzilgan holda, lekin to'g'ri "
        "ma'no bilan ber (ma'noni ixtiro qilma, faqat kontekstdan aniq "
        "chiqadigan narsani aks ettir).\n"
        "- FAQAT standart, adabiy me'yordagi o'zbek so'zlaridan foydalan. "
        "HECH QACHON so'z ixtiro qilma yoki mavjud bo'lmagan so'z shakli "
        "yasama.\n"
        "- Talaffuzi yoki yozilishi o'xshash, lekin ma'nosi butunlay boshqa "
        "so'zlarni CHALKASHTIRMA. Masalan:\n"
        "  * \"g'alati\" (qiziq/noodatiy) va \"g'arib\" (kambag'al/begona) "
        "— bular BOSHQA-BOSHQA so'z. \"странный/strange\" — \"g'alati\", "
        "\"g'arib\" EMAS.\n"
        "  * \"bezorilik\" (qo'pollik/tartibsizlik) so'zi to'g'ri shakl; "
        "\"bezoratlik\" degan so'z o'zbek tilida MAVJUD EMAS.\n"
        "  * Agar biror so'zning to'g'ri yozilishiga amin bo'lmasang, "
        "soddaroq va ishonchli so'z tanlang.\n"
        "- Javobni FAQAT quyidagi JSON formatida qaytar, boshqa hech qanday "
        "matn, izoh yoki markdown belgisi qo'shma:\n"
        '{"translations": ["tarjima1", "tarjima2", ...]}\n\n'
        "JSON massividagi elementlar soni aynan kirish segmentlari soniga "
        "teng bo'lishi SHART."
    )
    return prompt


def _build_proofread_prompt(source_texts: list[str], draft_translations: list[str]) -> str:
    pairs = "\n".join(
        f"{i+1}. MANBA: {src}\n   TARJIMA: {tr}"
        for i, (src, tr) in enumerate(zip(source_texts, draft_translations))
    )
    prompt = (
        "Sen o'zbek tili muharriri (proofreader)san. Quyida manba tildan "
        "(ingliz yoki rus) o'zbek tiliga qilingan tarjimalar ro'yxati "
        "berilgan. Vazifang — "
        "har bir tarjimani tekshirib, faqat quyidagi xatolarni tuzatish:\n"
        "- Mavjud bo'lmagan yoki ixtiro qilingan so'zlar (masalan "
        "\"bezoratlik\" — bunday so'z yo'q, to'g'risi \"bezorilik\").\n"
        "- Talaffuzi yaqin, lekin ma'nosi noto'g'ri so'z bilan almashtirilgan "
        "holatlar (masalan \"g'alati\" o'rniga \"g'arib\" yozilgan bo'lsa).\n"
        "- Grammatik yoki imlo xatolari.\n\n"
        "MUHIM: Agar tarjima allaqachon to'g'ri bo'lsa, uni O'ZGARTIRMA — "
        "faqat aniq xato bo'lgan joylarni tuzat. Ma'no yoki uslubni "
        "o'zgartirma, faqat xatolarni to'g'irla.\n\n"
        f"{pairs}\n\n"
        "Javobni FAQAT quyidagi JSON formatida qaytar, boshqa hech qanday "
        "matn qo'shma:\n"
        '{"corrected": ["tuzatilgan1", "tuzatilgan2", ...]}\n\n'
        "JSON massividagi elementlar soni aynan kirish tarjimalari soniga "
        "teng bo'lishi SHART."
    )
    return prompt


# ==================================================================
# GROQ ORQALI TARJIMA
# ==================================================================

def _call_groq(prompt: str) -> list[str] | None:
    parsed = _chat_json(prompt, temperature=0.3)
    if parsed and isinstance(parsed.get("translations"), list):
        return parsed["translations"]
    if parsed:
        print(f"  ⚠ Groq javobi kutilgan formatda emas: {str(parsed)[:200]!r}")
    return None


def _proofread_batch_groq(source_texts: list[str], draft_translations: list[str]) -> list[str]:
    prompt = _build_proofread_prompt(source_texts, draft_translations)
    parsed = _chat_json(prompt, temperature=0.1)
    corrected = parsed.get("corrected") if parsed else None
    if isinstance(corrected, list) and len(corrected) == len(draft_translations):
        return corrected
    print("  ⚠ Proofread natijasi mos kelmadi, original tarjima qoldiriladi.")
    return draft_translations


def _translate_batch_groq(batch_texts: list[str], context_texts: list[str]) -> list[str] | None:
    if not batch_texts:
        return []

    prompt = _build_prompt(batch_texts, context_texts)
    translations = _call_groq(prompt)

    if translations is None:
        return None

    if len(translations) != len(batch_texts):
        print(f"  ⚠ Groq {len(batch_texts)} ta kutilgan edi, "
              f"{len(translations)} ta qaytardi — bu guruh fallback'ga o'tadi.")
        return None

    return [str(t) for t in translations]


# ==================================================================
# FALLBACK: deep-translator (Google Translate, kontekstsiz)
# ==================================================================

ERROR_SIGNATURES = (
    "error 500", "that’s an error", "that's an error",
    "that’s all we know", "that's all we know",
    "<html", "<!doctype", "server error",
)


def _looks_like_error(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(sig in lowered for sig in ERROR_SIGNATURES)


def _translate_batch_fallback(batch_texts: list[str]) -> list[str]:
    from deep_translator import GoogleTranslator
    translator = GoogleTranslator(source="auto", target=TARGET_LANGUAGE)

    results = []
    for text in batch_texts:
        if not text:
            results.append("")
            continue

        translated = text  # eng oxirgi chora — original matn
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                candidate = translator.translate(text)
            except Exception as e:
                candidate = None
                print(f"    ⚠ Fallback tarjima xatosi, urinish {attempt}: {e}")

            if candidate and not _looks_like_error(candidate):
                translated = candidate
                break
            time.sleep(BASE_DELAY * attempt)
        else:
            print(f"    ❌ Fallback ham muvaffaqiyatsiz: {text!r} — "
                  f"original matn saqlanadi.")

        results.append(translated)
        time.sleep(1.0)

    # Hech bir segment tarjima bo'lmagan bo'lsa — jim davom etmaymiz
    nonempty = [(r, t) for r, t in zip(results, batch_texts) if t]
    if nonempty and all(r == t for r, t in nonempty):
        raise RuntimeError(
            "Tarjima umuman ishlamadi (Groq xato berdi, Google ham rad etdi). "
            "Groq modelini (GROQ_MODELS) va API kalitni tekshiring."
        )
    return results


# ==================================================================
# ASOSIY FUNKSIYA
# ==================================================================

def translate_segments(segments: list[dict], progress_cb=None) -> list[dict]:
    total = len(segments)
    print(f"Tarjima qilinmoqda ({total} ta segment, guruh hajmi: {BATCH_SIZE})...")

    provider = os.getenv("TRANSLATE_PROVIDER", "groq")  # "groq" yoki "google"
    use_groq = provider == "groq"
    if use_groq and not os.getenv("GROQ_API_KEY"):
        raise GroqProblem("no_key")
    if not use_groq:
        print("  ⚠ Google Translate (deep-translator) ishlatiladi.")

    all_texts = [seg["text"].strip() for seg in segments]
    last_context: list[str] = []
    groq_failures = 0
    fallback_used_count = 0

    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch_texts = all_texts[start:end]

        batch_result = None
        if use_groq:
            batch_result = _translate_batch_groq(batch_texts, last_context)
            if batch_result is None:
                groq_failures += 1

        if batch_result is None:
            print(f"  ↪ Segment {start+1}-{end}: fallback (Google Translate) ishlatilmoqda...")
            batch_result = _translate_batch_fallback(batch_texts)
            fallback_used_count += (end - start)
        elif ENABLE_PROOFREADING and use_groq:
            print(f"  🔍 Segment {start+1}-{end}: tarjima tekshirilmoqda (proofreading)...")
            batch_result = _proofread_batch_groq(batch_texts, batch_result)

        for i, translated in enumerate(batch_result):
            segments[start + i]["tarjima"] = translated

        # Keyingi guruh uchun kontekst — manba tildagi oxirgi gaplar
        last_context = batch_texts[-CONTEXT_TAIL:]

        print(f"  [{end}/{total}] guruh tarjima qilindi.")
        if progress_cb:
            progress_cb(end / total)

    out_path = TEMP_DIR / "translated.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    print(f"✅ Tarjima tayyor: {out_path}")
    if groq_failures:
        print(f"⚠ {groq_failures} ta guruhda Groq muvaffaqiyatsiz bo'lib, "
              f"fallback ishlatildi ({fallback_used_count} ta segment).")

    return segments


if __name__ == "__main__":
    with open(TEMP_DIR / "transcript.json", encoding="utf-8") as f:
        segs = json.load(f)
    translate_segments(segs)
