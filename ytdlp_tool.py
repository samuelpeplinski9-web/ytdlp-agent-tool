import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def ensure_ytdlp(auto_install: bool = True) -> bool:
    """Verify yt-dlp is installed, auto-installing via pip if missing."""
    if shutil.which("yt-dlp") is not None:
        return True
    if auto_install:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp"],
                check=True,
                capture_output=True,
                text=True,
            )
            return shutil.which("yt-dlp") is not None
        except subprocess.CalledProcessError:
            return False
    return False


def ensure_ffmpeg(auto_install: bool = True) -> str | None:
    """Locate ffmpeg or auto-install imageio-ffmpeg and expose a standard binary name."""
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg

    local_bin_dir = Path(__file__).resolve().parent / ".bin"
    exe_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    local_ffmpeg = local_bin_dir / exe_name
    if local_ffmpeg.exists():
        return str(local_ffmpeg)

    if not auto_install:
        return None

    try:
        try:
            import imageio_ffmpeg
        except ImportError:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "imageio-ffmpeg"],
                check=True,
                capture_output=True,
                text=True,
            )
            import imageio_ffmpeg

        raw_exe = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if not raw_exe.exists():
            return None

        # yt-dlp expects the binary inside --ffmpeg-location to be named 'ffmpeg'
        local_bin_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(raw_exe, local_ffmpeg)
        except OSError:
            shutil.copy2(raw_exe, local_ffmpeg)
        local_ffmpeg.chmod(0o755)
        return str(local_ffmpeg)
    except Exception:
        return None


def list_formats(url: str, include_storyboards: bool = False) -> dict[str, Any]:
    """Fetch video/audio streams plus available audio languages and subtitle scripts."""
    if not ensure_ytdlp():
        return {"ok": False, "error": "yt-dlp is missing and automatic installation failed."}

    ffmpeg_path = ensure_ffmpeg(auto_install=True)

    try:
        proc = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-playlist", url],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        first_line = proc.stdout.strip().splitlines()[0]
        info = json.loads(first_line)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Timed out while fetching metadata."}
    except subprocess.CalledProcessError as exc:
        return {
            "ok": False,
            "returncode": exc.returncode,
            "error": (exc.stderr or "Failed to retrieve video metadata.").strip(),
        }
    except (json.JSONDecodeError, IndexError) as exc:
        return {"ok": False, "error": f"Invalid JSON output from yt-dlp ({exc})."}

    raw_formats = info.get("formats") or []
    if not raw_formats:
        return {"ok": False, "error": "No downloadable formats found for this URL."}

    formats = []
    audio_languages = set()

    for idx, fmt in enumerate(raw_formats):
        vcodec = fmt.get("vcodec") or "none"
        acodec = fmt.get("acodec") or "none"
        ext = fmt.get("ext", "unknown")
        note = fmt.get("format_note") or ""

        # Skip storyboard preview grids (sb0, sb1, mhtml) unless explicitly requested
        if not include_storyboards and (
            ext == "mhtml" or "storyboard" in note.lower() or (vcodec == "images")
        ):
            continue

        lang = fmt.get("language")
        if lang and acodec != "none":
            audio_languages.add(lang)

        if vcodec != "none" and acodec != "none":
            stream_type = "video+audio"
        elif vcodec != "none":
            stream_type = "video_only (auto-merges with audio)"
        else:
            stream_type = "audio_only"

        formats.append(
            {
                "index": idx,
                "format_id": fmt.get("format_id", ""),
                "type": stream_type,
                "ext": ext,
                "resolution": fmt.get("resolution") or note or "audio only",
                "fps": fmt.get("fps"),
                "language": lang,
                "vcodec": vcodec,
                "acodec": acodec,
                "filesize_bytes": fmt.get("filesize") or fmt.get("filesize_approx"),
            }
        )

    manual_subs = sorted((info.get("subtitles") or {}).keys())
    auto_captions = sorted((info.get("automatic_captions") or {}).keys())

    return {
        "ok": True,
        "title": info.get("title", "Untitled"),
        "duration_seconds": info.get("duration"),
        "ffmpeg_ready": bool(ffmpeg_path),
        "ffmpeg_path": ffmpeg_path,
        "available_audio_languages": sorted(audio_languages),
        "manual_subtitle_languages": manual_subs,
        "auto_caption_languages_sample": auto_captions[:25],
        "total_auto_caption_languages": len(auto_captions),
        "formats": formats,
    }


def build_format_selector(
    format_id: str,
    audio_lang: str | None,
    has_ffmpeg: bool,
) -> str:
    """Build a smart yt-dlp format selector with automatic audio merging and language preference."""
    # Determine preferred audio stream selector
    if audio_lang:
        if audio_lang.lower() == "original":
            audio_sel = "ba[format_note*=original]/ba"
        else:
            audio_sel = f"ba[language^={audio_lang}]/ba"
    else:
        audio_sel = "ba[ext=m4a]/ba"

    # Default 'auto' mode: merge best MP4 video + audio if ffmpeg exists
    if format_id in ("auto", "best"):
        if has_ffmpeg:
            return f"bv*[ext=mp4]+({audio_sel})/bv*+({audio_sel})/b[ext=mp4]/b"
        return "b[ext=mp4]/b"

    # Height shortcuts like '1080p', '720p', '480p'
    if format_id.endswith("p") and format_id[:-1].isdigit() and has_ffmpeg:
        height = format_id[:-1]
        return f"bv*[height<={height}][ext=mp4]+({audio_sel})/bv*[height<={height}]+({audio_sel})/b[height<={height}]"

    # If user picked a single numeric video-only DASH ID (e.g. '137') without '+', pair with audio automatically
    if has_ffmpeg and "+" not in format_id and "/" not in format_id and format_id.isdigit():
        return f"{format_id}+({audio_sel})/{format_id}"

    return format_id


def download_media(
    url: str,
    format_id: str = "auto",
    output_dir: str = "./downloads",
    merge_format: str = "mp4",
    audio_lang: str | None = None,
    sub_langs: str | None = None,
    write_subs: bool = False,
    write_auto_subs: bool = False,
    embed_subs: bool = False,
    sub_format: str = "srt",
    extract_audio: bool = False,
    audio_format: str = "mp3",
) -> dict[str, Any]:
    """Download media with automatic ffmpeg merging, audio language selection, and subtitle scripts."""
    if not ensure_ytdlp():
        return {"ok": False, "error": "yt-dlp is missing and automatic installation failed."}

    ffmpeg_path = ensure_ffmpeg(auto_install=True)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    output_template = str(out_path / "%(title).100B [%(id)s].%(ext)s")

    cmd = ["yt-dlp", "--no-playlist", "--no-simulate"]

    if ffmpeg_path:
        cmd.extend(["--ffmpeg-location", str(Path(ffmpeg_path).parent)])

    if extract_audio:
        cmd.extend(["-f", "ba/b", "-x", "--audio-format", audio_format])
    else:
        resolved_format = build_format_selector(format_id, audio_lang, bool(ffmpeg_path))
        cmd.extend(["-f", resolved_format])
        if ffmpeg_path and merge_format:
            cmd.extend(["--merge-output-format", merge_format])

    # Subtitle & language script options
    if sub_langs or write_subs or write_auto_subs or embed_subs:
        langs = sub_langs or "en.*,en"
        cmd.extend(["--sub-langs", langs])
        if write_subs or (not write_auto_subs):
            cmd.append("--write-subs")
        if write_auto_subs:
            cmd.append("--write-auto-subs")
        if ffmpeg_path and sub_format:
            cmd.extend(["--convert-subs", sub_format])
        if ffmpeg_path and embed_subs:
            cmd.append("--embed-subs")

    cmd.extend(["--print", "after_move:filepath", "-o", output_template, url])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=600,
        )
        saved_files = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        # Also include any standalone .srt/.vtt subtitle files created in output_dir
        subtitle_files = [
            str(p)
            for p in out_path.iterdir()
            if p.suffix.lower() in (".srt", ".vtt", ".ass", ".lrc")
        ]
        return {
            "ok": True,
            "ffmpeg_used": ffmpeg_path,
            "command": cmd,
            "saved_media_files": saved_files,
            "subtitle_files_in_dir": subtitle_files,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Download timed out after 600 seconds."}
    except subprocess.CalledProcessError as exc:
        return {
            "ok": False,
            "returncode": exc.returncode,
            "error": (exc.stderr or "Download command failed.").strip(),
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Arena Agent yt-dlp tool with auto-ffmpeg merging & language/subtitle support."
    )
    parser.add_argument("url", help="Media URL to inspect or download")
    parser.add_argument(
        "--action",
        choices=["list", "download"],
        default="list",
        help="'list' to inspect streams/languages, or 'download' to fetch media",
    )
    parser.add_argument(
        "--format-id",
        default="auto",
        help="'auto' (best MP4+audio), resolution like '1080p'/'720p', single ID like '137' (auto-adds audio), or '137+140'",
    )
    parser.add_argument(
        "--merge-format",
        default="mp4",
        choices=["mp4", "mkv", "webm"],
        help="Container format when merging video and audio (default: mp4)",
    )
    parser.add_argument(
        "--audio-lang",
        default=None,
        help="Preferred audio track language code (e.g., 'en', 'ja', 'es', or 'original')",
    )
    parser.add_argument(
        "--sub-langs",
        default=None,
        help="Subtitle language codes separated by commas (e.g., 'en', 'ja', 'en,ja', 'all')",
    )
    parser.add_argument(
        "--write-subs",
        action="store_true",
        help="Download manual subtitle script files",
    )
    parser.add_argument(
        "--write-auto-subs",
        action="store_true",
        help="Download auto-generated caption script files",
    )
    parser.add_argument(
        "--embed-subs",
        action="store_true",
        help="Embed downloaded subtitles inside the video container as soft-subs",
    )
    parser.add_argument(
        "--sub-format",
        default="srt",
        help="Convert subtitle files to format (default: srt)",
    )
    parser.add_argument(
        "--extract-audio",
        action="store_true",
        help="Download audio only and convert using ffmpeg",
    )
    parser.add_argument(
        "--audio-format",
        default="mp3",
        choices=["mp3", "m4a", "wav", "opus", "flac"],
        help="Audio format when --extract-audio is enabled (default: mp3)",
    )
    parser.add_argument(
        "--output-dir",
        default="./downloads",
        help="Workspace folder for downloaded files",
    )

    args = parser.parse_args()
    if args.action == "list":
        result = list_formats(args.url)
    else:
        result = download_media(
            url=args.url,
            format_id=args.format_id,
            output_dir=args.output_dir,
            merge_format=args.merge_format,
            audio_lang=args.audio_lang,
            sub_langs=args.sub_langs,
            write_subs=args.write_subs,
            write_auto_subs=args.write_auto_subs,
            embed_subs=args.embed_subs,
            sub_format=args.sub_format,
            extract_audio=args.extract_audio,
            audio_format=args.audio_format,
        )

    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
