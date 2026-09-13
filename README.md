# SWE Drip V1

Autonomous design studio, print-on-demand operation, and Control Panel for software-engineer culture merchandise — built as a custom LangGraph pipeline (Paperclip/Hermes retired).

**Status (2026-09-13): docs-only.** The v1.0 spec kit is the source of truth; no runtime code exists yet. Implementation is sequenced through ASDLC (`asdlc-plan` → `asdlc-execute`) from `docs/swe-drip-delivery-acceptance-spec-v1.md`.

## Where knowledge lives

| Question | Answer in |
|---|---|
| What is the product and how does the system work? | [`docs/swe-drip-product-vision-v1.md`](docs/swe-drip-product-vision-v1.md) |
| What are we selling, to whom, at what price? | [`docs/swe-drip-product-definition-v1.md`](docs/swe-drip-product-definition-v1.md) |
| What must the Control Panel do? | [`docs/swe-drip-prd-v1.md`](docs/swe-drip-prd-v1.md) |
| How does it look and behave? | [`docs/swe-drip-ux-spec-v1.md`](docs/swe-drip-ux-spec-v1.md) |
| How is it built (stack, auth, persistence)? | [`docs/swe-drip-technical-spec-v1.md`](docs/swe-drip-technical-spec-v1.md) |
| Schemas, endpoints, model routing? | [`docs/swe-drip-data-api-llm-spec-v1.md`](docs/swe-drip-data-api-llm-spec-v1.md) |
| Build order and acceptance criteria? | [`docs/swe-drip-delivery-acceptance-spec-v1.md`](docs/swe-drip-delivery-acceptance-spec-v1.md) |
| Stack, gates, conventions, Context Map, Plane binding? | [`AGENTS.md`](AGENTS.md) |
| As-built vs target architecture? | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| What is sequenced and what has run? | [`plans/README.md`](plans/README.md), [`plans/PROGRESS.md`](plans/PROGRESS.md) |

## Deterministic gates

```bash
cmd /c "npm run verify"   # build && lint && test — the Ralph Loop gate
```

Win environment: use `cmd /c` variants; paths contain spaces.

## Workflow

1. `asdlc-plan` derives `specs/{feature}/spec.md` + `tasks/PBI-*.md` from the delivery phases / Plane `Todo` issues.
2. `asdlc-execute` runs the Ralph Loop: implement → gates → adversarial + constitutional review → `In Review`/`Done` with review-type sorting.
3. Plane binding: `kcb / SWDRP` (`d162b6d4-1205-4eea-9ef3-871354c5e8a3`) — verified 2026-09-13.

Reference: the retired POC (`C:\Users\kcb19\Work\KCB\SWE-DRIP`, remote `kcbdev/SWE-DRIP-POC`) is consultable for gaps/decisions but nothing is applied without human validation.
