# Document 2: How Are We Doing It?

## Tech Stack (All Free)

| Component | Tool | Purpose |
|---|---|---|
| Lead Discovery | Apify (free $5/month credits) | Runs LinkedIn scrapers on their servers |
| Data Enrichment | Apify + RapidAPI (free tiers) | Profile data, website, posts |
| Database | Supabase (free PostgreSQL) | Stores all leads in the cloud |
| Dashboard | Streamlit (free cloud hosting) | CRM-style web app for Mohit |
| Language | Python 3.10+ | Glues everything together |

---

## Project File Structure

```
LinkedIn Outreach/
│
├── discovery/                     # Phase 1: Find leads
│   ├── linkedin_posts.py          # Apify: posts with PM hiring keywords
│   ├── linkedin_jobs.py           # Apify: LinkedIn Jobs for PM roles
│   ├── wellfound.py               # Apify: Wellfound PM job listings
│   ├── crunchbase.py              # RapidAPI: recently funded startups
│   └── ycombinator.py             # Scrape YC/HN "Who is Hiring?"
│
├── enrichment/                    # Phase 2: Deepen data on each lead
│   ├── linkedin_profile.py        # Apify: full profile data
│   ├── linkedin_posts_detail.py   # Apify: recent posts + themes
│   ├── company_website.py         # Apify Website Crawler
│   └── pain_points.py             # Rule-based pain point + value prop generator
│
├── dashboard/                     # Phase 3: Streamlit CRM app
│   ├── app.py                     # Main Streamlit entry point
│   └── components/
│       ├── overview.py            # Stats cards, charts
│       ├── pipeline.py            # Kanban board (9 stages)
│       ├── lead_table.py          # Searchable/filterable table
│       └── lead_detail.py         # Full lead profile + messages + warm-up log
│
├── database.py                    # Supabase read/write helpers
├── pipeline.py                    # Orchestrator: runs all steps in order
├── config.py                      # All keywords, filters, API keys
├── main.py                        # Entry point: `python main.py`
├── requirements.txt
├── .env                           # API keys (never commit to git)
└── .env.example                   # Template for API keys
```

---

## Step-by-Step Execution Flow

### Step 1: Setup (One time only)
```bash
# 1. Install dependencies
pip install apify-client supabase streamlit python-dotenv pandas requests

# 2. Get API keys (all free):
#    Apify:    https://console.apify.com → Settings → API & Integrations
#    RapidAPI: https://rapidapi.com → sign up
#    Supabase: https://supabase.com → New project → Settings → API

# 3. Configure .env
cp .env.example .env
# Fill in: APIFY_TOKEN, RAPIDAPI_KEY, SUPABASE_URL, SUPABASE_KEY

# 4. Run pipeline
python main.py
```

### Step 2: Discovery (Runs automatically)
```
python main.py
  ↓
discovery/linkedin_posts.py     → Searches for posts: "hiring project manager", "looking for PM"...
discovery/linkedin_jobs.py      → Searches LinkedIn Jobs: "Project Manager" in India/US/UK/UAE
discovery/crunchbase.py         → Finds startups that raised Series A/B in last 60-90 days
discovery/wellfound.py          → Finds PM job listings at startups on Wellfound
discovery/ycombinator.py        → Reads HN "Who is Hiring?" monthly thread for PM mentions
  ↓
Filters applied:
  - Poster/founder title: Founder / CEO / CTO / MD only
  - EXCLUDE: HR / Talent / Recruiter / People Ops
  - Company: Tech / SaaS / IT Services (exclude staffing agencies)
  - Location: India / US / UK / UAE
  ↓
Result: List of LinkedIn profile URLs + signal data (what triggered them)
```

### Step 3: Enrichment (Runs automatically per profile)
```
For each profile URL found:
  ↓
enrichment/linkedin_profile.py  → Name, title, company, headline, about, experience, location
enrichment/linkedin_posts_detail.py → Last 10-15 posts → themes, tone, hiring mentions
enrichment/company_website.py   → Homepage, about, product, blog (5 pages max)
enrichment/pain_points.py       → Infer pain points from all data + generate PM value prop
  ↓
Quality score calculated (0–100):
  +30 pts: Founder/CEO/CTO title
  +20 pts: Company < 100 employees
  +20 pts: Signal < 7 days old
  +15 pts: Found in multiple sources
  +10 pts: SaaS/tech industry confirmed
  +5 pts:  Contact info found
  ↓
Data written to Supabase (one row per lead)
```

### Step 4: Dashboard (Always live)
```bash
# Run locally:
streamlit run dashboard/app.py

# OR access live on Streamlit Cloud:
https://linkedin-outreach-crm.streamlit.app
```

Dashboard auto-reads from Supabase — any new leads from pipeline appear instantly.

---

## How Messages Are Generated

For each lead, 5 messages are auto-generated using their data:

| Message | Timing | Word Limit | Framework |
|---|---|---|---|
| Connection Request Note | Day 0 | <40 words | Start with THEM, end with curiosity question |
| First DM (after connecting) | Day 0 | <60 words | Give-first (observation → question) |
| Follow-up #1 | Day 4 | <50 words | New angle, no pressure |
| Follow-up #2 | Day 10 | <50 words | Reference their website |
| Follow-up #3 | Day 17 | <50 words | Referral ask / low pressure |
| Follow-up #4 | Day 25 | <30 words | Final "breakup" message |

**Rules (from expert frameworks):**
- Never start with "I" — always start with the recipient
- I:You ratio must favor "you/your"
- Must reference specific data from their profile/post/website
- Never pitch your background in the first message
- Always end with a question, not a statement

---

## Apify Actors Used

| Actor | Purpose | Estimated Cost |
|---|---|---|
| `apify/linkedin-post-scraper` | Find hiring posts | ~$0.20/100 posts |
| `apify/linkedin-jobs-scraper` | Find PM job listings | ~$0.20/100 jobs |
| `anchor/linkedin-profile-scraper` | Full profile data | ~$0.40/100 profiles |
| `apify/website-content-crawler` | Company website | ~$0.80/80 companies |
| **Total per run** | | **~$1.50–2.00** (within $5 free) |

---

## Database Schema (Supabase)

Table: `leads`

```sql
id                    UUID PRIMARY KEY
name                  TEXT
first_name            TEXT
title                 TEXT
company               TEXT
location              TEXT
profile_url           TEXT UNIQUE     -- dedup key
headline              TEXT
about_snippet         TEXT
background_summary    TEXT
post_themes           TEXT[]
post_tone             TEXT
recent_notable_post   TEXT
company_website       TEXT
what_they_do          TEXT
company_size          TEXT
industry              TEXT
funding_stage         TEXT
funding_date          DATE
growth_signals        TEXT
hiring_post_found     BOOLEAN
hiring_post_snippet   TEXT
signal_type           TEXT            -- 'post', 'job_listing', 'funded', etc.
signal_text           TEXT
signal_date           DATE
lead_temperature      TEXT            -- 'hot', 'warm', 'cold'
quality_score         INTEGER
inferred_pain_points  TEXT[]
pm_value_prop         TEXT
msg_connection_note   TEXT
msg_first_dm          TEXT
msg_followup_1        TEXT
msg_followup_2        TEXT
msg_followup_3        TEXT
msg_followup_4        TEXT
pipeline_status       TEXT DEFAULT 'found'  -- kanban stage
warmup_viewed         BOOLEAN DEFAULT false
warmup_liked          BOOLEAN DEFAULT false
warmup_commented      BOOLEAN DEFAULT false
warmup_comment_text   TEXT
warmup_request_sent   BOOLEAN DEFAULT false
warmup_accepted       BOOLEAN DEFAULT false
notes                 TEXT
verified              BOOLEAN DEFAULT false
scraped_at            TIMESTAMPTZ DEFAULT now()
```

---

## Configuration (`config.py`)

```python
# Discovery: what to search for
POST_SEARCH_KEYWORDS = [
    "hiring project manager", "looking for a PM",
    "need a project manager", "we're hiring a PM",
    "PM role open", "project manager wanted",
    "hiring a junior PM", "fresher project manager",
]
JOB_SEARCH_TERMS = [
    "Project Manager", "Junior Project Manager",
    "Associate PM", "Fresher Project Manager",
]

# ICP Filters
TARGET_TITLES  = ["Founder", "Co-Founder", "CEO", "CTO", "MD", "Managing Director"]
EXCLUDE_TITLES = ["HR", "Human Resources", "Talent", "Recruiter", "Recruiting",
                  "Talent Acquisition", "People Operations", "Staffing"]
LOCATIONS      = ["India", "United States", "United Kingdom", "United Arab Emirates"]

# Limits (stay within free credits)
MAX_POSTS_PER_KEYWORD   = 50
MAX_JOBS_PER_TERM       = 50
MAX_PROFILES_TO_ENRICH  = 80
WEBSITE_PAGES_PER_SITE  = 5
```

---

## How to Run After Setup

```bash
# Run the full pipeline (discovery + enrichment + save to DB)
python main.py

# View the dashboard
streamlit run dashboard/app.py

# The dashboard URL (once deployed):
# https://linkedin-outreach-crm.streamlit.app
```
