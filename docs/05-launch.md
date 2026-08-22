# Launch Strategy

## Pre-launch checklist

### Store
- [ ] Fourthwall Brutal theme applied
- [ ] Custom CSS: `#0D0D0D` background, `#00FF41` accent, JetBrains Mono
- [ ] Brand logo uploaded (mono wordmark)
- [ ] PayPal payout configured (Dashboard → Payouts → verify Morocco/PayPal works)
- [ ] Email capture enabled: "Coming soon — get first access"
- [ ] Shipping rates configured for US / UK / EU
- [ ] Return policy set (Fourthwall default is fine)

### Content
- [ ] 10 validated designs live on FW store (Trend Scout validated each before design)
- [ ] 3 product showcase videos created (Video Agent)
- [ ] 20 dev humor tweets pre-scheduled in Buffer (Social Agent — no product links)
- [ ] Product Hunt listing drafted: title + tagline + description + screenshots
- [ ] Show HN post drafted (technical angle — the agent architecture)
- [ ] Launch email drafted in Loops.so (held, not sent)

### Distribution
- [ ] Twitter @swedrip account created, bio filled, pinned tweet ready
- [ ] Reddit karma: at least 5 value posts on r/ProgrammerHumor before launch
- [ ] Buffer connected to @swedrip Twitter account
- [ ] Loops.so email template tested (send to yourself first)

### Ops
- [ ] All 10 agents running and tested end-to-end
- [ ] Telegram founder notifications confirmed working
- [ ] Analytics Agent: test weekly report generation
- [ ] Finance Agent: test payout data retrieval from FW MCP

---

## Launch week — day by day

### Monday — Soft launch

**Morning (agents handle):**
- Email Agent sends launch email to waitlist: "SWE Drip is live"
- Social Agent posts Twitter launch thread (10 tweets, prepared by Copy Agent)

**Launch thread structure:**
```
Tweet 1: "We built a clothing brand run entirely by AI agents. It launched itself this morning."
Tweet 2: "There's a Trend Scout that reads r/ProgrammerHumor every Monday."
Tweet 3: "A Copy Agent that writes slogans. A Design Agent that generates the PNG."
Tweet 4: "A Listing Agent that publishes to the store. A Social Agent posting this right now."
Tweet 5–8: Show 3 best designs with product images
Tweet 9: "The whole stack: Paperclip + OpenRouter (FLUX.2 Pro for designs, Veo for videos) + Fourthwall"
Tweet 10: Link to store + "First 50 orders get a sticker pack free"
```

**Evening:** CEO reviews engagement → if thread >200 likes, deploy 20% launch discount promotion via FW MCP.

---

### Tuesday — Product Hunt

Submit at 12:01am PST (PH resets at midnight).

**Listing:**
```
Name: SWE Drip
Tagline: A clothing brand run entirely by AI agents. No humans involved.
Description:
  SWE Drip makes shirts, hoodies, and mugs for software engineers — and it runs itself.

  8 AI agents handle everything: trend research, slogan writing, design generation,
  Fourthwall listing, social posting, analytics, email, and finance. The founder
  gets a Telegram message once a week with the numbers.

  The tech: Paperclip (self-hosted) orchestrates agents. OpenRouter routes to
  Claude Sonnet (writing), FLUX.2 Pro (design), and Veo 3.1 Lite (product videos).
  Fourthwall handles the storefront, POD fulfillment, and payments.

  Every design is validated on Reddit before FLUX touches it.
```

**Screenshots:** FW store homepage, Paperclip agent board (shows 10 agents), a design being generated, weekly analytics report.

**Ask:** Post in relevant communities for PH support. Dev Twitter networks. Former colleagues.

---

### Wednesday — Hacker News

Post as Show HN.

```
Show HN: I built a clothing brand that runs itself with Paperclip + Fourthwall

Long version:

SWE Drip is a print-on-demand brand for software engineers. The unusual part:
it's fully autonomous. A CEO agent (Paperclip) orchestrates 10 specialized
agents. The founder gets one Telegram message per week.

The pipeline:
- Trend Scout: reads r/ProgrammerHumor, HN, Twitter every Monday. Scores
  potential designs by engagement × novelty × SWE specificity.
- Copy Agent: generates slogans ≤6 words. Validates against competitor catalog.
- Design Agent: calls FLUX.2 Pro via OpenRouter → 2048×2048 PNG →
  Fourthwall MCP ecommerce_create-offers-from-designs → product is live.
- Social Agent: posts Tuesday/Wednesday/Thursday. 4:1 value:promo ratio.
- Analytics Agent: Friday kill list and scale recommendations.

Total monthly AI cost: ~$100. Break-even: 5 shirt sales.

Interesting problems: agent drift (program.md gets stale), FLUX prompt
engineering for print-safe output, Veo 3.1 async video pipeline.

Store: [url] | Code details happy to share in comments.
```

HN loves meta-stories about systems. The architecture angle gets upvotes. Don't lead with the product — lead with the technical design.

---

### Thursday — Reddit

**r/ProgrammerHumor** — post the best meme design as an image post. No link. Caption is just the slogan. Let it breathe. If it gets >200 upvotes, the Social Agent replies: "I made a shirt of this lol: [link]"

**r/cscareerquestions** — post as text:
```
"Made shirts about things that actually happen at work. Currently surviving on caffeine and git blame."
[Image of top 3 designs]
```
No link in the post. Link in comments if engagement is strong.

---

### Friday–Sunday — Momentum

- Social Agent: one new design reveal per day
- Video Agent: first showcase clip goes live on Twitter + Instagram
- Analytics Agent: first real report (even if low data — establishes baseline)
- CEO: reads engagement data, adjusts next week's Trend Scout brief weighting

**Launch week targets:**
| Metric | Target |
|---|---|
| Email list growth | +200 subscribers |
| Twitter followers | +500 |
| First sale | Day 1 |
| Week 1 revenue | $300+ |
| PH ranking | Top 10 in Dev Tools |
| HN points | >50 |

---

## Channel-specific tactics

### Twitter/X

- Best posting window: Tue–Thu 9am–12pm ET (SWE audience peak)
- Thread format outperforms single tweets 3x for new accounts
- Never use hashtags — SWE Twitter culture hates them
- Reply to dev influencer threads (Primeagen, Theo, DHH) when genuinely relevant — never forced

### Reddit

**Karma-first strategy.** Before launch:
- Post 5 pure meme/humor posts (no products) on r/ProgrammerHumor
- Get to 500 karma on the account
- Never link to the store in the post body — always in comments
- Respect subreddit rules (r/ProgrammerHumor is strict on self-promo)

**Post timing:** Reddit SWE traffic peaks Mon–Thu, 10am–2pm ET.

### Fourthwall SEO (passive channel)

Every product Listing Agent publishes contributes to SEO.
FW has decent Google indexing. Each listing should have:
- Title with 2+ keywords (see `docs/01-brand.md` SEO keywords)
- 150–200 word description with natural keyword inclusion
- Proper tags

This builds passively. By month 3, expect 20–30% of traffic from organic search.

### Email — "The Agent Report"

Weekly newsletter. Sent by Email Agent every Saturday 9am.

Formula: meta-transparency about the AI process + this week's designs + one killed design + what's next. SWE readers are curious about the agent architecture — that curiosity is the open-rate driver.

Target open rate: >35% (SWE audiences are engaged when content is authentic)

---

## Launch don'ts

- Don't post the store link on Reddit before having karma
- Don't run paid ads in week 1 — organic signal first to validate designs
- Don't discount on day 1 without at least 24h of organic pricing data
- Don't promise delivery times you don't control (Fourthwall / POD handles fulfillment)
- Don't respond to negative comments defensively — Community Agent replies dry and moves on
