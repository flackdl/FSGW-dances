# AGENTS.md

FSGW English Country Dances search app: a static web frontend plus a Python
crawler that builds the dataset it serves.

## Commands

- Refresh data (regenerates data/dances.json):
    .venv/bin/python crawler/crawl.py --refresh
  (`--refresh` re-downloads every source page; omit it to reuse the cache in
  crawler/cache/.)
- First-time setup:
    python3 -m venv .venv && .venv/bin/python -m pip install -r crawler/requirements.txt
- Local preview (must be HTTP, not file://; app.js fetches data/dances.json):
    python3 -m http.server 8899   # open http://127.0.0.1:8899/

No test suite, linter, or build step. Verify by re-running the crawler and
checking the summary it prints (record count, years).

## Gotchas

- Always use .venv/bin/python. System python3 has broken requests/urllib3 and
  no bs4. The venv holds requests, beautifulsoup4, html5lib.
- "Import bs4 could not be resolved" is a false LSP warning (interpreter not
  pointed at .venv). Ignore it.
- data/dances.json (~6.7 MB) is GENERATED and committed. Never hand-edit it;
  edit crawler/crawl.py and re-run. Record schema is in crawler/README.md.
- Keep HTML_PARSER = "html5lib" in crawl.py: html.parser fails on the source's
  malformed/unclosed <tr> markup.
- The source mislabels prioryears/d.called.98.apr-jun.txt (a duplicate of the
  2006 Oct–Dec HTML). The crawler skips it on purpose — don't hand-parse it.

## Frontend

index.html + styles.css + app.js are fully static (no framework/bundler).
app.js loads data/dances.json and does all filtering/sorting/rendering
client-side. Keep the JSON shape backward-compatible.

## Git / deployment

- GitHub Pages serves the repo root of `main` (branch/legacy build; rebuilds on
  push). NOT GitHub Actions — the gh token lacks the `workflow` scope, so
  .github/workflows/* pushes are rejected. Don't add an Actions deploy.
- Push over HTTPS, not SSH. `gh` is authed as `flackdl` (plus an inactive
  `danielflack-noaa` account); SSH push fails with "Permission denied
  (publickey)". The HTTPS remote and `gh auth setup-git` are already set.
