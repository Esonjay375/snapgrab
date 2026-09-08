import json
import os
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler

ALLOWED = os.environ.get("ALLOWED_ORIGIN", "")
COBALT_API = os.environ.get("COBALT_API_URL", "https://api.cobalt.tools/")

class handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_POST(self):
        try:
            # CORS validation
            if ALLOWED:
                ref = (self.headers.get("Referer") or "") + (self.headers.get("Origin") or "")
                if ALLOWED not in ref:
                    return self._send(403, {"error": "forbidden"})

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body) if body else {}

            url = data.get("url", "").strip()
            if not url:
                return self._send(400, {"error": "missing url"})

            # Request payload for Cobalt API
            payload = json.dumps({
                "url": url,
                "videoQuality": data.get("videoQuality", "720"),
                "downloadMode": data.get("downloadMode", "auto") # 'auto' fetches video with sound
            }).encode('utf-8')

            req = urllib.request.Request(
                COBALT_API,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=25) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                self._send(200, res_data)

        except Exception as e:
            self._send(500, {"error": str(e)})
