# Stack & Infrastructure

## Overview

Three layers. Everything lives on one Hetzner VPS managed by Coolify.

```
┌──────────────────────────────────────────────────────────┐
│  Hetzner CX31 (€8/mo)                                    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Coolify  (port 8000, self-hosted PaaS)          │    │
│  │  SSL · Traefik reverse proxy · env vars · logs   │    │
│  │                                                  │    │
│  │  ┌──────────────────────────────────────────┐    │    │
│  │  │  Paperclip  (port 3000, Docker image)    │    │    │
│  │  │  CEO agent · task board · workers        │    │    │
│  │  │  /app/data   (named volume)              │    │    │
│  │  │  /workspace  (named volume, shared I/O)  │    │    │
│  │  └──────────────────────────────────────────┘    │    │
│  └──────────────────────────────────────────────────┘    │
└─────────────────────────┬────────────────────────────────┘
                          │ outbound HTTPS only
               ┌──────────┴──────────┐
               │                     │
         OpenRouter API        Fourthwall MCP
         (LLM/Image/Video)    (mcp.fourthwall.com)
         claude-sonnet-4-6    products / orders
         gemini-flash          analytics / payouts
         flux.2-pro            promotions / brand
         veo-3.1-lite
```

---

## Hetzner VPS

**Spec:** CX31 — 4 vCPU / 8 GB RAM / 80 GB NVMe / 20 TB traffic / €8/mo

Runs: Coolify (which manages Paperclip + future services).
All agent calls are outbound HTTP — no inbound ports needed except 22 (SSH) and 8000 (Coolify UI).
Once you add a domain and SSL, port 443 handles Coolify and optionally Paperclip's UI.

```bash
# Provision
hetzner-cli server create \
  --name swe-drip \
  --type cx31 \
  --image ubuntu-24.04 \
  --location nbg1 \
  --ssh-key ~/.ssh/id_ed25519.pub

# Minimal firewall before Coolify install
ssh root@[IP]
apt update
ufw allow 22 && ufw allow 8000 && ufw allow 80 && ufw allow 443 && ufw enable
```

---

## Coolify

<cite>Coolify is a self-hosted deployment platform that runs on top of Docker — it manages applications, databases, and SSL certificates from a web dashboard. The official install script brings everything up in 2–5 minutes on Ubuntu 24.04.</cite>

### Install

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

This installs Docker and starts all Coolify containers automatically. No manual Docker Compose editing required.

Access the dashboard at `http://[IP]:8000`. Create your admin account on first load.

### What Coolify gives you (vs raw Docker)

| Feature | Raw Docker Compose | Coolify |
|---|---|---|
| Deploy updates | SSH + `docker pull` + restart | Click "Redeploy" in UI |
| Environment variables | Edit `.env` via SSH | Web UI form, secrets masked |
| SSL certificates | Manual Certbot setup | Auto Let's Encrypt, auto-renew |
| Persistent volumes | Manual `docker volume` commands | Configured in UI, persists across redeploys |
| Logs | `docker logs` via SSH | Streaming in browser UI |
| Health checks | Manual | Configured in UI with auto-restart |
| Multiple services | Separate compose files | All in one dashboard |
| Reverse proxy | Manual Nginx/Traefik config | Traefik managed by Coolify automatically |

### Add your server

After creating your Coolify admin account:
`Servers → Add Server → Localhost`

Coolify connects to the local Docker daemon via the mounted socket. All deployments run on the same machine.

### Deploy Paperclip

`Projects → New Project → "swe-drip" → New Resource → Application → Based on existing Docker Image`

```
Image name:   paperclipai/paperclip:latest
Port:         3000
```

**Environment variables** — set in Coolify UI under the application's `Environment Variables` tab.
Mark all secrets as **Secret** (masked in UI, not exposed in logs):

| Variable | Value | Secret |
|---|---|---|
| `OPENAI_API_KEY` | `sk-or-v1-xxxx` (OpenRouter key) | ✅ |
| `OPENAI_BASE_URL` | `https://openrouter.ai/api/v1` | |
| `DEFAULT_MODEL` | `anthropic/claude-sonnet-4-6` | |
| `WORKSPACE_PATH` | `/workspace` | |
| `TELEGRAM_BOT_TOKEN` | `xxxx:xxxx` | ✅ |
| `TELEGRAM_CHAT_ID` | `xxxxxxxxxx` | ✅ |
| `FOURTHWALL_MCP_TOKEN` | `fw-oauth-xxxx` | ✅ |
| `LOOPS_API_KEY` | `xxxx` | ✅ |
| `BUFFER_ACCESS_TOKEN` | `xxxx` | ✅ |
| `OPENROUTER_API_KEY` | same as `OPENAI_API_KEY` | ✅ |

> All variables are **runtime variables** (not build-time). <cite>Runtime variables are written to a `.env` file loaded by Docker at container start — they are not baked into the image.</cite>

**Persistent storage** — under `Storages` tab of the Paperclip application:

| Source path (container) | Volume name | Purpose |
|---|---|---|
| `/app/data` | `paperclip-data` | Paperclip state, agent configs |
| `/workspace` | `paperclip-workspace` | Shared I/O between agents (briefs, reports, designs) |

<cite>Both types attach storage from outside the container. Data survives redeployments — only data stored in configured persistent storage persists when the container is replaced.</cite>

**Health check** — Coolify UI → Health Check tab:
```
Path:     /health
Interval: 30s
Timeout:  5s
Retries:  3
```

Click **Deploy**. Coolify pulls the image, mounts volumes, injects env vars, and starts the container. First deploy takes ~60s.

### Optional: domain + SSL

Point `paperclip.swedrip.com` (or any subdomain) to your VPS IP.
In Coolify application settings → Domains → add `https://paperclip.swedrip.com`.
<cite>Coolify uses Let's Encrypt and manages certificate issuance and renewal automatically — no manual Nginx or Certbot config.</cite>

After adding the domain, Coolify's Traefik instance handles all routing. Port 3000 no longer needs to be exposed publicly.

### Coolify MCP (bonus)

There is a community Coolify MCP server (`freqkflag/coolify-mcp-server`) that exposes the Coolify API as MCP tools. This means the CEO agent can be given access to restart services, check deployment logs, and redeploy Paperclip itself — full infrastructure-as-agent. Deploy it as a second Docker Image application in Coolify when ready.

---

## OpenRouter

Single API key, OpenAI-compatible endpoint (`https://openrouter.ai/api/v1`). Covers LLM, image, and video generation. Paperclip treats it as an OpenAI endpoint — no special integration code.

### Model selection by task

| Task | Model | Cost |
|---|---|---|
| CEO / Copy / Email | `anthropic/claude-sonnet-4-6` | $3/$15 per M tokens |
| Trend / Listing / Finance | `google/gemini-2.0-flash-001` | $0.075/$0.30 per M tokens |
| Social / Analytics / Community | `anthropic/claude-haiku-4-5` | $0.80/$4 per M tokens |
| Image generation | `black-forest-labs/flux.2-pro` | ~$0.03/image (megapixel pricing) |
| Image fallback | `google/gemini-3.1-flash-image` | ~$0.04/image |
| Video generation | `google/veo-3.1-lite` | ~$0.40/video (8s) |

### LLM call

```python
import httpx, os

def call_llm(system: str, user: str, model="anthropic/claude-sonnet-4-6") -> str:
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
        json={"model": model, "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]},
        timeout=60
    )
    return r.json()["choices"][0]["message"]["content"]
```

### Image generation (Design Agent)

```python
import httpx, base64, os

def generate_design(slogan: str, model="black-forest-labs/flux.2-pro") -> bytes:
    prompt = (
        f'Minimalist apparel design. Typography: JetBrains Mono Bold. '
        f'Text: "{slogan}". Terminal green #00FF41 on void black #0D0D0D. '
        f'Centered, isolated. No decorations. No gradients. Print-safe flat design.'
    )
    r = httpx.post(
        "https://openrouter.ai/api/v1/images",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
        json={"model": model, "prompt": prompt,
              "image_config": {"width": 2048, "height": 2048}},
        timeout=120
    )
    return base64.b64decode(r.json()["data"][0]["b64_json"])
```

### Video generation (Video Agent — async)

```python
import httpx, time, os

def generate_product_video(product_image_url: str, slogan: str) -> str:
    key = os.environ["OPENROUTER_API_KEY"]
    headers = {"Authorization": f"Bearer {key}"}

    r = httpx.post("https://openrouter.ai/api/v1/videos", headers=headers, json={
        "model": "google/veo-3.1-lite",
        "prompt": (
            f"Terminal screen. Green text '{slogan}' types out. "
            f"T-shirt materializes. Dark cinematic. SWE aesthetic. 8 seconds."
        ),
        "image_url": product_image_url,
        "duration": 8
    }, timeout=30)

    job_id = r.json()["id"]
    for _ in range(60):   # 10-minute timeout
        time.sleep(10)
        s = httpx.get(f"https://openrouter.ai/api/v1/videos/{job_id}", headers=headers).json()
        if s["status"] == "completed": return s["url"]
        if s["status"] == "failed": raise RuntimeError(s.get("error"))
    raise TimeoutError("Video job timed out after 10 minutes")
```

---

## Fourthwall

**Storefront theme:** Brutal.  
**Apply:** Dashboard → Themes → Brutal → Activate.

**Custom CSS** (Dashboard → Theme → Custom CSS):
```css
:root {
  --color-background: #0D0D0D;
  --color-primary: #00FF41;
  --color-text: #FFFFFF;
  --font-display: 'JetBrains Mono', monospace;
}
```

**Fourthwall as Merchant of Record:**
- All customer payments handled by Fourthwall (2.9% + $0.30 per transaction US)
- Sales tax collection and remittance automatic
- Customer support for catalog products handled by Fourthwall
- Payout: Dashboard → Payouts → configure PayPal (verified to work in Morocco)

**MCP integration:**
```
Server URL:  https://mcp.fourthwall.com
Auth:        OAuth 2.0
Setup:       FW Dashboard → Settings → Developer → MCP → copy token
             → paste as FOURTHWALL_MCP_TOKEN env var in Coolify
```

Key MCP tools:

| Tool | Agent | Purpose |
|---|---|---|
| `ecommerce_generate-product-design-previews` | Design Agent | Preview on mockups |
| `ecommerce_create-offers-from-designs` | Design Agent | Publish as live product |
| `ecommerce_get-analytics` | Analytics Agent | Sales, views, conversion |
| `ecommerce_create-promotion` | CEO Agent | Flash sales |
| `ecommerce_list-offers` | Analytics Agent | Active product list for kill logic |
| `ecommerce_update-offer` | Listing Agent | Price, description, status |
| `ecommerce_get-payout-transactions` | Finance Agent | Monthly reconciliation |
| `brand_from_url` | Design Agent | Brand consistency enforcement |

---

## Supporting services

### Loops.so (email)
```
API base:   https://app.loops.so/api/v1
Agent:      Email Agent
Plan:       Free to 1,000 contacts
Key env:    LOOPS_API_KEY
```

### Buffer (social scheduling)
```
API base:   https://api.bufferapp.com/1
Agent:      Social Agent
Plan:       Free (3 channels, 10 queued posts)
Key env:    BUFFER_ACCESS_TOKEN
```

### Telegram (founder notifications)
```python
import httpx, os

def notify_founder(message: str):
    httpx.post(
        f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
        json={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": message, "parse_mode": "Markdown"}
    )
```

---

## Monthly cost summary

| Item | Service | Min | Max |
|---|---|---|---|
| VPS | Hetzner CX31 | €8 | €8 |
| PaaS | Coolify | $0 | $0 |
| LLM calls | OpenRouter | $40 | $70 |
| Image generation | OpenRouter (FLUX.2 Pro) | $15 | $30 |
| Video generation | OpenRouter (Veo 3.1 Lite) | $10 | $20 |
| Email | Loops.so | $0 | $9 |
| Storefront | Fourthwall | $0 | $0 |
| Social scheduling | Buffer | $0 | $0 |
| **Total** | | **~$75** | **~$140** |
| **Break-even** | | **4–5 shirts** | |
