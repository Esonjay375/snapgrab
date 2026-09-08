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
                "skip_download": True,
                "noplaylist": True,
                "socket_timeout": 25,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if isinstance(info, dict) and info.get("entries"):
                info = info["entries"][0]

            all_formats = info.get("formats", [])

            # Categorize streams:
            # - MUXED: has both video and audio in the same file.
            # - VIDEO_ONLY: video stream with no audio track.
            # - AUDIO_ONLY: true audio stream (vcodec == 'none').
            muxed_streams = {}       # res -> format with audio+video
            video_only_streams = {}  # res -> format with video only (fallback)
            audio_streams = []       # true audio-only formats

            for f in all_formats:
                url_f = f.get("url")
                if not url_f:
                    continue

                vcodec = str(f.get("vcodec") or "").lower()
                acodec = str(f.get("acodec") or "").lower() if f.get("acodec") is not None else None
                format_id = str(f.get("format_id") or "").lower()
                is_dash = "dash" in format_id or "dash" in str(f.get("protocol") or "").lower()

                h = f.get("height") or 0
                w = f.get("width") or 0
                tbr = f.get("tbr") or 0

                # Resolution: use the short side for portrait videos (e.g. 1080x1920 -> 1080)
                res = min(h, w) if (h and w) else (h or w)

                # Has video track?
                has_video = (vcodec != "none" and vcodec != "") or res > 0

                # Has audio track?
                if acodec == "none":
                    has_audio = False
                elif is_dash:
                    has_audio = bool(acodec and acodec != "none")
                else:
                    # Non-DASH progressive streams (Instagram, TikTok, Facebook, etc.)
                    has_audio = True

                # Categorize strictly
                if vcodec == "none" or (not has_video and has_audio):
                    audio_streams.append(f)
                elif has_video and has_audio and res > 0:
                    prev = muxed_streams.get(res)
                    if prev is None:
                        muxed_streams[res] = f
                    else:
                        prev_is_dash = "dash" in str(prev.get("format_id") or "").lower()
                        if prev_is_dash and not is_dash:
                            muxed_streams[res] = f
                        elif not (is_dash and not prev_is_dash) and tbr > (prev.get("tbr") or 0):
                            muxed_streams[res] = f
                elif has_video and not has_audio and res > 0:
                    prev = video_only_streams.get(res)
                    if prev is None or tbr > (prev.get("tbr") or 0):
                        video_only_streams[res] = f

            # Best audio-only stream for MP3
            audio_streams.sort(key=lambda f: f.get("abr") or f.get("tbr") or 0, reverse=True)
            best_audio = audio_streams[0] if audio_streams else None

            def res_label(r):
                if r >= 1080: return "1080p HD"
                if r >= 720:  return "720p"
                if r >= 480:  return "480p"
                if r >= 360:  return "360p"
                return f"{r}p"

            formats = []
            seen_labels = set()

            # 1. ALWAYS PRIORITIZE MUXED STREAMS (WITH AUDIO)
            for res in sorted(muxed_streams, reverse=True):
                label = res_label(res)
                if label in seen_labels:
                    continue
                f = muxed_streams[res]
                formats.append({
                    "label": label,
                    "url": f["url"],
                    "audio": False,
                })
                seen_labels.add(label)

            # 2. Check top-level info["url"] if no muxed streams were found
            if not formats and info.get("url"):
                top_v = str(info.get("vcodec") or "").lower()
                top_a = str(info.get("acodec") or "").lower() if info.get("acodec") is not None else None
                if top_v != "none" and top_a != "none":
                    h = info.get("height") or 0
                    w = info.get("width") or 0
                    res = min(h, w) if (h and w) else (h or w)
                    label = res_label(res) if res else "1080p HD"
                    formats.append({
                        "label": label,
                        "url": info["url"],
                        "audio": False,
                    })
                    seen_labels.add(label)

            # 3. Only if ZERO muxed streams exist anywhere, fallback to video-only
            if not formats:
                for res in sorted(video_only_streams, reverse=True):
                    label = res_label(res)
                    if label in seen_labels:
                        continue
                    f = video_only_streams[res]
                    formats.append({
                        "label": label,
                        "url": f["url"],
                        "audio": False,
                    })
                    seen_labels.add(label)

            # 4. Add Audio MP3 option
            # If a dedicated audio stream exists, use it. Otherwise, use the smallest
            # muxed video stream so the browser can extract the audio track without downloading heavy video.
            if best_audio:
                formats.append({
                    "label": "Audio MP3",
                    "url": best_audio["url"],
                    "audio": True,
                })
            elif muxed_streams:
                smallest_res = min(muxed_streams)
                formats.append({
                    "label": "Audio MP3",
                    "url": muxed_streams[smallest_res]["url"],
                    "audio": True,
                })
            elif info.get("url"):
                formats.append({
                    "label": "Audio MP3",
                    "url": info["url"],
                    "audio": True,
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
