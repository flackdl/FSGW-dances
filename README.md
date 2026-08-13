# FSGW Dances Called &mdash; Search & Explore

A searchable web app for the **Folklore Society of Greater Washington (FSGW)**
English Country Dance listings &mdash; every dance called, caller, and musician
at the Glen Echo Town Hall dances from **1997 through the present**.

Live site: <https://flackdl.github.io/FSGW-dances/>

> **Note:** This repository is agent-friendly — it includes an `AGENTS.md`
> with commands and gotchas so AI coding agents (like opencode) can work on it
> efficiently.

## Features

- **Search** across dance names, callers, musicians, and hosts.
- **Filter** by year, month, caller, music type (live / recorded), and the
  `~` (first-after-break) and `*` (starred) markers.
- **Sort** any column (date, dance, caller, musicians).
- **Frequency view** &mdash; rank the most-called dances and the most prolific
  callers; click any entry to jump to every occurrence.

## How it works

The site is entirely static (no build step). `data/dances.json` holds the
normalized dataset, and `app.js` renders it in the browser.

## Refreshing the data

The source listings are updated periodically. To re-crawl and regenerate the
dataset:

```bash
python3 -m venv .venv            # first time only
.venv/bin/python -m pip install -r crawler/requirements.txt
.venv/bin/python crawler/crawl.py --refresh
```

This re-downloads every quarterly page (1997&ndash;present), re-parses it, and
rewrites `data/dances.json`. See [`crawler/README.md`](crawler/README.md) for
details on caching and the output schema.

## Repository layout

```
index.html          Frontend entry point
styles.css          Styling
app.js              Filtering / sorting / rendering logic
data/dances.json    Generated dataset (~16,600 dance records)
crawler/            Crawler + parser (Python)
```
