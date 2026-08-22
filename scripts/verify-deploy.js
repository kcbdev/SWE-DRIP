#!/usr/bin/env node
// PBI-004: offline deployment-contract checks — Dockerfile / nginx.conf / .coolify/app.json
// Live probes belong to tests/deployment.test.js (skips offline). This script never needs network.
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..');
let errors = 0;
const ok = (m) => console.log(`OK: ${m}`);
const fail = (m) => { console.error(`FAIL: ${m}`); errors++; };

const df = join(ROOT, 'Dockerfile');
if (!existsSync(df)) fail('Dockerfile missing');
else {
  const c = readFileSync(df, 'utf8');
  c.includes('FROM node:22-alpine AS builder') ? ok('builder stage') : fail('builder node:22-alpine missing');
  c.includes('FROM nginx:alpine') ? ok('runtime nginx:alpine') : fail('runtime nginx:alpine missing');
  c.includes('EXPOSE 80') ? ok('EXPOSE 80') : fail('EXPOSE 80 missing');
  c.includes('127.0.0.1/health') ? ok('healthcheck targets 127.0.0.1 (IPv6-safe)') : fail('healthcheck must target 127.0.0.1/health');
  /openrouter|fourthwall|telegram|plane_api|loops|buffer/i.test(c) ? fail('secret string in Dockerfile') : ok('no secrets baked');
}

const ng = join(ROOT, 'nginx.conf');
if (!existsSync(ng)) fail('nginx.conf missing');
else {
  const c = readFileSync(ng, 'utf8');
  c.includes('listen 80') && c.includes('listen [::]:80') ? ok('dual-stack listen 80') : fail('dual-stack listen missing');
  c.includes('location = /health') ? ok('/health location') : fail('/health location missing');
  c.includes('"status":"ok"') || c.includes("'status':'ok'") ? ok('health json') : fail('health json missing');
}

const appJsonPath = join(ROOT, '.coolify/app.json');
if (!existsSync(appJsonPath)) fail('.coolify/app.json missing');
else {
  try {
    const j = JSON.parse(readFileSync(appJsonPath, 'utf8'));
    j.server?.uuid === 'e4cowswcks844wow04c084wg' ? ok('server kcb') : fail('server kcb uuid mismatch');
    j.application?.domains?.includes('https://swedrip.kcb.ma') ? ok('domain swedrip.kcb.ma') : fail('swedrip domain missing in app.json');
    j.paperclip?.application?.fqdn === 'https://paperclip.kcb.ma' ? ok('paperclip fqdn captured') : fail('paperclip entry missing');
    j.application?.git_repository === 'https://github.com/kcbdev/SWE-DRIP' ? ok('git repo kcbdev/SWE-DRIP') : fail('git repo wrong in app.json');
  } catch (e) { fail('app.json invalid JSON: ' + e.message); }
}

if (errors) { console.error(`\nverify-deploy: ${errors} error(s)`); process.exit(1); }
console.log('\nverify-deploy: all deployment contracts OK');
