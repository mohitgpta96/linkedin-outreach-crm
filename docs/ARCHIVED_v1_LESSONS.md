# ARCHIVED: V1 Approach — What We Did & What NOT To Do

> Status: ARCHIVED. Do not repeat this approach.
> Lesson: Document failures so we never repeat them.

---

## What V1 Did (Summary)

- Scraped 5,237 raw leads from YC batches + GitHub + HN
- Filtered to 102 leads based on "PM hiring signal"
- Target: Founders who were HIRING a PM
- Built Streamlit CRM dashboard with 4 pages
- Generated 6 pre-written messages per lead
- Tried to automate LinkedIn outreach

---

## What Was WRONG (Lessons Learned)

### ❌ WRONG ICP
- V1 targeted founders who were **hiring a PM** (job candidates)
- Mohit is a **freelance Project Manager** — he needs clients, not job leads
- These are completely different people
- **Lesson: ICP was fundamentally wrong from the start**

### ❌ WRONG APPROACH: Scraping YC Batches
- YC batch scraping gave volume but not quality
- Most YC companies don't need a freelance PM
- No real buying signal — just "they exist in tech"
- **Lesson: Volume without signal = wasted effort**

### ❌ WRONG APPROACH: PM Hiring Signal Filter
- Filtering for "companies hiring a PM" is backwards
- If they're hiring a full-time PM, they don't want a freelancer
- Or they want someone different from what Mohit offers
- **Lesson: PM job listing ≠ PM freelance buyer signal**

### ❌ WRONG TOOL: Apify Credits
- Apify free credits depleted within weeks
- Built entire pipeline on a tool that ran out of budget
- Created dependency on a paid service with no backup plan
- **Lesson: Never build core pipeline on depleted/paid tools without a free alternative ready**

### ❌ WRONG TOOL: LinkedIn API scraping
- LinkedIn-api8 and LinkedIn-data-api both shut down
- Built enrichment logic around APIs that no longer exist
- Wasted time on dead-end integrations
- **Lesson: Verify APIs are alive BEFORE building on them**

### ❌ WRONG APPROACH: Automating LinkedIn actions
- Tried to automate connection requests and messages
- LinkedIn detects automation and bans accounts
- This risks Mohit's only professional channel
- **Lesson: Never automate LinkedIn actions that risk account ban**

### ❌ WRONG APPROACH: Apollo free plan
- Integrated Apollo enrichment — but free plan is 403 on all useful endpoints
- Code exists but does nothing
- **Lesson: Test API before writing integration code**

### ❌ WRONG APPROACH: Mass scraping then filtering
- Scraped 5,237 leads then filtered down to 102 (98% waste)
- Spent compute + time on 5,135 useless leads
- **Lesson: Filter FIRST (by signal), THEN scrape. Not the other way around.**

### ❌ WRONG APPROACH: Pre-generated messages for everyone
- Generated 6 messages for all 102 leads upfront
- Most messages never used (leads may never be contacted)
- Wasted tokens and storage
- **Lesson: Generate messages ON DEMAND when a lead is about to be contacted, not in bulk upfront**

### ❌ WRONG APPROACH: Complex dashboard too early
- Built a full Jira-style CRM before having even 1 client conversation
- Over-engineered for 0 proven results
- **Lesson: Build observability AFTER validating the lead source, not before**

---

## What APIs Are DEAD (Never Use Again)

| API | Status | Why Dead |
|-----|--------|----------|
| `linkedin-api8` (RapidAPI) | DEAD | Shut down, no longer providing service |
| `linkedin-data-api` (RapidAPI) | DEAD | Shut down, no longer providing service |
| `JSearch` (RapidAPI) | BLOCKED | Not subscribed, returns error |
| `Wellfound` scraping | BLOCKED | Cloudflare JS challenge, Python requests fail |
| `Apollo.io` free plan | USELESS | 403 on all enrichment endpoints |
| `Remotive API` | USELESS | < 5 results for PM category |
| `The Muse API` | USELESS | Only 5 US enterprise results |
| `Jobicy` | USELESS | 0 results for PM/tech tags |
| `Cutshort` | BLOCKED | Requires auth, 404 on public endpoints |

---

## What Constraints Exist (Never Violate)

1. **NO LinkedIn browser automation** — not even viewing profiles automatically
2. **NO automated connection requests or messages** — Mohit sends manually always
3. **NO using Mohit's LinkedIn session to READ profiles** — only for manual sending
4. **NO mass scraping then filtering** — always signal-first, then target
5. **NO building on paid/depleted APIs** — always have a free fallback
6. **NO generating messages for leads not ready to contact** — on-demand only

---

## What To Do Instead (V2 Direction)

- Start with SIGNAL, not volume
- Signal = founder is actively struggling / has urgency / has budget
- Sources: Crunchbase (recently funded) + LinkedIn posts (founder posting about problems)
- ICP = startup founder who NEEDS a freelance PM (not hiring one full-time)
- Approach: quality 50-100 leads/month, not 5,000 scraped
- Tools: Apify harvestapi actors (no cookies, reliable, priced per use)
- Harness Engineering: Plan → Approve → Build → Observe → Feedback

> See: `docs/02-HOW-WILL-WE-DO-IT.md` for V2 approach.
