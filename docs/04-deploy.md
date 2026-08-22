# Deployment Guide

Seven days to full autonomy. Follow in order — each day depends on the previous.

---

## Day 1 — Infrastructure (Hetzner + Coolify)

### 1.1 Provision VPS

```bash
hetzner-cli server create \
  --name swe-drip \
  --type cx31 \
  --image ubuntu-24.04 \
  --location nbg1 \
  --ssh-key ~/.ssh/id_ed25519.pub
```

Connect and harden:
```bash
ssh root@[IP]
apt update && apt upgrade -y
ufw allow 22 && ufw allow 8000 && ufw allow 80 && ufw allow 443
ufw enable
```

### 1.2 Install Coolify

One command. Takes 2–5 minutes. Installs Docker and starts all Coolify containers:

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

When it finishes, Coolify is running at `http://[IP]:8000`.

### 1.3 Coolify initial setup

Open `http://[IP]:8000` in your browser.

1. **Create admin account** — your email + password. This is the only Coolify account needed.
2. **Add server** → Servers → Add Server → select **Localhost** → Save.
   Coolify connects to the local Docker daemon via socket. Verify the connection shows green.
3. **Create project** → Projects → New Project → name it `swe-drip`.

### 1.4 Deploy Paperclip via Coolify

Inside the `swe-drip` project:

```
New Resource → Application → Based on existing Docker Image
```

Fill in:
```
Image:             paperclipai/paperclip:latest
Port:              3000
Name:              paperclip
```

**Do not click Deploy yet** — set env vars and volumes first.

### 1.5 Set environment variables

In the Paperclip application → **Environment Variables** tab.
Add each variable. Mark sensitive ones as **Secret** (eye icon — masked in UI and logs):

| Variable | Value | Secret |
|---|---|---|
| `OPENAI_API_KEY` | `sk-or-v1-xxxx` (your OpenRouter key) | ✅ |
| `OPENAI_BASE_URL` | `https://openrouter.ai/api/v1` | |
| `DEFAULT_MODEL` | `anthropic/claude-sonnet-4-6` | |
| `WORKSPACE_PATH` | `/workspace` | |
| `OPENROUTER_API_KEY` | same as `OPENAI_API_KEY` | ✅ |
| `TELEGRAM_BOT_TOKEN` | `xxxx:xxxx` | ✅ |
| `TELEGRAM_CHAT_ID` | `xxxxxxxxxx` | ✅ |
| `FOURTHWALL_MCP_TOKEN` | `fw-oauth-xxxx` | ✅ |
| `LOOPS_API_KEY` | `xxxx` | ✅ |
| `BUFFER_ACCESS_TOKEN` | `xxxx` | ✅ |

> All of these are **Runtime variables** (default). Do not enable "Build Variable" — they don't need to be baked into the image.

### 1.6 Configure persistent volumes

In the Paperclip application → **Storages** tab → Add Storage for each:

| Container path | Volume name | What it stores |
|---|---|---|
| `/app/data` | `paperclip-data` | Paperclip state, agent configs, org chart |
| `/workspace` | `paperclip-workspace` | Shared I/O: briefs, copy, reports, designs |

Both are named Docker volumes. Data persists across every redeploy.

### 1.7 Health check

In the Paperclip application → **Health Checks** tab:
```
Path:            /health
Port:            3000
Interval:        30s
Timeout:         5s
Retries:         3
Start period:    15s
```

Enable **Auto-restart on failure**.

### 1.8 Deploy

Click **Deploy**. Watch the build log stream in the Coolify UI.
First deploy pulls the image (~60s). On success, status shows **Running** in green.

Verify: `curl http://[IP]:3000/health` → `{"status":"ok"}`

### 1.9 Optional: domain + SSL

If you have a domain, point `paperclip.swedrip.com` (or similar) to your VPS IP.
In Coolify application → **Domains** tab:
```
Domain: https://paperclip.swedrip.com
```

Coolify auto-provisions a Let's Encrypt certificate and configures Traefik routing.
Certificate renews automatically. Port 3000 no longer needs to be public-facing.

### 1.10 External accounts (do in parallel)

- [ ] OpenRouter — fund with $50, copy API key → Coolify env vars
- [ ] Fourthwall → Dashboard → Settings → Developer → MCP → copy OAuth token → Coolify env var
- [ ] Telegram — create bot via @BotFather → token + chat ID → Coolify env vars
- [ ] Buffer — connect @swedrip Twitter account → copy access token → Coolify env var
- [ ] Loops.so — create workspace → copy API key → Coolify env var
- [ ] Twitter/X developer — apply for API write access (needed for Social Agent posting)

### 1.11 Initialise workspace files

SSH into the VPS and seed the shared workspace volume:

```bash
# Find the volume mount path
docker volume inspect paperclip-workspace

# Seed empty JSON files so agents don't fail on first read
docker exec $(docker ps -qf name=paperclip) sh -c '
  echo "[]" > /workspace/design_briefs.json
  echo "[]" > /workspace/listing_copy.json
  mkdir -p /workspace/designs /workspace/reports
'
```

---

## Day 2 — CEO + Trend Scout

### 2.1 Open Paperclip UI

Access at `http://[IP]:3000` (or your domain if configured).

### 2.2 Create CEO agent

`Company → Hire Agent` → paste SOUL.md:

```markdown
# CEO — SWE Drip

## Role
CEO of SWE Drip. Autonomous AI-run POD clothing brand for software engineers.
Operate via Paperclip task board. Read program.md before every decision cycle.

## Model
anthropic/claude-sonnet-4-6

## Mission
Ship 2 designs/week. Kill anything with 0 sales in 30 days.
Keep OpenRouter spend under $130/month total across all agents.
Escalate to founder only for: spend >$50 single decision, platform bans, payout issues.

## Decision rules
- Approve Trend Scout brief if score ≥ 60
- Kill design: 0 sales after 30 days → archive via FW MCP
- Scale design: 5+ sales in 14 days → expand to hoodie + mug variant
- Flash sale: weekly revenue drops >30% → 20% off top 3 products via FW MCP

## Files
- /workspace/program.md          (read first — institutional knowledge)
- /workspace/design_briefs.json
- /workspace/listing_copy.json
- /workspace/weekly_report.md
```

Set budget cap: **$30/month**.

### 2.3 Hire Trend Scout

- Model: `google/gemini-2.0-flash-001`
- Cron: `0 8 * * MON` (Mon 8am UTC+1)
- Budget: $6/mo
- Tools: `web_search`, `file_write`

**Test:** Manually assign task from CEO:
```
Scan r/ProgrammerHumor, r/cscareerquestions, and Twitter/X for viral SWE content.
Score each brief: engagement × novelty × SWE specificity. Return top 3 scoring >60.
Write to /workspace/design_briefs.json.
```

Verify `/workspace/design_briefs.json` is populated. If empty, check tool permissions.

> **Redeploy after agent changes:** Any change to Paperclip's agent config is saved inside
> the `/app/data` volume. No Coolify redeploy needed — just save in the Paperclip UI.
> Coolify redeploy is only needed when updating the Docker image version.

---

## Day 3 — Design pipeline (critical path)

This is the most important day. Everything downstream depends on this working.

### 3.1 Hire Copy Agent

- Model: `anthropic/claude-sonnet-4-6`
- Trigger: `on_task`
- Budget: $15/mo
- Tools: `file_read`, `file_write`, `web_search`

### 3.2 Hire Design Agent

- Model: `google/gemini-2.0-flash-001` (orchestrator — calls OR image API as a tool)
- Trigger: `on_task`
- Budget: $30/mo (covers image generation cost)

Add custom image generation tool:

```python
# Tool: generate_apparel_design
# Description: Generate print-ready PNG via FLUX.2 Pro on OpenRouter

import httpx, base64, os

def generate_apparel_design(slogan: str, model: str = "black-forest-labs/flux.2-pro") -> str:
    """Returns base64 PNG string."""
    r = httpx.post(
        "https://openrouter.ai/api/v1/images",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
        json={
            "model": model,
            "prompt": (
                f'Minimalist apparel design. JetBrains Mono Bold typography. '
                f'Text: "{slogan}". Terminal green #00FF41 on void black #0D0D0D. '
                f'Centered, isolated. No decorations. Print-safe flat design.'
            ),
            "image_config": {"width": 2048, "height": 2048}
        },
        timeout=120
    )
    return r.json()["data"][0]["b64_json"]
```

Add Fourthwall MCP as tool source:
`Settings → MCP Servers → Add → https://mcp.fourthwall.com → paste FOURTHWALL_MCP_TOKEN`

### 3.3 Hire Listing Agent

- Model: `google/gemini-2.0-flash-001`
- Trigger: `on_task`
- Budget: $5/mo
- Tools: FW MCP (`ecommerce_update-offer`, `ecommerce_list-collections`), `file_read`

### 3.4 Test full pipeline — Day 3 goal

CEO task:
```
Take the top brief from /workspace/design_briefs.json.
Run the full pipeline:
1. Copy Agent → generate slogan + listing copy → write to listing_copy.json
2. Design Agent → FLUX.2 Pro → PNG → FW MCP ecommerce_generate-product-design-previews
3. Design Agent → FW MCP ecommerce_create-offers-from-designs → product published
4. Listing Agent → verify price=$32, tags, collection correct on Fourthwall
5. Report: product name + Fourthwall URL
```

**Success:** A product appears in your Fourthwall store with correct price, description, and tags.
If FLUX.2 Pro output is unreadable (wrong font rendering), use the text-safe fallback prompt:

```python
# Fallback prompt — forces pure typographic output
fallback_prompt = (
    f'Large bold white monospace text "{slogan}" centred on solid black background. '
    f'No graphics. No decorations. Clean, readable, high-contrast. '
    f'Simple typographic design. Screen-printing ready.'
)
# Use model: "google/gemini-3.1-flash-image" as fallback
```

---

## Day 4 — Social + Video agents

### 4.1 Hire Social Agent

- Model: `anthropic/claude-haiku-4-5`
- Cron: `0 11 * * TUE,WED,THU` (11am ET)
- Budget: $4/mo
- Tools: `buffer_api`, FW MCP (`ecommerce_list-offers`), `file_read`

SOUL.md snippet:
```markdown
Post 3x/week. Tuesday: new design drop. Wednesday: dev meme only. Thursday: engagement.
Twitter: plain text first. Product link in reply thread only if >50 likes in 24h.
Reddit: value post only. Link in comment reply if >100 upvotes. Never in post body.
4:1 value:promo ratio enforced.
```

### 4.2 Hire Video Agent

- Orchestrator model: `anthropic/claude-haiku-4-5`
- Cron: `0 10 * * MON,THU`
- Budget: $20/mo

Add custom video generation tool:

```python
# Tool: generate_product_video
# Description: Generate 8s product clip via Veo 3.1 Lite (async)

import httpx, time, os

def generate_product_video(product_image_url: str, slogan: str) -> str:
    """Polls until video is ready. Returns video URL."""
    key = os.environ["OPENROUTER_API_KEY"]
    h = {"Authorization": f"Bearer {key}"}

    r = httpx.post("https://openrouter.ai/api/v1/videos", headers=h, json={
        "model": "google/veo-3.1-lite",
        "prompt": (
            f"Terminal screen. Green text '{slogan}' types character by character. "
            f"T-shirt materialises. Dark cinematic. SWE aesthetic. 8 seconds. "
            f"Ambient keyboard sounds."
        ),
        "image_url": product_image_url,
        "duration": 8
    }, timeout=30)

    job_id = r.json()["id"]
    for _ in range(60):            # 10-minute timeout
        time.sleep(10)
        s = httpx.get(f"https://openrouter.ai/api/v1/videos/{job_id}", headers=h).json()
        if s["status"] == "completed": return s["url"]
        if s["status"] == "failed":    raise RuntimeError(s.get("error"))
    raise TimeoutError("Video generation timed out after 10 minutes")
```

### 4.3 Test

Trigger Social Agent manually: "Post one tweet introducing SWE Drip and the first product."
Verify the tweet appears on @swedrip. If using Buffer, verify it appears in the queue.

---

## Day 5 — Operations agents

### 5.1 Analytics Agent

- Model: `anthropic/claude-haiku-4-5`
- Cron: `0 18 * * FRI` (6pm Fri, Marrakech time)
- Budget: $3/mo
- Tools: FW MCP (analytics suite), `file_write`, memory

Test manually → verify `/workspace/reports/weekly_report.md` is created.

### 5.2 Email Agent

- Model: `anthropic/claude-sonnet-4-6`
- Cron: `0 9 * * SAT`
- Budget: $5/mo
- Tools: Loops.so API, FW MCP (`ecommerce_list-offers`), `file_read`

Add Loops tool:
```python
# Tool: send_newsletter
import httpx, os

def send_newsletter(subject: str, body_html: str, list_id: str) -> dict:
    r = httpx.post(
        "https://app.loops.so/api/v1/campaigns",
        headers={"Authorization": f"Bearer {os.environ['LOOPS_API_KEY']}"},
        json={"subject": subject, "html": body_html, "listId": list_id}
    )
    return r.json()
```

### 5.3 Finance Agent

- Model: `google/gemini-2.0-flash-001`
- Cron: `0 9 1 * *` (1st of month)
- Budget: $2/mo
- Tools: FW MCP (`ecommerce_get-payout-transactions`, `ecommerce_get-payout-info`), `file_write`

### 5.4 Community Agent

- Model: `anthropic/claude-haiku-4-5`
- Cron: `0 */12 * * *` (every 12h)
- Budget: $4/mo
- Tools: Twitter API (mentions), Reddit API (keyword search), memory

---

## Day 6 — Full cycle verification

Run the complete weekly simulation. CEO orchestrates all agents in one task:

```
Run the full SWE Drip weekly cycle:
1. Trend Scout → find top 3 briefs from Reddit and Twitter
2. Copy Agent → generate copy for brief #1
3. Design Agent → create and publish to Fourthwall
4. Listing Agent → verify price, tags, collection
5. Social Agent → schedule drop announcement tweet via Buffer
6. Video Agent → generate 8s product clip
7. Analytics Agent → generate this week's report
Report the status of each step. Escalate any failures immediately.
```

All 7 steps should complete within 3 hours.

**Verification checklist:**
- [ ] One new product visible on Fourthwall store
- [ ] Tweet scheduled in Buffer queue
- [ ] `/workspace/reports/weekly_report.md` exists and contains KPI table
- [ ] Telegram notification received by founder
- [ ] No OpenRouter errors in Paperclip logs

---

## Day 7 — Store setup + pre-launch content

- Apply Brutal theme in Fourthwall Dashboard → Themes
- Add custom CSS (see `docs/02-stack.md` for brand CSS)
- Enable coming-soon email capture on FW store
- Run Trend Scout twice (Mon + Thu) this week to generate 10 validated briefs
- Design Agent processes all 10 → **10 products live on Fourthwall before launch**

---

## Week 2 — Pre-launch build

- Social Agent: pre-schedule 20 dev humor tweets (no product links yet) via Buffer
- Email Agent: write launch announcement, hold in Loops.so draft
- Video Agent: 3 product showcase clips created and stored
- Community Agent: 5 value posts on r/ProgrammerHumor to build karma
- CEO: draft Product Hunt listing and Show HN post text

**Launch gate — all must be true before launching:**
- [ ] 10 products live on Fourthwall
- [ ] 3 videos ready
- [ ] 20 tweets pre-scheduled
- [ ] Email list ≥50 subscribers from coming-soon page
- [ ] PH + HN posts drafted
- [ ] Founder Telegram confirmed working
- [ ] All 10 agents show `Running` in Paperclip dashboard

---

## Coolify operations reference

### Redeploy (pull latest image)

Coolify UI → swe-drip project → paperclip → **Redeploy**

Volumes are preserved. Environment variables are preserved. Zero-downtime if health check passes.

### Update environment variables

Coolify UI → paperclip app → **Environment Variables** → edit → **Save** → **Restart**

No SSH needed. Variables take effect on next container start.

### View logs

Coolify UI → paperclip app → **Logs** tab. Streams live. Filter by keyword.
Or SSH: `docker logs $(docker ps -qf name=paperclip) -f --tail 100`

### Backup workspace volume

```bash
# Run on VPS via SSH — backs up the shared workspace to /root/backups/
mkdir -p /root/backups
docker run --rm \
  -v paperclip-workspace:/workspace \
  -v /root/backups:/backup \
  alpine tar czf /backup/workspace-$(date +%Y%m%d).tar.gz -C / workspace
```

Automate via Hetzner's VPS snapshot feature (Dashboard → Server → Snapshots → enable daily).

### Add a second service (e.g. n8n for cron triggers)

Coolify makes multi-service trivial:
```
New Resource → Application → Based on existing Docker Image
Image: n8nio/n8n:latest
Port:  5678
Volumes: n8n-data → /home/node/.n8n
```

All services on the same VPS, all managed from one Coolify dashboard.

---

## Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| FLUX.2 Pro returns blurry/stylised text | Default FLUX aesthetic vs typography | Add explicit prompt constraints: "monospace font, no stylization, pure text design" |
| FW MCP `create-offers-from-designs` fails | PNG format issue | Verify output is RGB (not RGBA), <10MB, ≥2000×2000px |
| Veo 3.1 Lite times out | Complex prompt or server load | Simplify prompt, remove `image_url`, retry without image-to-video |
| Paperclip agent misses cron | Container timezone mismatch | Set `TZ=Africa/Casablanca` in Coolify env vars, redeploy |
| OpenRouter 429 (rate limited) | Burst requests from multiple agents | Add exponential backoff: `time.sleep(2**attempt)` |
| Coolify container shows Stopped | Health check failing | Check logs in Coolify UI → Logs tab. Usually a missing env var. |
| Volume data lost after redeploy | Volume not configured in Coolify | Re-add volumes in Storages tab — data is still in the Docker volume, just not mounted |
