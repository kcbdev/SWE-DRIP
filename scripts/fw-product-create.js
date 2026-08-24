// PBI-036: Fourthwall product-creation — corrected upload flow (403 root cause fixed).
// Usage:
//   FW_USERNAME=<api-user> FW_PASSWORD=<api-password> node scripts/fw-product-create.js \
//     --image docs/swe-drip-logos/logo-icon.png \
//     --name "EXIT 0 — Terminal Tee (draft)" \
//     --description "Terminal-green JetBrains Mono 'exit 0' on void black." \
//     --template pro_e25ZKMLjSGa_FCzF8D_z_Q --region front
// Creates a HIDDEN draft (publishOnCreate=false). No secrets baked — env only.
//
// The 403 that previously blocked product creation had two root causes:
//  1. The presigned PUT must echo TWO signed headers: Content-Type (== the
//     contentType declared to /media/upload-url) and
//     `x-goog-content-length-range: 0,<size>` where <size> is the EXACT byte
//     count also sent in the upload-url request body (`size` field). Wrong or
//     missing -> GCS `403 SignatureDoesNotMatch`.
//  2. POST /media/images REQUIRES width + height (pixel dims) in the FIRST
//     registration call, and registration CONSUMES the uploaded tmp file
//     (second registration of the same fileUrl -> 404 MEDIA_FILE_DO_NOT_EXISTS).

import { readFileSync, statSync } from 'node:fs';
import https from 'node:https';
import zlib from 'node:zlib';

const args = Object.fromEntries(process.argv.slice(2).map((a, i, arr) => {
  if (a.startsWith('--')) return [a.slice(2), arr[i + 1]];
  return null;
}).filter(Boolean));

const imagePath = args.image;
const name = args.name;
const description = args.description || '';
const templateId = args.template;
const region = args.region || 'front';
const publishOnCreate = args.publish === 'true';

if (!imagePath || !name || !templateId) {
  console.error('usage: FW_USERNAME=.. FW_PASSWORD=.. node scripts/fw-product-create.js --image <png> --name <n> --template <id> [--region front] [--publish true]');
  process.exit(2);
}
if (!process.env.FW_USERNAME || !process.env.FW_PASSWORD) {
  console.error('set FW_USERNAME + FW_PASSWORD (Fourthwall API user) — never bake credentials');
  process.exit(2);
}

const AUTH = 'Basic ' + Buffer.from(`${process.env.FW_USERNAME}:${process.env.FW_PASSWORD}`).toString('base64');
const img = readFileSync(imagePath);
const size = statSync(imagePath).size;
if (img.slice(0, 8).toString('hex') !== '89504e470d0a1a0a') { console.error('image must be a PNG'); process.exit(2); }
const width = img.readUInt32BE(16);
const height = img.readUInt32BE(20);

function raw(hostname, path, method, body, headers = {}) {
  return new Promise((resolve) => {
    const h = { ...headers };
    if (body !== undefined) h['Content-Length'] = Buffer.byteLength(body);
    const r = https.request({ hostname, path, method, headers: h }, resp => {
      const chunks = [];
      resp.on('data', c => chunks.push(c));
      resp.on('end', () => {
        const rawBuf = Buffer.concat(chunks);
        const buf = (resp.headers['content-encoding'] || '').includes('gzip') ? zlib.gunzipSync(rawBuf) : rawBuf;
        resolve({ status: resp.statusCode, data: buf.toString() });
      });
    });
    r.on('error', e => resolve({ status: 0, data: e.message }));
    if (body !== undefined) r.write(body);
    r.end();
  });
}
const api = (path, method, body, headers) => raw('api.fourthwall.com', path, method, body, { Accept: 'application/json', Authorization: AUTH, ...headers });

// 1. presigned URL — `size` is REQUIRED and signed into the URL
const up = JSON.parse((await api('/open-api/v1.0/media/upload-url', 'POST', JSON.stringify({ fileName: imagePath.split(/[\\/]/).pop(), contentType: 'image/png', size }), { 'Content-Type': 'application/json' })).data);
if (!up.uploadUrl) { console.error('upload-url failed:', JSON.stringify(up)); process.exit(1); }

// 2. PUT the bytes, echoing BOTH signed headers (Content-Type + x-goog-content-length-range)
const u = new URL(up.uploadUrl);
const put = await raw(u.hostname, u.pathname + u.search, 'PUT', img, { 'Content-Type': 'image/png', 'x-goog-content-length-range': `0,${size}` });
if (put.status !== 200) { console.error('GCS PUT failed:', put.status, put.data.slice(0, 200)); process.exit(1); }

// 3. register — FIRST call carries width+height (registration consumes the tmp file)
const reg = JSON.parse((await api('/open-api/v1.0/media/images', 'POST', JSON.stringify({ fileUrl: up.fileUrl, width, height }), { 'Content-Type': 'application/json' })).data);
if (!reg.id) { console.error('media register failed:', JSON.stringify(reg)); process.exit(1); }

// 4. create the product (hidden draft unless --publish true)
const productBody = {
  type: 'design',
  productTemplateId: templateId,
  name,
  description,
  regions: [{ region, imageId: String(reg.id), placementStrategy: 'AUTO' }],
  publishOnCreate
};
const pr = await api('/open-api/v1.0/products', 'POST', JSON.stringify(productBody), { 'Content-Type': 'application/json' });
if (pr.status !== 201) { console.error('product create failed:', pr.status, pr.data.slice(0, 300)); process.exit(1); }
const product = JSON.parse(pr.data);
console.log('DRAFT PRODUCT CREATED:', product.productId, '| customization:', product.customizationId, '| mockups:', product.images.length);
for (const im of product.images) console.log('  mockup:', im.region, im.style, im.color, `${im.width}x${im.height}`);