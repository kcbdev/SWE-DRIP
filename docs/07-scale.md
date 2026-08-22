# Scale Playbook

## Revenue milestones & unlock sequence

| MRR | Milestone | What to unlock | How |
|---|---|---|---|
| $500 | Break-even | All 10 agents running | Validates autonomous loop. 15–20 designs live. |
| $1k | Month 1 | Email newsletter launched | "The Agent Report" driving 30%+ of repeat orders. 200+ subscribers. |
| $2k | Month 2 | First newsletter collab | Community Agent identifies target. CEO drafts outreach. Free shirts as barter. |
| $3k | Month 2–3 | Stack-specific limited drops | "Rust Edition" drop. 48h window. Creates urgency. Trend Scout monitors stack subreddits for timing. |
| $5k | Month 3 | Paid amplification | Reddit ads on r/cscareerquestions ($300/mo). Twitter promoted posts ($200/mo). CAC target <$12. |
| $8k | Month 4–5 | Influencer collab drop | DM Primeagen, ThePrimeTime, Theo.gg — rev share on a custom design. 1 collab typically = 500–2k orders. |
| $12k | Month 6 | Discord community | Invite top buyers. Community votes on next designs. Agents read Discord for brief ideas. |
| $20k | Month 8 | Physical retail experiment | Pop-up at React Summit, RustConf, or similar. Test physical presence ROI vs online. |

---

## The scale arithmetic

**Unit economics at scale ($10k MRR):**
```
Average order value:      $38  (mix of shirts, hoodies, mugs)
Average margin:           50%
Gross profit per order:   $19
Orders needed for $10k:   526/month (~18/day)

Traffic needed:
  Fourthwall conv rate:   2.5% (industry avg 1.4%, target >2%)
  Visitors needed:        526 / 0.025 = ~21,000/month

Traffic breakdown at $10k MRR:
  Organic search (SEO):   ~6,000 (28%) — compounds with catalog size
  Twitter/X:              ~5,000 (24%) — agent-driven
  Email click-through:    ~3,000 (14%) — newsletter + list
  Reddit:                 ~3,000 (14%) — Social + Community agents
  Newsletter collabs:     ~2,000 (10%) — periodic spikes
  TikTok/Shorts:          ~2,000 (10%) — Video Agent
```

---

## Paid amplification (unlock at $5k MRR)

Only add paid ads after organic signals are clear. Ads amplify what's already working — they don't discover what works.

**Budget allocation at $5k MRR:**
```
Reddit ads (r/cscareerquestions):    $300/mo
Twitter promoted posts:              $200/mo
Total:                               $500/mo (10% of MRR)
```

**Reddit ads:**
- Subreddits: r/cscareerquestions, r/programming, r/learnprogramming
- Format: image ads only (no text ads — SWEs ignore them)
- CTA: "software engineers will understand" — curiosity-driven
- CAC target: <$12

**Twitter ads:**
- Promote top organic tweets only (already >100 likes before boosting)
- Targeting: followers of Primeagen, Theo, DHH, tpope
- Budget per promoted tweet: $30–50

**CEO automates ad management:**
- Analytics Agent identifies top-performing organic tweets weekly
- CEO creates promotion via Twitter API when organic tweet exceeds 100 likes
- Finance Agent tracks ad spend vs revenue lift
- Auto-pause any ad with CAC >$15

---

## Influencer collab playbook

**Target profile:**
- SWE content creator, 100k+ followers
- Authentic dev culture, not corporate
- Examples: ThePrimeagen (600k YT), Theo (~500k YT), tpope, DHH, Ben Awad

**Outreach template (CEO writes, founder sends manually):**
```
Hey [name],

I built a clothing brand run by AI agents. Trend Scout watches your streams
for phrases that would make good shirts. (It found three from you last month.)

Want to do a collab drop? I design a shirt based on something you're known for,
you mention it once, we split revenue 50/50 on the collab SKU. No contract.

Happy to send you samples first.

[link to store]
```

**Collab mechanics:**
1. Listing Agent creates a separate collection: "ThePrimeagen Collection"
2. Custom SKU tracked separately in FW
3. Finance Agent reports collab revenue split monthly
4. CEO handles payout to influencer via PayPal from FW proceeds

---

## The agent drift problem (and solution)

At scale, the biggest operational risk is **agent drift**: `program.md` grows stale or contradictory, CEO loses context on early learnings, and agents start repeating patterns that were killed months ago.

**Symptoms:**
- Designs that were killed 6 months ago reappear as new briefs
- Copy Agent produces copy that violates old brand rules (forgotten)
- Analytics Agent stop flagging patterns because `program.md` is too long to parse

**Solution — monthly program.md maintenance (Email Agent):**

On the 1st of each month, Email Agent runs a secondary task:

```markdown
Task: Summarize program.md into a condensed version.
Rules:
- Keep all "Winning patterns" — these are active
- Merge duplicate patterns into single consolidated lines
- Move patterns older than 90 days with no reinforcement to ## Archive section
- Keep all kill rules — these are hard constraints
- Trim Agent performance log to last 3 months only
- Output: /workspace/program-summary.md (CEO reads this first, not full program.md)
Output max: 500 lines
```

CEO switches to reading `program-summary.md` as its primary context after month 3.

---

## Discord community (unlock at $12k MRR)

**Purpose:** Community votes on next designs. Agents read Discord for brief ideas. Top buyers get early access.

**Structure:**
```
#announcements      — Email Agent cross-posts newsletter here
#new-designs        — Listing Agent posts when a product goes live
#vote-next          — Community Agent posts 3 brief options, community votes
#agent-logs         — Weekly CEO report dumped here for transparency
#general            — Dev chat, no moderation needed (SWEs self-moderate)
```

**Community Agent + Discord:**
Add Discord bot capability to Community Agent. It reads `#vote-next` results weekly and writes the winner to `design_briefs.json` with score=100 (auto-approved by CEO).

---

## Product expansion sequence

Don't expand too early. Each category should be validated before adding.

| Phase | Products | Unlock condition |
|---|---|---|
| Launch | T-shirt, mug, sticker pack | Day 1 |
| Month 2 | Hoodie | Top t-shirt design hits 20+ sales |
| Month 3 | Tote bag, hat | $3k MRR sustained 2 months |
| Month 4 | Desk mat, poster | Community Discord request |
| Month 6 | Limited run / signed prints | Influencer collab proven |

---

## Long-term moat

The CEO skill file (`agents/ceo/SKILL.md`) + `program.md` combination is the actual asset. Not the designs, not the Fourthwall store. Both can be recreated. But a `program.md` file with 12 months of learnings — which themes convert, which copy patterns kill, which agents underperform at what tasks — is something no competitor can replicate.

Guard it accordingly:
- Daily backup of `/workspace/program.md` to S3 or Hetzner Object Storage
- Weekly export of FW analytics data to `/workspace/reports/archive/`
- Monthly snapshot of full Paperclip agent config (`docker compose exec paperclip paperclip export`)
