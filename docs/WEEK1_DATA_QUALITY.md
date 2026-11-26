# Week 1 — Data Quality & Freshness

Date: 2026-11-09
Status: **code complete**, one data-repair command left to run (see §4).

---

## 1. What was actually wrong

### 1.1 The 145,000,000 EGP bug (fixed)

Sellers write redundant thousands:

```
السعر : 145000 الف ج      → intended 145,000 EGP
السعر : 84500 الف ج       → intended 84,500 EGP
```

The parser multiplied the number by 1,000 whenever it saw `الف`, producing
**145,000,000 EGP** and **84,500,000 EGP**. Impact:

- 1,295 listings above 500,000 EGP (max 145M).
- Poisoned training targets, item-index regressions, and any dashboard stat.
- A paying customer would have lost trust instantly.

### 1.2 The "message_id collision" false alarm (corrected)

An ad-hoc audit query joined `parsed_accounts` to `raw_messages` on
`message_id` alone, which inflated per-channel counts. Production code already
uses the composite key `(channel_username, message_id)`. A regression test now
locks that in (`tests/test_week1_data_quality.py::TestCompositeKey`).

### 1.3 Popularity points sold as prices (fixed)

The remaining 16 "high-value" listings were not prices at all:

```
الشعبيه 700k          → popularity points, stored as 700,000 EGP
- شعبيه ( 655k )      → popularity points, stored as 655,000 EGP
مطلوب شعبيه ... مطلوب 600k → a *buyer request*, stored as 600,000 EGP
```

15 of the 16 were this pattern, which put fake 500k–700k EGP accounts at the
very top of the market index. Several of those ads did contain a real price
later in the text (`السعر: 1300`, `سعر: 4500`), so the parser now masks
popularity values and walks every price-keyword window instead of only the
first one.

Only one genuine listing above 500k remains: **1,080,000 EGP**, confirmed by
its own `22,500 USDT` price in the same ad.

### 1.4 Staleness (surfaced, not yet solved)

Newest listing: **2026-05-23** → **~4,070 hours stale** (≈170 days) as of
2026-11-09. The product cannot be sold on stale data. A freshness monitor now
makes this impossible to miss.

---

## 2. What changed

| File | Change |
|---|---|
| `parser/regex_parser.py` | Redundant `الف` guard (`num >= 1000` → don't multiply); plausibility bounds `100 ≤ price ≤ 2,000,000`; USDT/دولار USD capture; popularity masking; all price-keyword windows tried; bare `سعر` recognised |
| `scripts/repair_prices.py` | Re-parses suspicious rows on a temp copy, swaps it in atomically, updates the training CSV, invalidates the market cache; dry-run by default |
| `intelligence/freshness.py` | Read-only freshness KPIs: last listing, hours stale, 24h/7d volume, active channels |
| `api/main.py` | `/health` now includes `data`; new `/health/data` probe |
| `main.py` | `--continuous`, `--interval-minutes`, `--lookback-days`; freshness logged every cycle |
| `ops/scheduler.py` | Freshness check + stale warning each cycle |
| `database/models.py`, `database/db.py` | Unique `(channel_username, message_id)` constraint/index for `parsed_accounts` |
| `tests/test_week1_data_quality.py` | 27 tests: typos, bounds, popularity, freshness, composite-key regression |

---

## 3. Verification (already run)

```
pytest: 119 passed
ruff:   All checks passed
mypy:   Success: no issues found in 21 source files
```

Current freshness:

```json
{
  "status": "stale",
  "last_listing_at": "2026-05-23T21:16:46+00:00",
  "hours_since_last": 4070.0,
  "listings_total": 56006,
  "listings_24h": 0
}
```

Dry-run of the repair:

```
suspicious rows: 2,526
repaired: 1,282 | dropped: 1,243 | unchanged: 1
```

- **1,282** real price repairs (e.g. 145,000,000 → 145,000).
- **1,243** unusable values dropped: sub-100 EGP fragments plus popularity
  points and buyer requests that carry no sale price.
- **1** legitimate high-value listing kept unchanged (1,080,000 EGP).

---

## 4. Apply the repair (one command)

The agent sandbox is read-only for project files, so run this in **your own
terminal** (stop the API/bot first so the DB file is free):

```powershell
cd "C:\Users\n\Documents\PROJECTS\PUBG Accounts"
python scripts/repair_prices.py --apply
```

It will:

1. Copy the live DB to `%TEMP%\opencode\pubg_repair_work.db`.
2. Repair 2,526 suspicious rows.
3. Swap the repaired DB back (with a safety copy in `%TEMP%\opencode`).
4. Update `data/parsed/csv/all_parsed_accounts.csv`.
5. Delete the stale market cache so the item index rebuilds.

Then restart the API and verify:

```powershell
python -c "import sqlite3; c=sqlite3.connect('data/raw/sqlite/pubg_accounts.db'); print('suspicious:', c.execute('select count(*) from parsed_accounts where price_egp>500000 or price_egp<100').fetchone()[0]); print('max:', c.execute('select max(price_egp) from parsed_accounts').fetchone()[0])"
```

Expected: `suspicious: 1`, `max: 1080000.0` (the one genuine high-value listing,
backed by its own 22,500 USDT price). No 145M values remain.

Note: the repair runs on a temp copy and swaps it back, so it needs write
access to the DB file. If you see `Access denied` / `disk I/O error`, close
anything holding the DB (API, bot, DB browser) and re-run.

---

## 5. Start fresh data (the real Week 2 task)

```powershell
python main.py --continuous --interval-minutes 30 --lookback-days 3
```

Leave it running (or add it as a Windows service / compose service). Then:

```powershell
python intelligence/freshness.py
```

`status` should flip to `fresh` after the first cycle, and `/health/data`
will show `listings_24h > 0`.

**Do not launch paid plans until `status` is `fresh` for 7 consecutive days.**

---

## 6. Known follow-ups (not blockers)

| Issue | Size | Plan |
|---|---|---|
| UC / top-up ads parsed as account listings (`60 شده = 60 جنيه`) | 401 rows (0.7%), 251 from one channel | Week 2: listing-type classifier, exclude recharge ads from the account price index |
| Listings with no price in the text (popularity-only ads) | ~1,243 rows | Leave null; the pricer already handles missing targets |
| CSV has 11 rows not present in the DB | 11 rows | Week 2: rebuild the CSV from the DB instead of appending |

