// Pure-Node PNG transparentizer for black-background designs.
// Decodes truecolor RGB PNG, keys the background out (alpha = luminance so
// anti-aliased green text edges stay crisp), re-encodes as RGBA PNG.
import { inflateSync, deflateSync } from 'node:zlib';
import { readFileSync, writeFileSync } from 'node:fs';

function parsePNG(buf) {
  let off = 8; const chunks = [];
  while (off < buf.length) {
    const len = buf.readUInt32BE(off);
    const type = buf.slice(off + 4, off + 8).toString('ascii');
    chunks.push({ type, data: buf.slice(off + 8, off + 8 + len) });
    off += 12 + len;
  }
  return chunks;
}

function unfilter(scanlines, width, height, bpp) {
  const out = Buffer.alloc(width * height * bpp);
  const stride = width * bpp;
  let pos = 0;
  for (let y = 0; y < height; y++) {
    const f = scanlines[pos]; pos++;
    const line = scanlines.slice(pos, pos + stride); pos += stride;
    for (let x = 0; x < stride; x++) {
      const raw = line[x];
      const left = x >= bpp ? out[(y * stride) + x - bpp] : 0;
      const up = y > 0 ? out[((y - 1) * stride) + x] : 0;
      const ul = (y > 0 && x >= bpp) ? out[((y - 1) * stride) + (x - bpp)] : 0;
      let v;
      switch (f) {
        case 0: v = raw; break;
        case 1: v = raw + left; break;
        case 2: v = raw + up; break;
        case 3: v = raw + ((left + up) >> 1); break;
        case 4: {
          const p = left + up - ul;
          const pa = Math.abs(p - left), pb = Math.abs(p - up), pc = Math.abs(p - ul);
          v = raw + (pa <= pb && pa <= pc ? left : (pb <= pc ? up : ul));
          break;
        }
        default: v = raw;
      }
      out[(y * stride) + x] = v & 0xff;
    }
  }
  return out;
}

function filter(pixels, width, height, bpp) {
  // simple pass-through filter (type 0) — valid PNG, slightly larger
  const stride = width * bpp;
  const out = Buffer.alloc(height * (stride + 1));
  for (let y = 0; y < height; y++) {
    out[y * (stride + 1)] = 0;
    pixels.copy(out, y * (stride + 1) + 1, y * stride, (y + 1) * stride);
  }
  return out;
}

function crc32(buf) {
  let c, crc = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    c = (crc ^ buf[i]) & 0xff;
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    crc = (crc >>> 8) ^ c;
  }
  return (crc ^ 0xffffffff) >>> 0;
}
// note: above crc is wrong (uses table-less per-byte but shifts wrong); use zlib-free table
function makeCRC(buf) {
  const table = [];
  for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = (c & 1) ? 0xedb88320 ^ (c >>> 1) : c >>> 1; table[n] = c >>> 0; }
  let crc = 0xffffffff;
  for (let i = 0; i < buf.length; i++) crc = table[(crc ^ buf[i]) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const td = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(makeCRC(td));
  return Buffer.concat([len, td, crc]);
}

function transparentize(inPath, outPath) {
  const buf = readFileSync(inPath);
  const chunks = parsePNG(buf);
  const ihdr = chunks.find(c => c.type === 'IHDR').data;
  const width = ihdr.readUInt32BE(0), height = ihdr.readUInt32BE(4);
  const bitDepth = ihdr[8], colorType = ihdr[9];
  console.log('input:', width + 'x' + height, 'bit', bitDepth, 'color', colorType);
  if (colorType !== 2 || bitDepth !== 8) throw new Error('only 8-bit RGB supported; got color=' + colorType);
  const raw = Buffer.concat(chunks.filter(c => c.type === 'IDAT').map(c => c.data));
  const scanlines = inflateSync(raw);
  const bpp = 3;
  const rgb = unfilter(scanlines, width, height, bpp);
  // alpha = luminance (black bg -> transparent, bright green text -> opaque)
  const rgba = Buffer.alloc(width * height * 4);
  for (let i = 0; i < width * height; i++) {
    const r = rgb[i * 3], g = rgb[i * 3 + 1], b = rgb[i * 3 + 2];
    const lum = Math.max(r, g, b);
    rgba[i * 4] = r; rgba[i * 4 + 1] = g; rgba[i * 4 + 2] = b; rgba[i * 4 + 3] = lum;
  }
  // encode: new IHDR with color type 6 (RGBA)
  const nIHDR = Buffer.alloc(13);
  nIHDR.writeUInt32BE(width, 0); nIHDR.writeUInt32BE(height, 4);
  nIHDR[8] = 8; nIHDR[9] = 6; nIHDR[10] = 0; nIHDR[11] = 0; nIHDR[12] = 0;
  const idat = deflateSync(filter(rgba, width, height, 4));
  const out = Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', nIHDR),
    chunk('IDAT', idat),
    chunk('IEND', Buffer.alloc(0))
  ]);
  writeFileSync(outPath, out);
  console.log('saved:', outPath, out.length, 'bytes | alpha-backed RGBA');
}

const [inPath, outPath] = process.argv.slice(2);
if (!inPath || !outPath) { console.error('usage: node scripts/png-transparent.js in.png out.png'); process.exit(2); }
transparentize(inPath, outPath);
