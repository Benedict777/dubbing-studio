"""
gui.py — Dublyaj studiyasi oynasi
Ishga tushirish: loyiha ildizidagi start.bat ni ikki marta bosing.
"""

import sys
import os

import config  # birinchi bo'lib import qilinadi (model yo'llari)
from config import PROJECT_ROOT, TEMP_DIR, DEFAULT_OUTPUT_DIR

# pythonw.exe bilan ishga tushganda stdout/stderr bo'lmaydi — logga yo'naltiramiz
if sys.stdout is None or sys.stderr is None or os.path.basename(sys.executable).lower() == "pythonw.exe":
    _log = open(TEMP_DIR / "gui.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = _log
    sys.stderr = _log

import json
import queue
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

from dotenv import set_key
from i18n import TEXTS, LANG_NAMES
from pipeline import run_pipeline, Cancelled
from translate import GroqProblem, check_groq  # yengil: groq/torch kutubxonalari lazy import

SETTINGS_FILE = PROJECT_ROOT / "gui_settings.json"
VIDEO_EXTS = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v", ".mp3", ".wav")
STAGES = ["transcribe", "translate", "tts", "mix", "merge"]
ERR_COLOR = "#b00020"


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(data: dict):
    try:
        SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class App:
    def __init__(self):
        self.root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
        self.root.geometry("720x760")
        self.root.minsize(640, 700)

        s = load_settings()
        self.lang = tk.StringVar(value=s.get("lang", "uz"))
        self.gender = tk.StringVar(value=s.get("gender", "male"))  # standart: erkak
        self.video_path = ""
        self.output_dir = s.get("output_dir", "")

        self.q = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker = None
        self.running = False
        self.last_result = None
        self.current_stage = None
        self.status_key = ("idle", None)  # holat matni tilga qarab qayta chiziladi

        self._build()
        self.apply_language()
        self.root.after(100, self._poll)

    # ---------------------------------------------------------- UI
    def _build(self):
        pad = {"padx": 14, "pady": 6}
        style = ttk.Style()
        try:
            style.theme_use("vista" if os.name == "nt" else "clam")
        except tk.TclError:
            pass
        style.configure("Start.TButton", font=("Segoe UI", 12, "bold"), padding=8)

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        self.lbl_lang = ttk.Label(top)
        self.lbl_lang.pack(side="right", padx=(6, 0))
        self.cmb_lang = ttk.Combobox(
            top, state="readonly", width=12,
            values=[LANG_NAMES[k] for k in LANG_NAMES],
        )
        self.cmb_lang.set(LANG_NAMES[self.lang.get()])
        self.cmb_lang.pack(side="right")
        self.cmb_lang.bind("<<ComboboxSelected>>", self._on_lang)

        # 1. Video
        self.fr_video = ttk.LabelFrame(self.root)
        self.fr_video.pack(fill="x", **pad)
        self.drop = tk.Label(
            self.fr_video, height=5, relief="groove", bd=2,
            bg="#f3f6fb", fg="#33415c", font=("Segoe UI", 11), wraplength=620,
        )
        self.drop.pack(fill="x", padx=10, pady=(10, 4))
        if HAS_DND:
            self.drop.drop_target_register(DND_FILES)
            self.drop.dnd_bind("<<Drop>>", self._on_drop)
        row = ttk.Frame(self.fr_video)
        row.pack(fill="x", padx=10, pady=(0, 10))
        self.btn_video = ttk.Button(row, command=self.pick_video)
        self.btn_video.pack(side="left")
        self.lbl_video = ttk.Label(row, wraplength=480)
        self.lbl_video.pack(side="left", padx=10)

        # 2. Output
        self.fr_out = ttk.LabelFrame(self.root)
        self.fr_out.pack(fill="x", **pad)
        row = ttk.Frame(self.fr_out)
        row.pack(fill="x", padx=10, pady=(10, 2))
        self.btn_out = ttk.Button(row, command=self.pick_output)
        self.btn_out.pack(side="left")
        self.btn_reset = ttk.Button(row, command=self.reset_output)
        self.btn_reset.pack(side="left", padx=8)
        self.lbl_out = ttk.Label(self.fr_out, wraplength=640)
        self.lbl_out.pack(fill="x", padx=10, pady=(2, 10))

        # 3. Voice
        self.fr_voice = ttk.LabelFrame(self.root)
        self.fr_voice.pack(fill="x", **pad)
        row = ttk.Frame(self.fr_voice)
        row.pack(fill="x", padx=10, pady=10)
        self.rb_male = ttk.Radiobutton(row, variable=self.gender, value="male")
        self.rb_male.pack(side="left", padx=(0, 20))
        self.rb_female = ttk.Radiobutton(row, variable=self.gender, value="female")
        self.rb_female.pack(side="left")

        # 4. Groq API kaliti
        self.fr_api = ttk.LabelFrame(self.root)
        self.fr_api.pack(fill="x", **pad)
        row = ttk.Frame(self.fr_api)
        row.pack(fill="x", padx=10, pady=(10, 2))
        self.ent_key = ttk.Entry(row, show="•")
        self.ent_key.pack(side="left", fill="x", expand=True)
        self.ent_key.bind("<Return>", self.save_key)
        self.btn_key = ttk.Button(row, command=self.save_key)
        self.btn_key.pack(side="left", padx=(8, 0))
        self.lbl_key = ttk.Label(self.fr_api, wraplength=640, justify="left")
        self.lbl_key.pack(fill="x", padx=10, pady=(2, 10))

        # Start / Cancel
        row = ttk.Frame(self.root)
        row.pack(fill="x", **pad)
        self.btn_start = ttk.Button(row, style="Start.TButton", command=self.start)
        self.btn_start.pack(side="left", fill="x", expand=True)
        self.btn_cancel = ttk.Button(row, command=self.cancel, state="disabled")
        self.btn_cancel.pack(side="left", padx=(8, 0))

        # Progress
        self.fr_prog = ttk.LabelFrame(self.root)
        self.fr_prog.pack(fill="x", **pad)
        self.lbl_stage = ttk.Label(self.fr_prog, font=("Segoe UI", 10, "bold"))
        self.lbl_stage.pack(anchor="w", padx=10, pady=(10, 2))
        self.bar_stage = ttk.Progressbar(self.fr_prog, maximum=100)
        self.bar_stage.pack(fill="x", padx=10)
        self.lbl_overall = ttk.Label(self.fr_prog)
        self.lbl_overall.pack(anchor="w", padx=10, pady=(10, 2))
        self.bar_overall = ttk.Progressbar(self.fr_prog, maximum=100)
        self.bar_overall.pack(fill="x", padx=10, pady=(0, 6))
        self.lbl_status = ttk.Label(self.fr_prog, wraplength=640, justify="left")
        self.lbl_status.pack(fill="x", padx=10, pady=(4, 4))
        self.btn_open = ttk.Button(self.fr_prog, command=self.open_folder)
        # "Papkani ochish" tugmasi faqat tugagach ko'rsatiladi

    # ---------------------------------------------------------- tillar
    def T(self, _name, **kw):
        t = TEXTS[self.lang.get()][_name]
        return t.format(**kw) if kw else t

    def _on_lang(self, _e=None):
        for code, name in LANG_NAMES.items():
            if name == self.cmb_lang.get():
                self.lang.set(code)
        self.apply_language()
        self._save()

    def apply_language(self):
        self.root.title(self.T("title"))
        self.lbl_lang.config(text=self.T("language"))
        self.fr_video.config(text=self.T("video_label"))
        self.drop.config(text=self.T("drop_hint") if HAS_DND else self.T("drop_hint_nodnd"))
        self.btn_video.config(text=self.T("choose_video"))
        self.fr_out.config(text=self.T("output_label"))
        self.btn_out.config(text=self.T("choose_output"))
        self.btn_reset.config(text=self.T("reset_output"))
        self.fr_voice.config(text=self.T("voice_label"))
        self.rb_male.config(text=self.T("male"))
        self.rb_female.config(text=self.T("female"))
        self.fr_api.config(text=self.T("api_label"))
        self.btn_key.config(text=self.T("key_btn"))
        self._refresh_key_label()
        self.btn_start.config(text=self.T("start"))
        self.btn_cancel.config(text=self.T("cancel"))
        self.fr_prog.config(text=self.T("overall"))
        self.btn_open.config(text=self.T("open_folder"))
        self._refresh_video_label()
        self._refresh_output_label()
        self._refresh_status()

    def _refresh_video_label(self):
        self.lbl_video.config(text=Path(self.video_path).name if self.video_path else self.T("no_video"))

    def _refresh_output_label(self):
        if self.output_dir:
            self.lbl_out.config(text=self.output_dir)
        else:
            self.lbl_out.config(text=self.T("output_default", path=str(DEFAULT_OUTPUT_DIR)))

    def _refresh_status(self):
        kind, extra = self.status_key
        self.lbl_status.config(
            foreground=ERR_COLOR if kind in ("error", "groq_problem") else ""
        )
        if kind == "idle":
            self.lbl_stage.config(text=self.T("stage_idle"))
            self.lbl_status.config(text="")
        elif kind == "running" and extra:
            pct = int(self.bar_stage["value"])
            self.lbl_stage.config(text=f"{self.T('stage_' + extra)} — {pct}%")
            self.lbl_status.config(text="")
        elif kind == "groq_problem":
            pk, detail = extra
            self.lbl_stage.config(text=self.T("groq_problem_title"))
            text = self.T("groq_" + pk)
            if detail:
                text += f"\n\n{detail}"
            self.lbl_status.config(text=text)
        elif kind == "done":
            self.lbl_stage.config(text=self.T("done", path=extra))
            self.lbl_status.config(text="")
        elif kind == "cancelled":
            self.lbl_stage.config(text=self.T("cancelled"))
            self.lbl_status.config(text="")
        elif kind == "cancelling":
            self.lbl_stage.config(text=self.T("cancelling"))
        elif kind == "error":
            self.lbl_stage.config(text=self.T("error"))
            self.lbl_status.config(text=f"{extra}\n{self.T('log_hint')}")
        self.lbl_overall.config(text=f"{self.T('overall')} — {int(self.bar_overall['value'])}%")

    # ---------------------------------------------------------- tanlash
    def set_video(self, path: str):
        self.video_path = path
        self._refresh_video_label()

    def pick_video(self):
        if self.running:
            return
        exts = " ".join(f"*{e}" for e in VIDEO_EXTS)
        path = filedialog.askopenfilename(
            filetypes=[(self.T("video_filter"), exts), (self.T("all_files"), "*.*")]
        )
        if path:
            self.set_video(path)

    def _on_drop(self, event):
        if self.running:
            return
        files = self.root.tk.splitlist(event.data)
        for f in files:
            if f.lower().endswith(VIDEO_EXTS):
                self.set_video(f)
                return
        if files:
            self.set_video(files[0])

    def pick_output(self):
        if self.running:
            return
        d = filedialog.askdirectory(initialdir=self.output_dir or str(DEFAULT_OUTPUT_DIR.parent))
        if d:
            self.output_dir = os.path.normpath(d)
            self._refresh_output_label()
            self._save()

    def reset_output(self):
        if self.running:
            return
        self.output_dir = ""
        self._refresh_output_label()
        self._save()

    # ---------------------------------------------------------- jarayon
    def start(self):
        if self.running:
            return
        if not self.video_path or not os.path.exists(self.video_path):
            messagebox.showwarning(self.T("title"), self.T("need_video"))
            return
        self._save()
        self.running = True
        self.cancel_event.clear()
        self.btn_open.pack_forget()
        self.bar_stage["value"] = 0
        self.bar_overall["value"] = 0
        self.status_key = ("running", "transcribe")
        self._set_controls(False)
        self._refresh_status()

        video, gender, out = self.video_path, self.gender.get(), self.output_dir or None

        def work():
            try:
                def on_progress(stage, sp, op):
                    self.q.put(("progress", stage, sp, op))
                result = run_pipeline(video, gender, out, on_progress, self.cancel_event)
                self.q.put(("done", str(result)))
            except Cancelled:
                self.q.put(("cancelled",))
            except GroqProblem as e:
                self.q.put(("groq_problem", e.kind, e.detail))
            except Exception as e:
                traceback.print_exc()
                self.q.put(("error", f"{type(e).__name__}: {e}"))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def cancel(self):
        if self.running:
            self.cancel_event.set()
            self.btn_cancel.config(state="disabled")
            self.status_key = ("cancelling", None)
            self._refresh_status()

    def _set_controls(self, enabled: bool):
        st = "normal" if enabled else "disabled"
        for w in (self.btn_start, self.btn_video, self.btn_out, self.btn_reset,
                  self.rb_male, self.rb_female, self.btn_key, self.ent_key):
            w.config(state=st)
        self.btn_cancel.config(state="disabled" if enabled else "normal")

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    _, stage, sp, op = msg
                    if not self.cancel_event.is_set():
                        self.status_key = ("running", stage)
                    self.bar_stage["value"] = sp
                    self.bar_overall["value"] = op
                    self._refresh_status()
                elif kind == "done":
                    self.running = False
                    self.last_result = msg[1]
                    self.bar_stage["value"] = 100
                    self.bar_overall["value"] = 100
                    self.status_key = ("done", msg[1])
                    self._set_controls(True)
                    self._refresh_status()
                    self.btn_open.pack(anchor="w", padx=10, pady=(0, 10))
                elif kind == "cancelled":
                    self.running = False
                    self.status_key = ("cancelled", None)
                    self._set_controls(True)
                    self._refresh_status()
                elif kind == "error":
                    self.running = False
                    self.status_key = ("error", msg[1])
                    self._set_controls(True)
                    self._refresh_status()
                elif kind == "groq_problem":
                    self.running = False
                    self.status_key = ("groq_problem", (msg[1], msg[2]))
                    self._set_controls(True)
                    self._refresh_status()
                    if msg[1] in ("no_key", "bad_key"):
                        self.ent_key.focus_set()
                    messagebox.showerror(self.T("groq_problem_title"), self.T("groq_" + msg[1]))
                elif kind == "key_ok":
                    self.lbl_key.config(text=self.T("key_ok", model=msg[1]), foreground="")
                elif kind == "key_bad":
                    self.lbl_key.config(text=self.T("groq_" + msg[1]), foreground=ERR_COLOR)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    # ---------------------------------------------------------- Groq API kaliti
    @staticmethod
    def _mask(val: str) -> str:
        return (val[:4] + "…" + val[-4:]) if len(val) > 10 else "…"

    def _refresh_key_label(self):
        val = os.getenv("GROQ_API_KEY")
        self.lbl_key.config(
            text=self.T("key_current", key=self._mask(val)) if val else self.T("key_none"),
            foreground="",
        )

    def save_key(self, _e=None):
        if self.running:
            return
        v = self.ent_key.get().strip()
        if not v:
            return
        env_path = PROJECT_ROOT / ".env"
        if not env_path.exists():
            env_path.touch()
        set_key(str(env_path), "GROQ_API_KEY", v)   # .env faylini yangilaydi
        os.environ["GROQ_API_KEY"] = v              # darrov amalda ishlaydi
        self.ent_key.delete(0, "end")
        self._check_async()                          # yangi kalit/modelni tekshiradi

    def _check_async(self):
        """Yangi kalit/model ishlashini fon oqimida tekshiradi."""
        self.lbl_key.config(text=self.T("key_checking"), foreground="")

        def work():
            try:
                self.q.put(("key_ok", check_groq()))
            except GroqProblem as e:
                self.q.put(("key_bad", e.kind, e.detail))
            except Exception as e:
                self.q.put(("key_bad", "network", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def open_folder(self):
        if self.last_result:
            folder = str(Path(self.last_result).parent)
            try:
                os.startfile(folder)  # Windows
            except AttributeError:
                import subprocess
                subprocess.Popen(["xdg-open", folder])

    def _save(self):
        save_settings({
            "lang": self.lang.get(),
            "gender": self.gender.get(),
            "output_dir": self.output_dir,
        })

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self._save()
        self.cancel_event.set()
        self.root.destroy()
        os._exit(0)  # ishlayotgan fon oqimni to'xtatish


if __name__ == "__main__":
    App().run()
