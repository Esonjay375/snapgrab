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

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,     # extract only - no video bytes pass through Vercel
                "noplaylist": True,
                "socket_timeout": 25,
                "format": "bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if isinstance(info, dict) and info.get("entries"):
                info = info["entries"][0]

            # Pass 1: collect MUXED streams (video + audio together) — these have sound
            muxed, seen_mux = [], set()
            audio_fmt = None
            for f in info.get("formats", []):
                if not f.get("url"):
                    continue
                vcodec = f.get("vcodec") or ""
                acodec = f.get("acodec") or ""
                h = f.get("height") or 0

                is_audio_only = vcodec in ("none", "") and acodec not in ("none", "")
                is_muxed = h > 0 and vcodec not in ("none", "") and acodec not in ("none", "")

                if is_audio_only and audio_fmt is None:
                    audio_fmt = f  # keep best audio-only for MP3 option
                elif is_muxed and h not in seen_mux:
                    label = f"{h}p HD" if h >= 1080 else f"{h}p"
                    muxed.append({"label": label, "url": f["url"], "audio": False})
                    seen_mux.add(h)

            formats = muxed[:]

            # Pass 2: if NO muxed streams found, fall back to any video stream (better than nothing)
            if not formats:
                seen_fb = set()
                for f in info.get("formats", []):
                    if not f.get("url"):
                        continue
                    vcodec = f.get("vcodec") or ""
                    h = f.get("height") or 0
                    if h > 0 and vcodec not in ("none", "") and h not in seen_fb:
                        label = f"{h}p HD" if h >= 1080 else f"{h}p"
                        formats.append({"label": label, "url": f["url"], "audio": False})
                        seen_fb.add(h)

            # Add audio-only MP3 option at the end
            if audio_fmt:
                formats.append({"label": "Audio MP3", "url": audio_fmt["url"], "audio": True})

            formats.sort(key=lambda x: (x["audio"], -int("".join(c for c in x["label"] if c.isdigit()) or 0)))
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
