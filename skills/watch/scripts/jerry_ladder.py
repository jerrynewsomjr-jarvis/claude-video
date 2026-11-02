"""Jerry's token-saving ladder for /watch (fork jerrynewsomjr-jarvis/claude-video, added 2026-11-02 by Jarvis).

FULL    full <url|file> - words + Guardian eyes (local, ours) -> REPORT.md, no Gemini  (Jerry: "watch and learn this")
Rung 1  transcript - OUR tools first. YouTube URL: the video's own captions through jerry-tools/local-lesson (no
                     download, ~2 s). Local file: faster-whisper small.en on this PC (offline, free).
Rung 2  frames     - get the file with OUR grabber (Newsom Docs, localhost:8090), else yt-dlp, then upstream
                     watch.py --detail transcript --timestamps <only the moments that matter> --resolution 1024.
                     --sheet tiles the frames 3 to a row (~60 % fewer image tokens than one image per frame).
Rung 3  deep watch - OUR full watch (Guardian eyes). Gemini is OFF (Jerry 11-02 "make our own thing"); `deep` kept only if he asks.
                     "local deep watch" = upstream --engine local --detail token-burner: only on request.
usage:
  python jerry_ladder.py transcript <url|file> [--out f.txt]
  python jerry_ladder.py fetch <url> [--dir D] [--quality 720]
  python jerry_ladder.py frames <url|file> --timestamps 0:05,3:20 [--resolution 1024] [--sheet] [--out-dir D]
  python jerry_ladder.py deep <url|file> --question "..." [--rounds 3 --wait 60]   (Gemini, model fallback chain)
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
    first = Image.open(paths[0][0])
    portrait = first.height > first.width                      # Shorts/TikTok: 5 across at 360 px, 2 rows
    per_row, w, rows_per_sheet = (5, 360, 2) if portrait else (3, 640, 3)
    ims = []
    for p, t in paths:
        im = Image.open(p).convert("RGB")
        im = im.resize((w, round(im.height * w / im.width)))
        ImageDraw.Draw(im).text((8, 6), t, fill=(255, 255, 0))
        ims.append((im, t))
    sheets = []
    for s in range(0, len(ims), per_row * rows_per_sheet):
        chunk = ims[s:s + per_row * rows_per_sheet]
        h = max(i.height for i, _ in chunk)
        rows = (len(chunk) + per_row - 1) // per_row
        canvas = Image.new("RGB", (per_row * w + (per_row - 1) * 6, rows * h + (rows - 1) * 6), "white")
        for k, (im, _) in enumerate(chunk):
            canvas.paste(im, ((k % per_row) * (w + 6), (k // per_row) * (h + 6)))
        if max(canvas.size) > 1900:                              # image guard: never hand Claude > 2000 px
            k = 1900 / max(canvas.size)
            canvas = canvas.resize((round(canvas.width * k), round(canvas.height * k)))
        path = os.path.join(out_dir, "sheet_%02d.jpg" % (len(sheets) + 1))
        canvas.save(path, quality=88)
        sheets.append((path, ",".join(t for _, t in chunk)))
    return sheets


# ------------------------------------------------------------------ rung 3: deep watch with model fallback
# 11-02: on the free tier Google answers 503 "high demand" for one flash model while another may be free; pro models
# have 0 free quota (429); older models refuse video (400). So: walk the chain, wait, walk it again.
DEEP_CHAIN = ["gemini-3.7-flash", "gemini-3.8-flash", "gemini-flash-latest", "gemini-3.6-flash", "gemini-3.5-flash"]


def deep(src, question, rounds=3, wait_s=60, out_dir=None):
    out_dir = out_dir or os.path.join(os.path.expanduser("~"), "holding", "watch-deep")
    tried = []
    for r in range(rounds):
        for m in DEEP_CHAIN:
            env = dict(os.environ, WATCH_GEMINI_MODEL=m)
            p = subprocess.run([sys.executable, os.path.join(HERE, "watch.py"), src, "--engine", "gemini",
                                "--question", question, "--out-dir", out_dir], capture_output=True, text=True,
                               env=env, creationflags=NOWIN)
            if "(failed)" not in p.stdout and p.returncode == 0:
                return p.stdout, m
            why = re.search(r"HTTP (\d{3})", p.stdout)
            tried.append("%s:%s" % (m, why.group(1) if why else "?"))
        if r < rounds - 1:
            time.sleep(wait_s)
    raise RuntimeError("deep watch unavailable (Google busy/quota): %s -> use rung 2 (frames + transcript)" % ", ".join(tried))


# ------------------------------------------------------------------ FULL WATCH: everything free, one report
# Jerry 11-02: "I want something built for you to be able to watch videos ... when I send you a video and I tell you
# to watch and learn what this guy says ... it's really to help you." Words + Guardian's local eyes (frames that matter,
# sounds, on-screen text, local vision model) + Gemini when Google has room -> one REPORT.md that Claude reads, then
# Claude looks at frame sheets itself wherever something matters. Game running = fine (stutter is OK, Jerry 11-02).
LITTLE_BRAIN = r"C:\Users\jerry\development\little-brain"
DEFAULT_Q = ("Describe everything that happens with timestamps: what is shown on screen (code, settings, websites, "
             "results, before/after), every step the speaker teaches, every tool and number they name.")
EYES_RUN = ("import sys, runpy; sys.path[:0] = ['.', 'little_brain']; import gamelight; gamelight.active = lambda: False; "
            "sys.argv = ['eyes.py'] + sys.argv[1:]; runpy.run_path('little_brain/eyes.py', run_name='__main__')")


EYES_MODEL, EYES_MAX_FRAMES = "minicpm-v4.5:8b", "64"   # 11-02 test: qwen3-vl:8b 4.5x slower, 12.8 GB RAM, would not critique -> deleted; minicpm stays


def eyes(local, question):
    env = dict(os.environ, GUARDIAN_EYES_MODEL=EYES_MODEL, GUARDIAN_EYES_MAX_FRAMES=EYES_MAX_FRAMES)
    # 11-02: no --ask - the 20B brain that writes that answer took 10-14 GB RAM and got every long watch reaped
    p = subprocess.run([sys.executable, "-c", EYES_RUN, local, "--no-index"], cwd=LITTLE_BRAIN, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NOWIN)
    keep = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.strip() and not re.search(
        r"Warning|warn\(|Creating model|Model files already|Could not find files|Checkpoint path|Using CPU|\x1b", ln)]
    return "\n".join(keep[-400:])


# 11-02: a 12-min watch held too much RAM next to the game + Docker and got reaped. Long videos are cut into 3-min
# pieces (stream copy, no re-encode) and watched one by one; each piece waits for >= 6 GB free RAM.
PIECE_S, MIN_FREE_GB = 180, 6.0


def _free_gb():
    import psutil
    return psutil.virtual_memory().available / 1e9


def _dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True, creationflags=NOWIN)
    return float(r.stdout.strip() or 0)


def _shift(text, off):
    def f(m):
        a = int(m.group(1)) * 60 + int(m.group(2)) + off
        b = int(m.group(3)) * 60 + int(m.group(4)) + off
        return "[%d:%02d - %d:%02d]" % (a // 60, a % 60, b // 60, b % 60)
    return re.sub(r"\[(\d+):(\d\d) - (\d+):(\d\d)\]", f, text)


def eyes_chunked(local, question, out_dir):
    total = _dur(local)
    if total <= PIECE_S + 20:
        return eyes(local, question)
    pdir = os.path.join(out_dir, "pieces")
    os.makedirs(pdir, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", local, "-map", "0", "-c", "copy", "-f", "segment",
                    "-segment_time", str(PIECE_S), "-reset_timestamps", "1", os.path.join(pdir, "piece_%02d.mp4")],
                   check=True, creationflags=NOWIN)
    pieces = sorted(glob.glob(os.path.join(pdir, "piece_*.mp4")))
    parts, off = [], 0.0
    for i, pc in enumerate(pieces):
        waited = 0
        while _free_gb() < MIN_FREE_GB and waited < 900:
            time.sleep(15); waited += 15
        print("[full] piece %d/%d at %d:%02d (%.1f GB free)" % (i + 1, len(pieces), int(off) // 60, int(off) % 60, _free_gb()), file=sys.stderr, flush=True)
        txt = eyes(pc, question)
        parts.append("### piece %d (starts %d:%02d)\n%s" % (i + 1, int(off) // 60, int(off) % 60, _shift(txt, int(off))))
        open(os.path.join(out_dir, "eyes_partial.txt"), "w", encoding="utf-8").write("\n\n".join(parts))
        off += _dur(pc)
    return "\n\n".join(parts)


def full(src, question=None, out_dir=None):
    question = question or DEFAULT_Q
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = out_dir or os.path.join(os.path.expanduser("~"), "holding", "watch-full", stamp)
    os.makedirs(out_dir, exist_ok=True)
    local = fetch(src) if is_url(src) else src
    t0 = time.time()
    text, via = transcript(src)
    open(os.path.join(out_dir, "transcript.txt"), "w", encoding="utf-8").write(text)
    print("[full] words: %s (%d chars, %.0f s)" % (via, len(text), time.time() - t0), file=sys.stderr)
    t1 = time.time()
    ey = eyes_chunked(local, question, out_dir)
    open(os.path.join(out_dir, "eyes.txt"), "w", encoding="utf-8").write(ey)
    print("[full] Guardian eyes done (%.0f s)" % (time.time() - t1), file=sys.stderr)
    gem, gem_note = "", "Gemini OFF (Jerry 11-02: our own tools only)"
    rep = os.path.join(out_dir, "REPORT.md")
    with open(rep, "w", encoding="utf-8") as f:
        f.write("# Full watch: %s\n- source: %s\n- local file: %s\n- words: %s -> transcript.txt\n- %s\n\n"
                % (stamp, src, local, via, gem_note))
        if gem:
            f.write("## Gemini watched it\n%s\n\n" % gem)
        f.write("## Guardian's eyes (local: frames that matter, sounds, on-screen text)\n%s\n\n" % ey)
        f.write("## Next\nLook yourself where it matters: jerry_ladder.py frames \"%s\" --timestamps <from above> --sheet\n" % local)
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("transcript"); a.add_argument("src"); a.add_argument("--out")
    b = sub.add_parser("fetch"); b.add_argument("url"); b.add_argument("--dir"); b.add_argument("--quality", default=720)
    c = sub.add_parser("frames"); c.add_argument("src"); c.add_argument("--timestamps", required=True)
    c.add_argument("--resolution", type=int, default=1024); c.add_argument("--out-dir"); c.add_argument("--sheet", action="store_true")
    fu = sub.add_parser("full"); fu.add_argument("src"); fu.add_argument("--question"); fu.add_argument("--out-dir")
    d = sub.add_parser("deep"); d.add_argument("src"); d.add_argument("--question", required=True)
    d.add_argument("--rounds", type=int, default=3); d.add_argument("--wait", type=int, default=60); d.add_argument("--out-dir")
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
    elif args.cmd == "full":
        print(full(args.src, args.question, args.out_dir))
    elif args.cmd == "deep":
        text, model = deep(args.src, args.question, args.rounds, args.wait, args.out_dir)
        sys.stdout.buffer.write(("# deep watch via %s\n%s" % (model, text)).encode("utf-8"))
    else:
        for p, t in frames(args.src, args.timestamps, args.resolution, args.out_dir, args.sheet):
            print("%s  (t=%s)" % (p, t))


if __name__ == "__main__":
    main()
