import http.server
import socketserver
import urllib.parse
from api.fetch import handler as FetchHandler

PORT = 8080

class CombinedHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        if parsed_path.path == "/api/fetch" or parsed_path.path == "/api/fetch.py":
            fetch_instance = FetchHandler(self.request, self.client_address, self)
            return
            
        return super().do_GET()

    def do_OPTIONS(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path.startswith("/api/"):
            fetch_instance = FetchHandler(self.request, self.client_address, self)
            return
        return super().do_OPTIONS()

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True

print(f"SnapGrab server running on http://localhost:{PORT}")
with ThreadedHTTPServer(("", PORT), CombinedHandler) as httpd:
    httpd.serve_forever()
