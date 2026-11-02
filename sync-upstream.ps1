# Pull bradautomates/claude-video updates into Jerry's fork without losing our changes (see JERRY.md).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
git fetch upstream
$behind = (git rev-list --count HEAD..upstream/main)
if ($behind -eq "0") { "Already up to date with upstream."; exit 0 }
"Merging $behind upstream commit(s)..."
git merge --no-edit upstream/main
if ($LASTEXITCODE -ne 0) { "CONFLICT: resolve it (keep upstream text, re-add our SKILL.md pointer line), then git commit."; exit 1 }
python -m pytest -q 2>&1 | Select-Object -Last 3
git push origin main
claude plugin marketplace update claude-video 2>&1 | Select-Object -Last 2
claude plugin uninstall watch@claude-video 2>&1 | Select-Object -Last 1
claude plugin install watch@claude-video 2>&1 | Select-Object -Last 1
"Done: fork and installed plugin are on the latest upstream + our changes."
