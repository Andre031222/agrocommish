import re
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.flasher import Flasher
from core.lang import T
from core.paths import FIRMWARE_DIR
from core.provisioner import Provisioner, esperar_dispositivo
from ui import theme as th
from ui.icons import icon
from ui.widgets import TONE_ICONS, card, eyebrow, primary_button, secondary_button

_CHIP = re.compile(r"chip (?:is|type)[\s.:]*\s*(ESP32[\w-]*)", re.IGNORECASE)


class FlashStep:

    def _build_flash(self, f):
        self._header(f, 1, "s2_header", "s2_sub")
        c = card(f)

        self._fw_row = ctk.CTkFrame(c, corner_radius=12)
        self._fw_row.pack(fill="x", padx=24, pady=(22, 0))
        self._fw_lbl = ctk.CTkLabel(self._fw_row, font=self.fonts.body_b, anchor="w", compound="left")
        self._fw_lbl.pack(side="left", fill="x", expand=True, padx=16, pady=12)
        self._btn_sel_fw = secondary_button(self._fw_row, T("s2_btn_seleccionar"), self._pick_firmware,
                                            self.fonts, width=110, height=34, font=self.fonts.small)
        self._btn_sel_fw.pack(side="right", padx=10)
        self._i18n.append((self._btn_sel_fw, "s2_btn_seleccionar"))
        self._refresh_fw_row()

        self._lbl_chip = ctk.CTkLabel(c, text=T("s2_chip_auto"), font=self.fonts.small,
                                      text_color=th.TEXT3, anchor="w", compound="left",
                                      image=icon("cpu", 16, th.TEXT3))
        self._lbl_chip.pack(fill="x", padx=24, pady=(12, 0))

        prog = ctk.CTkFrame(c, fg_color="transparent")
        prog.pack(fill="x", padx=24, pady=(18, 0))
        self._flash_bar = ctk.CTkProgressBar(prog, height=10, corner_radius=5,
                                             fg_color=th.SEP, progress_color=th.ACCENT)
        self._flash_bar.set(0)
        self._flash_bar.pack(side="left", fill="x", expand=True)
        self._lbl_flash_pct = ctk.CTkLabel(prog, text="0 %", width=72, font=self.fonts.mono_l,
                                           text_color=th.ACCENT, anchor="e")
        self._lbl_flash_pct.pack(side="left", padx=(12, 0))
        self._lbl_flash_fase = ctk.CTkLabel(c, text="", font=self.fonts.small,
                                            text_color=th.TEXT3, anchor="w")
        self._lbl_flash_fase.pack(fill="x", padx=24, pady=(6, 8))

        self._reg(eyebrow(c, self.fonts), "s2_log_label").pack(fill="x", padx=24, pady=(4, 6))
        self._flash_log = ctk.CTkTextbox(c, height=200, font=self.fonts.mono, fg_color=th.TERMINAL,
                                         text_color=th.TERMINAL_FG, corner_radius=12,
                                         scrollbar_button_color=th.SEP, wrap="word")
        self._flash_log.pack(fill="x", padx=24)
        self._flash_log.configure(state="disabled")

        self._btn_flash = primary_button(c, T("s2_btn_grabar"), self._do_flash, self.fonts, icon_name="zap")
        self._btn_flash.pack(fill="x", padx=24, pady=(18, 24))
        self._flash_indet = False

    def _refresh_fw_row(self):
        existe = Path(self._fw_path.get()).exists()
        tono = "success" if existe else "warn"
        fg, bg = th.TONES[tono]
        self._fw_row.configure(fg_color=bg)
        texto = (T("s2_fw_ok") if existe else T("s2_fw_missing"))
        self._fw_lbl.configure(text=f"  {texto}", text_color=fg, image=icon(TONE_ICONS[tono], 18, fg))

    def _lang_refresh_flash(self):
        self._refresh_fw_row()
        if self._btn_flash.cget("state") == "normal":
            self._btn_flash.configure(text=T("s2_btn_grabar"))

    def _pick_firmware(self):
        ruta = filedialog.askopenfilename(title=T("fw_title"), initialdir=str(FIRMWARE_DIR),
                                          filetypes=[(T("fw_filter"), "*.bin"), ("*", "*.*")])
        if ruta:
            self._fw_path.set(ruta)
            self._refresh_fw_row()
            self._save_cfg()

    def _log_write_ui(self, text: str):
        self._flash_log.configure(state="normal")
        self._flash_log.insert("end", text + "\n")
        self._flash_log.see("end")
        self._flash_log.configure(state="disabled")

    def _set_bar(self, valor: float):
        inicio = self._flash_bar.get()
        th.animate(self, 180, lambda e: self._flash_bar.set(inicio + (valor - inicio) * e))

    def _stop_indeterminate(self):
        if self._flash_indet:
            self._flash_indet = False
            self._flash_bar.stop()
            self._flash_bar.configure(mode="determinate")

    def _do_flash(self):
        port = self._get_port()
        if not port:
            self._log_write_ui(T("s2_err_sin_puerto"))
            return
        fw = self._fw_path.get()
        if not Path(fw).exists():
            self._log_write_ui(T("s2_err_fw_noexiste"))
            return
        self._log_write("FLASH_INICIO")
        self._btn_flash.configure(state="disabled", text=T("s2_grabando"))
        self._flash_indet = True
        self._flash_bar.configure(mode="indeterminate")
        self._flash_bar.start()
        self._lbl_flash_pct.configure(text="")
        self._lbl_flash_fase.configure(text=T("s2_fase_conectando"), text_color=th.TEXT3)
        self._log_write_ui(T("s2_log_puerto", port=port))
        self._log_write_ui(T("s2_log_fw", fw=fw))

        def run():
            if not self._serial_lock.acquire(blocking=False):
                self._ui(lambda: (self._log_write_ui(T("puerto_ocupado")), self._reset_flash_bar(),
                                  self._btn_flash.configure(state="normal", text=T("s2_btn_grabar"))))
                return
            try:
                Flasher(port, fw).flashear(
                    on_output=lambda l: self._ui(lambda: self._flash_linea(l)),
                    on_progress=lambda p: self._ui(lambda: self._flash_progreso(p)))
                self._ui(self._flash_ok)
            except (RuntimeError, FileNotFoundError, OSError) as e:
                self._ui(lambda err=str(e): self._flash_err(err))
            finally:
                self._serial_lock.release()

        threading.Thread(target=run, daemon=True).start()

    def _reset_flash_bar(self):
        self._stop_indeterminate()
        self._flash_bar.set(0)
        self._lbl_flash_pct.configure(text="0 %")
        self._lbl_flash_fase.configure(text="")

    def _reset_flash(self):
        self._reset_flash_bar()
        self._lbl_chip.configure(text=T("s2_chip_auto"), text_color=th.TEXT3, image=icon("cpu", 16, th.TEXT3))
        self._log_write_ui(T("nuevo_dispositivo"))

    def _flash_linea(self, linea: str):
        self._log_write_ui(linea)
        chip = _CHIP.search(linea)
        if chip:
            self._lbl_chip.configure(text=T("s2_chip", chip=chip.group(1)), text_color=th.INFO,
                                     image=icon("cpu", 16, th.INFO))
        texto = linea.lower()
        if "erasing" in texto:
            self._lbl_flash_fase.configure(text=T("s2_fase_borrando"), text_color=th.WARN)
        elif "hash of data verified" in texto:
            self._lbl_flash_fase.configure(text=T("s2_fase_verificado"), text_color=th.SUCCESS)

    def _flash_progreso(self, p: int):
        if self._flash_indet:
            self._stop_indeterminate()
            self._lbl_flash_fase.configure(text=T("s2_fase_grabando"), text_color=th.ACCENT)
        self._set_bar(p / 100)
        self._lbl_flash_pct.configure(text=f"{p} %")

    def _flash_ok(self):
        self._log_write("FLASH_OK")
        self._log_write_ui(T("s2_ok"))
        self._stop_indeterminate()
        self._set_bar(1.0)
        self._lbl_flash_pct.configure(text="100 %")
        self._lbl_flash_fase.configure(text=T("s2_fase_listo"), text_color=th.SUCCESS)
        self._btn_flash.configure(state="normal", text=T("s2_btn_grabar"))
        self._log_write_ui(T("s2_boot_wait"))
        self._milestone("flash")
        self._toast("success", T("toast_flash_t"), T("toast_flash_d"))
        threading.Thread(target=self._post_flash_worker, args=(self._get_port(),), daemon=True).start()

    def _post_flash_worker(self, port: str):
        if not self._serial_lock.acquire(timeout=10):
            self._ui(lambda: (self._log_write_ui(T("puerto_ocupado")), self._goto_config()))
            return
        try:
            try:
                info = esperar_dispositivo(port)
            except (TimeoutError, RuntimeError, OSError) as e:
                self._ui(lambda err=str(e): (self._log_write_ui(T("s2_boot_timeout", err=err)),
                                             self._goto_config()))
                return
            did = info.get("device_id") or "DESCONOCIDO"
            self._device_id = did
            self._ui(lambda: (self._log_write_ui(T("s2_dev_id", did=did)),
                              self._log_write_ui(T("s2_pins_scan"))))
            try:
                with Provisioner(port, timeout=4.0) as p:
                    r = p.detectar_pines(aplicar=True)
                if not r.get("ok"):
                    raise RuntimeError(r.get("error", "respuesta inválida"))
            except (TimeoutError, RuntimeError, OSError, ValueError) as e:
                self._ui(lambda err=str(e): (self._log_write_ui(T("pins_err", err=err)),
                                             self._goto_config()))
                return
        finally:
            self._serial_lock.release()
        self._ui(lambda: self._show_pins_after_flash(r))

    def _show_pins_after_flash(self, r: dict):
        msg, tone = self._interpretar_pines(r)
        self._log_write("PINES_DETECTADOS")
        self._log_write_ui(msg)
        self._lbl_pins_st.configure(text=msg, text_color=th.TONES[tone][0])
        self._toast(tone, T("toast_pins_t"), msg, ms=4500)
        self._goto_config()

    def _goto_config(self):
        if self._paso == 1:
            self._show_step(2)
            self._scan_wifi()

    def _flash_err(self, msg: str):
        self._log_write_ui(f"\nError: {msg}")
        self._reset_flash_bar()
        self._btn_flash.configure(state="normal", text=T("s2_reintento"))
        self._toast("error", T("toast_err_t"), msg.splitlines()[0][:120], ms=4500)
