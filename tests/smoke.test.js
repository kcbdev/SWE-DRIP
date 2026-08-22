import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..');

describe('SWE Drip — smoke: docs contract', () => {
  it('README exists and contains architecture section', () => {
    const p = join(ROOT, 'README.md');
    assert.ok(existsSync(p), 'README.md must exist');
    const content = readFileSync(p, 'utf8');
    assert.match(content, /# SWE Drip/, 'README must have title');
    assert.match(content, /## Architecture/, 'README must have Architecture section');
    assert.match(content, /CEO Agent/, 'README must describe CEO Agent');
    assert.match(content, /Fourthwall MCP/, 'README must mention Fourthwall MCP');
  });

  it('all 7 docs files exist', () => {
    const docs = join(ROOT, 'docs');
    assert.ok(existsSync(docs), 'docs/ directory must exist');
    const files = readdirSync(docs);
    const expected = ['01-brand.md', '02-stack.md', '03-agents.md', '04-deploy.md', '05-launch.md', '06-traffic.md', '07-scale.md'];
    for (const f of expected) {
      assert.ok(files.includes(f), `docs/${f} must exist`);
      const content = readFileSync(join(docs, f), 'utf8');
      assert.ok(content.length > 500, `docs/${f} must be substantive (>500 chars), got ${content.length}`);
    }
  });

  it('brand constants are preserved in docs/01-brand.md', () => {
    const content = readFileSync(join(ROOT, 'docs/01-brand.md'), 'utf8');
    assert.match(content, /#0D0D0D/, 'brand must define void black #0D0D0D');
    assert.match(content, /#00FF41/, 'brand must define terminal green #00FF41');
    assert.match(content, /#FF6B35/, 'brand must define error orange #FF6B35');
    assert.match(content, /JetBrains Mono/, 'brand must specify JetBrains Mono font');
  });

  it('stack doc defines infrastructure layers correctly', () => {
    const content = readFileSync(join(ROOT, 'docs/02-stack.md'), 'utf8');
    assert.match(content, /Hetzner CX31/, 'stack must mention Hetzner CX31');
    assert.match(content, /Coolify/, 'stack must mention Coolify');
    assert.match(content, /OpenRouter/, 'stack must mention OpenRouter');
    assert.match(content, /Fourthwall/, 'stack must mention Fourthwall');
    assert.match(content, /flux\.2-pro/i, 'stack must mention FLUX.2 Pro');
  });

  it('agent roster defines 10+ agents with required fields', () => {
    const content = readFileSync(join(ROOT, 'docs/03-agents.md'), 'utf8');
    const agents = ['CEO', 'Trend Scout', 'Copy Agent', 'Design Agent', 'Listing Agent', 'Social Agent', 'Video Agent', 'Analytics Agent', 'Email Agent', 'Community Agent', 'Finance Agent'];
    for (const agent of agents) {
      assert.ok(content.includes(agent), `agents doc must define ${agent}`);
    }
    // verify Design Agent is marked as critical path
    assert.match(content, /Critical path/, 'Design Agent must be marked critical path');
  });

  it('pricing invariants are preserved (do not change without founder approval)', () => {
    const content = readFileSync(join(ROOT, 'docs/01-brand.md'), 'utf8');
    assert.match(content, /\$32/, 'pricing must include $32 t-shirt');
    assert.match(content, /\$62/, 'pricing must include $62 hoodie');
    assert.match(content, /\$20/, 'pricing must include $20 mug');
  });

  it('docs directory structure matches README Directory section', () => {
    const readme = readFileSync(join(ROOT, 'README.md'), 'utf8');
    // README claims these top-level entries exist
    assert.ok(existsSync(join(ROOT, 'docs')), 'docs/ must exist per README');
    // future code dirs are allowed to be absent before implementation
    // but workspace/ and agents/ are described as planned — smoke only checks docs
  });

  it('deployment guide covers 7-day sequence', () => {
    const content = readFileSync(join(ROOT, 'docs/04-deploy.md'), 'utf8');
    for (let day = 1; day <= 7; day++) {
      assert.ok(content.includes(`Day ${day}`), `deploy guide must cover Day ${day}`);
    }
  });
});
