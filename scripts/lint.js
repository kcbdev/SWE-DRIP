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

if (errors > 0) {
  console.error(`\nlint: ${errors} error(s)`);
  process.exit(1);
} else {
  console.log('\nlint: all docs OK');
}
