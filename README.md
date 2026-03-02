# LinkedIn Outreach CRM

A Jira-like CRM dashboard for LinkedIn outreach to startup founders.

## Features

- Lead discovery from 5 sources: LinkedIn Posts, LinkedIn Jobs, Crunchbase, Wellfound, and YC/HN "Who is Hiring?"
- Enriched profiles with company intelligence and inferred pain points
- Personalized outreach messages (5 per lead) using proven frameworks (Josh Braun, Justin Welsh, Lavender)
- Kanban pipeline board with 9 stages (Found → Verified → Warming Up → Request Sent → Connected → Msg Sent → Replied → Interested → Closed)
- Full lead detail view with warm-up checklist

## Tech Stack

- **Discovery:** Apify (LinkedIn scrapers) + RapidAPI (Crunchbase)
- **Database:** Supabase (PostgreSQL)
- **Dashboard:** Streamlit

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```
APIFY_TOKEN=your_apify_token
RAPIDAPI_KEY=your_rapidapi_key
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
```

### 3. Set up the database (run once)

```bash
python3 main.py --setup-db
```

Copy the SQL output and run it in the Supabase SQL editor.

### 4. Run the pipeline

```bash
python3 main.py
```

This discovers leads, enriches them, and writes results to `output/leads.csv` and Supabase.

### 5. Launch the dashboard

```bash
streamlit run streamlit_app.py
```

## CLI Options

```
python3 main.py                    # Full run
python3 main.py --skip-discovery   # Use existing leads, re-enrich only
python3 main.py --skip-db          # Skip Supabase, write CSV only
python3 main.py --setup-db         # Print SQL schema for Supabase
```

## Deployment (Streamlit Cloud)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo
3. Set the main file path to `streamlit_app.py`
4. Add your secrets in the Streamlit Cloud dashboard under **Settings → Secrets**:

```toml
SUPABASE_URL = "your_supabase_project_url"
SUPABASE_KEY = "your_supabase_anon_key"
```

## ICP (Ideal Customer Profile)

Targeting: Founders, Co-Founders, CEOs, CTOs at tech startups (India, US, UK, UAE) actively hiring a Project Manager.

## Quality Score (0–100)

| Signal | Points |
|---|---|
| Founder/CEO/CTO title | +30 |
| Company < 100 employees | +20 |
| Signal < 7 days old | +20 |
| Multiple sources | +15 |
| SaaS/tech/IT industry | +10 |
| Contact info found | +5 |
