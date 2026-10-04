from http.server import BaseHTTPRequestHandler
import json, urllib.parse, urllib.request

def extract_media(url):
    # Route TikTok via TikWM (always works)
    if "tiktok.com" in url:
        try:
            req_url = f"https://tikwm.com/api/?url={urllib.parse.quote(url)}"
            req = urllib.request.Request(req_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8")).get("data", {})
                if "play" in data:
                    return {
                        "title": data.get("title") or "TikTok Video",
                        "thumbnail": data.get("cover") or "",
                        "formats": [
                            {"label": "HD No Watermark (MP4)", "url": data.get("hdplay") or data.get("play"), "audio": False},
                            {"label": "Audio Only (MP3)", "url": data.get("music"), "audio": True}
                        ]
                    }
        except Exception:
            pass

    # Route YouTube using a reliable embed & stream player fallback structure
    if "youtube.com" in url or "youtu.be" in url:
        video_id = ""
        if "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0].split("&")[0]
        elif "watch?v=" in url:
            video_id = url.split("watch?v=")[1].split("&")[0]
            
        if video_id:
            return {
                "title": "YouTube Video Playback & Download",
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                "formats": [
                    {
                        "label": "Download via Secure Stream (MP4)",
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "audio": False
                    },
                    {
                        "label": "Watch/Save via Embedded Player",
                        "url": f"https://www.youtube.com/embed/{video_id}",
                        "audio": False
                    }
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

            result = extract_media(url)
            if result:
                return self._send(200, result)

            return self._send(500, {"error": "Failed to extract media. Link may be private or unsupported."})

        except Exception as e:
            self._send(500, {"error": str(e)[:200]})