# ytdlp-agent-tool

A non-interactive, agent-ready `yt-dlp` Python wrapper built for **Arena AI Agent Mode** (LMArena) and local CLI workflows. It replaces blocking terminal `input()` prompts with structured JSON output and command-line flags, while automatically installing `yt-dlp` and `imageio-ffmpeg` inside fresh cloud sandboxes.

## Features

- **Zero-Setup Sandbox Dependencies:** Automatically checks for and installs `yt-dlp` and `imageio-ffmpeg` on first run, linking a clean `ffmpeg` binary in `.bin/` so video + audio streams merge seamlessly.
- **Automatic MP4 Video + Audio Merging:** Pairs high-resolution DASH video streams (`1080p`, `720p`, or raw format IDs like `137`) with audio automatically—no silent video files.
- **Multi-Language Audio & Subtitle Support:** Lists available dubbed audio tracks and subtitle languages, downloads `.srt` scripts, and embeds soft-subtitles directly into MP4 containers.
- **Audio-Only Extraction:** Extracts clean `.mp3`, `.m4a`, `.wav`, `.opus`, or `.flac` audio tracks.
- **Structured JSON Output:** Returns clean JSON metadata and file paths so AI agents can read results without parsing messy terminal logs.

---

## Quick Start in Arena AI Agent Mode

1. Open [Arena AI Agent Mode](https://arena.ai).
2. In the right-hand **Workspace** panel, click **`+` next to Connectors** and connect this GitHub repository (`ytdlp-agent-tool`, `main` branch).
3. Ask the agent in chat to inspect or download any supported URL using `ytdlp_tool.py`.

### Example Chat Prompts for Arena Agent

- **Inspect formats & languages:**
  > Run `ytdlp_tool.py` with `--action list` on `<URL>` and show me the available resolutions, audio languages, and subtitle codes in a table.

- **Download merged 1080p MP4 with audio:**
  > Run `ytdlp_tool.py` on `<URL>` with `--action download --format-id 1080p`.

- **Download 720p MP4 + English `.srt` subtitles (saved & embedded):**
  > Run `ytdlp_tool.py` on `<URL>` with `--action download --format-id 720p --sub-langs en --write-subs --write-auto-subs --embed-subs`.

---

## CLI Reference

```bash
# Show all available flags
python ytdlp_tool.py --help

# 1. List available formats, audio languages, and subtitle codes
python ytdlp_tool.py "<URL>" --action list

# 2. Download best available MP4 video + merged audio automatically
python ytdlp_tool.py "<URL>" --action download --format-id auto

# 3. Download by resolution shortcut (auto-merges video + audio)
python ytdlp_tool.py "<URL>" --action download --format-id 1080p
python ytdlp_tool.py "<URL>" --action download --format-id 720p

# 4. Download with specific dubbed audio language (e.g., Japanese, English, or original)
python ytdlp_tool.py "<URL>" --action download --format-id 1080p --audio-lang ja
python ytdlp_tool.py "<URL>" --action download --format-id 1080p --audio-lang original

# 5. Download manual/auto subtitles as .srt and embed soft-subs into the MP4
python ytdlp_tool.py "<URL>" --action download --format-id 720p --sub-langs "en,ja" --write-subs --write-auto-subs --embed-subs

# 6. Extract audio only as MP3
python ytdlp_tool.py "<URL>" --action download --extract-audio --audio-format mp3
```

### Arguments Summary

| Flag | Default | Description |
| :--- | :--- | :--- |
| `url` | *(Required)* | Media URL to inspect or download |
| `--action` | `list` | `list` to inspect streams/languages, or `download` to save media |
| `--format-id` | `auto` | `auto`, height like `1080p`/`720p`/`480p`, single ID (`137`), or combined (`137+140`) |
| `--merge-format` | `mp4` | Output container when merging video and audio (`mp4`, `mkv`, `webm`) |
| `--audio-lang` | `None` | Preferred audio track language code (`en`, `ja`, `es`, or `original`) |
| `--sub-langs` | `None` | Comma-separated subtitle language codes (`en`, `en,ja`, `all`) |
| `--write-subs` | `False` | Save manual subtitle script files to `./downloads` |
| `--write-auto-subs` | `False` | Save auto-generated caption files to `./downloads` |
| `--embed-subs` | `False` | Embed subtitles inside the video file as selectable soft-subs |
| `--sub-format` | `srt` | Subtitle conversion format (`srt`, `vtt`, `ass`) |
| `--extract-audio` | `False` | Download audio only and convert via `ffmpeg` |
| `--audio-format` | `mp3` | Target audio format when extracting (`mp3`, `m4a`, `wav`, `opus`, `flac`) |
| `--output-dir` | `./downloads` | Target directory for saved media and subtitle files |

---

## Exporting Files From Arena Agent Mode

### Files Under 128 MB (Native Workspace Download)
Arena Agent Mode workspaces sync up to **128.0 MB**. If your downloaded media is under 128 MB (and you are not in GitHub PR mode):
- Append `/download-workspace` to the end of your Arena chat URL (`https://arena.ai<chat-id>/download-workspace`), **or**
- Click the **`↓` download icon** in the top-right corner of the Workspace panel.

### Large Files Over 128 MB (GoFile Direct Upload)
If a high-resolution video exceeds Arena's 128 MB workspace sync budget (or if GitHub Connector PR mode is active), paste this prompt into Arena chat so the agent zips and uploads `./downloads` to GoFile and prints a direct `https://` link:

```text
Zip ./downloads (and ytdlp_tool.py if needed, excluding .bin) into /tmp/export.zip, upload it to GoFile with this command, print the https:// download link, and delete /tmp/export.zip afterward:

python3 -c '
import json, subprocess
srv = json.loads(subprocess.check_output(["curl", "-s", "https://gofile.io"], text=True))["data"]["servers"][0]["name"]
res = json.loads(subprocess.check_output(["curl", "-s", "-F", "file=@/tmp/export.zip", f"https://{srv}.gofile.io/uploadFile"], text=True))
print("DOWNLOAD LINK:", res["data"]["downloadPage"])
'
```

---

## Local Usage (Windows / macOS / Linux)

You can also run `ytdlp_tool.py` directly on your own computer with Python 3.10+ (no size limits):

```bash
pip install -U yt-dlp imageio-ffmpeg
python ytdlp_tool.py "<URL>" --action download --format-id 1080p
```
