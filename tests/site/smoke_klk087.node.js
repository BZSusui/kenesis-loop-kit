/*
 * KLK-087 動的スモーク（Node.js）— ページ構成（composition）の純ロジックと
 * 構成リスト UI を、DOM シムの上で**実際に動かして**検証する（smoke_klk022/079 と同型）。
 *
 * なぜ必要か:
 *   この機能の核は「**既存の使い方をしている限り出力が1バイトも変わらない**」こと。
 *   静的な文字列一致では、それを確かめられない。実際に buildInstruction を呼んで突き合わせる。
 *   UI も、並び替え・複製・削除・上限が本当に効くかは動かさないと分からない。
 *
 * Run: node tests/site/smoke_klk087.node.js
 * exit 0 = all pass / 1 = fail / 2 = harness error。ネットワーク非使用・Node標準のみ。
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(path.dirname(__dirname));
const src = fs.readFileSync(path.join(ROOT, 'draft-gen', 'index.html'), 'utf8');

const START = 'const COLUMN_KEYS';
const END = '\nfunction render() {';
const iStart = src.indexOf(START);
const iEnd = src.indexOf(END);
const RC_START = '// KLK-087: ページ構成リスト。状態は compState';
const RC_END = '// ---- イベント登録 ---';
const rcStart = src.indexOf(RC_START);
const rcEnd = src.indexOf(RC_END, rcStart);
if (iStart < 0 || iEnd < 0 || rcStart < 0 || rcEnd < 0) {
  console.error('[HARNESS ERROR] 純ロジック領域の抽出に失敗（マーカー不一致）');
  process.exit(2);
}
const slice = src.slice(iStart, iEnd);
const rc = src.slice(rcStart, rcEnd);

const results = [];
function check(name, passed, detail) { results.push([name, !!passed, detail]); }

// --- 最小 DOM シム ---------------------------------------------------------
class El {
  constructor(t) {
    this.tagName = (t || 'div').toUpperCase();
    this.children = []; this.attrs = {}; this._t = '';
    this.value = ''; this.disabled = false; this.dataset = {}; this.listeners = {};
    this.type = ''; this.className = ''; this.title = ''; this.rows = 0;
    this.maxLength = 0; this.placeholder = '';
  }
  get firstChild() { return this.children[0] || null; }
  appendChild(c) { this.children.push(c); return c; }
  removeChild(c) { this.children = this.children.filter(x => x !== c); return c; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  removeAttribute(k) { delete this.attrs[k]; }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
  addEventListener(e, f) { (this.listeners[e] = this.listeners[e] || []).push(f); }
  fire(e, ev) { (this.listeners[e] || []).forEach(f => f(Object.assign({ target: this, preventDefault() {} }, ev || {}))); }
  set textContent(v) { this._t = String(v); this.children = []; }
  get textContent() { return this._t; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  // KLK-091: ドラッグ&ドロップの検証に要る最小限
  get classList() {
    const self = this;
    self._cls = self._cls || new Set();
    return {
      add: c => self._cls.add(c),
      remove: (...cs) => cs.forEach(c => self._cls.delete(c)),
      toggle: (c, on) => (on ? self._cls.add(c) : self._cls.delete(c)),
      contains: c => self._cls.has(c),
    };
  }
  // 行の高さ 40px・上端 idx*40 を模す（上半分/下半分の判定を試せる）
  getBoundingClientRect() { return { top: this._top || 0, height: 40 }; }
}

function makeEnv() {
  const byId = { compList: new El(), compAddBtns: new El(), compCount: new El() };
  const doc = {
    getElementById: id => byId[id] || null,
    createElement: t => new El(t),
    querySelector: () => null,
    querySelectorAll: () => [],
  };
  const env = { document: doc, render: () => {}, JSON, Object, Array, String, console };
  const keys = Object.keys(env);
  const api = new Function(...keys, 'return (function(){' + slice + '\n' + rc +
    '\nreturn { get s(){return compState}, set s(v){compState=v},' +
    ' set o(v){compOpenIdx=v}, renderComposition, buildInstruction,' +
    ' normalizeComposition, isPlainComposition, normalizeCompositionEntry, compMove,' +
    ' SECTION_TYPE_POOLS, SECTION_KEYS, maxInstancesFor, COMPOSITION_MAX_TOTAL,' +
    ' SECTION_PLACEHOLDERS, placeholdersFor };})()'
  )(...keys.map(k => env[k]));
  return { api, byId };
}

const { api, byId } = makeEnv();
const BASE = {
  projectName: 'テスト', industryPreset: '飲食店・カフェ・食関連', column: '1col',
  colors: { mode: 'explicit' }, mainHex: '#2e7d6b', variants: 3, atari: 'standard',
};
const stable = o => { const c = JSON.parse(JSON.stringify(o)); c.meta.createdAt = 'X'; return JSON.stringify(c); };

// ===========================================================================
// P群 — ★後方互換（この機能の最重要不変条件）
// ===========================================================================
{
  const legacy = api.buildInstruction(Object.assign({}, BASE, { sections: ['ABOUT', 'MENU', 'GALLERY'] }));
  const viaComp = api.buildInstruction(Object.assign({}, BASE,
    { composition: [{ key: 'ABOUT' }, { key: 'MENU' }, { key: 'GALLERY' }] }));
  check('P1 従来の sections 指定と composition(既定相当)の出力が完全一致',
    stable(legacy) === stable(viaComp) && !('composition' in viaComp),
    '一致=' + (stable(legacy) === stable(viaComp)) + ' / composition キー=' + ('composition' in viaComp));
}
{
  // 見出し・リードを付けても、並びが canonical・各1個・型なしなら従来スキーマのまま
  const withText = api.buildInstruction(Object.assign({}, BASE, {
    composition: [{ key: 'ABOUT', heading: 'あいさつ' }, { key: 'MENU', lead: '説明' }],
  }));
  check('P2 見出し/リードだけなら composition を出さず sectionOptions に載る（従来スキーマで表せる）',
    !('composition' in withText)
      && withText.sectionOptions.ABOUT.heading === 'あいさつ'
      && withText.sectionOptions.MENU.lead === '説明',
    'composition=' + ('composition' in withText) + ' / opts=' + JSON.stringify(withText.sectionOptions));
}
{
  const noComp = api.buildInstruction(Object.assign({}, BASE, {}));
  check('P3 composition も sections も無い入力は従来既定（ABOUT/MENU/GALLERY）',
    JSON.stringify(noComp.sections) === '["ABOUT","MENU","GALLERY"]' && !('composition' in noComp),
    'sections=' + JSON.stringify(noComp.sections));
}

// ===========================================================================
// E群 — composition が要るときだけ出る
// ===========================================================================
{
  const dup = api.buildInstruction(Object.assign({}, BASE,
    { composition: [{ key: 'MENU' }, { key: 'ABOUT' }, { key: 'MENU' }] }));
  check('E1 重複があれば composition を出し、sections は canonical 順の集合',
    Array.isArray(dup.composition) && dup.composition.length === 3
      && JSON.stringify(dup.sections) === '["ABOUT","MENU"]'
      && dup.composition.map(e => e.key).join(',') === 'MENU,ABOUT,MENU',
    'composition=' + JSON.stringify(dup.composition.map(e => e.key)) + ' sections=' + JSON.stringify(dup.sections));
}
{
  const ord = api.buildInstruction(Object.assign({}, BASE,
    { composition: [{ key: 'GALLERY' }, { key: 'ABOUT' }] }));
  check('E2 並びが canonical と違えば composition を出す（並びを捨てない）',
    Array.isArray(ord.composition) && ord.composition.map(e => e.key).join(',') === 'GALLERY,ABOUT',
    JSON.stringify(ord.composition));
}
{
  const ty = api.buildInstruction(Object.assign({}, BASE,
    { composition: [{ key: 'ABOUT' }, { key: 'MENU', type: 'price-table' }, { key: 'GALLERY' }] }));
  check('E3 型を指定すれば composition を出す（canonical 順・各1個でも）',
    Array.isArray(ty.composition) && ty.composition[1].type === 'price-table',
    JSON.stringify(ty.composition));
}
{
  const real = api.buildInstruction(Object.assign({}, BASE, {
    composition: [
      { key: 'ABOUT', heading: '私たちについて' },
      { key: 'MENU', heading: 'ランチ', type: 'pat-cards' },
      { key: 'CTA' },
      { key: 'MENU', heading: 'ディナー', type: 'price-table', moreLink: { label: 'メニュー一覧へ' } },
      { key: 'CTA' },
    ],
  }));
  check('E4 実案件を模した構成（MENU×2・CTA×2・任意並び）が保たれる',
    real.composition.length === 5
      && real.composition.map(e => e.key).join(',') === 'ABOUT,MENU,CTA,MENU,CTA'
      && real.composition[3].moreLink.label === 'メニュー一覧へ',
    JSON.stringify(real.composition.map(e => e.key)));
  check('E5 第1インスタンスの見出しは sectionOptions にも載る（旧読み手への graceful degradation）',
    real.sectionOptions.MENU.heading === 'ランチ' && real.sectionOptions.ABOUT.heading === '私たちについて'
      && real.sectionOptions.CTA.purpose === 'contact',
    JSON.stringify(real.sectionOptions));
}

// ===========================================================================
// N群 — 正規化（上限・語彙・型・moreLink）
// ===========================================================================
const N = api.normalizeComposition;
check('N1 複製できるものは各3個まで（超過分は落とす）',
  N(new Array(5).fill({ key: 'MENU' })).entries.length === 3
    && N(new Array(5).fill({ key: 'CTA' })).entries.length === 3,
  'MENU=' + N(new Array(5).fill({ key: 'MENU' })).entries.length +
  ' CTA=' + N(new Array(5).fill({ key: 'CTA' })).entries.length);
check('N2 ACCESS / CONTACT / SEARCH は1個のみ',
  ['ACCESS', 'CONTACT', 'SEARCH'].every(k => N(new Array(3).fill({ key: k })).entries.length === 1),
  ['ACCESS', 'CONTACT', 'SEARCH'].map(k => k + '=' + N(new Array(3).fill({ key: k })).entries.length).join(' '));
{
  const many = [];
  ['ABOUT', 'MENU', 'GALLERY', 'VOICE', 'FLOW'].forEach(k => { many.push({ key: k }, { key: k }, { key: k }); });
  const r = N(many);
  check('N3 本文合計は 12 個で打ち切り', r.entries.length === 12 && r.dropped === 3,
    'entries=' + r.entries.length + ' dropped=' + r.dropped);
}
check('N4 語彙外・非オブジェクトは落とす（黙って通さない）',
  N([{ key: 'ABOUT' }, { key: 'HACK' }, { key: '../etc' }, 'MENU', null, 123]).entries.length === 1,
  JSON.stringify(N([{ key: 'ABOUT' }, { key: 'HACK' }, 'MENU', null]).entries));
{
  const r = N([{ key: 'MENU', type: 'pat-cards' }, { key: 'MENU', type: 'pat-grid' },
               { key: 'MENU', type: '<script>' }, { key: 'CTA', type: 'pat-cards' }]);
  check('N5 型は「そのKEYのプールに載っているか」で判定（別セクションの型・語彙外・CTA は付かない）',
    r.entries[0].type === 'pat-cards' && !r.entries[1].type && !r.entries[2].type && !r.entries[3].type,
    JSON.stringify(r.entries));
}
{
  const r = N([{ key: 'MENU', moreLink: { label: '一覧', href: 'https://evil.example/' } },
               { key: 'ABOUT', moreLink: { label: '詳しく', href: '/about' } },
               { key: 'FAQ', moreLink: { label: '' } }]);
  check('N6 moreLink は外部URLを落とし、相対パスは残し、空ラベルなら付けない（§4.3）',
    !r.entries[0].moreLink.href && r.entries[1].moreLink.href === '/about' && !r.entries[2].moreLink,
    JSON.stringify(r.entries.map(e => e.moreLink || null)));
}
{
  let threw = null;
  [null, undefined, 'x', 123, {}, [[]], [{ key: {} }]].forEach(v => { try { N(v); } catch (e) { threw = String(e); } });
  check('N7 壊れた入力でも例外を投げない', threw === null, threw || 'なし');
}

// ===========================================================================
// U群 — 構成リスト UI の実挙動
// ===========================================================================
{
  const { api: a2, byId: b2 } = makeEnv();
  a2.renderComposition();
  const list = b2.compList;
  const btns = i => list.children[i].children[0].children.filter(c => c.tagName === 'BUTTON');
  check('U1 初期表示は従来と同じ ABOUT / MENU / GALLERY の3行',
    a2.s.map(e => e.key).join(',') === 'ABOUT,MENU,GALLERY' && list.children.length === 3,
    a2.s.map(e => e.key).join(',') + ' / 行数=' + list.children.length);
  check('U2 先頭行の ↑ が無効・末尾行の ↓ が無効',
    btns(0).find(b => b.textContent === '↑').disabled === true
      && btns(2).find(b => b.textContent === '↓').disabled === true,
    '先頭↑=' + btns(0).find(b => b.textContent === '↑').disabled);
  btns(0).find(b => b.textContent === '↓').fire('click');
  check('U3 ↓ で並びが入れ替わる', a2.s.map(e => e.key).join(',') === 'MENU,ABOUT,GALLERY',
    a2.s.map(e => e.key).join(','));
  btns(0).find(b => b.textContent === '複製').fire('click');
  check('U4 複製で同じセクションがもう1つ増える', a2.s.map(e => e.key).join(',') === 'MENU,MENU,ABOUT,GALLERY',
    a2.s.map(e => e.key).join(','));
  btns(0).find(b => b.textContent === '削除').fire('click');
  check('U5 削除でその行だけ消える', a2.s.map(e => e.key).join(',') === 'MENU,ABOUT,GALLERY',
    a2.s.map(e => e.key).join(','));
}
{
  const { api: a3, byId: b3 } = makeEnv();
  a3.s = [{ key: 'MENU' }, { key: 'MENU' }, { key: 'MENU' }];
  a3.renderComposition();
  const addBtns = b3.compAddBtns.children;
  const menuBtn = addBtns.find(b => b.textContent === 'MENU');
  const aboutBtn = addBtns.find(b => b.textContent === 'ABOUT');
  check('U6 上限に達したセクションの「追加」だけが無効になる',
    menuBtn.disabled === true && aboutBtn.disabled === false,
    'MENU=' + menuBtn.disabled + ' ABOUT=' + aboutBtn.disabled);
  const dupBtn = b3.compList.children[0].children[0].children.filter(c => c.tagName === 'BUTTON')
    .find(b => b.textContent === '複製');
  check('U7 上限に達したら「複製」も無効になる', dupBtn.disabled === true, String(dupBtn.disabled));
}
{
  const { api: a4, byId: b4 } = makeEnv();
  a4.s = new Array(12).fill(0).map(() => ({ key: 'ABOUT' }));   // 正規化前の生状態
  a4.renderComposition();
  check('U8 合計が上限のとき件数表示が警告になる',
    b4.compCount.getAttribute('data-full') === '1' && /12 \/ 12/.test(b4.compCount.textContent),
    b4.compCount.textContent);
}
{
  const { api: a5, byId: b5 } = makeEnv();
  a5.s = [{ key: 'MENU' }];
  a5.o = 0;              // 設定を開いた状態で描画
  a5.renderComposition();
  const body = b5.compList.children[0].children[1];
  const sel = (function find(el) {
    if (el.tagName === 'SELECT') return el;
    for (const c of el.children) { const r = find(c); if (r) return r; }
    return null;
  })(body);
  const opts = sel ? sel.children.map(o => o.value) : [];
  check('U9 設定を開くと、そのセクションの型プールが選択肢に出る（先頭は自動）',
    sel && opts[0] === '' && opts.slice(1).join(',') === a5.SECTION_TYPE_POOLS.MENU.join(','),
    JSON.stringify(opts));
}
{
  const { api: a6, byId: b6 } = makeEnv();
  a6.s = [{ key: 'CTA' }];
  a6.o = 0;
  a6.renderComposition();
  const body = b6.compList.children[0].children[1];
  const hasSelect = (function find(el) {
    if (el.tagName === 'SELECT') return true;
    return el.children.some(find);
  })(body);
  check('U10 CTA には型の選択肢を出さない（§4.4 で自動整列するため）', hasSelect === false,
    'select あり=' + hasSelect);
}

// ===========================================================================
// D群 — ドラッグ&ドロップ並べ替え（KLK-091・↑↓ と同じ compMove を通ること）
// ===========================================================================
function dndEnv(keys) {
  const { api, byId } = makeEnv();
  api.s = keys.map(k => ({ key: k }));
  api.renderComposition();
  const rows = byId.compList.children;
  rows.forEach((r, i) => { r._top = i * 40; });
  const grip = i => rows[i].children[0].children.find(c => c.className === 'comp-grip');
  const dt = () => ({ effectAllowed: '', dropEffect: '', setData() {} });
  // half: 'top' なら行の上半分（前に入れる）・'bottom' なら下半分（後ろに入れる）
  const drag = (from, to, half) => {
    grip(from).fire('dragstart', { dataTransfer: dt() });
    const ev = { preventDefault() {}, dataTransfer: dt(),
                 clientY: to * 40 + (half === 'top' ? 5 : 35) };
    rows[to].listeners['dragover'].forEach(f => f(ev));
    rows[to].listeners['drop'].forEach(f => f(ev));
  };
  return { api, byId, rows, grip, drag };
}
// El.fire は1引数しか渡さないので、dataTransfer 付きイベントを渡せるよう拡張
{
  const { rows } = dndEnv(['A']);
  void rows;
}

{
  const t = dndEnv(['ABOUT', 'MENU', 'GALLERY', 'CTA']);
  check('D1 各行につまみ（draggable なグリップ）がある',
    [0, 1, 2, 3].every(i => t.grip(i) && t.grip(i).getAttribute('draggable') === 'true'),
    'グリップ=' + [0, 1, 2, 3].map(i => !!t.grip(i)).join(','));
  check('D2 draggable はつまみだけ（行や設定パネルには付けない＝入力を邪魔しない）',
    t.rows[0].getAttribute('draggable') === null,
    '行の draggable=' + t.rows[0].getAttribute('draggable'));
}
{
  const t = dndEnv(['ABOUT', 'MENU', 'GALLERY', 'CTA']);
  t.drag(0, 2, 'bottom');   // ABOUT を GALLERY の下へ
  check('D3 先頭を3番目の下へ落とすと、その位置へ移る',
    t.api.s.map(e => e.key).join(',') === 'MENU,GALLERY,ABOUT,CTA',
    t.api.s.map(e => e.key).join(','));
}
{
  const t = dndEnv(['ABOUT', 'MENU', 'GALLERY', 'CTA']);
  t.drag(3, 1, 'top');      // CTA を MENU の前へ
  check('D4 末尾を2番目の前へ落とすと、その位置へ移る',
    t.api.s.map(e => e.key).join(',') === 'ABOUT,CTA,MENU,GALLERY',
    t.api.s.map(e => e.key).join(','));
}
{
  const t = dndEnv(['ABOUT', 'MENU', 'GALLERY']);
  t.drag(1, 1, 'top');
  const a = t.api.s.map(e => e.key).join(',');
  t.drag(1, 1, 'bottom');
  const b = t.api.s.map(e => e.key).join(',');
  check('D5 自分自身の上／下へ落としても並びが変わらない',
    a === 'ABOUT,MENU,GALLERY' && b === 'ABOUT,MENU,GALLERY', a + ' / ' + b);
}
{
  const t = dndEnv(['ABOUT', 'MENU', 'GALLERY']);
  const ev = { preventDefault() {}, dataTransfer: { dropEffect: '' }, clientY: 5 };
  t.rows[2].listeners['drop'].forEach(f => f(ev));   // dragstart 無しでいきなり drop
  check('D6 ドラッグしていないのに drop が来ても何も起きない',
    t.api.s.map(e => e.key).join(',') === 'ABOUT,MENU,GALLERY',
    t.api.s.map(e => e.key).join(','));
}
{
  const t = dndEnv(['ABOUT', 'MENU', 'GALLERY']);
  t.grip(0).fire('dragstart', { dataTransfer: { effectAllowed: '', setData() {} } });
  // 行1は top=40・高さ40 なので、下半分は y=60〜80。75 を指す。
  const ev = { preventDefault() {}, dataTransfer: { dropEffect: '' }, clientY: 75 };
  t.rows[1].listeners['dragover'].forEach(f => f(ev));
  check('D7 dragover で落とす位置の目印が付く（上半分/下半分で切り替わる）',
    t.rows[1].classList.contains('drop-after') && !t.rows[1].classList.contains('drop-before'),
    'after=' + t.rows[1].classList.contains('drop-after')
      + ' before=' + t.rows[1].classList.contains('drop-before'));
  t.rows[1].listeners['dragleave'].forEach(f => f({}));
  check('D8 dragleave で目印が消える',
    !t.rows[1].classList.contains('drop-after') && !t.rows[1].classList.contains('drop-before'),
    'after=' + t.rows[1].classList.contains('drop-after'));
}
{
  // ★dragover で preventDefault を呼ばないと、ブラウザは drop を発火しない。
  //   シムでは「呼んだかどうか」を記録して確かめる（呼び忘れは実機でしか出ない不具合になる）。
  const t = dndEnv(['ABOUT', 'MENU', 'GALLERY']);
  t.grip(0).fire('dragstart', { dataTransfer: { effectAllowed: '', setData() {} } });
  let prevented = false;
  const ev = { preventDefault() { prevented = true; }, dataTransfer: { dropEffect: '' }, clientY: 45 };
  t.rows[1].listeners['dragover'].forEach(f => f(ev));
  check('D11 dragover が preventDefault を呼ぶ（呼ばないとブラウザは drop を発火しない）',
    prevented === true, 'preventDefault 呼び出し=' + prevented);
  check('D12 dragover が dropEffect を move にする（カーソル表示が「移動」になる）',
    ev.dataTransfer.dropEffect === 'move', 'dropEffect=' + ev.dataTransfer.dropEffect);
}
{
  // ドラッグしていないときは dragover でも preventDefault しない（無関係なドロップを受けない）
  const t = dndEnv(['ABOUT', 'MENU']);
  let prevented = false;
  t.rows[1].listeners['dragover'].forEach(f =>
    f({ preventDefault() { prevented = true; }, dataTransfer: { dropEffect: '' }, clientY: 45 }));
  check('D13 ドラッグしていないときは dragover を受け付けない',
    prevented === false, 'preventDefault 呼び出し=' + prevented);
}
{
  // ↑↓ とドラッグが同じ compMove を通ること（片方だけ壊れるのを防ぐ）
  const { api: a } = makeEnv();
  a.s = [{ key: 'A' }, { key: 'B' }, { key: 'C' }];
  a.compMove(0, 3);
  check('D9 ↑↓ とドラッグが共有する compMove の意味論（from を抜いて to へ挿す）',
    a.s.map(e => e.key).join(',') === 'B,C,A', a.s.map(e => e.key).join(','));
  a.s = [{ key: 'A' }, { key: 'B' }, { key: 'C' }];
  check('D10 compMove は範囲外・移動なしのとき false を返す',
    a.compMove(-1, 1) === false && a.compMove(9, 1) === false
      && a.compMove(1, 1) === false && a.compMove(1, 2) === false,
    '範囲外=' + a.compMove(-1, 1) + ' 同位置=' + a.compMove(1, 1));
}

// ===========================================================================
// H群 — セクション別の入力例（KLK-093・理恵さんの指摘）
// ===========================================================================
{
  const { api: a, byId: b } = makeEnv();
  const inputsOf = (key) => {
    a.s = [{ key }];
    a.o = 0;
    a.renderComposition();
    const body = b.compList.children[0].children[1];
    const found = [];
    (function walk(el) {
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') found.push(el);
      el.children.forEach(walk);
    })(body);
    return found;
  };

  // 全14セクションに例文が定義されていること
  const missing = a.SECTION_KEYS.filter(k => !a.SECTION_PLACEHOLDERS[k]);
  check('H1 14セクションすべてに専用の入力例がある', missing.length === 0,
    '欠け=' + (missing.join(',') || 'なし'));

  // 見出しの例がセクションごとに違うこと（共通の使い回しでない）
  const heads = a.SECTION_KEYS.map(k => a.SECTION_PLACEHOLDERS[k].heading);
  check('H2 見出しの例がセクションごとに異なる（全部同じ文言の使い回しでない）',
    new Set(heads).size === heads.length,
    '重複=' + heads.filter((h, i) => heads.indexOf(h) !== i).join(',') || 'なし');

  // ★理恵さんが挙げた具体例
  check('H3 PRICE の見出し例が「私たちについて」ではない（理恵さんの指摘）',
    inputsOf('PRICE')[0].placeholder === '例：料金プラン',
    'PRICE の見出し例=' + inputsOf('PRICE')[0].placeholder);
  check('H4 VOICE の誘導ボタン例が「メニュー一覧へ」ではない（理恵さんの指摘）',
    inputsOf('VOICE')[2].placeholder.indexOf('メニュー一覧へ') < 0,
    'VOICE のボタン例=' + inputsOf('VOICE')[2].placeholder);
  check('H5 ABOUT / MENU は従来どおりの例文が出る（もともと合っていたものは変えない）',
    inputsOf('ABOUT')[0].placeholder === '例：私たちについて'
      && inputsOf('MENU')[2].placeholder.indexOf('メニュー一覧へ') >= 0,
    'ABOUT=' + inputsOf('ABOUT')[0].placeholder + ' / MENU=' + inputsOf('MENU')[2].placeholder);

  // 下層ページを持たないのが自然なセクションでは、ボタン例で誘導しない
  const noSub = ['FLOW', 'ACCESS', 'CONTACT', 'CTA', 'SNS', 'SEARCH'];
  const wrong = noSub.filter(k => inputsOf(k)[2].placeholder.indexOf('例：') === 0);
  check('H6 下層ページを持たないセクションはボタン例で誘導しない（欄は出す）',
    wrong.length === 0 && inputsOf('FLOW')[2].placeholder.indexOf('誘導するときだけ') >= 0,
    '誘導してしまう=' + (wrong.join(',') || 'なし'));

  // リンク先の例もセクションに合っていること
  check('H7 リンク先の例がセクションに合っている（PRICE は /price/）',
    inputsOf('PRICE')[3].placeholder.indexOf('/price/') >= 0,
    'PRICE のリンク例=' + inputsOf('PRICE')[3].placeholder);

  // 語彙外の KEY でも壊れない
  check('H8 語彙にない KEY でも既定の例文を返して壊れない',
    a.placeholdersFor('NOPE').heading === '見出し',
    JSON.stringify(a.placeholdersFor('NOPE')));
}

// --- 出力 -------------------------------------------------------------------
console.log('='.repeat(78));
console.log('KLK-087 ページ構成（composition）動的スモーク');
console.log('='.repeat(78));
let failed = 0;
for (const [name, passed, detail] of results) {
  if (!passed) failed++;
  console.log('[' + (passed ? 'PASS' : 'FAIL') + '] ' + name);
  console.log('        ' + detail);
}
console.log('-'.repeat(78));
console.log(results.length + ' checks, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
