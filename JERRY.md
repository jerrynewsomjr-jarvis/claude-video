# Jerry's fork of claude-video (what we changed and why)

Fork of https://github.com/bradautomates/claude-video (MIT) made 2026-11-02 by Jarvis for Jerry Newsom, so Claude can
watch videos on Jerry's PC. Upstream does the heavy lifting (yt-dlp + ffmpeg + captions/Whisper + Gemini engine).

## Our changes (kept small so upstream updates merge cleanly)
| File | Change |
|---|---|
| `skills/watch/LADDER.md` | NEW. The token-saving ladder: transcript -> frames at chosen moments -> deep watch on request. |
| `skills/watch/scripts/jerry_ladder.py` | NEW. Our tools first: captions via jerry-tools/local-lesson, offline faster-whisper, downloads via the Newsom Docs grabber (localhost:8090) then yt-dlp; frames via upstream `watch.py --detail transcript --timestamps ... --resolution 1024`, optional `--sheet` tiling. |
| `skills/watch/SKILL.md` | ONE line after `# /watch` pointing at LADDER.md. Nothing else touched. |
| `JERRY.md`, `CLAUDE.md` (adds `@JERRY.md`), `sync-upstream.ps1` | NEW / one line. |

## Deep watch (Gemini)
Put the key in `%USERPROFILE%\.config\watch\.env` as `GEMINI_API_KEY=...` (never in this repo). Free key: aistudio.google.com/apikey.

## Pull upstream updates without losing ours
`powershell -File sync-upstream.ps1` - fetches bradautomates/claude-video, merges upstream/main into our main
(our files are new files plus one SKILL.md line, so conflicts are rare), runs the tests, pushes to the fork, and
updates the installed plugin. If git reports a conflict in SKILL.md: keep upstream's text and re-add our one pointer line.

## Installed as
`claude plugin marketplace add jerrynewsomjr-jarvis/claude-video` then `claude plugin install watch@claude-video`.
