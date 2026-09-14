#!/usr/bin/env node
/*
 * KLK-116 実効果テスト（tester所有・Node.js標準＋ヘッドレス Chrome＋ブリッジ実起動）
 *
 * 「palette の『モック生成画面へ送る』を押すと、別タブの SCR-001 に配色が入る」を
 * **実際に別タブへ届いたこと**で確かめる（文字列の有無ではなく実効果）。
 * ブリッジ（draft-gen/bridge.py）を空きポートで起動し、両画面を同一オリジンで開く。
 *
 *   E1 開いているタブへ即時: SCR-001 を開いた状態で palette の「送る」→ SCR-001 の 4色が payload と一致し、
 *      「受け取りました」が表示される
 *   E2 妨害注入: schema 違い / 全部壊れた hex を送っても SCR-001 の色が変わらない
 *   E3 保管分: SCR-001 を閉じた状態で送る → 新しく開いた SCR-001 は黙って変えず
 *      「届いています［反映する］」を出し、押すと入る。反映済みなら次に開いたときは出ない
 *
 * 実行: KLK_E2E_CHROME=<chrome のパス> node tests/site/e2e_klk116.node.js
 * 終了コード: 0=全PASS / 1=FAILあり / 2=ハーネス異常 / 3=環境理由でSKIP（Chrome 無し・ポート確保不可）
 */
'use strict';
const { spawn } = require('node:child_process');
const net = require('node:net');
const path = require('node:path');
const fs = require('node:fs');

const ROOT = path.join(__dirname, '..', '..');
const CHROME = process.env.KLK_E2E_CHROME
  || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium']
    .find(p => fs.existsSync(p));
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

// ---- CDP 最小クライアント -----------------------------------------------
function cdpClient(ws) {
  let id = 0; const pend = new Map();
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { const { res, rej } = pend.get(m.id); pend.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
  });
  return (method, params = {}) => new Promise((res, rej) => { const i = ++id; pend.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
}
async function openTab(debugPort, url) {
  const t = await (await fetch(`http://127.0.0.1:${debugPort}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' })).json();
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener('open', r));
  const send = cdpClient(ws);
  await send('Page.enable'); await send('Runtime.enable');
  // 読み込み完了待ち（document.readyState）
  for (let i = 0; i < 60; i++) {
    const r = await send('Runtime.evaluate', { expression: 'document.readyState', returnByValue: true });
    if (r.result.value === 'complete') break; await sleep(100);
  }
  const evalJs = async expr => (await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })).result.value;
  const close = async () => { ws.close(); await fetch(`http://127.0.0.1:${debugPort}/json/close/${t.id}`); };
  return { evalJs, close };
}

const results = [];
const check = (name, ok, detail) => results.push([name, !!ok, detail || '']);
const SCR_COLORS = `JSON.stringify({main:document.getElementById('hex-main').value, sub:document.getElementById('hex-sub').value, accent:document.getElementById('hex-accent').value, bg:document.getElementById('hex-bg').value})`;
const SCR_MSG = `document.getElementById('handoffMsg').textContent`;
const SCR_ROW_SHOWN = `document.getElementById('handoffRow').style.display !== 'none'`;
const SCR_APPLY_SHOWN = `document.getElementById('handoffApply').style.display !== 'none'`;

(async () => {
  let bridge, chrome;
  try {
    const bridgePort = await freePort();
    const debugPort = await freePort();
    const profile = fs.mkdtempSync('/tmp/klk116-chrome-');

    // ブリッジ実起動（同一オリジンの根拠・KLK-019）
    // ★ブリッジは起動時に `open <url>` で実ブラウザを開く（KLK-014）。テスト中に本物のブラウザが
    //   立ち上がらないよう、PATH の先頭に何もしない open / xdg-open を置く（bridge.py は変えない）
    const shim = fs.mkdtempSync('/tmp/klk116-shim-');
    for (const n of ['open', 'xdg-open']) { fs.writeFileSync(path.join(shim, n), '#!/bin/sh\nexit 0\n'); fs.chmodSync(path.join(shim, n), 0o755); }
    bridge = spawn('python3', [path.join(ROOT, 'draft-gen', 'bridge.py')],
      { env: { ...process.env, KLK_BRIDGE_PORT: String(bridgePort), PATH: shim + ':' + process.env.PATH }, stdio: 'ignore', cwd: ROOT });
    const base = `http://127.0.0.1:${bridgePort}`;
    if (!await waitHttp(`${base}/health`)) { console.log('SKIP: ブリッジが起動できません（ポート/環境）'); process.exit(3); }

    chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-prefers-reduced-motion',
      `--remote-debugging-port=${debugPort}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
    if (!await waitHttp(`http://127.0.0.1:${debugPort}/json/version`)) { console.error('[HARNESS ERROR] Chrome CDP が起きない'); process.exit(2); }

    // ---- E1: SCR-001 を開いた状態で palette から送る -------------------------
    const scr = await openTab(debugPort, `${base}/`);
    // localStorage は前回の残りが無い新規プロファイル。念のため消す
    await scr.evalJs(`localStorage.clear(); 'ok'`);
    const before = await scr.evalJs(SCR_COLORS);

    // palette は URL パラメータで即生成（KLK-004 の URL共有を利用）
    const pal = await openTab(debugPort, `${base}/palette/index.html?c=blue&seed=7`);
    const nBtn = await pal.evalJs(`document.querySelectorAll('.send-gen').length`);
    check('E0 palette に「送る」ボタンが案の数だけ描画される', nBtn >= 1, `buttons=${nBtn}`);
    const expected = await pal.evalJs(`JSON.stringify(handoffPayloadOf(currentPatterns[0]).colors)`);
    await pal.evalJs(`document.querySelector('.send-gen[data-p="0"]').click(); 'clicked'`);
    const btnText = await pal.evalJs(`document.querySelector('.send-gen[data-p="0"]').textContent`);
    await sleep(400);
    const after = await scr.evalJs(SCR_COLORS);
    const msg1 = await scr.evalJs(SCR_MSG);
    check('E1 ★「送る」で別タブの SCR-001 の4色が payload と一致する（即時・自動）',
      after === expected && after !== before, `before=${before} after=${after} expected=${expected}`);
    check('E1b 送信側は「送りました」、受信側は「受け取りました」を表示する',
      btnText.includes('送りました') && msg1.includes('受け取りました'), `btn=${btnText} msg=${msg1}`);
    check('E1c 受信で colorMode が pasted（生成指示書は既存の経路のまま）',
      (await scr.evalJs(`colorMode`)) === 'pasted');

    // ---- E2: 妨害注入 ---------------------------------------------------------
    const stable = await scr.evalJs(SCR_COLORS);
    await pal.evalJs(`sendHandoff({schema:'klk-other', version:1, colors:{main:'#000000',sub:'#000000',accent:'#000000',bg:'#000000'}, sentAt: Date.now()}); 'x'`);
    await sleep(300);
    const afterBadSchema = await scr.evalJs(SCR_COLORS);
    await pal.evalJs(`sendHandoff({schema:HANDOFF_SCHEMA, version:HANDOFF_VERSION, colors:{main:'red',sub:'<img>',accent:'#12',bg:'javascript:x'}, sentAt: Date.now()}); 'x'`);
    await sleep(300);
    const afterBadHex = await scr.evalJs(SCR_COLORS);
    check('E2 ★schema 違いを送っても SCR-001 の色は変わらない', afterBadSchema === stable, `now=${afterBadSchema}`);
    check('E2b ★全部壊れた hex を送っても変わらない', afterBadHex === stable, `now=${afterBadHex}`);

    // ---- E3: 保管分（SCR-001 を閉じてから送る → 開き直す） --------------------
    await scr.close();
    const expected2 = await pal.evalJs(`JSON.stringify(handoffPayloadOf(currentPatterns[1]).colors)`);
    await pal.evalJs(`document.querySelector('.send-gen[data-p="1"]').click(); 'clicked'`);
    await sleep(200);
    const scr2 = await openTab(debugPort, `${base}/`);
    const colors2 = await scr2.evalJs(SCR_COLORS);
    const rowShown = await scr2.evalJs(SCR_ROW_SHOWN);
    const applyShown = await scr2.evalJs(SCR_APPLY_SHOWN);
    const msg2 = await scr2.evalJs(SCR_MSG);
    check('E3 ★後から開いた SCR-001 は黙って色を変えず「届いています」＋［反映する］を出す',
      colors2 !== expected2 && rowShown && applyShown && msg2.includes('届いています'), `colors=${colors2} row=${rowShown} apply=${applyShown} msg=${msg2}`);
    await scr2.evalJs(`document.getElementById('handoffApply').click(); 'clicked'`);
    await sleep(200);
    const colors3 = await scr2.evalJs(SCR_COLORS);
    check('E3b ［反映する］で保管分の4色が入る', colors3 === expected2, `colors=${colors3} expected=${expected2}`);
    check('E3c 反映後は［反映する］が消える', !(await scr2.evalJs(SCR_APPLY_SHOWN)));
    await scr2.close();
    const scr3 = await openTab(debugPort, `${base}/`);
    check('E3d 反映済みの分は、次に開いたときにはもう出ない（消費済み判定）', !(await scr3.evalJs(SCR_ROW_SHOWN)));
    await scr3.close();
    await pal.close();
  } catch (e) {
    console.error('[HARNESS ERROR] ' + (e && e.stack || e));
    process.exitCode = 2;
  } finally {
    try { chrome && chrome.kill(); } catch {}
    try { bridge && bridge.kill(); } catch {}
  }
  if (process.exitCode === 2) process.exit(2);
  let failed = 0;
  console.log('KLK-116 実効果（ブリッジ実起動＋ヘッドレス Chrome・別タブへの受け渡し）');
  for (const [name, ok, detail] of results) { if (!ok) failed++; console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? '\n        ' + detail : ''}`); }
  console.log(`${results.length} checks, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
