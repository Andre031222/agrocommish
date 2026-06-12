import csv
import ctypes
import json
import socket
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from core.detector       import detectar_puertos, puertos_como_set
from core.flasher        import Flasher
from core.provisioner    import Provisioner, esperar_dispositivo, validar_lecturas
from core.config_manager import cargar as cfg_cargar, guardar as cfg_guardar
from core.qr_generator   import generar_qr, guardar_qr
from core.lang           import T, set_lang, get_lang

if getattr(sys, 'frozen', False):
    BASE_DIR      = Path(sys.executable).parent
    _MEIPASS_DIR  = Path(sys._MEIPASS)
else:
    BASE_DIR      = Path(__file__).parent
    _MEIPASS_DIR  = BASE_DIR

FIRMWARE_DIR     = BASE_DIR / "firmware"
LOGS_DIR         = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

_fw_bundled      = _MEIPASS_DIR / "firmware" / "firmware.bin"
_fw_external     = FIRMWARE_DIR / "firmware.bin"
DEFAULT_FIRMWARE = _fw_bundled if _fw_bundled.exists() else _fw_external

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

C_BG        = "#F2F2F7"
C_SURFACE   = "#FFFFFF"
C_BLUE      = "#007AFF"
C_BLUE_DK   = "#0062CC"
C_GREEN     = "#34C759"
C_RED       = "#FF3B30"
C_ORANGE    = "#FF9500"
C_TEXT      = "#1D1D1F"
C_TEXT2     = "#3C3C43"
C_TEXT3     = "#8A8A8E"
C_SEP       = "#E5E5EA"
C_STEP_DONE = "#34C759"
C_STEP_ACT  = "#007AFF"
C_STEP_OFF  = "#C7C7CC"
C_INPUT_BG  = "#F2F2F7"
C_SIDEBAR   = "#F9F9FB"

FONT_TITLE   = None
FONT_BODY    = None
FONT_SMALL   = None
FONT_MONO    = None
FONT_MONO_L  = None
FONT_CAPTION = None


def _spinner_frames() -> list[str]:
    return ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def _ip_local() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _puerto_abierto(host: str, puerto: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, puerto), timeout=timeout):
            return True
    except OSError:
        return False


def _api_base_local(server_url: str) -> str:
    parsed = urllib.parse.urlparse(server_url)
    if not parsed.scheme or not parsed.netloc:
        return "http://localhost:5000"
    host   = parsed.hostname or ""
    puerto = parsed.port or (443 if parsed.scheme == "https" else 80)
    es_lan = (host.startswith("192.168.") or host.startswith("10.") or
              host.startswith("127.") or host == "localhost" or
              any(host.startswith(f"172.{n}.") for n in range(16, 32)))
    if es_lan and _puerto_abierto("localhost", puerto, timeout=1.0):
        return f"{parsed.scheme}://localhost:{puerto}"
    return f"{parsed.scheme}://{parsed.netloc}"


def _titulo_claro(win):
    if sys.platform != "win32":
        return
    try:
        hwnd  = ctypes.windll.user32.GetParent(win.winfo_id())
        valor = ctypes.c_int(0)
        for attr in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(valor), ctypes.sizeof(valor))
    except (OSError, AttributeError):
        pass


def _load_logo(size: int) -> "ctk.CTkImage | None":
    try:
        img = Image.open(BASE_DIR / "assets" / "icon.ico").convert("RGBA")
        img = img.resize((size, size), Image.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    except (OSError, ValueError):
        return None


class SplashScreen:

    _STEPS_ES = [
        (0,    0.0,  "Iniciando AgroCommish…"),
        (450,  0.25, "Cargando interfaz…"),
        (900,  0.55, "Verificando dependencias…"),
        (1400, 0.80, "Preparando puertos…"),
        (1900, 1.0,  "¡Todo listo!"),
        (2350, 1.0,  None),
    ]
    _STEPS_EN = [
        (0,    0.0,  "Starting AgroCommish…"),
        (450,  0.25, "Loading interface…"),
        (900,  0.55, "Checking dependencies…"),
        (1400, 0.80, "Preparing ports…"),
        (1900, 1.0,  "All set!"),
        (2350, 1.0,  None),
    ]

    def __init__(self, master: ctk.CTk, on_done):
        self._on_done = on_done
        w, h = 420, 290

        self._win = ctk.CTkToplevel(master)
        self._win.overrideredirect(True)
        self._win.configure(fg_color=C_SURFACE)
        self._win.resizable(False, False)

        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        self._win.geometry(f"{w}x{h}+{x}+{y}")

        outer = ctk.CTkFrame(self._win, fg_color=C_SEP, corner_radius=16)
        outer.pack(fill="both", expand=True, padx=1, pady=1)

        inner = ctk.CTkFrame(outer, fg_color=C_SURFACE, corner_radius=15)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        _splash_logo = _load_logo(56)
        if _splash_logo:
            self._splash_logo_ref = _splash_logo
            ctk.CTkLabel(inner, image=_splash_logo, text="").pack(pady=(32, 0))
        else:
            logo_wrap = ctk.CTkFrame(inner, width=64, height=64,
                                     fg_color="#DCFCE7", corner_radius=18)
            logo_wrap.pack(pady=(32, 0))
            logo_wrap.pack_propagate(False)
            ctk.CTkLabel(logo_wrap, text="◆",
                         font=ctk.CTkFont(size=30)).pack(expand=True)

        ctk.CTkLabel(inner, text="AgroCommish",
                     font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
                     text_color=C_TEXT).pack(pady=(12, 2))

        ctk.CTkLabel(inner, text="Configurador IoT  •  v1.0",
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=C_TEXT3).pack()

        ctk.CTkFrame(inner, height=16, fg_color="transparent").pack()

        self._bar = ctk.CTkProgressBar(inner, width=320, height=5,
                                       corner_radius=3,
                                       fg_color=C_BG,
                                       progress_color=C_BLUE)
        self._bar.set(0)
        self._bar.pack(padx=50)

        self._lbl = ctk.CTkLabel(inner, text="",
                                 font=ctk.CTkFont(family="Segoe UI", size=11),
                                 text_color=C_TEXT3)
        self._lbl.pack(pady=(8, 0))

        self._win.lift()
        self._win.focus_force()
        self._win.update()

        self._run_animation()

    def _run_animation(self):
        steps = self._STEPS_EN if get_lang() == "en" else self._STEPS_ES
        for delay, progress, text in steps:
            self._win.after(delay, lambda p=progress, t=text: self._tick(p, t))

    def _tick(self, progress: float, text):
        if not self._win.winfo_exists():
            return
        self._bar.set(progress)
        if text is None:
            self._win.destroy()
            self._on_done()
        else:
            self._lbl.configure(text=text)


class Toast:

    ESTILOS = {
        "success": ("✓", "#16A34A", "#DCFCE7", "#BBF7D0"),
        "error":   ("✗", "#DC2626", "#FEE2E2", "#FECACA"),
        "warn":    ("⚠", "#D97706", "#FEF9C3", "#FDE68A"),
        "info":    ("●", "#0284C7", "#E0F2FE", "#BAE6FD"),
    }

    _activo: "Toast | None" = None
    _Y_FINAL = 16
    _Y_INICIO = -90

    def __init__(self, master, tipo: str, titulo: str, detalle: str = "", ms: int = 3400):
        if Toast._activo:
            Toast._activo.cerrar()
        Toast._activo = self

        icono, color, bg, borde = self.ESTILOS.get(tipo, self.ESTILOS["info"])
        self._master = master
        self._vivo   = True

        self._frame = ctk.CTkFrame(master, fg_color=C_SURFACE, corner_radius=12,
                                   border_width=1, border_color=borde)
        fila = ctk.CTkFrame(self._frame, fg_color="transparent")
        fila.pack(padx=16, pady=12)

        circulo = ctk.CTkLabel(
            fila, text=icono, width=34, height=34,
            fg_color=bg, corner_radius=17, text_color=color,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"))
        circulo.pack(side="left")

        col = ctk.CTkFrame(fila, fg_color="transparent")
        col.pack(side="left", padx=(12, 4))
        ctk.CTkLabel(col, text=titulo,
                     font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                     text_color=C_TEXT, anchor="w",
                     justify="left").pack(anchor="w")
        if detalle:
            ctk.CTkLabel(col, text=detalle, font=FONT_SMALL,
                         text_color=C_TEXT3, anchor="w", justify="left",
                         wraplength=380).pack(anchor="w")

        self._frame.place(relx=0.985, y=self._Y_INICIO, anchor="ne")
        self._animar(0, self._Y_INICIO, self._Y_FINAL, al_terminar=lambda:
                     master.after(ms, self._salir))

    def _animar(self, i: int, y0: int, y1: int, al_terminar=None):
        if not self._vivo:
            return
        PASOS = 12
        if i > PASOS:
            if al_terminar:
                al_terminar()
            return
        t = i / PASOS
        ease = 1 - (1 - t) ** 3
        self._frame.place_configure(y=int(y0 + (y1 - y0) * ease))
        self._master.after(14, lambda: self._animar(i + 1, y0, y1, al_terminar))

    def _salir(self):
        if not self._vivo:
            return
        self._animar(0, self._Y_FINAL, self._Y_INICIO, al_terminar=self.cerrar)

    def cerrar(self):
        if not self._vivo:
            return
        self._vivo = False
        if Toast._activo is self:
            Toast._activo = None
        try:
            self._frame.destroy()
        except tk.TclError:
            pass


class AgroFlasher(ctk.CTk):

    STEP_KEYS = ["step_1", "step_2", "step_3", "step_4", "step_5"]
    STEP_NUMS = ["1", "2", "3", "4", "5"]

    STEP_ICONS = [
        ("◉", "#EAF2FF", "#C5D8FF"),
        ("▼", "#F0EBFF", "#D9C8FF"),
        ("◎", "#EAFAF1", "#B8EDD4"),
        ("◇", "#FFF0EB", "#FFCBB8"),
        ("◆", "#DCFCE7", "#BBF7D0"),
    ]

    def __init__(self):
        super().__init__()
        self.withdraw()

        _cfg = cfg_cargar()
        set_lang(_cfg.get("language", "es"))

        self.title(T("app_title"))
        self.geometry("980x680")
        self.resizable(False, False)
        self.configure(fg_color=C_BG)

        _icon = BASE_DIR / "assets" / "icon.ico"
        if _icon.exists() and sys.platform == "win32":
            self.iconbitmap(str(_icon))

        global FONT_TITLE, FONT_BODY, FONT_SMALL, FONT_MONO, FONT_MONO_L, FONT_CAPTION
        FONT_TITLE   = ctk.CTkFont(family="Segoe UI", size=15, weight="bold")
        FONT_BODY    = ctk.CTkFont(family="Segoe UI", size=13)
        FONT_SMALL   = ctk.CTkFont(family="Segoe UI", size=11)
        FONT_MONO    = ctk.CTkFont(family="Consolas",  size=11)
        FONT_MONO_L  = ctk.CTkFont(family="Consolas",  size=14, weight="bold")
        FONT_CAPTION = ctk.CTkFont(family="Segoe UI", size=10)

        self._paso          = 0
        self._puerto        = ctk.StringVar(value=_cfg.get("last_port", ""))
        self._fw_path       = ctk.StringVar(value=_cfg.get("last_firmware") or str(DEFAULT_FIRMWARE))
        self._ssid          = ctk.StringVar(value=_cfg.get("last_ssid", ""))
        self._wifi_pass     = ctk.StringVar()

        _srv_default = f"http://{_ip_local()}:5000/api/sensores/lectura"
        _srv = _cfg.get("server_url") or _srv_default
        if "192.168.1.100" in _srv:
            _srv = _srv_default
        self._server_url    = ctk.StringVar(value=_srv)
        self._cfg_force     = False
        self._device_id     = None
        self._pin_dht       = None
        self._pin_soil      = None
        self._batch_count   = 0
        self._cal_visible   = False
        self._device_done   = False
        self._spinner_idx   = 0
        self._spinner_job   = None
        self._known_ports   = set()
        self._hotplug_on    = True
        self._animating     = False
        self._flash_indet   = False
        self._serial_lock   = threading.Lock()

        self._av_email    = ctk.StringVar(value=_cfg.get("av_email", ""))
        self._av_pass     = ctk.StringVar()
        self._av_web_url  = ctk.StringVar(value=_cfg.get("av_web_url", "http://localhost:3000"))
        self._av_last_url = None

        self._t_off = ctk.StringVar(value="0.0")
        self._h_off = ctk.StringVar(value="0.0")
        self._s_dry = ctk.StringVar(value="50")
        self._s_wet = ctk.StringVar(value="3200")

        self._i18n: list[tuple] = []

        self._log_file = LOGS_DIR / f"sesion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._log_init()

        self._build_ui()
        self._show_step(0, animated=False)
        threading.Thread(target=self._scan_ports, daemon=True).start()
        threading.Thread(target=self._hotplug_watch, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        SplashScreen(self, on_done=self._on_splash_done)

    def _on_splash_done(self):
        self.update_idletasks()
        w, h = 980, 680
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.attributes('-alpha', 0.0)
        self.deiconify()
        self.update_idletasks()
        _titulo_claro(self)
        self.lift()
        self.focus_force()
        self._fade_in()
        if DEMO_MODE:
            self.after(600, lambda: _inject_demo(self))

    def _fade_in(self, alpha: float = 0.0):
        if not self.winfo_exists():
            return
        alpha = min(1.0, alpha + 0.1)
        self.attributes('-alpha', alpha)
        if alpha < 1.0:
            self.after(16, lambda a=alpha: self._fade_in(a))

    def _reg(self, widget, key: str):
        widget.configure(text=T(key))
        self._i18n.append((widget, key))
        return widget

    def _toggle_lang(self):
        set_lang("en" if get_lang() == "es" else "es")
        cfg_guardar(language=get_lang())
        self._apply_lang()

    def _apply_lang(self):
        for widget, key in self._i18n:
            try:
                widget.configure(text=T(key))
            except tk.TclError:
                pass

        for lbl, key in zip(self._step_labels, self.STEP_KEYS):
            lbl.configure(text=T(key))

        self._btn_lang.configure(text=T("lang_btn"))
        self._btn_prev.configure(text=T("btn_anterior"))
        self._btn_next.configure(text=T("btn_continuar"))
        self._btn_new_dev.configure(text=T("btn_nuevo_dispositivo"))

        self._btn_cal.configure(
            text=T("s3_cal_toggle_op") if self._cal_visible else T("s3_cal_toggle"))

        if self._btn_flash.cget("state") == "normal":
            self._btn_flash.configure(text=T("s2_btn_grabar"))
        if self._btn_cfg.cget("state") == "normal":
            self._btn_cfg.configure(text=T("s3_btn_enviar"))
        if self._btn_cal_send.cget("state") == "normal":
            self._btn_cal_send.configure(text=T("s3_cal_btn"))
        if self._btn_test.cget("state") == "normal":
            self._btn_test.configure(text=T("s4_btn_test"))
        if self._btn_activate.cget("state") == "normal":
            self._btn_activate.configure(text=T("s5_btn_conectar"))

        self._btn_done.configure(
            text=T("s4_listo_done") if self._device_done else T("s4_btn_listo"))

        if not self._device_id:
            self._lbl_qr.configure(text=T("s4_qr_ph"))

        self._aplicar_pines_ui()

        self._lbl_test_st.configure(text=T("s4_hint_test"), text_color=C_TEXT3)
        self._lbl_summary.configure(
            text=(f"{T('s4_wifi_lbl')}    {self._ssid.get()}\n"
                  f"{T('s4_server_lbl')} {self._server_url.get()}\n"
                  f"{T('s4_port_lbl')}   {self._get_port()}"))

        self._btn_web_adv.configure(
            text=("▼  " if self._web_adv_visible else "▶  ") + T("s5_web_url"))

        self._btn_adv.configure(
            text=("▼  " if self._adv_visible else "▶  ") + T("s3_adv_server"))

        _fw_exists = Path(self._fw_path.get()).exists()
        self._fw_chip_lbl.configure(
            text=T("s2_fw_ok") if _fw_exists else T("s2_fw_missing"))

        _ph = ["(sin dispositivos)", "(no devices)"]
        curr = self._port_combo.cget("values")
        if not curr or curr[0] in _ph:
            self._port_combo.configure(values=[T("s1_sin_dev")])

    def _log_init(self):
        with open(self._log_file, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(
                ['timestamp', 'device_id', 'puerto', 'ssid', 'servidor', 'resultado'])

    def _log_write(self, resultado: str):
        with open(self._log_file, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([datetime.now().isoformat(),
                self._device_id or '', self._get_port(),
                self._ssid.get(), self._server_url.get(), resultado])

    def _save_cfg(self):
        cfg_guardar(server_url=self._server_url.get().strip(),
                    last_ssid=self._ssid.get().strip(),
                    last_firmware=self._fw_path.get().strip(),
                    last_port=self._get_port().strip(),
                    language=get_lang())

    def _toast(self, tipo: str, titulo: str, detalle: str = "", ms: int = 3400):
        Toast(self, tipo, titulo, detalle, ms)

    def _spin_start(self, label: ctk.CTkLabel, base_text: str):
        frames = _spinner_frames()
        def tick():
            if not self._spinner_job:
                return
            self._spinner_idx = (self._spinner_idx + 1) % len(frames)
            label.configure(text=f"{frames[self._spinner_idx]}  {base_text}")
            self._spinner_job = self.after(80, tick)
        self._spinner_idx = 0
        self._spinner_job = self.after(80, tick)

    def _spin_stop(self):
        if self._spinner_job:
            self.after_cancel(self._spinner_job)
            self._spinner_job = None

    def _build_ui(self):
        body = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)
        body.pack(fill="both", expand=True)

        self._sidebar = ctk.CTkFrame(body, width=210, fg_color=C_SIDEBAR, corner_radius=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        ctk.CTkFrame(body, width=1, fg_color=C_SEP, corner_radius=0).pack(side="left", fill="y")

        self._content = ctk.CTkFrame(body, fg_color=C_BG, corner_radius=0)
        self._content.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._build_footer()

        self._step_container = ctk.CTkFrame(self._content, fg_color=C_BG, corner_radius=0)
        self._step_container.pack(fill="both", expand=True)

        self._frames = [
            self._step1_detect(),
            self._step2_flash(),
            self._step3_config(),
            self._step4_verify(),
            self._step5_activate(),
        ]

    def _build_sidebar(self):
        brand = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=16, pady=(20, 0))

        _logo_md = _load_logo(32)
        if _logo_md:
            self._logo_md = _logo_md
            ctk.CTkLabel(brand, image=_logo_md, text="").pack(side="left")
        else:
            logo_sb = ctk.CTkFrame(brand, width=32, height=32,
                                   fg_color="#DCFCE7", corner_radius=9)
            logo_sb.pack(side="left")
            logo_sb.pack_propagate(False)
            ctk.CTkLabel(logo_sb, text="◆",
                         font=ctk.CTkFont(size=15)).pack(expand=True)

        txt_col = ctk.CTkFrame(brand, fg_color="transparent")
        txt_col.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(txt_col, text="AgroCommish",
                     font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                     text_color=C_TEXT, anchor="w").pack(anchor="w")
        lbl_cfg = ctk.CTkLabel(txt_col, text=T("configurador_iot"),
                               font=FONT_CAPTION, text_color=C_TEXT3, anchor="w")
        lbl_cfg.pack(anchor="w")
        self._i18n.append((lbl_cfg, "configurador_iot"))

        ctk.CTkFrame(self._sidebar, height=1, fg_color=C_SEP).pack(
            fill="x", padx=16, pady=(16, 8))

        self._step_rows:    list[ctk.CTkFrame] = []
        self._step_accents: list[ctk.CTkFrame] = []
        self._step_icons:   list[ctk.CTkLabel] = []
        self._step_labels:  list[ctk.CTkLabel] = []
        self._step_checks:  list[ctk.CTkLabel] = []

        for i, (num, step_key) in enumerate(zip(self.STEP_NUMS, self.STEP_KEYS)):
            row = ctk.CTkFrame(self._sidebar, fg_color="transparent",
                               corner_radius=8, height=44, cursor="hand2")
            row.pack(fill="x", padx=8, pady=1)
            row.pack_propagate(False)
            self._step_rows.append(row)

            accent = ctk.CTkFrame(row, width=3, height=22,
                                  fg_color="transparent", corner_radius=2)
            accent.pack(side="left", padx=(6, 4), pady=11)
            accent.pack_propagate(False)
            self._step_accents.append(accent)

            ic = ctk.CTkLabel(row, text=num, width=26, height=26,
                              fg_color=C_STEP_OFF, corner_radius=13,
                              font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                              text_color="white")
            ic.pack(side="left", padx=(0, 8), pady=9)
            self._step_icons.append(ic)

            lbl = ctk.CTkLabel(row, text=T(step_key), font=FONT_BODY,
                               text_color=C_TEXT3, anchor="w")
            lbl.pack(side="left", fill="x", expand=True)
            self._step_labels.append(lbl)

            chk = ctk.CTkLabel(row, text="", width=20,
                               font=ctk.CTkFont(size=13), text_color=C_GREEN)
            chk.pack(side="right", padx=6)
            self._step_checks.append(chk)

            step_n = i
            for w in (row, ic, lbl):
                w.bind("<Button-1>", lambda e, n=step_n: self._show_step(n))
                w.bind("<Enter>",    lambda e, r=row, n=step_n: self._sidebar_hover(r, n, True))
                w.bind("<Leave>",    lambda e, r=row, n=step_n: self._sidebar_hover(r, n, False))

        ctk.CTkFrame(self._sidebar, height=1, fg_color=C_SEP).pack(
            fill="x", padx=16, pady=(12, 0))

        self._lbl_sidebar_batch = ctk.CTkLabel(
            self._sidebar, text=self._batch_str(),
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=C_BLUE)
        self._lbl_sidebar_batch.pack(padx=16, anchor="w", pady=(10, 0))

        self._reg(
            ctk.CTkLabel(self._sidebar, text=T("unidades_listas"),
                         font=FONT_CAPTION, text_color=C_TEXT3),
            "unidades_listas"
        ).pack(padx=16, anchor="w", pady=(0, 10))

        self._btn_lang = ctk.CTkButton(
            self._sidebar, text=T("lang_btn"), width=56, height=26,
            fg_color=C_INPUT_BG, hover_color=C_SEP,
            text_color=C_BLUE, border_width=1, border_color=C_SEP,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            corner_radius=6, command=self._toggle_lang)
        self._btn_lang.pack(padx=16, anchor="w", pady=(0, 16))

    def _sidebar_hover(self, row: ctk.CTkFrame, step_n: int, entering: bool):
        if step_n == self._paso:
            return
        row.configure(fg_color="#F5F5F7" if entering else "transparent")

    def _build_footer(self):
        footer = ctk.CTkFrame(self._content, height=64, fg_color=C_SURFACE, corner_radius=0)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)

        ctk.CTkFrame(footer, height=1, fg_color=C_SEP, corner_radius=0).pack(fill="x", side="top")

        self._btn_prev = ctk.CTkButton(
            footer, text=T("btn_anterior"), width=120, height=36,
            fg_color=C_INPUT_BG, hover_color=C_SEP,
            text_color=C_TEXT2, font=FONT_BODY,
            border_width=1, border_color=C_SEP,
            corner_radius=8, command=self._prev)
        self._btn_prev.pack(side="left", padx=20, pady=14)

        self._btn_new_dev = ctk.CTkButton(
            footer, text=T("btn_nuevo_dispositivo"), width=180, height=36,
            fg_color=C_INPUT_BG, hover_color=C_SEP,
            text_color=C_BLUE, font=FONT_BODY,
            border_width=1, border_color=C_BLUE,
            corner_radius=8, state="disabled",
            command=self._new_device)
        self._btn_new_dev.pack(side="right", padx=(6, 20), pady=14)

        self._btn_next = ctk.CTkButton(
            footer, text=T("btn_continuar"), width=130, height=36,
            fg_color=C_BLUE, hover_color=C_BLUE_DK,
            text_color="white", font=FONT_BODY,
            corner_radius=8, command=self._next)
        self._btn_next.pack(side="right", padx=4, pady=14)

    def _step_header(self, parent, step_idx: int, title_key: str, sub_key: str,
                     title_lbl_attr: str = None, sub_lbl_attr: str = None):
        emoji, ico_bg, ico_border = self.STEP_ICONS[step_idx]

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(22, 0))

        text_col = ctk.CTkFrame(row, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)

        title_lbl = ctk.CTkLabel(text_col, text=T(title_key),
                                  font=FONT_TITLE, text_color=C_TEXT)
        title_lbl.pack(anchor="w")
        self._i18n.append((title_lbl, title_key))

        sub_lbl = ctk.CTkLabel(text_col, text=T(sub_key),
                                font=FONT_BODY, text_color=C_TEXT3,
                                wraplength=580, justify="left")
        sub_lbl.pack(anchor="w", pady=(2, 0))
        self._i18n.append((sub_lbl, sub_key))

        badge_outer = ctk.CTkFrame(row, width=58, height=58,
                                   fg_color=ico_border, corner_radius=16)
        badge_outer.pack(side="right", padx=(12, 0))
        badge_outer.pack_propagate(False)

        badge_inner = ctk.CTkFrame(badge_outer, width=54, height=54,
                                    fg_color=ico_bg, corner_radius=15)
        badge_inner.place(relx=0.5, rely=0.5, anchor="center")
        badge_inner.pack_propagate(False)

        ctk.CTkLabel(badge_inner, text=emoji,
                     font=ctk.CTkFont(size=24)).pack(expand=True)

        ctk.CTkFrame(parent, height=10, fg_color="transparent").pack()

    def _content_frame(self) -> ctk.CTkFrame:
        return ctk.CTkFrame(self._step_container, fg_color=C_BG, corner_radius=0)

    def _white_card(self, parent) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=C_SURFACE, corner_radius=12,
                             border_width=1, border_color=C_SEP)
        card.pack(fill="x", padx=24, pady=(0, 10))
        return card

    def _info_box(self, parent, text_key: str,
                  bg="#F0F7FF", border="#C9E2FF", fg="#1A6AC7"):
        box = ctk.CTkFrame(parent, fg_color=bg, corner_radius=8,
                            border_width=1, border_color=border)
        box.pack(fill="x", padx=24, pady=(0, 14))
        lbl = ctk.CTkLabel(box, text=T(text_key), font=FONT_SMALL,
                           text_color=fg, justify="left", wraplength=600)
        lbl.pack(anchor="w", padx=14, pady=10)
        self._i18n.append((lbl, text_key))

    def _warn_box(self, parent, text: str):
        box = ctk.CTkFrame(parent, fg_color="#FFF8E1", corner_radius=8,
                            border_width=1, border_color="#FFE082")
        box.pack(fill="x", padx=24, pady=(0, 10))
        ctk.CTkLabel(box, text=text, font=FONT_SMALL,
                     text_color="#E65100", justify="left",
                     wraplength=600).pack(anchor="w", padx=14, pady=10)

    def _step1_detect(self) -> ctk.CTkFrame:
        f = self._content_frame()
        self._step_header(f, 0, "s1_header", "s1_sub")

        card = self._white_card(f)

        status_row = ctk.CTkFrame(card, fg_color="transparent")
        status_row.pack(fill="x", padx=20, pady=(20, 16))

        self._dot = ctk.CTkLabel(
            status_row, text="●", width=28,
            font=ctk.CTkFont(size=22), text_color=C_STEP_OFF)
        self._dot.pack(side="left")

        self._lbl_port_st = ctk.CTkLabel(
            status_row, text=T("s1_esperando"),
            font=FONT_BODY, text_color=C_TEXT3, anchor="w")
        self._lbl_port_st.pack(side="left", padx=(10, 0), fill="x", expand=True)

        ctk.CTkButton(
            status_row, text="↺", width=36, height=36,
            fg_color=C_INPUT_BG, hover_color=C_SEP,
            text_color=C_BLUE, border_width=1, border_color=C_SEP,
            font=FONT_BODY, corner_radius=8,
            command=lambda: threading.Thread(
                target=self._scan_ports, daemon=True).start()
        ).pack(side="right")

        ctk.CTkFrame(card, height=1, fg_color=C_SEP).pack(fill="x", padx=20)

        self._port_combo = ctk.CTkComboBox(
            card, variable=self._puerto,
            values=[T("s1_sin_dev")],
            height=40,
            font=FONT_BODY, dropdown_font=FONT_BODY,
            fg_color=C_INPUT_BG, border_color=C_SEP,
            button_color=C_BLUE, dropdown_fg_color=C_SURFACE,
            text_color=C_TEXT, corner_radius=8)
        self._port_combo.pack(fill="x", padx=20, pady=(14, 20))

        return f

    def _step2_flash(self) -> ctk.CTkFrame:
        f = self._content_frame()
        self._step_header(f, 1, "s2_header", "s2_sub")

        card = self._white_card(f)

        fw_exists = Path(self._fw_path.get()).exists()

        self._fw_chip = ctk.CTkFrame(
            card,
            fg_color="#F0FDF4" if fw_exists else "#FFF8E1",
            corner_radius=8, border_width=1,
            border_color="#BBF7D0" if fw_exists else "#FFE082")
        self._fw_chip.pack(fill="x", padx=20, pady=(16, 0))

        chip_row = ctk.CTkFrame(self._fw_chip, fg_color="transparent")
        chip_row.pack(fill="x", padx=14, pady=10)

        self._fw_chip_lbl = ctk.CTkLabel(
            chip_row,
            text=T("s2_fw_ok") if fw_exists else T("s2_fw_missing"),
            font=FONT_BODY, anchor="w",
            text_color="#16A34A" if fw_exists else "#E65100")
        self._fw_chip_lbl.pack(side="left", fill="x", expand=True)

        self._btn_sel_fw = ctk.CTkButton(
            chip_row, text=T("s2_btn_seleccionar"), width=120, height=28,
            fg_color=C_INPUT_BG, hover_color=C_SEP,
            text_color=C_TEXT3, border_width=1, border_color=C_SEP,
            font=FONT_SMALL, corner_radius=6,
            command=self._pick_firmware)
        self._btn_sel_fw.pack(side="right")
        self._i18n.append((self._btn_sel_fw, "s2_btn_seleccionar"))

        ctk.CTkFrame(card, height=1, fg_color=C_SEP).pack(fill="x", padx=20, pady=(14, 8))

        lbl_log = ctk.CTkLabel(card, text=T("s2_log_label"),
                               font=FONT_CAPTION, text_color=C_TEXT3, anchor="w")
        lbl_log.pack(anchor="w", padx=20, pady=(0, 4))
        self._i18n.append((lbl_log, "s2_log_label"))

        prog_row = ctk.CTkFrame(card, fg_color="transparent")
        prog_row.pack(fill="x", padx=20, pady=(0, 2))

        self._flash_bar = ctk.CTkProgressBar(
            prog_row, height=14, corner_radius=7,
            fg_color=C_SEP, progress_color=C_BLUE)
        self._flash_bar.set(0)
        self._flash_bar.pack(side="left", fill="x", expand=True, pady=4)

        self._lbl_flash_pct = ctk.CTkLabel(
            prog_row, text="0 %", width=56,
            font=FONT_MONO_L, text_color=C_BLUE, anchor="e")
        self._lbl_flash_pct.pack(side="left", padx=(10, 0))

        self._lbl_flash_fase = ctk.CTkLabel(
            card, text="", font=FONT_SMALL, text_color=C_TEXT3, anchor="w")
        self._lbl_flash_fase.pack(fill="x", padx=20, pady=(0, 4))

        self._flash_log = ctk.CTkTextbox(
            card, height=195,
            font=FONT_MONO,
            fg_color="#F6F8FA",
            text_color="#24292F",
            scrollbar_button_color=C_SEP,
            corner_radius=8,
            wrap="word")
        self._flash_log.pack(fill="x", padx=20, pady=(0, 12))
        self._flash_log.configure(state="disabled")

        self._btn_flash = ctk.CTkButton(
            card, text=T("s2_btn_grabar"), height=42,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=C_BLUE, hover_color=C_BLUE_DK,
            text_color="white", corner_radius=8,
            command=self._do_flash)
        self._btn_flash.pack(fill="x", padx=20, pady=(0, 20))

        return f

    def _step3_config(self) -> ctk.CTkFrame:
        f = self._content_frame()
        self._step_header(f, 2, "s3_header", "s3_sub")

        card = self._white_card(f)

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=20, pady=(14, 4))

        lbl_redes = ctk.CTkLabel(top_row, text=T("s3_lbl_redes"),
                                 font=FONT_SMALL, text_color=C_TEXT3)
        lbl_redes.pack(side="left")
        self._i18n.append((lbl_redes, "s3_lbl_redes"))

        self._btn_scan_wifi = ctk.CTkButton(
            top_row, text=T("s3_btn_escanear"), height=26, width=110,
            fg_color="transparent", hover_color=C_SEP,
            text_color=C_BLUE, font=FONT_SMALL, corner_radius=6,
            command=self._scan_wifi)
        self._btn_scan_wifi.pack(side="right")
        self._i18n.append((self._btn_scan_wifi, "s3_btn_escanear"))

        self._nets_scroll = ctk.CTkScrollableFrame(
            card, height=120, fg_color=C_INPUT_BG,
            scrollbar_button_color=C_SEP, corner_radius=8)
        self._nets_scroll.pack(fill="x", padx=20)

        self._lbl_cfg_st = ctk.CTkLabel(
            card, text="", font=FONT_SMALL, text_color=C_TEXT3)
        self._lbl_cfg_st.pack(anchor="w", padx=20, pady=(4, 0))

        ctk.CTkFrame(card, height=1, fg_color=C_SEP).pack(
            fill="x", padx=20, pady=(8, 0))

        lbl_p = ctk.CTkLabel(card, text=T("s3_lbl_pass"),
                             font=FONT_SMALL, text_color=C_TEXT3, anchor="w")
        lbl_p.pack(anchor="w", padx=20, pady=(10, 3))
        self._i18n.append((lbl_p, "s3_lbl_pass"))

        pass_row = ctk.CTkFrame(card, fg_color="transparent")
        pass_row.pack(fill="x", padx=20)

        self._entry_pass = ctk.CTkEntry(
            pass_row, textvariable=self._wifi_pass,
            placeholder_text=T("s3_ph_pass"),
            height=38, font=FONT_BODY,
            fg_color=C_INPUT_BG, border_color=C_SEP,
            text_color=C_TEXT, corner_radius=8, show="●")
        self._entry_pass.pack(side="left", fill="x", expand=True)

        self._btn_show_pass = ctk.CTkButton(
            pass_row, text="○", width=38, height=38,
            fg_color=C_INPUT_BG, hover_color=C_SEP,
            text_color=C_TEXT3, border_color=C_SEP,
            border_width=1, corner_radius=8,
            command=self._toggle_pass_visibility)
        self._btn_show_pass.pack(side="left", padx=(6, 0))

        ctk.CTkFrame(card, height=1, fg_color=C_SEP).pack(
            fill="x", padx=20, pady=(10, 0))

        self._btn_adv = ctk.CTkButton(
            card, text="▶  " + T("s3_adv_server"),
            height=28, anchor="w",
            fg_color="transparent", hover_color=C_SEP,
            text_color=C_TEXT3, font=FONT_SMALL, corner_radius=6,
            command=self._toggle_adv)
        self._btn_adv.pack(anchor="w", padx=20, pady=(6, 0))

        self._adv_panel = ctk.CTkFrame(card, fg_color="transparent")
        self._adv_visible = False

        ctk.CTkEntry(
            self._adv_panel, textvariable=self._server_url,
            placeholder_text=T("s3_ph_server"),
            height=34, font=FONT_SMALL,
            fg_color=C_INPUT_BG, border_color=C_SEP,
            text_color=C_TEXT2, corner_radius=8
        ).pack(fill="x", padx=20, pady=(4, 6))

        self._btn_cfg = ctk.CTkButton(
            card, text=T("s3_btn_conectar"), height=40,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=C_BLUE, hover_color=C_BLUE_DK,
            text_color="white", corner_radius=8,
            command=self._do_config)
        self._btn_cfg.pack(fill="x", padx=20, pady=(10, 16))

        self._cal_toggle_row = ctk.CTkFrame(f, fg_color="transparent")
        self._cal_toggle_row.pack(fill="x", padx=24, pady=(6, 0))

        self._btn_cal = ctk.CTkButton(
            self._cal_toggle_row, text=T("s3_cal_toggle"),
            width=220, height=26, anchor="w",
            fg_color="transparent", hover_color=C_SEP,
            text_color=C_TEXT3, font=FONT_SMALL,
            command=self._toggle_cal)
        self._btn_cal.pack(side="left")

        lbl_opc = ctk.CTkLabel(self._cal_toggle_row, text=T("s3_cal_opcional"),
                               font=FONT_CAPTION, text_color=C_TEXT3)
        lbl_opc.pack(side="left", padx=4)
        self._i18n.append((lbl_opc, "s3_cal_opcional"))

        self._btn_pins = ctk.CTkButton(
            self._cal_toggle_row, text=T("pins_btn"), width=170, height=26,
            fg_color="transparent", hover_color=C_SEP,
            text_color=C_ORANGE, border_width=1, border_color=C_ORANGE,
            font=FONT_SMALL, corner_radius=6,
            command=self._do_detect_pins)
        self._btn_pins.pack(side="right")
        self._i18n.append((self._btn_pins, "pins_btn"))

        self._lbl_pins_st = ctk.CTkLabel(
            f, text="", font=FONT_SMALL, text_color=C_TEXT3,
            justify="left", anchor="w", wraplength=620)
        self._lbl_pins_st.pack(fill="x", padx=24, pady=(2, 0))

        self._cal_panel = ctk.CTkFrame(f, fg_color=C_SURFACE,
                                       corner_radius=10,
                                       border_width=1, border_color=C_SEP)
        self._cal_visible = False

        cal_hint = ctk.CTkLabel(self._cal_panel, text=T("s3_cal_hint"),
                                font=FONT_SMALL, text_color=C_TEXT3)
        cal_hint.pack(anchor="w", padx=20, pady=(10, 4))
        self._i18n.append((cal_hint, "s3_cal_hint"))

        def cal_field(parent, lbl_key, var, ph):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=2)
            lbl = ctk.CTkLabel(row, text=T(lbl_key), width=240, font=FONT_BODY,
                               text_color=C_TEXT2, anchor="w")
            lbl.pack(side="left")
            self._i18n.append((lbl, lbl_key))
            ctk.CTkEntry(row, textvariable=var, placeholder_text=ph,
                         width=110, height=32, font=FONT_BODY,
                         fg_color=C_INPUT_BG, border_color=C_SEP,
                         text_color=C_TEXT, corner_radius=8).pack(side="left")

        cal_field(self._cal_panel, "s3_cal_t_off", self._t_off, "0.0")
        cal_field(self._cal_panel, "s3_cal_h_off", self._h_off, "0.0")
        cal_field(self._cal_panel, "s3_cal_s_dry", self._s_dry, "50")
        cal_field(self._cal_panel, "s3_cal_s_wet", self._s_wet, "3200")

        self._lbl_cal_st = ctk.CTkLabel(
            self._cal_panel, text="", font=FONT_SMALL, text_color=C_TEXT3)
        self._lbl_cal_st.pack(anchor="w", padx=20, pady=(2, 0))

        self._btn_cal_send = ctk.CTkButton(
            self._cal_panel, text=T("s3_cal_btn"),
            height=30, fg_color=C_INPUT_BG, hover_color=C_SEP,
            text_color=C_BLUE, border_width=1, border_color=C_BLUE,
            font=FONT_BODY, corner_radius=8,
            command=self._do_calibrate)
        self._btn_cal_send.pack(anchor="w", padx=20, pady=(2, 10))

        return f

    def _step4_verify(self) -> ctk.CTkFrame:
        f = self._content_frame()
        self._step_header(f, 3, "s4_header", "s4_sub")

        card = self._white_card(f)

        hdr = ctk.CTkFrame(card, fg_color=C_BG, corner_radius=0, height=32)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        hdr_font = ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        for attr, key, w, px in [
            ("_lbl_hdr_sensor", "s4_col_sensor", 300, (16, 0)),
            ("_lbl_hdr_val",    "s4_col_val",    160, (0, 0)),
            ("_lbl_hdr_st",     "s4_col_st",       0, (0, 0)),
        ]:
            lbl = ctk.CTkLabel(hdr, text=T(key), width=w,
                               font=hdr_font, text_color=C_TEXT3, anchor="w")
            lbl.pack(side="left", padx=px, pady=6)
            self._i18n.append((lbl, key))
            setattr(self, attr, lbl)

        self._sensor_rows: list[dict] = []
        for nombre in T("s4_sensors"):
            ctk.CTkFrame(card, height=1, fg_color=C_SEP, corner_radius=0).pack(fill="x")
            row = ctk.CTkFrame(card, fg_color="transparent", height=46)
            row.pack(fill="x")
            row.pack_propagate(False)

            name_lbl = ctk.CTkLabel(row, text=nombre, width=300, font=FONT_BODY,
                                    text_color=C_TEXT, anchor="w")
            name_lbl.pack(side="left", padx=(16, 0), pady=10)

            lv = ctk.CTkLabel(row, text="—", width=160,
                               font=FONT_MONO_L, text_color=C_TEXT3, anchor="w")
            lv.pack(side="left")

            le = ctk.CTkLabel(row, text="—", font=FONT_BODY,
                               text_color=C_TEXT3, anchor="w")
            le.pack(side="left", fill="x", expand=True, padx=(0, 16))

            self._sensor_rows.append({'n': name_lbl, 'v': lv, 'e': le})

        ctk.CTkFrame(card, height=1, fg_color=C_SEP).pack(fill="x")

        self._lbl_test_st = ctk.CTkLabel(
            card, text=T("s4_hint_test"), font=FONT_SMALL,
            text_color=C_TEXT3, anchor="w")
        self._lbl_test_st.pack(fill="x", padx=20, pady=(8, 4))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 16))

        self._btn_test = ctk.CTkButton(
            btn_row, text=T("s4_btn_test"), height=40,
            fg_color=C_INPUT_BG, hover_color=C_SEP,
            text_color=C_BLUE, border_width=1, border_color=C_BLUE,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            corner_radius=8, command=self._do_test)
        self._btn_test.pack(side="left", fill="x", expand=True)

        self._btn_export = ctk.CTkButton(
            btn_row, text=T("s4_btn_export"), height=40, width=190,
            fg_color=C_INPUT_BG, hover_color=C_SEP,
            text_color=C_TEXT2, border_width=1, border_color=C_SEP,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            corner_radius=8, command=self._do_export_datos)
        self._btn_export.pack(side="left", padx=(10, 0))
        self._i18n.append((self._btn_export, "s4_btn_export"))

        bot = ctk.CTkFrame(f, fg_color="transparent")
        bot.pack(fill="x", padx=24, pady=(0, 10))

        qr_col = ctk.CTkFrame(bot, fg_color=C_SURFACE, corner_radius=12,
                               border_width=1, border_color=C_SEP, width=162)
        qr_col.pack(side="left", anchor="n")
        qr_col.pack_propagate(False)

        self._lbl_qr = ctk.CTkLabel(
            qr_col, text=T("s4_qr_ph"),
            font=FONT_SMALL, text_color=C_TEXT3,
            width=150, height=150)
        self._lbl_qr.pack(padx=6, pady=(6, 2))

        self._btn_save_qr = ctk.CTkButton(
            qr_col, text=T("s4_btn_save_qr"), width=148, height=26,
            fg_color=C_INPUT_BG, hover_color=C_SEP,
            text_color=C_BLUE, border_width=1, border_color=C_SEP,
            font=FONT_SMALL, corner_radius=6, state="disabled",
            command=self._save_qr)
        self._btn_save_qr.pack(pady=(0, 6))
        self._i18n.append((self._btn_save_qr, "s4_btn_save_qr"))

        right_col = ctk.CTkFrame(bot, fg_color="transparent")
        right_col.pack(side="left", fill="both", expand=True, padx=(16, 0))

        self._lbl_did = ctk.CTkLabel(
            right_col, text="", font=FONT_MONO_L, text_color=C_BLUE, anchor="w")
        self._lbl_did.pack(anchor="w", pady=(0, 4))

        self._lbl_summary = ctk.CTkLabel(
            right_col, text="", font=FONT_SMALL,
            text_color=C_TEXT3, justify="left", anchor="w")
        self._lbl_summary.pack(anchor="w", pady=(0, 12))

        self._btn_done = ctk.CTkButton(
            right_col, text=T("s4_btn_listo"), height=40,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=C_GREEN, hover_color="#28A745",
            text_color="white", corner_radius=8,
            command=self._mark_done)
        self._btn_done.pack(fill="x")

        self._lbl_result = ctk.CTkLabel(
            right_col, text="", font=FONT_BODY,
            text_color=C_GREEN, anchor="w")
        self._lbl_result.pack(anchor="w", pady=(8, 0))

        return f

    def _show_step(self, n: int, animated: bool = True):
        if self._animating:
            return
        old_n = self._paso

        for i, (row, accent, ic, lbl, _chk) in enumerate(zip(
                self._step_rows, self._step_accents,
                self._step_icons, self._step_labels, self._step_checks)):
            if i == n:
                row.configure(fg_color="#EAF2FF")
                accent.configure(fg_color=C_BLUE)
                ic.configure(fg_color=C_STEP_ACT, text=self.STEP_NUMS[i])
                lbl.configure(text_color=C_TEXT,
                              font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
            elif i < n:
                row.configure(fg_color="transparent")
                accent.configure(fg_color=C_STEP_DONE)
                ic.configure(fg_color=C_STEP_DONE, text="✓")
                lbl.configure(text_color=C_TEXT2, font=FONT_BODY)
            else:
                row.configure(fg_color="transparent")
                accent.configure(fg_color="transparent")
                ic.configure(fg_color=C_STEP_OFF, text=self.STEP_NUMS[i])
                lbl.configure(text_color=C_TEXT3, font=FONT_BODY)

        self._paso = n

        if n == 3:
            self._prepare_verify()
        elif n == 4:
            self._prepare_activate()

        self._btn_prev.configure(state="normal" if n > 0 else "disabled")
        self._btn_next.configure(state="normal" if n < 4 else "disabled")
        self._btn_new_dev.configure(state="disabled")

        if animated and old_n != n:
            self._animate_step_change(old_n, n)
        else:
            for fr in self._frames:
                fr.pack_forget()
            self._frames[n].pack(fill="both", expand=True)

    def _animate_step_change(self, old_n: int, new_n: int):
        if self._animating:
            return
        self._animating = True
        old_frame = self._frames[old_n]
        new_frame  = self._frames[new_n]
        self.update_idletasks()
        W         = self._step_container.winfo_width() or 770
        direction = 1 if new_n > old_n else -1

        for fr in self._frames:
            fr.pack_forget()
        old_frame.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        new_frame.place(x=W * direction, y=0, relwidth=1.0, relheight=1.0)
        new_frame.lift()

        STEPS = 18
        DELAY = 14

        def _step(i: int):
            if i > STEPS:
                try:
                    old_frame.place_forget()
                    new_frame.place_forget()
                    new_frame.pack(fill="both", expand=True)
                finally:
                    self._animating = False
                self._pulse_step_icon(new_n)
                return
            t    = i / STEPS
            ease = 1 - (1 - t) ** 3
            old_frame.place(x=int(-W * direction * ease),       y=0, relwidth=1.0, relheight=1.0)
            new_frame.place(x=int( W * direction * (1 - ease)), y=0, relwidth=1.0, relheight=1.0)
            self.after(DELAY, lambda: _step(i + 1))

        _step(0)

    def _pulse_step_icon(self, n: int):
        ic = self._step_icons[n]
        ic.configure(fg_color="#5AADFF")
        self.after(120, lambda: ic.configure(fg_color=C_STEP_ACT))

    def _prev(self):
        if self._paso > 0:
            self._show_step(self._paso - 1)

    def _next(self):
        if self._paso < 4:
            self._show_step(self._paso + 1)

    def _new_device(self):
        self._device_id   = None
        self._pin_dht     = None
        self._pin_soil    = None
        self._cfg_force   = False
        self._device_done = False
        self._show_step(0)
        threading.Thread(target=self._scan_ports, daemon=True).start()
        self._flash_reset_bar()
        self._log_write_ui(T("nuevo_dispositivo"))
        self._lbl_result.configure(text="")
        self._lbl_pins_st.configure(text="", text_color=C_TEXT3)
        self._btn_done.configure(state="normal", text=T("s4_btn_listo"))
        self._lbl_qr.configure(image="", text=T("s4_qr_ph"), text_color=C_TEXT3)
        self._btn_save_qr.configure(state="disabled")
        self._aplicar_pines_ui()
        for row in self._sensor_rows:
            row['v'].configure(text="—", text_color=C_TEXT3)
            row['e'].configure(text="—", text_color=C_TEXT3)

    def _scan_ports(self):
        ports  = detectar_puertos()
        values = [f"{p['port']}  —  {p['descripcion']}" for p in ports]
        esp32s = [p for p in ports if p['es_esp32']]
        self._known_ports = {p['port'] for p in ports}

        self.after(0, lambda v=values: self._port_combo.configure(
            values=v or [T("s1_sin_dev")]))

        if esp32s:
            sel = f"{esp32s[0]['port']}  —  {esp32s[0]['descripcion']}"
            self.after(0, lambda s=sel: self._puerto.set(s))
            self.after(0, lambda p=esp32s[0]: self._set_port_status(
                True, f"{p['port']}  —  {p['descripcion']}"))
        elif ports:
            self.after(0, lambda v=values: self._puerto.set(v[0]))
            self.after(0, lambda: self._set_port_status(None, T("s1_port_no_driver")))
        else:
            self.after(0, lambda: self._set_port_status(False, T("s1_esperando")))

    def _set_port_status(self, connected, msg: str):
        color_map = {True: C_GREEN, None: C_ORANGE, False: C_STEP_OFF}
        text_map  = {True: C_GREEN, None: C_ORANGE, False: C_TEXT3}
        self._dot.configure(text_color=color_map[connected])
        self._lbl_port_st.configure(text=msg, text_color=text_map[connected])

    def _hotplug_watch(self):
        time.sleep(1.5)
        prev_ports = puertos_como_set()
        while self._hotplug_on:
            time.sleep(1.5)
            try:
                curr_ports = puertos_como_set()
            except OSError:
                continue
            nuevos    = curr_ports - prev_ports
            desconect = prev_ports - curr_ports
            if nuevos or desconect:
                self._scan_ports()
                if nuevos:
                    ports  = detectar_puertos()
                    esp32s = [p for p in ports
                              if p['es_esp32'] and p['port'] in nuevos]
                    if esp32s:
                        self.after(0, lambda p=esp32s[0]: self.winfo_exists() and self._on_new_esp32(p))
            prev_ports = curr_ports

    def _on_new_esp32(self, port_info: dict):
        self._puerto.set(f"{port_info['port']}  —  {port_info['descripcion']}")
        self._set_port_status(True, f"✓  {port_info['port']}  —  {port_info['descripcion']}")
        self._pulse_dot(3)
        self._toast("info", T("toast_dev_t"), f"{port_info['port']}  —  {port_info['descripcion']}")
        if self._paso == 0:
            self.after(1200, lambda: self.winfo_exists() and self._paso == 0
                       and self._show_step(1))

    def _pulse_dot(self, times: int, state: bool = True):
        if not hasattr(self, '_dot'): return
        if times <= 0:
            self._dot.configure(text_color=C_GREEN); return
        self._dot.configure(text_color=C_GREEN if state else C_SEP)
        self.after(250, lambda: self._pulse_dot(times - 1, not state))

    def _on_close(self):
        self._hotplug_on = False
        self.destroy()

    def _get_port(self) -> str:
        raw = self._puerto.get()
        return raw.split("  —  ")[0].strip() if "  —  " in raw else raw.strip()

    def _pick_firmware(self):
        p = filedialog.askopenfilename(
            title=T("fw_title"),
            filetypes=[(T("fw_filter"), "*.bin"), ("Todos", "*.*")],
            initialdir=str(FIRMWARE_DIR))
        if p:
            self._fw_path.set(p)
            exists = Path(p).exists()
            self._fw_chip.configure(
                fg_color="#F0FDF4" if exists else "#FFF8E1",
                border_color="#BBF7D0" if exists else "#FFE082")
            self._fw_chip_lbl.configure(
                text=T("s2_fw_ok") if exists else T("s2_fw_missing"),
                text_color="#16A34A" if exists else "#E65100")
            self._save_cfg()

    def _log_write_ui(self, text: str):
        self._flash_log.configure(state="normal")
        self._flash_log.insert("end", text + "\n")
        self._flash_log.see("end")
        self._flash_log.configure(state="disabled")

    def _do_flash(self):
        port = self._get_port()
        if not port:
            self._log_write_ui(T("s2_err_sin_puerto")); return
        fw = self._fw_path.get()
        if not Path(fw).exists():
            self._log_write_ui(T("s2_err_fw_noexiste")); return
        self._log_write("FLASH_INICIO")
        self._btn_flash.configure(state="disabled", text=T("s2_grabando"))
        self._flash_indet = True
        self._flash_bar.configure(mode="indeterminate")
        self._flash_bar.start()
        self._lbl_flash_pct.configure(text="")
        self._lbl_flash_fase.configure(text=T("s2_fase_conectando"), text_color=C_TEXT3)
        self._log_write_ui(T("s2_log_puerto", port=port))
        self._log_write_ui(T("s2_log_fw", fw=fw))

        def run():
            if not self._serial_lock.acquire(blocking=False):
                self.after(0, lambda: self.winfo_exists() and (
                    self._log_write_ui(T("puerto_ocupado")),
                    self._flash_reset_bar(),
                    self._btn_flash.configure(state="normal", text=T("s2_btn_grabar"))))
                return
            try:
                Flasher(port, fw).flashear(
                    on_output=lambda l: self.after(0, lambda ln=l: self.winfo_exists() and self._flash_linea(ln)),
                    on_progress=lambda p: self.after(0, lambda pv=p: self.winfo_exists() and self._flash_progreso(pv)))
                self.after(0, lambda: self.winfo_exists() and self._flash_ok())
            except (RuntimeError, FileNotFoundError, OSError) as e:
                self.after(0, lambda err=str(e): self.winfo_exists() and self._flash_err(err))
            finally:
                self._serial_lock.release()

        threading.Thread(target=run, daemon=True).start()

    def _flash_reset_bar(self):
        if getattr(self, '_flash_indet', False):
            self._flash_indet = False
            self._flash_bar.stop()
            self._flash_bar.configure(mode="determinate")
        self._flash_bar.set(0)
        self._lbl_flash_pct.configure(text="0 %")
        self._lbl_flash_fase.configure(text="")

    def _flash_linea(self, linea: str):
        self._log_write_ui(linea)
        l = linea.lower()
        if "erasing" in l:
            self._lbl_flash_fase.configure(text=T("s2_fase_borrando"), text_color=C_ORANGE)
        elif "hash of data verified" in l:
            self._lbl_flash_fase.configure(text=T("s2_fase_verificado"), text_color=C_GREEN)

    def _flash_progreso(self, p: int):
        if self._flash_indet:
            self._flash_indet = False
            self._flash_bar.stop()
            self._flash_bar.configure(mode="determinate")
            self._lbl_flash_fase.configure(text=T("s2_fase_grabando"), text_color=C_BLUE)
        self._flash_bar.set(p / 100)
        self._lbl_flash_pct.configure(text=f"{p} %")

    def _flash_ok(self):
        self._log_write("FLASH_OK")
        self._log_write_ui(T("s2_ok"))
        if self._flash_indet:
            self._flash_indet = False
            self._flash_bar.stop()
            self._flash_bar.configure(mode="determinate")
        self._flash_bar.set(1.0)
        self._lbl_flash_pct.configure(text="100 %")
        self._lbl_flash_fase.configure(text=T("s2_fase_listo"), text_color=C_GREEN)
        self._btn_flash.configure(state="normal", text=T("s2_btn_grabar"))
        self._log_write_ui(T("s2_boot_wait"))
        self._toast("success", T("toast_flash_t"), T("toast_flash_d"))
        threading.Thread(target=self._post_flash_worker,
                         args=(self._get_port(),), daemon=True).start()

    def _post_flash_worker(self, port: str):
        def ui(fn):
            self.after(0, lambda: self.winfo_exists() and fn())

        if not self._serial_lock.acquire(timeout=10):
            ui(lambda: self._log_write_ui(T("puerto_ocupado")))
            ui(self._goto_config)
            return
        try:
            try:
                info = esperar_dispositivo(port)
            except (TimeoutError, RuntimeError, OSError) as e:
                err = str(e)
                ui(lambda: self._log_write_ui(T("s2_boot_timeout", err=err)))
                ui(self._goto_config)
                return

            did = info.get('device_id') or 'DESCONOCIDO'
            self._device_id = did
            ui(lambda: self._log_write_ui(T("s2_dev_id", did=did)))
            ui(lambda: self._log_write_ui(T("s2_pins_scan")))

            try:
                with Provisioner(port, timeout=4.0) as p:
                    r = p.detectar_pines(aplicar=True)
                if not r.get("ok"):
                    raise RuntimeError(r.get("error", "respuesta inválida"))
            except (TimeoutError, RuntimeError, OSError, ValueError) as e:
                err = str(e)
                ui(lambda: self._log_write_ui(T("pins_err", err=err)))
                ui(self._goto_config)
                return
        finally:
            self._serial_lock.release()

        def mostrar():
            msg, color = self._interpretar_pines(r)
            self._log_write("PINES_DETECTADOS")
            self._log_write_ui(msg)
            self._lbl_pins_st.configure(text=msg, text_color=color)
            tipo = {C_GREEN: "success", C_ORANGE: "warn"}.get(color, "error")
            self._toast(tipo, T("toast_pins_t"), msg, ms=4500)
            self._goto_config()
        ui(mostrar)

    def _goto_config(self):
        if self._paso == 1:
            self._show_step(2)
            self._scan_wifi()

    def _flash_err(self, msg: str):
        self._log_write_ui(f"\n✗  Error: {msg}")
        self._flash_reset_bar()
        self._btn_flash.configure(state="normal", text=T("s2_reintento"))
        self._toast("error", T("toast_err_t"), msg.splitlines()[0][:120], ms=4500)

    def _toggle_pass_visibility(self):
        show = self._entry_pass.cget("show")
        self._entry_pass.configure(show="" if show else "●")
        self._btn_show_pass.configure(text="◉" if show else "○")

    def _toggle_adv(self):
        self._adv_visible = not self._adv_visible
        if self._adv_visible:
            self._adv_panel.pack(fill="x", after=self._btn_adv)
            self._btn_adv.configure(text="▼  " + T("s3_adv_server"))
        else:
            self._adv_panel.pack_forget()
            self._btn_adv.configure(text="▶  " + T("s3_adv_server"))

    def _scan_wifi(self):
        port = self._get_port()
        if not port:
            self._lbl_cfg_st.configure(text=T("sin_puerto"), text_color=C_RED)
            return
        self._btn_scan_wifi.configure(state="disabled", text=T("s3_escaneando"))
        self._lbl_cfg_st.configure(text=T("s3_escaneando"), text_color=C_TEXT3)
        for w in self._nets_scroll.winfo_children():
            w.destroy()

        def run():
            if not self._serial_lock.acquire(timeout=8):
                self.after(0, lambda: self.winfo_exists() and (
                    self._lbl_cfg_st.configure(text=T("puerto_ocupado"), text_color=C_ORANGE),
                    self._btn_scan_wifi.configure(state="normal", text=T("s3_btn_escanear"))))
                return
            try:
                with Provisioner(port, timeout=18.0) as p:
                    nets = p.escanear_wifi()
                self.after(0, lambda n=nets: self.winfo_exists() and self._render_net_cards(n))
            except (TimeoutError, RuntimeError, OSError) as e:
                self.after(0, lambda err=str(e): self.winfo_exists() and (
                    self._lbl_cfg_st.configure(text=f"✗  {err}", text_color=C_RED),
                    self._btn_scan_wifi.configure(state="normal", text=T("s3_btn_escanear"))))
            finally:
                self._serial_lock.release()

        threading.Thread(target=run, daemon=True).start()

    def _render_net_cards(self, nets: list):
        for w in self._nets_scroll.winfo_children():
            w.destroy()

        if not nets:
            ctk.CTkLabel(self._nets_scroll, text=T("s3_ninguna_red"),
                         font=FONT_SMALL, text_color=C_TEXT3).pack(pady=8)
        else:
            for net in nets:
                ssid  = net.get('ssid', '')
                rssi  = net.get('rssi', -99)
                lock  = "◆" if net.get('secure') else "◇"
                bars  = "▂▄▆█" if rssi > -55 else ("▂▄▆" if rssi > -70 else "▂▄")
                label = f"{lock}  {ssid}    {bars} {rssi} dBm"

                btn = ctk.CTkButton(
                    self._nets_scroll, text=label,
                    height=34, anchor="w",
                    fg_color="transparent", hover_color="#EAF2FF",
                    text_color=C_TEXT, font=FONT_BODY,
                    corner_radius=8,
                    command=lambda s=ssid: self._select_net(s))
                btn.pack(fill="x", pady=2, padx=2)

        self._lbl_cfg_st.configure(
            text=T("s3_redes_found", n=len(nets)), text_color=C_GREEN)
        self._btn_scan_wifi.configure(state="normal", text="↺  " + T("s3_btn_escanear"))

    def _select_net(self, ssid: str):
        self._ssid.set(ssid)
        self._lbl_cfg_st.configure(
            text=f"✓  {ssid}  {T('s3_red_sel')}", text_color=C_BLUE)
        self._entry_pass.focus_set()

    def _do_config(self):
        port   = self._get_port()
        ssid   = self._ssid.get().strip()
        passwd = self._wifi_pass.get()
        server = self._server_url.get().strip()

        if not port:
            self._lbl_cfg_st.configure(text=T("sin_puerto"), text_color=C_RED); return
        if not ssid:
            self._lbl_cfg_st.configure(text=T("s3_sin_ssid"), text_color=C_RED); return
        if not server:
            self._lbl_cfg_st.configure(text=T("s3_sin_server"), text_color=C_RED); return
        _sp = urllib.parse.urlparse(server)
        if not _sp.scheme or not _sp.netloc:
            self._lbl_cfg_st.configure(text=T("s3_url_invalida"), text_color=C_RED); return

        self._btn_cfg.configure(state="disabled", text=T("s3_enviando"))
        self._spin_start(self._lbl_cfg_st, T("s3_enviando_cfg"))

        srv_host  = _sp.hostname
        srv_port  = _sp.port or (443 if _sp.scheme == "https" else 80)
        srv_force = self._cfg_force
        self._cfg_force = False

        def run():
            if not srv_force and not _puerto_abierto(srv_host, srv_port):
                def avisar():
                    self._cfg_force = True
                    self._spin_stop()
                    self._lbl_cfg_st.configure(
                        text=T("s3_srv_warn", base=f"{srv_host}:{srv_port}", ip=_ip_local()),
                        text_color=C_ORANGE)
                    self._btn_cfg.configure(state="normal", text=T("s3_btn_enviar"))
                self.after(0, lambda: self.winfo_exists() and avisar())
                return

            if not self._serial_lock.acquire(timeout=8):
                self.after(0, lambda: self.winfo_exists() and self._config_err(T("puerto_ocupado")))
                return
            try:
                with Provisioner(port) as p:
                    try:
                        self._device_id = p.identificar().get('device_id', 'DESCONOCIDO')
                    except (TimeoutError, RuntimeError, OSError):
                        self._device_id = "DESCONOCIDO"
                    r = p.configurar(ssid, passwd, server)
                did = r.get('device_id') or self._device_id
                self._device_id = did
                if r.get('ok'):
                    self.after(0, lambda d=did: self.winfo_exists() and self._config_ok(d))
                else:
                    self.after(0, lambda m=r.get('error', 'Error'): self.winfo_exists() and self._config_err(m))
            except (TimeoutError, RuntimeError, OSError) as e:
                self.after(0, lambda err=str(e): self.winfo_exists() and self._config_err(err))
            finally:
                self._serial_lock.release()

        threading.Thread(target=run, daemon=True).start()

    def _config_ok(self, did: str):
        self._log_write("CONFIG_OK")
        self._spin_stop()
        self._lbl_cfg_st.configure(text=T("s3_cfg_ok", did=did), text_color=C_GREEN)
        self._btn_cfg.configure(state="normal", text=T("s3_btn_enviar"))
        self._save_cfg()
        self._toast("success", T("toast_cfg_t"), f"ID: {did}")
        self._show_step(3)
        self.after(4000, self._auto_test)

    def _auto_test(self):
        if (self.winfo_exists() and self._paso == 3
                and self._btn_test.cget("state") == "normal"):
            self._do_test()

    def _config_err(self, msg: str):
        self._spin_stop()
        self._lbl_cfg_st.configure(text=f"✗  {msg}", text_color=C_RED)
        self._btn_cfg.configure(state="normal", text=T("s3_btn_enviar"))
        self._toast("error", T("toast_err_t"), msg.splitlines()[0][:120], ms=4500)

    def _toggle_cal(self):
        self._cal_visible = not self._cal_visible
        if self._cal_visible:
            self._cal_panel.pack(fill="x", padx=24, pady=(4, 0),
                                 after=self._cal_toggle_row)
            self._btn_cal.configure(text=T("s3_cal_toggle_op"))
        else:
            self._cal_panel.pack_forget()
            self._btn_cal.configure(text=T("s3_cal_toggle"))

    def _do_calibrate(self):
        port = self._get_port()
        if not port:
            self._lbl_cal_st.configure(text=T("sin_puerto"), text_color=C_RED); return
        try:
            t_off = float(self._t_off.get())
            h_off = float(self._h_off.get())
            s_dry = int(self._s_dry.get())
            s_wet = int(self._s_wet.get())
        except ValueError:
            self._lbl_cal_st.configure(text=T("s3_cal_invalidos"), text_color=C_RED); return
        if s_dry >= s_wet:
            self._lbl_cal_st.configure(text=T("s3_cal_soil_err"), text_color=C_RED); return

        self._btn_cal_send.configure(state="disabled", text=T("s3_enviando"))
        self._spin_start(self._lbl_cal_st, T("s3_cal_guardando"))

        def run():
            if not self._serial_lock.acquire(timeout=8):
                self.after(0, lambda: self.winfo_exists() and (
                    self._spin_stop(),
                    self._lbl_cal_st.configure(text=T("puerto_ocupado"), text_color=C_ORANGE),
                    self._btn_cal_send.configure(state="normal", text=T("s3_cal_btn"))))
                return
            try:
                with Provisioner(port) as p:
                    r = p.calibrar(t_off, h_off, s_dry, s_wet)
                if r.get('ok'):
                    self.after(0, lambda: self.winfo_exists() and self._lbl_cal_st.configure(
                        text=T("s3_cal_ok"), text_color=C_GREEN))
                else:
                    self.after(0, lambda m=r.get('error', '?'): self.winfo_exists() and self._lbl_cal_st.configure(
                        text=f"✗  {m}", text_color=C_RED))
            except (TimeoutError, RuntimeError, OSError) as e:
                self.after(0, lambda err=str(e): self.winfo_exists() and self._lbl_cal_st.configure(
                    text=f"✗  {err}", text_color=C_RED))
            finally:
                self._serial_lock.release()
                self.after(0, lambda: self.winfo_exists() and (
                    self._spin_stop(),
                    self._btn_cal_send.configure(state="normal", text=T("s3_cal_btn"))))

        threading.Thread(target=run, daemon=True).start()

    def _prepare_verify(self):
        self._lbl_did.configure(text=self._device_id or "—")
        self._lbl_summary.configure(
            text=(f"{T('s4_wifi_lbl')}    {self._ssid.get()}\n"
                  f"{T('s4_server_lbl')} {self._server_url.get()}\n"
                  f"{T('s4_port_lbl')}   {self._get_port()}"))
        self._lbl_test_st.configure(text=T("s4_hint_test"), text_color=C_TEXT3)
        self._aplicar_pines_ui()
        for row in self._sensor_rows:
            row['v'].configure(text="—", text_color=C_TEXT3)
            row['e'].configure(text="—", text_color=C_TEXT3)
        if self._device_id and self._device_id != "DESCONOCIDO":
            self._render_qr(self._device_id)

    def _do_test(self):
        port = self._get_port()
        if not port:
            self._lbl_test_st.configure(text=T("sin_puerto"), text_color=C_RED); return
        self._btn_test.configure(state="disabled", text=T("s4_leyendo"))

        def fallar(msg: str):
            self.after(0, lambda: self.winfo_exists() and (
                self._lbl_test_st.configure(text=msg, text_color=C_RED),
                self._btn_test.configure(state="normal", text=T("s4_btn_test"))))

        def run():
            if self._serial_lock.acquire(blocking=False):
                try:
                    with Provisioner(port, timeout=2.0) as p:
                        try:
                            data = p.leer_sensores(timeout=3.0)
                        except (TimeoutError, RuntimeError, ValueError):
                            self.after(0, lambda: self.winfo_exists() and
                                       self._lbl_test_st.configure(
                                           text=T("s4_serial_listen"), text_color=C_TEXT3))
                            data = p.escuchar_datos(max_espera=25.0)
                    results = validar_lecturas(data)
                    self.after(0, lambda r=results: self.winfo_exists() and self._show_sensor_results(r))
                    return
                except (TimeoutError, RuntimeError, OSError, ValueError):
                    pass
                finally:
                    self._serial_lock.release()

            server = self._server_url.get().strip()
            did = self._device_id or ""
            api_base = _api_base_local(server) if server else None

            if not api_base or not did or did == "DESCONOCIDO":
                fallar(T("s4_no_did"))
                return

            parsed   = urllib.parse.urlparse(api_base)
            srv_host = parsed.hostname
            srv_port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if not _puerto_abierto(srv_host, srv_port):
                fallar(T("s4_srv_unreachable",
                         base=f"{srv_host}:{srv_port}", ip=_ip_local()))
                return

            url = f"{api_base}/api/sensores/lecturas-recientes?esp32_id={urllib.parse.quote(did)}"
            TIMEOUT_S = 35
            for seg in range(TIMEOUT_S):
                resta = TIMEOUT_S - seg
                self.after(0, lambda s=resta: self.winfo_exists() and
                           self._lbl_test_st.configure(
                               text=T("s4_waiting_srv", s=s),
                               text_color=C_TEXT3))
                try:
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req, timeout=4) as resp:
                        body = json.loads(resp.read().decode())
                    lecturas = body.get("lecturas") or []
                    if lecturas:
                        data = {}
                        for lec in lecturas:
                            tipo  = lec.get("tipo_lectura", "")
                            valor = lec.get("valor")
                            if "temperatura" in tipo:
                                data["temperatura"] = valor
                            elif "humedad_aire" in tipo or "humedad_a" in tipo:
                                data["humedad_aire"] = valor
                            elif "humedad_suelo" in tipo or "humedad_s" in tipo:
                                data["humedad_suelo"] = valor
                        results = validar_lecturas(data)
                        self.after(0, lambda r=results: self.winfo_exists() and
                                   self._show_sensor_results(r))
                        return
                except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
                    pass
                time.sleep(1)

            fallar(T("s4_no_data"))

        threading.Thread(target=run, daemon=True).start()

    def _do_detect_pins(self):
        port = self._get_port()
        if not port:
            self._lbl_pins_st.configure(text=T("sin_puerto"), text_color=C_RED); return
        self._btn_pins.configure(state="disabled")
        self._lbl_pins_st.configure(text=T("pins_busy"), text_color=C_TEXT3)

        def run():
            if not self._serial_lock.acquire(timeout=8):
                self.after(0, lambda: self.winfo_exists() and (
                    self._btn_pins.configure(state="normal"),
                    self._lbl_pins_st.configure(text=T("puerto_ocupado"), text_color=C_ORANGE)))
                return
            try:
                with Provisioner(port, timeout=4.0) as p:
                    r = p.detectar_pines(aplicar=True)
            except (TimeoutError, RuntimeError, OSError, ValueError) as e:
                self.after(0, lambda err=str(e): self.winfo_exists() and
                           self._pins_result(None, err))
                return
            finally:
                self._serial_lock.release()
            self.after(0, lambda res=r: self.winfo_exists() and
                       self._pins_result(res, None))

        threading.Thread(target=run, daemon=True).start()

    def _pins_result(self, r: dict | None, err: str | None):
        self._btn_pins.configure(state="normal")
        if err is not None or not r or not r.get("ok"):
            self._lbl_pins_st.configure(
                text=T("pins_err", err=err or "respuesta inválida"),
                text_color=C_RED)
            return
        msg, color = self._interpretar_pines(r)
        self._lbl_pins_st.configure(text=msg, text_color=color)

    def _interpretar_pines(self, r: dict) -> tuple[str, str]:
        dht_pin  = r.get("dht_pin", -1) or -1
        soil_pin = r.get("soil_pin", -1) or -1
        dht_ok   = r.get("dht_state") == "detected" and dht_pin > 0
        soil_st  = r.get("soil_state", "not_found")

        if dht_ok:
            self._pin_dht = dht_pin
        if soil_pin > 0 and soil_st in ("detected", "maybe_air"):
            self._pin_soil = soil_pin
        self._aplicar_pines_ui()

        if dht_ok and soil_st == "detected":
            return T("pins_ok", dht=dht_pin, soil=soil_pin), C_GREEN
        if not dht_ok:
            return T("pins_dht_no"), C_RED
        if soil_st == "maybe_air":
            return T("pins_soil_air", soil=soil_pin), C_ORANGE
        return T("pins_soil_no"), C_RED

    def _aplicar_pines_ui(self):
        pines = [self._pin_dht, self._pin_dht, self._pin_soil]
        for row, base, pin in zip(self._sensor_rows, T("s4_sensors"), pines):
            texto = base if pin is None else f"{base}  ·  GPIO {pin}"
            row['n'].configure(text=texto)

    def _show_sensor_results(self, results: list[dict]):
        CM   = {'ok': C_GREEN, 'warn': C_ORANGE, 'error': C_RED}
        IM   = {'ok': '✓', 'warn': '⚠', 'error': '✗'}
        errs = warns = 0
        for i, r in enumerate(results):
            c   = CM.get(r['estado'], C_TEXT3)
            ico = IM.get(r['estado'], '?')
            vt  = f"{r['valor']:.1f} {r['unidad']}" if r['valor'] is not None else "—"
            self._sensor_rows[i]['v'].configure(text=vt, text_color=c)
            self._sensor_rows[i]['e'].configure(text=f"{ico}  {r['mensaje']}", text_color=c)
            if r['estado'] == 'error': errs += 1
            elif r['estado'] == 'warn': warns += 1

        self._btn_test.configure(state="normal", text=T("s4_btn_test"))
        self._log_write("TEST_ERROR" if errs else ("TEST_WARN" if warns else "TEST_OK"))
        dht_caido = any('NaN' in r['mensaje'] for r in results[:2] if r['estado'] == 'error')
        if dht_caido:
            self._lbl_test_st.configure(text=T("s4_dht_first"), text_color=C_RED)
            self._toast("error", T("toast_test_err_t"), T("s4_dht_first"), ms=5000)
        elif errs:
            self._lbl_test_st.configure(text=T("s4_test_errs", n=errs), text_color=C_RED)
            self._toast("error", T("toast_test_err_t"), T("s4_test_errs", n=errs), ms=4500)
        elif warns:
            self._lbl_test_st.configure(text=T("s4_test_warns", n=warns), text_color=C_ORANGE)
            self._toast("warn", T("toast_test_t"), T("s4_test_warns", n=warns))
        else:
            self._lbl_test_st.configure(text=T("s4_test_ok"), text_color=C_GREEN)
            self._toast("success", T("toast_test_t"), T("s4_test_ok"))

    def _do_export_datos(self):
        port = self._get_port()
        if not port:
            self._lbl_test_st.configure(text=T("sin_puerto"), text_color=C_RED); return
        did  = self._device_id or "device"
        path = filedialog.asksaveasfilename(
            title=T("s4_export_title"),
            defaultextension=".csv",
            initialfile=f"datos_{did}_{datetime.now():%Y%m%d_%H%M%S}.csv",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")])
        if not path:
            return
        self._btn_export.configure(state="disabled")
        self._lbl_test_st.configure(text=T("s4_export_busy", n=0), text_color=C_TEXT3)

        def run():
            if not self._serial_lock.acquire(timeout=8):
                self.after(0, lambda: self.winfo_exists() and (
                    self._btn_export.configure(state="normal"),
                    self._lbl_test_st.configure(text=T("puerto_ocupado"), text_color=C_ORANGE)))
                return
            try:
                def progreso(n, _fila):
                    self.after(0, lambda c=n: self.winfo_exists() and
                               self._lbl_test_st.configure(
                                   text=T("s4_export_busy", n=c), text_color=C_TEXT3))
                with Provisioner(port, timeout=1.0) as p:
                    filas = p.capturar_telemetria(65.0, on_lectura=progreso)
                if not filas:
                    raise TimeoutError(T("s4_no_data"))
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    w = csv.DictWriter(f, fieldnames=Provisioner.CAMPOS_TELEMETRIA)
                    w.writeheader()
                    w.writerows(filas)
                self.after(0, lambda n=len(filas): self.winfo_exists() and self._export_ok(n, path))
            except (TimeoutError, RuntimeError, OSError) as e:
                self.after(0, lambda err=str(e): self.winfo_exists() and (
                    self._btn_export.configure(state="normal"),
                    self._lbl_test_st.configure(text=f"✗  {err}", text_color=C_RED)))
            finally:
                self._serial_lock.release()

        threading.Thread(target=run, daemon=True).start()

    def _export_ok(self, n: int, path: str):
        self._btn_export.configure(state="normal")
        nombre = Path(path).name
        self._lbl_test_st.configure(
            text=T("s4_export_ok", n=n, name=nombre), text_color=C_GREEN)
        self._toast("success", T("toast_export_t"), T("s4_export_ok", n=n, name=nombre))

    def _render_qr(self, did: str):
        try:
            pil = generar_qr(did, box_size=7)
            img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(155, 155))
            self._lbl_qr.configure(image=img, text="")
            self._lbl_qr._qr_ref = img
            self._btn_save_qr.configure(state="normal")
        except (OSError, ValueError):
            self._lbl_qr.configure(text=T("s4_qr_err"), text_color=C_RED)

    def _save_qr(self):
        did  = self._device_id or "device"
        path = filedialog.asksaveasfilename(
            title=T("s4_qr_title"),
            defaultextension=".png",
            initialfile=f"QR_{did}.png",
            filetypes=[("PNG", "*.png"), ("Todos", "*.*")])
        if not path: return
        try:
            guardar_qr(did, path, box_size=10)
            self._lbl_result.configure(
                text=T("s4_qr_saved", name=Path(path).name), text_color=C_BLUE)
        except OSError as e:
            self._lbl_result.configure(text=f"Error: {e}", text_color=C_RED)

    def _mark_done(self):
        self._batch_count += 1
        self._device_done  = True
        self._log_write("LISTO")
        self._save_cfg()
        self._lbl_sidebar_batch.configure(text=self._batch_str())
        self._step_checks[3].configure(text="✓", text_color=C_GREEN)
        self._btn_done.configure(state="disabled", text=T("s4_listo_done"))
        self._lbl_result.configure(
            text=T("s4_batch_reg", n=self._batch_count), text_color=C_GREEN)
        self._btn_new_dev.configure(state="normal")
        self._toast("success", T("toast_listo_t"), T("s4_batch_reg", n=self._batch_count))
        self.after(800, lambda: self._show_step(4))

    def _batch_str(self) -> str:
        return str(self._batch_count)

    def _step5_activate(self) -> ctk.CTkFrame:
        f = self._content_frame()
        self._step_header(f, 4, "s5_header", "s5_sub")

        card = ctk.CTkFrame(f, fg_color=C_SURFACE, corner_radius=12,
                            border_width=1, border_color=C_SEP)
        card.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self._step5_form = ctk.CTkFrame(card, fg_color="transparent")
        self._step5_form.pack(fill="both", expand=True)

        api_row = ctk.CTkFrame(self._step5_form, fg_color="transparent")
        api_row.pack(fill="x", padx=24, pady=(20, 0))

        lbl_srv = ctk.CTkLabel(api_row, text=T("s5_srv_detect"),
                               font=FONT_SMALL, text_color=C_TEXT3, anchor="w")
        lbl_srv.pack(side="left")
        self._i18n.append((lbl_srv, "s5_srv_detect"))

        api_chip = ctk.CTkFrame(api_row, fg_color=C_INPUT_BG, corner_radius=6,
                                border_width=1, border_color=C_SEP)
        api_chip.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self._lbl_api_url = ctk.CTkLabel(api_chip, text="—",
                                         font=FONT_MONO, text_color=C_TEXT2, anchor="w")
        self._lbl_api_url.pack(anchor="w", padx=10, pady=4)

        ctk.CTkFrame(self._step5_form, height=16, fg_color="transparent").pack()

        def form_field(lbl_key, var, ph_key, show=""):
            wrap = ctk.CTkFrame(self._step5_form, fg_color="transparent")
            wrap.pack(fill="x", padx=24, pady=(0, 12))
            lbl = ctk.CTkLabel(wrap, text=T(lbl_key),
                               font=FONT_SMALL, text_color=C_TEXT3, anchor="w")
            lbl.pack(fill="x")
            self._i18n.append((lbl, lbl_key))
            kw = dict(textvariable=var, height=42, font=FONT_BODY,
                      fg_color=C_INPUT_BG, border_color=C_SEP,
                      corner_radius=8, placeholder_text=T(ph_key))
            if show:
                kw["show"] = show
            ctk.CTkEntry(wrap, **kw).pack(fill="x", pady=(4, 0))

        form_field("s5_email", self._av_email, "s5_ph_email")
        form_field("s5_pass",  self._av_pass,  "s5_pass", show="•")

        self._btn_web_adv = ctk.CTkButton(
            self._step5_form, text="▶  " + T("s5_web_url"),
            height=26, anchor="w",
            fg_color="transparent", hover_color=C_SEP,
            text_color=C_TEXT3, font=FONT_SMALL, corner_radius=6,
            command=self._toggle_web_adv)
        self._btn_web_adv.pack(anchor="w", padx=24, pady=(0, 4))

        self._web_adv_panel = ctk.CTkFrame(self._step5_form, fg_color="transparent")
        self._web_adv_visible = False

        ctk.CTkEntry(
            self._web_adv_panel, textvariable=self._av_web_url,
            placeholder_text=T("s5_ph_web"),
            height=36, font=FONT_SMALL,
            fg_color=C_INPUT_BG, border_color=C_SEP,
            text_color=C_TEXT2, corner_radius=8
        ).pack(fill="x", padx=24, pady=(4, 8))

        self._lbl_activate_st = ctk.CTkLabel(
            self._step5_form, text="", font=FONT_SMALL,
            text_color=C_TEXT3, anchor="w", wraplength=560)
        self._lbl_activate_st.pack(fill="x", padx=24, pady=(8, 6))

        self._btn_activate = ctk.CTkButton(
            self._step5_form, text=T("s5_btn_conectar"),
            height=44, fg_color="#16A34A", hover_color="#15803D",
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            corner_radius=8, command=self._do_activate)
        self._btn_activate.pack(fill="x", padx=24, pady=(0, 24))

        self._step5_success = ctk.CTkFrame(card, fg_color="transparent")

        check_wrap = ctk.CTkFrame(self._step5_success, width=72, height=72,
                                  fg_color="#DCFCE7", corner_radius=36)
        check_wrap.pack(pady=(48, 0))
        check_wrap.pack_propagate(False)
        ctk.CTkLabel(check_wrap, text="✓",
                     font=ctk.CTkFont(family="Segoe UI", size=32, weight="bold"),
                     text_color="#16A34A").pack(expand=True)

        lbl_done_ttl = ctk.CTkLabel(
            self._step5_success, text=T("s5_success_ttl"),
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=C_TEXT)
        lbl_done_ttl.pack(pady=(14, 2))
        self._i18n.append((lbl_done_ttl, "s5_success_ttl"))

        self._lbl_success_user = ctk.CTkLabel(
            self._step5_success, text="", font=FONT_BODY, text_color=C_TEXT3)
        self._lbl_success_user.pack()

        info = ctk.CTkFrame(self._step5_success, fg_color="#F0FDF4",
                            corner_radius=8, border_width=1, border_color="#BBF7D0")
        info.pack(fill="x", padx=40, pady=(20, 0))
        lbl_done_inf = ctk.CTkLabel(info, text=T("s5_success_inf"),
                                    font=FONT_SMALL, text_color="#166534", justify="left")
        lbl_done_inf.pack(anchor="w", padx=14, pady=12)
        self._i18n.append((lbl_done_inf, "s5_success_inf"))

        btn_reabrir = ctk.CTkButton(
            self._step5_success, text=T("s5_btn_reabrir"),
            height=42, fg_color=C_BLUE, hover_color=C_BLUE_DK,
            text_color="white", font=FONT_BODY,
            corner_radius=8, command=self._reopen_platform)
        btn_reabrir.pack(fill="x", padx=40, pady=(18, 6))
        self._i18n.append((btn_reabrir, "s5_btn_reabrir"))

        btn_back = ctk.CTkButton(
            self._step5_success, text=T("s5_btn_volver"),
            height=32, fg_color="transparent", hover_color=C_INPUT_BG,
            text_color=C_TEXT3, font=FONT_SMALL,
            border_width=0, corner_radius=8,
            command=self._reset_activate_form)
        btn_back.pack(fill="x", padx=40)
        self._i18n.append((btn_back, "s5_btn_volver"))

        return f

    def _toggle_web_adv(self):
        self._web_adv_visible = not self._web_adv_visible
        if self._web_adv_visible:
            self._web_adv_panel.pack(fill="x", after=self._btn_web_adv)
            self._btn_web_adv.configure(text="▼  " + T("s5_web_url"))
        else:
            self._web_adv_panel.pack_forget()
            self._btn_web_adv.configure(text="▶  " + T("s5_web_url"))

    def _prepare_activate(self):
        api_base = _api_base_local(self._server_url.get().strip())
        self._lbl_api_url.configure(
            text=api_base,
            text_color=C_ORANGE if api_base.startswith("http://") else "#166534")
        self._reset_activate_form()

    def _reset_activate_form(self):
        self._step5_success.pack_forget()
        self._lbl_activate_st.configure(text="", text_color=C_TEXT3)
        self._btn_activate.configure(state="normal", text=T("s5_btn_conectar"))
        self._step5_form.pack(fill="both", expand=True)

    def _reopen_platform(self):
        if self._av_last_url:
            webbrowser.open(self._av_last_url)

    def _do_activate(self):
        email    = self._av_email.get().strip()
        password = self._av_pass.get()
        web_url  = self._av_web_url.get().strip().rstrip("/")

        if not email or not password:
            self._lbl_activate_st.configure(text=T("s5_sin_creds"), text_color=C_RED)
            return

        api_base = _api_base_local(self._server_url.get().strip())

        if api_base.startswith("http://"):
            self._lbl_activate_st.configure(text=T("s5_http_warn"), text_color=C_ORANGE)

        self._btn_activate.configure(state="disabled", text=T("s5_conectando"))
        self._spin_start(self._lbl_activate_st, T("s5_logging_in"))

        def run():
            try:
                login_url = f"{api_base}/api/auth/login"
                payload   = json.dumps({"username": email, "password": password}).encode()
                req       = urllib.request.Request(
                    login_url, data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = json.loads(resp.read().decode())

                token = (body.get("token")
                         or body.get("access_token")
                         or (body.get("data") or {}).get("token")
                         or (body.get("data") or {}).get("access_token"))
                if not token:
                    raise ValueError(T("s5_no_token"))

                user_data = (body.get("data") or {}).get("user") or {}
                nombre    = user_data.get("nombre") or email
                cfg_guardar(av_email=email, av_web_url=web_url)

                auto_url = (f"{web_url}/auto-login"
                            f"#token={urllib.parse.quote(token)}"
                            f"&redirect=dispositivos")
                self._av_last_url = auto_url
                webbrowser.open(auto_url)

                def show_success():
                    if not self.winfo_exists():
                        return
                    self._spin_stop()
                    self._step5_form.pack_forget()
                    self._lbl_success_user.configure(text=T("s5_bienvenido", nombre=nombre))
                    self._step5_success.pack(fill="both", expand=True)
                    self._step_checks[4].configure(text="✓", text_color=C_GREEN)
                    self._toast("success", T("toast_login_t"), T("s5_bienvenido", nombre=nombre))

                self.after(0, show_success)

            except urllib.error.HTTPError as e:
                msg = T("s5_http_err", code=e.code)
                self.after(0, lambda m=msg: self.winfo_exists() and (
                    self._spin_stop(),
                    self._lbl_activate_st.configure(text=m, text_color=C_RED),
                    self._btn_activate.configure(state="normal", text=T("s5_reintento")),
                ))
            except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as e:
                msg = f"✗  {e}"
                self.after(0, lambda m=msg: self.winfo_exists() and (
                    self._spin_stop(),
                    self._lbl_activate_st.configure(text=m, text_color=C_RED),
                    self._btn_activate.configure(state="normal", text=T("s5_reintento")),
                ))

        threading.Thread(target=run, daemon=True).start()


DEMO_MODE = "--demo" in sys.argv


def _inject_demo(app):
    flash_lines = [
        "Puerto: COM3",
        "Firmware: firmware\\firmware.bin",
        "esptool.py v4.6.2  Serial port COM3",
        "Connecting...",
        "Chip is ESP32-D0WDQ6 (revision v1.0)",
        "Features: WiFi, BT, Dual Core, 240MHz, VRef calibration in efuse",
        "Uploading stub...  Running stub...  Stub running...",
        "Changing baud rate to 460800  Changed.",
        "Configuring flash size...",
        "Flash will be erased from 0x00000000 to 0x0009ffff...",
        "Writing at 0x00000000... (12 %)",
        "Writing at 0x00010000... (25 %)",
        "Writing at 0x00020000... (50 %)",
        "Writing at 0x00040000... (75 %)",
        "Writing at 0x00060000... (87 %)",
        "Writing at 0x0007ffff... (100 %)",
        "Wrote 655360 bytes (640 KB) at 0x00000000 in 18.2 seconds",
        "Hash of data verified.",
        "",
        "Firmware grabado correctamente.",
    ]
    for line in flash_lines:
        app._log_write_ui(line)
    app._flash_bar.set(1.0)
    app._lbl_flash_pct.configure(text="100 %")
    app._lbl_flash_fase.configure(text=T("s2_fase_listo"), text_color=C_GREEN)

    sensor_results = [
        {"valor": 22.4, "unidad": "C", "estado": "ok", "mensaje": "22.4 C"},
        {"valor": 58.2, "unidad": "%", "estado": "ok", "mensaje": "58.2 %"},
        {"valor": 34.1, "unidad": "%", "estado": "ok", "mensaje": "34.1 %"},
    ]
    app._pin_dht  = 15
    app._pin_soil = 34
    app._aplicar_pines_ui()
    app._show_sensor_results(sensor_results)
    app._render_qr("AC-ESP32-7F3A")

    for i in range(3):
        app._step_checks[i].configure(text="✓", text_color=C_GREEN)

    app._show_step(0)


def main():
    app = AgroFlasher()
    app.mainloop()


if __name__ == "__main__":
    main()
