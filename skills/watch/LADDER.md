# Jerry's defaults for /watch (fork jerrynewsomjr-jarvis/claude-video) - READ BEFORE RUNNING ANYTHING

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
3. **Deep watch** (only when Jerry says "deep watch" or the visuals ARE the question and rungs 1-2 fall short):
   `python "${SKILL_DIR}/scripts/jerry_ladder.py" deep "<src>" --question "<what to find>"` - walks the flash models
   (free tier: 503 "high demand" spikes, pro = 0 free quota), retries 3x a minute apart, then says to use rung 2.
   Key: GEMINI_API_KEY in `~/.config/watch/.env` (set 11-02).
   **Local deep watch** (only when Jerry says it): upstream `--engine local --detail token-burner` - frames to Claude.

Never paste API keys into chat or files in the repo. Report what you watched (rung, timestamps) in one line.
