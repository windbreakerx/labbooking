# Static JavaScript

## HTMX

`htmx.min.js` is loaded from here first; `base.html` falls back to unpkg if the file is missing or fails.

To vendor locally (recommended for production CSP):

```bash
bash scripts/fetch-htmx.sh
```

## Alpine.js

`alpine.min.js` is loaded from this directory in `base.html` (self-hosted, no CDN fallback in production path).

To vendor locally:

```bash
bash scripts/fetch-alpine.sh
```

## Student UI

`student.js` — client-side discipline catalog search on the student disciplines page.
