#!/usr/bin/env node
import mermaid from '/opt/homebrew/lib/node_modules/@slidev/cli/node_modules/mermaid/dist/mermaid.esm.mjs';
import { writeFileSync, mkdirSync, readFileSync, statSync } from 'fs';
import { dirname } from 'path';

// Inject jsdom polyfill for document/window
import { JSDOM } from 'jsdom';
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', { url: 'http://localhost' });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.navigator = dom.window.navigator;
globalThis.location = dom.window.location;
globalThis.URL = dom.window.URL;
globalThis.CSS = dom.window.CSS;

const args = process.argv.slice(2);
let mermaidSrc = args[0] || '';
let outPath = args[1] || '/Users/Yoo/SVN/00.GITHUB/ComsumableManager/docs/RebuildShelf/mermaid_seq.svg';

if (!mermaidSrc) {
  mermaidSrc = readFileSync(args[0] || '/tmp/mermaid_block_1.mmd', 'utf-8').trim();
}

mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  securityLevel: 'loose',
  fontFamily: '"PingFang SC", "Microsoft YaHei", sans-serif'
});

try {
  const { svg } = await mermaid.render('test-render-' + Date.now(), mermaidSrc);
  const dir = dirname(outPath);
  try { mkdirSync(dir, { recursive: true }); } catch {}
  writeFileSync(outPath, svg);
  console.log('SUCCESS: SVG generated');
  console.log('Size:', statSync(outPath).size, 'bytes');
} catch (e) {
  console.error('Mermaid render error:', e.message);
  console.error(e);
  process.exit(1);
}
