#!/usr/bin/env node
/*
 * KLK-129 実効果テスト（tester所有・Node.js標準＋ヘッドレス Chrome）
 *
 * 「せり出し横長画像の文言側が十分に広いか」を、**実際に描かれた箱の幅**で確かめる。
 * CSS の文字列ではなく、ブラウザが決めた列幅そのものを測る。
 *
 *   E1 ★白背景の文言側が 460px 以上ある（不具合当時は 273px だった）
 *   E2 ★画像側が文言側を押しつぶしていない（中身に押し広げられていない）
 *   E3 画像と文言が重なっている（「せり出し」という型が成立している）
 *   E4 ブロック全体が器からはみ出していない
 *   E5 ★`1fr 1fr` に戻すと E1 が崩れる（この検査が効いていることを、その場で確かめる）
 *   E6 モバイル（375px）では1列に畳まれる
 *
 * 題材は見本 samples/03（ABOUT が img-overlap）。file:// で開くのでブリッジは要らない。
 *
 * 実行: KLK_E2E_CHROME=<chrome のパス> node tests/site/e2e_klk129.node.js
 * 終了コード: 0=全PASS / 1=FAILあり / 2=ハーネス異常 / 3=環境理由でSKIP
 */
'use strict';
const { spawn } = require('node:child_process');
const net = require('node:net');
const path = require('node:path');
const fs = require('node:fs');

const ROOT = path.join(__dirname, '..', '..');
const TARGET = path.join(ROOT, 'samples', '03_クリニック_ナビ下配置', 'index-a.html');
const CHROME = process.env.KLK_E2E_CHROME
  || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium']
    .find(p => fs.existsSync(p));
if (!CHROME || !fs.existsSync(CHROME)) { console.log('SKIP: ヘッドレス Chrome が見つかりません'); process.exit(3); }
if (!fs.existsSync(TARGET)) { console.log('SKIP: 題材の見本がありません'); process.exit(3); }

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

// 実際に描かれた箱を測る
const MEASURE = `(() => {
  const a = document.querySelector('.m-about.img-overlap')
         || document.querySelector('[data-about="img-overlap"]');
  if (!a) return JSON.stringify({ found: false });
  const img = a.querySelector('.atari') || a.querySelector('.ab-media');
  const txt = a.querySelector('.txt') || a.querySelector('.ab-body');
  const ab = a.getBoundingClientRect(), ib = img.getBoundingClientRect(), tb = txt.getBoundingClientRect();
  return JSON.stringify({
    found: true,
    img: Math.round(ib.width), txt: Math.round(tb.width), all: Math.round(ab.width),
    overlap: Math.round(ib.right - tb.left),
    parent: Math.round(a.parentElement.clientWidth),
    stacked: tb.top >= ib.bottom - 2,
    // 実際に解決された列の本数（CSS の文字列ではなくブラウザの答えを見る）
    cols: getComputedStyle(a).gridTemplateColumns.trim().split(/\s+/).length,
    imgRight: Math.round(ib.right), docW: document.documentElement.scrollWidth, vw: window.innerWidth,
  });
})()`;

(async () => {
  let chrome;
  try {
    const dp = await freePort();
    const profile = fs.mkdtempSync('/tmp/klk129-prof-');
    chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--allow-file-access-from-files',
      `--remote-debugging-port=${dp}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
    if (!await waitHttp(`http://127.0.0.1:${dp}/json/version`)) { console.error('[HARNESS ERROR] Chrome CDP が起きない'); process.exit(2); }

    const url = 'file://' + TARGET;
    const t = await (await fetch(`http://127.0.0.1:${dp}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' })).json();
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    await openWs(ws);
    let id = 0; const pend = new Map();
    ws.addEventListener('message', ev => {
      const m = JSON.parse(ev.data);
      if (m.id && pend.has(m.id)) { const { res, rej } = pend.get(m.id); pend.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
    });
    const send = (method, params = {}) => new Promise((res, rej) => { const i = ++id; pend.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
    await send('Page.enable'); await send('Runtime.enable');
    await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 1000, deviceScaleFactor: 1, mobile: false });
    await sleep(1500);
    const ev = async e => (await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true })).result.value;
    // スクロール連動の演出で隠れていることがあるので出しておく
    await ev(`document.querySelectorAll('.reveal').forEach(e => e.classList.add('in','visible','show'));`);

    const m = JSON.parse(await ev(MEASURE));
    if (!m.found) { console.error('[HARNESS ERROR] 題材に img-overlap が無い'); process.exit(2); }

    check('E1 ★白背景の文言側が 460px 以上ある（不具合当時は 273px）',
      m.txt >= 460, `文言側=${m.txt}px 画像=${m.img}px 全体=${m.all}px`);
    check('E2 ★画像側が文言側を押しつぶしていない',
      m.txt >= m.img * 0.6, `画像=${m.img}px 文言=${m.txt}px（比 ${(m.txt / m.img).toFixed(2)}）`);
    check('E3 画像と文言が重なっている（「せり出し」が成立している）',
      m.overlap > 10, `重なり=${m.overlap}px`);
    check('E4 ブロックが器からはみ出していない',
      m.all <= m.parent, `全体=${m.all}px 器=${m.parent}px`);

    // ---- E5: ★`1fr 1fr` に戻すと本当に崩れるか、その場で確かめる
    await ev(`(() => {
      const st = document.createElement('style');
      st.id = 'klk129-break';
      st.textContent = '.m-about.img-overlap,[data-about="img-overlap"]{grid-template-columns:1fr 1fr !important;max-width:900px !important;}';
      document.head.appendChild(st);
    })()`);
    await sleep(300);
    const broken = JSON.parse(await ev(MEASURE));
    check('E5 ★`1fr 1fr` に戻すと文言側が痩せる（この検査が効いていることの確認）',
      broken.txt < m.txt, `戻したとき=${broken.txt}px / いま=${m.txt}px`);
    await ev(`document.getElementById('klk129-break').remove()`);
    await sleep(200);

    // ---- E6: モバイル
    await send('Emulation.setDeviceMetricsOverride', { width: 375, height: 800, deviceScaleFactor: 1, mobile: true });
    await sleep(400);
    const sp = JSON.parse(await ev(MEASURE));
    // ★「畳まれたか」は列の本数で見る。幅の比で見ると、はみ出していても通ってしまう
    //   （最初そう書いてしまい、375px で器375pxに対し文言400pxという状態を PASS にしていた）。
    check('E6 モバイル（375px）では1列に畳まれる',
      sp.cols === 1, `列の本数=${sp.cols} 文言側=${sp.txt}px 器=${sp.parent}px`);

    // ★375px で画像が画面からはみ出さないこと（理恵さんの指摘・2026-09-15）
    //   原因は min-height と aspect-ratio の組み合わせ。min-height:300px × 4/3 で
    //   幅が 400px 以上に固定され、375px の画面に収まらなかった。
    //   ★比べる相手は **端末の幅(375)** であって window.innerWidth ではない。
    //     中身がはみ出すとレイアウトビューポート自体が広がる（実測で 420 になった）ので、
    //     innerWidth と比べると**はみ出していても必ず通ってしまう**。
    //     最初そう書いてしまい、直す前のCSSに戻しても PASS のままだった。
    const PHONE = 375;
    check('E7 ★375px で画像が画面に収まり、ページが横スクロールしない',
      sp.imgRight <= PHONE && sp.docW <= PHONE + 1,
      `画像の右端=${sp.imgRight}px 端末=${PHONE}px 文書=${sp.docW}px（innerWidth=${sp.vw}）`);

    // 表は器の中で横スクロールしたままにする（理恵さんの意向: 表は縮めない）
    const tbl = JSON.parse(await ev(`(() => {
      const t = document.querySelector('.hours-table');
      if (!t) return JSON.stringify({ found: false });
      let p = t.parentElement, sc = null;
      while (p && p !== document.body) {
        const o = getComputedStyle(p).overflowX;
        if (o === 'auto' || o === 'scroll') { sc = p; break; }
        p = p.parentElement;
      }
      return JSON.stringify({ found: true, wrapped: !!sc,
        scrollable: sc ? sc.scrollWidth > sc.clientWidth : false });
    })()`));
    check('E8 幅のある表は器の中で横スクロールしたまま（表は縮めない）',
      !tbl.found || (tbl.wrapped && tbl.scrollable),
      tbl.found ? `器で包まれている=${tbl.wrapped} 横スクロール可=${tbl.scrollable}` : '題材に表なし');

    ws.close();
  } catch (e) {
    console.error('[HARNESS ERROR] ' + (e && e.stack || e));
    process.exitCode = 2;
  } finally {
    try { chrome && chrome.kill(); } catch {}
  }
  if (process.exitCode === 2) process.exit(2);
  let failed = 0;
  console.log('KLK-129 実効果（見本を実描画して列幅を実測）');
  for (const [name, ok, detail] of results) { if (!ok) failed++; console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? '\n        ' + detail : ''}`); }
  console.log(`${results.length} checks, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
