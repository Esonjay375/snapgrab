from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.parse
import urllib.request

INVIDIOUS_INSTANCES = [
    "https://inv.tux.pizza",
    "https://invidious.nerdvpn.de",
    "https://yewtu.be",
    "https://invidious.privacydev.net",
    "https://iv.melmac.space",
]

def extract_yt_id(url):
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    path = parsed.path.lstrip("/")
    for prefix in ("shorts/", "embed/", "v/"):
        if path.startswith(prefix):
            return path[len(prefix):].split("/")[0].split("?")[0]
    return path.split("/")[0].split("?")[0] or None

def fetch_youtube_data(url):
    vid = extract_yt_id(url)
    if not vid:
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    for base in INVIDIOUS_INSTANCES:
        try:
            req_url = f"{base}/api/v1/videos/{vid}?fields=title,lengthSeconds,videoThumbnails,adaptiveFormats,formatStreams"
            req = urllib.request.Request(req_url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))

            title = data.get("title") or "YouTube Video"
            dur = int(data.get("lengthSeconds") or 0)
            duration = f"{dur // 60}:{dur % 60:02d}"
            
            thumbs = data.get("videoThumbnails") or []
            thumbnail = next((t["url"] for t in thumbs if t.get("quality") in ("high", "medium", "sddefault")), "")
            if thumbnail and thumbnail.startswith("/"):
                thumbnail = base + thumbnail

            video_streams = {}
            audio_url = None
            best_audio_bitrate = 0

            # Collect adaptive streams
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

            # Collect muxed format streams
            for f in data.get("formatStreams") or []:
                furl = f.get("url") or ""
                ftype = f.get("type") or ""
                if not furl or "video/" not in ftype:
                    continue
                res = int(f.get("resolution", "0p").replace("p", "") or 0)
                if res >= 360 and res not in video_streams:
                    video_streams[res] = furl

            formats = []
            for res in sorted(video_streams, reverse=True):
                label = f"{res}p HD" if res >= 720 else f"{res}p"
                formats.append({"label": label, "url": video_streams[res], "audio": False})

            if audio_url:
                formats.append({"label": "Audio MP3", "url": audio_url, "audio": True})

            if formats:
                return {
                    "title": title,
                    "duration": duration,
                    "thumbnail": thumbnail,
                    "formats": formats
                }
        except Exception:
            continue

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
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            url = (qs.get("url") or [""])[0].strip()

            if not url:
                return self._send(400, {"error": "missing url"})

            data = fetch_youtube_data(url)
            if data:
                return self._send(200, data)
            
            return self._send(404, {"error": "Could not fetch video details from YouTube"})

        except Exception as e:
            self._send(500, {"error": str(e)[:200]})
