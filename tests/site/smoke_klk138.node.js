#!/usr/bin/env node
/*
 * KLK-138 言葉と色の物差し — 自己検査＋人間の判定との一致（Node 標準のみ）
 *
 *   T1 変換の基準値（OKLCH・HSV・HSL）
 *   T2 マスの自己判定（108格子マス＋無彩色・金属8マス = 116/116）
 *   T3 ruler.json の整合（20語・ok/maybe が重ならない・マスIDが格子にある・辞書ラベルが生成側にある）
 *   T4 規則の分岐（格子マスの代表色から組んだ合成の案。判定データの色は使わない）
 *   T5 決定性（同じ入力で2回採点して一致）
 *   一致検査 V-M / V-G / V-C / V-E（tickets/work/KLK-138/ の判定データがあるときだけ。無ければ SKIP で合格）
 *
 * 実行: node tests/site/smoke_klk138.node.js
 * 終了コード: 0=全PASS / 1=FAILあり / 2=ハーネス異常
 * 設計: docs/designs/KLK-138.md §4.8・§4.9
 */
'use strict';
const R = require('./klk138_ruler.js');
const Gen = require('./klk138_generator.js');

const results = [];
function check(name, cond, detail) {
  results.push({ name, ok: !!cond, detail: detail || '' });
}
const near = (a, b, tol) => Math.abs(a - b) <= tol;

let ruler, gen;
try {
  ruler = R.loadRuler();
  gen = Gen.load();
} catch (e) {
  console.error('[HARNESS ERROR] ' + e.message);
  process.exit(2);
}
const rep = id => R.cellRepHex(id, ruler);

// ---- T1 変換の基準値 -------------------------------------------------------
{
  const w = R.rgbToOklch(R.hexToRgb('#ffffff'));
  check('T1 白 → OKLCH L=1.000±0.001・C<0.001', near(w[0], 1, 0.001) && w[1] < 0.001, w.map(x => x.toFixed(4)).join(','));
  const k = R.rgbToOklch(R.hexToRgb('#000000'));
  check('T1 黒 → OKLCH L=0.000±0.001', near(k[0], 0, 0.001), k[0].toFixed(4));
  const r = R.rgbToOklch(R.hexToRgb('#ff0000'));
  check('T1 赤 → OKLCH L=0.628±0.001・C=0.258±0.001・h=29.2±0.3',
    near(r[0], 0.628, 0.001) && near(r[1], 0.258, 0.001) && near(r[2], 29.2, 0.3), r.map(x => x.toFixed(4)).join(','));
  const v = R.rgbToHsv(R.hexToRgb('#ff0000'));
  check('T1 赤 → HSV (0, 1, 1)', v[0] === 0 && v[1] === 1 && v[2] === 1, v.join(','));
  const g = R.rgbToHsl(R.hexToRgb('#808080'));
  check('T1 灰 → HSL s=0', g[1] === 0, g.join(','));
}

// ---- T2 マスの自己判定 -----------------------------------------------------
{
  const ids = [];
  for (const t of ruler.grid.tones) for (const h of ruler.grid.hues) ids.push(`${t.key}-${String(h).padStart(3, '0')}`);
  for (const n of ruler.grid.neutrals) ids.push(`n-${n.key}`);
  const bad = ids.filter(id => R.classify(rep(id), ruler).cell !== id);
  check(`T2 116マスの代表色が自分のIDに判定される（${ids.length - bad.length}/${ids.length}）`,
    ids.length === 116 && bad.length === 0, bad.join(' '));
}

// ---- T3 ruler.json の整合 --------------------------------------------------
{
  const words = Object.keys(ruler.words);
  check('T3 代表語が20語ちょうど', words.length === 20, String(words.length));
  const gridIds = new Set();
  for (const t of ruler.grid.tones) for (const h of ruler.grid.hues) gridIds.add(`${t.key}-${String(h).padStart(3, '0')}`);
  for (const n of ruler.grid.neutrals) gridIds.add(`n-${n.key}`);
  const overlap = [], unknown = [];
  for (const w of words) {
    const d = ruler.words[w];
    if (d.kind !== 'cells') continue;
    const ok = new Set(d.cells.ok);
    for (const c of d.cells.maybe) if (ok.has(c)) overlap.push(`${w}:${c}`);
    const all = d.cells.ok.concat(d.cells.maybe, ...(d.okWhen || []).map(x => x.cells));
    for (const c of all) if (!gridIds.has(c)) unknown.push(`${w}:${c}`);
  }
  check('T3 cells 語の ok と maybe が重ならない', overlap.length === 0, overlap.join(' '));
  check('T3 すべてのマスIDが格子にある', unknown.length === 0, unknown.join(' '));
  const withDict = words.filter(w => ruler.words[w].dictLabel);
  const missing = withDict.filter(w => !gen.hasLabel(ruler.words[w].dictLabel));
  check(`T3 辞書あり${withDict.length}語の dictLabel が生成側の辞書にある`, withDict.length === 16 && missing.length === 0, missing.join(' '));
}

// ---- T4 規則の分岐（合成の案） ---------------------------------------------
function pal(bg, main, sub, accent) {
  return { bg: rep(bg), main: rep(main), sub: rep(sub), accent: rep(accent) };
}
function expect(name, word, p, want, ctx, wantPenalty) {
  let res;
  try { res = R.scorePalette(word, p, ruler, ctx || {}); } catch (e) { check('T4 ' + name, false, e.message); return; }
  const penOk = !wantPenalty || res.penalties.includes(wantPenalty);
  check(`T4 ${name} → ${want}${wantPenalty ? '（' + wantPenalty + '）' : ''}`, res.verdict === want && penOk,
    `got ${res.verdict} [${res.penalties.join(',')}]`);
}
// cells
expect('cells ○（全役割が範囲内）', 'かわいい', pal('n-white', 'light-330', 'pale-150', 'pale-000'), 'ok');
expect('cells △（メインが△のマス）', 'かわいい', pal('n-white', 'n-gray', 'pale-150', 'pale-000'), 'maybe');
expect('cells ×（メインが範囲外）', 'かわいい', pal('n-white', 'dark-240', 'pale-150', 'pale-000'), 'ng');
expect('cells △（サブが範囲外）', 'かわいい', pal('n-white', 'light-330', 'dark-240', 'pale-000'), 'maybe');
expect('cells かわいい age=0 で条件つきマスは△', 'かわいい', pal('n-white', 'dull-330', 'pale-150', 'pale-000'), 'maybe', { age: 0 });
expect('cells かわいい age=0.4 で条件つきマスは○', 'かわいい', pal('n-white', 'dull-330', 'pale-150', 'pale-000'), 'ok', { age: 0.4 });
expect('cells 背景 light に暗い背景 ×', 'さわやか', pal('dark-210', 'pale-180', 'n-white', 'pale-180'), 'ng');
expect('cells 背景 light に中間の背景 △', 'さわやか', pal('n-gray', 'pale-180', 'n-white', 'pale-180'), 'maybe');
expect('cells 背景 dark に明るい背景 ×', '高級感', pal('n-white', 'dark-270', 'n-charcoal', 'n-gold'), 'ng');
expect('cells 背景 dark に暗い背景 ○', '高級感', pal('n-black', 'dark-270', 'n-charcoal', 'n-gold'), 'ok');
expect('蛍光 standard: サブ1つ △', 'かわいい', pal('n-white', 'light-330', 'vivid-120', 'pale-000'), 'maybe', {}, 'neon:sub');
expect('蛍光 standard: 2つ ×', 'かわいい', pal('n-white', 'light-330', 'vivid-120', 'vivid-180'), 'ng', {}, 'neon:accent');
expect('蛍光 allow: メインが蛍光でも ○', 'ポップ', pal('n-white', 'vivid-120', 'light-000', 'bright-000'), 'ok');
{
  const p = pal('n-white', 'vivid-120', 'light-000', 'bright-000');
  const def = Object.assign({}, ruler.words['ポップ'], { neonPolicy: 'standard' });
  const res = R.scoreCells(p, def, ruler, {});
  check('T4 蛍光 standard: メインが蛍光なら × → ng', res.verdict === 'ng' && res.penalties.includes('neon:main'), `got ${res.verdict}`);
}
expect('蛍光 accentOnly: アクセントの蛍光は数えない ○', '情熱的な', pal('n-white', 'vivid-000', 'n-white', 'vivid-120'), 'ok');
expect('蛍光 accentOnly: サブの蛍光は数える △', '情熱的な', pal('n-white', 'vivid-000', 'vivid-120', 'n-black'), 'maybe', {}, 'neon:sub');
{
  // 暖色 weak: 語の範囲（○△）から鮮やかな暖色（蛍光でない）のマスを選び、アクセントに置く
  const word = Object.keys(ruler.words).find(w => {
    const d = ruler.words[w];
    return d.kind === 'cells' && d.warmAccentPolicy === 'weak' && d.cells.ok.concat(d.cells.maybe).some(c => R.isWarmVivid(rep(c), ruler) && !R.isNeon(rep(c), ruler));
  });
  if (!word) check('T4 暖色 weak の対象マスがある', false, 'なし');
  else {
    const d = ruler.words[word];
    const warmCell = d.cells.ok.concat(d.cells.maybe).find(c => R.isWarmVivid(rep(c), ruler) && !R.isNeon(rep(c), ruler));
    const coolCell = d.cells.ok.find(c => !R.isWarmVivid(rep(c), ruler) && !R.isNeon(rep(c), ruler));
    const bg = d.bg === 'dark' ? 'n-black' : 'n-white';
    expect(`暖色 weak: ${word} の鮮やかな暖色アクセントで ○→△`, word, pal(bg, coolCell, coolCell, warmCell), 'maybe', {}, 'warmAccent');
    expect(`暖色 weak: ${word} の寒色アクセントは ○`, word, pal(bg, coolCell, coolCell, coolCell), 'ok');
    const none = Object.assign({}, d, { warmAccentPolicy: 'none' });
    const res = R.scoreCells(pal(bg, coolCell, coolCell, warmCell), none, ruler, {});
    check('T4 暖色 none: 同じ案が ○', res.verdict === 'ok', `got ${res.verdict}`);
  }
}
// elegant
// エレガント型A（改訂 2026-11-26: 設計 §4.8 の7件）
expect('エレガント 型A ○', 'エレガント', pal('n-white', 'grayish-300', 'pale-300', 'dull-300'), 'ok');
expect('エレガント 型A 中くらいの鮮やかさ △', 'エレガント', pal('n-white', 'soft-300', 'pale-300', 'dull-300'), 'maybe', {}, 'semiVividMain');
expect('エレガント 型A 鮮やかすぎるメイン ×', 'エレガント', pal('n-white', 'bright-270', 'pale-300', 'dull-300'), 'ng', {}, 'vividMain');
expect('エレガント 型A 暗い背景＋暗いアクセント △', 'エレガント', pal('dark-270', 'soft-330', 'pale-300', 'dull-300'), 'maybe', {}, 'darkBgAccent');
expect('エレガント 型A 暗い背景＋明るいアクセント＋明るいメイン ○', 'エレガント', pal('dark-270', 'soft-330', 'dull-300', 'pale-300'), 'ok');
expect('エレガント 型A 暗い背景＋明るいアクセント＋暗いメイン △', 'エレガント', pal('dark-270', 'dark-300', 'dull-300', 'pale-300'), 'maybe', {}, 'darkBgMain');
expect('エレガント 型A 明るい背景なら暗いメインでも ○', 'エレガント', pal('n-white', 'dark-300', 'pale-300', 'dull-300'), 'ok');
expect('エレガント 型B 濃い一点あり ○', 'エレガント', pal('n-white', 'soft-030', 'pale-030', 'n-black'), 'ok');
expect('エレガント 型B 濃い一点なし △', 'エレガント', pal('n-white', 'soft-030', 'pale-030', 'n-gold'), 'maybe', {}, 'noDarkPoint');
expect('エレガント どちらでもない ×', 'エレガント', pal('n-white', 'dark-240', 'n-charcoal', 'n-gold'), 'ng');
expect('エレガント 蛍光1つで ×', 'エレガント', pal('n-white', 'soft-300', 'pale-300', 'vivid-180'), 'ng', {}, 'neon:accent');
// combo
expect('かっこいい モノトーン＋寒色アクセント ○', 'かっこいい', pal('n-white', 'n-black', 'n-gray', 'bright-210'), 'ok');
expect('かっこいい 鮮やかな暖色アクセント △', 'かっこいい', pal('n-white', 'n-black', 'n-gray', 'bright-030'), 'maybe', {}, 'warmAccent');
expect('かっこいい モノトーンでないメイン △', 'かっこいい', pal('n-white', 'dull-210', 'n-gray', 'bright-210'), 'maybe', {}, 'notMono');
expect('かっこいい パステルのメイン ×', 'かっこいい', pal('n-white', 'light-210', 'n-gray', 'bright-210'), 'ng', {}, 'pastelMain');
expect('かっこいい カラフル ×', 'かっこいい', pal('n-white', 'deep-120', 'deep-240', 'bright-000'), 'ng', {}, 'colorful');
expect('かっこいい 蛍光 ×', 'かっこいい', pal('n-white', 'n-black', 'n-gray', 'vivid-180'), 'ng', {}, 'neon:accent');
expect('かっこいい クリームの背景でも ○', 'かっこいい', pal('pale-000', 'n-black', 'n-gray', 'bright-210'), 'ok');
expect('スタイリッシュ クリームの背景 ×', 'スタイリッシュ', pal('pale-000', 'n-black', 'n-gray', 'bright-210'), 'ng', {}, 'creamBg');
expect('スタイリッシュ モノトーン＋寒色アクセント ○', 'スタイリッシュ', pal('n-white', 'n-black', 'n-gray', 'bright-210'), 'ok');
expect('シンプル 低彩度・少ない色相 ○', 'シンプル', pal('n-white', 'n-lgray', 'pale-210', 'n-gray'), 'ok');
expect('シンプル 純黒を含む △', 'シンプル', pal('n-white', 'n-lgray', 'pale-210', 'n-black'), 'maybe', {}, 'pureBlack');
expect('シンプル 金を含む △', 'シンプル', pal('n-white', 'n-lgray', 'pale-210', 'n-gold'), 'maybe', {}, 'metal');
expect('シンプル 鮮やか2色以上 ×', 'シンプル', pal('n-white', 'n-lgray', 'bright-000', 'bright-210'), 'ng', {}, 'vivid>=2');
expect('シンプル メインが金 ×', 'シンプル', pal('n-white', 'n-gold', 'pale-210', 'n-gray'), 'ng', {}, 'metalMain');
expect('シンプル メインが銀の代表色でほかの条件を満たす ○（銀は金属として扱わない）', 'シンプル', pal('n-white', 'n-silver', 'pale-210', 'n-gray'), 'ok');
expect('シンプル 蛍光 ×', 'シンプル', pal('n-white', 'n-lgray', 'pale-210', 'vivid-180'), 'ng', {}, 'neon:accent');

// ---- T5 決定性 -------------------------------------------------------------
{
  const run = () => {
    const out = [];
    for (const w of Object.keys(ruler.words)) {
      const d = ruler.words[w];
      if (!d.dictLabel || !gen.hasLabel(d.dictLabel)) continue; // 辞書に無いラベルは T3 で FAIL として報告する
      for (const seed of [gen.initialSeed, 1, 2]) {
        for (const p of gen.generate({ dictLabel: d.dictLabel, seed })) out.push(R.scorePalette(w, p, ruler, {}));
      }
    }
    return JSON.stringify(out);
  };
  const a = run(), b = run();
  check('T5 同じ入力で2回採点して結果が一致する', a === b, '');
  check('T5 初期シードが index.html の式どおり 73294978', gen.initialSeed === 73294978, String(gen.initialSeed));
}

// ---- 一致検査（判定データがあるときだけ） ------------------------------------
let validation = null;
let data = null, partial = null;
try { data = R.loadJudgmentData(); } catch (e) {
  if (e instanceof R.PartialDataError) partial = e.message; else throw e;
}
if (partial) {
  check('V 判定データが一部だけ欠けていない（全部ある／全部無い のどちらか）', false, partial);
} else if (!data) {
  check('V 人間の判定との一致 [SKIP] 判定データが無い（Git除外）', true);
} else {
  validation = R.validateAgainstHumans(ruler, data);
  for (const t of R.checkTargets(validation)) {
    const miss = t.set === 'V-G' ? '' : validation[t.set]._mismatches.map(m => `${m.id}(${m.source}) 人間${m.human}/物差し${m.ruler}`).join(' ');
    check(`${t.set} ${t.key}=${t.value}（目安 ${t.op} ${t.th}）`, t.ok, t.ok ? '' : '外れた案: ' + miss);
  }
}

// ---- 結果 ------------------------------------------------------------------
console.log('='.repeat(78));
console.log('KLK-138 言葉と色の物差し 自己検査（T1-T5）＋人間の判定との一致');
console.log('='.repeat(78));
for (const r of results) {
  console.log(`[${r.ok ? 'PASS' : 'FAIL'}] ${r.name}${!r.ok && r.detail ? '\n       ' + r.detail : ''}`);
}
if (validation) {
  console.log('-'.repeat(78));
  for (const k of Object.keys(validation)) {
    const v = validation[k];
    let line = `${k.padEnd(9)} n=${String(v.n).padStart(3)} 完全一致 ${v.exact} 隣接 ${v.adjacent} 逆転 ${v.reversal} MAE ${v.mae}（全部△ ${v.maeAllMaybe}）`;
    if (k === 'V-G') line += ` 人間 ${v.humanRate} 物差し ${v.rulerRate} 差 ${v.diff}`;
    console.log(line);
  }
}
const fails = results.filter(r => !r.ok).length;
console.log('-'.repeat(78));
console.log(`${results.length - fails}/${results.length} PASS`);
process.exit(fails ? 1 : 0);
