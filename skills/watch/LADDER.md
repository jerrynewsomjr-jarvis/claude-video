# Jerry's defaults for /watch (fork jerrynewsomjr-jarvis/claude-video) - READ BEFORE RUNNING ANYTHING

**When Jerry says "watch this", "learn what he says", "study this video": run the FULL WATCH first** (free, no Claude
image tokens): `python "${SKILL_DIR}/scripts/jerry_ladder.py" full "<url-or-file>" --question "<what he wants>"`
-> REPORT.md with every word (timestamped), Guardian's local eyes (frames that matter in every 30 s, sounds, on-screen
text, local vision model). NO Gemini (Jerry 11-02: "I want to make our own thing"). Read REPORT.md, then look at frame sheets yourself
(rung 2) for every moment that matters. A running game is fine (Jerry 11-02: stutter is OK). Long videos: run it in
the background and keep working. For quick questions about a video, use the rungs below instead.

Climb ONE rung at a time and stop as soon as the question is answered. Every frame costs tokens; Jerry is on a
small plan. Script: `${SKILL_DIR}/scripts/jerry_ladder.py` (same folder rules as watch.py).

1. **Transcript only (default).** `python "${SKILL_DIR}/scripts/jerry_ladder.py" transcript "<url-or-file>" --out <file>`
   - YouTube: the video's own captions through Jerry's app (jerry-tools/local-lesson), no download, ~2 s.
   - Local file / no captions: faster-whisper on this PC (offline, free). Read it, then decide if frames are needed.
2. **Frames only where they matter.** Pick timestamps from the transcript - code, settings, websites, a result
   being shown, "look at this", before/after comparisons - then:
   `python "${SKILL_DIR}/scripts/jerry_ladder.py" frames "<url-or-file>" --timestamps 0:05,3:20,6:45 --sheet`
   - Downloads with Jerry's grabber (Newsom Docs, localhost:8090) first, then yt-dlp, then upstream's downloader.
   - 1024 px frames; `--sheet` tiles 3 per row at 640 px (use it unless small text must be read; drop it for code).
3. **Deep watch = OUR full watch** (`full`, above): Guardian's local eyes on the whole video. Gemini and upstream
   `--engine gemini` are OFF - Jerry 11-02 "stop the Gemini stuff ... I want to make our own thing". Never use them unless he asks.
   **Local deep watch with Claude's eyes** (only when he asks): upstream `--engine local --detail token-burner`.

Never paste API keys into chat or files in the repo. Report what you watched (rung, timestamps) in one line.
