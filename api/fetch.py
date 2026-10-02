from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.parse
import urllib.request
import yt_dlp

# Hardcoded cookie fallback in case environment variable is not set
COOKIES_DATA = """# Netscape HTTP Cookie File
# https://curl.haxx.se/rfc/cookie_spec.html
# This is a generated file! Do not edit.
"""

def get_cookie_path(path="/tmp/yt_cookies.txt"):
    """Writes environment variable or fallback cookies to a temporary file for yt-dlp."""
    try:
        custom = os.environ.get("YOUTUBE_COOKIES") or COOKIES_DATA
        if custom and len(custom.strip()) > 50:
            with open(path, "w", encoding="utf-8") as f:
                f.write(custom.strip() + "\n")
            return path
    except Exception:
        pass
    if os.path.exists("cookies.txt"):
        return os.path.abspath("cookies.txt")
    return None

ALLOWED = os.environ.get("ALLOWED_ORIGIN", "")

INVIDIOUS_INSTANCES = [
    "https://inv.tux.pizza",
    "https://invidious.nerdvpn.de",
    "https://yewtu.be",
    "https://invidious.privacydev.net",
    "https://iv.melmac.space",
]

def _yt_video_id(url):
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    path = parsed.path.lstrip("/")
    for prefix in ("shorts/", "embed/", "v/"):
        if path.startswith(prefix):
            return path[len(prefix):].split("/")[0].split("?")[0]
    return path.split("/")[0].split("?")[0] or None

def fetch_youtube_invidious(url):
    vid = _yt_video_id(url)
    if not vid:
        return None

    api_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    for base in INVIDIOUS_INSTANCES:
        try:
            req = urllib.request.Request(
                f"{base}/api/v1/videos/{vid}?fields=title,lengthSeconds,videoThumbnails,adaptiveFormats,formatStreams",
                headers=api_headers,
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))

            title = data.get("title") or "YouTube Video"
            dur = int(data.get("lengthSeconds") or 0)
            duration = f"{dur//60}:{dur%60:02d}"
            thumbs = data.get("videoThumbnails") or []
            thumbnail = next((t["url"] for t in thumbs if t.get("quality") in ("high", "medium", "sddefault")), "")
            if thumbnail and thumbnail.startswith("/"):
                thumbnail = base + thumbnail

            video_streams = {}
            audio_url = None
            best_audio_bitrate = 0

            for f in data.get("adaptiveFormats") or []:
                ftype = f.get("type") or ""
                furl = f.get("url") or ""
                if not furl:
                    continue
                if "video/" in ftype and "vp9" not in ftype.lower():
                    res = int(f.get("resolution", "0p").replace("p", "") or 0)
                    if res >= 360 and res not in video_streams:
                        video_streams[res] = furl
                elif "audio/" in ftype:
                    bitrate = int(f.get("bitrate") or 0)
                    if bitrate > best_audio_bitrate:
                        best_audio_bitrate = bitrate
                        audio_url = furl

            formats = []
            for res in sorted(video_streams, reverse=True):
                label = f"{res}p" if res < 720 else (f"{res}p HD" if res == 1080 else f"{res}p")
                formats.append({"label": label, "url": video_streams[res], "audio": False})

            if audio_url:
                formats.append({"label": "Audio MP3", "url": audio_url, "audio": True})

            if formats:
                return {"title": title, "duration": duration, "thumbnail": thumbnail, "formats": formats}
        except Exception:
            continue

    return None

def fetch_tiktok(url):
    encoded = urllib.parse.quote(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    try:
        req = urllib.request.Request(f"https://www.tikwm.com/api/?url={encoded}", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            if data.get("code") == 0 and data.get("data"):
                d = data["data"]
                formats = []
                if d.get("hdplay"): formats.append({"label": "1080p HD", "url": d["hdplay"], "audio": False})
                if d.get("play"):   formats.append({"label": "720p",    "url": d["play"],   "audio": False})
                if d.get("music"):  formats.append({"label": "Audio MP3","url": d["music"], "audio": True})
                if formats:
                    dur = int(d.get("duration") or 0)
                    return {
                        "title": d.get("title") or "TikTok Video",
                        "duration": f"{dur//60}:{dur%60:02d}",
                        "thumbnail": d.get("cover") or "",
                        "formats": formats
                    }
    except Exception:
        pass
    return None

class handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
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
            if "health" in qs:
                cp = get_cookie_path()
                return self._send(200, {"status": "ok", "has_cookie": bool(cp)})

            url = (qs.get("url") or [""])[0].strip()
            if not url:
                return self._send(400, {"error": "missing url"})

            # Handle TikTok
            if any(k in url.lower() for k in ["tiktok.com", "douyin.com"]):
                tt_data = fetch_tiktok(url)
                if tt_data:
                    return self._send(200, tt_data)

            is_youtube = any(k in url.lower() for k in ["youtube.com", "youtu.be"])
            proxy = os.environ.get("HTTP_PROXY") or os.environ.get("PROXY_URL") or os.environ.get("HTTPS_PROXY")

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": False,
                "ignoreerrors": True,
                "socket_timeout": 20,
            }

            if proxy:
                ydl_opts["proxy"] = proxy

            if is_youtube:
                cp = get_cookie_path()
                if cp:
                    ydl_opts["cookiefile"] = cp

                info = None
                last_exc = None

                # Primary client attempt with iOS/Android emulation
                try:
                    ydl_opts["extractor_args"] = {
                        "youtube": {
                            "player_client": ["ios", "mweb", "android"]
                        }
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                    if not info or not info.get("formats"):
                        raise Exception("No formats returned")
                except Exception as exc:
                    last_exc = exc
                    info = None

                # Fallback client attempts if blocked
                if not info:
                    for client_args in [
                        ["web", "mweb"],
                        ["tv_embedded"],
                        ["android"]
                    ]:
                        try:
                            ydl_opts["extractor_args"] = {"youtube": {"player_client": client_args}}
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                info = ydl.extract_info(url, download=False)
                            if info and info.get("formats"):
                                break
                        except Exception as exc:
                            last_exc = exc
                            info = None

                # Secondary API Fallback if yt-dlp is completely blocked
                if not info:
                    invidious_data = fetch_youtube_invidious(url)
                    if invidious_data:
                        return self._send(200, invidious_data)
                    raise last_exc or Exception("All YouTube extraction strategies failed")

            else:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

            if isinstance(info, dict) and info.get("entries"):
                entries = list(info["entries"])
                info = entries[0] if entries else info

            all_formats = info.get("formats", [])
            formats = []
            seen_resolutions = set()

            for f in all_formats:
                url_f = f.get("url")
                if not url_f or ".m3u8" in url_f:
                    continue

                h = f.get("height") or 0
                w = f.get("width") or 0
                res = min(h, w) if (h and w) else (h or w)

                if res > 0 and res not in seen_resolutions:
                    label = f"{res}p HD" if res >= 720 else f"{res}p"
                    formats.append({
                        "label": label,
                        "url": url_f,
                        "audio": False
                    })
                    seen_resolutions.add(res)

            # Sort formats by resolution descending
            formats.sort(key=lambda x: int(''.join(filter(str.isdigit, x['label'])) or 0), reverse=True)

            # Add fallback Audio entry
            if all_formats:
                best_audio = next((f for f in reversed(all_formats) if f.get("vcodec") == "none" and f.get("url")), all_formats[0])
                formats.append({
                    "label": "Audio MP3",
                    "url": best_audio["url"],
                    "audio": True
                })

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
