# Week 3 — Monetization Foundation

Date: 2026-11-14
Status: **code complete and tested**; bot UI wiring is the remaining step.

---

## 1. What was built

| Layer | File | Purpose |
|---|---|---|
| Data model | `database/models.py` | `users`, `subscriptions`, `payments`, `usage_events`, `credit_ledger` |
| User repo | `database/users.py` | Create/find users, refresh profile, attach partner referral, ban |
| Plans | `services/entitlements.py` | Plan specs, active subscription, grant/renew, expiry |
| Metering | `services/usage.py` | 3 checks/day free, unlimited Pro, credit fallback |
| Payments | `services/payments.py` | Create/approve/reject payments, 25% partner share, payout report |
| Catalog | `services/catalog.py` | Offers, per-currency prices, what each offer grants |
| Bot UX | `bot/paywall.py` | Onboarding texts, plans, quota, payment instructions, activation |
| Notifier | `services/notifier.py` | Bot API sender for background jobs (no second session) |
| Lifecycle | `services/lifecycle.py` | Expiry notices, renewal reminders, daily digest, once-a-day gate |
| Admin CLI | `scripts/admin.py` | Operate everything manually before/alongside the bot UI |
| Tests | `tests/test_entitlements.py`, `tests/test_paywall.py`, `tests/test_lifecycle.py` | 59 tests across plans, limits, credits, payments, lifecycle |

New tables are created automatically by `init_db()` (`Base.metadata.create_all`).

---

## 2. Plans (single source of truth)

| Plan | Checks/day | Features |
|---|---|---|
| `free` | 3 | `delayed_deals` |
| `pro_monthly` | unlimited | realtime alerts, filters, full index |
| `pro_annual` | unlimited | same as monthly |
| `business` | unlimited | + bulk export, API access, badge, 5 seats |

Pricing lives in the plan docs, not in code — change prices without a deploy
(`docs/BUSINESS_PLAN.md` §14.3).

**Renewals stack:** granting Pro while Pro is still active extends from the
current expiry instead of resetting it.

---

## 3. Usage rules

```
consume_check(user)
  ├─ banned?              → denied ("banned")
  ├─ Pro/Business?        → allowed, unlimited
  ├─ under 3 in 24h?      → allowed, remaining = 3 - used - 1
  ├─ credits > 0?         → allowed, consumes 1 credit
  └─ otherwise            → denied ("limit_reached")
```

- The window is a **rolling 24h**, not a calendar day.
- Only `kind="check"` is metered. `alert` / `valuation` are logged but free.
- Credits are an append-only ledger: `balance = SUM(delta)`. Never negative.

---

## 4. Payment flow

```
User pays (Stars / Vodafone Cash / InstaPay)
        ↓
Payment(status=pending)
        ↓
Admin verifies proof  →  approve_payment(...)
        ↓
Subscription granted  +  partner_share = 25% of gross
        ↓
Partner monthly report (scripts/admin.py partners)
```

- Approval is **idempotent**: approving twice does not double-grant.
- Rejected payments cannot be approved later.
- `partner_code` defaults to the user's `referred_by` (first partner wins).

---

## 5. Operating it (admin CLI)

```powershell
# Who is this user?
python scripts/admin.py user 123456789

# Grant / renew Pro
python scripts/admin.py grant 123456789 pro_monthly --days 30 --price 299 --currency EGP

# Add credits
python scripts/admin.py credits 123456789 5 --reason manual

# Pending wallet payments
python scripts/admin.py payments --status pending

# Approve a Vodafone Cash payment (grants Pro for 30 days)
python scripts/admin.py approve 12 --plan pro_monthly --days 30 --by owner

# Approve a credit purchase (5 checks)
python scripts/admin.py approve 13 --credits 5 --by owner

# Reject with a reason
python scripts/admin.py reject 14 --reason "no proof" --by owner

# Monthly partner report
python scripts/admin.py partners --since 2026-11-01

# Housekeeping (run daily via scheduler later)
python scripts/admin.py expire
```

Verified end-to-end on a throwaway DB: referral → pending payment → approve →
`pro_monthly` active → partner share `74.75` on a `299` payment.

---

## 6. Daily lifecycle (runs inside the scheduler)

`ops/scheduler.py` calls `run_daily_if_due()` on every tick, but the job itself
runs **at most once per UTC calendar day** (state file: `logs/lifecycle_last_run.txt`,
git-ignored).

```
run_daily_maintenance()
  ├─ find active subs already past expiry   → send "انتهى اشتراكك" (before flipping)
  ├─ find subs expiring within 3 days       → send renewal reminder
  ├─ expire_stale_subscriptions()           → status = expired
  └─ send owner digest                      → users, checks, revenue, pending, active
```

- Notices go out **before** access is revoked, so nobody loses Pro silently.
- Banned users are never messaged.
- Prices in messages use the user's own currency (EGP / SAR / AED).
- With no `BOT_TOKEN`, sends are counted as `skipped` and the job still expires plans.
- Failures are counted (`failed`), never raised — one bad chat id cannot stop the job.

Telegram sending uses the **Bot API over HTTPS** (`services/notifier.py`), not a
second Telethon session, because the bot process already owns that session.

---

## 7. Bot surface (what a user sees)

| Command | Behaviour |
|---|---|
| `/start [partner_code]` | Creates/refreshes user, attaches partner once, shows plans |
| `/plans` | Prices in the user's currency |
| `/me` | Plan, expiry, checks used in 24h, credit balance |
| `/country eg\|sa\|ae` | Sets currency |
| `/pay <offer>` | Wallet instructions; next message becomes payment proof |
| any account text | **Gated**: 3 free checks / 24h, then credits, then upgrade prompt |
| photo/document after `/pay` | Forwarded to you + creates a pending payment |
| `/payments` (owner) | Pending payments with ✅ / ❌ buttons |
| `/review` (owner) | Low-confidence ads for labelling |

Owner approval in chat: tapping ✅ calls `approve_payment()`, which grants from
`offer_code` (plan + days, or credits) and records the 25% partner share. The
buyer gets an activation message immediately.

---

## 8. What is left before a stranger can pay

1. **Telegram Stars**: needs Bot API `createInvoiceLink` + `successful_payment`
   reconciliation. **Deliberately deferred** — Vodafone Cash / InstaPay cover
   the Egypt launch, and a half-working money path is worse than none.
2. **API auth**: map Telegram `initData` → `users.telegram_id` for the dashboard.
3. **Refresh proof**: run the bot once with real wallet numbers and approve a
   1 EGP test payment end-to-end.

---

## 9. Verification

```
pytest: 180 passed
ruff:   All checks passed
mypy:   Success: no issues found in 32 source files
```

Manual flow verified against `%TEMP%\opencode\admin_test.db` (throwaway).
Lifecycle verified with an injected transport (no network, no real chat ids).
