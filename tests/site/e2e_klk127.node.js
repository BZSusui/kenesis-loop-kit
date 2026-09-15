#!/usr/bin/env node
/*
 * KLK-127 実効果テスト（tester所有・Node.js標準＋ヘッドレス Chrome＋ブリッジ実起動）
 *
 * 「業種を一覧で選び、さらに自由入力で具体的に書いても、参考素材がその業種に絞られる」を
 * **実際に描かれたサムネイルの枚数と業種**で確かめる。
 *
 * ★カタログは実データを使わない。`/catalog.json` の応答を**差し替えた固定の題材**で走らせる。
 *   実カタログ（Git 除外・環境ごとに中身が違う）に依存すると、
 *   「3件になるはず」という判定が環境次第で意味を失うため。差し替えたことは先に assert する。
 *
 *   E1 ★一覧で選び、自由入力にも書いたとき、その業種だけに絞られる（不具合の再現面）
 *   E2 一覧だけ選んだとき（従来どおり絞られる）
 *   E3 一覧が無く自由入力だけのとき（前方一致・見つからなければ全件）
 *   E4 業種未選択のときは全件（KLK-094 の前提を壊さない）
 *   E5 ★チップが実際の結果と一致する（全件に落ちたらそう言う）
 *   E6 ★生成指示書の industry は従来どおり自由入力が優先される（出力を変えない）
 *   E7 「すべての実績」「同じテイストのみ」の挙動を変えていない
 *
 * 実行: KLK_E2E_CHROME=<chrome のパス> node tests/site/e2e_klk127.node.js
 * 終了コード: 0=全PASS / 1=FAILあり / 2=ハーネス異常 / 3=環境理由でSKIP
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
async function waitLoaded(send, url, tries = 100) {
  const bare = s => String(s).split('#')[0].split('?')[0];
  const want = bare(url);
  for (let i = 0; i < tries; i++) {
    const r = await send('Runtime.evaluate', {
      expression: 'JSON.stringify({h: location.href, s: document.readyState})', returnByValue: true });
    try {
      const v = JSON.parse(r.result.value);
      if (v.s === 'complete' && v.h !== 'about:blank' && bare(v.h) === want) return true;
    } catch {}
    await sleep(100);
  }
  throw new Error('ページが読み終わりませんでした: ' + url);
}
function cdpClient(ws) {
  let id = 0; const pend = new Map();
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { const { res, rej } = pend.get(m.id); pend.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
  });
  return (method, params = {}) => new Promise((res, rej) => { const i = ++id; pend.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
}

// ---- 固定の題材（実カタログに依存しない）--------------------------------
// クリニック3件 / 飲食4件 / 美容2件 = 9件。テイストは意図的にばらす。
const FIXTURE = [];
const MAKE = (n, industry, taste) => {
  for (let i = 1; i <= n; i++) {
    FIXTURE.push({ id: `${industry}-${i}`, title: `${industry}の実績${i}`, file: '',
      industry, taste, tags: [industry], colors: [] });
  }
};
MAKE(3, 'クリニック・病院・介護リハビリ', 'シンプル');
MAKE(4, '飲食店・カフェ・食関連', 'ナチュラル');
MAKE(2, '美容室・エステ・化粧品', 'シンプル');

const results = [];
const check = (name, ok, detail) => results.push([name, !!ok, detail || '']);

(async () => {
  let bridge, chrome;
  try {
    const bp = await freePort();
    const shim = fs.mkdtempSync('/tmp/klk127-shim-');
    for (const n of ['open', 'xdg-open']) { fs.writeFileSync(path.join(shim, n), '#!/bin/sh\nexit 0\n'); fs.chmodSync(path.join(shim, n), 0o755); }
    bridge = spawn('python3', [path.join(ROOT, 'draft-gen', 'bridge.py')],
      { env: { ...process.env, KLK_BRIDGE_PORT: String(bp), PATH: shim + ':' + process.env.PATH }, stdio: 'ignore', cwd: ROOT });
    if (!await waitHttp(`http://127.0.0.1:${bp}/health`)) { console.log('SKIP: ブリッジが起動できません'); process.exit(3); }

    const debugPort = await freePort();
    const profile = fs.mkdtempSync('/tmp/klk127-chrome-');
    chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars',
      `--remote-debugging-port=${debugPort}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
    if (!await waitHttp(`http://127.0.0.1:${debugPort}/json/version`)) { console.error('[HARNESS ERROR] Chrome CDP が起きない'); process.exit(2); }

    // ★/catalog.json の応答を題材へ差し替える（差し替えたことは window.__swapped で確かめる）
    const swap = `
      (() => {
        window.__swapped = 0;
        const FIX = ${JSON.stringify(FIXTURE)};
        const orig = window.fetch;
        window.fetch = async (...args) => {
          if (String(args[0] || '').indexOf('/catalog.json') < 0) return orig(...args);
          window.__swapped++;
          return new Response(JSON.stringify({ entries: FIX }),
            { status: 200, headers: { 'content-type': 'application/json' } });
        };
      })();`;

    const url = `http://127.0.0.1:${bp}/`;
    const t = await (await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, { method: 'PUT' })).json();
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    await openWs(ws);
    const send = cdpClient(ws);
    await send('Page.enable'); await send('Runtime.enable');
    await send('Page.addScriptToEvaluateOnNewDocument', { source: swap });
    await send('Page.navigate', { url });
    await waitLoaded(send, url);
    await sleep(1800);

    const ev = async e => (await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true })).result.value;

    const swapped = await ev('window.__swapped');
    if (!swapped) { console.error('[HARNESS ERROR] /catalog.json を差し替えられていない'); process.exit(2); }
    check('E0 ★題材を実際に読ませた（実カタログに依存していない）',
      swapped > 0 && (await ev('catalogEntries.length')) === FIXTURE.length,
      `差し替え=${swapped}回 読み込み件数=${await ev('catalogEntries.length')}（題材 ${FIXTURE.length} 件）`);

    // 業種/自由入力/絞り込みを設定し、描かれた結果を読む
    const setAndRead = (preset, custom, mode) => `(async () => {
      const f = document.getElementById('thumbFilter');
      f.value = ${JSON.stringify(mode || '近い業種のみ')};
      f.dispatchEvent(new Event('change', { bubbles: true }));
      const sel = document.getElementById('industrySelect');
      sel.value = ${JSON.stringify(preset)}; sel.dispatchEvent(new Event('change', { bubbles: true }));
      const c = document.getElementById('industryCustom');
      c.value = ${JSON.stringify(custom)}; c.dispatchEvent(new Event('input', { bubbles: true }));
      await new Promise(r => setTimeout(r, 300));
      const cards = Array.from(document.querySelectorAll('#thumbs .thumb'));
      const note = document.getElementById('thumbNote');
      const more = document.getElementById('thumbsMore');
      return JSON.stringify({
        chip: document.getElementById('industryChip').textContent,
        shown: cards.length,
        industries: Array.from(new Set(cards.map(x => x.dataset.industry))),
        hiddenCount: more.hidden ? 0 : 1,
        note: note.style.display !== 'none' ? note.textContent : '',
        instruction: buildInstruction(collectInput()).industry,   // {preset, custom, resolved}
      });
    })()`;

    const CLINIC = 'クリニック・病院・介護リハビリ';
    const DETAIL = '小児科・アレルギー科のクリニック';

    const both = JSON.parse(await ev(setAndRead(CLINIC, DETAIL)));
    check('E1 ★一覧で選び、自由入力にも書いたとき、その業種だけに絞られる',
      both.shown === 3 && both.industries.length === 1 && both.industries[0] === CLINIC,
      `${both.shown}件 業種=${both.industries.join(',')}`);

    check('E5 ★チップが実際の結果と一致する（絞れているときは業種名）',
      both.chip === `業種「${CLINIC}」に近い実績を表示中`, both.chip);

    check('E6 ★生成指示書の industry は自由入力が優先される（出力を変えない）',
      both.instruction.resolved === DETAIL && both.instruction.preset === CLINIC
      && both.instruction.custom === DETAIL,
      `resolved=${both.instruction.resolved} preset=${both.instruction.preset} custom=${both.instruction.custom}`);

    const presetOnly = JSON.parse(await ev(setAndRead(CLINIC, '')));
    check('E2 一覧だけ選んだとき（従来どおり絞られる）',
      presetOnly.shown === 3 && presetOnly.industries[0] === CLINIC
      && presetOnly.instruction.resolved === CLINIC,
      `${presetOnly.shown}件 resolved=${presetOnly.instruction.resolved}`);

    const customOnly = JSON.parse(await ev(setAndRead('', DETAIL)));
    check('E3 一覧が無く自由入力だけのとき（当たらなければ全件・従来どおり）',
      customOnly.shown === FIXTURE.length && customOnly.note.indexOf('見つからないため') >= 0
      && customOnly.instruction.resolved === DETAIL,
      `${customOnly.shown}件 注記=${customOnly.note || 'なし'}`);

    check('E5b ★全件に落ちたらチップもそう言う（自己矛盾を作らない）',
      customOnly.chip.indexOf('すべての実績を表示中') >= 0
      && customOnly.chip.indexOf(DETAIL) >= 0, customOnly.chip);

    const none = JSON.parse(await ev(setAndRead('', '')));
    check('E4 業種未選択のときは全件（KLK-094 の前提を壊さない）',
      none.shown === FIXTURE.length && none.chip.indexOf('業種を選ぶと') >= 0,
      `${none.shown}件 チップ=${none.chip}`);

    const all = JSON.parse(await ev(setAndRead(CLINIC, DETAIL, 'すべての実績')));
    const taste2 = JSON.parse(await ev(`(async () => {
      const r = document.querySelector('input[name=taste][data-taste="ナチュラル"]');
      if (r) { r.checked = true; r.dispatchEvent(new Event('change', { bubbles: true })); }
      const f = document.getElementById('thumbFilter');
      f.value = '同じテイストのみ'; f.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise(x => setTimeout(x, 300));
      const cards = Array.from(document.querySelectorAll('#thumbs .thumb'));
      return JSON.stringify({
        shown: cards.length,
        tastes: Array.from(new Set(cards.map(c => c.dataset.taste))),
        chip: document.getElementById('industryChip').textContent,
      });
    })()`));
    check('E7 「すべての実績」「同じテイストのみ」の挙動を変えていない',
      all.shown === FIXTURE.length && all.chip === 'すべての実績を表示中'
      && taste2.shown === 4 && taste2.tastes.length === 1 && taste2.tastes[0] === 'ナチュラル',
      `すべて=${all.shown}件 / テイスト=${taste2.shown}件（${taste2.tastes.join(',')}）チップ=${taste2.chip}`);

    ws.close();
  } catch (e) {
    console.error('[HARNESS ERROR] ' + (e && e.stack || e));
    process.exitCode = 2;
  } finally {
    try { chrome && chrome.kill(); } catch {}
    try { bridge && bridge.kill(); } catch {}
  }
  if (process.exitCode === 2) process.exit(2);
  let failed = 0;
  console.log('KLK-127 実効果（実ブリッジ→画面→描かれたサムネイルの業種と枚数）');
  for (const [name, ok, detail] of results) { if (!ok) failed++; console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? '\n        ' + detail : ''}`); }
  console.log(`${results.length} checks, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
