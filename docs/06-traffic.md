# Traffic & Growth

## Organic traffic engines

| Channel | Strategy | Agent | Volume potential |
|---|---|---|---|
| Twitter/X | 3x/week dev humor. 4:1 meme:product. Reply to big dev accounts. | Social + Community | Primary — SWE Twitter is the watering hole |
| Reddit | r/ProgrammerHumor (2M), r/cscareerquestions (800k), stack subreddits. Value first, always. | Social + Community | High — viral post = hundreds of orders |
| Fourthwall SEO | Every listing contributes to Google indexing. Listing Agent optimizes every product. | Listing Agent | Passive — compounds over months |
| Email newsletter | "The Agent Report" — weekly meta-transparency about the AI pipeline. Sent by Email Agent. | Email Agent | High conversion — owned channel |
| YouTube Shorts / TikTok | Video Agent generates 8s product clips. "AI designed this shirt in 3 seconds" content. | Video Agent + Social | Discovery — non-Twitter SWEs |
| SWE newsletter collabs | Cold outreach to TLDR Tech, Pragmatic Engineer, Quastor, Bytes.dev. Free shirts as barter. | Community Agent (finds targets) | Spiky — each collab = 100–500 visits |
| HN / dev blogs | Technical posts about agent architecture, not the product. Founder writes. | Manual | Authority — HN = early adopter credibility |

---

## Automated content calendar

All cron-based, agent-driven. Zero founder involvement after setup.

```
Monday    08:00  Trend Scout scans Reddit, HN, Twitter/X — top 3 briefs
Monday    10:00  CEO approves briefs, assigns to Copy Agent
Monday–Tue       Copy → Design → Listing pipeline runs
Tuesday   11:00  Social Agent: new design drop tweet + Buffer schedule
Tuesday          Video Agent: start generating product clip (async)
Wednesday 11:00  Social Agent: pure dev meme (no product link)
Thursday  11:00  Social Agent: engagement post (poll or question)
Thursday         Video Agent: post completed clip to Twitter + schedule for IG Reels
Friday    18:00  Analytics Agent: weekly_report.md + kill list + program.md update
Friday           CEO: reads report → fires kill list → flags scale list
Saturday  09:00  Email Agent: "The Agent Report" newsletter → sent to list
1st/month 09:00  Finance Agent: reconciliation + payout tracking → founder Telegram
```

---

## Content ratio rules

Enforced in Social Agent SOUL.md. Non-negotiable.

```
4:1   value posts to product posts
      (4 memes, culture, dev humor → 1 product link)

3:1   Twitter text vs image posts in month 1
      (build voice before pushing visuals)

1:0   Reddit links in post body
      (never — always in comment reply only)

1:5   Promotional language
      (1 post with direct CTA per 5 posts total)
```

---

## The organic flywheel

```
Trend Scout finds viral SWE frustration
  → Copy Agent packages it into a slogan (≤6 words)
    → Design Agent ships a shirt in <24h
      → Social Agent posts on Twitter + Reddit
        → SWEs share it in team chats / DMs
          → Traffic spike to Fourthwall
            → Orders convert
              → Analytics Agent surfaces winner
                → CEO writes to program.md:
                  "incident culture content converts 3x"
                  → Trend Scout scores this theme higher next week
                    → Better briefs → better designs → more shares

↺ Each cycle the brand gets smarter.
```

The `program.md` file is the flywheel's memory. Without it, the loop resets every week. With it, compound improvement is automatic.

---

## Newsletter collab targets

When MRR >$2k, Community Agent identifies and CEO drafts outreach to:

| Newsletter | Subscribers | Audience fit | Approach |
|---|---|---|---|
| TLDR Tech | ~500k | SWE, tech readers | Free shirts for the team + shoutout swap |
| The Pragmatic Engineer | ~350k | Senior SWEs specifically | Product drop collab — limited run |
| Quastor | ~100k | SWE, CS fundamentals | Sponsored issue ($200–500) |
| Bytes.dev | ~200k | JavaScript devs | Stack-specific JS edition collab |
| Console.dev | ~40k | Dev tools audience | Gift card giveaway in issue |
| TLDR AI | ~150k | AI engineers | Meta-angle: "AI-run brand makes shirts about AI engineers" |

**Outreach sequence:**
1. Community Agent finds contact/social for each newsletter author
2. CEO drafts cold DM/email: genuine fan note + one-line pitch + free shirt offer
3. No pitch decks. Short. Human. Specific.
4. If no reply in 7 days: one follow-up. Then move on.

---

## YouTube Shorts / TikTok strategy

**Content format (Video Agent):**

Type 1 — Design process (most popular):
```
"AI agent just made this shirt in 90 seconds"
[Screen: Paperclip task board assigning to Design Agent]
[Screen: FLUX generating the design live]
[End: Product on Fourthwall]
8 seconds. No voiceover. Terminal sounds.
```

Type 2 — Meme → product:
```
[Reddit screenshot: viral SWE complaint with 4k upvotes]
[Cut to: shirt with that exact phrase]
[Cut to: FW product page]
"The agents saw this. Made a shirt. It's live."
```

Type 3 — Kill list reveal (weekly):
```
"The AI killed 3 designs this week."
[Show: Analytics Agent report with 0-sales designs highlighted]
[Show: FW listing going inactive]
"No mercy."
```

**Platform notes:**
- TikTok: post natively, not via Buffer (algorithm penalizes Buffer posts)
- YouTube Shorts: upload via YouTube API (Video Agent can call this)
- Instagram Reels: post via Buffer (Facebook/IG API integration)

---

## SEO keyword strategy

Handled by Listing Agent on every product publish.

**Fourthwall product title formula:**
`[Stack/concept] + [product type] + [phrase] + [occasion or gifting keyword]`

**Tag strategy (Fourthwall allows multiple tags):**

Tier 1 — Broad (2–3 tags):
`programmer shirt`, `developer gift`, `software engineer shirt`

Tier 2 — Mid (3–4 tags):
`rust programmer shirt`, `python developer shirt`, `coding shirt`

Tier 3 — Long-tail (4–5 tags):
`funny shirt for software engineer`, `programmer birthday gift`, `git blame shirt`

Each listing should have 8–12 tags. Listing Agent enforces this.

**SEO compounds over time.** By month 3 with 30+ products live, expect 20–30% of Fourthwall traffic from direct Google search.

---

## Monthly growth targets

| Month | Revenue | Designs live | Email list | Twitter followers |
|---|---|---|---|---|
| 1 | $800 | 10–15 | 200 | 500 |
| 2 | $2,000 | 20–25 | 500 | 1,500 |
| 3 | $4,000 | 35–40 | 1,000 | 3,000 |
| 6 | $10,000 | 60–80 | 3,000 | 8,000 |
| 12 | $25,000 | 100+ | 8,000 | 20,000 |

These are organic-only projections (no paid ads). Assumes agents run reliably and newsletter collabs begin at month 2.
