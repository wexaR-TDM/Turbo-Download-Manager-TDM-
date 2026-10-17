"""Tarayıcı eklentisi ve ikinci program örneği için yerel HTTP köprüsü (yalnızca 127.0.0.1).

Web sayfalarının bu porta istek atmasını engellemek için özel `X-TurboDM` başlığı zorunludur:
bu başlık tarayıcıda CORS ön kontrolünü (preflight) tetikler ve biz ona izin vermediğimiz için
sıradan siteler istek gönderemez. Eklentiler host_permissions sayesinde CORS'tan muaftır.
"""
import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

requests = queue.Queue()   # GUI tarafından tick'te okunur

# Eşzamanlı yanıt veren işleyiciler (yol → fonksiyon(data) → dict). GUI başlarken doldurur.
# /formats: eklentinin sayfada kalite menüsü gösterebilmesi için video kaliteleri (yt-dlp, ~3 sn).
handlers = {}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _host_ok(self):
        """DNS rebinding koruması: kötü niyetli bir alan adı 127.0.0.1'e çözülse bile tarayıcı Host başlığına
        o alan adını yazar. Yalnızca gerçekten yerel adresle gelen istekler kabul edilir."""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        return host in ("127.0.0.1", "localhost", "::1")

    def do_OPTIONS(self):
        self._reply(403, {"error": "forbidden"})

    def do_GET(self):
        if not self._host_ok():
            return self._reply(403, {"error": "forbidden"})
        if self.path == "/ping":
            self._reply(200, {"app": "TurboDM"})
        else:
            self._reply(404, {"error": "not found"})

    def do_POST(self):
        if self.headers.get("X-TurboDM") != "1" or not self._host_ok():
            return self._reply(403, {"error": "forbidden"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(min(n, 1 << 20)) or b"{}")
        except ValueError:
            return self._reply(400, {"error": "bad json"})
        if self.path == "/add" and isinstance(data.get("url"), str):
            # Tarayıcının başlattığı indirme ("check"): kabul etmeden önce TurboDM dosyaya gerçekten ulaşabiliyor mu?
            # Ulaşamıyorsa (bot koruması, giriş, süresi dolmuş bağlantı…) reddedilir; eklenti indirmeyi tarayıcıda sürdürür.
            if data.get("check") and "/check" in handlers:
                try:
                    reason = handlers["/check"](data)
                except Exception as e:  # noqa: BLE001
                    reason = str(e) or e.__class__.__name__
                if reason:
                    requests.put({"notice": reason, "url": data["url"]})
                    return self._reply(200, {"ok": False, "reason": reason})
            requests.put(data)
            self._reply(200, {"ok": True})
        elif self.path == "/show":
            requests.put({"show": True})
            self._reply(200, {"ok": True})
        elif self.path == "/quit":  # kurulum/kaldırma programı için
            requests.put({"quit": True})
            self._reply(200, {"ok": True})
        elif self.path in handlers:
            try:
                self._reply(200, handlers[self.path](data))
            except Exception as e:  # noqa: BLE001
                self._reply(200, {"error": str(e) or e.__class__.__name__})
        else:
            self._reply(400, {"error": "bad request"})


def start(port):
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
