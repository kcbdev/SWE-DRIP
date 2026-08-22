import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, existsSync, rmSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = join(import.meta.dirname, '..');
const WS = join(ROOT, 'workspace');
const seed = () => execFileSync(process.execPath, [join(ROOT, 'scripts', 'seed-workspace.js')], { encoding: 'utf8' });

// import validators from the CLI script (ESM exports)
const { validateDesignBrief, validateListingCopy } = await import(pathToFileURL(join(ROOT, 'scripts', 'validate-workspace.js')).href);

describe('PBI-005 — workspace schemas', () => {
  it('schema files exist and are structurally sound', () => {
    const db = JSON.parse(readFileSync(join(ROOT, 'schemas/design_brief.schema.json'), 'utf8'));
    assert.equal(db.type, 'array');
    const req = db.items.required;
    for (const k of ['phrase', 'source_url', 'score', 'score_breakdown', 'rationale', 'suggested_aesthetic']) {
      assert.ok(req.includes(k), `design_brief requires ${k}`);
    }
    const lc = JSON.parse(readFileSync(join(ROOT, 'schemas/listing_copy.schema.json'), 'utf8'));
    for (const k of ['brief_id', 'primary_slogan', 'fw_title', 'fw_description', 'fw_tags', 'product_types']) {
      assert.ok(lc.items.required.includes(k), `listing_copy requires ${k}`);
    }
  });
});

describe('PBI-005 — design brief validator', () => {
  const valid = {
    phrase: 'git push --force (and pray)',
    source_url: 'https://reddit.com/r/ProgrammerHumor/x',
    score: 82,
    score_breakdown: { engagement: 35, novelty: 22, specificity: 25 },
    rationale: 'universal shared trauma',
    suggested_aesthetic: 'terminal',
    flag: null
  };
  it('accepts a valid brief', () => assert.deepEqual(validateDesignBrief(valid), []));
  it('rejects score >100', () => assert.ok(validateDesignBrief({ ...valid, score: 101 }).some(e => e.includes('out of range'))));
  it('rejects breakdown sum != score', () => assert.ok(validateDesignBrief({ ...valid, score: 90 }).some(e => e.includes('sum'))));
  it('rejects engagement >40', () => assert.ok(validateDesignBrief({ ...valid, score_breakdown: { engagement: 41, novelty: 22, specificity: 19 } }).some(e => e.includes('engagement'))));
  it('enforces score<60 requires flag (spec business rule)', () => {
    const low = { ...valid, score: 45, score_breakdown: { engagement: 15, novelty: 15, specificity: 15 } };
    assert.ok(validateDesignBrief(low).some(e => e.includes('< 60')));
    assert.deepEqual(validateDesignBrief({ ...low, flag: 'CEO review' }), []);
  });
  it('rejects bad aesthetic enum', () => assert.ok(validateDesignBrief({ ...valid, suggested_aesthetic: 'pastel' }).some(e => e.includes('aesthetic'))));
});

describe('PBI-005 — listing copy validator', () => {
  const valid = {
    brief_id: 'b-001',
    primary_slogan: 'git blame',
    slogan_variants: ['git blame', 'blameless', 'who did this'],
    fw_title: 'Git Blame Developer T-Shirt | Funny Coding Gift',
    fw_description: 'x '.repeat(160).trim(),
    fw_tags: Array.from({ length: 13 }, (_, i) => `tag${i}`),
    product_types: ['tshirt'],
    product_url: null
  };
  it('accepts valid copy', () => assert.deepEqual(validateListingCopy(valid), []));
  it('rejects slogan with 7 words', () => assert.ok(validateListingCopy({ ...valid, primary_slogan: 'one two three four five six seven' }).some(e => e.includes('>6'))));
  it('rejects fw_title >60 chars', () => assert.ok(validateListingCopy({ ...valid, fw_title: 'x'.repeat(61) }).some(e => e.includes('>60'))));
  it('rejects description outside 150-200 words', () => assert.ok(validateListingCopy({ ...valid, fw_description: 'too short' }).some(e => e.includes('150-200'))));
  it('rejects tags != 13', () => assert.ok(validateListingCopy({ ...valid, fw_tags: valid.fw_tags.slice(0, 12) }).some(e => e.includes('exactly 13'))));
  it('rejects unknown product_type', () => assert.ok(validateListingCopy({ ...valid, product_types: ['poster'] }).some(e => e.includes('poster'))));
});

describe('PBI-005 — seed idempotence', () => {
  beforeEach(() => {
    // start from clean slate but keep dirs
    if (!existsSync(WS)) seed();
    for (const f of ['design_briefs.json', 'listing_copy.json']) {
      const p = join(WS, f);
      if (existsSync(p)) rmSync(p);
    }
  });

  it('seeds missing files as [] and exits 0 twice', () => {
    const out1 = seed();
    assert.match(out1, /seeded design_briefs\.json/);
    assert.equal(JSON.parse(readFileSync(join(WS, 'design_briefs.json'), 'utf8')).length, 0);
    const out2 = seed(); // second run must not fail
    assert.match(out2, /preserved design_briefs\.json/);
  });

  it('never overwrites existing data', () => {
    seed();
    writeFileSync(join(WS, 'design_briefs.json'), JSON.stringify([{ phrase: 'exit 0' }]));
    seed();
    const after = JSON.parse(readFileSync(join(WS, 'design_briefs.json'), 'utf8'));
    assert.equal(after.length, 1);
    assert.equal(after[0].phrase, 'exit 0');
  });

  it('live workspace files pass validators', () => {
    seed();
    const db = JSON.parse(readFileSync(join(WS, 'design_briefs.json'), 'utf8'));
    for (const b of db) assert.deepEqual(validateDesignBrief(b), []);
    const lc = JSON.parse(readFileSync(join(WS, 'listing_copy.json'), 'utf8'));
    for (const c of lc) assert.deepEqual(validateListingCopy(c), []);
  });
});
