# The 60-day sprint: first profit as fast as possible

## The honest part first

**Nobody can guarantee profit in 60 days.** Anyone who promises it is selling you something. Revenue
depends on getting people to say yes, and no system controls that.

What you *can* guarantee is that **you don't lose money**, and that every deal you close is profitable:

1. **Keep fixed costs under $150/month.** The homelab is already paid for.
2. **Never build before you're paid.** Take 50% upfront on every project, or 100% for anything under $1,000.
3. **Sell fixed scope at a fixed price**, so a project can't turn into unpaid hours.

With those three rules, profit is no longer a question of luck. It becomes a question of **volume**:
how many real sales conversations you have. The agents exist to multiply that volume.

---

## 10 things successful developers have used to make money with Claude

These are recurring patterns from public build-in-public stories and freelance marketplaces. They are
not verified income claims.

| # | Model | How it makes money | Typical price |
|---|---|---|---|
| 1 | **Freelance builds with Claude Code** (Upwork, Contra, referrals) | Fixed-price projects delivered 3-5× faster than before: scripts, integrations, dashboards, DevOps, bug fixes | $300-5,000 per project |
| 2 | **AI automation for one local niche** ("AI automation agency") | Speed-to-lead, missed-call text-back, reminders, review requests built in n8n + Claude | $1,500-3,000 setup + $300-1,000/mo |
| 3 | **Website rebuild + AI lead capture** for local businesses | Modern site plus an AI chat/form that answers and books 24/7 | $1,000-3,000 + $50-150/mo hosting |
| 4 | **AI integration consulting** for small companies | Chat-over-your-documents, internal tools, workflow audits | $3,000-15,000 per project |
| 5 | **Managed IT and security for small offices** ("MSP-lite") | Firewall, backups, monitoring (your pfSense/Wazuh skills) | $300-1,500/mo per office |
| 6 | **Research and data services** | Market research, competitor reports, enriched lead lists (public business data only) | $200-2,000 per report |
| 7 | **Micro-SaaS** built with Claude Code | Niche software subscriptions, Chrome extensions, Shopify apps | $10-100/mo per user, slow ramp |
| 8 | **Templates and digital products** | n8n workflow packs, Claude Code setups, Notion systems | $20-150 each, needs an audience |
| 9 | **Build-in-public content** (YouTube, newsletter) | Sponsorships, affiliates, inbound clients | Months before it pays |
| 10 | **Courses, cohorts, and coaching** | Teaching AI and automation skills | Needs an audience and credibility first |

## Scoring them for *your* 60 days

Each model is scored from 1 to 5 on each criterion (5 is best):

| # | Model | Speed to 1st $ | No audience needed | Fits your skills | Low startup cost | Recurring | Agent leverage | **Total /30** |
|---|---|---|---|---|---|---|---|---|
| 2 | AI automation, one local niche | 4 | 5 | 5 | 5 | 5 | 5 | **29** |
| 1 | Freelance builds with Claude Code | 5 | 5 | 5 | 4 | 2 | 4 | **25** |
| 3 | Website + AI lead capture | 4 | 5 | 4 | 5 | 3 | 4 | **25** |
| 5 | MSP-lite IT and security | 3 | 5 | 5 | 4 | 5 | 2 | 24 |
| 4 | AI integration consulting | 3 | 4 | 4 | 5 | 3 | 4 | 23 |
| 6 | Research and data services | 3 | 4 | 3 | 5 | 3 | 5 | 23 |
| 7 | Micro-SaaS | 1 | 3 | 4 | 4 | 5 | 4 | 21 |
| 8 | Templates / digital products | 2 | 2 | 4 | 5 | 3 | 5 | 21 |
| 9 | Build-in-public content | 1 | 1 | 4 | 5 | 4 | 5 | 20 |
| 10 | Courses / coaching | 1 | 1 | 3 | 4 | 3 | 3 | 15 |

Items 7-10 are good businesses, but they need an audience or months of runway, so they come after
day 60. The content engine starts in the background now, because it compounds.

## The final top 3

1. **AI automation for one local niche.** The best overall: recurring revenue, no audience needed,
   and the agent team does most of the work. This is the business you're building.
2. **Freelance builds with Claude Code.** The *fastest* cash. Demand already exists on the
   marketplaces, so you can be paid within 2-3 weeks. It funds the sprint and builds your portfolio.
3. **Website + AI lead capture.** The easiest "yes" for a local owner who isn't ready for a full
   automation package. It gets you in the door, and you upsell into #1 within 30 days.

These three combine into one process: freelance work brings fast cash and proof, websites open doors,
and automation retainers make it recurring.

---

## The process: a pre-sold 60-day sprint

### Days 1-7: set up (no selling yet)

| Task | Who |
|---|---|
| Fix the cp01 disk; deploy AgentOS phase 1 ([DEPLOY.md](DEPLOY.md)) | You |
| Pick the niche (`niche-researcher` + `strategist`) | Agents → you decide |
| Build **2 demos** with Claude Code: (a) a speed-to-lead bot for a fictional business in your niche; (b) a website rebuild of a real local business's site (don't publish it; it's for your pitch) | You + Claude Code |
| Upwork and Contra profiles that focus on **"AI automation + n8n + Python + Kubernetes/DevOps"** | You (`quality-reviewer` edits the copy) |
| Stripe, Cal.com booking link, 1-page contract (50% deposit, fixed scope, 2 revision rounds) | You |
| Start warming up the separate outreach domain | You |

### Days 8-30: two sales tracks running at once

**Track A: freelance (fast cash)**
- Every morning, paste 10-15 fresh job posts into Mission Control → `freelance-bidder`.
- Send the best **5 bids a day** by hand. Target fixed-price jobs between $300 and $3,000 in automation,
  AI integration, n8n, Python, or DevOps. Bid early, and answer the client's question in the first two lines.
- Budget about $30-50 for Upwork Connects.

**Track B: local businesses (recurring)**
- `lead-sourcer` → `lead-enricher` → `outreach-writer`: 15 personal emails a weekday, which you approve in batches.
- **Also do 5 phone calls or walk-ins a day.** In-person and phone close local owners far faster than email.
- The offer to open with: *"Free 15-minute missed-lead check. I'll call your business after hours and
  show you what happens to that customer."* Then pitch the website or Starter package.

**Goal by day 30:** at least 1 paid project (deposit received).

### Days 31-60: deliver, convert, compound

- Deliver fast, using `solutions-architect` and `workflow-builder` (set `AGENTOS_PHASE=2` once the first deposit lands).
- At every delivery, offer the **monthly retainer** (hosting, monitoring, tweaks). Ask for a testimonial and a referral.
- Keep both sales tracks running at the same daily numbers. Raise prices 20% after the first 2 testimonials.
- Turn each delivered project into one video or post, via `content-strategist`.

### Leading indicators (check them daily in Mission Control)

| By day | Outreach sent | Bids sent | Real conversations | Paid deals |
|---|---|---|---|---|
| 15 | 100 + 50 calls/visits | 35 | 4 | 0-1 |
| 30 | 250 + 100 calls/visits | 75 | 10 | 1-2 |
| 60 | 550 + 200 calls/visits | 150 | 25 | 3-6 |

**Kill rule:** if you have 10+ conversations by day 30 but no sale, change the **offer or price**.
If you have fewer than 10 conversations, increase **volume**, or change the **niche**. Don't change the tools.

### What 60 days realistically produces

| Outcome | Revenue in 60 days | What it looks like |
|---|---|---|
| Slow | $0-1,500 | A few small freelance jobs; the pipeline is building |
| **Likely, if you hit the daily numbers** | **$2,500-6,000** | 2-4 freelance projects + 1-2 local setups + first retainers |
| Strong | $8,000-12,000+ | A higher-value project lands, and retainers start stacking |

Costs over the same 60 days are about $150-300 (API, domains, Workspace, Connects). With deposits
upfront, every closed deal is profitable from day one. **$10k in a single month usually comes in
months 4-6, once retainers stack.** The sprint is how you get there without losing money on the way.
