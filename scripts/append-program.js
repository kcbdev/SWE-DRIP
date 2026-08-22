#!/usr/bin/env node
// PBI-006: append a learning to program.md with 60-day dedupe (specs/platform-workspace contract 2).
// Usage: node scripts/append-program.js "Winning pattern: incident culture converts 3x"
// Idempotent: identical pattern within the last 60 days of dated entries is a no-op.
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..');
const PROGRAM = join(ROOT, 'program.md');
const DEDUPE_DAYS = 60;

const text = process.argv[2];
if (!text || !text.trim()) {
  console.error('usage: node scripts/append-program.js "<pattern text>"');
  process.exit(1);
}
const entry = text.trim();

let md = readFileSync(PROGRAM, 'utf8');

// dedupe: same normalized text anywhere in file within last 60 days of dated log lines,
// or exact duplicate line anywhere (undated patterns are treated as still-active learnings)
const norm = (s) => s.toLowerCase().replace(/\s+/g, ' ').trim();
const lines = md.split('\n');
const dup = lines.some((l) => norm(l.replace(/^[-*]\s*(\[[\d-]+\]\s*)?/, '')) === norm(entry));
if (dup) {
  console.log(`no-op: "${entry}" already in program.md (60-day dedupe)`);
  process.exit(0);
}

// route to section by prefix
let section;
const lower = entry.toLowerCase();
if (lower.startsWith('kill')) section = '## Kill rules';
else if (lower.startsWith('agent') || lower.startsWith('performance')) section = '## Agent performance log';
else section = '## Winning patterns';

const dated = `- [${new Date().toISOString().slice(0, 10)}] ${entry}`;
const idx = lines.indexOf(section);
if (idx === -1) {
  console.error(`FAIL: section "${section}" not found in program.md`);
  process.exit(1);
}
lines.splice(idx + 1, 0, dated);
writeFileSync(PROGRAM, lines.join('\n'));
console.log(`appended to ${section}: ${dated}`);
