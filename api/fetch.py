from http.server import BaseHTTPRequestHandler
import json, os, urllib.parse
import yt_dlp

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

                for f in info.get("formats", []):
                    if not f.get("url"):
                        continue

                    # Capture Audio
                    if f.get("vcodec") == "none" and f.get("acodec") != "none":
                        if "audio" not in seen:
                            formats.append({"label": "Audio MP3", "url": f["url"], "audio": True})
                            seen.add("audio")

                    # Capture Video (Progressive or Combined Formats)
                    elif f.get("height") and f.get("vcodec") != "none":
                        h = f["height"]
                        # Filter to standard resolutions or any valid video height
                        if h not in seen:
                            # Prefer formats that contain both video and audio if direct links are used
                            has_audio = f.get("acodec") != "none"
                            label = f"{h}p" + (" HD" if h >= 720 else "")
                            if not has_audio:
                                label += " (No Audio)"

                            formats.append({
                                "label": label,
                                "url": f["url"],
                                "audio": False
                            })
                            seen.add(h)

                # Sort: Video first (highest resolution down), then Audio
                formats.sort(key=lambda x: (
                    x["audio"], 
                    -int("".join(c for c in x["label"] if c.isdigit()) or 0)
                ))

                if not formats:
                    return self._send(404, {"error": "no downloadable formats found"})

                dur = int(info.get("duration") or 0)
                self._send(200, {
                    "title": info.get("title") or "Video",
                    "duration": f"{dur // 60}:{dur % 60:02d}",
                    "thumbnail": info.get("thumbnail") or "",
                    "formats": formats,
                })

        except Exception as e:
            self._send(500, {"error": str(e)[:200]})
