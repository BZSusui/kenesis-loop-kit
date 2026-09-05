/*
 * KLK-094 動的スモーク（Node.js）— 参考サムネイルの段階表示（さらに表示 / 折りたたむ）。
 *
 * なぜ必要か:
 *   カタログが増えると「⑦参考にする素材」だけでページを何度もスクロールすることになる。
 *   業種未選択のときは matchesIndustry が全件 true を返すため、**初回訪問時こそ全件が並ぶ**。
 *   既定18件に畳んで「さらに表示」で開く。
 *   ★もっとも大事なのは「**選択済みは畳んでも隠さない**」こと。
 *     3枚選んだあと絞り込みを変えて選択が19番目以降に来ると、
 *     見えないのに選ばれている状態になり「なぜ3枚目が選べないのか」で詰まる。
 *
 * Run: node tests/site/smoke_klk094.node.js
 * exit 0 = all pass / 1 = fail / 2 = harness error。ネットワーク非使用・Node標準のみ。
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(path.dirname(__dirname));
const src = fs.readFileSync(path.join(ROOT, 'draft-gen', 'index.html'), 'utf8');

const START = 'function visibleThumbs';
const END = 'function renderThumbs(';
const i = src.indexOf(START);
const j = src.indexOf(END, i);
if (i < 0 || j < 0) {
  console.error('[HARNESS ERROR] visibleThumbs を抽出できません（マーカー不一致）');
  process.exit(2);
}
const visibleThumbs = new Function(src.slice(i, j) + '\nreturn visibleThumbs;')();

const results = [];
function check(name, passed, detail) { results.push([name, !!passed, detail]); }

const mk = n => Array.from({ length: n }, (_, k) => ({ id: 'cat-' + String(k + 1).padStart(4, '0') }));
const LIMIT = 18;

// --- 基本 -------------------------------------------------------------------
{
  const r = visibleThumbs(mk(56), [], LIMIT, false);
  check('T1 畳んだ状態では既定18件だけ出す（56件のカタログ）',
    r.visible.length === 18 && r.hiddenCount === 38,
    r.visible.length + '件 / 隠れ' + r.hiddenCount + '件');
}
{
  const r = visibleThumbs(mk(56), [], LIMIT, true);
  check('T2 展開すると全件出る', r.visible.length === 56 && r.hiddenCount === 0,
    r.visible.length + '件 / 隠れ' + r.hiddenCount + '件');
}
{
  const a = visibleThumbs(mk(18), [], LIMIT, false);
  const b = visibleThumbs(mk(12), [], LIMIT, false);
  check('T3 18件以下なら畳まない（隠れ0＝ボタンを出さない状態）',
    a.hiddenCount === 0 && b.hiddenCount === 0 && b.visible.length === 12,
    '18件→隠れ' + a.hiddenCount + ' / 12件→隠れ' + b.hiddenCount);
}

// --- ★選択済みを隠さない ----------------------------------------------------
{
  const r = visibleThumbs(mk(106), ['cat-0025'], LIMIT, false);
  const ids = r.visible.map(e => e.id);
  check('T4 ★19番目以降の選択済みも畳んだ状態で表示する',
    ids.indexOf('cat-0025') >= 0 && r.visible.length === 19,
    r.visible.length + '件 / cat-0025 を含む=' + (ids.indexOf('cat-0025') >= 0));
}
{
  const r = visibleThumbs(mk(106), ['cat-0020', 'cat-0050', 'cat-0080'], LIMIT, false);
  const ids = r.visible.map(e => e.id);
  check('T5 選択3枚がすべて範囲外でも全部表示する（最大3枚まで選べる仕様）',
    r.visible.length === 21
      && ['cat-0020', 'cat-0050', 'cat-0080'].every(id => ids.indexOf(id) >= 0),
    r.visible.length + '件 / 末尾=' + ids.slice(-3).join(','));
}
{
  const r = visibleThumbs(mk(106), ['cat-0050'], LIMIT, false);
  const ids = r.visible.map(e => e.id);
  check('T6 選択済みを足しても元の並び順を崩さない（末尾に寄せない）',
    ids[16] === 'cat-0017' && ids[17] === 'cat-0018' && ids[18] === 'cat-0050',
    ids.slice(16, 19).join(' '));
}
{
  const r = visibleThumbs(mk(106), ['cat-0005'], LIMIT, false);
  check('T7 選択済みが先頭18件の中にあるときは件数が増えない（二重に出さない）',
    r.visible.length === 18 && r.hiddenCount === 88,
    r.visible.length + '件 / 隠れ' + r.hiddenCount);
}

// --- 壊れた入力 --------------------------------------------------------------
{
  let threw = null;
  [null, undefined, 'x', 123, {}].forEach(v => {
    try { visibleThumbs(v, [], LIMIT, false); } catch (e) { threw = String(e); }
  });
  const empty = visibleThumbs([], [], LIMIT, false);
  const noSel = visibleThumbs(mk(30), null, LIMIT, false);
  check('T8 壊れた入力でも例外を投げない（空リスト・null・非配列）',
    threw === null && empty.visible.length === 0 && noSel.visible.length === 18,
    threw || '空=' + empty.visible.length + ' / sel=null→' + noSel.visible.length);
}

// --- 配線（描画側が純関数と件数表示・折りたたみを持つこと）--------------------
check('T9 renderThumbs が visibleThumbs を通している',
  src.indexOf('const shown = visibleThumbs(list, selectedIds, THUMBS_COLLAPSED_LIMIT, thumbsExpanded);') >= 0,
  '配線=' + (src.indexOf('visibleThumbs(list, selectedIds') >= 0));
check('T10 「さらに表示」「折りたたむ」の両方がある（開いたら戻せる）',
  src.indexOf('さらに表示する（残り ') >= 0 && src.indexOf('折りたたむ（先頭 ') >= 0,
  'さらに表示=' + (src.indexOf('さらに表示する（残り ') >= 0)
    + ' / 折りたたむ=' + (src.indexOf('折りたたむ（先頭 ') >= 0));
check('T11 何件中何件を表示しているか出す（これで全部かが分かる）',
  src.indexOf("' 件中 '") >= 0 && src.indexOf("' 件を表示中'") >= 0,
  '件数表示=' + (src.indexOf("' 件中 '") >= 0));
check('T12 18件以下ならボタン自体を出さない',
  src.indexOf('if (total <= THUMBS_COLLAPSED_LIMIT) { host.hidden = true; return; }') >= 0,
  '非表示=' + (src.indexOf('if (total <= THUMBS_COLLAPSED_LIMIT)') >= 0));
check('T13 絞り込み・業種・テイストを変えたら畳んだ状態へ戻す',
  src.indexOf('function resetThumbsExpansion()') >= 0
    && src.indexOf('function refilterThumbs() { resetThumbsExpansion(); applyThumbFilter(); }') >= 0
    && src.indexOf("addEventListener('change', refilterThumbs)") >= 0,
  'reset=' + (src.indexOf('function resetThumbsExpansion()') >= 0)
    + ' / 結線=' + (src.indexOf("addEventListener('change', refilterThumbs)") >= 0));
check('T14 既定の表示件数が18（6列×3行の目安）',
  src.indexOf('THUMBS_COLLAPSED_LIMIT = 18') >= 0,
  '既定=' + (src.indexOf('THUMBS_COLLAPSED_LIMIT = 18') >= 0));

// --- 出力 -------------------------------------------------------------------
console.log('='.repeat(78));
console.log('KLK-094 参考サムネイルの段階表示 動的スモーク');
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
