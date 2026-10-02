"""Long-running HTTP entry point for Railway.

Wraps the serverless handlers in api/fetch.py and api/merge.py in a single
http.server instance that listens on $PORT.

Routes:
    /fetch, /api/fetch   -> api.fetch.handler (yt-dlp metadata extraction)
    /merge, /api/merge   -> api.merge.handler (streaming download proxy)
    /health, /healthz    -> 200 OK
    /                    -> index.html, if present
"""
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from api.fetch import handler as FetchHandler  # noqa: E402
from api.merge import handler as MergeHandler  # noqa: E402

ROUTES = {
    "/fetch": FetchHandler,
    "/api/fetch": FetchHandler,
    "/merge": MergeHandler,
    "/api/merge": MergeHandler,
}


class Router(BaseHTTPRequestHandler):
    """Dispatches each request to the matching wrapped handler class."""

    def _target(self):
        path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
        return ROUTES.get(path)

    def _delegate(self, method_name):
        target = self._target()
        if target is None:
            return False

        # Build an instance of the target class that shares this request's
        # state (socket files, headers, path) without re-running __init__,
        # which would try to handle a new request.
        delegate = target.__new__(target)
        delegate.__dict__ = self.__dict__
        getattr(delegate, method_name)()
        return True

    def _send_body(self, status, content_type, body, head_only=False):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _send_json(self, status, payload, head_only=False):
        self._send_body(
            status,
            "application/json; charset=utf-8",
            json.dumps(payload).encode("utf-8"),
            head_only,
        )

    def _static_or_404(self, head_only=False):
        path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"

        if path in {"/health", "/healthz"}:
            return self._send_json(200, {"status": "ok"}, head_only)

        if path in {"/", "/index.html"}:
            index_path = os.path.join(BASE_DIR, "index.html")
            if os.path.isfile(index_path):
                with open(index_path, "rb") as f:
                    body = f.read()
                return self._send_body(200, "text/html; charset=utf-8", body, head_only)

        return self._send_json(404, {"error": "not found"}, head_only)

    def do_GET(self):
        if not self._delegate("do_GET"):
            self._static_or_404()

    def do_HEAD(self):
        if not self._delegate("do_HEAD"):
            self._static_or_404(head_only=True)

    def do_OPTIONS(self):
        if not self._delegate("do_OPTIONS"):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Range, Content-Type")
            self.end_headers()


def main():
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Router)
    print(f"Listening on 0.0.0.0:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
