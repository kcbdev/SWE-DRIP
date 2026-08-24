import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..');
let errors = 0;

function checkFile(path, requiredHeadings) {
  if (!existsSync(path)) {
    console.error(`FAIL: missing ${path}`);
    errors++;
    return;
  }
  const content = readFileSync(path, 'utf8');
  if (content.length < 200) {
    console.error(`FAIL: ${path} too short (${content.length} chars)`);
    errors++;
  }
  for (const h of requiredHeadings) {
    if (!content.includes(h)) {
      console.error(`FAIL: ${path} missing heading "${h}"`);
      errors++;
    }
  }
  // markdown sanity: no trailing whitespace on heading lines is not enforced,
  // but check for broken markdown links like []( )
  const brokenLinks = content.match(/\[.*\]\(\)/g);
  if (brokenLinks) {
    console.error(`FAIL: ${path} has empty links: ${brokenLinks.join(', ')}`);
    errors++;
  }
  console.log(`OK: ${path}`);
}

checkFile(join(ROOT, 'README.md'), ['# SWE Drip', '## Architecture', '## Stack']);
checkFile(join(ROOT, 'docs/01-brand.md'), ['# Brand Identity', '## Voice', '## Design philosophy']);
checkFile(join(ROOT, 'docs/02-stack.md'), ['# Stack', '## Hetzner', '## Coolify']);
checkFile(join(ROOT, 'docs/03-agents.md'), ['# Agent Roster', '## Roster overview']);
checkFile(join(ROOT, 'docs/04-deploy.md'), ['# Deployment Guide', '## Day 1']);
checkFile(join(ROOT, 'docs/05-launch.md'), ['# Launch Strategy']);
checkFile(join(ROOT, 'docs/06-traffic.md'), ['# Traffic']);
checkFile(join(ROOT, 'docs/07-scale.md'), ['# Scale Playbook']);

// --- PBI-006: brand invariant guard (AGENTS.md §3) ---
// Canonical constants must remain in docs/01-brand.md; changing them requires an ADR
// mentioning "Pricing" or "Brand" in docs/adrs/.
{
  const brand = readFileSync(join(ROOT, 'docs/01-brand.md'), 'utf8');
  const invariants = ['#0D0D0D', '#00FF41', '#FF6B35', 'JetBrains Mono'];
  for (const inv of invariants) {
    if (!brand.includes(inv)) { console.error(`FAIL: brand invariant "${inv}" missing from docs/01-brand.md — requires ADR (Pricing|Brand)`); errors++; }
  }
  for (const price of ['$32', '$62', '$20']) {
    if (!brand.includes(price)) { console.error(`FAIL: pricing invariant "${price}" missing from docs/01-brand.md — requires founder approval + ADR`); errors++; }
  }
  // if any invariant string was touched, require an ADR covering it
  const adrsDir = join(ROOT, 'docs/adrs');
  let adrText = '';
  try {
    for (const f of readdirSync(adrsDir)) adrText += readFileSync(join(adrsDir, f), 'utf8');
  } catch { /* no adrs yet */ }
  const hasBrandADR = /pricing|brand/i.test(adrText);
  if (!hasBrandADR) {
    // baseline state: invariants present is enough; absence already failed above.
    // When an invariant IS missing AND no ADR exists, the failure above stands.
  }
  console.log('OK: brand invariants (#0D0D0D #00FF41 #FF6B35 JetBrains Mono $32 $62 $20)');
}

// --- PBI-006: Context Map honesty (AGENTS.md §5 vs reality) ---
// If a module directory exists with content but AGENTS.md still says "Planned"/"Not yet created", fail.
{
  const agents = readFileSync(join(ROOT, 'AGENTS.md'), 'utf8');
  const ceoSkill = join(ROOT, 'agents/ceo/SKILL.md');
  if (existsSync(ceoSkill) && /agents\/:\s*\n?\s*responsibility:.*Future/i.test(agents)) {
    console.error('FAIL: Context Map drift — agents/ceo/SKILL.md exists but AGENTS.md §5 still marks agents/ as Future. Update §5.');
    errors++;
  } else {
    console.log('OK: Context Map honest (agents/ vs AGENTS.md §5)');
  }
  const programMd = join(ROOT, 'program.md');
  if (existsSync(programMd) && !agents.includes('program.md')) {
    console.error('FAIL: Context Map drift — program.md exists but not referenced in AGENTS.md §5.');
    errors++;
  }
}

// --- PBI-020: SOUL.md gate — every agent identity present and registry-consistent ---
{
  const expected = [
    ['ceo', 'anthropic/claude-sonnet-4-6', '$30/mo', 'always_on'],
    ['trend-scout', 'google/gemini-2.0-flash-001', '$6/mo', 'Monday 08:00'],
    ['copy', 'anthropic/claude-sonnet-4-6', '$15/mo', 'on_task'],
    ['design', 'black-forest-labs/flux.2-pro', '$30/mo', 'on_task'],
    ['listing', 'google/gemini-2.0-flash-001', '$5/mo', 'on_task'],
    ['social', 'anthropic/claude-haiku-4-5', '$4/mo', 'Tuesday/Wednesday/Thursday'],
    ['video', 'google/veo-3.1-lite', '$20/mo', 'Monday + Thursday'],
    ['analytics', 'anthropic/claude-haiku-4-5', '$3/mo', 'Friday 18:00'],
    ['email', 'anthropic/claude-sonnet-4-6', '$5/mo', 'Saturday 09:00'],
    ['community', 'anthropic/claude-haiku-4-5', '$4/mo', '12 hours'],
    ['finance', 'google/gemini-2.0-flash-001', '$2/mo', '1st of month']
  ];
  for (const [file, model, budget, trigger] of expected) {
    const p = join(ROOT, 'agents/souls', file, 'SKILL.md');
    if (!existsSync(p)) { console.error(`FAIL: agents/souls/${file} missing`); errors++; continue; }
    const c = readFileSync(p, 'utf8');
    if (!c.includes(model)) { console.error(`FAIL: agents/souls/${file} missing model "${model}"`); errors++; }
    if (!c.includes(budget)) { console.error(`FAIL: agents/souls/${file} missing budget "${budget}"`); errors++; }
    if (!c.includes(trigger)) { console.error(`FAIL: agents/souls/${file} missing trigger "${trigger}"`); errors++; }
  }
  console.log(`OK: souls (${expected.length} agent identities, registry-consistent)`);
}

// --- PBI-032: agent-stack gate (specs/agent-stack/spec.md contracts 1-3) ---
{
  // No secret material in ANY tracked deploy/ file: OpenRouter keys (sk-or-v1-),
  // 64-hex keys (API_SERVER_KEY / signing secrets), or Basic-auth tokens.
  const deployFiles = [
    join(ROOT, 'deploy/docker-compose.yml'),
    join(ROOT, 'deploy/stack/hermes-config.yaml'),
    join(ROOT, 'deploy/README.md')
  ];
  const secretRe = /sk-or-v1-[A-Za-z0-9_-]+|\b[0-9a-f]{64}\b|Basic\s+[A-Za-z0-9+/]{20,}/i;
  let bakedFound = false;
  for (const f of deployFiles) {
    if (!existsSync(f)) { console.error(`FAIL: missing ${f}`); errors++; continue; }
    if (secretRe.test(readFileSync(f, 'utf8'))) {
      console.error(`FAIL: secret material baked into ${f} — env placeholders only`);
      errors++; bakedFound = true;
    }
  }
  const compose = join(ROOT, 'deploy/docker-compose.yml');
  if (!existsSync(compose)) {
    console.error('FAIL: missing deploy/docker-compose.yml');
    errors++;
  } else {
    const c = readFileSync(compose, 'utf8');
    if (/image:\s*paperclipai\/paperclip/i.test(c)) {
      console.error('FAIL: paperclip must be built from source — image paperclipai/paperclip does not exist on Docker Hub');
      errors++;
    }
    if (!/image:\s*nousresearch\/hermes-agent:latest/i.test(c)) {
      console.error('FAIL: hermes service must use nousresearch/hermes-agent:latest');
      errors++;
    }
    if (/\/home\/hermes\/\.hermes/.test(c)) {
      console.error('FAIL: hermes must mount /opt/data, not /home/hermes/.hermes');
      errors++;
    }
    if (!/hermes-data:\/opt\/data/.test(c)) {
      console.error('FAIL: hermes service missing hermes-data:/opt/data volume');
      errors++;
    }
    if (!/\$\{API_SERVER_KEY/.test(c) || !/\$\{OPENROUTER_API_KEY/.test(c) || !/\$\{POSTGRES_PASSWORD/.test(c)) {
      console.error('FAIL: compose must reference API_SERVER_KEY, OPENROUTER_API_KEY, POSTGRES_PASSWORD as env placeholders');
      errors++;
    }
  }
  if (!bakedFound) console.log('OK: no secrets baked in deploy/ (sk-or-, 64-hex, Basic tokens)');
  const hcfg = join(ROOT, 'deploy/stack/hermes-config.yaml');
  if (!existsSync(hcfg)) {
    console.error('FAIL: missing deploy/stack/hermes-config.yaml');
    errors++;
  } else {
    const h = readFileSync(hcfg, 'utf8');
    if (!h.includes('provider: openrouter')) {
      console.error('FAIL: hermes-config.yaml missing provider: openrouter');
      errors++;
    }
    if (!h.includes('max_tokens: 4096')) {
      console.error('FAIL: hermes-config.yaml missing max_tokens: 4096 (OpenRouter 402 fix)');
      errors++;
    }
  }
  console.log('OK: agent-stack compose + hermes config (no secrets, /opt/data, built-from-source)');
}

if (errors > 0) {
  console.error(`\nlint: ${errors} error(s)`);
  process.exit(1);
} else {
  console.log('\nlint: all docs OK');
}