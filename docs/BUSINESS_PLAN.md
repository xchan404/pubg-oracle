# Project Oracle — Business Plan
## From scraper to a money-making market-intelligence business

> **One line:** You already own the hardest asset — a trained Arabic PUBG-account pricing engine fed by real Telegram market data. The money is not in the model; it is in **distribution + freshness + trust**. This plan turns the code into a product people pay for every month.

---

## 0. Executive summary

| Question | Answer |
|---|---|
| What is the product? | **Oracle** — a price-intelligence and deal-alert service for the PUBG Mobile account market in Egypt/MENA. |
| Who pays? | Flippers/resellers (fast cash), account stores/channels (volume), casual buyers (one-off checks). |
| How do we charge? | Freemium subscription (299 EGP/mo), store plan (1,999 EGP/mo), pay-per-check credits, later white-label + escrow fee. |
| Why now? | The engine, bot, dashboard, item index, repost detection and trust scores are **already built and tested (92 tests)**. Only the commercial layer is missing. |
| What is the #1 blocker? | **Fresh data and distribution.** Data ends 2026-05-23 (≈5.5 months stale) and there are **0 users / 0 verified sales labels**. |
| Realistic 12-month target | 600–800 paying users + 25–40 stores → **250k–400k EGP MRR** (~$5k–8k/mo), break-even inside 60–90 days. |
| Biggest risk | Legal/platform gray zone around account trading → position as *market intelligence*, not brokerage. |

---

## 1. Reality check — what you actually own

Measured from the live database (`data/raw/sqlite/pubg_accounts.db`) and model artifacts on 2026-11-09:

| Asset | Current state | Verdict |
|---|---|---|
| Listings | **56,006** raw Telegram ads | Strong seed corpus |
| Priced listings | **33,174 (59.2%)** | Good; 70%+ needed for a paid product |
| Channels | **8** (2 dominate: TA3MIASTOREMiNi1, sa3kgaming1) | Too narrow → single-point-of-failure |
| Date coverage | 2024-12-31 → **2026-05-23** | ⚠️ **Stale by ~5.5 months** |
| Median asking price | **4,500 EGP** (~$90) | Healthy mass market |
| Price spread | p25 = 2,300 · p75 = 8,500 · p90 = 25,000 · p99 = 27.5M | Whale tail is noisy |
| Price outliers | **1,295 listings > 500k EGP** (max 145M) | ✅ Fixed Week 1: redundant `الف` typos + popularity points read as prices |
| Model accuracy | MAE ≈ **1,450 EGP** (retrain log) / 2,789 (eval); conformal ±5,346 cheap, ±28,783 whale | Sellable for cheap/mid; do **not** promise whale accuracy |
| Intelligence | Item index (32 items), repost engine (25,584 unique accounts, 19% repost), channel trust A+→D | **Unique differentiator** — nobody else sells this in Arabic |
| Bot | Sniper alerts + one-tap feedback buttons + `/review` | This is your **distribution + data flywheel** |
| Dashboard/API | 28 routes, 6 tabs, WebSocket feed | Ready for B2B demo |
| Auth / billing / entitlements | **None** | ⚠️ The whole commercial layer is missing |
| Verified sale labels | **0** | Model cannot improve until real users tap |
| Legal entity / terms / privacy | **None** | Needed before charging money |
| Data integrity | Composite `(channel_username, message_id)` keys verified + regression test | ✅ Correct (my earlier ad-hoc query was wrong) |

### The honest conclusion
You have a **90%-built product and a 0%-built business**. The next 90 days should be 20% engineering, 80% packaging, distribution and trust.

---

## 2. Market — who has the money

### 2.1 Market math (bottom-up estimate)

- ~**4,000–4,700 listings/month** across the 8 scraped channels alone.
- Assume **20–25% actually sell** → 800–1,150 transactions/month.
- × median **4,500 EGP** → **3.6M–5.2M EGP GMV/month** in 8 channels.
- The Egyptian PUBG trading ecosystem likely has **50–150 active channels** → **20M–60M EGP/month GMV** (order of magnitude, not audited).

A flipper earning **500–2,000 EGP profit per flip** needs only **2–4 flips/month** to justify a 299 EGP subscription. That is an extremely easy value proposition — **if** the alerts are fast and accurate.

### 2.2 Customer segments

| Segment | Size (est.) | Pain | Willingness to pay | Product |
|---|---|---|---|---|
| **Flippers / resellers** | 300–1,500 active | Miss underpriced accounts; can't value fast | 200–500 EGP/mo | Pro alerts + valuation + portfolio |
| **Account stores / channels** | 50–150 | Set prices, manage inventory, prove trust | 1,000–5,000 EGP/mo | Business plan, bulk valuation, API, trust badge |
| **Casual buyers/sellers** | 10k+ | Afraid of overpaying | 10–50 EGP/check | Free tier + credit packs |
| **Middlemen** | 50–200 | Need escrow + reputation | % of transaction | Escrow partnership (later) |
| **Channel owners** | 50–150 | Want engagement + monetization | Revenue share | White-label price bot |
| **Marketplaces / content creators** | 10–30 | Need Arabic price data | API license | Data API (later) |

### 2.3 Competition

| Competitor type | Weakness you exploit |
|---|---|
| Facebook groups / Telegram "price police" | Manual, slow, biased, no data |
| Global marketplaces (Gameflip, PlayerAuctions) | USD pricing, wrong market, no Telegram coverage |
| Random price bots | No ML, no history, no item index, no trust scores |
| Middlemen | Charge 5–10%, no analytics |
| **You** | Arabic-first, EGP-native, real Telegram data, explainable model, repost/trust intelligence |

**Moat to build:** proprietary verified-sale data (from the feedback buttons) + channel trust graph + freshness. None of these can be copied quickly.

---

## 3. The money map — 7 revenue streams, ranked

| # | Stream | Speed to revenue | Effort | Ceiling | Recommendation |
|---|---|---|---|---|---|
| 1 | **Pro subscription** (alerts + valuation) | 2–3 weeks | Low | High | **Start here** |
| 2 | **Store/Business plan** (bulk + API) | 4–6 weeks | Medium | High | Phase 2 |
| 3 | **Pay-per-check credits** | 1–2 weeks | Low | Medium | Bundle with free tier |
| 4 | **Channel partnership / revenue share** | 2–4 weeks | Low | High (distribution) | Do in parallel |
| 5 | **White-label bot for channel owners** | 8–12 weeks | Medium | High | Phase 3 |
| 6 | **Escrow / middleman fee (1–2%)** | 4–6 months | High (legal) | Very high | Only with partner |
| 7 | **Data/API licensing** | 6–12 months | Medium | Medium | Opportunistic |

**Rule:** never run more than two monetization experiments at once. Subscription + channel partnerships first.

---

## 4. Recommended model — "Freemium + Pro + Stores"

### 4.1 Packaging (launch prices, EGP)

| Plan | Price | What they get | Target |
|---|---|---|---|
| **Free** | 0 | 3 valuations/day, daily top-3 deals (delayed 30 min), basic market stats | Acquisition |
| **Pro** | **299 EGP/mo** or **2,499 EGP/yr** (save 30%) | Unlimited valuations, real-time alerts, custom filters (budget/items/segment/min profit), portfolio P&L, price history, priority support | Flippers |
| **Business** | **1,999 EGP/mo** | 5 seats, bulk valuation (CSV/Excel), 10k API calls/mo, branded weekly report, trust badge, dedicated support | Stores/channels |
| **White-label** | **5,000–15,000 EGP/mo** + setup | Bot under the channel's brand, revenue share 20–30% | Channel owners |
| **Credits** | **15 EGP/check** (10 for 120) | One-off deep valuation report | Casual users |

> Anchor the annual plan. Launch with "first 50 Pro at 199 EGP/mo forever" to create urgency.

### 4.2 Payment rails (Egypt reality)

| Method | Use | Notes |
|---|---|---|
| **Telegram Stars** | Global/instant | Easiest MVP; platform fee applies |
| **Vodafone Cash / InstaPay** | Local | Manual activation + admin approval in bot (fastest to launch) |
| **Paymob / Fawry** | Scale | Requires company + KYC; add at 50+ paying users |
| **Bank transfer** | Business plan | Invoice-based for stores |

Start with **Stars + manual Vodafone Cash**. Automate later.

### 4.3 Unit economics

| Item | Cost |
|---|---|
| VPS (API + bot + scheduler) | $20–40/mo |
| Proxies / Telegram accounts | $20–60/mo |
| Payment fees | 2.5–3.5% |
| Support (your time) | 5–10 h/week early |
| Marketing | 10–20% of revenue |
| **Marginal cost per user** | **< 5 EGP/mo** |

At 299 EGP/mo, **gross margin > 95%**. Break-even at ~5–8 Pro subscribers.

### 4.4 Financial scenarios

| Scenario | Paying users | Stores | MRR (EGP) | MRR (~USD) |
|---|---|---|---|---|
| **Conservative (month 3)** | 40 Pro | 3 | ~18,000 | ~$360 |
| **Base (month 6)** | 200 Pro | 12 | ~85,000 | ~$1,700 |
| **Aggressive (month 12)** | 800 Pro | 40 + 3 white-label | ~390,000 | ~$7,800 |

Assumptions: 3–5% free→paid conversion, <8% monthly churn, 20–30% of revenue reinvested in channel partnerships.

---

## 5. Product roadmap mapped to revenue

### Phase A — "Revenue-ready foundation" (weeks 1–3) — **must ship before charging**

**Engineering**
1. **Fix data integrity (P0)**
   - Composite identity `(channel_username, message_id)` everywhere: `database/ads.py`, `scraper/`, `intelligence/market_data.py`, `ml/dataset_builder.py`.
   - Migration + unique index; backfill.
2. **Price outlier QA** ✅
   - Sanity bounds `100 ≤ price ≤ 2,000,000` + redundant `الف` guard.
   - Popularity points (`شعبيه 650k`) and buyer requests are no longer read as prices.
   - 2,526 suspicious rows audited; repair script + 27 tests added.
3. **Freshness pipeline**
   - Continuous scraper mode in `scraper/` (not one-shot).
   - `ops/scheduler.py`: scrape every 15–30 min, health metric "minutes since last listing".
   - Expand to 15–30 channels (see GTM).
   - Alert if no new listings in 2h.
4. **Accounts + entitlements**
   - New `database/users.py` (telegram_id, plan, expiry, usage counters).
   - New `services/entitlements.py` (free/pro/business gates).
   - Bot deep-link login: `/start` → magic token → web session.
5. **Payments (MVP)**
   - `services/payments.py`: Telegram Stars invoice + manual Vodafone Cash request.
   - `database/subscriptions.py`: plan, start, expiry, renewal, refund log.
   - Admin commands in bot: approve/reject payment, extend, ban.
6. **Metering + free tier**
   - `services/usage.py`: 3 checks/day free, unlimited Pro; API rate limits.
7. **Analytics**
   - `services/analytics.py`: activation, DAU/WAU, checks/user, conversion, churn events.
   - Simple `/admin/stats` endpoint + dashboard tab.

**Business**
- Write Terms of Service + Privacy Policy (Arabic + English).
- Define refund policy.
- Open a Vodafone Cash wallet / InstaPay account for collections.
- Draft partner pitch deck (1 page).

**Exit criteria:** a stranger can pay 299 EGP and get Pro access without you touching the server.

---

### Phase B — "Paid launch" (weeks 4–6)

**Engineering**
1. **Alert quality engine**
   - Personalized filters: budget range, must-have items, segment, min profit, channel blocklist.
   - Deduplicate alerts by fingerprint (already have `ml/fingerprint.py`).
   - Latency target: **< 3 minutes** from listing to alert.
   - "Why this deal" explanation card (SHAP/feature contributions already possible).
2. **Valuation report v2**
   - Shareable image/PDF card (Arabic) with fair value, conformal range, comparables, item breakdown.
   - Watermark free tier; clean for Pro.
3. **Portfolio + sold tracking**
   - Already built (`intelligence/portfolio.py`, feedback labels). Surface in bot: `/portfolio`.
4. **Referral system**
   - `services/referrals.py`: unique code, 1 week free per paid referral, leaderboard.
5. **Onboarding funnel**
   - `/start` → choose goal (flip / buy / sell) → budget → 3 sample alerts → paywall.

**Business / GTM**
- Recruit **20 beta flippers** (free Pro for 30 days in exchange for feedback + testimonial).
- Partner with **3 channels**: free price bot + pinned post + 20–30% revenue share.
- Daily free "top 3 underpriced accounts" post in partner channels (your best ad).
- Launch offer: first 50 Pro at 199 EGP/mo locked forever.

**Exit criteria:** 100+ activated users, 15–25 paying, first 5 verified sales labels/week.

---

### Phase C — "B2B / stores" (weeks 7–12)

**Engineering**
1. **Business dashboard**
   - Bulk valuation: upload CSV/Excel of ads → priced sheet + profit ranking.
   - Inventory view (positions, aging, P&L).
   - Team seats + roles.
2. **Public API v1**
   - API keys, quotas, docs (`/docs` already exists).
   - Endpoints: `/v1/valuate`, `/v1/item-index`, `/v1/market/summary`, `/v1/deals`.
3. **Trust badges**
   - Sell "Verified by Oracle" badge to stores based on `intelligence/trust.py` grades.
   - Public store profile page.
4. **Weekly market report**
   - Auto-generated Arabic report (PDF + Telegram post): price index, top movers, repost warnings, trust changes.
   - Free version = marketing; paid = detailed + early.

**Business**
- Close **10–15 stores** at 1,999 EGP/mo.
- Pilot **1 white-label** channel bot (5,000 EGP/mo).
- Start escrow partner conversations (lawyer + trusted middleman).

**Exit criteria:** 60k–90k EGP MRR, churn < 8%, 10+ verified labels/week.

---

### Phase D — "Ecosystem" (months 4–6)

1. **Escrow/middleman integration** — partner-operated, 1–2% fee, Oracle provides valuation + trust + dispute evidence. **Do not hold funds yourself without legal structure.**
2. **White-label rollout** — 3–5 channels.
3. **Data API licensing** — marketplaces/content creators.
4. **Mobile-first PWA** — installable, push notifications.
5. **Expansion** — GCC (SAR/AED pricing, 2–3× ARPU), same engine, new channels.

---

### Phase E — "Scale" (months 6–12)

- 1,000+ paying users, 40+ stores.
- Verified-sale dataset > 5,000 labels → retrain → whale accuracy improves → premium "whale valuation" tier.
- Consider a licensed company + Paymob/Fawry.
- Explore adjacent games (Free Fire, Fortnite) with the same engine.

---

## 6. Go-to-market playbook

### 6.1 The wedge: free price-check bot inside partner channels

Channel owners have the audience you lack. Give them:
- A free branded price bot in their channel (they look high-tech).
- 20–30% revenue share on subscriptions sourced from their channel.
- A trust badge and weekly market report content.

In exchange: pinned post + bot admin rights + one promo post/week.

**Target list:** start with the 8 scraped channels, then expand to 30.

### 6.2 First 100 users (14 days)

| Day | Action |
|---|---|
| 1–2 | Fix data integrity + outliers; restart scraper continuously |
| 3–4 | Ship free tier + 3-check limit + onboarding |
| 5–6 | Ship Stars + Vodafone Cash payments; test end-to-end |
| 7 | Recruit 20 beta flippers from the channels (DM + free month) |
| 8–10 | Partner with 3 channels; publish daily top-3 deals |
| 11–12 | Launch referral + annual plan |
| 13–14 | Collect testimonials, publish "first week results" post |

### 6.3 Content engine (Arabic)

- **TikTok/Reels/Shorts:** "قيّم حسابك قبل ما تشتري" — 30-second valuations of real listings.
- **Telegram:** daily top deals, weekly market report, "repost of the week" (expose fake listings).
- **YouTube:** monthly "state of the PUBG account market" (uses item index + trust data).
- **SEO (later):** Arabic landing pages: "سعر حساب ببجي", "تقييم حساب ببجي".

### 6.4 Referral loop

- 1 week free per paid referral.
- Store referral: 1 month free per 5 Pro referrals.
- Leaderboard + badges for top referrers.

---

## 7. Trust, legal, and compliance

> This section is not optional if you charge money. Budget one lawyer review (~5–10k EGP) before escrow.

| Risk | Reality | Mitigation |
|---|---|---|
| **PUBG ToS** | Account trading violates PUBG Mobile terms | Position as **market data / price discovery**, not a marketplace or broker. No facilitation of transfer. Clear disclaimer. |
| **Telegram ToS** | Scraping can violate terms / lead to bans | Use official API + rate limits; no spam; no resale of raw messages; respect privacy. |
| **Personal data (Egypt PDPL 151/2020)** | Ads may contain phone numbers/names | Redact PII in outputs; store minimum; no PII resale; privacy policy; deletion requests. |
| **Payments** | Consumer protection + refunds | Clear terms, refund window, invoices, manual approval early. |
| **Fraud** | Fake listings, chargebacks | Trust scores, verified labels, escrow only via partner, manual review for high-value. |
| **Liability** | Bad valuation → user loses money | Show conformal range + confidence + "not financial advice"; cap liability in ToS. |
| **Minor users** | Account trading often involves minors | 18+ terms; age gate in onboarding. |

**Business positioning line:** *"Oracle is a market-intelligence service that estimates fair prices from public listings. It does not sell, broker, or transfer game accounts."*

---

## 8. Metrics that matter

| Metric | Target | Why |
|---|---|---|
| Data freshness | < 24h (alert < 3 min) | Core promise |
| Price detection rate | > 70% | Product quality |
| Free → Pro conversion | 3–5% | Revenue engine |
| Monthly churn | < 8% | LTV |
| Alerts opened | > 60% | Engagement |
| Verified labels/week | 20+ | Model flywheel |
| Checks per active user/week | 5+ | Habit |
| MRR / ARPU | 300 EGP / 350 EGP | Business health |
| CAC (channel partner) | < 300 EGP | Payback < 1 month |
| Support tickets/100 users | < 10 | Scalability |

Dashboard: add an **Admin → Business** tab with MRR, paying users, churn, funnel, data freshness.

---

## 9. Risks and mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Data goes stale again | High | Fatal | Continuous scraper + freshness alert + on-call runbook |
| Telegram bans accounts | Medium | High | Multiple accounts, proxies, official API, diversify channels |
| Model accuracy disappoints whales | Medium | Medium | Sell confidence tiers; verified-sale flywheel; don't overpromise |
| Channel partners refuse | Medium | High | Start with 1–2 friendly channels; offer revenue share + free tech |
| Legal challenge / ToS | Low–Medium | High | Positioning, disclaimers, lawyer review, no escrow without partner |
| Payment friction in Egypt | High | Medium | Stars + manual wallets first; Paymob at scale |
| Competitor copies you | Medium | Medium | Speed, verified data, channel lock-in, brand |
| You burn out | Medium | High | Automate ops; focus on 2 revenue streams; hire support at 100 users |

---

## 10. 30 / 60 / 90-day execution plan

### Days 1–30 — "Make it chargeable"
- [ ] Fix `(channel, message_id)` integrity + migration
- [ ] Price outlier audit + parser guards + tests
- [ ] Continuous scraper + freshness monitoring + 15 channels
- [ ] Users, entitlements, usage metering
- [ ] Telegram Stars + Vodafone Cash payments + admin approval
- [ ] Free tier + onboarding + 3-check limit
- [ ] Terms + Privacy (Arabic/English)
- [ ] Recruit 20 beta flippers
- [ ] **Target: 15 paying users, 20k EGP MRR**

### Days 31–60 — "Make it grow"
- [ ] Personalized alerts + latency < 3 min
- [ ] Shareable valuation cards
- [ ] Portfolio in bot
- [ ] Referral system
- [ ] 3 channel partnerships + daily free deals post
- [ ] Weekly market report (auto)
- [ ] **Target: 60 paying users, 25k–40k EGP MRR**

### Days 61–90 — "Make it B2B"
- [ ] Bulk valuation (CSV/Excel)
- [ ] Public API v1 + keys + quotas
- [ ] Business dashboard + seats
- [ ] Trust badges for stores
- [ ] 10–15 store customers
- [ ] White-label pilot
- [ ] **Target: 100+ paying users + 10 stores, 60k–90k EGP MRR**

---

## 11. Concrete engineering backlog (file-level)

| Task | Files | Est. |
|---|---|---|
| Composite key + migration | `database/ads.py`, `scraper/*`, `intelligence/market_data.py`, `ml/dataset_builder.py` | 2–3 d |
| Price outlier guards | `parser/*`, `tests/test_platform.py` | 1–2 d |
| Continuous scraper + health | `scraper/*`, `ops/scheduler.py` | 2–3 d |
| Users + entitlements | `database/users.py`, `services/entitlements.py` | 2 d |
| Payments (Stars + manual) | `services/payments.py`, `database/subscriptions.py`, `bot/telegram_bot.py` | 3–4 d |
| Usage metering | `services/usage.py`, `api/main.py` | 1–2 d |
| Analytics | `services/analytics.py`, admin routes | 2 d |
| Alert filters + dedupe | `bot/telegram_bot.py`, `database/alerts.py` | 3 d |
| Shareable report card | `intelligence/reports.py`, `api/static/*` | 3 d |
| Referrals | `services/referrals.py`, bot | 2 d |
| Bulk valuation | `api/main.py`, `intelligence/bulk.py` | 3–4 d |
| API keys + quotas | `api/auth.py`, `database/api_keys.py` | 2–3 d |
| Admin business tab | `api/static/index.html`, `app.js`, admin routes | 3 d |
| Trust badges | `intelligence/trust.py`, public pages | 2 d |

**Total Phase A–C:** ~6–8 weeks of focused work.

---

## 12. What NOT to build yet

- ❌ Mobile app (PWA is enough)
- ❌ Escrow before legal structure
- ❌ Multi-game expansion
- ❌ Fancy ML upgrades (transformer, LLM pricing) — data > models now
- ❌ Crypto payments
- ❌ Marketplace with checkout (huge legal/support burden)

---

## 13. Decisions I need from you

1. **Operating model:** run it as a real business (entity, payments, support) or sell/license the tech to an existing store/channel?
2. **Market:** Egypt only first, or Egypt + GCC (higher prices, harder payments)?
3. **Time/budget:** how many hours/week can you invest, and what monthly infra/marketing budget is comfortable?
4. **Access:** do you personally know any channel owners or big flippers who could be the first 3 partners?

Answer those four and I'll convert Phase A into a day-by-day build plan and start shipping it.

---

## 14. YOUR CHOSEN PATH (locked 2026-11-09)

### 14.1 Decisions

| Decision | Choice | Consequence |
|---|---|---|
| Operating model | **Run it as a business** | Need terms, refund policy, payment collection, support workflow |
| Market | **Egypt + GCC** | Multi-currency from day one; GCC ARPU 2–3× Egypt; more channels to scrape |
| Time | **5–10 h/week** | No big-bang launch. Revenue-critical path only. ~12 weeks to B2B, not 6. |
| Budget | **Minimal** | Free-tier infra, Telegram Stars + manual wallets, no paid ads — channel partnerships only |
| Access | **Warm channel contacts** | GTM starts in week 1, in parallel with engineering |

### 14.2 What this means (the honest trade-off)

At 5–10 h/week you have roughly **40–60 productive hours/month**. Phase A engineering alone is ~35–45 h. Therefore:

- **Weeks 1–4:** engineering + partner recruitment in parallel (partners first — they take calendar time, not build time).
- **Weeks 5–8:** paid launch + iteration.
- **Weeks 9–12:** only then start B2B.
- **Defer:** bulk CSV valuation, public API, white-label, escrow. They are Phase C/D, not now.

### 14.3 Pricing for Egypt + GCC

| Plan | Egypt | GCC | Notes |
|---|---|---|---|
| Free | 0 | 0 | 3 checks/day, delayed top-3 deals |
| **Pro monthly** | **299 EGP** | **79 SAR / 79 AED** | Real-time alerts, unlimited checks, filters |
| **Pro annual** | **2,499 EGP** | **699 SAR / 699 AED** | ~30% discount, improves cash flow |
| **Business** | **1,999 EGP** | **499 SAR / 499 AED** | 5 seats, bulk, API, badge |
| Credits | 15 EGP/check | 5 SAR/check | Casual buyers |

GCC pricing is ~3× Egypt because account prices and purchasing power are higher. Keep the same product; localize currency and channels.

### 14.4 Minimal-budget infrastructure

| Need | Choice | Cost |
|---|---|---|
| API + bot + scheduler | Existing PC initially → Oracle Cloud Always Free / Hetzner CX22 | $0–6/mo |
| Database | SQLite (already) → Postgres only at 1k+ users | $0 |
| Payments | Telegram Stars (global) + Vodafone Cash/InstaPay manual (Egypt) | 0 fixed |
| Scraping | Existing Telegram session + 1 backup account | $0 |
| Monitoring | `/health` + Telegram alert to yourself | $0 |
| Marketing | Channel partnerships (rev share, no upfront) | 20–30% of referred revenue |

**Total fixed cost: under $10/month** until ~100 paying users.

### 14.5 12-week calendar (5–10 h/week)

#### Weeks 1–2 — Foundation + partners (≈16 h)
**Engineering (10 h)**
- [x] Composite-key regression test (production joins were already correct)
- [x] Price outlier guards + `scripts/repair_prices.py` for the 1,295 bad rows
- [x] Continuous scraper (`--continuous`) + freshness monitor (`/health/data`)

**Business (6 h)**
- [ ] DM 10 warm contacts; pitch: free branded price bot + 25% revenue share
- [ ] Sign 2–3 partner channels
- [ ] Draft Terms + Privacy (Arabic/English, template + lawyer later)

**Milestone:** fresh data flowing, 2–3 partners verbally committed.

#### Weeks 3–4 — Chargeable product (≈16 h)
**Engineering (14 h)**
- [x] `database/users.py` + `services/entitlements.py`
- [x] `services/usage.py` (3/day free, unlimited Pro)
- [x] `services/payments.py` + `scripts/admin.py` (manual Vodafone Cash approval)
- [x] In-bot wallet flow: `/pay` → proof (text or screenshot) → owner ✅/❌
- [x] Subscription expiry + renewal reminders (`services/lifecycle.py` + scheduler)
- [x] `/start` onboarding, `/plans`, `/me`, `/country`, free-tier gate
- [ ] Telegram Stars invoice (deferred: manual wallets cover Egypt launch)

**Business (2 h)**
- [ ] Open Vodafone Cash / InstaPay collection
- [ ] Set refund policy

**Milestone:** a stranger can pay and get Pro without you touching the server.

#### Weeks 5–6 — Launch (≈16 h)
**Engineering (10 h)**
- [ ] Alert filters (budget, items, segment, min profit) + fingerprint dedupe
- [ ] Latency instrumentation (target < 3 min)
- [ ] Shareable Arabic valuation card (image/PDF)

**Business (6 h)**
- [ ] 20 beta flippers (free month for feedback)
- [ ] Daily "top 3 deals" post in partner channels
- [ ] Launch offer: first 50 Pro at 199 EGP/mo locked forever

**Milestone:** 15–25 paying users, first verified labels.

#### Weeks 7–8 — Retention + GCC (≈16 h)
**Engineering (8 h)**
- [ ] Referral codes + rewards
- [ ] Portfolio in bot (`/portfolio`)
- [ ] Basic analytics dashboard (MRR, churn, conversion)

**Business (8 h)**
- [ ] Add 5–8 GCC channels to the scraper
- [ ] Currency detection in parser (SAR/AED/EGP)
- [ ] Recruit 2 GCC partners; launch SAR pricing

**Milestone:** 40–60 paying, 30k–45k EGP MRR.

#### Weeks 9–12 — B2B (≈16–24 h)
- [ ] Bulk valuation (CSV upload) — only if 5+ stores asked
- [ ] Business plan + seats
- [ ] Trust badges for stores
- [ ] 5–10 store customers
- [ ] Weekly auto market report

**Milestone:** 80–120 paying + 5–10 stores, 60k–90k EGP MRR.

### 14.6 Division of labor

| Task | You | Me (agent) |
|---|---|---|
| Partner outreach / DMs | ✅ (your contacts) | Draft messages, pitch deck, rev-share terms |
| Payment wallet / legal | ✅ | Templates, policy text, invoice format |
| Data fixes, auth, billing code | — | ✅ |
| Scraper ops / monitoring | — | ✅ setup + runbook |
| Content (daily posts) | ✅ approve | ✅ generate from live data |
| Support | ✅ early | Macros + FAQ + bot self-service |

### 14.7 The single next action

**This week, before writing any billing code:** send the partner pitch to 10 contacts. Distribution is the only thing that cannot be coded, and it has the longest lead time. Everything else can ship in parallel.

### 14.8 Success criteria for the 12 weeks

- [ ] Data freshness < 24h, 15+ channels
- [ ] 80–120 paying users, 5–10 stores
- [ ] 60k–90k EGP MRR
- [ ] 20+ verified sale labels/week
- [ ] Churn < 8%/month
- [ ] You spend < 10 h/week on operations (automation working)
