import json
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

import customtkinter as ctk

from core.config_manager import guardar as cfg_guardar
from core.lang import T
from core.network import api_base_local
from ui import theme as th
from ui.icons import blank, icon
from ui.widgets import Banner, entry, eyebrow, ghost_button, primary_button, secondary_button

_CHECKLIST = (("port", "chk_port"), ("flash", "chk_flash"), ("pins", "chk_pins"),
              ("wifi", "chk_wifi"), ("sensors", "chk_sensors"), ("cloud", "chk_cloud"))


class ActivateStep:

    def _build_activate(self, f):
        self._api_inseguro = False
        self._header(f, 4, "s5_header", "s5_sub")
        cols = ctk.CTkFrame(f, fg_color="transparent")
        cols.pack(fill="both", expand=True, pady=(0, 24))
        cols.grid_columnconfigure(0, weight=2, uniform="c")
        cols.grid_columnconfigure(1, weight=3, uniform="c")

        self._build_checklist(cols).grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        form_card = ctk.CTkFrame(cols, fg_color=th.CARD, corner_radius=16)
        form_card.grid(row=0, column=1, sticky="nsew")
        self._build_login(form_card)
        self._build_success(form_card)

    def _build_checklist(self, parent):
        box = ctk.CTkFrame(parent, fg_color=th.CARD, corner_radius=16)
        self._reg(ctk.CTkLabel(box, font=self.fonts.headline, text_color=th.TEXT, anchor="w"),
                  "chk_title").pack(fill="x", padx=22, pady=(20, 2))
        self._lbl_chk_progress = ctk.CTkLabel(box, text="", font=self.fonts.small,
                                              text_color=th.TEXT3, anchor="w")
        self._lbl_chk_progress.pack(fill="x", padx=22)
        self._chk_bar = ctk.CTkProgressBar(box, height=6, corner_radius=3, fg_color=th.SEP,
                                           progress_color=th.SUCCESS)
        self._chk_bar.set(0)
        self._chk_bar.pack(fill="x", padx=22, pady=(10, 12))
        self._chk_items = {}
        for key, texto in _CHECKLIST:
            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x", padx=22, pady=5)
            badge = ctk.CTkLabel(row, text="", width=26, height=26, corner_radius=13, fg_color=th.SEP,
                                 image=blank(15))
            badge.pack(side="left")
            label = self._reg(ctk.CTkLabel(row, font=self.fonts.body, text_color=th.TEXT3, anchor="w"), texto)
            label.pack(side="left", padx=(12, 0), fill="x", expand=True)
            self._chk_items[key] = (badge, label)
        ctk.CTkFrame(box, height=12, fg_color="transparent").pack()
        self._refresh_checklist()
        return box

    def _refresh_checklist(self):
        hechos = sum(self._milestones.values())
        total = len(self._milestones)
        for key, (badge, label) in self._chk_items.items():
            ok = self._milestones[key]
            badge.configure(image=icon("check", 15, th.ON_ACCENT) if ok else blank(15),
                            fg_color=th.SUCCESS if ok else th.SEP)
            label.configure(text_color=th.TEXT if ok else th.TEXT3)
        self._lbl_chk_progress.configure(text=T("chk_progress", n=hechos, total=total))
        self._chk_target = hechos / total
        inicio = self._chk_bar.get()
        th.animate(self, 360, lambda e: self._chk_bar.set(inicio + (self._chk_target - inicio) * e))

    def _build_login(self, parent):
        self._step5_form = ctk.CTkFrame(parent, fg_color="transparent")
        self._step5_form.pack(fill="both", expand=True, padx=2, pady=2)
        form = self._step5_form

        self._reg(eyebrow(form, self.fonts), "s5_srv_detect").pack(fill="x", padx=24, pady=(22, 6))
        self._lbl_api_url = ctk.CTkLabel(form, text="—", font=self.fonts.mono, text_color=th.TEXT2,
                                         fg_color=th.INPUT, corner_radius=10, height=40, anchor="w",
                                         compound="left")
        self._lbl_api_url.pack(fill="x", padx=24)

        for key, var, ph, show in (("s5_email", self._av_email, "s5_ph_email", ""),
                                   ("s5_pass", self._av_pass, "s5_pass", "●")):
            self._reg(eyebrow(form, self.fonts), key).pack(fill="x", padx=24, pady=(18, 6))
            entry(form, self.fonts, var, T(ph), show=show).pack(fill="x", padx=24)

        self._btn_web_adv = ghost_button(form, "", self._toggle_web_adv, self.fonts,
                                         anchor="w", text_color=th.TEXT3)
        self._btn_web_adv.pack(anchor="w", padx=18, pady=(12, 0))
        self._web_adv_panel = ctk.CTkFrame(form, fg_color="transparent")
        self._web_adv_visible = False
        entry(self._web_adv_panel, self.fonts, self._av_web_url, T("s5_ph_web"),
              font=self.fonts.mono, height=42).pack(fill="x", padx=24, pady=(4, 4))

        self._lbl_activate_st = ctk.CTkLabel(form, text="", font=self.fonts.small, text_color=th.TEXT3,
                                             anchor="w", justify="left", wraplength=460)
        self._lbl_activate_st.pack(fill="x", padx=24, pady=(10, 6))
        self._btn_activate = primary_button(form, T("s5_btn_conectar"), self._do_activate, self.fonts,
                                            icon_name="cloud-upload")
        self._btn_activate.pack(fill="x", padx=24, pady=(0, 24))
        self._lang_refresh_activate()

    def _build_success(self, parent):
        self._step5_success = ctk.CTkFrame(parent, fg_color="transparent")
        box = self._step5_success
        self._success_icon = ctk.CTkLabel(box, text="", width=88, height=88, corner_radius=44,
                                          fg_color=th.SUCCESS_BG, image=icon("circle-check-big", 44, th.SUCCESS))
        self._success_icon.pack(pady=(44, 0))
        self._reg(ctk.CTkLabel(box, font=self.fonts.title, text_color=th.TEXT), "s5_success_ttl").pack(pady=(16, 2))
        self._lbl_success_user = ctk.CTkLabel(box, text="", font=self.fonts.body, text_color=th.TEXT3)
        self._lbl_success_user.pack()
        aviso = Banner(box, self.fonts, "success")
        aviso.pack(fill="x", padx=32, pady=(22, 0))
        self._reg(aviso.label, "s5_success_inf")
        self._reg(primary_button(box, "", self._reopen_platform, self.fonts, icon_name="arrow-right",
                                 compound="right"),
                  "s5_btn_reabrir").pack(fill="x", padx=32, pady=(18, 6))
        self._reg(secondary_button(box, "", self._reset_activate_form, self.fonts,
                                   text_color=th.TEXT3), "s5_btn_volver").pack(fill="x", padx=32, pady=(0, 24))

    def _lang_refresh_activate(self):
        self._btn_web_adv.configure(text=f"  {T('s5_web_url')}", image=icon(
            "chevron-down" if self._web_adv_visible else "chevron-right", 16, th.TEXT3))
        if self._btn_activate.cget("state") == "normal":
            self._btn_activate.configure(text=T("s5_btn_conectar"))

    def _toggle_web_adv(self):
        self._web_adv_visible = not self._web_adv_visible
        if self._web_adv_visible:
            self._web_adv_panel.pack(fill="x", after=self._btn_web_adv)
        else:
            self._web_adv_panel.pack_forget()
        self._lang_refresh_activate()

    def _prepare_activate(self):
        api_base = api_base_local(self._server_url.get().strip())
        inseguro = api_base.startswith("http://")
        self._api_inseguro = inseguro
        color = th.WARN if inseguro else th.SUCCESS
        self._lbl_api_url.configure(text=f"  {api_base}", text_color=color,
                                    image=icon("lock-open" if inseguro else "lock", 16, color))
        self._reset_activate_form()

    def _reset_activate_form(self):
        self._step5_success.pack_forget()
        aviso = T("s5_http_warn") if self._api_inseguro else ""
        self._lbl_activate_st.configure(text=aviso, text_color=th.WARN)
        self._btn_activate.configure(state="normal", text=T("s5_btn_conectar"))
        self._step5_form.pack(fill="both", expand=True, padx=2, pady=2)

    def _reopen_platform(self):
        if self._av_last_url:
            webbrowser.open(self._av_last_url)

    def _do_activate(self):
        email = self._av_email.get().strip()
        password = self._av_pass.get()
        web_url = self._av_web_url.get().strip().rstrip("/")
        if not email or not password:
            self._lbl_activate_st.configure(text=T("s5_sin_creds"), text_color=th.DANGER)
            return
        api_base = api_base_local(self._server_url.get().strip())
        self._btn_activate.configure(state="disabled", text=T("s5_conectando"))
        self._spin_start(self._lbl_activate_st, T("s5_logging_in"))
        threading.Thread(target=self._login_worker, args=(api_base, email, password, web_url),
                         daemon=True).start()

    def _login_worker(self, api_base: str, email: str, password: str, web_url: str):
        try:
            req = urllib.request.Request(
                f"{api_base}/api/auth/login",
                data=json.dumps({"username": email, "password": password}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
            datos = body.get("data") or {}
            token = (body.get("token") or body.get("access_token")
                     or datos.get("token") or datos.get("access_token"))
            if not token:
                raise ValueError(T("s5_no_token"))
            nombre = (datos.get("user") or {}).get("nombre") or email
            cfg_guardar(av_email=email, av_web_url=web_url)
            self._av_last_url = f"{web_url}/auto-login#token={urllib.parse.quote(token)}&redirect=dispositivos"
            webbrowser.open(self._av_last_url)
            self._ui(lambda: self._login_ok(nombre))
        except urllib.error.HTTPError as e:
            self._ui(lambda m=T("s5_http_err", code=e.code): self._login_err(m))
        except (urllib.error.URLError, OSError, ValueError) as e:
            self._ui(lambda m=f"✗  {e}": self._login_err(m))

    def _login_ok(self, nombre: str):
        self._spin_stop()
        self._av_pass.set("")
        self._step5_form.pack_forget()
        self._lbl_success_user.configure(text=T("s5_bienvenido", nombre=nombre))
        self._step5_success.pack(fill="both", expand=True)
        self._milestone("cloud")
        self._toast("success", T("toast_login_t"), T("s5_bienvenido", nombre=nombre))

    def _login_err(self, msg: str):
        self._spin_stop()
        self._lbl_activate_st.configure(text=msg, text_color=th.DANGER)
        self._btn_activate.configure(state="normal", text=T("s5_reintento"))
