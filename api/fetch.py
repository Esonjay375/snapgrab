from http.server import BaseHTTPRequestHandler
import json, os, urllib.parse
import yt_dlp

# Optional anti-abuse: set ALLOWED_ORIGIN env var in Vercel → e.g. https://yourapp.vercel.app
ALLOWED = os.environ.get("ALLOWED_ORIGIN", "")

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
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        try:
            if ALLOWED:
                ref = (self.headers.get("Referer") or "") + (self.headers.get("Origin") or "")
                if ALLOWED not in ref:
                    return self._send(403, {"error": "forbidden"})

            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            url = (qs.get("url") or [""])[0].strip()
            if not url:
                return self._send(400, {"error": "missing url"})

            # ydl options modified to allow progressive formats (video + audio in one stream)
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
                "socket_timeout": 25,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if isinstance(info, dict) and info.get("entries"):
                info = info["entries"][0]

            formats, seen = [], set()

            # Iterate through available streams
            for f in info.get("formats", []):
                if not f.get("url"):
                    continue

                vcodec = f.get("vcodec")
                acodec = f.get("acodec")
                height = f.get("height")

                # 1. Video formats (prefer progressive formats with audio built-in)
                if vcodec and vcodec != "none" and height:
                    has_audio = acodec and acodec != "none"
                    key = f"video_{height}"
                    
                    if key not in seen:
                        label = f"{height}p" + (" HD" if height >= 720 else "")
                        if not has_audio:
                            label += " (No Audio)"
                            
                        formats.append({
                            "label": label,
                            "url": f["url"],
                            "audio": False
                        })
                        seen.add(key)

                # 2. Audio-only formats
                elif vcodec == "none" and acodec and acodec != "none":
                    if "audio" not in seen:
                        formats.append({
                            "label": "Audio MP3",
                            "url": f["url"],
                            "audio": True
                        })
                        seen.add("audio")

            # 3. Fallback for Images/Photos (e.g., Instagram/Twitter posts)
            if not formats and info.get("url"):
                formats.append({
                    "label": "Download Image",
                    "url": info["url"],
                    "audio": False
                })
            elif not formats and info.get("thumbnail"):
                formats.append({
                    "label": "Download Image/Thumbnail",
                    "url": info["thumbnail"],
                    "audio": False
                })

            # Sort: Video/Images first (highest resolution down), Audio last
            formats.sort(key=lambda x: (
                x["audio"], 
                -int("".join(c for c in x["label"] if c.isdigit()) or 0)
            ))

            if not formats:
                return self._send(404, {"error": "no downloadable formats found"})

            dur = int(info.get("duration") or 0)
            self._send(200, {
                "title": info.get("title") or "Media",
                "duration": f"{dur // 60}:{dur % 60:02d}",
                "thumbnail": info.get("thumbnail") or "",
                "formats": formats,
            })
        except Exception as e:
            self._send(500, {"error": str(e)[:200]})
