from http.server import BaseHTTPRequestHandler
import json, urllib.parse, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Backup instances (verified alive Oct 2026) — used only if the live list is unreachable
BACKUP_INSTANCES = [
    "https://invidious.f5.si",
    "https://invidious.nerdvpn.de",
    "https://inv.nadeko.net",
    "https://yt.chocolatemoo53.com",
    "https://invidious.tiekoetter.com",
]

def get_working_instances():
    """Fetch the public Invidious instance list; return healthy ones, API-enabled first."""
    try:
        req = urllib.request.Request("https://api.invidious.io/instances.json", headers=UA)
        with urllib.request.urlopen(req, timeout=6) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        api_ok, plain = [], []
        for host, meta in raw:
            if meta.get("type") != "https":
                continue
            mon = meta.get("monitor") or {}
            if not mon or mon.get("down"):
                continue
            base = meta.get("uri") or f"https://{host}"
            (api_ok if meta.get("api") else plain).append(base)
        return api_ok + plain or BACKUP_INSTANCES
    except Exception:
        return BACKUP_INSTANCES

def extract_youtube(video_id):
    """Try each healthy Invidious instance until one returns real stream URLs."""
    for base in get_working_instances():
        try:
            api = (f"{base}/api/v1/videos/{video_id}"
                   f"?fields=title,videoThumbnails,formatStreams,adaptiveFormats")
            req = urllib.request.Request(api, headers=UA)
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            title = data.get("title") or "YouTube Video"

            thumb = ""
            for t in data.get("videoThumbnails", []):
                if t.get("quality") == "medium":
                    thumb = t.get("url") or ""

            # Best combined video+audio MP4 stream
            video_fmt = None
            for s in data.get("formatStreams", []):
                if s.get("type", "").startswith("video/mp4") and s.get("url"):
                    video_fmt = s
                    break
            if not video_fmt and data.get("formatStreams"):
                video_fmt = data["formatStreams"][0]

            # Best audio-only stream (usually itag 140 = m4a)
            audio_fmt = None
            for a in data.get("adaptiveFormats", []):
                if a.get("type", "").startswith("audio/mp4") and a.get("url"):
                    audio_fmt = a
                    break

            formats = []
            if video_fmt:
                res = video_fmt.get("resolution") or "MP4"
                formats.append({"label": f"Download Video ({res})",
                                "url": video_fmt["url"], "audio": False})
            else:
                formats.append({"label": "Download Video (MP4)",
                                "url": f"{base}/latest_version?id={video_id}&itag=22",
                                "audio": False})
            if audio_fmt:
                formats.append({"label": "Download Audio (MP3)",
                                "url": audio_fmt["url"], "audio": True})
            else:
                formats.append({"label": "Download Audio (MP3)",
                                "url": f"{base}/latest_version?id={video_id}&itag=140",
                                "audio": True})

            return {"title": title,
                    "thumbnail": thumb or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                    "formats": formats}
        except Exception:
            continue  # instance dead or rate-limited — try the next one
    return None

def extract_media(url):
    # Route TikTok via TikWM
    if "tiktok.com" in url:
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

    # Route YouTube — fixed: multi-instance with real API data
    if "youtube.com" in url or "youtu.be" in url:
        video_id = ""
        if "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0].split("&")[0]
        elif "watch?v=" in url:
            video_id = url.split("watch?v=")[1].split("&")[0]
        elif "/shorts/" in url:
            video_id = url.split("/shorts/")[1].split("?")[0].split("&")[0]

        if video_id:
            result = extract_youtube(video_id)
            if result:
                return result

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