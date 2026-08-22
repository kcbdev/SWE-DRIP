import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = join(import.meta.dirname, '..');
const { AGENTS, TOTAL_BUDGET_CAP_USD_MONTH, getAgent, listAgents } =
  await import(pathToFileURL(join(ROOT, 'agents', 'lib', 'config.js')).href);
const { resolveConfig, callLLM, generateImage, buildVideoJobRequest, buildVideoPollRequest, sumAgentSpend, assertBudgetCap } =
  await import(pathToFileURL(join(ROOT, 'agents', 'lib', 'provider.js')).href);

describe('PBI-019 — agent registry mirrors docs/03-agents.md roster', () => {
  const roster = [
    ['ceo', 'anthropic/claude-sonnet-4-6', 30],
    ['trendScout', 'google/gemini-2.0-flash-001', 6],
    ['copy', 'anthropic/claude-sonnet-4-6', 15],
    ['design', 'black-forest-labs/flux.2-pro', 30],
    ['listing', 'google/gemini-2.0-flash-001', 5],
    ['social', 'anthropic/claude-haiku-4-5', 4],
    ['video', 'google/veo-3.1-lite', 20],
    ['analytics', 'anthropic/claude-haiku-4-5', 3],
    ['email', 'anthropic/claude-sonnet-4-6', 5],
    ['community', 'anthropic/claude-haiku-4-5', 4],
    ['finance', 'google/gemini-2.0-flash-001', 2]
  ];
  it('has all 11 agents with doc-correct model + budget', () => {
    assert.equal(listAgents().length, 11);
    for (const [key, model, cap] of roster) {
      const a = getAgent(key);
      assert.equal(a.model, model, `${key} model`);
      assert.equal(a.budgetCapUsdMonth, cap, `${key} budget`);
    }
  });
  it('per-agent caps sum under the $130 total cap', () => {
    const sum = listAgents().reduce((s, a) => s + a.budgetCapUsdMonth, 0);
    assert.ok(sum <= TOTAL_BUDGET_CAP_USD_MONTH, `caps sum ${sum} > ${TOTAL_BUDGET_CAP_USD_MONTH}`);
  });
  it('getAgent throws on unknown key', () => assert.throws(() => getAgent('nope'), /unknown agent/));
});

describe('PBI-019 — provider request shapes (mocked fetch)', () => {
  const env = { OPENROUTER_API_KEY: 'sk-or-test', OPENAI_BASE_URL: 'https://openrouter.ai/api/v1' };

  it('callLLM posts exact chat shape to /chat/completions', async () => {
    let captured;
    const fetchImpl = async (url, init) => {
      captured = { url, init };
      return { ok: true, json: async () => ({ choices: [{ message: { content: 'hi' } }] }) };
    };
    const out = await callLLM('sys', 'usr', 'anthropic/claude-sonnet-4-6', { fetchImpl, env });
    assert.equal(out, 'hi');
    assert.equal(captured.url, 'https://openrouter.ai/api/v1/chat/completions');
    assert.equal(captured.init.headers.Authorization, 'Bearer sk-or-test');
    const body = JSON.parse(captured.init.body);
    assert.deepEqual(body, { model: 'anthropic/claude-sonnet-4-6', messages: [{ role: 'system', content: 'sys' }, { role: 'user', content: 'usr' }] });
  });

  it('generateImage posts image_config 2048x2048 to /images', async () => {
    let captured;
    const fetchImpl = async (url, init) => {
      captured = { url, init };
      return { ok: true, json: async () => ({ data: [{ b64_json: Buffer.from('png').toString('base64') }] }) };
    };
    const buf = await generateImage('prompt text', 'black-forest-labs/flux.2-pro', { fetchImpl, env });
    assert.equal(buf.toString(), 'png');
    assert.equal(captured.url, 'https://openrouter.ai/api/v1/images');
    const body = JSON.parse(captured.init.body);
    assert.equal(body.model, 'black-forest-labs/flux.2-pro');
    assert.deepEqual(body.image_config, { width: 2048, height: 2048 });
  });

  it('video job + poll builders match docs/02-stack shape', () => {
    const job = buildVideoJobRequest('terminal prompt', 'google/veo-3.1-lite', { env });
    assert.equal(job.url, 'https://openrouter.ai/api/v1/videos');
    const jb = JSON.parse(job.init.body);
    assert.equal(jb.model, 'google/veo-3.1-lite');
    assert.equal(jb.duration, 8);
    const poll = buildVideoPollRequest('job_123', { env });
    assert.equal(poll.url, 'https://openrouter.ai/api/v1/videos/job_123');
    assert.equal(poll.init.method, 'GET');
  });
});

describe('PBI-019 — missing key fails loud with founder instructions', () => {
  it('throws naming OPENROUTER_API_KEY + Paperclip UI, zero network attempts', async () => {
    let networkTouched = false;
    const fetchImpl = async () => { networkTouched = true; return { ok: true, json: async () => ({}) }; };
    await assert.rejects(
      () => callLLM('s', 'u', 'm', { fetchImpl, env: {} }),
      (e) => e.message.includes('set OPENROUTER_API_KEY') && e.message.includes('Paperclip UI')
    );
    assert.equal(networkTouched, false, 'must not attempt network without key');
  });
});

describe('PBI-019 — budget cap guard', () => {
  const dir = join(ROOT, 'workspace', 'reports');
  it('passes when projected <= $130', () => {
    const r = assertBudgetCap(10, undefined); // no reports dir -> current 0
    assert.equal(r.projected, 10);
  });
  it('throws naming the breach when projected > $130', () => {
    assert.throws(() => assertBudgetCap(131), /Budget cap exceeded.*\$131\.00.*\$130/);
  });
  it('sums spend from workspace/reports/*.json fixtures', () => {
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, 'week1.json'), JSON.stringify({ spend_usd: 40 }));
    writeFileSync(join(dir, 'week2.json'), JSON.stringify({ spend_usd: 35 }));
    writeFileSync(join(dir, 'notes.md'), 'not json, skipped');
    assert.equal(sumAgentSpend(dir), 75);
    rmSync(join(dir, 'week1.json'));
    rmSync(join(dir, 'week2.json'));
  });
});

describe('PBI-019 — no secrets in repo (contract 5)', () => {
  it('no sk-or- pattern in tracked source files', () => {
    const offenders = [];
    for (const dir of ['agents', 'scripts', 'tests', 'schemas']) {
      for (const f of readdirSync(join(ROOT, dir), { recursive: true })) {
        const p = join(ROOT, dir, f);
        try {
          if (readFileSync(p, 'utf8').match(/sk-or-v1-[A-Za-z0-9]/)) offenders.push(p);
        } catch { /* binary */ }
      }
    }
    assert.deepEqual(offenders, []);
  });
});
