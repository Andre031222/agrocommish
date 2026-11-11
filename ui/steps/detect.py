import threading
import time

import customtkinter as ctk

from core.detector import detectar_puertos, puertos_como_set
from core.lang import T
from ui import theme as th
from ui.icons import icon
from ui.widgets import Banner, card, secondary_button, separator

SEP_PUERTO = "  —  "


class DetectStep:

    def _build_detect(self, f):
        self._header(f, 0, "s1_header", "s1_sub")
        c = card(f)
        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(22, 18))
        self._dot = ctk.CTkLabel(row, text="", width=44, height=44, corner_radius=12,
                                 fg_color=th.INPUT, image=icon("usb", 22, th.OFF))
        self._dot.pack(side="left")
        self._lbl_port_st = ctk.CTkLabel(row, text=T("s1_esperando"), font=self.fonts.body_b,
                                         text_color=th.TEXT3, anchor="w", justify="left",
                                         wraplength=640)
        self._lbl_port_st.pack(side="left", padx=(14, 0), fill="x", expand=True)
        secondary_button(row, "", lambda: threading.Thread(target=self._scan_ports, daemon=True).start(),
                         self.fonts, icon_name="refresh-cw", width=44, height=44,
                         text_color=th.INFO).pack(side="right")

        separator(c, padx=24)
        self._port_combo = ctk.CTkComboBox(
            c, variable=self._puerto, values=[T("s1_sin_dev")], height=46,
            font=self.fonts.body, dropdown_font=self.fonts.body, fg_color=th.INPUT,
            border_color=th.SEP, border_width=1, button_color=th.ACCENT,
            button_hover_color=th.ACCENT_DK, dropdown_fg_color=th.INPUT,
            dropdown_text_color=th.TEXT, dropdown_hover_color=th.HOVER,
            text_color=th.TEXT, corner_radius=12)
        self._port_combo.pack(fill="x", padx=24, pady=(18, 24))

        hint = Banner(f, self.fonts, "info")
        hint.pack(fill="x", pady=(0, 12))
        self._reg(hint.label, "s1_hint_auto")
        self._reg(ctk.CTkLabel(f, font=self.fonts.small, text_color=th.TEXT3, anchor="w",
                               justify="left", wraplength=860), "s1_boards").pack(fill="x", pady=(0, 24))

    def _scan_ports(self):
        ports = detectar_puertos()
        values = [f"{p['port']}{SEP_PUERTO}{p['descripcion']}" for p in ports]
        esp32s = [p for p in ports if p["es_esp32"]]
        self._known_ports = {p["port"] for p in ports}
        self._ui(lambda: self._port_combo.configure(values=values or [T("s1_sin_dev")]))
        if esp32s:
            sel = f"{esp32s[0]['port']}{SEP_PUERTO}{esp32s[0]['descripcion']}"
            self._ui(lambda: (self._puerto.set(sel), self._set_port_status(True, sel)))
        elif ports:
            self._ui(lambda: (self._puerto.set(values[0]),
                              self._set_port_status(None, T("s1_port_no_driver"))))
        else:
            self._ui(lambda: self._set_port_status(False, T("s1_esperando")))

    def _set_port_status(self, connected, msg: str):
        tono = {True: "success", None: "warn", False: None}[connected]
        fg, bg = th.TONES[tono] if tono else (th.OFF, th.INPUT)
        self._dot.configure(image=icon("usb", 22, fg), fg_color=bg)
        self._lbl_port_st.configure(text=msg, text_color=fg if tono else th.TEXT3)
        self._milestone("port", connected is True)

    def _hotplug_watch(self):
        time.sleep(1.5)
        previos = puertos_como_set()
        while self._hotplug_on:
            time.sleep(1.0)
            try:
                actuales = puertos_como_set()
            except OSError:
                continue
            nuevos = actuales - previos
            if nuevos or previos - actuales:
                self._scan_ports()
                esp32s = [p for p in detectar_puertos() if p["es_esp32"] and p["port"] in nuevos]
                if esp32s:
                    self._ui(lambda p=esp32s[0]: self._on_new_esp32(p))
            previos = actuales

    def _on_new_esp32(self, info: dict):
        texto = f"{info['port']}{SEP_PUERTO}{info['descripcion']}"
        self._puerto.set(texto)
        self._set_port_status(True, texto)
        self._pulse_dot(4)
        self._toast("success", T("toast_dev_t"), texto)
        if self._paso == 0:
            self.after(700, lambda: self.winfo_exists() and self._paso == 0 and self._show_step(1))

    def _pulse_dot(self, veces: int, encendido: bool = True):
        fg, bg = th.TONES["success"]
        self._dot.configure(fg_color=bg if encendido or veces <= 0 else th.INPUT)
        if veces > 0:
            self.after(160, lambda: self._pulse_dot(veces - 1, not encendido))

    def _get_port(self) -> str:
        return self._puerto.get().split(SEP_PUERTO)[0].strip()
