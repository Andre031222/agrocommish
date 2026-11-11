// HTML del portal de configuración (captive portal)
// En un .h separado: el preprocesador de sketches de Arduino (ctags)
// malinterpreta el JavaScript del raw string y genera prototipos inválidos.
#pragma once

const char* SETUP_HTML = R"=====(
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AgroVision — Configurar dispositivo</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
       background:#f0fdf4;min-height:100vh;display:flex;align-items:center;
       justify-content:center;padding:16px}
  .card{background:#fff;border-radius:20px;padding:28px 24px;
        max-width:420px;width:100%;box-shadow:0 8px 32px rgba(0,0,0,.1)}
  .logo{display:flex;align-items:center;gap:10px;margin-bottom:24px}
  .logo-icon{width:40px;height:40px;background:#10b981;border-radius:12px;
             display:flex;align-items:center;justify-content:center}
  .logo-icon svg{width:22px;height:22px;stroke:#fff;fill:none;stroke-width:2}
  .logo-text h1{font-size:18px;font-weight:900;color:#111;line-height:1}
  .logo-text p{font-size:11px;color:#10b981;font-weight:600;margin-top:2px}
  .badge{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;
         background:#fef3c7;color:#92400e;border-radius:20px;font-size:12px;
         font-weight:700;margin-bottom:20px}
  .badge-dot{width:8px;height:8px;background:#f59e0b;border-radius:50%;
             animation:pulse 1s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
  h2{font-size:15px;font-weight:700;color:#111;margin-bottom:6px}
  .sub{font-size:13px;color:#6b7280;margin-bottom:20px;line-height:1.5}
  label{display:block;font-size:12px;font-weight:600;color:#374151;margin-bottom:6px}
  select,input{width:100%;padding:11px 14px;border:1.5px solid #e5e7eb;
               border-radius:12px;font-size:14px;color:#111;
               background:#fff;outline:none;transition:.2s}
  select:focus,input:focus{border-color:#10b981;box-shadow:0 0 0 3px rgba(16,185,129,.15)}
  .field{margin-bottom:16px}
  .device-box{background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;
              padding:12px 14px;margin-bottom:20px}
  .device-box .label{font-size:11px;color:#9ca3af;font-weight:600;
                      text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}
  .device-box .value{font-family:monospace;font-size:14px;font-weight:700;color:#111}
  .btn{width:100%;padding:14px;background:#10b981;color:#fff;border:none;
       border-radius:12px;font-size:15px;font-weight:700;cursor:pointer;
       transition:.2s;display:flex;align-items:center;justify-content:center;gap:8px}
  .btn:hover{background:#059669}
  .btn:disabled{background:#9ca3af;cursor:not-allowed}
  .btn svg{width:18px;height:18px;stroke:#fff;fill:none;stroke-width:2.5}
  .spinner{width:18px;height:18px;border:2.5px solid rgba(255,255,255,.4);
           border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite;
           display:none}
  @keyframes spin{to{transform:rotate(360deg)}}
  .msg{padding:10px 14px;border-radius:10px;font-size:13px;font-weight:600;
       margin-top:12px;display:none}
  .msg.ok{background:#d1fae5;color:#065f46}
  .msg.err{background:#fee2e2;color:#991b1b}
  .steps{margin-top:24px;padding-top:20px;border-top:1px solid #f3f4f6}
  .steps h3{font-size:12px;font-weight:700;color:#374151;margin-bottom:10px;
            text-transform:uppercase;letter-spacing:.06em}
  .step{display:flex;gap:10px;margin-bottom:8px;align-items:flex-start}
  .step-num{width:20px;height:20px;background:#10b981;color:#fff;border-radius:50%;
            font-size:10px;font-weight:700;display:flex;align-items:center;
            justify-content:center;flex-shrink:0;margin-top:1px}
  .step p{font-size:12px;color:#6b7280;line-height:1.5}
  .adv{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;
       padding:10px 12px;margin-bottom:16px}
  .adv-title{font-size:11px;font-weight:700;color:#065f46;margin-bottom:4px}
  .adv p{font-size:12px;color:#6b7280}
  details{margin-bottom:16px}
  summary{font-size:12px;font-weight:600;color:#6b7280;cursor:pointer;
          padding:8px 0;list-style:none}
  summary::before{content:'▶ ';font-size:10px}
  details[open] summary::before{content:'▼ '}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <div class="logo-icon">
      <svg viewBox="0 0 24 24"><path d="M11 20A7 7 0 0 1 4 13c0-3.87 3.13-7 7-7 3.87 0 7 3.13 7 7a7 7 0 0 1-7 7z"/><path d="M11 20c0-4-2-7-7-8" stroke-linecap="round"/></svg>
    </div>
    <div class="logo-text">
      <h1>AgroVision</h1>
      <p>Configuración IoT</p>
    </div>
  </div>

  <div class="badge">
    <span class="badge-dot"></span>
    Modo configuración activo
  </div>

  <h2>Conectar a tu red WiFi</h2>
  <p class="sub">Selecciona tu red WiFi e ingresa la contraseña para que el dispositivo pueda enviar datos al servidor.</p>

  <div class="device-box">
    <div class="label">ID del dispositivo</div>
    <div class="value" id="devId">Cargando...</div>
  </div>

  <form id="wifiForm" onsubmit="guardar(event)">
    <div class="field">
      <label>Red WiFi disponible</label>
      <select id="ssid" required>
        <option value="">Escaneando redes...</option>
      </select>
    </div>

    <div class="field">
      <label>Contraseña WiFi</label>
      <input type="password" id="pass" placeholder="Contraseña de la red" autocomplete="off">
    </div>

    <details>
      <summary>Configuración avanzada del servidor</summary>
      <div style="padding-top:10px">
        <div class="field">
          <label>URL del servidor AgroVision</label>
          <input type="text" id="serverUrl" placeholder="http://192.168.x.x:5000/api/sensores/lectura">
        </div>
        <div class="adv">
          <div class="adv-title">¿Dónde encuentro la URL?</div>
          <p>Es la IP de la computadora donde corre el backend + el puerto 5000. Ejemplo: <code>http://192.168.1.100:5000/api/sensores/lectura</code></p>
        </div>
      </div>
    </details>

    <button class="btn" type="submit" id="saveBtn">
      <svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
      <span id="btnText">Guardar y conectar</span>
      <span class="spinner" id="spin"></span>
    </button>
  </form>

  <div class="msg" id="msg"></div>

  <div class="steps">
    <h3>¿Qué pasa después?</h3>
    <div class="step">
      <div class="step-num">1</div>
      <p>El dispositivo guarda la configuración y se conecta a tu red WiFi</p>
    </div>
    <div class="step">
      <div class="step-num">2</div>
      <p>Empieza a enviar lecturas de temperatura y humedad al servidor</p>
    </div>
    <div class="step">
      <div class="step-num">3</div>
      <p>Entra al panel AgroVision → <strong>Mis Dispositivos</strong> → aparecerá como pendiente</p>
    </div>
    <div class="step">
      <div class="step-num">4</div>
      <p>Haz clic en <strong>Vincular a cultivo</strong> para asociarlo a tu parcela</p>
    </div>
  </div>
</div>

<script>
  // Cargar redes WiFi y datos del dispositivo
  window.addEventListener('load', function() {
    fetch('/scan').then(r => r.json()).then(d => {
      const sel = document.getElementById('ssid');
      sel.innerHTML = '';
      if (!d.networks || !d.networks.length) {
        sel.innerHTML = '<option value="">No se encontraron redes</option>';
        return;
      }
      d.networks.forEach(n => {
        const opt = document.createElement('option');
        opt.value = n.ssid;
        opt.textContent = n.ssid + '  (' + n.rssi + ' dBm)' + (n.secure ? ' 🔒' : ' 🔓');
        sel.appendChild(opt);
      });
    }).catch(() => {
      document.getElementById('ssid').innerHTML = '<option value="">Error al escanear</option>';
    });

    fetch('/info').then(r => r.json()).then(d => {
      document.getElementById('devId').textContent = d.device_id || '—';
      if (d.server_url) document.getElementById('serverUrl').value = d.server_url;
    }).catch(() => {});
  });

  function mostrarMsg(txt, tipo) {
    const el = document.getElementById('msg');
    el.textContent = txt;
    el.className = 'msg ' + tipo;
    el.style.display = 'block';
  }

  function guardar(e) {
    e.preventDefault();
    const ssid = document.getElementById('ssid').value;
    const pass = document.getElementById('pass').value;
    const srv  = document.getElementById('serverUrl').value;

    if (!ssid) { mostrarMsg('Selecciona una red WiFi', 'err'); return; }

    const btn = document.getElementById('saveBtn');
    document.getElementById('btnText').textContent = 'Guardando...';
    document.getElementById('spin').style.display = 'block';
    btn.disabled = true;

    fetch('/save', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ ssid, pass, server_url: srv })
    })
    .then(r => r.json())
    .then(d => {
      if (d.success) {
        mostrarMsg('✅ Configuración guardada. El dispositivo se reiniciará y conectará a "' + ssid + '"', 'ok');
        document.getElementById('btnText').textContent = 'Listo';
      } else {
        mostrarMsg('Error: ' + (d.message || 'No se pudo guardar'), 'err');
        btn.disabled = false;
      }
    })
    .catch(() => {
      mostrarMsg('Error de conexión. Intenta de nuevo.', 'err');
      btn.disabled = false;
      document.getElementById('btnText').textContent = 'Guardar y conectar';
      document.getElementById('spin').style.display = 'none';
    });
  }
</script>
</body>
</html>
)=====";
