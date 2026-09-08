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
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if isinstance(info, dict) and info.get("entries"):
                info = info["entries"][0]

            all_formats = info.get("formats", [])

            # Separate video-only, audio-only and muxed streams
            video_streams = {}   # height -> best format
            audio_streams = []   # all audio-only streams sorted by quality
            muxed_streams = {}   # height -> muxed format

            for f in all_formats:
                if not f.get("url"):
                    continue
                vcodec = (f.get("vcodec") or "").lower()
                acodec = (f.get("acodec") or "").lower()
                h      = f.get("height") or 0
                w      = f.get("width")  or 0
                tbr    = f.get("tbr") or 0

                # Use SHORT side as resolution — this handles portrait videos correctly.
                # e.g. Instagram Reel 1080×1920 → res=1080 → "1080p HD" (not "1920p HD")
                res = min(h, w) if (h and w) else (h or w)

                v_present = vcodec and vcodec != "none"
                a_present = acodec and acodec != "none"

                if v_present and a_present and res:
                    # Muxed stream — prefer highest tbr per resolution
                    prev = muxed_streams.get(res)
                    if prev is None or tbr > (prev.get("tbr") or 0):
                        muxed_streams[res] = f
                elif v_present and not a_present and res:
                    # Video-only DASH stream — prefer highest tbr per resolution
                    prev = video_streams.get(res)
                    if prev is None or tbr > (prev.get("tbr") or 0):
                        video_streams[res] = f
                elif a_present and not v_present:
                    # Audio-only stream
                    audio_streams.append(f)

            # Sort audio streams by quality descending, pick best
            audio_streams.sort(key=lambda f: f.get("abr") or f.get("tbr") or 0, reverse=True)
            best_audio = audio_streams[0] if audio_streams else None

            def res_label(res):
                """Convert short-side pixel count to standard quality label."""
                if res >= 1080: return f"{res}p HD" if res == 1080 else "1080p HD"
                if res >= 720:  return "720p"
                if res >= 480:  return "480p"
                if res >= 360:  return "360p"
                return f"{res}p"

            # Build output formats list
            # Priority: muxed > video+audio_url pair > nothing
            formats = []
            seen_res = set()

            # Add muxed streams first (have audio built-in, no merging needed)
            for res in sorted(muxed_streams, reverse=True):
                label = res_label(res)
                if label in seen_res:
                    continue  # skip duplicate quality tiers
                f = muxed_streams[res]
                formats.append({
                    "label": label,
                    "url": f["url"],
                    "audio_url": None,
                    "audio": False,
                })
                seen_res.add(label)

            # Add video-only streams paired with best audio URL so frontend can merge
            if best_audio:
                for res in sorted(video_streams, reverse=True):
                    label = res_label(res)
                    if label in seen_res:
                        continue  # already have this quality tier
                    f = video_streams[res]
                    formats.append({
                        "label": label,
                        "url": f["url"],
                        "audio_url": best_audio["url"],
                        "audio": False,
                    })
                    seen_res.add(label)


            # Also check top-level url (yt-dlp's chosen best single stream)
            # and requested_formats (what yt-dlp would merge for best quality)
            top_url = info.get("url")
            req_fmts = info.get("requested_formats", [])

            # If yt-dlp selected a single muxed stream, use it as fallback
            if top_url and not req_fmts and not any(not f["audio"] for f in formats):
                h = info.get("height") or 0
                w = info.get("width") or 0
                res = min(h, w) if (h and w) else (h or w)
                label = res_label(res) if res else "Best"
                formats.insert(0, {
                    "label": label,
                    "url": top_url,
                    "audio_url": None,
                    "audio": False,
                })

            # If yt-dlp requested separate video+audio for best quality, expose those
            if len(req_fmts) == 2:
                v_rf = next((f for f in req_fmts if (f.get("vcodec") or "") not in ("none","")), None)
                a_rf = next((f for f in req_fmts if (f.get("vcodec") or "") in ("none","")), None)
                if v_rf and a_rf:
                    h = v_rf.get("height") or 0
                    w = v_rf.get("width") or 0
                    res = min(h, w) if (h and w) else (h or w)
                    label = res_label(res) if res else "Best"
                    if not any(f["label"] == label for f in formats):
                        formats.insert(0, {
                            "label": label,
                            "url": v_rf["url"],
                            "audio_url": a_rf["url"],
                            "audio": False,
                        })

            # Audio MP3 option always at the end
            if best_audio:
                formats.append({
                    "label": "Audio MP3",
                    "url": best_audio["url"],
                    "audio_url": None,
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
