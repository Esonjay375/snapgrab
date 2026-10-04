from http.server import BaseHTTPRequestHandler
import json, urllib.parse, urllib.request

def extract_media(url):
    # Route TikTok via TikWM
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

    # Route YouTube using active and reliable endpoints
    if "youtube.com" in url or "youtu.be" in url:
        instances = [
            "https://api.cobalt.tools/api/json",
            "https://co.vosh.lol/api/json"
        ]
        
        payload = json.dumps({
            "url": url,
            "vQuality": "720"
        }).encode("utf-8")
        
        for api_url in instances:
            try:
                req = urllib.request.Request(
                    api_url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Origin": "https://cobalt.tools",
                        "Referer": "https://cobalt.tools/"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    status = data.get("status")
                    
                    stream_url = data.get("url")
                    if not stream_url and "picker" in data and len(data["picker"]) > 0:
                        stream_url = data["picker"][0].get("url")
                    
                    if status in ["stream", "redirect", "picker"] and stream_url:
                        return {
                            "title": data.get("filename") or "YouTube Video",
                            "thumbnail": data.get("thumbnail") or "",
                            "formats": [
                                {
                                    "label": "Download Video (MP4)",
                                    "url": stream_url,
                                    "audio": False
                                }
                            ]
                        }
            except Exception:
                continue

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