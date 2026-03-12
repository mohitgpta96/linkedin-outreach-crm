# Ideal Client Profile (ICP) — LinkedIn Outreach

## Why This Doc Exists
Every outreach message starts here. If the prospect doesn't match
this profile, don't waste a connection request. Quality targeting
beats volume every time.

---

## Primary Target Personas

### Persona 1: Scaling Startup CTO / VP Engineering
- **Title:** CTO, VP of Engineering, Head of Engineering
- **Company Stage:** Series A to Series C (funded, actively growing)
- **Team Size:** 5-50 engineers, growing fast
- **Pain:** Hiring developers but nobody managing delivery. Sprints
  are chaotic, deadlines slip, stakeholders are frustrated.
- **Why They Need Mohit:** They need PM structure NOW but can't
  wait 2-3 months for a full-time PM hire.

### Persona 2: Founder / CEO of Small Tech Company
- **Title:** Founder, Co-Founder, CEO
- **Company Stage:** Bootstrapped or Seed to Series A
- **Team Size:** 3-15 people total
- **Pain:** Founder is playing PM themselves. Context-switching
  between building product, talking to customers, managing sprints,
  and fundraising. Burning out.
- **Why They Need Mohit:** Offload the PM role so they can focus
  on product vision and business growth.

### Persona 3: Engineering Manager Drowning in Process
- **Title:** Engineering Manager, Director of Engineering
- **Company Stage:** Any (startup to mid-size)
- **Team Size:** Managing 2+ squads
- **Pain:** Spending 60%+ of time in meetings, status updates,
  stakeholder management instead of actual engineering leadership.
- **Why They Need Mohit:** Fractional PM takes over the process
  work so they can focus on technical decisions and team growth.

### Persona 4: Technical Program Manager Needing Backup
- **Title:** TPM, Senior TPM, Program Manager
- **Company Stage:** Mid-size to large (100+ employees)
- **Pain:** Managing too many workstreams simultaneously. Needs
  a reliable fractional PM to own 1-2 specific projects.
- **Why They Need Mohit:** Extra bandwidth for specific initiatives
  without headcount approval.

---

## Target Industries (Priority Order)

### Tier 1 — High Priority
- **SaaS Companies** — Always shipping, always need PM support
- **FinTech** — Regulatory pressure means deadlines are real
- **HealthTech** — Complex stakeholder environments, compliance needs
- **DevTools / Developer Platforms** — Technical audience, values structure

### Tier 2 — Good Fit
- **EdTech** — Growing fast post-pandemic, often under-structured
- **E-Commerce / D2C Tech Teams** — Seasonal pressure, launch cycles
- **AI/ML Startups** — Fast-moving, research + product tension needs PM
- **Infrastructure / Engineering Firms Going Digital** — Mohit's
  domain overlap with engineering/STP background is a differentiator

### Tier 3 — Opportunistic
- **Media/Content Tech** — If they have engineering teams
- **PropTech** — Growing space, needs operational discipline
- **CleanTech / Climate Tech** — Engineering-heavy, often chaotic

---

## Geographic Targeting

### Primary Markets
- **India** — Bangalore, Hyderabad, Pune, NCR, Mumbai tech ecosystems
  (timezone alignment, language comfort, market knowledge)
- **USA** — Bay Area, NYC, Austin, Seattle
  (highest rates, largest market, IST overlap for morning standups)
- **UK / Europe** — London, Berlin
  (good timezone overlap with IST, growing startup ecosystems)

### Timezone Consideration
Mohit works from IST. Best prospects are in:
- IST (India) — full overlap
- GMT/CET (UK/Europe) — 4-5.5 hour difference, manageable
- EST (US East Coast) — 9.5-10.5 hour difference, morning overlap
- PST (US West Coast) — 12.5-13.5 hour difference, minimal overlap
  (workable for async-heavy teams, not ideal for daily standups)

---

## Buying Signals — When to Reach Out

### Strong Signals (Reach out immediately)
- Just announced a funding round (Series A/B/C)
- Posted a job listing for Project Manager or Scrum Master
- Founder posted about being overwhelmed / wearing too many hats
- Company announced a major product launch timeline
- Engineering team grew 50%+ in last 6 months (check LinkedIn)
- Posted about missed deadlines, sprint issues, or delivery problems

### Medium Signals (Worth a connection request)
- Growing engineering team (3+ dev hires in last quarter)
- Active on LinkedIn discussing product development challenges
- Company in a competitive market where speed-to-ship matters
- Recently pivoted or launched a new product line
- Attending/speaking at startup or tech conferences

### Weak Signals (Connect but don't prioritize)
- General tech leadership content posting
- Hiring for roles other than PM but growing overall
- Active LinkedIn presence without specific pain indicators

---

## Red Flags — Do NOT Target

### Skip These Prospects
- **Large enterprises (500+ employees)** — They have PM teams,
  procurement processes, and won't hire a freelancer via LinkedIn
- **Companies with 3+ PMs already** — Saturated, no gap for you
- **Digital marketing agencies** — Low budget, high churn, scope creep
- **Outsourcing/body-shopping firms** — Race to bottom on rates
- **Anyone posting about layoffs** — Not in hiring/spending mode
- **Crypto/Web3 projects** — High volatility, payment risk
  (exception: well-funded, established companies in the space)
- **Anyone who hasn't posted in 6+ months** — Inactive on LinkedIn,
  your message will go unseen

### Skip These Behaviors
- Profile looks fake or recently created
- Connection count is very low (<100) — may not be active
- Already connected to 3+ freelance PMs (saturated inbox)
- Company website is down or looks abandoned

---

## Prospect Research Checklist

Before drafting ANY outreach message, Claude must gather:

### Required (Must Have All)
- [ ] Full name and current title
- [ ] Company name, stage, and approximate size
- [ ] What the company builds (product/service)
- [ ] At least ONE buying signal from the list above
- [ ] At least ONE personalization hook (recent post, project,
      milestone, shared interest)

### Nice to Have
- [ ] Recent LinkedIn posts or articles they've published
- [ ] Mutual connections
- [ ] Company's tech stack (if relevant to tool proficiency pitch)
- [ ] Funding history (Crunchbase)
- [ ] Glassdoor/team sentiment indicators

### Save Research To
File: `prospects/researched/{company-name}-{person-name}.md`

Format:
```
# {Full Name} — {Title} at {Company}

## Company
- Stage: {Seed/A/B/C}
- Size: {employee count}
- Product: {what they build}
- Recent news: {funding, launch, hiring}

## Buying Signals
- {signal 1}
- {signal 2}

## Personalization Hooks
- {hook 1: recent post about X}
- {hook 2: shared interest in Y}

## Recommended Approach
- Message type: {connection request / InMail}
- Lead angle: {what to open with}
- Service fit: {which tier from service-offerings.md}
```

---

## ICP Refinement Rules

This document is LIVING — update it based on results:

- **Monthly:** Review acceptance rates by persona. If Persona 2
  (founders) accepts at 50% but Persona 4 (TPMs) accepts at 10%,
  shift focus to founders.

- **Quarterly:** Review which industries converted to actual
  conversations or paid work. Promote winning industries,
  demote non-performers.

- **Ongoing:** If a new pattern emerges (e.g., "Climate tech CTOs
  are super responsive"), add it immediately.

Track ICP performance in `prospects/outreach-log.csv` with columns:
`date, name, company, persona_type, industry, signal, accepted_y_n,
replied_y_n, converted_y_n, notes`
