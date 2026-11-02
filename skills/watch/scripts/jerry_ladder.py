"""Jerry's token-saving ladder for /watch (fork jerrynewsomjr-jarvis/claude-video, added 2026-11-02 by Jarvis).

Rung 1  transcript - OUR tools first. YouTube URL: the video's own captions through jerry-tools/local-lesson (no
                     download, ~2 s). Local file: faster-whisper small.en on this PC (offline, free).
Rung 2  frames     - get the file with OUR grabber (Newsom Docs, localhost:8090), else yt-dlp, then upstream
                     watch.py --detail transcript --timestamps <only the moments that matter> --resolution 1024.
                     --sheet tiles the frames 3 to a row (~60 % fewer image tokens than one image per frame).
Rung 3  deep watch - upstream watch.py --engine gemini (GEMINI_API_KEY in ~/.config/watch/.env).
                     "local deep watch" = upstream --engine local --detail token-burner: only on request.
usage:
  python jerry_ladder.py transcript <url|file> [--out f.txt]
  python jerry_ladder.py fetch <url> [--dir D] [--quality 720]
  python jerry_ladder.py frames <url|file> --timestamps 0:05,3:20 [--resolution 1024] [--sheet] [--out-dir D]
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LESSON = r"C:\Users\jerry\jerry-tools\local-lesson"
GRABBER = "http://localhost:8090"
VIDEO_EXT = (".mp4", ".mkv", ".webm", ".mov", ".m4v")
NOWIN = 0x08000000 if os.name == "nt" else 0          # never flash a console window on Jerry's screen


def is_url(s):
    return bool(re.match(r"^https?://", s or ""))


# ------------------------------------------------------------------ rung 1: transcript
def transcript(src):
    if is_url(src):
        sys.path.insert(0, LESSON)
        try:
            from local_lesson import captions_text          # our app: YouTube's own captions, no download
            text = captions_text(src)
            if text:
                return text, "captions (jerry-tools/local-lesson)"
        except Exception as exc:                             # never fatal: fall through to the file route
            print("our caption route failed: %s" % type(exc).__name__, file=sys.stderr)
        src = fetch(src)
    from faster_whisper import WhisperModel                  # our offline transcriber (Meme Cut / studio)
    model = WhisperModel("small.en", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(src, language="en", beam_size=5, vad_filter=True)
    lines = ["[%d:%02d] %s" % (int(s.start) // 60, int(s.start) % 60, s.text.strip()) for s in segs]
    return "\n".join(lines), "faster-whisper small.en (local)"


# ------------------------------------------------------------------ download: our grabber, then yt-dlp
def _post(path, body):
    req = urllib.request.Request(GRABBER + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def _landed_file(item):
    """the grabber reports where a finished item landed; accept a string, list or dict"""
    found = []

    def walk(v):
        if isinstance(v, str) and v.lower().endswith(VIDEO_EXT) and os.path.exists(v):
            found.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(item.get("landed"))
    return found[0] if found else None


def fetch_grabber(url, quality, timeout=600):
    r = _post("/api/batch", {"urls": [url], "quality": str(quality), "tvserver": False, "device": True})
    bid = r.get("batch_id")
    if not bid:
        raise RuntimeError("grabber refused: %s" % str(r)[:200])
    t0 = time.time()
    while time.time() - t0 < timeout:
        b = json.load(urllib.request.urlopen("%s/api/queue/batch/%s" % (GRABBER, bid), timeout=15)).get("batch") or {}
        c = b.get("counts") or {}
        items = b.get("items") or []
        if c.get("done"):
            path = _landed_file(items[0]) if items else None
            if path:
                return path
            raise RuntimeError("grabber finished but no video file found in 'landed'")
        if c.get("failed") or c.get("cancelled"):
            raise RuntimeError("grabber: %s" % ((items[0].get("message") if items else "") or "failed"))
        time.sleep(4)
    raise RuntimeError("grabber timed out")


def fetch_ytdlp(url, quality, folder):
    os.makedirs(folder, exist_ok=True)
    fmt = "bv*[height<=%s][ext=mp4]+ba[ext=m4a]/b[height<=%s][ext=mp4]/b" % (quality, quality)
    out = os.path.join(folder, "%(id)s.%(ext)s")
    subprocess.run([sys.executable, "-m", "yt_dlp", "-q", "--no-warnings", "--no-playlist", "-f", fmt,
                    "--merge-output-format", "mp4", "-o", out, url], check=True, creationflags=NOWIN)
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", url)
    hits = sorted(glob.glob(os.path.join(folder, (m.group(1) if m else "*") + ".*")), key=os.path.getmtime)
    hits = [h for h in hits if h.lower().endswith(VIDEO_EXT)]
    if not hits:
        raise RuntimeError("yt-dlp produced no video file")
    return hits[-1]


def fetch(url, folder=None, quality=720):
    folder = folder or os.path.join(os.path.expanduser("~"), "holding", "watch-downloads")
    try:
        p = fetch_grabber(url, quality)
        print("downloaded with OUR grabber: %s" % p, file=sys.stderr)
        return p
    except Exception as exc:
        print("grabber route failed (%s) -> yt-dlp" % exc, file=sys.stderr)
    p = fetch_ytdlp(url, quality, folder)
    print("downloaded with yt-dlp: %s" % p, file=sys.stderr)
    return p


# ------------------------------------------------------------------ rung 2: frames only where they matter
def frames(src, timestamps, resolution=1024, out_dir=None, sheet=False):
    if is_url(src):
        src = fetch(src)
    out_dir = out_dir or os.path.join(os.path.dirname(os.path.abspath(src)), "watch-frames")
    cmd = [sys.executable, os.path.join(HERE, "watch.py"), src, "--detail", "transcript", "--timestamps", timestamps,
           "--resolution", str(resolution), "--out-dir", out_dir, "--no-whisper"]
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=NOWIN)
    paths = re.findall(r"`([^`]+cue_\d+\.jpg)` \(t=([0-9:]+)", r.stdout)
    if not paths:
        sys.stderr.write(r.stdout[-1500:] + r.stderr[-800:])
        raise RuntimeError("watch.py returned no cue frames")
    if not sheet:
        return [(p, t) for p, t in paths]
    from PIL import Image, ImageDraw
    per_row, w = 3, 640
    ims = []
    for p, t in paths:
        im = Image.open(p).convert("RGB")
        im = im.resize((w, round(im.height * w / im.width)))
        ImageDraw.Draw(im).text((8, 6), t, fill=(255, 255, 0))
        ims.append((im, t))
    sheets, rows_per_sheet = [], 3
    for s in range(0, len(ims), per_row * rows_per_sheet):
        chunk = ims[s:s + per_row * rows_per_sheet]
        h = max(i.height for i, _ in chunk)
        rows = (len(chunk) + per_row - 1) // per_row
        canvas = Image.new("RGB", (per_row * w + (per_row - 1) * 6, rows * h + (rows - 1) * 6), "white")
        for k, (im, _) in enumerate(chunk):
            canvas.paste(im, ((k % per_row) * (w + 6), (k // per_row) * (h + 6)))
        path = os.path.join(out_dir, "sheet_%02d.jpg" % (len(sheets) + 1))
        canvas.save(path, quality=88)
        sheets.append((path, ",".join(t for _, t in chunk)))
    return sheets


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("transcript"); a.add_argument("src"); a.add_argument("--out")
    b = sub.add_parser("fetch"); b.add_argument("url"); b.add_argument("--dir"); b.add_argument("--quality", default=720)
    c = sub.add_parser("frames"); c.add_argument("src"); c.add_argument("--timestamps", required=True)
    c.add_argument("--resolution", type=int, default=1024); c.add_argument("--out-dir"); c.add_argument("--sheet", action="store_true")
    args = ap.parse_args()
    if args.cmd == "transcript":
        text, via = transcript(args.src)
        if args.out:
            open(args.out, "w", encoding="utf-8").write(text)
            print("transcript via %s -> %s (%d chars)" % (via, args.out, len(text)))
        else:
            sys.stdout.buffer.write(("# transcript via %s\n%s\n" % (via, text)).encode("utf-8"))
    elif args.cmd == "fetch":
        print(fetch(args.url, args.dir, args.quality))
    else:
        for p, t in frames(args.src, args.timestamps, args.resolution, args.out_dir, args.sheet):
            print("%s  (t=%s)" % (p, t))


if __name__ == "__main__":
    main()
