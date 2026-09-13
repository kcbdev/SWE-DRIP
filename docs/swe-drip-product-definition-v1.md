# SWE Drip — Product Definition Document v1.0

*Companion to the Product Vision Document (v1.0, architecture/decisions). This document defines the product itself — what it is, who it's for, what it does at launch, and how success is measured. The Vision doc answers "how does the system work"; this answers "what are we actually selling, to whom, and why would they buy it."*

---

## 1. One-line definition

SWE Drip is an apparel brand for software engineers, run by an autonomous AI pipeline that researches, designs, produces (via print-on-demand), publishes, and markets terminal/dev-culture merchandise with minimal founder intervention.

## 2. Problem statement

Developer-identity merchandise today is either generic ("I ♥ coding" mugs, low cultural specificity) or produced by small creators who can't sustain a fast-enough design cadence to track a culture that moves in months, not years (2026's shift from "coding" to "agentic/vibe coding" identity jokes is a concrete example — a slow-moving brand misses that window entirely). SWE Drip's bet is that an AI-run design/publish pipeline can match the speed of the culture it's selling identity around, at a cost structure ($130/mo cap) no small human-run shop can match.

## 3. Target customer

**Primary persona:** individual contributor or senior software engineer, active in dev-culture spaces (X/Twitter tech, Reddit programming subs, Hacker News), self-aware about the AI-coding-tools shift, buys identity/humor merch as a low-friction way to signal in-group belonging (at a desk, at a meetup, on a video call background).

**Secondary persona:** engineering teams/managers buying a small batch for a team or event (lower priority for v1, but a `product_count_target` per collection and defined pricing invariants make this feasible later without a scope change).

**Not the target:** general "geek culture" or broad tech-adjacent buyers — the brand's specificity (terminal green, JetBrains Mono, log-format jokes) is the point, not a limitation to soften.

## 4. Value proposition

- **Cultural currency:** designs reference what's actually happening in dev culture right now (agentic coding, orchestrator patterns, "the AI wrote code neither of us understands"), not evergreen generic programmer jokes.
- **Consistent brand world:** every product belongs to a locked collection aesthetic (style, palette, placement) rather than being a one-off print — buyers can recognize "a SWE Drip shirt" across the catalog.
- **Fast rotation:** monthly collection cycles mean the catalog doesn't go stale, and underperforming lines get replaced rather than lingering.

## 5. Product scope at launch

### 5.1 Collections (locked sequencing from prior strategy work)
1. **Terminal Collection** — proven, live, control group. Terminal-log style, black/charcoal only (contrast-locked).
2. **Vibe Coding** — next to launch, timed to the current cultural peak of AI-generated-code identity humor.
3. **Agent Orchestrator** — premium/niche, targets senior engineers running multi-agent workflows.
4. **Stack-Specific** — evergreen long-tail, per-language/framework identity tees, launched last (already has a nav slot on the storefront).

### 5.2 Product categories (per Fourthwall's catalog structure)
Apparel is the launch focus (tees proven live). Accessories, Drinkware, and Home & Living are explicitly **phase 2** — not because they're deprioritized philosophically, but because the placement/colorway/QC system needs to prove itself on the simplest garment shape (a flat rectangular print area) before extending to categories with tighter or curved imprint zones (mugs, tote bags) — extending too early risks compounding an unsolved design-quality problem across more surface types.

### 5.3 Price invariants (unchanged, already enforced)
Tee: $32 · Hoodie: $62 · Mug: $20 — enforced as a hard check at the Shelf pipeline step, not a per-product judgment call.

## 6. Functional scope (customer-facing)

- Browse by collection (`Terminal Collection`, `Stack-Specific`, future collections added as nav grows)
- Standard Fourthwall storefront commerce: cart, checkout, sizing, USD currency selector (already live in the header)
- No account/login requirement beyond what Fourthwall's checkout requires
- No customer-facing customization (no build-your-own-shirt) — the brand's value is curation and cultural specificity, not configurability

## 7. Functional scope (internal / pipeline-facing — cross-reference to Vision doc §3.2)

The product is inseparable from the pipeline that makes it: research → collection contract → design → QC gate → publish → price → market → measure → rotate. This document doesn't re-specify the pipeline (see Vision doc); it defines the **outputs** the pipeline is accountable for:

- A design that passes the aesthetic QC rubric (style-cohesion, focal point, placement-fit, contrast) before it can reach a customer
- A product listing with brand-voice copy (slogan ≤6 words, dry/terminal-culture tone, no hashtags) — already a locked Copy Agent contract
- A price that matches the invariant table exactly, no exceptions
- A collection assignment that matches a currently-active, non-retired collection contract

## 8. Non-functional requirements

| Requirement | Value | Source |
|---|---|---|
| Monthly AI spend cap | $130 | Existing SOUL budget allocation ($124 currently assigned) |
| Break-even | 4-5 shirt sales/month | Existing cost model |
| Brand visual lock | #0D0D0D void black, #00FF41 terminal green, JetBrains Mono; no gradients, shadows, rounded pills, or pastels | Storefront CSS skill, already enforced |
| Payout | Fourthwall as merchant of record (2.9% + $0.30), payout via PayPal to Morocco | Confirmed |
| Storefront availability | Must move off `COMING_SOON` before any marketing push is meaningful — this is a launch blocker, not a background task | Current live-state finding |

## 9. Success metrics

**Leading (design/pipeline health):**
- Aesthetic-QC first-attempt pass rate (fewer regenerations = better-calibrated contracts)
- Time from collection-contract approval to first live product in that collection

**Lagging (commercial):**
- Units and conversion per collection, measured against that collection's own `kpi_thresholds`
- Overall monthly revenue vs. break-even (4-5 units)
- Return/complaint rate per collection, cross-checked against QC scores to validate whether the rubric actually predicts customer satisfaction

**Cultural (qualitative, tracked not gated):**
- Organic mentions/shares in dev-culture spaces (X, Reddit, HN) — the Community Agent's monitored-keyword log is the raw signal source, no formal target set yet at v1

## 10. Constraints and assumptions

- Design generation quality is bounded by current image-model capability (riverflow-v2-pro / gpt-5-image-mini / seedream) — the QC gate catches failures, it doesn't fix an underlying model limitation
- Fourthwall's DTG print method assumed for all launch products (no screen-print spot-color constraint to design around)
- Single-founder operation — HITL gates (§ Vision doc) exist specifically because there is no design/ops team to distribute review load across; this shapes how aggressively automation can be trusted, not just what's technically possible

## 11. Explicit out-of-scope (v1)

- Multi-creator or platform ambitions (Fourthwall Channel API)
- Non-apparel product categories (Accessories/Drinkware/Home & Living) — phase 2
- Customer-facing design customization
- International currency/localization beyond Fourthwall's built-in USD selector
- Paid advertising — launch relies on Product Hunt / Show HN / Reddit / Twitter thread, organic only at v1

## 12. Glossary

- **Collection contract:** the locked YAML spec (style, palette, colorways, placement templates, KPI thresholds) that governs every design generated under a given collection
- **HITL gate:** a pipeline step where execution pauses for founder review before continuing
- **Aesthetic QC:** the rubric-scored check for style-cohesion, focal point, placement-fit, and contrast — distinct from technical QC (file validity)
- **Price invariant:** a fixed price per product category, enforced mechanically, never a per-product decision

---

*This document defines the product. See the Product Vision Document v1.0 for the system architecture that delivers it, and prior collection-strategy discussion for the launch sequencing rationale behind §5.1.*
