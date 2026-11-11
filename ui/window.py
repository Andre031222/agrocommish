import csv
import sys
import threading
import tkinter as tk
from datetime import datetime

import customtkinter as ctk

from core.config_manager import cargar as cfg_cargar, guardar as cfg_guardar
from core.lang import T, set_lang, get_lang
from core.network import ip_local
from core.paths import DEFAULT_FIRMWARE, ICON, LOGO, LOGS_DIR
from ui import theme as th
from ui.icons import icon
from ui.steps.activate import ActivateStep
from ui.steps.configure import ConfigureStep
from ui.steps.detect import DetectStep
from ui.steps.flash import FlashStep
from ui.steps.verify import VerifyStep
from ui.widgets import SplashScreen, Toast, load_logo, primary_button, secondary_button


class AgroCommish(ctk.CTk, DetectStep, FlashStep, ConfigureStep, VerifyStep, ActivateStep):

    STEP_KEYS = ("step_1", "step_2", "step_3", "step_4", "step_5")
    STEP_ICONS = ("usb", "zap", "wifi", "activity", "cloud-upload")
    MILESTONES = ("port", "flash", "pins", "wifi", "sensors", "cloud")
    SIDEBAR_OPEN = 260
    SIDEBAR_CLOSED = 76
    CONTENT_MAX = 980
    CONTENT_PAD = 40
    WIDTH, HEIGHT = 1200, 820

    def __init__(self, demo: bool = False):
        super().__init__()
        self.withdraw()
        cfg = cfg_cargar()
        set_lang(cfg.get("language", "es"))
        th.apply_appearance(cfg.get("appearance", "system"))
        self.fonts = th.Fonts()
        self._demo = demo

        self.title(T("app_title"))
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.minsize(1040, 720)
        self.configure(fg_color=th.BG)
        if ICON.exists() and sys.platform == "win32":
            self.iconbitmap(str(ICON))

        self._init_state(cfg)
        self._build()
        self._show_step(0)
        threading.Thread(target=self._scan_ports, daemon=True).start()
        threading.Thread(target=self._hotplug_watch, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        steps = [(0, 0.2, T("splash_1")), (220, 0.55, T("splash_2")),
                 (480, 0.85, T("splash_3")), (740, 1.0, T("splash_ready")), (980, 1.0, None)]
        SplashScreen(self, self.fonts, LOGO, T("configurador_iot"), steps, self._on_splash_done)

    def _init_state(self, cfg: dict):
        self._paso = 0
        self._puerto = ctk.StringVar(value=cfg.get("last_port", ""))
        self._fw_path = ctk.StringVar(value=cfg.get("last_firmware") or str(DEFAULT_FIRMWARE))
        self._ssid = ctk.StringVar(value=cfg.get("last_ssid", ""))
        self._wifi_pass = ctk.StringVar()
        self._server_url = ctk.StringVar(
            value=cfg.get("server_url") or f"http://{ip_local()}:5000/api/sensores/lectura")
        self._av_email = ctk.StringVar(value=cfg.get("av_email", ""))
        self._av_pass = ctk.StringVar()
        self._av_web_url = ctk.StringVar(value=cfg.get("av_web_url", "https://agroyachay.ginit.dev"))
        self._av_last_url = None
        self._t_off = ctk.StringVar(value="0.0")
        self._h_off = ctk.StringVar(value="0.0")
        self._s_dry = ctk.StringVar(value="50")
        self._s_wet = ctk.StringVar(value="3200")

        self._cfg_force = False
        self._device_id = None
        self._pin_dht = None
        self._pin_soil = None
        self._batch_count = 0
        self._device_done = False
        self._spinner_job = None
        self._known_ports = set()
        self._hotplug_on = True
        self._serial_lock = threading.Lock()
        self._sidebar_open = True
        self._sidebar_busy = False
        self._milestones = dict.fromkeys(self.MILESTONES, False)
        self._i18n: list[tuple] = []
        self._i18n_fn: list = []

        LOGS_DIR.mkdir(exist_ok=True)
        self._log_file = LOGS_DIR / f"sesion_{datetime.now():%Y%m%d_%H%M%S}.csv"
        with open(self._log_file, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["timestamp", "device_id", "puerto", "ssid", "servidor", "resultado"])

    def _on_splash_done(self):
        x = (self.winfo_screenwidth() - self.WIDTH) // 2
        y = max(20, (self.winfo_screenheight() - self.HEIGHT) // 2)
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
        self.attributes("-alpha", 0.0)
        self.deiconify()
        self.lift()
        self.focus_force()
        th.animate(self, 220, lambda e: self.attributes("-alpha", e))
        if self._demo:
            from ui.demo import inject_demo
            self.after(300, lambda: inject_demo(self))

    def _build(self):
        body = ctk.CTkFrame(self, fg_color=th.BG, corner_radius=0)
        body.pack(fill="both", expand=True)
        self._sidebar = ctk.CTkFrame(body, width=self.SIDEBAR_OPEN, fg_color=th.SIDEBAR, corner_radius=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        ctk.CTkFrame(body, width=1, fg_color=th.SEP, corner_radius=0).pack(side="left", fill="y")
        self._content = ctk.CTkFrame(body, fg_color=th.BG, corner_radius=0)
        self._content.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._build_footer()
        self._step_container = ctk.CTkFrame(self._content, fg_color=th.BG, corner_radius=0)
        self._step_container.pack(fill="both", expand=True)
        self._step_container.grid_rowconfigure(0, weight=1)
        self._step_container.grid_columnconfigure(0, weight=1)
        self._step_container.bind("<Configure>", lambda e: self._center_columns(e.width))

        self._pages, self._columns = [], []
        for build in (self._build_detect, self._build_flash, self._build_configure,
                      self._build_verify, self._build_activate):
            page = ctk.CTkScrollableFrame(self._step_container, fg_color=th.BG, corner_radius=0,
                                          scrollbar_button_color=th.BG,
                                          scrollbar_button_hover_color=th.SEP)
            column = ctk.CTkFrame(page, fg_color="transparent")
            column.pack(fill="x", padx=self.CONTENT_PAD)
            build(column)
            page.grid(row=0, column=0, sticky="nsew")
            self._pages.append(page)
            self._columns.append(column)

    def _center_columns(self, ancho: int):
        margen = max(self.CONTENT_PAD, (ancho - self.CONTENT_MAX) // 2)
        for column in self._columns:
            column.pack_configure(padx=margen)

    def _build_sidebar(self):
        f = self.fonts
        self._sb_top = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        self._sb_top.pack(fill="x", padx=14, pady=(16, 0))
        self._btn_sidebar = ctk.CTkButton(
            self._sb_top, text="", image=icon("panel-left", 20, th.TEXT2), width=40, height=36,
            fg_color="transparent", hover_color=th.HOVER, corner_radius=10, command=self._toggle_sidebar)
        self._btn_sidebar.pack(side="left")

        self._brand = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        self._brand.pack(fill="x", padx=18, pady=(12, 0))
        self._logo = load_logo(LOGO, 40)
        self._logo_lbl = ctk.CTkLabel(self._brand, image=self._logo, text="", width=40)
        self._logo_lbl.pack(side="left")
        self._brand_text = ctk.CTkFrame(self._brand, fg_color="transparent")
        self._brand_text.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(self._brand_text, text="AgroCommish", font=f.headline,
                     text_color=th.TEXT, anchor="w").pack(anchor="w")
        self._reg(ctk.CTkLabel(self._brand_text, font=f.caption, text_color=th.TEXT3, anchor="w"),
                  "configurador_iot").pack(anchor="w")

        ctk.CTkFrame(self._sidebar, height=1, fg_color=th.SEP).pack(fill="x", padx=16, pady=(16, 10))

        self._step_rows, self._step_icons, self._step_labels = [], [], []
        for i, key in enumerate(self.STEP_KEYS):
            row = ctk.CTkFrame(self._sidebar, fg_color="transparent", corner_radius=12,
                               height=50, cursor="hand2")
            row.pack(fill="x", padx=10, pady=2)
            row.pack_propagate(False)
            badge = ctk.CTkLabel(row, text="", width=34, height=34, corner_radius=10)
            badge.pack(side="left", padx=(10, 12))
            label = ctk.CTkLabel(row, text=T(key), font=f.body, text_color=th.TEXT3, anchor="w")
            label.pack(side="left", fill="x", expand=True)
            for w in (row, badge, label):
                w.bind("<Button-1>", lambda e, n=i: self._show_step(n))
                w.bind("<Enter>", lambda e, n=i: self._hover_row(n, True))
                w.bind("<Leave>", lambda e, n=i: self._hover_row(n, False))
            self._step_rows.append(row)
            self._step_icons.append(badge)
            self._step_labels.append(label)

        self._sb_bottom = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        self._sb_bottom.pack(side="bottom", fill="x", padx=14, pady=(0, 16))
        self._batch_box = ctk.CTkFrame(self._sb_bottom, fg_color=th.CARD, corner_radius=14,
                                       border_width=1, border_color=th.SEP)
        self._batch_box.pack(fill="x", pady=(0, 10))
        self._lbl_batch = ctk.CTkLabel(self._batch_box, text="0", font=f.display, text_color=th.ACCENT)
        self._lbl_batch.pack(anchor="w", padx=16, pady=(10, 0))
        self._reg(ctk.CTkLabel(self._batch_box, font=f.caption, text_color=th.TEXT3),
                  "unidades_listas").pack(anchor="w", padx=16, pady=(0, 10))

        self._prefs = ctk.CTkFrame(self._sb_bottom, fg_color="transparent")
        self._prefs.pack(fill="x")
        estilo = dict(height=38, fg_color=th.INPUT, hover_color=th.HOVER, text_color=th.TEXT2,
                      border_width=1, border_color=th.SEP, font=f.small, corner_radius=10)
        self._btn_theme = ctk.CTkButton(self._prefs, text="", image=icon("sun-moon", 18, th.TEXT2),
                                        compound="left", command=self._cycle_theme, **estilo)
        self._btn_lang = ctk.CTkButton(self._prefs, text="", image=icon("languages", 18, th.TEXT2),
                                       compound="left", width=70, command=self._toggle_lang, **estilo)
        self._layout_sidebar()

    def _layout_sidebar(self):
        abierta = self._sidebar_open
        self._btn_sidebar.pack_configure(side="left" if abierta else "top")
        self._logo_lbl.pack_configure(side="left" if abierta else "top")
        if abierta:
            self._brand_text.pack(side="left", padx=(12, 0))
            self._batch_box.pack(fill="x", pady=(0, 10), before=self._prefs)
        else:
            self._brand_text.pack_forget()
            self._batch_box.pack_forget()
        for badge, label in zip(self._step_icons, self._step_labels):
            if abierta:
                badge.pack_configure(side="left", padx=(10, 12), pady=0)
                label.pack(side="left", fill="x", expand=True)
            else:
                label.pack_forget()
                badge.pack_configure(side="top", padx=0, pady=8)
        self._btn_theme.pack_forget()
        self._btn_lang.pack_forget()
        if abierta:
            self._btn_theme.pack(side="left", fill="x", expand=True)
            self._btn_lang.pack(side="left", padx=(8, 0))
        else:
            self._btn_theme.pack(side="top", pady=(0, 8))
            self._btn_lang.pack(side="top")
        self._refresh_prefs()

    def _build_footer(self):
        footer = ctk.CTkFrame(self._content, height=84, fg_color=th.BG, corner_radius=0)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        self._progress = ctk.CTkProgressBar(footer, height=3, corner_radius=0,
                                            fg_color=th.SEP, progress_color=th.ACCENT)
        self._progress.set(0.2)
        self._progress.pack(fill="x", side="top")
        self._btn_prev = secondary_button(footer, T("btn_anterior"), self._prev, self.fonts,
                                          icon_name="arrow-left", width=150)
        self._btn_prev.pack(side="left", padx=self.CONTENT_PAD, pady=18)
        self._btn_new_dev = secondary_button(footer, T("btn_nuevo_dispositivo"), self._new_device,
                                             self.fonts, icon_name="plus", width=210,
                                             text_color=th.ACCENT, state="disabled")
        self._btn_new_dev.pack(side="right", padx=(10, self.CONTENT_PAD), pady=18)
        self._btn_next = primary_button(footer, T("btn_continuar"), self._next, self.fonts,
                                        icon_name="arrow-right", compound="right", width=170, height=42)
        self._btn_next.pack(side="right", pady=18)

    def _header(self, parent, idx: int, title_key: str, sub_key: str):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(fill="x", pady=(26, 16))
        etiqueta = ctk.CTkLabel(box, font=self.fonts.eyebrow, text_color=th.ACCENT, anchor="w")
        etiqueta.pack(anchor="w")

        def actualizar():
            etiqueta.configure(text=T("step_of", n=idx + 1, total=5))

        actualizar()
        self._i18n_fn.append(actualizar)
        self._reg(ctk.CTkLabel(box, font=self.fonts.title, text_color=th.TEXT, anchor="w"),
                  title_key).pack(anchor="w", pady=(4, 0))
        self._reg(ctk.CTkLabel(box, font=self.fonts.body, text_color=th.TEXT3, anchor="w",
                               justify="left", wraplength=860), sub_key).pack(anchor="w", pady=(6, 0))

    def _reg(self, widget, key: str):
        widget.configure(text=T(key))
        self._i18n.append((widget, key))
        return widget

    def _hover_row(self, n: int, entrando: bool):
        if n != self._paso:
            self._step_rows[n].configure(fg_color=th.HOVER if entrando else "transparent")

    def _toggle_sidebar(self):
        if self._sidebar_busy:
            return
        self._sidebar_busy = True
        self._sidebar_open = not self._sidebar_open
        inicio = self._sidebar.winfo_width()
        fin = self.SIDEBAR_OPEN if self._sidebar_open else self.SIDEBAR_CLOSED
        if not self._sidebar_open:
            self._layout_sidebar()

        def terminar():
            if self._sidebar_open:
                self._layout_sidebar()
            self._sidebar_busy = False

        th.animate(self, 160, lambda e: self._sidebar.configure(width=int(inicio + (fin - inicio) * e)),
                   terminar, th.ease_in_out)

    def _cycle_theme(self):
        actual = cfg_cargar().get("appearance", "system")
        indice = th.APPEARANCES.index(actual) if actual in th.APPEARANCES else 0
        siguiente = th.APPEARANCES[(indice + 1) % len(th.APPEARANCES)]
        th.apply_appearance(siguiente)
        cfg_guardar(appearance=siguiente)
        self._refresh_prefs()

    def _refresh_prefs(self):
        if not self._sidebar_open:
            self._btn_theme.configure(text="", width=44)
            self._btn_lang.configure(text="", width=44)
            return
        nombres = {"system": T("theme_system"), "light": T("theme_light"), "dark": T("theme_dark")}
        modo = cfg_cargar().get("appearance", "system")
        self._btn_theme.configure(text=f"  {nombres.get(modo, nombres['system'])}", width=120)
        self._btn_lang.configure(text=f" {T('lang_btn')}", width=70)

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
        for fn in self._i18n_fn:
            fn()
        for label, key in zip(self._step_labels, self.STEP_KEYS):
            label.configure(text=T(key))
        self._btn_prev.configure(text=T("btn_anterior"))
        self._btn_next.configure(text=T("btn_continuar"))
        self._btn_new_dev.configure(text=T("btn_nuevo_dispositivo"))
        self._refresh_prefs()
        self._refresh_checklist()
        self._lang_refresh_flash()
        self._lang_refresh_configure()
        self._lang_refresh_verify()
        self._lang_refresh_activate()

    def _paint_sidebar(self, n: int):
        for i, (row, badge, label) in enumerate(zip(self._step_rows, self._step_icons, self._step_labels)):
            if i == n:
                row.configure(fg_color=th.ACCENT_BG)
                badge.configure(fg_color=th.ACCENT, image=icon(self.STEP_ICONS[i], 18, th.ON_ACCENT))
                label.configure(text_color=th.TEXT, font=self.fonts.body_b)
            elif i < n:
                row.configure(fg_color="transparent")
                badge.configure(fg_color=th.SUCCESS_BG, image=icon("check", 18, th.SUCCESS))
                label.configure(text_color=th.TEXT2, font=self.fonts.body)
            else:
                row.configure(fg_color="transparent")
                badge.configure(fg_color=th.CARD, image=icon(self.STEP_ICONS[i], 18, th.TEXT3))
                label.configure(text_color=th.TEXT3, font=self.fonts.body)

    def _show_step(self, n: int):
        anterior = self._paso
        self._paso = n
        self._paint_sidebar(n)
        if n == 3:
            self._prepare_verify()
        elif n == 4:
            self._prepare_activate()
        self._btn_prev.configure(state="normal" if n > 0 else "disabled")
        self._btn_next.configure(state="normal" if n < 4 else "disabled")
        self._btn_new_dev.configure(state="normal" if self._device_done else "disabled")

        if anterior != n:
            self._pages[n]._parent_canvas.yview_moveto(0)
        self._pages[n].lift()
        self._progress_target = (n + 1) / 5
        inicio = self._progress.get()
        th.animate(self, 260, lambda e: self._progress.set(inicio + (self._progress_target - inicio) * e))

    def _prev(self):
        if self._paso > 0:
            self._show_step(self._paso - 1)

    def _next(self):
        if self._paso < 4:
            self._show_step(self._paso + 1)

    def _new_device(self):
        self._device_id = None
        self._pin_dht = None
        self._pin_soil = None
        self._cfg_force = False
        self._device_done = False
        self._milestones = dict.fromkeys(self.MILESTONES, False)
        self._refresh_checklist()
        self._reset_flash()
        self._reset_configure()
        self._reset_verify()
        self._show_step(0)
        threading.Thread(target=self._scan_ports, daemon=True).start()

    def _milestone(self, key: str, done: bool = True):
        if self._milestones[key] != done:
            self._milestones[key] = done
            self._refresh_checklist()

    def _toast(self, tone: str, title: str, detail: str = "", ms: int = 3200):
        Toast(self, self.fonts, tone, title, detail, ms)

    def _spin_start(self, label, base_text: str):
        marcos = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

        def tick(i=0):
            if self._spinner_job:
                label.configure(text=f"{marcos[i % len(marcos)]}  {base_text}")
                self._spinner_job = self.after(90, lambda: tick(i + 1))

        self._spinner_job = self.after(0, tick)

    def _spin_stop(self):
        if self._spinner_job:
            self.after_cancel(self._spinner_job)
            self._spinner_job = None

    def _ui(self, fn):
        self.after(0, lambda: self.winfo_exists() and fn())

    def _log_write(self, resultado: str):
        with open(self._log_file, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([datetime.now().isoformat(), self._device_id or "",
                                    self._get_port(), self._ssid.get(),
                                    self._server_url.get(), resultado])

    def _save_cfg(self):
        cfg_guardar(server_url=self._server_url.get().strip(),
                    last_ssid=self._ssid.get().strip(),
                    last_firmware=self._fw_path.get().strip(),
                    last_port=self._get_port().strip(),
                    language=get_lang())

    def _on_close(self):
        self._hotplug_on = False
        self.destroy()
