import threading
import urllib.parse

import customtkinter as ctk

from core.lang import T
from core.network import clave_wifi_valida, ip_local, puerto_abierto
from core.provisioner import Provisioner
from ui import theme as th
from ui.icons import icon
from ui.widgets import Banner, card, entry, eyebrow, ghost_button, primary_button, secondary_button, separator


def _senal(rssi: int) -> str:
    return "wifi" if rssi > -55 else "wifi-high" if rssi > -67 else "wifi-low" if rssi > -78 else "wifi-zero"


class ConfigureStep:

    def _build_configure(self, f):
        self._header(f, 2, "s3_header", "s3_sub")
        self._net_security: dict[str, bool] = {}
        self._net_rows: dict[str, ctk.CTkFrame] = {}
        c = card(f)

        top = ctk.CTkFrame(c, fg_color="transparent")
        top.pack(fill="x", padx=24, pady=(20, 8))
        self._reg(eyebrow(top, self.fonts), "s3_lbl_redes").pack(side="left")
        self._btn_scan_wifi = ghost_button(top, T("s3_btn_escanear"), self._scan_wifi, self.fonts,
                                           icon_name="refresh-cw", width=150)
        self._btn_scan_wifi.pack(side="right")

        self._nets_scroll = ctk.CTkScrollableFrame(c, height=190, fg_color=th.INPUT, corner_radius=12,
                                                   scrollbar_button_color=th.SEP)
        self._nets_scroll.pack(fill="x", padx=24)
        self._lbl_cfg_st = ctk.CTkLabel(c, text="", font=self.fonts.small, text_color=th.TEXT3,
                                        anchor="w", justify="left", wraplength=760)
        self._lbl_cfg_st.pack(fill="x", padx=24, pady=(8, 0))

        self._security = Banner(c, self.fonts, "info")

        separator(c, padx=24, pady=(14, 0))
        self._reg(eyebrow(c, self.fonts), "s3_lbl_pass").pack(fill="x", padx=24, pady=(16, 6))
        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(fill="x", padx=24)
        self._entry_pass = entry(row, self.fonts, self._wifi_pass, T("s3_ph_pass"), show="●")
        self._entry_pass.pack(side="left", fill="x", expand=True)
        self._btn_show_pass = secondary_button(row, T("s3_pass_show"), self._toggle_pass_visibility,
                                               self.fonts, icon_name="eye", width=118, height=46,
                                               font=self.fonts.small, text_color=th.TEXT2)
        self._btn_show_pass.pack(side="left", padx=(10, 0))
        self._lbl_pass_hint = ctk.CTkLabel(c, text=T("s3_pass_privacy"), font=self.fonts.caption,
                                           text_color=th.TEXT3, anchor="w", compound="left")
        self._lbl_pass_hint.pack(fill="x", padx=24, pady=(6, 0))
        self._wifi_pass.trace_add("write", lambda *_: self._validate_pass())

        self._btn_adv = ghost_button(c, "", self._toggle_adv, self.fonts, anchor="w", text_color=th.TEXT3)
        self._btn_adv.pack(anchor="w", padx=18, pady=(12, 0))
        self._adv_panel = ctk.CTkFrame(c, fg_color="transparent")
        self._adv_visible = False
        entry(self._adv_panel, self.fonts, self._server_url, T("s3_ph_server"),
              font=self.fonts.mono, height=42).pack(fill="x", padx=24, pady=(4, 4))

        self._btn_cfg = primary_button(c, T("s3_btn_conectar"), self._do_config, self.fonts, icon_name="wifi")
        self._btn_cfg.pack(fill="x", padx=24, pady=(14, 24))

        tools = card(f)
        bar = ctk.CTkFrame(tools, fg_color="transparent")
        bar.pack(fill="x", padx=18, pady=(14, 6))
        self._btn_cal = ghost_button(bar, "", self._toggle_cal, self.fonts, anchor="w", text_color=th.TEXT2,
                                     icon_name="sliders-horizontal")
        self._btn_cal.pack(side="left")
        self._reg(ctk.CTkLabel(bar, font=self.fonts.caption, text_color=th.TEXT3), "s3_cal_opcional").pack(side="left")
        self._btn_pins = secondary_button(bar, T("pins_btn"), self._do_detect_pins, self.fonts,
                                          icon_name="scan-search", width=190, height=38,
                                          font=self.fonts.small, text_color=th.WARN)
        self._btn_pins.pack(side="right")
        self._i18n.append((self._btn_pins, "pins_btn"))
        self._lbl_pins_st = ctk.CTkLabel(tools, text="", font=self.fonts.small, text_color=th.TEXT3,
                                         justify="left", anchor="w", wraplength=760)
        self._lbl_pins_st.pack(fill="x", padx=24, pady=(0, 14))

        self._cal_panel = ctk.CTkFrame(tools, fg_color="transparent")
        self._cal_visible = False
        self._reg(ctk.CTkLabel(self._cal_panel, font=self.fonts.small, text_color=th.TEXT3, anchor="w"),
                  "s3_cal_hint").pack(fill="x", padx=24, pady=(0, 8))
        for key, var, ph in (("s3_cal_t_off", self._t_off, "0.0"), ("s3_cal_h_off", self._h_off, "0.0"),
                             ("s3_cal_s_dry", self._s_dry, "50"), ("s3_cal_s_wet", self._s_wet, "3200")):
            fila = ctk.CTkFrame(self._cal_panel, fg_color="transparent")
            fila.pack(fill="x", padx=24, pady=3)
            self._reg(ctk.CTkLabel(fila, width=300, font=self.fonts.body, text_color=th.TEXT2, anchor="w"),
                      key).pack(side="left")
            entry(fila, self.fonts, var, ph, width=130, height=40).pack(side="left")
        self._lbl_cal_st = ctk.CTkLabel(self._cal_panel, text="", font=self.fonts.small, text_color=th.TEXT3)
        self._lbl_cal_st.pack(anchor="w", padx=24, pady=(6, 0))
        self._btn_cal_send = secondary_button(self._cal_panel, T("s3_cal_btn"), self._do_calibrate,
                                              self.fonts, text_color=th.INFO)
        self._btn_cal_send.pack(anchor="w", padx=24, pady=(6, 18))

        self._lang_refresh_configure()

    def _lang_refresh_configure(self):
        self._btn_adv.configure(text=f"  {T('s3_adv_server')}", image=icon(
            "chevron-down" if self._adv_visible else "chevron-right", 16, th.TEXT3))
        self._btn_cal.configure(text=f"  {T('s3_cal_toggle')}")
        visible = self._entry_pass.cget("show") == ""
        self._btn_show_pass.configure(text=f" {T('s3_pass_hide') if visible else T('s3_pass_show')}",
                                      image=icon("eye-off" if visible else "eye", 18, th.TEXT2))
        for btn, key in ((self._btn_cfg, "s3_btn_enviar"), (self._btn_cal_send, "s3_cal_btn")):
            if btn.cget("state") == "normal":
                btn.configure(text=T(key))
        self._validate_pass()

    def _reset_configure(self):
        self._wifi_pass.set("")
        self._lbl_pins_st.configure(text="", text_color=th.TEXT3)

    def _toggle_pass_visibility(self):
        self._entry_pass.configure(show="" if self._entry_pass.cget("show") else "●")
        self._lang_refresh_configure()

    def _toggle_adv(self):
        self._adv_visible = not self._adv_visible
        if self._adv_visible:
            self._adv_panel.pack(fill="x", after=self._btn_adv)
        else:
            self._adv_panel.pack_forget()
        self._lang_refresh_configure()

    def _toggle_cal(self):
        self._cal_visible = not self._cal_visible
        if self._cal_visible:
            self._cal_panel.pack(fill="x", after=self._lbl_pins_st)
        else:
            self._cal_panel.pack_forget()
        self._lang_refresh_configure()

    def _selected_security(self):
        return self._net_security.get(self._ssid.get().strip())

    def _validate_pass(self, estricto: bool = False) -> bool:
        clave = self._wifi_pass.get()
        segura = self._selected_security()
        valida = clave_wifi_valida(clave, segura)
        if valida or not (clave or estricto):
            texto, color, nombre = T("s3_pass_privacy"), th.TEXT3, "lock"
        else:
            texto, color, nombre = T("s3_pass_open") if segura is False else T("s3_pass_len"), th.DANGER, "triangle-alert"
        self._lbl_pass_hint.configure(text=f"  {texto}", text_color=color, image=icon(nombre, 14, color))
        return valida

    def _scan_wifi(self):
        port = self._get_port()
        if not port:
            self._lbl_cfg_st.configure(text=T("sin_puerto"), text_color=th.DANGER)
            return
        self._btn_scan_wifi.configure(state="disabled", text=T("s3_escaneando"))
        self._lbl_cfg_st.configure(text=T("s3_escaneando"), text_color=th.TEXT3)
        for w in self._nets_scroll.winfo_children():
            w.destroy()

        def run():
            if not self._serial_lock.acquire(timeout=8):
                self._ui(lambda: (self._lbl_cfg_st.configure(text=T("puerto_ocupado"), text_color=th.WARN),
                                  self._btn_scan_wifi.configure(state="normal", text=T("s3_btn_escanear"))))
                return
            try:
                with Provisioner(port, timeout=18.0) as p:
                    nets = p.escanear_wifi()
                self._ui(lambda: self._render_net_cards(nets))
            except (TimeoutError, RuntimeError, OSError) as e:
                self._ui(lambda err=str(e): (
                    self._lbl_cfg_st.configure(text=f"{err}", text_color=th.DANGER),
                    self._btn_scan_wifi.configure(state="normal", text=T("s3_btn_escanear"))))
            finally:
                self._serial_lock.release()

        threading.Thread(target=run, daemon=True).start()

    def _render_net_cards(self, nets: list):
        for w in self._nets_scroll.winfo_children():
            w.destroy()
        self._net_security = {n.get("ssid", ""): bool(n.get("secure")) for n in nets}
        self._net_rows = {}
        if not nets:
            ctk.CTkLabel(self._nets_scroll, text=T("s3_ninguna_red"), font=self.fonts.small,
                         text_color=th.TEXT3).pack(pady=12)
        for net in nets:
            self._net_row(net.get("ssid", ""), net.get("rssi", -99), bool(net.get("secure")))
        self._lbl_cfg_st.configure(text=T("s3_redes_found", n=len(nets)), text_color=th.SUCCESS)
        self._btn_scan_wifi.configure(state="normal", text=T("s3_btn_escanear"))
        if self._ssid.get().strip() in self._net_rows:
            self._select_net(self._ssid.get().strip())

    def _net_row(self, ssid: str, rssi: int, segura: bool):
        row = ctk.CTkFrame(self._nets_scroll, fg_color="transparent", corner_radius=10,
                           height=46, cursor="hand2")
        row.pack(fill="x", pady=2, padx=2)
        row.pack_propagate(False)
        ssid_lbl = ctk.CTkLabel(row, text=ssid, font=self.fonts.body, text_color=th.TEXT, anchor="w")
        ssid_lbl.pack(side="left", padx=14, fill="x", expand=True)
        tag_fg, tag_bg = th.TONES["success" if segura else "warn"]
        tag = ctk.CTkLabel(row, text=f" {T('s3_net_secure') if segura else T('s3_net_open')}  ",
                           image=icon("lock" if segura else "lock-open", 14, tag_fg), compound="left",
                           font=self.fonts.caption, text_color=tag_fg, fg_color=tag_bg,
                           corner_radius=8, height=26, width=112)
        tag.pack(side="right", padx=(10, 12))
        senal = ctk.CTkLabel(row, text=f"  {rssi} dBm", image=icon(_senal(rssi), 18, th.TEXT3),
                             compound="left", font=self.fonts.mono, text_color=th.TEXT3,
                             width=120, anchor="e")
        senal.pack(side="right")
        for w in (row, ssid_lbl, tag, senal):
            w.bind("<Button-1>", lambda e, s=ssid: self._select_net(s))
            w.bind("<Enter>", lambda e, s=ssid: self._hover_net(s, True))
            w.bind("<Leave>", lambda e, s=ssid: self._hover_net(s, False))
        self._net_rows[ssid] = row

    def _hover_net(self, ssid: str, entrando: bool):
        if ssid != self._ssid.get().strip():
            self._net_rows[ssid].configure(fg_color=th.HOVER if entrando else "transparent")

    def _select_net(self, ssid: str):
        self._ssid.set(ssid)
        for nombre, row in self._net_rows.items():
            row.configure(fg_color=th.ACCENT_BG if nombre == ssid else "transparent")
        self._lbl_cfg_st.configure(text=f"{ssid}  {T('s3_red_sel')}", text_color=th.ACCENT)
        segura = self._net_security.get(ssid)
        if segura is None:
            self._security.pack_forget()
        else:
            self._security.set(T("s3_wifi_secure") if segura else T("s3_wifi_open"),
                               "success" if segura else "warn")
            self._security.pack(fill="x", padx=24, pady=(10, 0), after=self._lbl_cfg_st)
        if segura is False:
            self._wifi_pass.set("")
        self._validate_pass()
        self._entry_pass.focus_set()

    def _do_config(self):
        port = self._get_port()
        ssid = self._ssid.get().strip()
        passwd = self._wifi_pass.get()
        server = self._server_url.get().strip()
        url = urllib.parse.urlparse(server)
        error = (T("sin_puerto") if not port else T("s3_sin_ssid") if not ssid
                 else T("s3_sin_server") if not server
                 else T("s3_url_invalida") if not url.scheme or not url.netloc
                 else None)
        if error:
            self._lbl_cfg_st.configure(text=error, text_color=th.DANGER)
            return
        if not self._validate_pass(estricto=True):
            self._entry_pass.focus_set()
            return

        self._btn_cfg.configure(state="disabled", text=T("s3_enviando"))
        self._spin_start(self._lbl_cfg_st, T("s3_enviando_cfg"))
        host, puerto = url.hostname, url.port or (443 if url.scheme == "https" else 80)
        forzar, self._cfg_force = self._cfg_force, False

        def run():
            if not forzar and not puerto_abierto(host, puerto):
                self._ui(lambda: self._server_unreachable(host, puerto))
                return
            if not self._serial_lock.acquire(timeout=8):
                self._ui(lambda: self._config_err(T("puerto_ocupado")))
                return
            try:
                with Provisioner(port) as p:
                    try:
                        self._device_id = p.identificar().get("device_id", "DESCONOCIDO")
                    except (TimeoutError, RuntimeError, OSError):
                        self._device_id = "DESCONOCIDO"
                    r = p.configurar(ssid, passwd, server)
                did = r.get("device_id") or self._device_id
                self._device_id = did
                if r.get("ok"):
                    self._ui(lambda: self._config_ok(did))
                else:
                    self._ui(lambda: self._config_err(r.get("error", "Error")))
            except (TimeoutError, RuntimeError, OSError) as e:
                self._ui(lambda err=str(e): self._config_err(err))
            finally:
                self._serial_lock.release()

        threading.Thread(target=run, daemon=True).start()

    def _server_unreachable(self, host: str, puerto: int):
        self._cfg_force = True
        self._spin_stop()
        self._lbl_cfg_st.configure(text=T("s3_srv_warn", base=f"{host}:{puerto}", ip=ip_local()),
                                   text_color=th.WARN)
        self._btn_cfg.configure(state="normal", text=T("s3_btn_enviar"))

    def _config_ok(self, did: str):
        self._log_write("CONFIG_OK")
        self._spin_stop()
        self._wifi_pass.set("")
        self._lbl_cfg_st.configure(text=T("s3_cfg_ok", did=did), text_color=th.SUCCESS)
        self._btn_cfg.configure(state="normal", text=T("s3_btn_enviar"))
        self._save_cfg()
        self._milestone("wifi")
        self._toast("success", T("toast_cfg_t"), f"ID: {did}")
        self._show_step(3)
        self.after(4000, self._auto_test)

    def _config_err(self, msg: str):
        self._spin_stop()
        self._lbl_cfg_st.configure(text=f"{msg}", text_color=th.DANGER)
        self._btn_cfg.configure(state="normal", text=T("s3_btn_enviar"))
        self._toast("error", T("toast_err_t"), msg.splitlines()[0][:120], ms=4500)

    def _do_calibrate(self):
        port = self._get_port()
        if not port:
            self._lbl_cal_st.configure(text=T("sin_puerto"), text_color=th.DANGER)
            return
        try:
            t_off, h_off = float(self._t_off.get()), float(self._h_off.get())
            s_dry, s_wet = int(self._s_dry.get()), int(self._s_wet.get())
        except ValueError:
            self._lbl_cal_st.configure(text=T("s3_cal_invalidos"), text_color=th.DANGER)
            return
        if s_dry >= s_wet:
            self._lbl_cal_st.configure(text=T("s3_cal_soil_err"), text_color=th.DANGER)
            return
        self._btn_cal_send.configure(state="disabled", text=T("s3_enviando"))
        self._spin_start(self._lbl_cal_st, T("s3_cal_guardando"))

        def run():
            if not self._serial_lock.acquire(timeout=8):
                self._ui(lambda: self._cal_done(T("puerto_ocupado"), th.WARN))
                return
            try:
                with Provisioner(port) as p:
                    r = p.calibrar(t_off, h_off, s_dry, s_wet)
                if r.get("ok"):
                    self._ui(lambda: self._cal_done(T("s3_cal_ok"), th.SUCCESS))
                else:
                    self._ui(lambda: self._cal_done(f"{r.get('error', '?')}", th.DANGER))
            except (TimeoutError, RuntimeError, OSError) as e:
                self._ui(lambda err=str(e): self._cal_done(f"{err}", th.DANGER))
            finally:
                self._serial_lock.release()

        threading.Thread(target=run, daemon=True).start()

    def _cal_done(self, texto: str, color):
        self._spin_stop()
        self._lbl_cal_st.configure(text=texto, text_color=color)
        self._btn_cal_send.configure(state="normal", text=T("s3_cal_btn"))

    def _do_detect_pins(self):
        port = self._get_port()
        if not port:
            self._lbl_pins_st.configure(text=T("sin_puerto"), text_color=th.DANGER)
            return
        self._btn_pins.configure(state="disabled")
        self._lbl_pins_st.configure(text=T("pins_busy"), text_color=th.TEXT3)

        def run():
            if not self._serial_lock.acquire(timeout=8):
                self._ui(lambda: (self._btn_pins.configure(state="normal"),
                                  self._lbl_pins_st.configure(text=T("puerto_ocupado"), text_color=th.WARN)))
                return
            try:
                with Provisioner(port, timeout=4.0) as p:
                    r = p.detectar_pines(aplicar=True)
            except (TimeoutError, RuntimeError, OSError, ValueError) as e:
                self._ui(lambda err=str(e): self._pins_result(None, err))
                return
            finally:
                self._serial_lock.release()
            self._ui(lambda: self._pins_result(r, None))

        threading.Thread(target=run, daemon=True).start()

    def _pins_result(self, r, err):
        self._btn_pins.configure(state="normal")
        if err is not None or not r or not r.get("ok"):
            self._lbl_pins_st.configure(text=T("pins_err", err=err or "respuesta inválida"),
                                        text_color=th.DANGER)
            return
        msg, tone = self._interpretar_pines(r)
        self._lbl_pins_st.configure(text=msg, text_color=th.TONES[tone][0])

    def _interpretar_pines(self, r: dict) -> tuple[str, str]:
        dht_pin = r.get("dht_pin", -1) or -1
        soil_pin = r.get("soil_pin", -1) or -1
        dht_ok = r.get("dht_state") == "detected" and dht_pin > 0
        soil_st = r.get("soil_state", "not_found")
        if dht_ok:
            self._pin_dht = dht_pin
        if soil_pin > 0 and soil_st in ("detected", "maybe_air"):
            self._pin_soil = soil_pin
        self._aplicar_pines_ui()
        self._milestone("pins", dht_ok and soil_st == "detected")

        if dht_ok and soil_st == "detected":
            return T("pins_ok", dht=dht_pin, soil=soil_pin), "success"
        if not dht_ok:
            return T("pins_dht_no"), "error"
        if soil_st == "maybe_air":
            return T("pins_soil_air", soil=soil_pin), "warn"
        return T("pins_soil_no"), "error"
