# FSGW Dance Data Crawler

Fetches and parses the FSGW "Dances Called" listings
(https://fsgw2.org/ecd/dancescalled/d.called.html) into a single normalized
JSON dataset (`data/dances.json`).

## Setup (first time)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r crawler/requirements.txt
```

## Refresh the data

```bash
# Re-download every page and regenerate data/dances.json
.venv/bin/python crawler/crawl.py --refresh

# Reuse the on-disk cache (only re-parses; skips unchanged downloads)
.venv/bin/python crawler/crawl.py
```

Raw pages are cached under `crawler/cache/` (git-ignored). The script prints a
per-page record count and writes a summary (`count`, `years`) into the JSON so
you can sanity-check each refresh.

## Output schema

One record per individual dance:

| field             | meaning                                            |
|-------------------|----------------------------------------------------|
| `date`            | ISO date `YYYY-MM-DD`                              |
| `year`/`month`/`day` | numeric components                              |
| `callers`         | list of caller names (split on " and "/" & ")      |
| `caller`          | raw caller text                                    |
| `music`           | musicians / "Recorded"                             |
| `music_type`      | `live` \| `recorded` \| `null`                     |
| `host`            | host name (virtual-dance era) or `null`            |
| `dance`           | dance name                                         |
| `set` / `pos`     | which program column and position within it        |
| `order`           | flat reading order within the evening              |
| `first_after_break` | `~` marker (first dance after mid-evening break)  |
| `starred`         | `*` marker (Spring Ball / footnote)                |
| `notes`           | footnote text or `null`                            |
| `source`          | source page URL                                    |
