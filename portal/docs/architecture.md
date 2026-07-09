# Unified Portal Architecture — SharePoint as Backbone
## Technical Specification

**Mirabaud Financial Research** · July 2026 · Internal

---

## 1. The shift: from loose files to a connected portal

Today the portal is 9 separate HTML files shared via email or Teams. Each is an island — they link to each other in the nav bar but share nothing: no data, no config, no state. The API key is entered separately in each tool. Updating one page means redistribiting a file. There is no single URL an advisor can bookmark.

The fix: **host the entire portal on a single SharePoint document library**. This does three things at once. It gives every advisor one URL (`https://mirabaud.sharepoint.com/sites/ResearchPortal/Pages/portal.html`). It makes all pages same-origin so they can fetch shared data from a central folder without CORS issues. And it keeps everything within Research's control — no IT project, no vendor dependency, just a SharePoint site.

This isn't the full production deployment (that's the vendor's job on `mirabaud-compass.com`). This is the operational bridge that makes Phase 1 tools usable at scale while Track 1 runs in parallel.

---

## 2. Architecture overview

```
SharePoint Site: "Research Portal"
│
├── Pages/                            ← All portal HTML files (the application)
│   ├── portal.html                   ← Homepage / shell
│   ├── equity_screener.html          ← Equity screener
│   ├── fixed_income.html             ← FI screener
│   ├── structured_products.html      ← Structured products
│   ├── esg_sri.html                  ← ESG & SRI
│   ├── funds_etf.html                ← Funds & ETFs
│   ├── thematics_amc.html            ← Thematic baskets / AMC
│   ├── research.html                 ← Research notes
│   └── admin.html                    ← Content management
│
├── Data/                             ← Central data store (JSON files)
│   ├── portal-config.json            ← Shared config: API key, nav, settings
│   ├── equity-universe.json          ← ~590 securities, refreshed from BBG
│   ├── research-notes.json           ← All publications metadata
│   ├── investment-ideas.json         ← Ideas by asset class
│   ├── advisory-narrative.json       ← Strategy bar content (IC msg, narrative)
│   ├── fi-universe.json              ← Phase 2: 254 FI issuers
│   ├── fund-list.json                ← Phase 2: 87 approved funds
│   ├── esg-data.json                 ← Phase 2: ESG scores
│   └── last-update.json              ← Timestamps for all data sources
│
├── Source/                           ← Raw files Khaled uploads (input)
│   ├── Equity/
│   │   └── BBG_RAW_latest.xlsx
│   ├── Fixed Income/
│   │   └── FI_universe.xlsx          ← Phase 2
│   ├── Research/
│   │   ├── ideas.xlsx                ← Investment ideas master file
│   │   └── notes.xlsx                ← Research notes master file
│   └── Strategy/
│       ├── narrative.docx            ← Advisory narrative + IC message
│       └── wim_latest.pdf            ← Weekly Investment Meeting PDF
│
├── Publications/                     ← PDF reports accessible from the portal
│   ├── Equity/
│   ├── Fixed Income/
│   ├── Structured Products/
│   ├── ESG/
│   └── Funds/
│
└── Archive/                          ← Auto-archived previous versions
    └── Equity/
        └── BBG_RAW_2026-07-09.xlsx
```

---

## 3. The shared config file — `portal-config.json`

This is the glue. Every portal page loads it first. It replaces the scattered API key inputs, hardcoded data, and inconsistent settings across pages.

```json
{
  "version": "1.2",
  "updated": "2026-07-09T14:30:00Z",
  "dataRoot": "../Data/",
  "pubRoot": "../Publications/",

  "apiKey": "",

  "strategy": {
    "narrative": "Central banks remain on hold amid resilient labour markets and sticky services inflation.\n\nEquity valuations are pricing in a soft landing — selectivity is key.\n\nIn Fixed Income, short duration IG corporates offer compelling carry.\n\nThematic focus: AI infrastructure and European defence remain our top convictions.",
    "icMessage": "Maintain overweight Equities vs Fixed Income.\nWithin equities, favour Quality Growth over Value.\nIn FI, stay short duration with preference for IG credit over govies.\nContinue to reduce USD exposure as Fed divergence widens vs ECB.",
    "icDate": "7 July 2026"
  },

  "dataSources": {
    "equity":    { "file": "equity-universe.json",    "label": "Equity Universe",     "updated": null },
    "fi":        { "file": "fi-universe.json",         "label": "FI Universe",         "updated": null },
    "ideas":     { "file": "investment-ideas.json",    "label": "Investment Ideas",     "updated": null },
    "research":  { "file": "research-notes.json",      "label": "Research Notes",       "updated": null },
    "funds":     { "file": "fund-list.json",           "label": "Fund List",            "updated": null },
    "esg":       { "file": "esg-data.json",            "label": "ESG Data",             "updated": null },
    "narrative": { "file": "advisory-narrative.json",  "label": "Advisory Narrative",   "updated": null }
  }
}
```

### How pages use it

Every portal page includes a shared loader at the top of its `<script>` block:

```javascript
// ════════════════════════════════════════════════════
// PORTAL SHARED LOADER — reads portal-config.json
// ════════════════════════════════════════════════════
var PORTAL = { config: null, dataRoot: '../Data/' };

async function loadPortalConfig() {
  try {
    var resp = await fetch('../Data/portal-config.json', { credentials: 'include' });
    if (!resp.ok) return false;
    PORTAL.config = await resp.json();
    PORTAL.dataRoot = PORTAL.config.dataRoot || '../Data/';
    // Load shared API key
    if (PORTAL.config.apiKey) window._AK = PORTAL.config.apiKey;
    return true;
  } catch(e) {
    console.log('[portal] Config not available — standalone mode');
    return false;
  }
}

async function loadPortalData(sourceKey) {
  if (!PORTAL.config) return null;
  var src = PORTAL.config.dataSources[sourceKey];
  if (!src || !src.file) return null;
  try {
    var resp = await fetch(PORTAL.dataRoot + src.file, { credentials: 'include' });
    if (!resp.ok) return null;
    return await resp.json();
  } catch(e) {
    console.log('[portal] Could not load', sourceKey);
    return null;
  }
}
```

### What this changes in each page

| Page | Currently | With shared config |
|---|---|---|
| **portal.html** | Ideas/notes hardcoded in JS, narrative hardcoded in HTML, API key entered per session | Fetches `research-notes.json`, `investment-ideas.json`, reads narrative from config |
| **equity_screener** | Manual file upload required on each session | Auto-loads `equity-universe.json` on init, file upload as fallback |
| **fixed_income** | Manual data (Phase 2) | Fetches `fi-universe.json` |
| **funds_etf** | Hardcoded fund list | Fetches `fund-list.json` |
| **esg_sri** | Hardcoded data | Fetches `esg-data.json` |
| **admin.html** | Edits localStorage or HTML directly | Writes to SharePoint `Data/` folder via SP REST API |
| **All pages** | API key entered separately in each tool | Reads from `portal-config.json` once |

The critical design principle: **every page still works standalone.** If the config fetch fails (offline, `file://` mode, testing), the page falls back to its current behavior — manual upload, hardcoded data, local API key entry. Zero regression.

---

## 4. Power Automate flows — one per data source

### 4.1 Flow: `MIR — Equity Data Refresh`

**Trigger:** File modified in `Source/Equity/` (.xlsx)

**Process:**
1. Run Office Script on the Excel file (finds ISIN header row, skips Bloomberg metadata, outputs clean JSON array — same logic as the existing `buildRows()` parser)
2. Validate: `count > 100` (minimum viable universe)
3. Wrap in metadata envelope: `{ meta: { source, timestamp, count }, data: [...] }`
4. Archive previous file: copy current `BBG_RAW_latest.xlsx` to `Archive/Equity/BBG_RAW_YYYY-MM-DD.xlsx`
5. Write `Data/equity-universe.json`
6. Update `Data/last-update.json` (equity timestamp)
7. Post to Teams: "📊 Equity universe refreshed — 590 securities"

### 4.2 Flow: `MIR — Research Notes Refresh`

**Trigger:** File modified in `Source/Research/notes.xlsx`

**Process:**
1. List rows from Excel table (structured: title, date, asset class, type, tags, excerpt, pdf_path, recommendation)
2. Transform to JSON matching the `RESEARCH_NOTES` array structure in portal.html
3. Write `Data/research-notes.json`
4. Update `last-update.json`
5. Teams notification

### 4.3 Flow: `MIR — Investment Ideas Refresh`

**Trigger:** File modified in `Source/Research/ideas.xlsx`

**Process:**
1. List rows (columns: title, asset_class, date, tags, excerpt, detail, pdf_path, ticker, logo_url)
2. Group by asset class (equity, fi, sp, fund)
3. Transform to JSON matching the `IDEAS_COLS` structure in portal.html
4. Write `Data/investment-ideas.json`
5. Update `last-update.json`
6. Teams notification

### 4.4 Flow: `MIR — Advisory Narrative Update`

**Trigger:** File modified in `Source/Strategy/narrative.docx`

**Process:**
1. Extract text content from the Word document (Power Automate has a native Word connector, or use a simple Office Script)
2. Parse sections: advisory narrative block, IC message block, IC date
3. Write `Data/advisory-narrative.json`
4. Optionally update `portal-config.json` strategy section directly
5. Teams notification

### 4.5 Flow: `MIR — Publication Router`

**Trigger:** File created in `Publications/` (any subfolder), .pdf only

**Process:**
1. Detect subfolder → determine asset class
2. Extract filename metadata (date, title)
3. Append entry to `Data/research-notes.json` (add the new publication, maintain the full list)
4. Teams notification: "📄 New publication: [title] — now visible in portal"

This one is powerful — Khaled drops a PDF into the right folder, and it automatically appears in the portal's research notes carousel without touching the admin page.

---

## 5. How the admin page evolves

Currently `admin.html` is a local content editor. On SharePoint, it becomes a true CMS:

**Read:** loads all data from `Data/` folder (ideas, notes, narrative, config)

**Write:** uses the SharePoint REST API to update JSON files directly:

```javascript
async function saveToSharePoint(filename, data) {
  var siteUrl = 'https://mirabaud.sharepoint.com/sites/ResearchPortal';
  var folderPath = '/Data/';
  var digestResp = await fetch(siteUrl + '/_api/contextinfo', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Accept': 'application/json' }
  });
  var digest = (await digestResp.json()).FormDigestValue;

  var resp = await fetch(
    siteUrl + "/_api/web/GetFileByServerRelativeUrl('" +
    "/sites/ResearchPortal" + folderPath + filename +
    "')/$value",
    {
      method: 'PUT',
      credentials: 'include',
      headers: {
        'X-RequestDigest': digest,
        'Content-Type': 'application/json',
        'X-HTTP-Method': 'PUT',
        'IF-MATCH': '*'
      },
      body: JSON.stringify(data)
    }
  );
  return resp.ok;
}
```

This means Khaled or an analyst can edit investment ideas, update the advisory narrative, or add research notes directly from the admin page — and the changes are immediately live for all advisors. No file redistribution. No Power Automate needed for manual editorial updates.

---

## 6. Migration path — from loose files to connected portal

### Step 1 — Set up SharePoint site (Day 1)

Create the SharePoint site with the folder structure from Section 2. Upload all 9 HTML files to `Pages/`. Create empty JSON files in `Data/` with the correct structure.

### Step 2 — Extract hardcoded data from portal.html (Day 1-2)

The portal currently has `RESEARCH_NOTES`, `IDEAS_COLS`, advisory narrative, and IC message hardcoded in the JavaScript. Extract these into the corresponding JSON files in `Data/`. This is a one-time manual operation.

### Step 3 — Add the shared loader to each page (Day 2-3)

Add the `loadPortalConfig()` + `loadPortalData()` functions to each HTML file. Modify each page's init to try loading from SharePoint first, fall back to current behavior.

Priority order:
1. `portal.html` — biggest win (most hardcoded data to externalize)
2. `equity_screener.html` — second biggest win (eliminates manual file upload)
3. `admin.html` — makes it a real CMS
4. Remaining pages — as their data becomes available

### Step 4 — Build Power Automate flows (Day 3-5)

Start with the equity flow (4.1) since it's the most impactful. Then research notes (4.2) and ideas (4.3). Advisory narrative (4.4) can wait since it changes less frequently.

### Step 5 — Build the source Excel templates (Day 2-3)

Create clean Excel templates for Khaled to use when updating data:

- `ideas.xlsx` — columns: title, asset_class, date, tags, excerpt, detail, pdf_path, ticker
- `notes.xlsx` — columns: title, date, ac, type, tags, excerpt, pdf, rec, ticker
- `narrative.docx` — simple Word doc with two sections (narrative + IC message)

These templates match exactly what the Power Automate flows expect. Khaled fills them in, drops them in `Source/`, everything propagates.

### Step 6 — Test with one advisor (Day 5-7)

Share the SharePoint portal URL with one Geneva advisor. Observe: does everything load? Are the nav links working? Is the data current? Does the API key persist across pages?

### Step 7 — Roll out (Week 2)

Replace the file-distribution workflow with a single SharePoint URL sent to all offices.

---

## 7. What this architecture gives you

| Before (loose files) | After (SharePoint backbone) |
|---|---|
| 9 separate files distributed via email | One URL for the entire portal |
| Data embedded in HTML or uploaded manually | Central data folder, auto-refreshed |
| API key entered in each tool separately | Shared config, entered once |
| Updating content = regenerating HTML + redistribiting | Khaled updates an Excel → live in seconds |
| No version control | SharePoint versioning on every file |
| No usage analytics | SharePoint site analytics (who opens what) |
| Advisors may run different versions | Everyone on the same version, always |
| CORS blocks cross-file data fetching | Same-origin, everything just works |

---

## 8. What this is NOT

This is not the production deployment. The vendor on Track 1 will build the real infrastructure: SSO authentication, Bloomberg live feeds, proper CMS, hosted on `mirabaud-compass.com`. This SharePoint setup is the operational bridge — it makes Phase 1 tools usable at scale today while the production build runs through Q3-Q4.

When the vendor delivers, the migration is clean: the data model (JSON files) and the HTML prototypes transfer directly. The SharePoint architecture actually produces the data contracts the vendor needs.

---

## 9. Auth test — still needed

Before building any of this, run the `sharepoint_test.html` from the previous deliverable. But this time, the test question is different. You're not testing whether a `file://` page can reach SharePoint (it can't). You're testing whether a page served from SharePoint can reach the SharePoint REST API — which it should by default, since it's same-origin.

The specific test: upload `sharepoint_test.html` to the `Pages/` folder of the SharePoint site, then open it from there. Point Test 1 at a file in the `Data/` folder on the same site. This should pass cleanly.

If it does → proceed with the full architecture.
If it doesn't → there's a tenant-level restriction that Serkan needs to raise with IT (single email, five-minute fix: "allow JavaScript execution in SharePoint document libraries").

---

## 10. Immediate next steps

| # | Task | Owner | Time |
|---|---|---|---|
| 1 | Create the SharePoint site + folder structure | Arnaud | 1 hour |
| 2 | Upload `sharepoint_test.html` to `Pages/`, test fetch from same site | Arnaud | 30 min |
| 3 | Extract hardcoded data from `portal.html` into JSON files | Arnaud + Claude | 2-3 hours |
| 4 | Add shared loader to `portal.html` and `equity_screener.html` | Arnaud + Claude | 2-3 hours |
| 5 | Build the `ideas.xlsx` and `notes.xlsx` templates for Khaled | Arnaud + Claude | 1 hour |
| 6 | Build Power Automate flow for equity data | Arnaud | 2-3 hours |
| 7 | Test end-to-end with Khaled: drop Excel → data appears in portal | Arnaud + Khaled | 1 hour |

---

*Document prepared for the Mirabaud Financial Research Portal project — July 2026*
