#!/usr/bin/env node
/*
 * KLK-120 実効果テスト（tester所有・Node.js標準＋ヘッドレス Chrome＋ブリッジ実起動）
 *
 * 「登録済みエントリを画面から編集できる」を、**実際に catalog.json が書き換わったか**で確かめる。
 * 経路を丸ごと通す: SCR-004 の ✏ → モーダル → POST /catalog-update → catalog.json。
 *
 * ★実カタログ（catalog/・社外秘・167件）には触らない。
 *   bridge.py は自分のファイル位置からリポジトリルートを決めるので、
 *   **一時フォルダに draft-gen/ と catalog/ を用意してそこで起動する**（サンドボックス）。
 *   テストが途中で落ちても本物のカタログは無傷である。
 *
 *   E1 ✏ ボタンがカードに出る
 *   E2 モーダルが開き、既存の値が入っている
 *   E3 何も変えずに保存すると「変更はありません」（差分だけ送る作りであることの確認）
 *   E4 背景トーンを付けて保存 → catalog.json に実際に書かれる
 *   E5 ★他の項目（tags・sectionLayouts・taste）が巻き添えで消えない
 *   E6 「（未設定）」を選ぶとキーごと消える（元に戻せる）
 *   E7 件数が変わらない
 *   E8 妨害注入: 主配色を全部外すと画面が止める（空配列を送らない）
 *   E9 ★主配色を変えるとカードのタグも入れ替わる（KLK-121・実ユーザーの指摘）
 *      手で書いたタグ（業種の略称・自由語）は残ること
 *
 * 実行: KLK_E2E_CHROME=<chrome のパス> node tests/site/e2e_klk120.node.js
 * 終了コード: 0=全PASS / 1=FAILあり / 2=ハーネス異常 / 3=環境理由でSKIP
 */
'use strict';
const { spawn } = require('node:child_process');
const net = require('node:net');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');

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
async function waitHttp(url, tries = 80) {
  for (let i = 0; i < tries; i++) { try { const r = await fetch(url); if (r.ok) return true; } catch {} await sleep(150); }
  return false;
}
function cdpClient(ws) {
  let id = 0; const pend = new Map();
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { const { res, rej } = pend.get(m.id); pend.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
  });
  return (method, params = {}) => new Promise((res, rej) => { const i = ++id; pend.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
}

// 実カタログを模した最小データ（本物には触らない）
const SANDBOX_CATALOG = {
  schema: 'klk-catalog', version: 1, generatedAt: '2026-01-01T00:00:00+09:00',
  entries: [
    {
      id: 'cat-0001', file: 'cat-0001.png', title: 'サンプル工房',
      industry: 'ジュエリー・時計・貴金属', taste: '高級感', colors: ['ゴールド'],
      source: 'own', columns: '1col', tags: ['ジュエリー', '高級感', '1カラム'],
      note: 'テスト用のダミー', sectionLayouts: { HERO: 'split', ABOUT: 'img-right' },
      addedAt: '2026-01-01T00:00:00+09:00',
    },
    {
      id: 'cat-0002', file: 'cat-0002.png', title: 'サンプルカフェ',
      industry: '飲食店・カフェ・食関連', taste: 'ナチュラル', colors: ['グリーン'],
      source: 'ref', columns: '1col', tags: ['カフェ'], note: '',
      addedAt: '2026-01-02T00:00:00+09:00',
    },
  ],
};

const results = [];
const check = (name, ok, detail) => results.push([name, !!ok, detail || '']);

(async () => {
  let bridge, chrome, sandbox;
  try {
    sandbox = fs.mkdtempSync(path.join(os.tmpdir(), 'klk120-root-'));
    fs.mkdirSync(path.join(sandbox, 'draft-gen'), { recursive: true });
    fs.mkdirSync(path.join(sandbox, 'catalog', 'img'), { recursive: true });
    fs.mkdirSync(path.join(sandbox, 'catalog', '.pending'), { recursive: true });
    for (const f of ['bridge.py', 'catalog.html', 'index.html']) {
      fs.copyFileSync(path.join(ROOT, 'draft-gen', f), path.join(sandbox, 'draft-gen', f));
    }
    fs.writeFileSync(path.join(sandbox, 'catalog', 'catalog.json'),
      JSON.stringify(SANDBOX_CATALOG, null, 2), 'utf8');
    const catPath = path.join(sandbox, 'catalog', 'catalog.json');
    const readCat = () => JSON.parse(fs.readFileSync(catPath, 'utf8'));

    const bp = await freePort();
    const shim = fs.mkdtempSync(path.join(os.tmpdir(), 'klk120-shim-'));
    for (const n of ['open', 'xdg-open']) {
      fs.writeFileSync(path.join(shim, n), '#!/bin/sh\nexit 0\n'); fs.chmodSync(path.join(shim, n), 0o755);
    }
    bridge = spawn('python3', [path.join(sandbox, 'draft-gen', 'bridge.py')],
      { env: { ...process.env, KLK_BRIDGE_PORT: String(bp), PATH: shim + ':' + process.env.PATH },
        stdio: 'ignore', cwd: sandbox });
    if (!await waitHttp(`http://127.0.0.1:${bp}/health`)) { console.log('SKIP: ブリッジが起動できません'); process.exit(3); }

    // サンドボックスで動いていることを先に確かめる（本物を触っていない証明）
    const served = await (await fetch(`http://127.0.0.1:${bp}/catalog.json`)).json();
    if (!(served.entries && served.entries.length === 2)) {
      console.error('[HARNESS ERROR] サンドボックスのカタログが配信されていない（本物を見ている恐れ）');
      process.exit(2);
    }

    const dp = await freePort();
    const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'klk120-prof-'));
    chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars',
      `--remote-debugging-port=${dp}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
    if (!await waitHttp(`http://127.0.0.1:${dp}/json/version`)) { console.error('[HARNESS ERROR] Chrome CDP が起きない'); process.exit(2); }

    const t = await (await fetch(`http://127.0.0.1:${dp}/json/new?${encodeURIComponent(`http://127.0.0.1:${bp}/catalog`)}`, { method: 'PUT' })).json();
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    await new Promise(r => ws.addEventListener('open', r));
    const send = cdpClient(ws);
    await send('Runtime.enable');
    const ev = async e => (await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true })).result.value;
    await sleep(2200);

    check('E1 ✏ ボタンがカードに出る',
      (await ev(`document.querySelectorAll(".item .edit").length`)) === 2,
      '件数=' + await ev(`document.querySelectorAll(".item .edit").length`));

    const openModal = async id => {
      await ev(`document.querySelector('.edit[data-edit-id="${id}"]').click();1`);
      await sleep(350);
    };
    const status = () => ev(`document.getElementById("editStatus").textContent`);
    const save = async () => { await ev(`document.getElementById("editSave").click();1`); await sleep(1600); };

    await openModal('cat-0001');
    check('E2 モーダルが開き、既存の値が入っている',
      (await ev(`document.getElementById("editModalBack").classList.contains("open")`))
      && (await ev(`document.getElementById("editTaste").value`)) === '高級感'
      && (await ev(`document.getElementById("editTitle").value`)) === 'サンプル工房',
      'taste=' + await ev(`document.getElementById("editTaste").value`));

    // E3 何も変えずに保存 → 差分なし
    await ev(`document.getElementById("editSave").click();1`); await sleep(400);
    check('E3 何も変えずに保存すると「変更はありません」（差分だけ送る作り）',
      (await status()).includes('変更はありません'), await status());

    // E4 背景トーンを付ける
    await ev(`document.querySelectorAll('input[name="editBg"]').forEach(i=>{i.checked=(i.value==="ダーク")});1`);
    await save();
    check('E4 ★保存が成功し、catalog.json に実際に書かれる',
      (await status()).includes('保存しました') && readCat().entries[0].bgTone === 'ダーク',
      'status=' + await status() + ' / bgTone=' + readCat().entries[0].bgTone);

    const e0 = readCat().entries[0];
    check('E5 ★他の項目が巻き添えで消えない（tags・sectionLayouts・taste・addedAt）',
      Array.isArray(e0.tags) && e0.tags.length === 3
      && e0.sectionLayouts && e0.sectionLayouts.HERO === 'split'
      && e0.taste === '高級感' && e0.addedAt === '2026-01-01T00:00:00+09:00',
      `tags=${(e0.tags || []).length} sectionLayouts=${JSON.stringify(e0.sectionLayouts)} taste=${e0.taste}`);

    // E6 未設定へ戻す
    await openModal('cat-0001');
    await ev(`document.querySelectorAll('input[name="editBg"]').forEach(i=>{i.checked=(i.value==="")});1`);
    await save();
    check('E6 ★「（未設定）」でキーごと消える（元に戻せる）',
      !('bgTone' in readCat().entries[0]),
      'status=' + await status() + ' / キー有無=' + ('bgTone' in readCat().entries[0]));

    check('E7 件数が変わらない', readCat().entries.length === 2, '件数=' + readCat().entries.length);

    // E8 妨害注入: 主配色を全部外す → 画面が止める（空配列を送らない）
    await openModal('cat-0001');
    const before = JSON.stringify(readCat().entries[0].colors);
    await ev(`document.getElementById("editColors").querySelectorAll("input[data-ec]").forEach(i=>{i.checked=false});1`);
    await ev(`document.getElementById("editSave").click();1`); await sleep(900);
    check('E8 妨害注入: 主配色を全部外すと画面が止め、データは変わらない',
      (await status()).includes('主配色は1つ以上') && JSON.stringify(readCat().entries[0].colors) === before,
      'status=' + await status() + ' / colors=' + JSON.stringify(readCat().entries[0].colors));

    // ---- E9: 主配色を変えるとタグも入れ替わる（KLK-121）
    await openModal('cat-0001');
    await ev(`document.getElementById("editColors").querySelectorAll("input[data-ec]").forEach(i=>{i.checked=(i.getAttribute("data-ec")==="ネイビー")});1`);
    await save();
    const e9 = readCat().entries[0];
    // ★カードは並び替わるので id で特定する。再描画は非同期なので少し待って読み直す
    const readCardTags = () => ev(`(() => {
      const btn = document.querySelector('.edit[data-edit-id="cat-0001"]');
      const card = btn && btn.closest('.item');
      return JSON.stringify(card ? Array.from(card.querySelectorAll('.tags span')).map(s => s.textContent) : null);
    })()`);
    let shown = await readCardTags();
    for (let i = 0; i < 12 && String(shown).indexOf('ネイビー') < 0; i++) {
      await sleep(300); shown = await readCardTags();
    }
    check('E9 ★主配色を変えるとタグも入れ替わり、手書きタグは残る',
      e9.tags.indexOf('ネイビー') >= 0 && e9.tags.indexOf('ゴールド') < 0
      && e9.tags.indexOf('ジュエリー') >= 0 && e9.tags.indexOf('高級感') >= 0
      && String(shown).indexOf('ネイビー') >= 0 && String(shown).indexOf('ゴールド') < 0,
      'tags=' + JSON.stringify(e9.tags) + ' / カード表示=' + shown);

    ws.close();
  } catch (e) {
    console.error('[HARNESS ERROR] ' + (e && e.stack || e));
    process.exitCode = 2;
  } finally {
    try { chrome && chrome.kill(); } catch {}
    try { bridge && bridge.kill(); } catch {}
    try { sandbox && fs.rmSync(sandbox, { recursive: true, force: true }); } catch {}
  }
  if (process.exitCode === 2) process.exit(2);
  let failed = 0;
  console.log('KLK-120 実効果（SCR-004 の ✏ → /catalog-update → catalog.json・サンドボックス）');
  for (const [name, ok, detail] of results) { if (!ok) failed++; console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? '\n        ' + detail : ''}`); }
  console.log(`${results.length} checks, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
