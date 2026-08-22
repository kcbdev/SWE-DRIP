# SWE Drip

> The only clothing brand that makes software engineers feel seen — not patronized.

An autonomous AI-run print-on-demand clothing brand targeting software engineers in the US, UK, and EU. Founded and operated from Morocco. The entire company runs on an agent stack — a CEO agent orchestrates ten specialized workers covering trend research, copy, design, listing, social, video, analytics, email, community, and finance. The founder's only touchpoints are a weekly Telegram digest and high-stakes escalations.

---

## Architecture

```
                    CEO Agent (Paperclip)
                           │
        ┌──────────────────┼──────────────────┐
        │           Hermes Workers             │
        │                                      │
  Trend Scout    Copy Agent    Design Agent    │
  Listing Agent  Social Agent  Video Agent     │
  Analytics      Email Agent   Community       │
  Finance Agent                                │
        │                                      │
        └──────────────────┼───────────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
       Fourthwall MCP            External Tools
  Products · Orders · Analytics   Reddit · HN
  Promotions · Designs · Payouts  Midjourney/FLUX
  Brand tools · OAuth 2.0         Buffer · Twitter
```

---

## Stack

| Layer | Tool | Role |
|---|---|---|
| VPS | Hetzner CX31 (€8/mo) | Single server for all services |
| PaaS | **Coolify** (self-hosted) | Deployment UI, SSL, env vars, volumes, restarts |
| Orchestration | Paperclip (deployed via Coolify) | CEO agent, task board, budget caps, audit log |
| Models | OpenRouter | Single key for LLM + image + video |
| Storefront | Fourthwall (Brutal theme) | POD, payments (MOR), MCP integration |
| Email | Loops.so | Weekly newsletter + transactional |
| Scheduling | Buffer | Social post scheduling |
| Notifications | Telegram bot | Founder escalation alerts |

---

## Monthly costs

| Item | Cost |
|---|---|
| Hetzner CX31 VPS | €8/mo |
| OpenRouter — LLM | $40–70/mo |
| OpenRouter — Images (FLUX.2 Pro) | $15–30/mo |
| OpenRouter — Video (Veo 3.1 Lite) | $10–20/mo |
| Loops.so | Free → $9/mo |
| Fourthwall | $0 platform fee |
| Buffer | $0 (free tier) |
| Coolify | $0 (self-hosted, open-source) |
| **Total** | **~$75–130/mo** |
| **Break-even** | **4–5 shirt sales** |

---

## Directory

```
swe-drip/
├── README.md
├── docs/
│   ├── 01-brand.md          Brand identity, design rules, proven slogans
│   ├── 02-stack.md          Infrastructure, Coolify setup, OpenRouter config, FW MCP
│   ├── 03-agents.md         10 agents: models, tools, costs, SOUL.md templates
│   ├── 04-deploy.md         Day-by-day deployment guide (Coolify-first)
│   ├── 05-launch.md         Pre-launch checklist + launch week playbook
│   ├── 06-traffic.md        Organic channels, content calendar, flywheel
│   └── 07-scale.md          Revenue milestones, unlock sequence
├── agents/
│   ├── ceo/
│   │   ├── SKILL.md         CEO agent runtime skill
│   │   └── references/      agent-team.md, brand-context.md, payments.md, program-md-template.md
│   └── souls/               Individual SOUL.md files per agent
├── workspace/               Shared agent I/O (design_briefs.json, listing_copy.json, reports)
└── program.md               Institutional knowledge base (auto-updated by Analytics Agent)
```

---

## Quick start

```bash
# 1. Provision Hetzner VPS (CX31, Ubuntu 24.04)
hetzner-cli server create --name swe-drip --type cx31 --image ubuntu-24.04

# 2. Install Coolify (one-line, 2–5 min)
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash

# 3. Open Coolify UI at http://[IP]:8000
#    → Create admin account
#    → Add server (localhost)
#    → Deploy Paperclip as Docker image (paperclipai/paperclip:latest)
#    → Set environment variables in Coolify UI
#    → Configure persistent volumes for /app/data and /workspace

# 4. Connect Fourthwall MCP
#    Fourthwall Dashboard → Settings → Developer → MCP → copy OAuth token
#    → Paste into Paperclip settings (or as env var FOURTHWALL_MCP_TOKEN)

# 5. Follow docs/04-deploy.md for full agent deployment (Days 2–7)
```

Full deployment guide: [docs/04-deploy.md](docs/04-deploy.md)
