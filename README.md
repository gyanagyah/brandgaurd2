# 🛡️ BrandGuard — AI Brand Compliance Platform

BrandGuard checks social-media drafts **before they are published**. A creator submits post text (and optionally an image); BrandGuard retrieves the company's own brand guidelines, product facts and legal rules from a vector knowledge base (RAG), asks an LLM (via **Groq**) to score the draft across seven categories, applies a deterministic scoring engine with hard "critical issue" overrides, and routes passing content to a human reviewer for final approval.

Built with **Streamlit**, **ChromaDB**, **SQLite** and the **Groq API**. It is tuned for **Indian advertising rules** (ASCI guidelines, Consumer Protection Act) but works with whatever rules you upload.

---

## Table of contents

1. [How it works](#how-it-works)
2. [Quick start](#quick-start)
3. [Configuration](#configuration)
4. [First-run walkthrough](#first-run-walkthrough)
5. [Features in depth](#features-in-depth)
6. [Scoring model](#scoring-model)
7. [Data model](#data-model)
8. [Project structure](#project-structure)
9. [Troubleshooting](#troubleshooting)
10. [Known issues](#known-issues)
11. [Project planner / roadmap](#project-planner--roadmap)

---

## How it works

```
Creator ──► Submit text/image ──► Retrieve top-5 guideline chunks (ChromaDB)
                                         │
                                         ▼
                          Build prompt ► Groq LLM (7 category scores + flags + fixes)
                                         │
                                         ▼
                     Scoring engine: weighted score, critical-issue cap, decision
                                         │
              ┌──────────────────────────┴───────────────────────────┐
              ▼                                                      ▼
   Score ≥ 70, no critical issues                          Needs work / Fail
   → "Send for Human Review"                               → fix & resubmit (diff + score trend)
              │
              ▼
   Reviewer: Approve / Reject / Request revision ──► Approved Posts
```

Admins feed the knowledge base: uploaded documents are chunked (~500 characters, 50 overlap), embedded by ChromaDB's default embedding model, and stored in a persistent vector collection called `brand_guidelines`.

---

## Quick start

### Prerequisites

- **Python 3.11+** (recommended; the pinned `pandas`/`numpy` versions need a recent Python)
- A free **Groq API key** — create one at <https://console.groq.com>
- Internet access on first run (ChromaDB downloads its default embedding model the first time you ingest or query)

### 1. Clone

```bash
git clone https://github.com/gyanagyah/brandgaurd2.git
cd brandgaurd2
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> ⚠️ The `requirements.txt` committed in the repo is **missing `groq`**, which `evaluate.py` imports at start-up. Until it is updated, also run:
>
> ```bash
> pip install "groq>=0.11.0"
> ```
>
> On **Windows**, `pysqlite3-binary` (listed at the end of `requirements.txt`) has no wheel — remove that line or install with `pip install -r requirements.txt --no-deps` and add the packages you need. It is optional (see [Troubleshooting](#troubleshooting)).

### 4. Add your Groq API key

Create `data/.env` (git-ignored):

```env
GROQ_API_KEY=gsk_your_key_here
```

### 5. Run

```bash
streamlit run app.py
```

Streamlit opens <http://localhost:8501>. The SQLite database (`brandguard.db`) and vector store (`chroma_data/`) are created automatically on first launch.

---

## Configuration

| Item | Where | Notes |
|---|---|---|
| `GROQ_API_KEY` | `data/.env`, a root `.env`, an environment variable, or Streamlit secrets (`st.secrets["GROQ_API_KEY"]`) | Looked up in that order. If missing, the app prints a warning and evaluation fails. |
| Theme | `.streamlit/config.toml` | Light theme, blue primary (`#2563eb`). |
| Logo | `data/logo.jpg` | Shown on login, sidebar and page headers. Falls back to a 🛡️ emoji if absent. |
| Scoring weights & thresholds | `scoring.py` | `CATEGORY_WEIGHTS`, `PASS_THRESHOLD` (70), `WARNING_THRESHOLD` (50), `CRITICAL_SCORE_CAP` (49), `CRITICAL_KEYWORDS`. |
| Chunk size / overlap | `ingest.py` | `chunk_text(chunk_size=500, overlap=50)`. |
| Retrieval depth | `evaluate.py` | `n_results=5` guideline chunks per evaluation. |
| Model choice | `evaluate.py` | Models are discovered live from your Groq account — see [Evaluation engine](#evaluation-engine). |

**Deploying on Streamlit Community Cloud:** add `GROQ_API_KEY` under *App settings → Secrets*. `app.py` swaps in `pysqlite3` for `sqlite3` when available, which is what ChromaDB needs on hosts with an old system SQLite.

---

## First-run walkthrough

1. **Register three accounts** on the login screen (*Register* tab): one `admin`, one `reviewer`, one `creator`. Sign in as each in turn (use **Logout** in the sidebar to switch).
2. **Admin:** open *Upload Documents* and add your brand guidelines, product fact sheets and legal rules (`.txt` or `.pdf`), or paste text in *Add Text Guidelines*. Check *View Knowledge Base* to confirm chunks were stored and try a test search.
3. **Creator:** submit a draft with a campaign objective. Review the scores, critical issues and suggested fixes. Edit and resubmit until it passes.
4. **Creator:** click **Send for Human Review** on a passing result.
5. **Reviewer:** approve, reject, or request a revision from *Pending Review*; approved items appear under *Approved Posts*.

Try a deliberately bad draft to see the guard-rails in action, e.g. *"Our SuperWidget Pro is guaranteed to boost productivity by 500%!"* — unsupported claims should trigger a critical issue and cap the score.

---

## Features in depth

### 🔐 Authentication & role-based access (RBAC)

- Username/password login with **bcrypt**-hashed passwords stored in SQLite (`users` table).
- Registration form lets the user pick a role: `creator`, `reviewer` or `admin`.
- The role is locked to the account. Each role sees exactly one workspace (there is no in-app role switching):

| Role | Workspace | Can do |
|---|---|---|
| **Creator** | Submit Content + Feedback History | Submit drafts, get AI feedback, resubmit, send for review, browse own history |
| **Reviewer** | Approve Posts | Review AI-passed posts, approve / reject / request revision, browse approved posts |
| **Admin** | Knowledge Base | Upload & manage guidelines, facts and legal rules; search the KB |

- Sidebar (all roles): active-role badge, logout, **live stats** (KB chunks, total submissions, average score) and a **threshold legend** (Pass ≥ 70, Improve ≥ 50, Fail < 50).

### 🎨 Creator workspace

**Submit Content**
- Post text, plus an optional image (`png`, `jpg`, `jpeg`, `gif`, `webp`) with preview.
- Seven campaign objectives: *brand awareness, lead generation, engagement, product launch, promotional offer, educational, event promotion*. The objective feeds the "Campaign Effectiveness" score.
- Images are saved to `temp_uploads/` and sent to a **vision-capable** Groq model as a base64 data URL.
- Results screen:
  - Decision banner (pass / needs improvement / fail) with the reason
  - Overall-score gauge, critical-issue count, "ready for review" flag
  - Seven category score tiles with 🟢🟡🟠🔴 indicators
  - Expandable per-category feedback
  - 🚨 Critical issues list
  - 💡 Suggestions, each with **issue → risk → guideline reference → fix**
  - AI summary
- **Send for Human Review** appears only when the result is eligible (score ≥ 70 and no critical issues). It sets the submission status to `sent_for_review`.

**Edit & Resubmit**
- Edit the text and re-evaluate. The new draft is stored as a child submission (`parent_submission_id`) so revision chains are preserved.
- Shows a **side-by-side diff** (red = removed, green = added) and a **score trend** (original vs new, delta, and how many critical issues were fixed vs still open).

**Feedback History**
- Creators see only their own submissions (latest 20), as expandable cards with status pill, score, category grid, critical flags, full feedback, suggestions, and the reviewer decision history.
- *Clear History* deletes submissions, evaluations and reviews (with a confirmation step) — see [Known issues](#known-issues).

### ✅ Reviewer workspace

- **Pending Review** lists submissions with status `sent_for_review` along with the latest evaluation: score gauge, critical-issue flag, category scores, full AI feedback, post text and image.
- Actions: **Approve**, **Reject**, **Request Revision**. Each writes a row to `reviews` and updates the submission status (`approved`, `rejected`, or back to `pending` for revisions).
- **Approved Posts** shows approved content with reviewer name/date, AI score and the final text/image.

### ⚙️ Admin workspace — knowledge base

- **Upload Documents:** multiple `.txt` / `.pdf` files at once. The document type is **auto-detected from the filename** (`guideline`, `fact`/`product` → factsheet, `legal`/`regulatory` → legal, `template`), falling back to the type selected in the dropdown.
- **Add Text Guidelines:** paste text with a title and type — no file needed.
- **View Knowledge Base:** total vector chunks and documents, per-document metadata (type, chunks, version, upload time, preview), and a 🗑️ button that removes the document's chunks from ChromaDB and soft-deletes the SQLite record.
- **Search Knowledge Base:** semantic search with relevance (distance) scores — useful for checking what the evaluator will actually retrieve.

### 🤖 Evaluation engine

Implemented in `evaluate.py`:

1. **Retrieve** — top-5 guideline chunks for the post text (or the objective if the text is empty). If retrieval fails, evaluation continues using general brand standards.
2. **Prompt** — a structured prompt containing the guidelines, objective and post, requesting strict JSON: scores, critical flags, per-category feedback, suggestions, and a summary.
3. **Model selection** — lists the models available on your Groq account, excludes whisper/guard/TTS/embedding models, and prefers larger general-purpose chat models (70B first). With an image it restricts to vision-capable models. Falls back to `llama-3.3-70b-versatile` / `llama-4-scout` if listing fails.
4. **Resilience** — up to 3 attempts per model with back-off on 429/503 errors, skips unavailable models (404), and falls through to the next model.
5. **Robust JSON parsing** — direct parse → fenced ```json block → first `{…}` span. If everything fails, neutral 50-point scores are returned with an explanatory message.
6. **Score** via the scoring engine, then **save** the evaluation to SQLite.

Temperature is `0.1` for consistent scoring.

### 📊 Analytics

`db.py` includes analytics queries (score distribution, category averages, approval trend, common failure categories), and `app.py` contains a full `dashboard_page()` with KPIs, approval-rate bar, histogram, category chart, trend line and recent-submissions list. **It is not yet reachable from any role** — see [Known issues](#known-issues) and the [planner](#project-planner--roadmap).

---

## Scoring model

Seven categories, each scored 0–100 by the LLM, combined by weight:

| Category | Weight | What it checks |
|---|---:|---|
| Factual Accuracy | 20% | Product details and claims match approved facts |
| Regulatory Compliance | 20% | Indian ad law (ASCI, Consumer Protection Act), required disclaimers |
| Brand Identity | 15% | Tone, vocabulary, voice |
| Visual Consistency | 15% | Logos, colours, design elements |
| Campaign Effectiveness | 10% | Alignment with the stated objective |
| Accessibility | 10% | Readability, contrast, clarity |
| Overall Design | 10% | Layout and communication quality |

**Critical-issue override.** A draft has critical issues if the LLM lists any `critical_flags`, **or** the combined feedback text contains one of the keywords in `CRITICAL_KEYWORDS` (e.g. *unverified claim, misleading claim, missing disclaimer, ASCI violation, offensive content, copyright violation, unauthorized logo*). Critical issues **cap the overall score at 49** regardless of the weighted result and force a `fail`.

**Decision logic**

| Condition | Decision | Can go to human review? |
|---|---|:---:|
| Any critical issue | `fail` | No |
| Score ≥ 70 | `pass` | **Yes** |
| 50 ≤ score < 70 | `needs_improvement` | No |
| Score < 50 | `fail` | No |

Submission lifecycle: `pending → evaluated → sent_for_review → approved | rejected` (a "revision needed" decision sends it back to `pending`).

---

## Data model

**SQLite** (`brandguard.db`, created by `db.init_db()` on import):

| Table | Purpose |
|---|---|
| `users` | username, bcrypt `password_hash`, `role` |
| `documents` | knowledge-base file records (filename, type, preview, chunk count, version, `is_active` soft-delete flag) |
| `submissions` | creator drafts: text, image path, objective, status, `parent_submission_id` for resubmissions |
| `evaluations` | the 7 category scores, overall score, critical flags / feedback / suggestions (JSON), `has_critical_issues` |
| `reviews` | reviewer decision (`approved`, `rejected`, `revision_needed`), comments, timestamp |

**ChromaDB** (`chroma_data/`): a persistent collection `brand_guidelines` holding text chunks with metadata `filename`, `doc_type`, `chunk_index`, `total_chunks`.

---

## Project structure

```
brandgaurd2/
├── app.py              # Streamlit UI: login, RBAC, creator/reviewer/admin/dashboard pages
├── db.py               # SQLite layer: schema, CRUD, auth (bcrypt), analytics queries
├── ingest.py           # Knowledge-base ingestion: read PDF/TXT, chunk, store in ChromaDB
├── retrive.py          # RAG retrieval + prompt formatting (filename spelled "retrive")
├── evaluate.py         # Groq-powered evaluation pipeline (RAG → LLM → scoring → DB)
├── scoring.py          # Weights, thresholds, critical checks, final decision
├── requirements.txt    # Python dependencies
├── data/
│   ├── logo.jpg        # Brand logo used in the UI
│   ├── requirments.txt # Old, minimal dependency list (superseded; see Known issues)
│   └── .env            # (you create) GROQ_API_KEY — git-ignored
├── .streamlit/config.toml   # Light theme
└── .gitignore          # ignores chroma_data/, temp_uploads/, brandguard.db, .env files
```

Generated at runtime (all git-ignored): `brandguard.db`, `chroma_data/`, `temp_uploads/`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'groq'` | `pip install "groq>=0.11.0"` (missing from `requirements.txt`). |
| "GROQ_API_KEY not found" warning / evaluation fails | Add the key to `data/.env`, a root `.env`, or Streamlit secrets; restart the app. |
| `RuntimeError: Your system has an unsupported version of sqlite3` (ChromaDB) | On Linux: `pip install pysqlite3-binary` — `app.py` swaps it in automatically. |
| `pysqlite3-binary` fails to install on Windows | Not available there; drop it from requirements. You only need it if your SQLite is older than ChromaDB requires. |
| "Knowledge base is empty" in logs / generic evaluations | Log in as admin and ingest documents first. |
| Evaluation says all models failed / rate limit | Wait and retry, check your Groq quota, confirm the key is valid. |
| PDF ingests as "empty" | The PDF is probably scanned images (no extractable text). Use a text-based PDF or paste the text. |
| First ingest is slow | ChromaDB is downloading its default embedding model; it is cached afterwards. |
| Want a clean slate | Stop the app and delete `brandguard.db` and/or `chroma_data/`. |

---

## Known issues

Found while reading the code for this README (none were changed):

| # | Area | Issue |
|---|---|---|
| 1 | Dependencies | `requirements.txt` omits `groq` (required) and includes unused packages (`google-genai`, `google`, `kubernetes`, …). |
| 2 | Dashboard | `dashboard_page()` exists but no role lists a "Dashboard" page, so it is unreachable. |
| 3 | Security | Anyone can self-register as **admin** or **reviewer** from the login page. |
| 4 | Data | "Clear My History" calls `delete_all_submissions()`, which wipes **every** user's submissions, not just the caller's. |
| 5 | Reviewer | The **Reject** button renders a reason text box *after* the click and saves immediately, so the typed reason is never captured. |
| 6 | Scoring | Keyword matching on feedback text can false-positive (e.g. feedback saying "no missing disclaimer" contains the phrase *missing disclaimer*). |
| 7 | Code | `ingest.py` defines `read_pdf_file` twice; the second definition overrides the first, so the `PyPDF2` fallback is never used. |
| 8 | Comments | Several comments/docstrings still mention an 85-point pass threshold; the actual `PASS_THRESHOLD` is 70. |
| 9 | Dead code | `splash_page()` is defined but never shown; `data/requirments.txt` is a stale, misspelled duplicate. |
| 10 | Ingestion | Re-uploading the same filename adds duplicate chunks (IDs include a timestamp), and deleting by filename removes all versions. |
| 11 | Uploads | Uploaded images are stored under their original filename in `temp_uploads/`, so same-named files overwrite each other. |
| 12 | Tests | No automated tests. |

---

## Project planner / roadmap

Priorities: 🔴 do first · 🟠 next · 🟢 nice to have. Effort: S (<½ day), M (1–2 days), L (3+ days).

### Phase 0 — Stabilise (week 1)

- [ ] 🔴 **S** Fix `requirements.txt`: add `groq`, remove unused packages, make `pysqlite3-binary` Linux-only
- [ ] 🔴 **S** Delete `data/requirments.txt`
- [ ] 🔴 **M** Restrict self-registration: only `creator` is self-service; admins create reviewer/admin accounts (or require an invite code)
- [ ] 🔴 **S** Make "Clear My History" scoped to the signed-in creator
- [ ] 🔴 **S** Fix the Reject flow so the reason is captured before saving
- [ ] 🟠 **S** Remove the duplicate `read_pdf_file`; keep the `pypdf` → `PyPDF2` fallback
- [ ] 🟠 **S** Update the 85 → 70 threshold comments

### Phase 1 — Complete the product (weeks 2–3)

- [ ] 🔴 **S** Surface the Dashboard (give Admin — and optionally Reviewer — a second page)
- [ ] 🟠 **M** Replace keyword-based critical detection with structured, negation-aware checks (or rely on the LLM's `critical_flags` plus a curated phrase list)
- [ ] 🟠 **M** Unique image filenames (UUID) and clean-up of `temp_uploads/`
- [ ] 🟠 **M** Document versioning: re-upload bumps `version` and replaces old chunks
- [ ] 🟠 **S** Show which guideline chunks were retrieved on the results screen (`guideline_sources` is already returned)
- [ ] 🟢 **S** Real radar chart on the dashboard (currently a bar chart)

### Phase 2 — Quality & trust (weeks 4–5)

- [ ] 🔴 **M** Unit tests for `scoring.py`, `chunk_text`, `_parse_json_response`, and DB functions
- [ ] 🟠 **M** Mock-LLM integration test for `evaluate_post`
- [ ] 🟠 **M** Golden set of good/bad sample posts to track scoring drift across models
- [ ] 🟠 **S** Password policy and login rate-limiting; session timeout
- [ ] 🟢 **S** Structured logging instead of `print`

### Phase 3 — Scale & collaboration (weeks 6+)

- [ ] 🟠 **L** Move from SQLite to Postgres; hosted vector store for multi-user deployments
- [ ] 🟠 **M** Email / Slack notification when a post is sent for review or decided
- [ ] 🟠 **L** Multi-brand / multi-tenant knowledge bases
- [ ] 🟢 **M** Export reports (PDF/CSV) and an audit trail of reviewer decisions
- [ ] 🟢 **M** Multi-language content support (Hindi and other Indian languages)
- [ ] 🟢 **L** Direct publishing hooks to social platforms after approval
- [ ] 🟢 **S** Dockerfile and CI (lint + tests) for one-command deployment

### Operating checklist (every release)

- [ ] `pip install -r requirements.txt` works in a clean virtualenv
- [ ] App starts with `streamlit run app.py`
- [ ] Register → ingest → submit → review flow passes end to end
- [ ] A deliberately non-compliant post is capped at ≤ 49 and cannot be sent for review
- [ ] No secrets committed (`.env`, API keys)

---

## License

No license file is included in the repository yet. Add one (e.g. MIT) before sharing or accepting contributions.
