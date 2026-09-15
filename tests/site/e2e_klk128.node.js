#!/usr/bin/env node
/*
 * KLK-128 実効果テスト（tester所有・Node.js標準＋ヘッドレス Chrome＋ブリッジ実起動）
 *
 * 「一覧が軽くなったか」を、**実際に読み込まれた画像の画素数**で確かめる。
 * 文字列の一致ではなく、ブラウザが展開したメモリ量そのものを見る。
 *
 *   E1 ★一覧がサムネイルを使う（実際に読み込まれた URL で確かめる）
 *   E2 ★展開メモリが原寸より1桁小さい（同じ画面で**両方測って比べる**）
 *   E3 拡大（🔍）は原寸のまま
 *   E4 ★サムネイルが無いときは原寸で出る（実際に 404 にして確かめる）
 *   E5 ★原寸も出せないときは黙らない（何件出せなかったかを画面に出す）
 *   E6 実績カタログ画面（SCR-004）の一覧もサムネイルを使う
 *
 * ★カタログの実データが要る（catalog/img と catalog/thumb）。無ければ SKIP。
 *
 * 実行: KLK_E2E_CHROME=<chrome のパス> node tests/site/e2e_klk128.node.js
 * 終了コード: 0=全PASS / 1=FAILあり / 2=ハーネス異常 / 3=環境理由でSKIP
 */
'use strict';
const { spawn } = require('node:child_process');
const net = require('node:net');
const path = require('node:path');
const fs = require('node:fs');

const ROOT = path.join(__dirname, '..', '..');
const IMG_DIR = path.join(ROOT, 'catalog', 'img');
const THUMB_DIR = path.join(ROOT, 'catalog', 'thumb');
const CHROME = process.env.KLK_E2E_CHROME
  || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium']
    .find(p => fs.existsSync(p));
if (!CHROME || !fs.existsSync(CHROME)) { console.log('SKIP: ヘッドレス Chrome が見つかりません'); process.exit(3); }
if (!fs.existsSync(IMG_DIR) || fs.readdirSync(IMG_DIR).length < 5) {
  console.log('SKIP: 実績カタログの画像がありません（catalog/ は Git 管理外）'); process.exit(3);
}
if (!fs.existsSync(THUMB_DIR) || fs.readdirSync(THUMB_DIR).length < 5) {
  console.log('SKIP: サムネイルが未生成（python3 tools/make-catalog-thumbs.py）'); process.exit(3);
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
function freePort() {
  return new Promise((res, rej) => {
    const s = net.createServer(); s.unref();
    s.on('error', rej);
    s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
  });
}
async function waitHttp(url, tries = 100) {
  for (let i = 0; i < tries; i++) { try { const r = await fetch(url); if (r.ok) return true; } catch {} await sleep(150); }
  return false;
}
function openWs(ws, ms = 20000) {
  return new Promise((res, rej) => {
    const to = setTimeout(() => rej(new Error('CDP の WebSocket が ' + ms + 'ms で開きませんでした')), ms);
    ws.addEventListener('open', () => { clearTimeout(to); res(); });
    ws.addEventListener('error', () => { clearTimeout(to); rej(new Error('CDP の WebSocket でエラー')); });
    ws.addEventListener('close', () => { clearTimeout(to); rej(new Error('CDP の WebSocket が閉じられました')); });
  });
}

const results = [];
const check = (name, ok, detail) => results.push([name, !!ok, detail || '']);

// 1タブぶんの道具立て。blockThumbs を真にすると /catalog/thumb/ を実際に 404 にする。
async function openTab(debugPort, url, opts) {
  opts = opts || {};
  const t = await (await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, { method: 'PUT' })).json();
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await openWs(ws);
  let id = 0; const pend = new Map();
  const state = { blocked: 0 };
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { const { res, rej } = pend.get(m.id); pend.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); return; }
    if (m.method === 'Fetch.requestPaused') {
      const u = m.params.request.url;
      const kill = (opts.blockThumbs && u.indexOf('/catalog/thumb/') >= 0)
                || (opts.blockAll && u.indexOf('/catalog/') >= 0 && u.indexOf('.json') < 0);
      if (kill) { state.blocked++; send('Fetch.failRequest', { requestId: m.params.requestId, errorReason: 'Failed' }); }
      else { send('Fetch.continueRequest', { requestId: m.params.requestId }); }
    }
  });
  const send = (method, params = {}) => new Promise((res, rej) => { const i = ++id; pend.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
  await send('Page.enable'); await send('Runtime.enable');
  if (opts.blockThumbs || opts.blockAll) {
    await send('Fetch.enable', { patterns: [{ urlPattern: '*/catalog/*' }] });
  }
  await send('Emulation.setDeviceMetricsOverride', { width: 1400, height: 1200, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url });
  const ev = async e => (await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true })).result.value;
  return { send, ev, state, close: async () => { ws.close(); await fetch(`http://127.0.0.1:${debugPort}/json/close/${t.id}`); } };
}

// 一覧の実測（読み込み済みだけを数える）
const MEASURE = `(() => {
  const im = Array.from(document.querySelectorAll('#thumbs img.shot'));
  const loaded = im.filter(i => i.complete && i.naturalWidth > 0);
  let px = 0, thumb = 0, full = 0;
  loaded.forEach(i => { px += i.naturalWidth * i.naturalHeight;
    (i.currentSrc.indexOf('/catalog/thumb/') >= 0 ? thumb++ : full++); });
  const note = document.getElementById('thumbNote');
  return JSON.stringify({
    cards: document.querySelectorAll('#thumbs .thumb').length,
    imgs: im.length, loaded: loaded.length, thumb: thumb, full: full,
    mb: Math.round(px * 4 / 1048576),
    note: (note && note.style.display !== 'none') ? note.textContent : '',
  });
})()`;

(async () => {
  let bridge, chrome;
  try {
    const bp = await freePort();
    const shim = fs.mkdtempSync('/tmp/klk128-shim-');
    for (const n of ['open', 'xdg-open']) { fs.writeFileSync(path.join(shim, n), '#!/bin/sh\nexit 0\n'); fs.chmodSync(path.join(shim, n), 0o755); }
    bridge = spawn('python3', [path.join(ROOT, 'draft-gen', 'bridge.py')],
      { env: { ...process.env, KLK_BRIDGE_PORT: String(bp), PATH: shim + ':' + process.env.PATH }, stdio: 'ignore', cwd: ROOT });
    if (!await waitHttp(`http://127.0.0.1:${bp}/health`)) { console.log('SKIP: ブリッジが起動できません'); process.exit(3); }

    const debugPort = await freePort();
    const profile = fs.mkdtempSync('/tmp/klk128-chrome-');
    chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', `--remote-debugging-port=${debugPort}`,
      `--user-data-dir=${profile}`, '--window-size=1400,1200', 'about:blank'], { stdio: 'ignore' });
    if (!await waitHttp(`http://127.0.0.1:${debugPort}/json/version`)) { console.error('[HARNESS ERROR] Chrome CDP が起きない'); process.exit(2); }

    const HOME = `http://127.0.0.1:${bp}/`;

    // ---- 通常（サムネイルあり）
    const a = await openTab(debugPort, HOME);
    await sleep(3000);
    await a.ev(`document.getElementById('thumbs').scrollIntoView()`);
    await sleep(9000);
    const withThumb = JSON.parse(await a.ev(MEASURE));
    check('E1 ★一覧がサムネイルを使う',
      withThumb.loaded > 0 && withThumb.thumb === withThumb.loaded && withThumb.full === 0,
      `${withThumb.loaded}枚読込 サムネ=${withThumb.thumb} 原寸=${withThumb.full}`);

    const zoom = await a.ev(`(() => {
      const z = document.querySelector('#thumbs .thumb .zoom'); if (!z) return 'ボタンなし';
      z.click();
      const i = document.querySelector('#modalImg img');
      return i ? i.getAttribute('src') : 'なし';
    })()`);
    check('E3 拡大（🔍）は原寸のまま',
      typeof zoom === 'string' && zoom.indexOf('/catalog/img/') === 0,
      `拡大の src=${zoom}`);
    await a.close();

    // ---- ★サムネイルを実際に 404 にする（止めたことを先に assert する）
    const b = await openTab(debugPort, HOME, { blockThumbs: true });
    await sleep(3000);
    await b.ev(`document.getElementById('thumbs').scrollIntoView()`);
    await sleep(14000);
    const noThumb = JSON.parse(await b.ev(MEASURE));
    check('E4 ★サムネイルが無いときは原寸で出る（実際に 404 にして確認）',
      b.state.blocked > 0 && noThumb.loaded > 0
      && noThumb.full === noThumb.loaded && noThumb.thumb === 0,
      `止めた件数=${b.state.blocked} ${noThumb.loaded}枚読込 原寸=${noThumb.full}`);

    check('E2 ★展開メモリが原寸より1桁小さい',
      withThumb.loaded > 0 && noThumb.loaded > 0
      && withThumb.mb * 5 < noThumb.mb,
      `サムネイル ${withThumb.mb}MB（${withThumb.loaded}枚） / 原寸 ${noThumb.mb}MB（${noThumb.loaded}枚）`);
    await b.close();

    // ---- ★原寸も出せないとき、黙らない
    const c = await openTab(debugPort, HOME, { blockAll: true });
    await sleep(3000);
    await c.ev(`document.getElementById('thumbs').scrollIntoView()`);
    await sleep(12000);
    const dead = JSON.parse(await c.ev(MEASURE));
    check('E5 ★原寸も出せないときは黙らない（件数を画面に出す）',
      c.state.blocked > 0 && dead.loaded === 0
      && dead.note.indexOf('表示できませんでした') >= 0,
      `止めた件数=${c.state.blocked} 注記=${JSON.stringify(dead.note)}`);
    await c.close();

    // ---- 実績カタログ画面
    const d = await openTab(debugPort, `http://127.0.0.1:${bp}/catalog.html`);
    await sleep(7000);
    const cat = JSON.parse(await d.ev(`(() => {
      const im = Array.from(document.querySelectorAll('#grid img'));
      const loaded = im.filter(i => i.complete && i.naturalWidth > 0);
      let thumb = 0, full = 0;
      loaded.forEach(i => { (i.currentSrc.indexOf('/catalog/thumb/') >= 0 ? thumb++ : full++); });
      return JSON.stringify({ loaded: loaded.length, thumb: thumb, full: full });
    })()`));
    check('E6 実績カタログ画面（SCR-004）の一覧もサムネイルを使う',
      cat.loaded > 0 && cat.thumb === cat.loaded && cat.full === 0,
      `${cat.loaded}枚読込 サムネ=${cat.thumb} 原寸=${cat.full}`);
    await d.close();
  } catch (e) {
    console.error('[HARNESS ERROR] ' + (e && e.stack || e));
    process.exitCode = 2;
  } finally {
    try { chrome && chrome.kill(); } catch {}
    try { bridge && bridge.kill(); } catch {}
  }
  if (process.exitCode === 2) process.exit(2);
  let failed = 0;
  console.log('KLK-128 実効果（実ブリッジ→画面→読み込まれた画像の画素数）');
  for (const [name, ok, detail] of results) { if (!ok) failed++; console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? '\n        ' + detail : ''}`); }
  console.log(`${results.length} checks, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
