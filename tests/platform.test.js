import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, rmSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = join(import.meta.dirname, '..');
const PROGRAM = join(ROOT, 'program.md');
const SUMMARY = join(ROOT, 'program-summary.md');
const append = (t) => execFileSync(process.execPath, [join(ROOT, 'scripts', 'append-program.js'), t], { encoding: 'utf8' });
const compact = () => execFileSync(process.execPath, [join(ROOT, 'scripts', 'compact-program.js')], { encoding: 'utf8' });
const { decideApproveBrief, decideKill, decideScale, decideFlashSale } =
  await import(pathToFileURL(join(ROOT, 'agents', 'ceo', 'rules.js')).href);

describe('PBI-006 — CEO decision rules (pure)', () => {
  it('approve brief at exactly 60 and above; reject below', () => {
    assert.equal(decideApproveBrief(60), true);
    assert.equal(decideApproveBrief(100), true);
    assert.equal(decideApproveBrief(59), false);
    assert.equal(decideApproveBrief(0), false);
  });
  it('kill only when >30 days AND 0 sales', () => {
    assert.equal(decideKill(31, 0), true);
    assert.equal(decideKill(30, 0), false);   // boundary: not >30
    assert.equal(decideKill(100, 1), false);  // has sales
    assert.equal(decideKill(10, 0), false);   // too young
  });
  it('scale at >=5 sales in 14 days', () => {
    assert.equal(decideScale(5), true);
    assert.equal(decideScale(6), true);
    assert.equal(decideScale(4), false);
  });
  it('flash sale only at <= -30% WoW', () => {
    assert.equal(decideFlashSale(-0.30), true);
    assert.equal(decideFlashSale(-0.45), true);
    assert.equal(decideFlashSale(-0.29), false);
    assert.equal(decideFlashSale(0.1), false);
  });
});

describe('PBI-006 — program.md append dedupe', () => {
  const before = readFileSync(PROGRAM, 'utf8');
  it('appends a new pattern to Winning patterns', () => {
    const out = append('Winning pattern: incident culture converts 3x');
    assert.match(out, /appended to ## Winning patterns/);
    assert.ok(readFileSync(PROGRAM, 'utf8').includes('incident culture converts 3x'));
  });
  it('second identical append is a no-op (60-day dedupe)', () => {
    const out = append('Winning pattern: incident culture converts 3x');
    assert.match(out, /no-op/);
    const count = readFileSync(PROGRAM, 'utf8').split('\n').filter(l => l.includes('incident culture converts 3x')).length;
    assert.equal(count, 1);
  });
  it('kill-prefixed entries route to Kill rules section', () => {
    const out = append('Kill rule test entry: never ship pastel designs');
    assert.match(out, /appended to ## Kill rules/);
  });
});

describe('PBI-006 — program compaction (drift fix)', () => {
  it('compacts: merges dupes, archives stale, keeps kill rules verbatim, <=500 lines', () => {
    // seed a bloated program with duplicates + stale + old log
    const staleDate = new Date(Date.now() - 120 * 86400000).toISOString().slice(0, 10);
    const recentDate = new Date().toISOString().slice(0, 10);
    const oldLogDate = new Date(Date.now() - 120 * 86400000).toISOString().slice(0, 10);
    const bloated = [
      '# program.md — SWE Drip institutional memory', '',
      '## Winning patterns',
      `- [${recentDate}] Winning pattern: terminal aesthetic converts`,
      `- [${recentDate}] Winning pattern: terminal aesthetic converts`,          // duplicate -> merge
      `- [${staleDate}] Winning pattern: rust edition drop`,                     // stale >90d unreinforced -> archive
      '', '## Kill rules',
      '- 0 sales after 30 days → archive listing via FW MCP `ecommerce_update-offer` status inactive',
      '- Pricing invariant: $32 tee / $62 hoodie / $20 mug — founder approval required',
      '', '## Agent performance log',
      `- [${oldLogDate}] Trend Scout missed cron`,                               // >90d -> trimmed
      `- [${recentDate}] Analytics report generated`,                            // kept
      '', '## Archive', ''
    ].join('\n');
    writeFileSync(PROGRAM, bloated);
    compact();
    const s = readFileSync(SUMMARY, 'utf8');
    const lines = s.split('\n');
    // merged duplicate
    assert.equal(lines.filter(l => l.includes('terminal aesthetic converts')).length, 1);
    // stale archived
    assert.ok(s.includes('rust edition drop'));
    const archiveIdx = s.indexOf('## Archive');
    const winningIdx = s.indexOf('## Winning patterns');
    assert.ok(s.indexOf('rust edition drop') > archiveIdx, 'stale pattern moved under Archive');
    // kill rules verbatim
    assert.ok(s.includes('archive listing via FW MCP'));
    assert.ok(s.includes('$32 tee / $62 hoodie / $20 mug'));
    // log trimmed to 90d
    assert.ok(!s.includes('Trend Scout missed cron'), 'old log entry removed');
    assert.ok(s.includes('Analytics report generated'));
    // line cap
    assert.ok(lines.length <= 500, `summary ${lines.length} lines must be <=500`);
  });
});

describe('PBI-006 — lint guards', () => {
  it('brand invariants still present in docs/01-brand.md (lint enforces)', () => {
    const brand = readFileSync(join(ROOT, 'docs/01-brand.md'), 'utf8');
    for (const inv of ['#0D0D0D', '#00FF41', '#FF6B35', 'JetBrains Mono', '$32', '$62', '$20']) {
      assert.ok(brand.includes(inv), `${inv} missing`);
    }
  });
});
