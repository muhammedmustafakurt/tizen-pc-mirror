"""PC screen -> MJPEG stream for the TizenBrew mirror module.

Usage:
    pip install mss pillow
    python server.py --allow <TV_IP> [--port 8765] [--fps 15] [--width 1280] [--quality 60] [--monitor 1]

Only the IPs given with --allow (and this PC itself) may fetch the stream.
"""
import argparse
import io
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import mss
from PIL import Image

BOUNDARY = "frame"


class Grabber(threading.Thread):
    """Captures the screen once, shared by all clients."""

    def __init__(self, monitor, fps, width, quality):
        super().__init__(daemon=True)
        self.monitor, self.fps, self.width, self.quality = monitor, fps, width, quality
        self.cond = threading.Condition()
        self.jpeg = None
        self.seq = 0
        self.clients = 0

    def run(self):
        with mss.mss() as sct:
            mon = sct.monitors[self.monitor]
            interval = 1.0 / self.fps
            while True:
                t0 = time.time()
                if self.clients > 0:
                    shot = sct.grab(mon)
                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                    if img.width > self.width:
                        h = round(img.height * self.width / img.width)
                        img = img.resize((self.width, h), Image.BILINEAR)
                    buf = io.BytesIO()
                    img.save(buf, "JPEG", quality=self.quality)
                    with self.cond:
                        self.jpeg = buf.getvalue()
                        self.seq += 1
                        self.cond.notify_all()
                time.sleep(max(0.0, interval - (time.time() - t0)))


def make_handler(grabber, allowed):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            print("[%s] %s" % (self.client_address[0], fmt % args))

        def do_GET(self):
            ip = self.client_address[0]
            if ip not in allowed:
                self.send_error(403, "forbidden")
                return
            if self.path.split("?")[0] != "/stream":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=" + BOUNDARY)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            grabber.clients += 1
            last = -1
            try:
                while True:
                    with grabber.cond:
                        grabber.cond.wait_for(lambda: grabber.seq != last, timeout=5)
                        data, last = grabber.jpeg, grabber.seq
                    if data is None:
                        continue
                    self.wfile.write(
                        ("--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n"
                         % (BOUNDARY, len(data))).encode() + data + b"\r\n")
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            finally:
                grabber.clients -= 1

    return Handler


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--allow", nargs="+", required=True, help="TV IP address(es) allowed to connect")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--fps", type=int, default=15)
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--quality", type=int, default=60)
    p.add_argument("--monitor", type=int, default=1, help="1 = primary monitor")
    a = p.parse_args()

    grabber = Grabber(a.monitor, a.fps, a.width, a.quality)
    grabber.start()
    allowed = set(a.allow) | {"127.0.0.1"}
    srv = ThreadingHTTPServer(("0.0.0.0", a.port), make_handler(grabber, allowed))
    print("Streaming on port %d, allowed: %s  (Ctrl+C to stop)" % (a.port, ", ".join(sorted(allowed))))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
