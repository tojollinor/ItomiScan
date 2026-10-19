"""Dependency-free ItomiScan administration pages.

All untrusted values are escaped. Only system metrics use a tiny same-origin
script; forms and authentication do not require JavaScript.
"""
from html import escape
import json

from itomiscan import branding


def e(value):
    return escape(str(value), quote=True)


def logo_svg(size=44):
    """Use the same icon geometry and palette as the physical scanner."""
    polygon = " ".join(f"{x},{y}" for x, y in
                       zip(branding.DOCUMENT[::2], branding.DOCUMENT[1::2]))
    corners = "".join(
        f'<path d="M {x} {y+dy} L {x} {y} L {x+dx} {y}" '
        f'stroke="{branding.CYAN}" stroke-width="4" fill="none"/>'
        for x, y, dx, dy in branding.CORNERS
    )
    return (f'<svg class="brand-icon" width="{int(size)}" height="{int(size)}" '
            'viewBox="0 0 72 72" aria-hidden="true" focusable="false">'
            f'<rect x="1" y="1" width="70" height="70" fill="{branding.BLUE}"/>'
            f'<polygon points="{polygon}" fill="#fff"/>'
            f'<rect x="{branding.LINE_LEFT}" y="{branding.LINE_START}" '
            f'width="{branding.LINE_RIGHT-branding.LINE_LEFT}" '
            f'height="{branding.LINE_HEIGHT}" fill="{branding.CYAN}"/>'
            + corners + '</svg>')


# Only static same-origin asset. No third-party libraries or sensitive data.
STATUS_JS = """(() => {
  const elements = document.querySelectorAll('[data-status-key]');
  const charts = document.querySelectorAll('[data-metric-chart]');
  if (!elements.length && !charts.length) return;
  const histories = new Map();
  let busy = false;
  function draw(chart, value) {
    const key = chart.dataset.metricChart;
    let list = histories.get(key);
    if (!list) { list = []; histories.set(key, list); }
    list.push(Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : null);
    if (list.length > 300) list.shift();
    const points = [];
    for (let i = 0; i < list.length; i++) {
      if (list[i] === null) continue;
      points.push((10 + i * 300 / 299).toFixed(2) + ',' +
                  (110 - list[i]).toFixed(2));
    }
    const line = chart.querySelector('polyline');
    if (line) line.setAttribute('points', points.join(' '));
  }
  async function refresh() {
    if (busy || document.hidden) return;
    busy = true;
    try {
      const response = await fetch('/api/metrics',
          {cache:'no-store', credentials:'same-origin'});
      if (!response.ok) return;
      const data = await response.json();
      elements.forEach(element => {
        const key = element.getAttribute('data-status-key');
        if (Object.prototype.hasOwnProperty.call(data, key)) {
          element.textContent = String(data[key]);
        }
      });
      const memory = document.querySelector('[data-ram-progress]');
      const fill = document.querySelector('[data-ram-fill]');
      const detail = document.querySelector('[data-ram-detail]');
      const percent = Number(data.ram_percent);
      if (memory && fill && data.ram_percent != null && Number.isFinite(percent)) {
        const bounded = Math.max(0, Math.min(100, percent));
        memory.setAttribute('aria-valuenow', String(bounded));
        fill.style.width = bounded + '%';
        if (detail) detail.textContent = data.ram_used + ' von ' + data.ram_total +
            ' belegt · ' + data.ram_free + ' verfügbar (' + bounded.toFixed(1) + ' %)';
      }
      charts.forEach(chart => {
        const key = chart.dataset.metricChart;
        const value = key === 'cpu' ? parseFloat(data.cpu) :
                      (data.ram_percent == null ? NaN : Number(data.ram_percent));
        draw(chart, value);
        const label = chart.parentElement.querySelector('[data-chart-value]');
        if (label) label.textContent = Number.isFinite(value) ?
            (key === 'ram' ? data.ram_used + ' / ' + data.ram_total + ' · ' : '') +
            value.toFixed(1) + ' %' : 'Nicht verfügbar';
      });
    } catch (_error) { /* Retain previous samples if temporarily offline. */ }
    finally { busy = false; }
  }
  refresh();
  const timer = window.setInterval(refresh, 1000);
  window.addEventListener('pagehide', () => clearInterval(timer), {once:true});
})();"""



# Short, dependency-free feedback for forms that may trigger I/O.
# The message appears immediately; the CSS spinner starts only if navigation
# takes more than a brief moment. Form data remains intact for all submitters.
LOADING_JS = """(() => {
  const layer = document.getElementById('itomiscan-working');
  const message = document.getElementById('itomiscan-working-message');
  if (!layer || !message) return;
  let pending = false;
  const names = {
    '/printers': 'Netzwerk wird nach Druckern durchsucht …',
    '/targets': 'Netzwerk wird nach Zielsystemen durchsucht …',
    '/printers/install': 'Drucker wird eingerichtet …',
    '/printers/test': 'Testseite wird an CUPS übergeben …',
    '/targets/paperless/test': 'Paperless-Verbindung wird geprüft …',
    '/targets/paperless/login': 'Paperless-Anmeldung wird geprüft …',
    '/system/diagnose': 'Scanner und SANE werden geprüft …',
    '/backups/restore': 'Konfiguration wird wiederhergestellt …',
    '/system/password': 'Webpasswort wird geändert …',
    '/remote/command': 'Auftrag wird an den Scanner übergeben …'
  };
  document.addEventListener('submit', event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || event.defaultPrevented) return;
    if (pending) { event.preventDefault(); return; }
    const submitter = event.submitter;
    if (submitter && submitter.hasAttribute('data-no-loading')) return;
    const action = new URL(form.getAttribute('action') || location.href, location.href);
    const label = submitter && submitter.textContent ? submitter.textContent.trim() : '';
    const query = form.querySelector('[name="search"][value="1"]');
    const work = names[action.pathname] ||
      (query ? 'Geräte werden gesucht …' : label ? label + ' …' : 'Änderungen werden gespeichert …');
    message.textContent = work;
    layer.hidden = false;
    layer.setAttribute('aria-busy', 'true');
    pending = true;
    // Do not disable the submitter synchronously: its name/value are required
    // for native form serialization (e.g. restart vs. shutdown).
    window.setTimeout(() => {
      form.querySelectorAll('button[type="submit"],button:not([type])')
        .forEach(button => { if (!button.disabled) { button.disabled = true; button.dataset.itomiLoadingLocked = '1'; } });
    }, 0);
  }, false);
  window.addEventListener('pageshow', () => {
    pending = false;
    layer.hidden = true;
    layer.removeAttribute('aria-busy');
    document.querySelectorAll('button[data-itomi-loading-locked]').forEach(button => {
      button.disabled = false;
      delete button.dataset.itomiLoadingLocked;
    });
  });
})();"""

TARGET_SELECT_JS = """(() => {
  const form = document.getElementById('new-target-form');
  if (!form) return;
  const kind = form.querySelector('[name="kind"]');
  const address = form.querySelector('[name="address"]');
  const help = document.getElementById('target-address-help');
  function update() {
    form.querySelectorAll('[data-target-section]').forEach(section => {
      const selected = section.dataset.targetSection === kind.value;
      section.hidden = !selected;
      // Hidden controls cannot block browser validation of the selected form.
      section.querySelectorAll('input,select').forEach(input => {
        input.disabled = !selected;
      });
    });
    if (help) help.textContent =
      'Optional: vollständige Zieladresse statt Einzelfeldern eingeben. ' +
      'Keine Zugangsdaten in die URL schreiben.';
  }
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-select-paperless]');
    if (!button) return;
    kind.value = 'paperless';
    update();
    const url = form.querySelector('[name="paperless_url"]');
    if (url) url.value = button.dataset.selectPaperless;
    address.value = '';
    const name = form.querySelector('[name="name"]');
    if (name && !name.value.trim()) name.value = 'Paperless';
    form.scrollIntoView({behavior:'smooth', block:'center'});
    if (url) url.focus();
  });
  kind.addEventListener('change', update);
  update();
})();"""

VNC_JS = """import RFB from '/novnc/core/rfb.js';
(() => {
  const screen = document.getElementById('remote-vnc-screen');
  if (!screen) return;
  const holder = document.getElementById('remote-live-placeholder');
  const label = document.getElementById('remote-live-status');
  const retry = document.getElementById('remote-reconnect');
  const login = document.getElementById('remote-login-link');
  const csrf = document.querySelector('form[action="/remote/live/stop"] input[name="csrf"]').value;
  let rfb = null, connected = false, closed = false;
  function state(message, ready=false) {
    connected = ready;
    label.textContent = message;
    holder.hidden = ready;
    screen.hidden = !ready;
    retry.hidden = ready;
  }
  async function post(path) {
    const response = await fetch(path, {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: new URLSearchParams({csrf})
    });
    if (response.redirected || response.status === 401) {
      login.hidden = false;
      throw new Error('Bitte erneut anmelden.');
    }
    if (!response.ok) throw new Error('Verbindung nicht verfügbar.');
  }
  function connect() {
    if (rfb) { rfb.disconnect(); rfb = null; }
    state('Verbindung wird hergestellt …');
    retry.hidden = true;
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = protocol + '//' + location.host + '/remote/vnc/ws';
    try {
      rfb = new RFB(screen, url, {credentials: {password: screen.dataset.password}});
      rfb.scaleViewport = true;
      rfb.resizeSession = false;
      rfb.viewOnly = false;
      rfb.qualityLevel = 5;
      rfb.compressionLevel = 7;
      rfb.addEventListener('connect', () => state('Livebild aktiv · Klicken oder tippen zum Bedienen', true));
      rfb.addEventListener('disconnect', () => {
        if (!closed) state('Fernsteuerung unterbrochen. Wiederherstellen wählen.');
      });
      rfb.addEventListener('securityfailure', () => state('VNC-Anmeldung fehlgeschlagen.'));
    } catch (_error) {
      state('Fernsteuerung konnte nicht gestartet werden.');
    }
  }
  retry.addEventListener('click', async () => {
    retry.disabled = true;
    try {
      await post('/remote/live/reconnect');
      const response = await fetch('/remote', {credentials:'same-origin', cache:'no-store'});
      if (!response.ok || response.redirected) throw new Error('Anmeldung abgelaufen.');
      const html = new DOMParser().parseFromString(await response.text(), 'text/html');
      const newScreen = html.getElementById('remote-vnc-screen');
      if (!newScreen) throw new Error('Keine aktive VNC-Sitzung.');
      screen.dataset.password = newScreen.dataset.password;
      connect();
    } catch (error) {
      state(error.message);
    } finally {retry.disabled = false;}
  });
  const keepAlive = setInterval(async () => {
    if (closed || document.hidden) return;
    try { await post('/remote/live/ping'); }
    catch (_error) { if (!closed) state('Sitzung abgelaufen. Wiederherstellen wählen.'); }
  }, 8000);
  window.addEventListener('pagehide', () => {
    closed = true;
    clearInterval(keepAlive);
    if (rfb) rfb.disconnect();
  }, {once:true});
  connect();
})();"""

REMOTE_JS = """(() => {
  const status = document.getElementById('remote-command-status');
  document.querySelectorAll('[data-power-confirm]').forEach(form => {
    form.addEventListener('click', event => {
      const button = event.target.closest('button[name="action"]');
      if (!button) return;
      const action = button.value === 'restart' ? 'neu starten' : 'herunterfahren';
      if (!window.confirm('ItomiScan wirklich ' + action + '?')) event.preventDefault();
    });
  });
  async function refreshStatus() {
    if (!status || document.hidden) return;
    try {
      const response = await fetch('/api/remote-status',
          {cache:'no-store', credentials:'same-origin'});
      if (!response.ok || response.redirected) return;
      const item = await response.json();
      status.textContent = item ? 'Letzter Auftrag #' + item.id + ': ' +
          item.action + ' · ' + item.status + ' · ' + item.detail :
          'Noch kein Fernauftrag';
    } catch (_error) {}
  }
  refreshStatus();
  const statusTimer = window.setInterval(refreshStatus, 2500);
  const frame = document.getElementById('remote-live-frame');
  if (!frame) {
    window.addEventListener('pagehide', () => clearInterval(statusTimer), {once:true});
    return;
  }
  const feedback = document.getElementById('remote-live-status');
  const placeholder = document.getElementById('remote-live-placeholder');
  const heading = document.getElementById('remote-live-heading');
  const detail = document.getElementById('remote-live-detail');
  const retry = document.getElementById('remote-reconnect');
  const login = document.getElementById('remote-login-link');
  const csrf = document.querySelector('form[action="/remote/live/stop"] input[name="csrf"]').value;
  const send = document.getElementById('remote-send-text');
  const input = document.getElementById('remote-text');
  const keyButtons = document.querySelectorAll('[data-remote-key]');
  let mode = 'loading';
  let halted = false;
  let fetching = false;
  let badFrames = 0;
  let lastImage = null;
  function setMode(next, title='', message='') {
    mode = next;
    const ready = next === 'active';
    frame.hidden = !ready;
    placeholder.hidden = ready;
    retry.hidden = next === 'loading' || ready || next === 'login';
    login.hidden = next !== 'login';
    input.disabled = !ready;
    send.disabled = !ready;
    keyButtons.forEach(button => { button.disabled = !ready; });
    if (!ready) {
      heading.textContent = title;
      detail.textContent = message;
      feedback.textContent = message;
    } else {
      feedback.textContent = 'Livebild aktiv · Berühren oder klicken zum Bedienen';
    }
  }
  function authLost(response) {
    return response.redirected || response.status === 401 ||
        (response.url && new URL(response.url, location.href).pathname === '/login');
  }
  function lostLogin() {
    setMode('login', 'Webanmeldung abgelaufen',
      'Bitte erneut anmelden. Die Fernsteuerung wird erst danach wieder freigegeben.');
  }
  function disconnected(message) {
    setMode('stopped', 'Fernsteuerung unterbrochen', message);
  }
  async function post(path, values={}) {
    const body = new URLSearchParams({csrf, ...values});
    const response = await fetch(path, {method:'POST', credentials:'same-origin',
      cache:'no-store', headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body});
    if (authLost(response)) {
      lostLogin();
      throw new Error('Webanmeldung abgelaufen');
    }
    if (!response.ok) {
      if (response.status === 409) throw new Error('Der Scanner wird bereits in einem anderen Browser gesteuert.');
      if (response.status === 403) throw new Error('Fernsteuerungssitzung abgelaufen oder Eingabe abgelehnt.');
      throw new Error('Scanner momentan nicht erreichbar. Bitte erneut versuchen.');
    }
    return response;
  }
  async function reconnect() {
    if (halted || mode === 'restoring') return;
    setMode('loading', 'Verbindung wird hergestellt …', 'Fernsteuerung wird neu aktiviert.');
    retry.disabled = true;
    try {
      await post('/remote/live/reconnect');
      badFrames = 0;
      // Remain in loading state until a real JPEG arrives.
      feedback.textContent = 'Livebild wird geladen …';
      await refreshFrame();
    } catch (error) {
      if (mode !== 'login') disconnected(error.message);
    } finally { retry.disabled = false; }
  }
  retry.addEventListener('click', reconnect);
  frame.addEventListener('click', async event => {
    if (halted || mode !== 'active') return;
    const box = frame.getBoundingClientRect();
    if (!box.width || !box.height) return;
    const x = Math.max(0, Math.min(1000,
        Math.round((event.clientX - box.left) / box.width * 1000)));
    const y = Math.max(0, Math.min(1000,
        Math.round((event.clientY - box.top) / box.height * 1000)));
    try { await post('/remote/live/input', {kind:'click', x:String(x), y:String(y)}); }
    catch (err) { if (mode !== 'login') disconnected(err.message); }
  });
  keyButtons.forEach(button => {
    button.addEventListener('click', async () => {
      if (mode !== 'active') return;
      try { await post('/remote/live/input', {kind:'key', key_name:button.dataset.remoteKey}); }
      catch (err) { if (mode !== 'login') disconnected(err.message); }
    });
  });
  send.addEventListener('click', async () => {
    if (mode !== 'active') return;
    const value = input.value;
    if (!/^[A-Za-z0-9 .@-]*$/.test(value)) {
      feedback.textContent = 'Nur Buchstaben, Zahlen, Leerzeichen, Punkt, @ und - unterstützt.';
      return;
    }
    send.disabled = true;
    try {
      for (const character of value) {
        const name = {' ':'space', '.':'period', '@':'at', '-':'minus'}[character] || character;
        await post('/remote/live/input', {kind:'key', key_name:name});
        await new Promise(resolve => setTimeout(resolve, 230));
      }
      input.value = '';
    } catch (err) {
      if (mode !== 'login') disconnected(err.message);
    } finally { send.disabled = mode !== 'active'; }
  });
  async function refreshFrame() {
    if (halted || fetching || document.hidden || mode === 'stopped' || mode === 'login') return;
    fetching = true;
    try {
      const response = await fetch('/api/remote-frame?frame=' + Date.now(),
        {cache:'no-store', credentials:'same-origin'});
      if (authLost(response)) { lostLogin(); return; }
      if (response.status === 403) {
        disconnected('Die Live-Sitzung ist abgelaufen. Mit Wiederherstellen erneut verbinden.');
        return;
      }
      if (!response.ok || !(response.headers.get('Content-Type') || '').includes('image/jpeg')) {
        if (++badFrames >= 4) disconnected('Kein aktuelles Scannerbild verfügbar. Verbindung erneut versuchen.');
        return;
      }
      const blob = await response.blob();
      if (!blob.size || blob.size > 512 * 1024) throw new Error('Ungültiges Bildschirmbild');
      const url = URL.createObjectURL(blob);
      frame.onload = () => {
        if (lastImage) URL.revokeObjectURL(lastImage);
        lastImage = url;
        badFrames = 0;
        if (mode !== 'login' && mode !== 'stopped') setMode('active');
      };
      frame.onerror = () => {
        URL.revokeObjectURL(url);
        if (++badFrames >= 4) disconnected('Scannerbild kann nicht dargestellt werden.');
      };
      frame.src = url;
    } catch (_error) {
      if (++badFrames >= 4) disconnected('Verbindung zum Scanner unterbrochen. Bitte erneut versuchen.');
    } finally { fetching = false; }
  }
  refreshFrame();
  const frameTimer = window.setInterval(refreshFrame, 900);
  const keepAlive = window.setInterval(async () => {
    if (halted || document.hidden || mode !== 'active') return;
    try { await post('/remote/live/ping'); }
    catch (error) { if (mode !== 'login') disconnected(error.message); }
  }, 8000);
  window.addEventListener('pagehide', () => {
    halted = true;
    clearInterval(statusTimer); clearInterval(frameTimer); clearInterval(keepAlive);
    if (lastImage) URL.revokeObjectURL(lastImage);
  }, {once:true});
})();"""

PRINTER_CHOOSE_JS = """(() => {
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-select-printer]');
    if (!button) return;
    const field = document.querySelector('form[action="/printers/save"] input[name="address"]');
    if (field) {
      field.value = button.dataset.selectPrinter;
      field.focus();
    }
  });
})();"""


DIALOG_JS = """(() => {
  document.addEventListener('click', event => {
    const open = event.target.closest('[data-dialog-open]');
    if (open) {
      const dialog = document.getElementById(open.dataset.dialogOpen);
      if (dialog && typeof dialog.showModal === 'function') dialog.showModal();
      return;
    }
    const close = event.target.closest('[data-dialog-close]');
    if (close) {
      const dialog = close.closest('dialog');
      if (dialog) dialog.close();
    }
  });
  document.querySelectorAll('dialog.detail-dialog').forEach(dialog => {
    dialog.addEventListener('click', event => {
      if (event.target === dialog) dialog.close();
    });
  });
})();"""


def detail_dialog(identifier, label, summary, content):
    """Compact row backed by a native, focus-trapping modal detail dialog."""
    return ('<div class="entry-row"><div><strong>' + e(label) + '</strong>'
            '<p class="muted">' + e(summary) + '</p></div>'
            '<button class="secondary" type="button" data-dialog-open="' + e(identifier) +
            '">Details</button></div>'
            '<dialog class="detail-dialog" id="' + e(identifier) + '">'
            '<div class="dialog-top"><h2>' + e(label) +
            '</h2><button class="secondary" type="button" data-dialog-close>Schließen</button></div>'
            + content + '</dialog>')


def metric(key, value, *, inline=False):
    tag = "span" if inline else "strong"
    return f'<{tag} data-status-key="{e(key)}">{e(value)}</{tag}>'


CSS = """
:root{color-scheme:dark;--bg:#101927;--pane:#192738;--fg:#f1f5fb;--soft:#a8bacd;--accent:#5fc7eb;--ok:#53c49b;--line:#32455a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,DejaVu Sans,sans-serif;line-height:1.45}
.wrap{max-width:1120px;margin:auto;padding:22px 22px 50px}
header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;border-bottom:1px solid var(--line);padding-bottom:14px}
.brand{display:flex;align-items:center;gap:11px;font-size:1.8rem;font-weight:800;letter-spacing:-.035em}.brand b{color:#42bfea}.brand-icon{flex:none;border-radius:8px}.brand-name{white-space:nowrap}
nav{display:flex;flex-wrap:wrap;gap:9px;align-items:center}a{color:var(--accent)}nav a{padding:10px 9px;text-decoration:none;color:var(--fg);border-radius:9px}
nav a:hover,nav a.active{background:#2a4560}.nav-home-brand{display:inline-flex;align-items:center;gap:7px;font-weight:750;white-space:nowrap}.nav-home-brand b{color:#42bfea}.nav-home-brand .brand-icon{border-radius:5px}
h1{font-size:1.65rem;margin:28px 0 10px}h2{font-size:1.15rem;margin:4px 0 14px}
p{color:var(--soft)}small,.muted{color:var(--soft)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(285px,1fr));gap:16px}
.card{background:var(--pane);padding:20px;border-radius:15px;min-width:0}.card p{margin-top:0}.wide{grid-column:1/-1}
label{display:block;color:var(--soft);font-size:.92rem;margin:11px 0 5px}
input,select,textarea,button{font:inherit;max-width:100%}
input,select,textarea{background:#0e1c2d;color:var(--fg);border:1px solid #587088;border-radius:8px;padding:10px;width:100%}
textarea{min-height:80px}input:focus,select:focus,textarea:focus{outline:2px solid var(--accent);outline-offset:1px}
button,.action{display:inline-block;background:#2a75c1;color:white;border:0;border-radius:9px;padding:11px 16px;cursor:pointer;margin-top:13px;text-decoration:none;font-weight:600}
button:hover,.action:hover{background:#3586d7}.secondary{background:#30485f}.danger{background:#8c4050}
.notice{background:#153b3a;border:1px solid #337869;padding:13px 17px;border-radius:9px;margin:18px 0}
.alert{background:#4b2834;border:1px solid #a05d6b;padding:13px 17px;border-radius:9px;margin:18px 0}
.pill{display:inline-block;padding:4px 10px;border-radius:20px;color:var(--ok);background:#1c3938;font-weight:600}.status-key{margin-bottom:4px}.status-metric{font-size:1.3rem;font-weight:700;color:var(--fg)}.status-note{font-size:.88rem;color:var(--soft)}
.inline{display:inline-block;margin:0}.data{background:#0d1a2a;padding:14px;border-radius:10px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:270px;overflow:auto;font-size:.92rem}
table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;border-bottom:1px solid var(--line);word-break:break-word}
.end{margin-top:24px;border-top:1px solid var(--line);padding-top:13px}
.login{max-width:460px;margin:12vh auto 0}.login h1{margin-top:4px}
@media(max-width:650px){.wrap{padding:14px}nav a{padding:8px 5px}.card{padding:16px}table{font-size:.86rem}.brand{font-size:1.5rem}}

.entry-list{display:flex;flex-direction:column;gap:10px}
.tile-check{display:flex;align-items:center;gap:10px}
.tile-check input{width:auto;min-width:18px;height:18px;margin:0}
fieldset{border:1px solid var(--line);border-radius:9px;margin-top:12px;padding:10px 14px}
.entry-row{display:flex;align-items:center;justify-content:space-between;gap:14px;background:var(--pane);padding:12px 17px;border-radius:12px}
.entry-row p{margin:3px 0 0;overflow-wrap:anywhere}
.entry-row button{margin:0;flex:none}
.detail-dialog{background:var(--pane);color:var(--fg);border:1px solid var(--line);border-radius:15px;padding:22px;max-width:min(740px,94vw);width:100%;max-height:88vh;overflow:auto}
.detail-dialog::backdrop{background:rgba(0,0,0,.73)}
.dialog-top{display:flex;justify-content:space-between;align-items:center;gap:12px}
.dialog-top button{margin:0}
.detail-dialog .card{padding:0}
.monitor-chart{width:100%;height:auto;display:block;background:#101d2e;border-radius:9px}
.memory-track{height:20px;background:#101d2e;border-radius:10px;overflow:hidden;border:1px solid var(--line)}
.memory-fill{height:100%;width:0;background:#42bfea;transition:width .5s linear}
.remote-screen{max-width:768px;background:#101d2e;border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:12px 0}
.remote-screen img{width:100%;height:auto;display:block;cursor:crosshair;touch-action:manipulation}
.remote-placeholder{min-height:300px;aspect-ratio:4/3;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;padding:24px;text-align:center}
.remote-placeholder p{margin:0;max-width:450px}
.remote-placeholder button{margin:0}
[hidden]{display:none!important}
.working-overlay{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(5,12,22,.7);z-index:1000;padding:18px}
.working-panel{width:min(430px,95vw);background:var(--pane);border:1px solid var(--line);border-radius:14px;padding:24px;text-align:center;box-shadow:0 14px 40px #0007}
.working-panel .brand-icon{display:block;margin:0 auto 13px;width:52px;height:52px}.working-panel .brand-icon rect:nth-of-type(2){animation:itomi-scan 1.3s ease-in-out infinite alternate}
@keyframes itomi-scan{to{transform:translateY(35px)}}
@media(prefers-reduced-motion:reduce){.working-panel .brand-icon rect:nth-of-type(2){animation:none}}
button:disabled{opacity:.67;cursor:wait}
.remote-keys{max-width:770px}.remote-keys button{margin-right:9px}
"""


def layout(title, body, *, active="", csrf="", notice="", error="", logged=True, live=False):
    navigation = ""
    if logged:
        links = (("/", "Übersicht"), ("/profiles", "Scanprofile"),
                 ("/users", "Benutzer"), ("/home-buttons", "Startseite"), ("/remote", "Fernsteuerung"), ("/targets", "Zielsysteme"), ("/printers", "Drucker"), ("/jobs", "Aufträge"), ("/system", "System"),
                 ("/backups", "Sicherung"))
        navigation = '<nav aria-label="Hauptnavigation">' + "".join(
            f'<a class="{("active" if url == active else "")}" href="{url}">{e(label)}</a>'
            for url, label in links
        ) + (f'<form class="inline" method="post" action="/logout">'
             f'<input type="hidden" name="csrf" value="{e(csrf)}">'
             '<button class="secondary">Abmelden</button></form></nav>')
    messages = (f'<div class="notice">{e(notice)}</div>' if notice else "") + (
        f'<div class="alert">{e(error)}</div>' if error else "")
    return ('<!doctype html><html lang="de"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(title)} · ItomiScan</title><style>{CSS}</style></head>'
            '<body><main class="wrap"><header><div class="brand">'
            + logo_svg() + '<div class="brand-name">Itomi<b>Scan</b></div>'
            f'</div>{navigation}</header>{messages}{body}'
            '<div class="end muted">ItomiScan 1.0.0 Entwicklung · '
            'Webadministration nur im geschützten LAN/VPN</div></main>'
            + ('<script defer src="/assets/status.js"></script>' if live else '')
            + ('<script defer src="/assets/admin-dialogs.js"></script>' if logged else '')
            + ('<script defer src="/assets/loading.js"></script>' if logged else '')
            + ('<div id="itomiscan-working" class="working-overlay" role="status" aria-live="polite" hidden>'
               '<div class="working-panel">' + logo_svg(52) +
               '<strong id="itomiscan-working-message">Bitte warten …</strong></div></div>' if logged else '')
            + '</body></html>')


def token(csrf):
    return f'<input type="hidden" name="csrf" value="{e(csrf)}">'


def options(items, current):
    return "".join(f'<option value="{e(item)}"'
                   + (" selected" if str(item) == str(current) else "")
                   + f'>{e(item)}</option>' for item in items)


def login(error=""):
    content = ('<div class="login card"><h1>Webadministration</h1>'
               '<p>Bitte das Administratorpasswort eingeben. '
               'Ein Benutzername ist nicht erforderlich.</p>'
               '<form method="post" action="/login"><label for="password">Passwort</label>'
               '<input id="password" type="password" name="password" '
               'autocomplete="current-password" maxlength="128" required>'
               '<button>Anmelden</button></form><p><small>Die erste Einrichtung erfolgt '
               'sicher über die lokale Konsole/SSH. Es gibt kein Standardpasswort.'
               '</small></p></div>')
    return layout("Anmelden", content, logged=False, error=error)


def chart_panel(title, key):
    return ('<article class="card"><h2>' + e(title) + '</h2>'
            '<p class="status-metric" data-chart-value>Messung läuft …</p>'
            '<svg class="monitor-chart" data-metric-chart="' + e(key) +
            '" viewBox="0 0 320 122" role="img" aria-label="Auslastung der letzten fünf Minuten">'
            '<path d="M10 10V110H310" fill="none" stroke="#587088" stroke-width="1"/>'
             '<path d="M10 10H310M10 60H310" fill="none" stroke="#32455a" stroke-width=".6" stroke-dasharray="3 3"/>'
             '<text x="14" y="9" fill="#a8bacd" font-size="9">100%</text>'
             '<text x="14" y="57" fill="#a8bacd" font-size="9">50%</text>'
             '<text x="14" y="105" fill="#a8bacd" font-size="9">0%</text>'
            '<polyline fill="none" stroke="#42bfea" stroke-width="2" points=""/>'
            '<text x="10" y="120" fill="#a8bacd" font-size="9">−5 min</text>'
            '<text x="310" y="120" fill="#a8bacd" font-size="9" text-anchor="end">Jetzt</text>'
            '</svg></article>')


def overview(status, counts, csrf, notice=""):
    body = '<h1>Übersicht</h1><p>Scanner und Einstellungen im Blick.</p>'
    items = (
        ("Scanner", status.get("scanner", "Nicht geprüft"),
         "Erkennung über die Systemdiagnose starten."),
        ("Scanprofile", str(counts["profiles"]), "Gemeinsam mit dem Touchdisplay gespeichert."),
        ("Zielsysteme", str(counts["targets"]),
         "Konfiguration vorbereitet; Übertragung und Druck folgen."),
        ("Versionszweig", status.get("branch", "Unbekannt"),
         "Entwicklung ist kein Release."),
    )
    body += '<section class="grid">' + "".join(
        f'<article class="card"><h2>{e(name)}</h2>'
        + (f'<p class="pill">{metric("scanner", value)}</p>' if name == "Scanner"
           else f'<p class="pill">{e(value)}</p>')
        + f'<p>{e(description)}</p></article>' for name, value, description in items
    ) + '</section>'
    body += '<h2>Systemauslastung</h2><section class="grid">'
    body += chart_panel('CPU-Auslastung', 'cpu') + chart_panel('Arbeitsspeicher', 'ram')
    body += '</section><section class="grid" style="margin-top:16px">'
    body += ('<article class="card"><h2>Arbeitsspeicherbelegung</h2>'
             '<div class="memory-track" role="progressbar" aria-label="Arbeitsspeicher belegt" '
             'aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" data-ram-progress>'
             '<div class="memory-fill" data-ram-fill></div></div>'
             '<p data-ram-detail>Messung läuft …</p></article>')
    body += ('<article class="card"><h2>Datenträger</h2><p class="status-metric">'
             + metric('disk', status.get('disk', 'Nicht verfügbar'))
             + '</p></article>')
    body += '</section><h2>Gerätezustand</h2><section class="grid">'
    for heading, key in (
        ("Web-Admin-Dienst", "web_service"),
        ("Zustelldienst", "delivery_service"),
        ("Wartende Aufträge", "jobs_pending"),
        ("Zu prüfende Aufträge", "jobs_review"),
    ):
        body += (f'<article class="card"><h2>{e(heading)}</h2>'
                 f'<p class="status-metric">{metric(key, status.get(key, "Nicht verfügbar"))}</p></article>')
    body += '</section><p class="status-note">CPU/RAM-Aktualisierung jede Sekunde, '
    body += 'ohne Seitenwechsel oder automatischen Scannertest.</p>'
    return layout("Übersicht", body, active="/", csrf=csrf, notice=notice,
                  live=True)


def profiles_page(profiles, selected, csrf, notice="", *, printers=None, printer_selections=None):
    printers = printers or []
    printer_selections = printer_selections or {}
    body = '<h1>Scanprofile</h1><p>Die Änderungen stehen dem Touchdisplay beim nächsten Profilaufruf zur Verfügung.</p>'
    body += '<section class="entry-list">'
    for index, item in enumerate(profiles):
        name = item["name"]
        detail = (f'<article class="card"><h2>{e(name)}'
                 + (' <span class="pill">Ausgewählt</span>' if name == selected else "")
                 + '</h2><form method="post" action="/profiles/save">'
                 + token(csrf)
                 + f'<label>Profilname</label><input name="name" maxlength="32" required value="{e(name)}">'
                 + '<label>Farbmodus</label><select name="mode">' +
                 options(("Color", "Gray", "Lineart", "Halftone"), item["mode"]) +
                 '</select><label>Einzug</label><select name="source">' +
                 options(("ADF Front", "ADF Back", "ADF Duplex"), item["source"]) +
                 f'</select><label>Auflösung (DPI)</label><input type="number" name="resolution" min="50" max="600" value="{e(item["resolution"])}">'
                 + '<label>Ausgabe</label><select name="output">' +
                 options(("PDF", "Bild (PNG)"), item["output"]) +
                 f'</select><label>Erweiterte SANE-Einstellungen (JSON)</label>'
                 f'<textarea name="advanced">{e(json.dumps(item.get("settings", {}), ensure_ascii=False, indent=2))}</textarea>'
                 '<button>Profil speichern</button></form>'
                 '<form method="post" action="/profiles/select">'
                 + token(csrf) + f'<input type="hidden" name="name" value="{e(name)}">'
                 '<button class="secondary">Als Standard verwenden</button></form>'
                 '<form method="post" action="/profiles/printer">' + token(csrf)
                 + '<input type="hidden" name="name" value="' + e(name) + '">'
                 '<label>Bevorzugter Drucker für Kopieren</label>'
                 '<select name="target_id"><option value="0">Kein bevorzugter Drucker</option>'
                 + "".join('<option value="' + e(p["id"]) + '"' +
                           (' selected' if printer_selections.get(name) == p["id"] else '') +
                           '>' + e(p["name"]) + '</option>' for p in printers)
                 + '</select><button class="secondary">Druckerzuordnung speichern</button>'
                 '</form></article>')
        body += detail_dialog(f'profile-{index}', name,
                              f'{item["mode"]} · {item["resolution"]} DPI · {item["source"]}', detail)
    body += '</section><div class="card" style="margin-top:16px"><h2>Neues Profil</h2>'
    body += ('<form method="post" action="/profiles/save">' + token(csrf)
             + '<label>Name</label><input name="name" maxlength="32" required>'
             + '<label>Farbmodus</label><select name="mode">'
             + options(("Color", "Gray", "Lineart", "Halftone"), "Color")
             + '</select><label>Einzug</label><select name="source">'
             + options(("ADF Duplex", "ADF Front", "ADF Back"), "ADF Duplex")
             + '</select><label>Auflösung (DPI)</label><input type="number" name="resolution" min="50" max="600" value="200">'
             + '<label>Ausgabe</label><select name="output">'
             + options(("PDF", "Bild (PNG)"), "PDF")
             + '</select><label>Erweiterte SANE-Einstellungen (JSON)</label>'
             + '<textarea name="advanced">{}</textarea><button>Profil hinzufügen</button></form></div>')
    return layout("Scanprofile", body, active="/profiles", csrf=csrf, notice=notice)


def targets_page(targets, csrf, notice=""):
    body = ('<h1>Zielsysteme</h1><p>Adressen hier vorbereiten. '
            '<strong>Die Übertragung an Paperless, das Speichern im Netzwerk '
            'und das Drucken sind noch nicht aktiv.</strong> '
            'API-Tokens und Zugangsdaten gehören derzeit nicht in diese Felder.</p>')
    body += '<section class="grid">'
    for item in targets:
        body += (f'<article class="card"><h2>{e(item["name"])}</h2>'
                 f'<p>{e(item["kind"])} · {e(item["address"])}</p>'
                 f'<form method="post" action="/targets/delete">' + token(csrf)
                 + f'<input type="hidden" name="id" value="{e(item["id"])}">'
                 '<button class="danger">Ziel entfernen</button></form></article>')
    body += '</section><div class="card" style="margin-top:16px"><h2>Neues Ziel vorbereiten</h2>'
    body += ('<form method="post" action="/targets/save">' + token(csrf)
             + '<label>Zieltyp</label><select name="kind">'
             + options(("paperless", "printer", "network", "email"), "paperless")
             + '</select><label>Anzeigename</label><input name="name" required maxlength="60">'
             + '<label>Adresse (ohne Zugangsdaten)</label>'
             '<input name="address" required maxlength="350" placeholder="https://paperless.lan oder ipp://drucker/ipp/print">'
             '<button>Ziel speichern</button></form></div>')
    return layout("Zielsysteme", body, active="/targets", csrf=csrf, notice=notice)


def system_page(state, settings, csrf, diagnostic="", notice=""):
    body = '<h1>System und Diagnose</h1><section class="grid">'
    body += '<article class="card"><h2>Geräteinformationen</h2>'
    for title, key in (
        ("Host", "hostname"), ("IP", "ip"), ("System", "platform"),
        ("Git-Zweig", "branch"), ("Commit", "commit"), ("Uptime", "uptime"),
        ("Scanner", "scanner"),
    ):
        body += (f'<p><strong>{e(title)}:</strong> '
                 f'{metric(key, state.get(key, "Nicht verfügbar"), inline=True)}</p>')
    body += '</article><article class="card"><h2>CPU und Arbeitsspeicher</h2>'
    for title, key in (
        ("CPU-Auslastung", "cpu"), ("RAM gesamt", "ram_total"),
        ("RAM belegt", "ram_used"), ("RAM verfügbar", "ram_free"),
    ):
        body += (f'<p><strong>{e(title)}:</strong> '
                 f'{metric(key, state.get(key, "Nicht verfügbar"), inline=True)}</p>')
    body += '</article><article class="card"><h2>Datenträger</h2>'
    for title, key in (
        ("Gesamtkapazität", "disk_total"), ("Belegt", "disk_used"),
        ("Frei", "disk_free"),
    ):
        body += (f'<p><strong>{e(title)}:</strong> '
                 f'{metric(key, state.get(key, "Nicht verfügbar"), inline=True)}</p>')
    body += '</article><article class="card"><h2>Dienste und Zustellung</h2>'
    for title, key in (
        ("Web-Admin", "web_service"), ("Zustelldienst", "delivery_service"),
        ("Wartende Aufträge", "jobs_pending"), ("Zu prüfende Aufträge", "jobs_review"),
    ):
        body += (f'<p><strong>{e(title)}:</strong> '
                 f'{metric(key, state.get(key, "Nicht verfügbar"), inline=True)}</p>')
    body += '</article></section>'
    body += '<section class="grid" style="margin-top:16px">' + chart_panel('CPU-Verlauf', 'cpu') + chart_panel('RAM-Verlauf', 'ram') + '</section>'
    body += '<p class="status-note">CPU und RAM werden jede Sekunde aktualisiert. '
    body += 'Nicht gespeicherte Formulare bleiben unberührt.</p>'
    body += ('<article class="card"><h2>Geräteeinstellungen</h2>'
             '<p>Änderungen des Bildschirmschoners greifen am Display spätestens '
             'nach einem Neustart der Oberfläche.</p>'
             '<form method="post" action="/system/settings">' + token(csrf)
             + f'<label>Gerätename</label><input maxlength="48" name="device_label" value="{e(settings["device_label"])}">'
             + f'<label>Bildschirmschoner (Minuten)</label><input type="number" name="screensaver_minutes" min="1" max="60" value="{e(settings["screensaver_minutes"])}">'
             + '<button>Einstellungen speichern</button></form></article>')
    body += ('<article class="card" style="margin-top:16px"><h2>SANE-Scannererkennung</h2>'
             '<p>Diese Diagnose startet ausschließlich <code>scanimage -L</code>. '
             'Ein laufender Scan sollte vorher abgeschlossen sein.</p>'
             '<form method="post" action="/system/diagnose">' + token(csrf)
             + '<button class="secondary">Scanner prüfen</button></form>'
             + (f'<pre class="data">{e(diagnostic)}</pre>' if diagnostic else "")
             + '</article><article class="card" style="margin-top:16px"><h2>Administratorpasswort ändern</h2>'
             '<form method="post" action="/system/password">' + token(csrf)
             + '<label>Aktuelles Passwort</label><input type="password" name="current_password" autocomplete="current-password" required>'
             + '<label>Neues Passwort (mindestens 10 Zeichen)</label><input type="password" name="new_password" minlength="10" maxlength="128" autocomplete="new-password" required>'
             + '<label>Neues Passwort wiederholen</label><input type="password" name="confirm_password" minlength="10" maxlength="128" autocomplete="new-password" required>'
             '<button>Passwort ändern</button></form></article>')
    return layout("System", body, active="/system", csrf=csrf, notice=notice,
                  live=True)

def backup_page(csrf, notice=""):
    body = ('<h1>Konfiguration sichern</h1><section class="grid"><article class="card">'
            '<h2>Export</h2><p>Profile, Einstellungen und Zieladressen als JSON-Datei sichern. '
            'Administratorpasswort, Hash, Sitzungen und Zugangsdaten sind nicht enthalten.</p>'
            '<a class="action" href="/backup.json">JSON-Sicherung herunterladen</a></article>'
            '<article class="card"><h2>Wiederherstellen</h2>'
            '<p>Der Import ersetzt Scanprofile, Geräteeinstellungen und Zieladressen. '
            'Das Administratorpasswort bleibt erhalten. Bitte vorher eine Sicherung herunterladen.</p>'
            '<form method="post" action="/backups/restore" enctype="multipart/form-data">'
            + token(csrf) +
            '<label>Konfigurationsdatei (JSON, maximal 128 KB)</label>'
            '<input type="file" name="backup" accept=".json,application/json" required>'
            '<button class="danger">Konfiguration wiederherstellen</button></form></article>'
            '</section>')
    return layout("Sicherung", body, active="/backups", csrf=csrf, notice=notice)
