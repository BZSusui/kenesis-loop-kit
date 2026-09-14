#!/usr/bin/env node
/*
 * KLK-117 実効果テスト（tester所有・Node.js標準＋ヘッドレス Chrome＋ブリッジ実起動）
 *
 * 「型を選び直すセレクタに日本語ラベルが出る」を、**実際に描かれた <option> の文字**で確かめる。
 * 経路を丸ごと通す: compare_template.html → make_compare.py → 実ブリッジ /sections → 画面の DOM。
 * 文字列が template に在るかではなく、人が見る選択肢がどうなっているかを見る。
 *
 *   E1 番地を選ぶと、型セレクタの選択肢が「日本語ラベル（マーカー）」になる
 *   E2 選択肢の value はマーカーのまま（送る desiredType が日本語にならない）
 *   E3 ラベルの中身がブリッジの SECTION_TYPE_LABELS と一致する（画面で勝手に作っていない）
 *   E4 現在の型に「（現在）」が付き、既定で選ばれている（KLK-078/079 の不変条件）
 *   E5 型を持たない番地（NAV-01/FOOTER-01）では「この番地に型はありません」
 *   E6 ★labels を返さないブリッジ（旧版）を模しても、マーカーだけで壊れずに出る
 *
 * ★compare.html の BASE は 127.0.0.1:8765 固定なので、このポートが空いているときだけ走る。
 *   使用中なら SKIP（静的・動的の層は別に担保されている）。
 *
 * 実行: KLK_E2E_CHROME=<chrome のパス> node tests/site/e2e_klk117.node.js
 * 終了コード: 0=全PASS / 1=FAILあり / 2=ハーネス異常 / 3=環境理由でSKIP
 */
'use strict';
const { spawn, spawnSync } = require('node:child_process');
const net = require('node:net');
const path = require('node:path');
const fs = require('node:fs');

const ROOT = path.join(__dirname, '..', '..');
const PORT = 8765;                       // compare.html の BASE 固定値
const SAMPLE = path.join(ROOT, 'samples', '03_クリニック_ナビ下配置');
const WORK_REL = path.join('mockups', '_klk117_e2e_' + process.pid);   // .gitignore 対象
const WORK = path.join(ROOT, WORK_REL);

const CHROME = process.env.KLK_E2E_CHROME
  || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium']
    .find(p => fs.existsSync(p));
if (!CHROME || !fs.existsSync(CHROME)) { console.log('SKIP: ヘッドレス Chrome が見つかりません'); process.exit(3); }

const sleep = ms => new Promise(r => setTimeout(r, ms));
function portFree(port) {
  return new Promise(res => {
    const s = net.createServer();
    s.once('error', () => res(false));
    s.once('listening', () => s.close(() => res(true)));
    s.listen(port, '127.0.0.1');
  });
}
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
// ★CDP の WebSocket 接続待ちには必ず上限を置く。
//   `await new Promise(r => ws.addEventListener('open', r))` は開かなければ**永久に待つ**。
//   入れ子でスイートを回すと Chrome が何個も立ち上がり、接続できないまま固まって
//   外側の 300 秒タイムアウトで落ちていた（単独なら5秒で終わるのに・KLK-122 で判明）。
//   上限を置けば「開かなかった」と分かる形で早く失敗する。
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
async function openTab(debugPort, url, initScript) {
  // about:blank で開いてから初期化スクリプトを仕込み、そのあと目的のURLへ移動する
  //   （ページ自身の JS より先に差し込む必要があるため）
  const t = await (await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, { method: 'PUT' })).json();
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await openWs(ws);
  const send = cdpClient(ws);
  await send('Page.enable'); await send('Runtime.enable');
  if (initScript) await send('Page.addScriptToEvaluateOnNewDocument', { source: initScript });
  await send('Page.navigate', { url });
  for (let i = 0; i < 60; i++) {
    const r = await send('Runtime.evaluate', { expression: 'document.readyState', returnByValue: true });
    if (r.result.value === 'complete') break; await sleep(100);
  }
  return {
    evalJs: async expr => (await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })).result.value,
    close: async () => { ws.close(); await fetch(`http://127.0.0.1:${debugPort}/json/close/${t.id}`); },
  };
}

const results = [];
const check = (name, ok, detail) => results.push([name, !!ok, detail || '']);

// 番地を選び、型セレクタの中身を読む
const pick = addr => `(async () => {
  const sel = document.getElementById('regen-addr');
  sel.value = ${JSON.stringify(addr)};
  sel.dispatchEvent(new Event('change'));
  await new Promise(r => setTimeout(r, 120));
  const ts = document.getElementById('regen-type');
  return JSON.stringify({
    disabled: ts.disabled,
    value: ts.value,
    options: Array.from(ts.options).map(o => ({ value: o.value, text: o.textContent })),
  });
})()`;

(async () => {
  let bridge, chrome;
  try {
    if (!await portFree(PORT)) { console.log(`SKIP: ポート ${PORT} が使用中（compare.html の BASE は固定）`); process.exit(3); }

    // ---- 題材を作る: 見本の index を mockups/ 配下へ写し、compare.html を現テンプレートから起こす
    fs.mkdirSync(WORK, { recursive: true });
    for (const f of ['index-a.html', 'index-b.html', 'index-c.html']) {
      const src = path.join(SAMPLE, f);
      if (fs.existsSync(src)) fs.copyFileSync(src, path.join(WORK, f));
    }
    const mk = spawnSync('python3', [path.join(ROOT, 'draft-gen', 'make_compare.py'), WORK_REL],
      { cwd: ROOT, encoding: 'utf8' });
    if (mk.status !== 0 || !fs.existsSync(path.join(WORK, 'compare.html'))) {
      console.error('[HARNESS ERROR] make_compare.py 失敗: ' + (mk.stderr || mk.stdout));
      process.exit(2);
    }

    // ---- ブリッジ実起動（起動時の `open` は no-op shim で抑止）
    const shim = fs.mkdtempSync('/tmp/klk117-shim-');
    for (const n of ['open', 'xdg-open']) { fs.writeFileSync(path.join(shim, n), '#!/bin/sh\nexit 0\n'); fs.chmodSync(path.join(shim, n), 0o755); }
    bridge = spawn('python3', [path.join(ROOT, 'draft-gen', 'bridge.py')],
      { env: { ...process.env, KLK_BRIDGE_PORT: String(PORT), PATH: shim + ':' + process.env.PATH }, stdio: 'ignore', cwd: ROOT });
    if (!await waitHttp(`http://127.0.0.1:${PORT}/health`)) { console.log('SKIP: ブリッジが起動できません'); process.exit(3); }

    // ブリッジが持つラベル表を取り出す（画面の表示と突き合わせる正）
    const secResp = await (await fetch(
      `http://127.0.0.1:${PORT}/sections?folder=${encodeURIComponent(WORK_REL)}&letter=a`)).json();
    const byAddr = {};
    for (const s of secResp.sections) byAddr[s.addr] = s;
    check('E0 /sections が labels を返す', !!(byAddr['MENU-01'] && byAddr['MENU-01'].labels),
      `MENU-01 labels=${JSON.stringify((byAddr['MENU-01'] || {}).labels || null)}`);

    const debugPort = await freePort();
    const profile = fs.mkdtempSync('/tmp/klk117-chrome-');
    chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars',
      `--remote-debugging-port=${debugPort}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
    if (!await waitHttp(`http://127.0.0.1:${debugPort}/json/version`)) { console.error('[HARNESS ERROR] Chrome CDP が起きない'); process.exit(2); }

    const tab = await openTab(debugPort, 'file://' + path.join(WORK, 'compare.html'));
    await sleep(900);   // health 検知 → /sections → 番地セレクタの組み立てを待つ

    // ---- E1〜E4: 型を持つ番地
    const menu = JSON.parse(await tab.evalJs(pick('MENU-01')));
    const expected = byAddr['MENU-01'].labels;
    const current = byAddr['MENU-01'].current;

    const allLabelled = menu.options.every(o => o.text.includes(expected[o.value]) && o.text.includes(o.value));
    check('E1 ★選択肢が「日本語ラベル（マーカー）」で描かれる', allLabelled && menu.options.length === 6,
      `${menu.options.length}件 / 例: ${menu.options.slice(0, 2).map(o => o.text).join(' , ')}`);

    check('E2 ★選択肢の value はマーカーのまま（desiredType が日本語にならない）',
      menu.options.every(o => /^[a-z0-9-]+$/.test(o.value)) && menu.options.some(o => o.value === 'tab-switch'),
      `values=${menu.options.map(o => o.value).join(',')}`);

    const mismatched = menu.options.filter(o => !o.text.startsWith(expected[o.value]));
    check('E3 ★ラベルの中身がブリッジの表と一致する（画面で作り足していない）',
      mismatched.length === 0, mismatched.map(o => `${o.value}→${o.text}`).join(' / ') || 'すべて一致');

    const cur = menu.options.find(o => o.value === current);
    check('E4 現在の型に「（現在）」が付き、既定で選ばれている',
      !!cur && cur.text.includes('（現在）') && menu.value === current,
      `current=${current} text=${cur && cur.text} selected=${menu.value}`);

    // ---- E5: 型を持たない番地
    const nav = JSON.parse(await tab.evalJs(pick('NAV-01')));
    check('E5 型を持たない番地は無効＋「この番地に型はありません」',
      nav.disabled && nav.options.length === 1 && nav.options[0].text.includes('型はありません'),
      `disabled=${nav.disabled} text=${nav.options.map(o => o.text).join('')}`);

    await tab.close();

    // ---- E6: ★旧ブリッジ（labels を返さない版）を実際に食わせる。
    //      ページ内の変数をいじるのではなく、**/sections の応答から labels を剥がす**。
    //      剥がせたことを先に assert してから判定する（壊れていないのに通る空検査を避ける）。
    const strip = `
      (() => {
        window.__stripped = 0;
        const orig = window.fetch;
        window.fetch = async (...args) => {
          const res = await orig(...args);
          const url = String(args[0] || '');
          if (url.indexOf('/sections') < 0) return res;
          const j = await res.clone().json();
          (j.sections || []).forEach(s => { if (s.labels) { window.__stripped++; delete s.labels; } });
          return new Response(JSON.stringify(j), { status: res.status, headers: { 'content-type': 'application/json' } });
        };
      })();`;
    const tab2 = await openTab(debugPort, 'file://' + path.join(WORK, 'compare.html'), strip);
    await sleep(1200);
    const strippedCount = await tab2.evalJs('window.__stripped');
    const legacy = JSON.parse(await tab2.evalJs(pick('ABOUT-01')));
    const labelWords = Object.values(byAddr['ABOUT-01'].labels);
    const noJapanese = legacy.options.every(o => !labelWords.some(w => o.text.includes(w)));
    check('E6 ★labels を実際に剥がした応答を食わせても、マーカーだけで壊れずに出る（旧ブリッジ互換）',
      strippedCount > 0 && legacy.options.length === 6
      && legacy.options.every(o => o.text.includes(o.value)) && noJapanese,
      `剥がした件数=${strippedCount} / 例: ${legacy.options.slice(0, 2).map(o => o.text).join(' , ')}`);
    await tab2.close();
  } catch (e) {
    console.error('[HARNESS ERROR] ' + (e && e.stack || e));
    process.exitCode = 2;
  } finally {
    try { chrome && chrome.kill(); } catch {}
    try { bridge && bridge.kill(); } catch {}
    try { fs.rmSync(WORK, { recursive: true, force: true }); } catch {}
  }
  if (process.exitCode === 2) process.exit(2);
  let failed = 0;
  console.log('KLK-117 実効果（テンプレート→make_compare→実ブリッジ→画面の選択肢）');
  for (const [name, ok, detail] of results) { if (!ok) failed++; console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? '\n        ' + detail : ''}`); }
  console.log(`${results.length} checks, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
