// PBI-032: offline contract checks for the working agent stack (specs/agent-stack/spec.md).
// These run in CI/local with zero external calls — docker is optional.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..');

test('agent-stack: compose defines postgres, paperclip (built), hermes', () => {
  const p = join(ROOT, 'deploy/docker-compose.yml');
  assert.ok(existsSync(p), 'deploy/docker-compose.yml exists');
  const c = readFileSync(p, 'utf8');
  assert.match(c, /postgres:/);
  assert.match(c, /paperclip:/);
  assert.match(c, /hermes:/);
  assert.match(c, /build:/, 'paperclip is built, not pulled');
  assert.doesNotMatch(c, /image:\s*paperclipai\/paperclip/i, 'no nonexistent paperclip image');
  assert.match(c, /image:\s*nousresearch\/hermes-agent:latest/i, 'hermes image present');
});

test('agent-stack: hermes memory path is /opt/data, not /home/hermes', () => {
  const c = readFileSync(join(ROOT, 'deploy/docker-compose.yml'), 'utf8');
  assert.match(c, /hermes-data:\/opt\/data/, 'hermes state volume at /opt/data');
  assert.doesNotMatch(c, /\/home\/hermes\/\.hermes/, 'no legacy /home/hermes mount');
});

test('agent-stack: no secrets baked into deploy/ files', () => {
  const secretRe = /sk-or-v1-[A-Za-z0-9_-]+|\b[0-9a-f]{64}\b|Basic\s+[A-Za-z0-9+/]{20,}/i;
  for (const f of ['deploy/docker-compose.yml', 'deploy/stack/hermes-config.yaml', 'deploy/README.md']) {
    const c = readFileSync(join(ROOT, f), 'utf8');
    assert.doesNotMatch(c, secretRe, `no secret material in ${f}`);
  }
  const c = readFileSync(join(ROOT, 'deploy/docker-compose.yml'), 'utf8');
  assert.doesNotMatch(c, /sk-or-/, 'no OpenRouter key baked');
  assert.doesNotMatch(c, /a16ac6f/, 'no Hermes gateway key baked');
});

test('agent-stack: secrets referenced as env placeholders', () => {
  const c = readFileSync(join(ROOT, 'deploy/docker-compose.yml'), 'utf8');
  assert.match(c, /\$\{API_SERVER_KEY/, 'API_SERVER_KEY placeholder');
  assert.match(c, /\$\{OPENROUTER_API_KEY/, 'OPENROUTER_API_KEY placeholder');
  assert.match(c, /\$\{POSTGRES_PASSWORD/, 'POSTGRES_PASSWORD placeholder');
  assert.match(c, /\$\{BETTER_AUTH_SECRET/, 'BETTER_AUTH_SECRET placeholder');
});

test('agent-stack: hermes-config.yaml caps tokens + openrouter provider', () => {
  const h = readFileSync(join(ROOT, 'deploy/stack/hermes-config.yaml'), 'utf8');
  assert.match(h, /provider:\s*openrouter/);
  assert.match(h, /max_tokens:\s*4096/, 'token cap fixes OpenRouter 402');
});
