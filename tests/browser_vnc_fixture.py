"""Loopback-only browser regression fixture using the installed noVNC decoder.

Run from the repository: python3 tests/browser_vnc_fixture.py
Open http://127.0.0.1:18844/remote to check image decoding under the real CSP.
Only synthetic pixels are served; this fixture never opens X11 or VNC.
"""
import base64
import io
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from itomiscan.web.server import AdminHandler
from itomiscan.web.vnc_bridge import NOVNC_ROOT

HTML = """<!doctype html><html><head><title>noVNC image regression</title></head>
<body><h1>noVNC image regression</h1><p id="result">Waiting for frame</p>
<canvas id="screen"></canvas><script type="module" src="/fixture.js"></script>
</body></html>"""
image = io.BytesIO()
Image.new("RGB", (128, 64), (220, 20, 30)).save(image, "JPEG")
JPEG = base64.b64encode(image.getvalue()).decode("ascii")
JS = """import Display from '/novnc/core/display.js';
const canvas = document.getElementById('screen');
const display = new Display(canvas);
display.resize(128, 128);
const data = Uint8Array.from(atob('JPEG_DATA'), c => c.charCodeAt(0));
display.imageRect(0, 0, 128, 64, 'image/jpeg', data);
display.fillRect(0, 64, 128, 64, [20, 220, 30]);
display.flip();
display.onflush = () => {
  const context = canvas.getContext('2d');
  const red = context.getImageData(32, 32, 1, 1).data;
  const green = context.getImageData(32, 96, 1, 1).data;
  document.getElementById('result').textContent =
    red[0] > 200 && red[1] < 40 && green[1] > 200 && green[0] < 40
      ? 'PASS: JPEG and following framebuffer update rendered'
      : 'FAIL: incorrect framebuffer pixels';
};
if (display.pending()) display.flush(); else display.onflush();
setTimeout(() => {
  const result = document.getElementById('result');
  if (result.textContent === 'Waiting for frame')
    result.textContent = 'FAIL: image decoder blocked; framebuffer queue stalled';
}, 1500);
""".replace("JPEG_DATA", JPEG)


class FixtureHandler(AdminHandler):
    def do_GET(self):
        if self.path == "/remote":
            return self._response(200, HTML, vnc_images=True)
        if self.path == "/fixture.js":
            return self._response(200, JS, mime="text/javascript")
        if self.path.startswith("/novnc/"):
            relative = self.path[len("/novnc/"):]
            target = (NOVNC_ROOT / relative).resolve()
            if NOVNC_ROOT.resolve() in target.parents and target.is_file():
                return self._response(200, target.read_bytes(), mime="text/javascript")
        return self._response(404, "Not found")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 18844), FixtureHandler)
    server.secure = False
    server.bind_ip = "127.0.0.1"
    print("Synthetic noVNC fixture on http://127.0.0.1:18844/remote", flush=True)
    server.serve_forever()
