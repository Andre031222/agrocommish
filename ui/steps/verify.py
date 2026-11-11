import csv
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.lang import T
from core.network import api_base_local, ip_local, puerto_abierto
from core.provisioner import Provisioner, validar_lecturas
from core.qr_generator import generar_qr, guardar_qr
from ui import theme as th
from ui.icons import blank, icon
from ui.widgets import TONE_ICONS, card, eyebrow, primary_button, secondary_button, separator

_TONOS = {"ok": "success", "warn": "warn", "error": "error"}


class VerifyStep:

    def _build_verify(self, f):
        self._header(f, 3, "s4_header", "s4_sub")
        c = card(f)

        head = ctk.CTkFrame(c, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=(18, 10))
        for key, ancho in (("s4_col_sensor", 360), ("s4_col_val", 180), ("s4_col_st", 0)):
            self._reg(eyebrow(head, self.fonts, width=ancho), key).pack(side="left")

        self._sensor_rows = []
        for nombre in T("s4_sensors"):
            separator(c, padx=24)
            row = ctk.CTkFrame(c, fg_color="transparent", height=52)
            row.pack(fill="x", padx=24)
            row.pack_propagate(False)
            n = ctk.CTkLabel(row, text=nombre, width=360, font=self.fonts.body, text_color=th.TEXT, anchor="w")
            n.pack(side="left")
            v = ctk.CTkLabel(row, text="—", width=180, font=self.fonts.mono_l, text_color=th.TEXT3, anchor="w")
            v.pack(side="left")
            e = ctk.CTkLabel(row, text="—", font=self.fonts.small, text_color=th.TEXT3,
                             corner_radius=10, height=30, anchor="w", compound="left")
            e.pack(side="left", padx=(0, 8))
            self._sensor_rows.append({"n": n, "v": v, "e": e})

        separator(c, padx=24)
        self._lbl_test_st = ctk.CTkLabel(c, text=T("s4_hint_test"), font=self.fonts.small,
                                         text_color=th.TEXT3, anchor="w", justify="left", wraplength=760)
        self._lbl_test_st.pack(fill="x", padx=24, pady=(12, 8))
        botones = ctk.CTkFrame(c, fg_color="transparent")
        botones.pack(fill="x", padx=24, pady=(0, 22))
        self._btn_test = secondary_button(botones, T("s4_btn_test"), self._do_test, self.fonts,
                                          icon_name="activity", height=46, text_color=th.INFO,
                                          font=self.fonts.body_b)
        self._btn_test.pack(side="left", fill="x", expand=True)
        self._btn_export = secondary_button(botones, T("s4_btn_export"), self._do_export_datos,
                                            self.fonts, icon_name="download", height=46, width=210)
        self._btn_export.pack(side="left", padx=(10, 0))
        self._i18n.append((self._btn_export, "s4_btn_export"))

        bottom = ctk.CTkFrame(f, fg_color="transparent")
        bottom.pack(fill="x", pady=(0, 24))
        qr = ctk.CTkFrame(bottom, fg_color=th.CARD, corner_radius=16)
        qr.pack(side="left", anchor="n")
        self._lbl_qr = ctk.CTkLabel(qr, text=T("s4_qr_ph"), font=self.fonts.small, text_color=th.TEXT3,
                                    width=164, height=164, fg_color=("#FFFFFF", "#FFFFFF"), corner_radius=12)
        self._lbl_qr.pack(padx=14, pady=(14, 8))
        self._btn_save_qr = secondary_button(qr, T("s4_btn_save_qr"), self._save_qr, self.fonts,
                                             icon_name="qr-code", height=36, width=176, font=self.fonts.small,
                                             text_color=th.INFO, state="disabled")
        self._btn_save_qr.pack(padx=14, pady=(0, 14))
        self._i18n.append((self._btn_save_qr, "s4_btn_save_qr"))

        info = ctk.CTkFrame(bottom, fg_color=th.CARD, corner_radius=16)
        info.pack(side="left", fill="both", expand=True, padx=(14, 0))
        self._lbl_did = ctk.CTkLabel(info, text="—", font=self.fonts.mono_l, text_color=th.ACCENT, anchor="w")
        self._lbl_did.pack(fill="x", padx=22, pady=(20, 6))
        self._lbl_summary = ctk.CTkLabel(info, text="", font=self.fonts.mono, text_color=th.TEXT2,
                                         justify="left", anchor="w")
        self._lbl_summary.pack(fill="x", padx=22)
        self._btn_done = primary_button(info, T("s4_btn_listo"), self._mark_done, self.fonts,
                                        tone=th.SUCCESS, hover=th.ACCENT_DK, icon_name="check")
        self._btn_done.pack(fill="x", padx=22, pady=(18, 8))
        self._lbl_result = ctk.CTkLabel(info, text="", font=self.fonts.small, text_color=th.SUCCESS, anchor="w")
        self._lbl_result.pack(fill="x", padx=22, pady=(0, 16))

    def _lang_refresh_verify(self):
        if self._btn_test.cget("state") == "normal":
            self._btn_test.configure(text=T("s4_btn_test"))
        self._btn_done.configure(text=T("s4_listo_done") if self._device_done else T("s4_btn_listo"))
        if not self._device_id:
            self._lbl_qr.configure(text=T("s4_qr_ph"))
        self._aplicar_pines_ui()
        self._update_summary()

    def _reset_verify(self):
        self._lbl_result.configure(text="")
        self._btn_done.configure(state="normal", text=T("s4_btn_listo"))
        self._lbl_qr.configure(image="", text=T("s4_qr_ph"))
        self._btn_save_qr.configure(state="disabled")
        self._clear_sensor_rows()
        self._aplicar_pines_ui()

    def _clear_sensor_rows(self):
        for fila in self._sensor_rows:
            fila["v"].configure(text="—", text_color=th.TEXT3)
            fila["e"].configure(text="—", text_color=th.TEXT3, fg_color="transparent", image=blank(16))

    def _update_summary(self):
        self._lbl_summary.configure(text=(f"{T('s4_wifi_lbl'):<10}{self._ssid.get()}\n"
                                          f"{T('s4_server_lbl'):<10}{self._server_url.get()}\n"
                                          f"{T('s4_port_lbl'):<10}{self._get_port()}"))

    def _aplicar_pines_ui(self):
        pines = (self._pin_dht, self._pin_dht, self._pin_soil)
        for fila, nombre, pin in zip(self._sensor_rows, T("s4_sensors"), pines):
            fila["n"].configure(text=nombre if pin is None else f"{nombre}  ·  GPIO {pin}")

    def _prepare_verify(self):
        self._lbl_did.configure(text=self._device_id or "—")
        self._update_summary()
        self._lbl_test_st.configure(text=T("s4_hint_test"), text_color=th.TEXT3)
        self._aplicar_pines_ui()
        if self._device_id and self._device_id != "DESCONOCIDO":
            self._render_qr(self._device_id)

    def _do_test(self):
        port = self._get_port()
        if not port:
            self._lbl_test_st.configure(text=T("sin_puerto"), text_color=th.DANGER)
            return
        self._btn_test.configure(state="disabled", text=T("s4_leyendo"))
        threading.Thread(target=self._test_worker, args=(port,), daemon=True).start()

    def _test_worker(self, port: str):
        if self._serial_lock.acquire(blocking=False):
            try:
                with Provisioner(port, timeout=2.0) as p:
                    try:
                        data = p.leer_sensores(timeout=3.0)
                    except (TimeoutError, RuntimeError, ValueError):
                        self._ui(lambda: self._lbl_test_st.configure(text=T("s4_serial_listen"),
                                                                     text_color=th.TEXT3))
                        data = p.escuchar_datos(max_espera=25.0)
                results = validar_lecturas(data)
                self._ui(lambda: self._show_sensor_results(results))
                return
            except (TimeoutError, RuntimeError, OSError, ValueError):
                pass
            finally:
                self._serial_lock.release()
        self._test_via_server()

    def _test_via_server(self):
        server = self._server_url.get().strip()
        did = self._device_id or ""
        api_base = api_base_local(server) if server else None
        if not api_base or not did or did == "DESCONOCIDO":
            self._test_failed(T("s4_no_did"))
            return
        url = urllib.parse.urlparse(api_base)
        host, puerto = url.hostname, url.port or (443 if url.scheme == "https" else 80)
        if not puerto_abierto(host, puerto):
            self._test_failed(T("s4_srv_unreachable", base=f"{host}:{puerto}", ip=ip_local()))
            return
        consulta = f"{api_base}/api/sensores/lecturas-recientes?esp32_id={urllib.parse.quote(did)}"
        for restante in range(35, 0, -1):
            self._ui(lambda s=restante: self._lbl_test_st.configure(text=T("s4_waiting_srv", s=s),
                                                                    text_color=th.TEXT3))
            try:
                with urllib.request.urlopen(consulta, timeout=4) as resp:
                    lecturas = json.loads(resp.read().decode()).get("lecturas") or []
                if lecturas:
                    results = validar_lecturas(_lecturas_a_dict(lecturas))
                    self._ui(lambda: self._show_sensor_results(results))
                    return
            except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
                pass
            time.sleep(1)
        self._test_failed(T("s4_no_data"))

    def _test_failed(self, msg: str):
        self._ui(lambda: (self._lbl_test_st.configure(text=msg, text_color=th.DANGER),
                          self._btn_test.configure(state="normal", text=T("s4_btn_test"))))

    def _show_sensor_results(self, results: list[dict]):
        errores = sum(r["estado"] == "error" for r in results)
        avisos = sum(r["estado"] == "warn" for r in results)
        for i, r in enumerate(results):
            tono = _TONOS.get(r["estado"], "info")
            fg, bg = th.TONES[tono]
            valor = f"{r['valor']:.1f} {r['unidad']}" if r["valor"] is not None else "—"
            self.after(110 * i, lambda fila=self._sensor_rows[i], v=valor, fg=fg, bg=bg, r=r, t=tono: (
                fila["v"].configure(text=v, text_color=fg),
                fila["e"].configure(text=f"  {r['mensaje']}   ", text_color=fg, fg_color=bg,
                                    image=icon(TONE_ICONS[t], 16, fg))))

        self._btn_test.configure(state="normal", text=T("s4_btn_test"))
        self._log_write("TEST_ERROR" if errores else "TEST_WARN" if avisos else "TEST_OK")
        dht_caido = any("NaN" in r["mensaje"] for r in results[:2] if r["estado"] == "error")
        if dht_caido:
            texto, tono = T("s4_dht_first"), "error"
        elif errores:
            texto, tono = T("s4_test_errs", n=errores), "error"
        elif avisos:
            texto, tono = T("s4_test_warns", n=avisos), "warn"
        else:
            texto, tono = T("s4_test_ok"), "success"
        self._lbl_test_st.configure(text=texto, text_color=th.TONES[tono][0])
        self._toast(tono, T("toast_test_err_t") if tono == "error" else T("toast_test_t"), texto)
        self._milestone("sensors", not errores)

    def _do_export_datos(self):
        port = self._get_port()
        if not port:
            self._lbl_test_st.configure(text=T("sin_puerto"), text_color=th.DANGER)
            return
        did = self._device_id or "device"
        path = filedialog.asksaveasfilename(
            title=T("s4_export_title"), defaultextension=".csv",
            initialfile=f"datos_{did}_{datetime.now():%Y%m%d_%H%M%S}.csv",
            filetypes=[("CSV", "*.csv"), ("*", "*.*")])
        if not path:
            return
        self._btn_export.configure(state="disabled")
        self._lbl_test_st.configure(text=T("s4_export_busy", n=0), text_color=th.TEXT3)
        threading.Thread(target=self._export_worker, args=(port, path), daemon=True).start()

    def _export_worker(self, port: str, path: str):
        if not self._serial_lock.acquire(timeout=8):
            self._ui(lambda: (self._btn_export.configure(state="normal"),
                              self._lbl_test_st.configure(text=T("puerto_ocupado"), text_color=th.WARN)))
            return
        try:
            def progreso(n, _fila):
                self._ui(lambda: self._lbl_test_st.configure(text=T("s4_export_busy", n=n),
                                                             text_color=th.TEXT3))
            with Provisioner(port, timeout=1.0) as p:
                filas = p.capturar_telemetria(65.0, on_lectura=progreso)
            if not filas:
                raise TimeoutError(T("s4_no_data"))
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=Provisioner.CAMPOS_TELEMETRIA)
                writer.writeheader()
                writer.writerows(filas)
            self._ui(lambda: self._export_ok(len(filas), path))
        except (TimeoutError, RuntimeError, OSError) as e:
            self._ui(lambda err=str(e): (self._btn_export.configure(state="normal"),
                                         self._lbl_test_st.configure(text=f"{err}", text_color=th.DANGER)))
        finally:
            self._serial_lock.release()

    def _export_ok(self, n: int, path: str):
        self._btn_export.configure(state="normal")
        texto = T("s4_export_ok", n=n, name=Path(path).name)
        self._lbl_test_st.configure(text=texto, text_color=th.SUCCESS)
        self._toast("success", T("toast_export_t"), texto)

    def _render_qr(self, did: str):
        try:
            pil = generar_qr(did, box_size=8)
            img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(164, 164))
            self._lbl_qr.configure(image=img, text="")
            self._lbl_qr.qr_image = img
            self._btn_save_qr.configure(state="normal")
        except (OSError, ValueError):
            self._lbl_qr.configure(text=T("s4_qr_err"), text_color=th.DANGER)

    def _save_qr(self):
        did = self._device_id or "device"
        path = filedialog.asksaveasfilename(title=T("s4_qr_title"), defaultextension=".png",
                                            initialfile=f"QR_{did}.png",
                                            filetypes=[("PNG", "*.png"), ("*", "*.*")])
        if not path:
            return
        try:
            guardar_qr(did, path, box_size=10)
            self._lbl_result.configure(text=T("s4_qr_saved", name=Path(path).name), text_color=th.INFO)
        except OSError as e:
            self._lbl_result.configure(text=f"{e}", text_color=th.DANGER)

    def _mark_done(self):
        self._batch_count += 1
        self._device_done = True
        self._log_write("LISTO")
        self._save_cfg()
        self._lbl_batch.configure(text=str(self._batch_count))
        self._btn_done.configure(state="disabled", text=T("s4_listo_done"))
        self._lbl_result.configure(text=T("s4_batch_reg", n=self._batch_count), text_color=th.SUCCESS)
        self._btn_new_dev.configure(state="normal")
        self._toast("success", T("toast_listo_t"), T("s4_batch_reg", n=self._batch_count))
        self.after(700, lambda: self._show_step(4))

    def _auto_test(self):
        if self.winfo_exists() and self._paso == 3 and self._btn_test.cget("state") == "normal":
            self._do_test()


def _lecturas_a_dict(lecturas: list) -> dict:
    data = {}
    for lec in lecturas:
        tipo, valor = lec.get("tipo_lectura", ""), lec.get("valor")
        if "temperatura" in tipo:
            data["temperatura"] = valor
        elif "humedad_a" in tipo:
            data["humedad_aire"] = valor
        elif "humedad_s" in tipo:
            data["humedad_suelo"] = valor
    return data
