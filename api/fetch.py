from http.server import BaseHTTPRequestHandler
import json, urllib.parse, urllib.request
import yt_dlp

def extract_ytdlp(url):
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "title": info.get("title", "Downloaded Media"),
            "thumbnail": info.get("thumbnail", ""),
            "duration": f"{info.get('duration', '')}s",
            "formats": [
                {
                    "label": f"Download ({info.get('ext', 'mp4').upper()})",
                    "url": info.get("url"),
                    "audio": False
                }
            ]
        }

def extract_tikwm(url):
    req_url = f"https://tikwm.com/api/?url={urllib.parse.quote(url)}"
    req = urllib.request.Request(req_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=6) as resp:
        data = json.loads(resp.read().decode("utf-8")).get("data", {})
        if "play" in data:
            return {
                "title": data.get("title") or "TikTok Video",
                "thumbnail": data.get("cover") or "",
                "duration": f"{data.get('duration', '')}s",
                "formats": [
                    {"label": "HD No Watermark (MP4)", "url": data.get("hdplay") or data.get("play"), "audio": False},
                    {"label": "Audio Only (MP3)", "url": data.get("music"), "audio": True}
                ]
            }
    return None

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

    def do_GET(self):
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            url = (qs.get("url") or [""])[0].strip()
            if not url:
                return self._send(400, {"error": "Missing URL parameter."})

            result = None
            
            if "tiktok.com" in url:
                try:
                    result = extract_tikwm(url)
                except Exception:
                    pass

            if not result:
                try:
                    result = extract_ytdlp(url)
                except Exception as e:
                    print(f"yt-dlp failed: {e}")

            if result:
                return self._send(200, result)

            return self._send(500, {"error": "Failed to extract media. Link may be private or unsupported."})

        except Exception as e:
            self._send(500, {"error": str(e)[:200]})