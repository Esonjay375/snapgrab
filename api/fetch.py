from http.server import BaseHTTPRequestHandler
import json, urllib.parse, urllib.request

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def extract_tiktok(url):
    try:
        req_url = f"https://tikwm.com/api/?url={urllib.parse.quote(url)}"
        req = urllib.request.Request(req_url, headers=UA)
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
    return None

def pick_best(fmt_list, key, reverse=True):
    return max(fmt_list, key=key) if fmt_list else None

def extract_youtube(video_id):
    if yt_dlp is None:
        raise RuntimeError("yt-dlp not installed — add it to requirements.txt")

    url = f"https://www.youtube.com/watch?v={video_id}"
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 15,
        "extractor_retries": 2,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    fmts = info.get("formats") or []

    # Combined video+audio in one file (progressive) — these always play with sound
    progressive = [f for f in fmts
                   if f.get("vcodec") not in (None, "none")
                   and f.get("acodec") not in (None, "none")
                   and f.get("ext") == "mp4"
                   and f.get("url")]
    best_prog = pick_best(progressive, lambda f: f.get("height") or 0)

    # Audio-only streams
    audio_only = [f for f in fmts
                  if f.get("vcodec") in (None, "none")
                  and f.get("acodec") not in (None, "none")
                  and f.get("url")]
    # Prefer m4a (universal), then anything else by bitrate
    audio_only.sort(key=lambda f: ((f.get("ext") == "m4a"), f.get("abr") or 0), reverse=True)
    best_audio = audio_only[0] if audio_only else None

    formats = []
    if best_prog:
        res = best_prog.get("height")
        formats.append({
            "label": f"Download Video ({res}p MP4)" if res else "Download Video (MP4)",
            "url": best_prog["url"],
            "audio": False
        })
    if best_audio:
        ext = (best_audio.get("ext") or "m4a").upper()
        formats.append({
            "label": f"Download Audio ({ext})",
            "url": best_audio["url"],
            "audio": True
        })

    if not formats:
        raise RuntimeError("No downloadable streams found — video may be age-restricted or members-only")

    return {
        "title": info.get("title") or "YouTube Video",
        "thumbnail": info.get("thumbnail") or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        "formats": formats
    }

def extract_media(url):
    if "tiktok.com" in url:
        r = extract_tiktok(url)
        if r:
            return r

    if "youtube.com" in url or "youtu.be" in url:
        video_id = ""
        if "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0].split("&")[0]
        elif "watch?v=" in url:
            video_id = url.split("watch?v=")[1].split("&")[0]
        elif "/shorts/" in url:
            video_id = url.split("/shorts/")[1].split("?")[0].split("&")[0]
        elif "/live/" in url:
            video_id = url.split("/live/")[1].split("?")[0].split("&")[0]

        if video_id:
            return extract_youtube(video_id)  # raises with a real error message on failure

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
            parsed = urllib.parse.urlparse(self.path)

            # Optional proxy endpoint: /download?u=<urlencoded-stream-url>
            # Use this if a direct googlevideo link fails in the browser (IP binding)
            if parsed.path == "/download":
                return self._proxy_download(parsed)

            qs = urllib.parse.parse_qs(parsed.query)
            url = (qs.get("url") or [""])[0].strip()
            if not url:
                return self._send(400, {"error": "Missing URL parameter."})

            result = extract_media(url)
            if result:
                return self._send(200, result)

            return self._send(500, {"error": "Failed to extract media. Link may be private or unsupported."})

        except Exception as e:
            self._send(500, {"error": str(e)[:300]})

    def _proxy_download(self, parsed):
        qs = urllib.parse.parse_qs(parsed.query)
        target = (qs.get("u") or [""])[0]
        if not target.startswith("http"):
            return self._send(400, {"error": "Bad download URL"})
        try:
            req = urllib.request.Request(target, headers=UA)
            upstream = urllib.request.urlopen(req, timeout=30)
            self.send_response(200)
            self.send_header("Content-Type",
                upstream.headers.get("Content-Type", "application/octet-stream"))
            cd = upstream.headers.get("Content-Disposition")
            if cd:
                self.send_header("Content-Disposition", cd)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            while True:
                chunk = upstream.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except Exception as e:
            try:
                self._send(500, {"error": str(e)[:200]})
            except Exception:
                pass