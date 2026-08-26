// Seedream 5.0 Lite generation via sandbase.ai (direct provider — OpenRouter
// flattens seedream to JPEG; sandbase honors output_format).
// Usage: SANDBASE_API_KEY=... node scripts/seedream-gen.js "prompt" out.png
// Proven request shape (founder 2026-08-25): POST https://api.sandbase.ai/v1/run
// { model: "bytedance/seedream/5.0/lite/edit", images?, prompt, aspect_ratio, output_format }
import https from 'node:https';
import { writeFileSync } from 'node:fs';

const KEY = process.env.SANDBASE_API_KEY;
if (!KEY) { console.error('set SANDBASE_API_KEY'); process.exit(2); }
const prompt = process.argv[2];
const outPath = process.argv[3] || 'seedream-out.png';
if (!prompt) { console.error('usage: node scripts/seedream-gen.js "prompt" out.png'); process.exit(2); }

function api(path, method, body) {
  return new Promise((resolve) => {
    const d = JSON.stringify(body);
    const h = { Authorization: `Bearer ${KEY}`, 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(d) };
    const r = https.request({ hostname: 'api.sandbase.ai', path, method, headers: h }, resp => {
      const chunks = [];
      resp.on('data', c => chunks.push(c));
      resp.on('end', () => resolve({ status: resp.statusCode, data: Buffer.concat(chunks).toString() }));
    });
    r.on('error', e => resolve({ status: 0, data: e.message }));
    r.write(d);
    r.end();
  });
}

const body = {
  model: 'bytedance/seedream/5.0/lite/edit',
  prompt: prompt + ' Transparent background (alpha 0 outside the artwork), PNG with alpha channel.',
  aspect_ratio: '1:1',
  output_format: 'png'
};
const r = await api('/v1/run', 'POST', body);
console.log('run →', r.status, r.data.slice(0, 300));
let runId = '';
try { runId = JSON.parse(r.data).id || JSON.parse(r.data).runId || ''; } catch {}
// poll
for (let i = 0; i < 30; i++) {
  await new Promise(res => setTimeout(res, 5000));
  const p = await api('/v1/run/' + runId, 'GET');
  console.log('poll', i, '→', p.status, p.data.slice(0, 200));
  try {
    const j = JSON.parse(p.data);
    const out = j.output || j.result || j.images || j.url;
    if (typeof out === 'string' && /^https?:\/\//.test(out)) {
      // download result
      const img = await new Promise((resolve) => {
        https.get(out, res => { const c = []; res.on('data', x => c.push(x)); res.on('end', () => resolve(Buffer.concat(c))); }).on('error', e => resolve(null));
      });
      if (img) { writeFileSync(outPath, img); console.log('SAVED', outPath, img.length, 'bytes | PNG:', img.slice(0, 8).toString('hex') === '89504e470d0a1a0a', '| colorType:', img[25]); }
      break;
    }
    if (j.status === 'completed' || j.status === 'done' || j.status === 'succeeded') { console.log('completed but no url — raw:', p.data.slice(0, 300)); break; }
  } catch {}
}