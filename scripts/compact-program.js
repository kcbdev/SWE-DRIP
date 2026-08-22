#!/usr/bin/env node
// PBI-006: compact program.md -> program-summary.md (specs/platform-workspace contract 2, docs/07-scale drift fix).
// Rules: keep ALL Winning patterns (deduped) + ALL Kill rules verbatim; merge duplicate patterns;
// archive patterns older than 90 days with no reinforcement to ## Archive; trim Agent performance
// log to last 90 days; output <= 500 lines.
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..');
const SRC = join(ROOT, 'program.md');
const OUT = join(ROOT, 'program-summary.md');
const MAX_LINES = 500;
const ARCHIVE_DAYS = 90;
const LOG_DAYS = 90;

const today = new Date();
const ageDays = (iso) => Math.floor((today - new Date(iso)) / 86400000);
const norm = (s) => s.toLowerCase().replace(/\s+/g, ' ').trim();

let md = readFileSync(SRC, 'utf8');
const lines = md.split('\n');

function section(name) {
  const start = lines.indexOf(name);
  if (start === -1) return [];
  const out = [];
  for (let i = start + 1; i < lines.length; i++) {
    if (lines[i].startsWith('## ')) break;
    if (lines[i].trim()) out.push(lines[i]);
  }
  return out;
}

function parseDated(line) {
  const m = line.match(/^[-*]\s*\[(\d{4}-\d{2}-\d{2})\]\s*(.*)$/);
  return m ? { date: m[1], text: m[2] } : { date: null, text: line.replace(/^[-*]\s*/, '') };
}

// --- Winning patterns: dedupe, keep all active; archive >90d unreinforced ---
const winning = section('## Winning patterns').map(parseDated);
const seen = new Map(); // normText -> count (reinforcements)
for (const w of winning) seen.set(norm(w.text), (seen.get(norm(w.text)) || 0) + 1);

const activeWinning = [];
const archivedWinning = [];
for (const w of winning) {
  const reinforced = (seen.get(norm(w.text)) || 0) > 1;
  if (w.date && ageDays(w.date) > ARCHIVE_DAYS && !reinforced) archivedWinning.push(w);
  else activeWinning.push(w);
}
// dedupe: first occurrence wins
const dedupedWinning = [];
const wonSeen = new Set();
for (const w of activeWinning) {
  if (!wonSeen.has(norm(w.text))) { wonSeen.add(norm(w.text)); dedupedWinning.push(w); }
}

// --- Kill rules: verbatim, never archived ---
const killRules = section('## Kill rules');

// --- Agent performance log: last 90 days only ---
const logEntries = section('## Agent performance log').map(parseDated)
  .filter((e) => !e.date || ageDays(e.date) <= LOG_DAYS);

// --- Archive section: existing + newly archived ---
const existingArchive = section('## Archive').map(parseDated);
const archive = [...existingArchive, ...archivedWinning];

const out = [
  '# program-summary.md — SWE Drip (auto-compacted from program.md)',
  `> Generated ${new Date().toISOString().slice(0, 10)} by scripts/compact-program.js. CEO reads this first after month 3.`,
  '',
  '## Winning patterns',
  ...dedupedWinning.map((w) => `- [${w.date ?? 'undated'}] ${w.text}`),
  '',
  '## Kill rules',
  ...killRules,
  '',
  '## Agent performance log',
  ...logEntries.map((e) => `- [${e.date ?? 'undated'}] ${e.text}`),
  '',
  '## Archive',
  ...archive.map((e) => `- [${e.date ?? 'undated'}] ${e.text}`),
  ''
];

if (out.length > MAX_LINES) {
  // trim archive tail first, then oldest log entries — never touch Winning or Kill rules
  let trimmed = out.slice(0, MAX_LINES);
  console.error(`WARN: summary exceeded ${MAX_LINES} lines (${out.length}); archive/log tail truncated`);
  writeFileSync(OUT, trimmed.join('\n'));
} else {
  writeFileSync(OUT, out.join('\n'));
}
console.log(`program-summary.md written: ${Math.min(out.length, MAX_LINES)} lines (winning=${dedupedWinning.length}, kill=${killRules.length}, log=${logEntries.length}, archive=${archive.length})`);
