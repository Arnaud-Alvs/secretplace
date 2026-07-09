# Mirabaud — Front Office Investment Portal

Internal research platform for Wealth Management front office.
One URL, one design, one experience across Geneva, Zurich, Basel, Paris, Dubai, and Luxembourg.

**Status:** Phase 1 — Prototype active, productionisation RFP in progress.

## Architecture

```
pages/          → 9 portal HTML files (the application)
data/           → JSON data files (auto-refreshed via Power Automate)
docs/           → Project documentation, specs, architecture notes
source/         → Excel templates for data input (mirrored from SharePoint)
```

## Data flow

```
SharePoint (source Excel) → Power Automate → GitHub API → data/*.json → GitHub Pages serves portal
```

All portal pages load `data/portal-config.json` on init for shared configuration (API key, data paths, strategy content). Each page fetches its specific dataset from `data/`. Manual file upload remains as a fallback if the data endpoint is unreachable.

## Local development

Clone the repo and serve locally:

```bash
# Any static server works — the portal is vanilla HTML/CSS/JS
npx serve .
# or
python -m http.server 8000
```

Then open `http://localhost:8000/pages/portal.html`.

Opening HTML files directly via `file://` works for individual page testing but cross-page data fetching will fail due to CORS. Use a local server for the full connected experience.

## Deployment

GitHub Pages serves from the `main` branch root. The live URL is:

```
https://[username].github.io/mirabaud-portal/pages/portal.html
```

## Team

- **Khaled Louhichi** — Head of Financial Research (vision, content, validation)
- **Serkan Akar** — Investment Data Specialist & AI Steward (architecture, QualIT, deployment)
- **Arnaud Alves** — Project contributor (prototypes, codebase, data integration)

## Confidential

Internal use only. This repository contains aggregated public market data and proprietary analytical frameworks. Do not redistribute externally.
