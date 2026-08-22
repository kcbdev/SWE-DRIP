#!/usr/bin/env node
// PBI-005: zero-dep workspace validators (manual mirror of schemas/*.json — no ajv).
// Usage: node scripts/validate-workspace.js            -> validates live workspace files
//        node scripts/validate-workspace.js <file.json> -> validates one file (type inferred by name)
// Exports validators for tests. Exit 1 on violation.
import { readFileSync, existsSync } from 'node:fs';
import { join, basename } from 'node:path';

const ROOT = join(import.meta.dirname, '..');

export function validateDesignBrief(b) {
  const errors = [];
  const req = ['phrase', 'source_url', 'score', 'score_breakdown', 'rationale', 'suggested_aesthetic'];
  for (const k of req) if (!(k in b)) errors.push(`missing required field "${k}"`);
  if ('phrase' in b && (typeof b.phrase !== 'string' || b.phrase.length < 1)) errors.push('phrase must be non-empty string');
  if ('source_url' in b && (typeof b.source_url !== 'string' || b.source_url.length < 1)) errors.push('source_url must be non-empty string');
  if ('score' in b) {
    if (typeof b.score !== 'number') errors.push('score must be number');
    else if (b.score < 0 || b.score > 100) errors.push(`score ${b.score} out of range 0-100`);
    // business rule (spec): refuse score<60 unless flagged for CEO review
    if (typeof b.score === 'number' && b.score < 60 && !b.flag) errors.push(`score ${b.score} < 60 requires "flag" for CEO review`);
  }
  if ('score_breakdown' in b) {
    const sb = b.score_breakdown;
    const limits = { engagement: 40, novelty: 30, specificity: 30 };
    for (const [k, max] of Object.entries(limits)) {
      const v = sb?.[k];
      if (typeof v !== 'number') errors.push(`score_breakdown.${k} must be number`);
      else if (v < 0 || v > max) errors.push(`score_breakdown.${k}=${v} out of range 0-${max}`);
    }
    if (typeof b.score === 'number' && typeof sb?.engagement === 'number' && typeof sb?.novelty === 'number' && typeof sb?.specificity === 'number') {
      if (sb.engagement + sb.novelty + sb.specificity !== b.score) errors.push('score must equal sum of breakdown');
    }
  }
  if ('suggested_aesthetic' in b && !['terminal', 'minimal', 'dark-humor'].includes(b.suggested_aesthetic)) {
    errors.push(`suggested_aesthetic "${b.suggested_aesthetic}" not in terminal|minimal|dark-humor`);
  }
  if ('flag' in b && b.flag !== null && typeof b.flag !== 'string') errors.push('flag must be string or null');
  return errors;
}

export function validateListingCopy(c) {
  const errors = [];
  const req = ['brief_id', 'primary_slogan', 'fw_title', 'fw_description', 'fw_tags', 'product_types'];
  for (const k of req) if (!(k in c)) errors.push(`missing required field "${k}"`);
  if ('primary_slogan' in c) {
    const words = c.primary_slogan.trim().split(/\s+/).length;
    if (words > 6) errors.push(`primary_slogan has ${words} words (>6)`);
  }
  if ('fw_title' in c && c.fw_title.length > 60) errors.push(`fw_title ${c.fw_title.length} chars (>60)`);
  if ('fw_description' in c) {
    const words = c.fw_description.trim().split(/\s+/).length;
    if (words < 150 || words > 200) errors.push(`fw_description ${words} words outside 150-200`);
  }
  if ('fw_tags' in c) {
    if (!Array.isArray(c.fw_tags) || c.fw_tags.length !== 13) errors.push(`fw_tags must have exactly 13 items (got ${Array.isArray(c.fw_tags) ? c.fw_tags.length : 'non-array'})`);
  }
  if ('product_types' in c) {
    const allowed = ['tshirt', 'hoodie', 'mug'];
    if (!Array.isArray(c.product_types) || c.product_types.length < 1) errors.push('product_types must be non-empty array');
    else for (const t of c.product_types) if (!allowed.includes(t)) errors.push(`product_type "${t}" not in tshirt|hoodie|mug`);
  }
  if ('product_url' in c && c.product_url !== null && typeof c.product_url !== 'string') errors.push('product_url must be string or null');
  return errors;
}

function validateFile(path) {
  const name = basename(path);
  let data;
  try { data = JSON.parse(readFileSync(path, 'utf8')); } catch (e) { console.error(`FAIL: ${path} invalid JSON: ${e.message}`); process.exit(1); }
  if (!Array.isArray(data)) { console.error(`FAIL: ${path} top-level must be array`); process.exit(1); }
  const fn = name.startsWith('design_briefs') ? validateDesignBrief : validateListingCopy;
  let bad = 0;
  data.forEach((item, i) => {
    const errs = fn(item);
    if (errs.length) { bad++; errs.forEach(e => console.error(`FAIL: ${path}[${i}] ${e}`)); }
  });
  if (bad) { console.error(`\nvalidate-workspace: ${bad} invalid item(s) in ${path}`); process.exit(1); }
  console.log(`OK: ${path} (${data.length} item(s) valid)`);
}

const arg = process.argv[2];
if (arg) {
  validateFile(arg.startsWith('/') || /^[a-zA-Z]:/.test(arg) ? arg : join(process.cwd(), arg));
} else {
  let missing = false;
  for (const f of ['design_briefs.json', 'listing_copy.json']) {
    const p = join(ROOT, 'workspace', f);
    if (!existsSync(p)) { console.error(`FAIL: workspace/${f} missing — run scripts/seed-workspace.js`); missing = true; }
    else validateFile(p);
  }
  if (missing) process.exit(1);
}
