from http.server import BaseHTTPRequestHandler
import urllib.parse, urllib.request, os, re

ALLOWED = os.environ.get("ALLOWED_ORIGIN", "")

class handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, Content-Type")
        self.send_header("Access-Control-Expose-Headers", "Content-Length, Content-Disposition")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_HEAD(self):
        self.do_GET(head_only=True)

    def do_GET(self, head_only=False):
        target = ""
        try:
            if ALLOWED:
                ref = (self.headers.get("Referer") or "") + (self.headers.get("Origin") or "")
                if ALLOWED not in ref:
                    self.send_response(403); self.end_headers(); return

            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            target = (qs.get("url") or [""])[0].strip()
            filename = (qs.get("filename") or [""])[0].strip()
            if not target:
                self.send_response(400); self.end_headers(); return

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Fetch-Mode": "navigate",
            }

            if any(d in target.lower() for d in ["tiktok", "byteimg", "musical.ly", "douyin"]):
                headers["Referer"] = "https://www.tiktok.com/"

            req = urllib.request.Request(target, headers=headers)

            with urllib.request.urlopen(req, timeout=25) as resp:
                status = resp.status
                content_type = resp.headers.get("Content-Type", "application/octet-stream")
                content_length = resp.headers.get("Content-Length")

                # If this is an audio download request, ensure audio MIME type
                if filename and filename.lower().endswith(".mp3"):
                    content_type = "audio/mpeg"

                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self._cors()
                self.send_header("Cache-Control", "public, max-age=3600")
                if content_length:
                    self.send_header("Content-Length", content_length)

                if filename:
                    safe_filename = re.sub(r'[^\w\-.]', '_', filename)
                    self.send_header("Content-Disposition", f'attachment; filename="{safe_filename}"')

                self.end_headers()

                if head_only:
                    return

                # Stream in 64 KB chunks
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

        except Exception as e:
            # If server-side fetch fails, redirect directly to the source URL so download never fails
            try:
                if target:
                    self.send_response(302)
                    self.send_header("Location", target)
                    self._cors()
                    self.end_headers()
                else:
                    self.send_response(502)
                    self.send_header("Content-Type", "text/plain")
                    self._cors()
                    self.end_headers()
                    self.wfile.write(str(e)[:200].encode())
            except Exception:
                pass
