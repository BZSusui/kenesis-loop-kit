#!/usr/bin/env node
/*
 * KLK-126 実効果テスト（tester所有・Node.js標準＋ヘッドレス Chrome＋ブリッジ実起動）
 *
 * 「型を**絵で見て**選べる」を、実際に描かれた DOM と**実測した位置・大きさ**で確かめる。
 * 経路を丸ごと通す: compare_template.html → make_compare.py → 実ブリッジ /sections → 画面。
 * テンプレートに文字列が在るかは check_klk126.py が見る。ここは**動くか**だけを見る。
 *
 *   E1 顔のボタンが「絵＋日本語ラベル」で描かれる
 *   E2 ★押すとモーダルが開き、その番地のプールが1行ずつ出る
 *   E3 ★各行に絵が実際に描かれている（空の箱になっていない）
 *   E4 ★行を押すと <select> の値がそのマーカーになり、モーダルが閉じる
 *   E5 現在の型の行に「現在」が付く（KLK-079 の不変条件の見せ方）
 *   E6 型を持たない番地ではボタンが無効（KLK-081）
 *   E7 Esc で閉じ、フォーカスがボタンへ戻る
 *   E8 ★375px でも1行が保たれ、アイコンが潰れない（実測）
 *   E9 ★描画に外部リソースを1つも使っていない（NFR-005）
 *   E10 ★レシピに無いマーカーを**実際に食わせても**空の行にならない
 *
 * ★compare.html の BASE は 127.0.0.1:8765 固定なので、このポートが空いているときだけ走る。
 *
 * 実行: KLK_E2E_CHROME=<chrome のパス> node tests/site/e2e_klk126.node.js
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
const WORK_REL = path.join('mockups', '_klk126_e2e_' + process.pid);   // .gitignore 対象
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
// 接続待ちには必ず上限を置く（開かないと永久に待つ・KLK-122）
function openWs(ws, ms = 20000) {
  return new Promise((res, rej) => {
    const to = setTimeout(() => rej(new Error('CDP の WebSocket が ' + ms + 'ms で開きませんでした')), ms);
    ws.addEventListener('open', () => { clearTimeout(to); res(); });
    ws.addEventListener('error', () => { clearTimeout(to); rej(new Error('CDP の WebSocket でエラー')); });
    ws.addEventListener('close', () => { clearTimeout(to); rej(new Error('CDP の WebSocket が閉じられました')); });
  });
}
// 目的の URL が読み終わるまで待つ（about:blank を掴まない・KLK-125）
async function waitLoaded(send, url, tries = 80) {
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
async function openTab(debugPort, url, initScript) {
  const t = await (await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, { method: 'PUT' })).json();
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await openWs(ws);
  const send = cdpClient(ws);
  await send('Page.enable'); await send('Runtime.enable');
  if (initScript) await send('Page.addScriptToEvaluateOnNewDocument', { source: initScript });
  await send('Page.navigate', { url });
  await waitLoaded(send, url);
  return {
    send,
    evalJs: async expr => (await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })).result.value,
    close: async () => { ws.close(); await fetch(`http://127.0.0.1:${debugPort}/json/close/${t.id}`); },
  };
}

const results = [];
const check = (name, ok, detail) => results.push([name, !!ok, detail || '']);

// 番地を選んでモーダルを開き、一覧の実測値を返す
const openFor = addr => `(async () => {
  const sel = document.getElementById('regen-addr');
  sel.value = ${JSON.stringify(addr)};
  sel.dispatchEvent(new Event('change'));
  await new Promise(r => setTimeout(r, 150));
  const face = document.getElementById('regen-type-btn');
  const faceIco = face.querySelector('.ico');
  const faceTxt = face.querySelector('.rtb-txt');
  const before = {
    faceDisabled: face.disabled,
    faceHasIcon: !!faceIco && faceIco.querySelectorAll('div,i').length > 0,
    faceText: faceTxt ? faceTxt.textContent : '',
  };
  face.click();
  await new Promise(r => setTimeout(r, 150));
  const modal = document.getElementById('type-modal');
  const rows = Array.from(document.querySelectorAll('#type-modal-list .tm-row')).map(r => {
    const ico = r.querySelector('.ico');
    const nm = r.querySelector('.tm-name');
    const ib = ico ? ico.getBoundingClientRect() : null;
    const nb = nm ? nm.getBoundingClientRect() : null;
    const rb = r.getBoundingClientRect();
    return {
      type: r.getAttribute('data-type'),
      name: nm ? nm.textContent : '',
      marker: (r.querySelector('.tm-mk') || {}).textContent || '',
      now: !!r.querySelector('.tm-now'),
      current: r.getAttribute('aria-current') === 'true',
      parts: ico ? ico.querySelectorAll('div,i').length : 0,
      painted: ico ? Array.from(ico.querySelectorAll('div,i')).filter(e => {
        const b = e.getBoundingClientRect(); return b.width > 0.5 && b.height > 0.5;
      }).length : 0,
      icoW: ib ? Math.round(ib.width) : 0, icoH: ib ? Math.round(ib.height) : 0,
      rowH: Math.round(rb.height),
      sideBySide: !!(ib && nb) && nb.left >= ib.right - 1
                  && Math.abs((ib.top + ib.bottom) / 2 - (nb.top + nb.bottom) / 2) < rb.height / 2,
    };
  });
  return JSON.stringify({
    before, open: !modal.hidden, addr: document.getElementById('type-modal-addr').textContent, rows,
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
    const shim = fs.mkdtempSync('/tmp/klk126-shim-');
    for (const n of ['open', 'xdg-open']) { fs.writeFileSync(path.join(shim, n), '#!/bin/sh\nexit 0\n'); fs.chmodSync(path.join(shim, n), 0o755); }
    bridge = spawn('python3', [path.join(ROOT, 'draft-gen', 'bridge.py')],
      { env: { ...process.env, KLK_BRIDGE_PORT: String(PORT), PATH: shim + ':' + process.env.PATH }, stdio: 'ignore', cwd: ROOT });
    if (!await waitHttp(`http://127.0.0.1:${PORT}/health`)) { console.log('SKIP: ブリッジが起動できません'); process.exit(3); }

    const secResp = await (await fetch(
      `http://127.0.0.1:${PORT}/sections?folder=${encodeURIComponent(WORK_REL)}&letter=a`)).json();
    const byAddr = {};
    for (const s of secResp.sections) byAddr[s.addr] = s;
    if (!byAddr['MENU-01'] || !byAddr['MENU-01'].pool) {
      console.error('[HARNESS ERROR] 題材に MENU-01 が無い'); process.exit(2);
    }

    const debugPort = await freePort();
    const profile = fs.mkdtempSync('/tmp/klk126-chrome-');
    chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars',
      `--remote-debugging-port=${debugPort}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
    if (!await waitHttp(`http://127.0.0.1:${debugPort}/json/version`)) { console.error('[HARNESS ERROR] Chrome CDP が起きない'); process.exit(2); }

    const tab = await openTab(debugPort, 'file://' + path.join(WORK, 'compare.html'));
    await sleep(900);

    const menu = JSON.parse(await tab.evalJs(openFor('MENU-01')));
    const want = byAddr['MENU-01'];

    check('E1 顔のボタンが「絵＋日本語ラベル」で描かれる',
      menu.before.faceHasIcon && menu.before.faceText === (want.labels || {})[want.current],
      `icon=${menu.before.faceHasIcon} text=${JSON.stringify(menu.before.faceText)} 現在=${want.current}`);

    check('E2 ★押すとモーダルが開き、その番地のプールが1行ずつ出る',
      menu.open && menu.rows.length === want.pool.length
      && menu.rows.every((r, i) => r.type === want.pool[i]) && menu.addr === 'MENU-01',
      `開いた=${menu.open} 行=${menu.rows.length}/${want.pool.length} 番地=${menu.addr}`);

    const thin = menu.rows.filter(r => r.painted < 3);
    check('E3 ★各行に絵が実際に描かれている（空の箱になっていない）',
      thin.length === 0,
      `最少パーツ数=${Math.min(...menu.rows.map(r => r.painted))} 薄い行=${thin.map(r => r.type).join(',') || 'なし'}`);

    const cur = menu.rows.find(r => r.type === want.current);
    check('E5 現在の型の行に「現在」が付く',
      !!cur && cur.now && cur.current && menu.rows.filter(r => r.now).length === 1,
      `current=${want.current} 印=${cur && cur.now}`);

    const other = want.pool.find(t => t !== want.current);
    const picked = JSON.parse(await tab.evalJs(`(async () => {
      const rows = Array.from(document.querySelectorAll('#type-modal-list .tm-row'));
      const row = rows.find(r => r.getAttribute('data-type') === ${JSON.stringify(other)});
      row.click();
      await new Promise(r => setTimeout(r, 120));
      const ts = document.getElementById('regen-type');
      return JSON.stringify({
        value: ts.value, hidden: ts.hidden,
        closed: document.getElementById('type-modal').hidden,
        face: (document.querySelector('#regen-type-btn .rtb-txt') || {}).textContent || '',
      });
    })()`));
    check('E4 ★行を押すと <select> の値がそのマーカーになり、モーダルが閉じる',
      picked.value === other && picked.closed && picked.hidden
      && picked.face === (want.labels || {})[other],
      `value=${picked.value}（期待 ${other}）閉じた=${picked.closed} select は隠れたまま=${picked.hidden} 顔=${picked.face}`);

    const nav = JSON.parse(await tab.evalJs(`(async () => {
      const sel = document.getElementById('regen-addr');
      sel.value = 'NAV-01'; sel.dispatchEvent(new Event('change'));
      await new Promise(r => setTimeout(r, 150));
      const face = document.getElementById('regen-type-btn');
      face.click();
      await new Promise(r => setTimeout(r, 120));
      return JSON.stringify({
        disabled: face.disabled, text: face.textContent,
        opened: !document.getElementById('type-modal').hidden,
      });
    })()`));
    check('E6 型を持たない番地ではボタンが無効で、モーダルも開かない（KLK-081）',
      nav.disabled && !nav.opened && nav.text.indexOf('型はありません') >= 0,
      `disabled=${nav.disabled} 開いた=${nav.opened} 文言=${JSON.stringify(nav.text)}`);

    const esc = JSON.parse(await tab.evalJs(`(async () => {
      const sel = document.getElementById('regen-addr');
      sel.value = 'MENU-01'; sel.dispatchEvent(new Event('change'));
      await new Promise(r => setTimeout(r, 150));
      const face = document.getElementById('regen-type-btn');
      face.click();
      await new Promise(r => setTimeout(r, 120));
      const openedAt = !document.getElementById('type-modal').hidden;
      const focusedRow = document.activeElement && document.activeElement.className.indexOf('tm-row') >= 0;
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      await new Promise(r => setTimeout(r, 120));
      return JSON.stringify({
        openedAt, focusedRow,
        closed: document.getElementById('type-modal').hidden,
        backToFace: document.activeElement === face,
      });
    })()`));
    check('E7 Esc で閉じ、フォーカスがボタンへ戻る',
      esc.openedAt && esc.focusedRow && esc.closed && esc.backToFace,
      `開いた=${esc.openedAt} 行にフォーカス=${esc.focusedRow} 閉じた=${esc.closed} 戻った=${esc.backToFace}`);

    // ---- E8: 375px で実測する
    await tab.send('Emulation.setDeviceMetricsOverride',
      { width: 375, height: 700, deviceScaleFactor: 1, mobile: true });
    await sleep(250);
    const small = JSON.parse(await tab.evalJs(openFor('MENU-01')));
    const stacked = small.rows.filter(r => !r.sideBySide);
    const tiny = small.rows.filter(r => r.icoW < 50 || r.icoH < 30);
    check('E8 ★375px でも1行が保たれ、アイコンが潰れない（実測）',
      small.open && stacked.length === 0 && tiny.length === 0,
      `アイコン=${small.rows[0] && small.rows[0].icoW}×${small.rows[0] && small.rows[0].icoH}px `
      + `行高=${small.rows.map(r => r.rowH).join(',')} 縦積み=${stacked.map(r => r.type).join(',') || 'なし'}`);

    // ★モーダルは画面内に収まっているか。ページが横スクロールしていると
    //   （375px で実測したら幅 446px あった）右端と閉じるボタンが画面の外へ出る。
    const fit = JSON.parse(await tab.evalJs(`(() => {
      const box = document.querySelector('.tm-box').getBoundingClientRect();
      return JSON.stringify({
        vw: window.innerWidth, docW: document.documentElement.scrollWidth,
        left: Math.round(box.left), right: Math.round(box.right),
        x: Math.round(document.getElementById('type-modal-x').getBoundingClientRect().right),
      });
    })()`));
    check('E11 ★375px でモーダルが画面内に収まる（ページが横へはみ出していない）',
      fit.vw <= 376 && fit.docW <= fit.vw + 1 && fit.left >= 0 && fit.right <= fit.vw + 1 && fit.x <= fit.vw,
      `画面幅=${fit.vw} 文書幅=${fit.docW} 枠=${fit.left}〜${fit.right} 閉じるボタン右端=${fit.x}`);

    const ext = await tab.evalJs(`(() => {
      const box = document.getElementById('type-modal');
      const bad = [];
      box.querySelectorAll('*').forEach(e => {
        const t = e.tagName.toLowerCase();
        if (t === 'img' || t === 'svg' || t === 'picture' || t === 'object') bad.push(t);
        const bg = getComputedStyle(e).backgroundImage;
        if (bg && bg !== 'none') bad.push('bg:' + bg.slice(0, 40));
      });
      return JSON.stringify({ count: box.querySelectorAll('*').length, bad });
    })()`);
    const extJ = JSON.parse(ext);
    check('E9 ★描画に外部リソースを1つも使っていない（NFR-005）',
      extJ.bad.length === 0 && extJ.count > 100,
      `要素=${extJ.count} 外部=${extJ.bad.slice(0, 3).join(' / ') || 'なし'}`);
    await tab.close();

    // ---- E10: ★レシピに無いマーカーを**実際に**プールへ混ぜる。
    //      混ざったことを先に assert してから判定する（壊れていないのに通る空検査を避ける）。
    const inject = `
      (() => {
        window.__injected = 0;
        const orig = window.fetch;
        window.fetch = async (...args) => {
          const res = await orig(...args);
          if (String(args[0] || '').indexOf('/sections') < 0) return res;
          const j = await res.clone().json();
          (j.sections || []).forEach(s => {
            if (s.addr === 'MENU-01' && s.pool && s.pool.length) {
              s.pool = s.pool.concat(['klk126-unknown-marker']);
              window.__injected++;
            }
          });
          return new Response(JSON.stringify(j), { status: res.status, headers: { 'content-type': 'application/json' } });
        };
      })();`;
    const tab2 = await openTab(debugPort, 'file://' + path.join(WORK, 'compare.html'), inject);
    await sleep(1200);
    const injected = await tab2.evalJs('window.__injected');
    const un = JSON.parse(await tab2.evalJs(openFor('MENU-01')));
    const unknown = un.rows.find(r => r.type === 'klk126-unknown-marker');
    check('E10 ★レシピに無いマーカーを実際に食わせても、空の行にならない',
      injected > 0 && !!unknown && unknown.painted > 0 && unknown.name === 'klk126-unknown-marker',
      `混ぜた件数=${injected} 行=${!!unknown} 描いたパーツ=${unknown && unknown.painted} 名前=${unknown && unknown.name}`);
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
  console.log('KLK-126 実効果（テンプレート→make_compare→実ブリッジ→画面で開いて選ぶ）');
  for (const [name, ok, detail] of results) { if (!ok) failed++; console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? '\n        ' + detail : ''}`); }
  console.log(`${results.length} checks, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
