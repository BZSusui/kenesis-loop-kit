#!/usr/bin/env node
/*
 * KLK-130 実効果テスト（tester所有・Node.js標準＋ヘッドレス Chrome）
 *
 * マニュアルを**実際に開いて**、読む人が困る状態になっていないかを見る。
 * 文字列があるかは check_klk130.py が見る。ここは描かれ方だけを見る。
 *
 *   E1 サイドナビのリンクがすべて生きている（リンク切れなし）
 *   E2 ★mac の節へのリンクが、その節へ実際に飛ぶ
 *   E3 本文が横にはみ出していない（1400px）
 *   E4 ★スマホ幅（375px）でも横スクロールしない
 *   E5 ダイアログ文言の箱が、ちゃんと箱として描かれている（素の文字列になっていない）
 *
 * 実行: KLK_E2E_CHROME=<chrome のパス> node tests/site/e2e_klk130.node.js
 * 終了コード: 0=全PASS / 1=FAILあり / 2=ハーネス異常 / 3=環境理由でSKIP
 */
'use strict';
const { spawn } = require('node:child_process');
const net = require('node:net');
const path = require('node:path');
const fs = require('node:fs');

const ROOT = path.join(__dirname, '..', '..');
const TARGET = path.join(ROOT, '使い方マニュアル.html');
const CHROME = process.env.KLK_E2E_CHROME
  || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium']
    .find(p => fs.existsSync(p));
if (!CHROME || !fs.existsSync(CHROME)) { console.log('SKIP: ヘッドレス Chrome が見つかりません'); process.exit(3); }
if (!fs.existsSync(TARGET)) { console.log('SKIP: マニュアルがありません'); process.exit(3); }

const sleep = ms => new Promise(r => setTimeout(r, ms));
function freePort() {
  return new Promise((res, rej) => {
    const s = net.createServer(); s.unref();
    s.on('error', rej);
    s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
  });
}
async function waitHttp(url, tries = 80) {
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

(async () => {
  let chrome;
  try {
    const dp = await freePort();
    const profile = fs.mkdtempSync('/tmp/klk130-prof-');
    chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--allow-file-access-from-files',
      `--remote-debugging-port=${dp}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
    if (!await waitHttp(`http://127.0.0.1:${dp}/json/version`)) { console.error('[HARNESS ERROR] Chrome CDP が起きない'); process.exit(2); }

    const t = await (await fetch(`http://127.0.0.1:${dp}/json/new?${encodeURIComponent('file://' + TARGET)}`, { method: 'PUT' })).json();
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    await openWs(ws);
    let id = 0; const pend = new Map();
    ws.addEventListener('message', ev => {
      const m = JSON.parse(ev.data);
      if (m.id && pend.has(m.id)) { const { res, rej } = pend.get(m.id); pend.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
    });
    const send = (method, params = {}) => new Promise((res, rej) => { const i = ++id; pend.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
    await send('Page.enable'); await send('Runtime.enable');
    const ev = async e => (await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true })).result.value;

    // ---- 1400px
    await send('Emulation.setDeviceMetricsOverride', { width: 1400, height: 1100, deviceScaleFactor: 1, mobile: false });
    await sleep(900);

    const broken = JSON.parse(await ev(`(() => {
      const bad = Array.from(document.querySelectorAll('a[href^="#"]'))
        .filter(a => !document.getElementById(a.getAttribute('href').slice(1)))
        .map(a => a.getAttribute('href'));
      return JSON.stringify(bad);
    })()`));
    check('E1 サイドナビ・本文のページ内リンクがすべて生きている',
      broken.length === 0, `切れているリンク=${broken.join(',') || 'なし'}`);

    const jump = JSON.parse(await ev(`(() => {
      const a = Array.from(document.querySelectorAll('a[href="#start"]'))
        .find(x => x.closest('table'));
      if (!a) return JSON.stringify({ found: false });
      a.click();
      const sec = document.getElementById('start');
      const h3 = Array.from(sec.querySelectorAll('h3')).map(h => h.textContent);
      return JSON.stringify({ found: true, hasMac: h3.some(x => x.indexOf('Mac で初回') >= 0) });
    })()`));
    check('E2 ★対処表のリンクが mac の節を含む「起動する」へ飛ぶ',
      jump.found && jump.hasMac, `リンクあり=${jump.found} macの節あり=${jump.hasMac}`);

    const over = JSON.parse(await ev(`(() => {
      const w = document.documentElement.clientWidth;
      const bad = [];
      document.querySelectorAll('main *').forEach(e => {
        const b = e.getBoundingClientRect();
        if (b.width > 0 && b.right > w + 1) bad.push(e.tagName + '.' + String(e.className).slice(0, 24));
      });
      return JSON.stringify({ w: w, docW: document.documentElement.scrollWidth, bad: bad.slice(0, 5) });
    })()`));
    check('E3 本文が横にはみ出していない（1400px）',
      over.bad.length === 0 && over.docW <= over.w + 1,
      `はみ出し=${over.bad.join(' / ') || 'なし'} 文書幅=${over.docW}px`);

    const dlg = JSON.parse(await ev(`(() => {
      const d = document.querySelector('.dialog');
      if (!d) return JSON.stringify({ found: false });
      const cs = getComputedStyle(d);
      return JSON.stringify({ found: true,
        text: d.textContent.trim().slice(0, 30),
        boxed: cs.borderTopWidth !== '0px' || cs.backgroundColor !== 'rgba(0, 0, 0, 0)' });
    })()`));
    check('E5 ダイアログ文言が箱として描かれている（素の文字列になっていない）',
      dlg.found && dlg.boxed, `${dlg.found ? dlg.text : '.dialog なし'} / 箱=${dlg.boxed}`);

    // ---- 375px
    await send('Emulation.setDeviceMetricsOverride', { width: 375, height: 800, deviceScaleFactor: 1, mobile: true });
    await sleep(600);
    const sp = JSON.parse(await ev(`(() => JSON.stringify({
      docW: document.documentElement.scrollWidth, vw: 375,
    }))()`));
    check('E4 ★スマホ幅（375px）でも横スクロールしない',
      sp.docW <= sp.vw + 1, `文書幅=${sp.docW}px 端末=${sp.vw}px`);

    ws.close();
  } catch (e) {
    console.error('[HARNESS ERROR] ' + (e && e.stack || e));
    process.exitCode = 2;
  } finally {
    try { chrome && chrome.kill(); } catch {}
  }
  if (process.exitCode === 2) process.exit(2);
  let failed = 0;
  console.log('KLK-130 実効果（マニュアルを実際に開いて描かれ方を見る）');
  for (const [name, ok, detail] of results) { if (!ok) failed++; console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? '\n        ' + detail : ''}`); }
  console.log(`${results.length} checks, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
