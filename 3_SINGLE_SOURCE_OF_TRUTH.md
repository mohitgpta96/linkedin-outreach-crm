# Document 3: Single Source of Truth

## Everything You Need to Know About This Project

---

## 1. Project Goal
Build a LinkedIn Outreach Intelligence Tool that:
- Finds Founders/CEOs/CTOs actively hiring a PM (5 sources)
- Enriches each lead with their profile, posts, company website, pain points
- Displays everything in a CRM dashboard (cloud-hosted, like HubSpot)
- Generates 5 personalized outreach messages per lead (expert-optimized)
- Mohit reviews leads manually and sends messages himself

---

## 2. ICP (Ideal Client Profile)
```
Title:    Founder / Co-Founder / CEO / CTO / MD
EXCLUDE:  HR / Talent / Recruiter / People Ops (any variation)
Company:  Tech startup / SaaS / IT services (NOT staffing agencies)
Size:     5–200 employees preferred
Location: India / United States / United Kingdom / UAE
Signal:   Hired/posted about needing a PM in last 30 days
```

---

## 3. Tools & Services (All Free)

| Service | What For | URL | Free Tier |
|---|---|---|---|
| Apify | LinkedIn scraping (runs on their servers) | apify.com | $5/month credits |
| RapidAPI | Crunchbase, profile enrichment | rapidapi.com | 100-500 req/month |
| Supabase | Cloud database (PostgreSQL) | supabase.com | 500MB, free forever |
| Streamlit | Dashboard hosting | streamlit.io | Free forever |
| Python 3.10+ | Everything | — | Free |

---

## 4. API Keys Needed (You Must Set Up)
```bash
APIFY_TOKEN=           # console.apify.com → Settings → API & Integrations
RAPIDAPI_KEY=          # rapidapi.com → sign up → API key
SUPABASE_URL=          # supabase.com → project → Settings → API → URL
SUPABASE_KEY=          # supabase.com → project → Settings → API → anon key
```

---

## 5. Lead Discovery: 5 Sources

| # | Source | How | Signal |
|---|---|---|---|
| 1 | LinkedIn Posts | Apify post scraper | Post with PM hiring keywords |
| 2 | LinkedIn Jobs | Apify jobs scraper | Active PM job listing |
| 3 | Crunchbase | RapidAPI | Series A/B funding in last 90 days |
| 4 | Wellfound | Apify scraper | PM job at startup, founder posting |
| 5 | YC / Hacker News | HTTP scraper | HN "Who is Hiring?" PM mention |

All sources feed into a single deduplication pipeline (keyed by `profile_url`).

---

## 6. Enrichment: What We Collect Per Lead

```
LinkedIn Profile:    name, title, company, location, headline, about, experience
Recent Posts:        last 10-15 posts → themes, tone, hiring mentions
Company Website:     what they do, team size, products, growth signals (5 pages)
Pain Points:         inferred from all data (rules-based)
PM Value Prop:       specific ways Mohit can solve their pain
Quality Score:       0–100 (see scoring table below)
```

---

## 7. Quality Scoring

| Signal | Points |
|---|---|
| Title = Founder/CEO/CTO | +30 |
| Company < 100 employees | +20 |
| Signal < 7 days old | +20 |
| Found in 2+ sources | +15 |
| Industry = SaaS/tech/IT | +10 |
| Contact info found | +5 |
| **Max total** | **100** |

Lead temperature: 🔥 Hot = 70+, ⚡ Warm = 40–69, ❄️ Cold = <40

---

## 8. Dashboard: 4 Pages

### Page 1 — Overview
Stats cards + charts: total leads, hot/warm/cold breakdown, leads by source/location/status, outreach funnel

### Page 2 — Pipeline (Kanban)
9 stages: `Found → Verified → Warming Up → Request Sent → Connected → Msg Sent → Replied → Interested → Closed`

### Page 3 — Lead Table
Search + filter + sort. Filter by: location, source, quality score, company type, status.

### Page 4 — Lead Detail Panel (click any lead)
Shows:
- Full profile data
- Why they were found (signal text)
- Company intelligence
- Inferred pain points
- PM value proposition
- 5 ready-to-copy messages (with copy buttons)
- Warm-up activity checklist (checkboxes saved to DB)
- Pipeline status dropdown
- Personal notes field

---

## 9. Generated Messages (5 Per Lead)

| # | Timing | Words | Framework |
|---|---|---|---|
| Connection Note | Day 0 | <40 | Start with THEM + curiosity question |
| First DM | Day 0 (after connect) | <60 | Give-first + curiosity question |
| Follow-up 1 | Day 4 | <50 | New angle, no pressure |
| Follow-up 2 | Day 10 | <50 | Website reference |
| Follow-up 3 | Day 17 | <50 | Referral ask / low pressure |
| Follow-up 4 | Day 25 | <30 | Final breakup |

**Always:** Start with them, not "I". End with a question. Under 75 words.

---

## 10. Expert Frameworks Built In

| Expert | Rule Applied |
|---|---|
| **Vaibhav Sisinty** | Warm up 5–7 days before connecting (Ninja Outbound) |
| **Will Allred (Lavender)** | <75 words, I:You ratio, mobile-first, start with THEM |
| **Josh Braun** | Questions not statements; assume nothing; remove pressure |
| **Aaron Ross** | Referral variant message, 4-touch minimum sequence |
| **Justin Welsh** | Give-first (observe/compliment before any ask) |
| **Lemlist** | 5 follow-ups = 22.37% reply rate vs 4.5% for 1 message |

---

## 11. Filters & Exclusions

```python
# Include only:
TARGET_TITLES  = ["Founder", "Co-Founder", "CEO", "CTO", "MD", "Managing Director"]

# Exclude always (even if title also contains a target keyword):
EXCLUDE_TITLES = ["HR", "Human Resources", "Talent", "Recruiter", "Recruiting",
                  "Talent Acquisition", "People Operations", "Staffing", "Headhunter"]

# Exclude company types:
EXCLUDE_COMPANIES = ["staffing agency", "recruitment firm", "HR services", "headhunting"]
```

---

## 12. Accuracy Expectations

| Stage | % Relevant |
|---|---|
| Raw results (no filter) | 30–40% |
| After title + industry filter | 60–70% |
| After enrichment + company size filter | 75–85% |
| After Mohit's manual 5-min review | 90–95% |

Out of 100 leads found, expect ~80 to be genuinely relevant without manual review.

---

## 13. What Mohit Does (Manual Steps)

After pipeline runs and dashboard populates:
1. Open dashboard → sort by quality_score (highest first)
2. Review each lead's detail panel (1–2 min per lead)
3. Check `verified = YES / NO` for each
4. Follow warm-up sequence for verified leads:
   - Day 1: View profile + follow company
   - Day 2: Like a post
   - Day 3: Leave a specific comment
   - Day 4: Send connection request (copy from dashboard)
   - Day 6–7: Send first DM (copy from dashboard)
5. Update `pipeline_status` as they move through stages

---

## 14. What Claude Does vs. Cannot Do

### Can Do Autonomously
- Write all code
- Configure all APIs
- Run the pipeline on Mohit's machine
- Build and deploy the dashboard
- Generate personalized messages per lead
- Read LinkedIn public data via browser

### Must Be Done by Mohit
- Create LinkedIn, Apify, RapidAPI, Supabase accounts
- Enter LinkedIn password (security rule)
- Send connection requests and messages (manually)
- Enter any billing/credit card info

---

## 15. Known Bugs & Risks
→ See full checklist: `memory/bugs_and_mistakes.md`

**Top 3 critical:**
1. Always normalize LinkedIn URLs before dedup (strip `/`, lowercase, remove `?`)
2. Never hardcode Apify actor names — verify at runtime
3. If title contains ANY exclude keyword → discard, even if it has a target keyword too

---

## 16. Competitors & What We Learned

| Name | Their Approach | What We Take |
|---|---|---|
| **Raj Shamani** | ECG content + PEU persuasion | PEU in message framing: Pain → Emotion → Urgency |
| **Ankur Warikoo** | Inbound brand building (long-term) | Post PM content 1–2×/week in parallel |
| **Vaibhav Sisinty** | Ninja Outbound (engage before messaging) | Core warm-up sequence in our pipeline |

---

## 17. Additional Outreach Channels (Beyond LinkedIn)

| Channel | Why Use It |
|---|---|
| **Twitter/X** | Founders more accessible, less saturated |
| **Product Hunt** | Find founders on launch day (hottest hiring signal) |
| **Hacker News** | Monthly "Who is Hiring?" — founders only, no HR |
| **Wellfound** | Direct founder contact at early-stage startups |
| **SaaStr / FoundersBeta Discord** | Join, add value 30 days, then mention availability |

---

## 18. Phase Roadmap

| Phase | What | When |
|---|---|---|
| **Phase 1** | Discovery + Enrichment + CRM Dashboard | Now |
| **Phase 2** | Email enrichment (Hunter.io / Apollo free tiers) | After Phase 1 is running |
| **Phase 3** | Multi-channel outreach (LinkedIn + Email) | After first leads replied |
| **Future** | Automated connection requests (with Mohit's per-batch approval) | When Mohit is ready |
