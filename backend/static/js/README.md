# Static JavaScript

## HTMX

`htmx.min.js` is loaded from here first; `base.html` falls back to unpkg if the file is missing or fails.

To vendor locally (recommended for production CSP):

```bash
bash scripts/fetch-htmx.sh
```

## Student UI

`student.js` — client-side discipline catalog search on the student disciplines page.
