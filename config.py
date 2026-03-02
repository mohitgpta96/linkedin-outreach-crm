"""
Central configuration for the LinkedIn Outreach Intelligence Tool.
All keywords, filters, limits, and API credentials live here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── API Keys ────────────────────────────────────────────────────────────────
APIFY_TOKEN   = os.getenv("APIFY_TOKEN", "")
RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY", "")
SUPABASE_URL  = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY", "")

# ─── ICP (Ideal Customer Profile) — STRICT DEFINITION ───────────────────────
# Target: Founders / CEOs / CTOs at tech startups who are ACTIVELY HIRING a PM.
# A lead must have at least ONE confirmed PM hiring signal to stay in the pipeline.
# All leads without PM hiring signals are deleted during the filter step.
#
# PM hiring signal = ANY of:
#   - signal_text / signal_type references a PM job posting
#   - growth_signals contains "Actively hiring PM" (from careers page scrape)
#   - careers_page_roles mentions project/product manager
#   - source is a PM job listing platform (The Muse, RemoteOK, HN, Wellfound, YC)

# ─── Phase 1: Discovery ───────────────────────────────────────────────────────
# STRICT: All keywords must indicate the founder/company is HIRING a PM.
POST_KEYWORDS = [
    "hiring project manager",
    "looking for a PM",
    "need a project manager",
    "we're hiring a PM",
    "PM role open",
    "project manager wanted",
    "hiring a junior PM",
    "fresher project manager",
    "seeking project manager",
    "join us as project manager",
    "open role project manager",
    "we need a PM",
    "building our PM team",
]

JOB_SEARCH_TERMS = [
    "Project Manager",
    "Junior Project Manager",
    "Associate PM",
    "Fresher Project Manager",
    "Product Manager",
    "Junior PM",
]

# Only reach out to decision-makers (the people who actually hire PMs)
TARGET_TITLES = [
    "Founder",
    "Co-Founder",
    "CEO",
    "Chief Executive Officer",
    "CTO",
    "Chief Technology Officer",
    "MD",
    "Managing Director",
    "Director",
    "VP Engineering",
    "VP of Engineering",
    "Head of Product",
    "President",
    "Owner",
    "General Manager",
]

# Skip HR / talent / recruiter profiles
EXCLUDE_TITLES = [
    "HR",
    "Human Resources",
    "Talent",
    "Recruiter",
    "Recruiting",
    "Talent Acquisition",
    "People Operations",
    "Staffing",
    "Headhunter",
    "TA Manager",
    "TA Lead",
    "HR Manager",
    "HR Business Partner",
    "People & Culture",
]

# Skip companies in these industries (they recruit PMs, they don't hire them)
EXCLUDE_INDUSTRIES = [
    "staffing",
    "recruitment",
    "HR services",
    "executive search",
    "outsourcing",
]

LOCATIONS = [
    "India",
    "United States",
    "United Kingdom",
    "United Arab Emirates",
]

# Target industries (SaaS, tech, IT)
TARGET_INDUSTRIES = [
    "Technology",
    "Software",
    "SaaS",
    "IT Services",
    "Information Technology",
    "Internet",
    "Computer Software",
    "Mobile",
    "Fintech",
    "Edtech",
    "Healthtech",
    "E-commerce",
    "Startup",
]

# ─── Phase 2: Enrichment ─────────────────────────────────────────────────────
MAX_POSTS_TO_ANALYZE    = 15   # recent posts per person
WEBSITE_PAGES_TO_CRAWL  = 5    # per company

# ─── Rate Limits (Apify $5 free credits) ─────────────────────────────────────
MAX_DISCOVERY_RESULTS   = 100
MAX_PROFILES_TO_ENRICH  = 80

# ─── Quality Score Thresholds ────────────────────────────────────────────────
QUALITY_SCORE_HOT  = 70   # above this = high priority
QUALITY_SCORE_WARM = 45   # above this = medium priority

# ─── Lead Temperature (days since signal) ────────────────────────────────────
HOT_DAYS  = 7
WARM_DAYS = 30

# ─── Output ──────────────────────────────────────────────────────────────────
OUTPUT_DIR = "output"
CSV_FILENAME = "leads.csv"

# ─── Apify Actor IDs (verified from Apify Store March 2026) ──────────────────
APIFY_LINKEDIN_POST_SCRAPER    = "supreme_coder/linkedin-post"          # 4.8★ 7.4K users - takes search URLs
APIFY_LINKEDIN_JOBS_SCRAPER    = "curious_coder/linkedin-jobs-scraper"  # 4.9★ 18K users  - takes jobs search URLs
APIFY_LINKEDIN_PROFILE_SCRAPER = "dev_fusion/linkedin-profile-scraper"  # 4.7★ 40K users  - takes profileUrls[]
APIFY_LINKEDIN_POSTS_SCRAPER   = "apimaestro/linkedin-profile-posts"    # 4.6★ 15K users  - takes username per call
APIFY_WEBSITE_CRAWLER          = "apify/website-content-crawler"        # official Apify crawler
APIFY_WELLFOUND_SCRAPER        = "curious_coder/wellfound-scraper"      # fallback (may not exist)
