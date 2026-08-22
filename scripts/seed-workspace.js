#!/usr/bin/env node
// PBI-005: idempotent workspace seed (docs/04-deploy.md 1.11, local sim of Coolify volume).
// Creates dirs + empty JSON files ONLY if missing. Never overwrites existing data. Always exits 0.
import { mkdirSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..');
const WS = join(ROOT, 'workspace');

for (const dir of [WS, join(WS, 'designs'), join(WS, 'reports'), join(WS, 'fixtures')]) {
  mkdirSync(dir, { recursive: true });
}

for (const f of ['design_briefs.json', 'listing_copy.json']) {
  const p = join(WS, f);
  if (!existsSync(p)) {
    writeFileSync(p, '[]\n');
    console.log(`seeded ${f} -> []`);
  } else {
    // touch nothing; report preserved state
    let n = '?';
    try { n = String(JSON.parse(readFileSync(p, 'utf8')).length); } catch { /* leave */ }
    console.log(`preserved ${f} (${n} item(s))`);
  }
}
console.log('workspace ready');
process.exit(0);
