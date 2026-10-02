from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.parse
import yt_dlp

ALLOWED = os.environ.get("ALLOWED_ORIGIN", "")


def is_youtube_url(url):
    host = urllib.parse.urlparse(url).netloc.lower()
    return any(domain in host for domain in [
        "youtube.com",
        "youtu.be",
        "youtube-nocookie.com",
    ])


def is_tiktok_url(url):
    host = urllib.parse.urlparse(url).netloc.lower()
    return any(domain in host for domain in [
        "tiktok.com",
        "vm.tiktok.com",
        "vt.tiktok.com",
        "douyin.com",
    ])


def clean_title(value):
    value = value or "Video"
    return str(value).strip()[:200]


def duration_label(seconds):
    try:
        seconds = int(seconds or 0)
    except (ValueError, TypeError):
        seconds = 0

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining = seconds % 60

    if hours:
        return f"{hours}:{minutes:02d}:{remaining:02d}"
    return f"{minutes}:{remaining:02d}"


def resolution_label(height, width):
    try:
        height = int(height or 0)
        width = int(width or 0)
    except (ValueError, TypeError):
        return "Video"

    resolution = min(height, width) if height and width else (height or width)

    if resolution >= 2160:
        return "4K"
    if resolution >= 1440:
        return "1440p"
    if resolution >= 1080:
        return "1080p HD"
    if resolution >= 720:
        return "720p"
    if resolution >= 480:
        return "480p"
    if resolution >= 360:
        return "360p"
    if resolution:
        return f"{resolution}p"
    return "Video"


def get_ytdlp_options():
    return {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 45,
        "retries": 2,
        "extractor_retries": 2,
        "fragment_retries": 2,
        "geo_bypass": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    }


def extract_with_fallbacks(url):
    """
    Attempt normal yt-dlp extraction, then try YouTube player-client fallbacks.
    Returns a single-video info dictionary or raises the last useful error.
    """
    attempts = [
        None,
        {
            "youtube": {
                "player_client": ["web_creator", "mweb", "tv_embedded"]
            }
        },
        {
            "youtube": {
                "player_client": ["tv_embedded"]
            }
        },
        {
            "youtube": {
                "player_client": ["web"]
            }
        },
    ]

    last_error = None

    for extractor_args in attempts:
        options = get_ytdlp_options()

        proxy = (
            os.environ.get("HTTPS_PROXY")
            or os.environ.get("HTTP_PROXY")
            or os.environ.get("PROXY_URL")
        )
        if proxy:
            options["proxy"] = proxy

        if extractor_args:
            options["extractor_args"] = extractor_args

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                raise RuntimeError("No data was returned by yt-dlp")

            # Should not occur with noplaylist=True, but safely handle it.
            if isinstance(info, dict) and info.get("entries"):
                entries = [entry for entry in info.get("entries", []) if entry]
                if not entries:
                    raise RuntimeError("The playlist does not contain an available video")
                info = entries[0]

            if not isinstance(info, dict):
                raise RuntimeError("yt-dlp returned an invalid response")

            if info.get("formats") or info.get("url"):
                return info

            raise RuntimeError("No downloadable formats were returned")

        except Exception as error:
            last_error = error

    raise last_error or RuntimeError("All video extraction methods failed")


def build_formats(info):
    """
    Return direct source URLs grouped as:
    - Progressive/muxed video (video + audio)
    - Video-only streams when no progressive stream exists at a given quality
    - Best available audio stream

    Note: Video-only DASH streams need FFmpeg merging with audio for a finished
    file that includes sound. Vercel cannot reliably perform that merge.
    """
    all_formats = info.get("formats") or []

    muxed = {}
    video_only = {}
    audio_only = []

    for fmt in all_formats:
        stream_url = fmt.get("url")
        if not stream_url:
            continue

        protocol = str(fmt.get("protocol") or "").lower()
        ext = str(fmt.get("ext") or "").lower()
        vcodec = str(fmt.get("vcodec") or "").lower()
        acodec = str(fmt.get("acodec") or "").lower()

        # Ignore image/storyboard formats. Keep HLS out because browser downloads
        # of manifests often do not create a real media file.
        if ext in {"mhtml", "jpg", "jpeg", "png", "webp", "gif"}:
            continue
        if "storyboard" in stream_url:
            continue
        if "m3u8" in protocol or ".m3u8" in stream_url:
            continue

        try:
            height = int(fmt.get("height") or 0)
            width = int(fmt.get("width") or 0)
        except (ValueError, TypeError):
            height, width = 0, 0

        resolution = min(height, width) if height and width else (height or width)
        bitrate = float(fmt.get("tbr") or fmt.get("abr") or 0)

        has_video = vcodec not in {"", "none"}
        has_audio = acodec not in {"", "none"}

        if not has_video and has_audio:
            audio_only.append(fmt)
            continue

        if has_video and has_audio and resolution:
            existing = muxed.get(resolution)
            if not existing or bitrate > float(existing.get("tbr") or 0):
                muxed[resolution] = fmt
            continue

        if has_video and not has_audio and resolution:
            existing = video_only.get(resolution)
            if not existing or bitrate > float(existing.get("tbr") or 0):
                video_only[resolution] = fmt

    formats = []
    seen = set()

    # Give the user progressive formats first: these contain both video and audio.
    for resolution in sorted(muxed.keys(), reverse=True):
        fmt = muxed[resolution]
        label = resolution_label(fmt.get("height"), fmt.get("width"))

        if label in seen:
            continue

        formats.append({
            "label": label,
            "url": fmt["url"],
            "audio": False,
            "hasAudio": True,
            "needsMerge": False,
            "ext": fmt.get("ext") or "mp4",
        })
        seen.add(label)

    # Add video-only streams only if the same quality wasn't already available muxed.
    # Mark them clearly so the frontend can explain that high-resolution audio
    # requires a dedicated FFmpeg worker.
    for resolution in sorted(video_only.keys(), reverse=True):
        fmt = video_only[resolution]
        label = resolution_label(fmt.get("height"), fmt.get("width"))

        if label in seen:
            continue

        formats.append({
            "label": f"{label} (video only)",
            "url": fmt["url"],
            "audio": False,
            "hasAudio": False,
            "needsMerge": True,
            "ext": fmt.get("ext") or "mp4",
        })
        seen.add(label)

    # Find the best audio-only format.
    audio_only.sort(
        key=lambda fmt: float(fmt.get("abr") or fmt.get("tbr") or 0),
        reverse=True,
    )

    if audio_only:
        best_audio = audio_only[0]
        formats.append({
            "label": "Audio source",
            "url": best_audio["url"],
            "audio": True,
            "hasAudio": True,
            "needsMerge": False,
            "ext": best_audio.get("ext") or "m4a",
        })

    # Final fallback if yt-dlp returned one already-selected URL.
    if not formats and info.get("url"):
        formats.append({
            "label": "Video",
            "url": info["url"],
            "audio": False,
            "hasAudio": True,
            "needsMerge": False,
            "ext": info.get("ext") or "mp4",
        })

    return formats


class handler(BaseHTTPRequestHandler):
    def send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        try:
            if ALLOWED:
                origin = self.headers.get("Origin") or ""
                referer = self.headers.get("Referer") or ""

                if ALLOWED not in origin and ALLOWED not in referer:
                    return self.send_json(403, {
                        "error": "forbidden"
                    })

            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            url = (query.get("url") or [""])[0].strip()

            if not url:
                return self.send_json(400, {
                    "error": "missing url"
                })

            if not url.startswith(("https://", "http://")):
                return self.send_json(400, {
                    "error": "invalid url"
                })

            # This endpoint is intentionally optimized for YouTube first.
            # yt-dlp may support other public video URLs, but each platform
            # changes independently and can require a dedicated extractor.
            info = extract_with_fallbacks(url)
            formats = build_formats(info)

            if not formats:
                return self.send_json(404, {
                    "error": "no downloadable formats found"
                })

            return self.send_json(200, {
                "title": clean_title(info.get("title")),
                "duration": duration_label(info.get("duration")),
                "thumbnail": info.get("thumbnail") or "",
                "source": "youtube" if is_youtube_url(url) else "other",
                "formats": formats,
            })

        except Exception as error:
            # Sends the real backend reason to help debugging. Do not expose
            # private cookies, credentials, or raw stack traces.
            message = str(error).replace("\n", " ").strip()[:350]

            return self.send_json(500, {
                "error": "Could not fetch video details",
                "detail": message or "Unknown extraction error"
            })
