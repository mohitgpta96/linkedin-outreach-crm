# Document 1: What Are We Doing?

## The Mission
Mohit is a fresher Project Manager. He wants to land his first PM role at a startup directly — not through job boards or HR — but by reaching the **decision makers themselves**: Founders, CEOs, CTOs who are actively looking for a PM right now.

This tool makes that possible at scale.

---

## The Problem We're Solving

| Problem | Reality |
|---|---|
| Most fresher PMs apply on job boards | They compete with 200+ applicants for every role |
| Reaching out to HR/recruiters | HR screens freshers out; no direct access to decision-makers |
| Cold generic messages to founders | 2–5% response rate; founders ignore templated pitches |
| No intelligence about the person | Can't write a personalized message without knowing their story |

**Our solution:** Find founders who are publicly signaling a need for a PM → understand everything about them → generate messages so personalized they feel like warm outreach, not cold.

---

## Who We're Targeting (ICP)

| Field | Value |
|---|---|
| **Role** | Founder, Co-Founder, CEO, CTO, MD |
| **NOT** | HR, Talent Acquisition, Recruiter, People Ops |
| **Company type** | Tech startups, IT services/agencies, SaaS companies |
| **Company size** | 5–200 employees (small enough that the founder is the hiring decision) |
| **Location** | India, United States, United Kingdom, UAE |
| **Signal** | Actively hiring a PM — through a post, job listing, or recent funding |

---

## What We're Building

### Tool 1: Lead Discovery Engine
Finds ICP leads from 5 sources:
1. LinkedIn posts — founders who wrote "hiring a PM"
2. LinkedIn Jobs — PM job postings by founders (not HR)
3. Crunchbase — recently funded startups (hiring trigger)
4. Wellfound — PM jobs at startups, direct founder contact
5. Y Combinator / Hacker News — founders posting PM needs

### Tool 2: Enrichment Engine
For each lead found, collects:
- Full LinkedIn profile (headline, about, experience, post themes)
- Recent posts — what they talk about, their tone, their pain
- Company website — what they do, how big they are, growth signals
- Inferred pain points (why they need a PM specifically)
- PM value proposition (how Mohit can solve their specific problem)

### Tool 3: Cloud CRM Dashboard
A Streamlit dashboard (like a mini HubSpot) that shows:
- All leads in a pipeline (9 stages from Found → Closed)
- Full lead detail panel with every piece of data + 5 pre-written messages
- Warm-up activity tracker (checkboxes per lead)
- Quality scoring and lead temperature (Hot / Warm / Cold)

---

## What Success Looks Like

| Metric | Target |
|---|---|
| Quality leads found per week | 50–100 (after filter) |
| Leads with quality score > 70 | 75–85% |
| Connection request acceptance rate | 40–60% (with warm-up) |
| First DM reply rate | 15–25% (with personalization) |
| Leads → conversations → opportunities | 3–5 per month |

---

## What We Are NOT Doing
- NOT automating message sending (Mohit sends manually)
- NOT scraping competitors' data for resale
- NOT using LinkedIn Premium or Sales Navigator (free tools only)
- NOT building a complex backend — simple Python + free cloud services
- NOT collecting email/phone in Phase 1 (enrichment comes later)

---

## Phase Plan

| Phase | What | Status |
|---|---|---|
| **Phase 1** | Lead Discovery + Enrichment + Dashboard | Building now |
| **Phase 2** | Email enrichment (Hunter.io, Apollo free tiers) | Later |
| **Phase 3** | Message automation (with Mohit's approval per batch) | Later |
