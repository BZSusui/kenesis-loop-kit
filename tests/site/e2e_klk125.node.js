#!/usr/bin/env node
/*
 * KLK-125 実効果テスト（tester所有・Node.js標準＋ヘッドレス Chrome）
 *
 * 「SCR-001 の行ごとの設定でも、型が日本語ラベル付きで出る」を
 * **実際に描かれた <option> の文字**で確かめる。file:// で開くのでブリッジは要らない。
 *
 *   E1 行の「設定」を開くと型セレクタが出る
 *   E2 ★選択肢が「日本語ラベル（マーカー）」で描かれる
 *   E3 ★option の value はマーカーのまま（生成指示書へ渡る値が変わらない）
 *   E4 先頭は「自動（案ごとに振り分け）」（既存の振る舞いを壊さない）
 *   E5 セクションを変えるとその型が出る（ABOUT と MENU で中身が違う）
 *
 * 実行: KLK_E2E_CHROME=<chrome のパス> node tests/site/e2e_klk125.node.js
 * 終了コード: 0=全PASS / 1=FAILあり / 2=ハーネス異常 / 3=環境理由でSKIP
 */
'use strict';
const { spawn } = require('node:child_process');
const net = require('node:net');
const path = require('node:path');
const fs = require('node:fs');

const ROOT = path.join(__dirname, '..', '..');
const CHROME = process.env.KLK_E2E_CHROME
  || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Chromium.app/Contents/MacOS/Chromium'].find(p => fs.existsSync(p));
if (!CHROME || !fs.existsSync(CHROME)) { console.log('SKIP: ヘッドレス Chrome が見つかりません'); process.exit(3); }

const sleep = ms => new Promise(r => setTimeout(r, ms));
function freePort() {
  return new Promise((res, rej) => {
    const s = net.createServer(); s.unref();
    s.on('error', rej);
    s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
  });
}
async function waitHttp(url, tries = 60) {
  for (let i = 0; i < tries; i++) { try { const r = await fetch(url); if (r.ok) return true; } catch {} await sleep(150); }
  return false;
}
// ★接続待ちには上限を置く（上限が無いと開かなかったときに永久に待つ・KLK-122）
function openWs(ws, ms = 20000) {
  return new Promise((res, rej) => {
    const to = setTimeout(() => rej(new Error('CDP の WebSocket が ' + ms + 'ms で開きませんでした')), ms);
    ws.addEventListener('open', () => { clearTimeout(to); res(); });
    ws.addEventListener('error', () => { clearTimeout(to); rej(new Error('CDP の WebSocket でエラー')); });
    ws.addEventListener('close', () => { clearTimeout(to); rej(new Error('CDP の WebSocket が閉じられました')); });
  });
}
function cdpClient(ws) {
  let id = 0; const pend = new Map();
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { const { res, rej } = pend.get(m.id); pend.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
  });
  return (method, params = {}) => new Promise((res, rej) => { const i = ++id; pend.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
}

const results = [];
const check = (name, ok, detail) => results.push([name, !!ok, detail || '']);

(async () => {
  let chrome;
  try {
    const dp = await freePort();
    const profile = fs.mkdtempSync('/tmp/klk125-prof-');
    chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars',
      `--remote-debugging-port=${dp}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
    if (!await waitHttp(`http://127.0.0.1:${dp}/json/version`)) { console.error('[HARNESS ERROR] Chrome CDP が起きない'); process.exit(2); }

    const url = 'file://' + path.join(ROOT, 'draft-gen', 'index.html');
    const t = await (await fetch(`http://127.0.0.1:${dp}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' })).json();
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    await openWs(ws);
    const send = cdpClient(ws);
    await send('Runtime.enable');
    const ev = async e => (await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true })).result.value;
    await sleep(1500);

    // n 番目の「設定」を開き、その中の型セレクタを読む
    const openRow = async n => {
      await ev(`(()=>{const b=Array.from(document.querySelectorAll('button')).filter(x=>/設定/.test(x.textContent))[${n}]; if(b)b.click(); return !!b})()`);
      await sleep(400);
      return JSON.parse(await ev(`(()=>{
        const s = Array.from(document.querySelectorAll('select'))
          .find(x => Array.from(x.options).some(o => /^(自動)/.test(o.textContent)));
        return JSON.stringify(s ? Array.from(s.options).map(o => ({ v: o.value, t: o.textContent })) : null);
      })()`));
    };

    const menu = await openRow(1);   // 既定は ABOUT / MENU / GALLERY
    check('E1 行の「設定」を開くと型セレクタが出る', menu && menu.length === 7,
      '選択肢=' + (menu ? menu.length : 'なし'));

    if (menu) {
      const body = menu.slice(1);
      check('E2 ★選択肢が「日本語ラベル（マーカー）」で描かれる',
        body.every(o => o.t.includes('（' + o.v + '）') && o.t.indexOf('（') > 0),
        '例: ' + body.slice(0, 2).map(o => o.t).join(' , '));
      check('E3 ★option の value はマーカーのまま',
        body.every(o => /^[a-z0-9-]+$/.test(o.v)) && body.some(o => o.v === 'price-table'),
        'values=' + body.map(o => o.v).join(','));
      check('E4 先頭は「自動（案ごとに振り分け）」',
        menu[0].v === '' && menu[0].t.includes('自動'), menu[0].t);
    }

    const about = await openRow(0);
    check('E5 セクションごとに中身が違う（ABOUT と MENU）',
      about && menu && about.some(o => o.v === 'img-left') && menu.some(o => o.v === 'pat-cards'),
      'ABOUT=' + (about ? about.slice(1, 3).map(o => o.v).join(',') : 'なし'));

    ws.close();
  } catch (e) {
    console.error('[HARNESS ERROR] ' + (e && e.stack || e));
    process.exitCode = 2;
  } finally {
    try { chrome && chrome.kill(); } catch {}
  }
  if (process.exitCode === 2) process.exit(2);
  let failed = 0;
  console.log('KLK-125 実効果（SCR-001 の型セレクタに日本語ラベル）');
  for (const [name, ok, detail] of results) { if (!ok) failed++; console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? '\n        ' + detail : ''}`); }
  console.log(`${results.length} checks, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
