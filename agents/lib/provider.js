// PBI-019: OpenRouter provider layer — the ONLY place Hermes workers touch the network.
// specs/llm-config contracts 2,3. Key is founder-owned: set OPENROUTER_API_KEY (or
// OPENAI_API_KEY alias) in Paperclip UI env vars or Coolify → swedrip → Environment Variables.
// Never baked into code or image. fetch is injectable for tests.

const DEFAULT_BASE_URL = 'https://openrouter.ai/api/v1';

export function resolveConfig(env = process.env) {
  const baseUrl = (env.OPENAI_BASE_URL || DEFAULT_BASE_URL).replace(/\/$/, '');
  const apiKey = env.OPENROUTER_API_KEY || env.OPENAI_API_KEY || null;
  return { baseUrl, apiKey };
}

function requireKey(env = process.env) {
  const { baseUrl, apiKey } = resolveConfig(env);
  if (!apiKey) {
    throw new Error(
      'OpenRouter API key missing — set OPENROUTER_API_KEY to continue. ' +
      'Founder setup: paste the key in Paperclip UI → Environment Variables, or Coolify → ' +
      'swe-drip/swedrip → Environment Variables (mark Secret), then redeploy. ' +
      `Base URL in use: ${baseUrl}`
    );
  }
  return { baseUrl, apiKey };
}

function headers(apiKey) {
  return { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' };
}

// --- LLM chat (docs/02-stack.md call_llm shape) ---
export async function callLLM(system, user, model, opts = {}) {
  const doFetch = opts.fetchImpl ?? globalThis.fetch;
  const env = opts.env ?? process.env;
  const { baseUrl, apiKey } = requireKey(env);
  const body = { model, messages: [{ role: 'system', content: system }, { role: 'user', content: user }] };
  const res = await doFetch(`${baseUrl}/chat/completions`, {
    method: 'POST', headers: headers(apiKey), body: JSON.stringify(body),
    signal: AbortSignal.timeout(opts.timeoutMs ?? 60000)
  });
  if (!res.ok) throw new Error(`OpenRouter chat failed ${res.status}: ${await res.text()}`);
  const json = await res.json();
  return json.choices[0].message.content;
}

// --- Image generation (Design Agent; docs/02-stack.md generate_design shape) ---
export async function generateImage(prompt, model, opts = {}) {
  const doFetch = opts.fetchImpl ?? globalThis.fetch;
  const env = opts.env ?? process.env;
  const { baseUrl, apiKey } = requireKey(env);
  const width = opts.width ?? 2048, height = opts.height ?? 2048;
  const body = { model, prompt, image_config: { width, height } };
  const res = await doFetch(`${baseUrl}/images`, {
    method: 'POST', headers: headers(apiKey), body: JSON.stringify(body),
    signal: AbortSignal.timeout(opts.timeoutMs ?? 120000)
  });
  if (!res.ok) throw new Error(`OpenRouter images failed ${res.status}: ${await res.text()}`);
  const json = await res.json();
  return Buffer.from(json.data[0].b64_json, 'base64');
}

// --- Video generation (Video Agent; docs/02-stack.md generate_product_video shape) ---
// Async: POST /videos -> poll GET /videos/{id} every 10s, <=60 tries (10 min), per spec contract 2.
export function buildVideoJobRequest(prompt, model, opts = {}) {
  const env = opts.env ?? process.env;
  const { baseUrl, apiKey } = requireKey(env);
  return {
    url: `${baseUrl}/videos`,
    init: {
      method: 'POST', headers: headers(apiKey),
      body: JSON.stringify({ model, prompt, duration: opts.duration ?? 8 })
    }
  };
}

export function buildVideoPollRequest(jobId, opts = {}) {
  const env = opts.env ?? process.env;
  const { baseUrl, apiKey } = requireKey(env);
  return { url: `${baseUrl}/videos/${jobId}`, init: { method: 'GET', headers: headers(apiKey) } };
}

export async function generateVideo(prompt, model, opts = {}) {
  const doFetch = opts.fetchImpl ?? globalThis.fetch;
  const maxTries = opts.maxTries ?? 60;
  const intervalMs = opts.intervalMs ?? 10000;

  const job = buildVideoJobRequest(prompt, model, opts);
  const startRes = await doFetch(job.url, { ...job.init, signal: AbortSignal.timeout(30000) });
  if (!startRes.ok) throw new Error(`OpenRouter videos POST failed ${startRes.status}: ${await startRes.text()}`);
  const { id } = await startRes.json();

  for (let i = 0; i < maxTries; i++) {
    await new Promise(r => setTimeout(r, intervalMs));
    const poll = buildVideoPollRequest(id, opts);
    const s = await (await doFetch(poll.url, poll.init)).json();
    if (s.status === 'completed') return s.url;
    if (s.status === 'failed') throw new Error(s.error ?? 'video generation failed');
  }
  throw new Error('Video generation timed out after 10 minutes');
}

// --- Budget guard (specs/platform-workspace Decision-4 + AGENTS.md §3) ---
import { readdirSync, readFileSync, existsSync } from 'node:fs';
import { join as _join } from 'node:path';
import { TOTAL_BUDGET_CAP_USD_MONTH } from './config.js';

export function sumAgentSpend(reportsDir, readImpl = { readdirSync, readFileSync, existsSync }) {
  const { readdirSync: rd, readFileSync: rf, existsSync: ex } = readImpl;
  if (!ex(reportsDir)) return 0;
  let total = 0;
  for (const f of rd(reportsDir)) {
    if (!f.endsWith('.json')) continue;
    try {
      const j = JSON.parse(rf(_join(reportsDir, f), 'utf8'));
      total += Number(j.spend_usd ?? j.spend ?? 0);
    } catch { /* skip malformed */ }
  }
  return total;
}

export function assertBudgetCap(projectedAdditionalUsd = 0, reportsDir = undefined, cap = TOTAL_BUDGET_CAP_USD_MONTH) {
  const current = reportsDir ? sumAgentSpend(reportsDir) : 0;
  const projected = current + projectedAdditionalUsd;
  if (projected > cap) {
    throw new Error(`Budget cap exceeded: $${projected.toFixed(2)} projected > $${cap}/mo cap (current spend $${current.toFixed(2)}, additional $${projectedAdditionalUsd.toFixed(2)}). Reduce scope or raise cap via ADR.`);
  }
  return { current, projected, cap };
}
