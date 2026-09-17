#!/usr/bin/env node
/*
 * KLK-136 実効果テスト（tester所有・Node.js標準＋ヘッドレス Chrome＋ブリッジ実起動）
 *
 * 「既定以外のポートで起動しても、画面がブリッジを見つけるか」を実際に確かめる。
 * 文字列の一致ではなく、**空きポートでブリッジを立て、ブラウザで開いて読み込ませる**。
 *
 *   E1 ★既定以外のポートで、画面がブリッジを見つける（/health が通り稼働と判定される）
 *   E2 ★既定以外のポートで、実績カタログを実際に読み込む（参考素材のカードが出る）
 *   E3 画面の接続先が配信元と一致している（location.origin を使っている）
 *   E4 ★8765 を一度も叩いていない（決め打ちが残っていない）
 *
 * ★カタログの実データが要る（catalog/img）。無ければ SKIP。
 *
 * 実行: KLK_E2E_CHROME=<chrome のパス> node tests/site/e2e_klk136.node.js
 * 終了コード: 0=全PASS / 1=FAILあり / 2=ハーネス異常 / 3=環境理由でSKIP
 */
'use strict';
const { spawn } = require('node:child_process');
const net = require('node:net');
const path = require('node:path');
const fs = require('node:fs');

const ROOT = path.join(__dirname, '..', '..');
const IMG_DIR = path.join(ROOT, 'catalog', 'img');
const CHROME = process.env.KLK_E2E_CHROME
  || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium']
    .find(p => fs.existsSync(p));
if (!CHROME || !fs.existsSync(CHROME)) { console.log('SKIP: ヘッドレス Chrome が見つかりません'); process.exit(3); }
if (!fs.existsSync(IMG_DIR) || fs.readdirSync(IMG_DIR).length < 5) {
  console.log('SKIP: 実績カタログの画像がありません（catalog/ は Git 管理外）'); process.exit(3);
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

const results = [];
const check = (name, ok, detail) => results.push([name, !!ok, detail || '']);

(async () => {
  let bridge, chrome;
  try {
    // ★既定の 8765 ではないポートで起動する。ここが本チケットの主題
    const bp = await freePort();
    if (bp === 8765) { console.log('SKIP: 空きポートがたまたま既定と同じでした'); process.exit(3); }
    const shim = fs.mkdtempSync('/tmp/klk136-shim-');
    for (const n of ['open', 'xdg-open']) { fs.writeFileSync(path.join(shim, n), '#!/bin/sh\nexit 0\n'); fs.chmodSync(path.join(shim, n), 0o755); }
    bridge = spawn('python3', [path.join(ROOT, 'draft-gen', 'bridge.py')],
      { env: { ...process.env, KLK_BRIDGE_PORT: String(bp), PATH: shim + ':' + process.env.PATH }, stdio: 'ignore', cwd: ROOT });
    if (!await waitHttp(`http://127.0.0.1:${bp}/health`)) { console.log('SKIP: ブリッジが起動できません'); process.exit(3); }

    const debugPort = await freePort();
    const profile = fs.mkdtempSync('/tmp/klk136-chrome-');
    chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', `--remote-debugging-port=${debugPort}`,
      `--user-data-dir=${profile}`, '--window-size=1400,1200', 'about:blank'], { stdio: 'ignore' });
    if (!await waitHttp(`http://127.0.0.1:${debugPort}/json/version`)) { console.error('[HARNESS ERROR] Chrome CDP が起きない'); process.exit(2); }

    const t = await (await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, { method: 'PUT' })).json();
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    await new Promise((res, rej) => {
      const to = setTimeout(() => rej(new Error('CDP の WebSocket が開かない')), 20000);
      ws.addEventListener('open', () => { clearTimeout(to); res(); });
      ws.addEventListener('error', () => { clearTimeout(to); rej(new Error('CDP の WebSocket でエラー')); });
    });
    let id = 0; const pend = new Map();
    ws.addEventListener('message', ev => {
      const m = JSON.parse(ev.data);
      if (m.id && pend.has(m.id)) { const { res, rej } = pend.get(m.id); pend.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
    });
    const send = (method, params = {}) => new Promise((res, rej) => { const i = ++id; pend.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
    await send('Page.enable'); await send('Runtime.enable');

    // ★画面が実際に叩いた URL を記録する。8765 を叩いていないことまで見る（E4）
    await send('Page.addScriptToEvaluateOnNewDocument', {
      source: '(()=>{window.__hits=[];const o=window.fetch;window.fetch=function(){'
            + 'try{window.__hits.push(String((arguments[0]&&arguments[0].url)||arguments[0]||""));}catch(e){}'
            + 'return o.apply(this,arguments);};})();',
    });
    await send('Page.navigate', { url: `http://127.0.0.1:${bp}/` });
    await sleep(6000);
    const ev = async e => (await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true })).result.value;

    const alive = await ev('typeof catalogAlive === "undefined" ? null : catalogAlive');
    check('E1 ★既定以外のポートで、画面がブリッジを見つける',
      alive === true, `catalogAlive=${alive} / ポート=${bp}`);

    const entries = await ev('typeof catalogEntries === "undefined" ? -1 : catalogEntries.length');
    const cards = await ev('document.querySelectorAll("#thumbs .thumb").length');
    check('E2 ★既定以外のポートで、実績カタログを実際に読み込む',
      entries > 0 && cards > 0, `読み込み件数=${entries} / 参考素材のカード=${cards}`);

    const origin = await ev('BRIDGE_ORIGIN');
    check('E3 接続先が配信元と一致している（location.origin を使っている）',
      origin === `http://127.0.0.1:${bp}`, `BRIDGE_ORIGIN=${origin} / 配信元=http://127.0.0.1:${bp}`);

    const hits = await ev('JSON.stringify(window.__hits || [])');
    const stray = JSON.parse(hits || '[]').filter(u => u.indexOf(':8765') >= 0);
    check('E4 ★8765 を一度も叩いていない（決め打ちが残っていない）',
      stray.length === 0, `8765 への要求=${stray.length}件 ${stray.slice(0, 2).join(' ')}`);

    ws.close();
  } catch (e) {
    console.error('[HARNESS ERROR] ' + (e && e.stack || e));
    process.exit(2);
  } finally {
    try { bridge && bridge.kill(); } catch {}
    try { chrome && chrome.kill(); } catch {}
  }

  console.log('KLK-136 実効果（既定以外のポートで画面がブリッジを見つける）');
  let failed = 0;
  for (const [name, ok, detail] of results) {
    if (!ok) failed++;
    console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}`);
    console.log(`        ${detail}`);
  }
  console.log(`${results.length} checks, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
