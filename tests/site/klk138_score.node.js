#!/usr/bin/env node
/*
 * KLK-138 言葉と色の物差し — ベースラインの採点 CLI（Node 標準のみ）
 *
 *   node tests/site/klk138_score.node.js                    # 日本語の表を表示
 *   node tests/site/klk138_score.node.js --json             # JSON を標準出力へ
 *   node tests/site/klk138_score.node.js --write-baseline --label v1.3 [--compare-with v1.2]
 *                                                           # tests/fixtures/klk138/baseline-{label}.json に書き出す
 *   node tests/site/klk138_score.node.js --check            # 現行版（生成側の指紋が一致する1件）の再現確認
 *
 * ベースラインは生成側の版ごとに1ファイル。指紋が今の生成側と一致するものが「現行版」、ほかは「過去版」。
 * 過去版は上書きしない（指紋の違う既存ファイルへの書き出しは拒否）。
 *
 * 終了コード: 0=正常（得点率がいくつでも 0）／1=再現確認の不一致・書き出しの拒否／2=ハーネス異常・使い方の誤り
 * 設計: docs/designs/KLK-138.md §4.7・§4.8、docs/designs/KLK-140.md §4.8（M1: ラベル・過去版・比較の小計）
 */
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const R = require('./klk138_ruler.js');
const Gen = require('./klk138_generator.js');

const BASE_DIR = path.join(R.ROOT, 'tests', 'fixtures', 'klk138');
const LABEL_RE = /^v\d+(\.\d+)+$/;
const FILE_RE = /^baseline-(v\d+(?:\.\d+)+)\.json$/;
const UNRECORDED = '未記録';
const REF_SEEDS = Array.from({ length: 32 }, (_, i) => i + 1);
const AGE_VARIANT = { word: 'かわいい', age: 0.4 };
const NO_DICT_STATUS = '辞書なし（新設予定）';

function rulerSha() {
  return crypto.createHash('sha256').update(fs.readFileSync(R.RULER_PATH)).digest('hex').slice(0, 16);
}

function rolesStr(res) {
  const r = res.roles;
  const cell = x => (typeof x === 'string' ? x : x.cell);
  const bg = typeof r.bg === 'string' ? r.bg : 'L' + r.bg.L.toFixed(2);
  return { main: cell(r.main), sub: cell(r.sub), accent: cell(r.accent), bg };
}

function scoreWord(gen, ruler, word, seed, age) {
  const def = ruler.words[word];
  const pals = gen.generate({ dictLabel: def.dictLabel, age, seed });
  const results = R.scoreSet(word, pals, ruler, { age });   // KLK-140 改善ループ2: 3案まとめて（明るい背景の例外）
  return pals.map((p, i) => {
    const res = results[i];
    return { seed, scheme: p.scheme, verdict: res.verdict, points: res.points, roles: rolesStr(res), penalties: res.penalties };
  });
}

function baselinePath(label) {
  return path.join(BASE_DIR, 'baseline-' + label + '.json');
}

// baseline-*.json をすべて読む。[{ label, file, data }]（ラベル順）
function listBaselines() {
  if (!fs.existsSync(BASE_DIR)) return [];
  return fs.readdirSync(BASE_DIR).filter(f => FILE_RE.test(f)).sort().map(f => {
    const file = path.join(BASE_DIR, f);
    let data;
    try { data = JSON.parse(fs.readFileSync(file, 'utf8')); } catch (e) {
      throw new Gen.HarnessError(f + ' が読めない: ' + e.message);
    }
    return { label: FILE_RE.exec(f)[1], file, data };
  });
}

function currentBaselines(fingerprint) {
  return listBaselines().filter(b => b.data && b.data.generator && b.data.generator.fingerprint === fingerprint);
}

// 比較の小計（KLK-140 §4.8.3）。prev は比較対象のベースライン（過去版）
function comparisonOf(prev, withLabel, primaryWords, refWords) {
  const words = Object.keys(prev.primary.words).filter(w => prev.primary.words[w].rate !== null).sort();
  let b0 = [], passed = 0, refSum = 0, refCount = 0;
  for (const w of words) {
    const d = primaryWords[w];
    if (!d || d.rate === null) throw new Gen.HarnessError('比較対象の語が採点されていない: ' + w);
    b0 = b0.concat(d.palettes);
    if (d.pass) passed++;
    refSum += refWords[w].sum; refCount += refWords[w].count;
  }
  const primary = { rate: R.r4(R.rateOf(b0)), palettes: b0.length, wordsPassed: passed,
    prevRate: prev.primary.overall.rate, prevWordsPassed: prev.primary.overall.wordsPassed };
  const reference = { rate: R.r4(refSum / refCount), palettes: refCount, prevRate: prev.reference.overall.rate };
  const notLower = primary.rate >= primary.prevRate && primary.wordsPassed >= primary.prevWordsPassed &&
    reference.rate >= reference.prevRate;
  return { with: withLabel, words, primary, reference, notLower };
}

function readBaseline(label) {
  const file = baselinePath(label);
  if (!fs.existsSync(file)) return null;
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch (e) {
    throw new Gen.HarnessError(path.basename(file) + ' が読めない: ' + e.message);
  }
}

function compute({ withValidation, label, compareWith }) {
  const ruler = R.loadRuler();
  const gen = Gen.load();
  const passMin = ruler.scoring.wordPassMin;
  const words = Object.keys(ruler.words);
  const scored = words.filter(w => ruler.words[w].dictLabel);
  for (const w of scored) {
    if (!gen.hasLabel(ruler.words[w].dictLabel)) throw new Gen.HarnessError('辞書ラベルが生成側に無い: ' + ruler.words[w].dictLabel);
  }

  if (label === undefined) {
    // 表示・--json: 現行版のラベルと、その比較対象（comparison.with）を使う
    const cur = currentBaselines(gen.fingerprint);
    label = cur.length === 1 ? cur[0].label : UNRECORDED;
    if (compareWith === undefined && cur.length === 1 && cur[0].data.comparison) compareWith = cur[0].data.comparison.with;
  }

  // 主条件 B0
  const primaryWords = {};
  let all = [];
  let passed = 0;
  for (const w of words) {
    const def = ruler.words[w];
    if (!def.dictLabel) {
      primaryWords[w] = { dictLabel: null, status: NO_DICT_STATUS, rate: null };
      continue;
    }
    const pals = scoreWord(gen, ruler, w, gen.initialSeed, 0);
    const rate = R.rateOf(pals);
    const pass = rate >= passMin - 1e-12;
    if (pass) passed++;
    all = all.concat(pals);
    primaryWords[w] = { dictLabel: def.dictLabel, rate: R.r4(rate), pass, palettes: pals };
  }
  const primary = {
    overall: { rate: R.r4(R.rateOf(all)), palettes: all.length, wordsPassed: passed, wordsScored: scored.length },
    words: primaryWords,
  };

  // 追加条件 B0-age
  const agePals = scoreWord(gen, ruler, AGE_VARIANT.word, gen.initialSeed, AGE_VARIANT.age);
  const ageVariant = { [AGE_VARIANT.word]: { age: AGE_VARIANT.age, rate: R.r4(R.rateOf(agePals)), palettes: agePals } };

  // 参考条件 B1
  let refAll = [];
  const bySchemeAcc = {};
  const refWordAcc = {};
  for (const w of scored) refWordAcc[w] = { sum: 0, count: 0 };
  for (const seed of REF_SEEDS) for (const w of scored) {
    const pals = scoreWord(gen, ruler, w, seed, 0);
    refAll = refAll.concat(pals);
    for (const p of pals) { refWordAcc[w].sum += p.points; refWordAcc[w].count++; }
    for (const p of pals) {
      const a = bySchemeAcc[p.scheme] || (bySchemeAcc[p.scheme] = { sum: 0, count: 0 });
      a.sum += p.points; a.count++;
    }
  }
  const bySchemes = {};
  for (const k of Object.keys(bySchemeAcc).sort()) bySchemes[k] = { rate: R.r4(bySchemeAcc[k].sum / bySchemeAcc[k].count), count: bySchemeAcc[k].count };
  const refByWord = {};
  for (const w of scored) refByWord[w] = { rate: R.r4(refWordAcc[w].sum / refWordAcc[w].count), palettes: refWordAcc[w].count };
  const reference = { seeds: REF_SEEDS, overall: { rate: R.r4(R.rateOf(refAll)), palettes: refAll.length }, bySchemes,
    words: refByWord };

  const out = {
    schema: 'klk138-baseline',
    version: 2,
    generator: { file: 'palette/index.html', label, fingerprint: gen.fingerprint, initialSeed: gen.initialSeed },
    ruler: { version: ruler.version, sha256: rulerSha() },
    primary, ageVariant, reference,
  };
  if (compareWith) {
    const prev = readBaseline(compareWith);
    if (!prev) throw new Gen.HarnessError('比較対象のベースラインが無い: baseline-' + compareWith + '.json');
    out.comparison = comparisonOf(prev, compareWith, primaryWords, refWordAcc);
  }
  if (withValidation) {
    const data = R.loadJudgmentData();
    out.rulerValidation = data ? R.publicValidation(R.validateAgainstHumans(ruler, data)) : null;
  }
  return out;
}

const SYM = { ok: '○', maybe: '△', ng: '×' };

function printTable(b) {
  const pct = x => (x === null || x === undefined ? '—' : (x * 100).toFixed(1) + '%');
  console.log('='.repeat(72));
  console.log(`KLK-138 言葉と色の物差し — 現行版 ${b.generator.label} のベースライン`);
  console.log(`生成側 fingerprint=${b.generator.fingerprint} 初期シード=${b.generator.initialSeed} / ruler v${b.ruler.version} sha=${b.ruler.sha256}`);
  console.log('='.repeat(72));
  console.log('\n[主条件 B0] 1語・スライダー0・初期シード・3案（○=1 △=0.5 ×=0、語は得点率 0.75 以上で合格）');
  const words = b.primary.words;
  for (const w of Object.keys(words)) {
    const d = words[w];
    if (d.rate === null) continue;
    const marks = d.palettes.map(p => SYM[p.verdict]).join('');
    console.log(`  ${d.pass ? '合格  ' : '不合格'} ${pct(d.rate).padStart(6)}  ${marks}  ${w}（辞書: ${d.dictLabel}）`);
  }
  const o = b.primary.overall;
  console.log(`\n  全体の合格率（${o.wordsScored}語・${o.palettes}案の平均）: ${pct(o.rate)}   合格した語: ${o.wordsPassed} / ${o.wordsScored}`);
  const noDict = Object.keys(words).filter(w => words[w].rate === null);
  if (noDict.length) {
    console.log('\n[辞書なし] 採点しない（分母に入れない）');
    for (const w of noDict) console.log(`  ${words[w].status}  ${w}`);
  }
  console.log('\n[追加条件 B0-age]（参考行。分母に入れない）');
  for (const w of Object.keys(b.ageVariant)) {
    const a = b.ageVariant[w];
    console.log(`  ${w}（大人かわいい・age=${a.age}）: ${pct(a.rate)}  ${a.palettes.map(p => SYM[p.verdict]).join('')}`);
  }
  const nRef = Object.keys(b.reference.words || {}).length || o.wordsScored;
  console.log(`\n[参考条件 B1] シード ${b.reference.seeds[0]}〜${b.reference.seeds[b.reference.seeds.length - 1]} × ${nRef}語 × 3案 = ${b.reference.overall.palettes}案: ${pct(b.reference.overall.rate)}`);
  for (const k of Object.keys(b.reference.bySchemes)) {
    const s = b.reference.bySchemes[k];
    console.log(`  ${pct(s.rate).padStart(6)}  出現 ${String(s.count).padStart(4)}  ${k}`);
  }
  if (b.reference.words) {
    console.log('  語ごと:');
    for (const w of Object.keys(b.reference.words)) {
      const s = b.reference.words[w];
      console.log(`  ${pct(s.rate).padStart(6)}  ${String(s.palettes).padStart(4)}案  ${w}`);
    }
  }
  if (b.comparison) {
    const c = b.comparison;
    console.log(`\n[比較] 既存${c.words.length}語（${c.with} と同じ語）: B0 ${pct(c.primary.prevRate)}→${pct(c.primary.rate)}・` +
      `合格 ${c.primary.prevWordsPassed}→${c.primary.wordsPassed}／B1 ${pct(c.reference.prevRate)}→${pct(c.reference.rate)}` +
      `（${c.notLower ? '下回らない' : '下回る'}）`);
  }
  if (b.rulerValidation !== undefined) {
    console.log('\n[物差しの検証] 人間の判定との一致（§4.9）');
    if (!b.rulerValidation) console.log('  [SKIP] 判定データが無い（Git除外）');
    else {
      for (const k of Object.keys(b.rulerValidation)) {
        const v = b.rulerValidation[k];
        let line = `  ${k.padEnd(9)} n=${String(v.n).padStart(3)} 完全一致 ${v.exact} 隣接一致 ${v.adjacent} 逆転 ${v.reversal} 平均絶対誤差 ${v.mae}（全部△ ${v.maeAllMaybe}）`;
        if (k === 'V-G') line += ` 人間 ${v.humanRate} 物差し ${v.rulerRate} 差 ${v.diff}`;
        console.log(line);
      }
      const t = R.checkTargets(b.rulerValidation);
      const ng = t.filter(x => !x.ok);
      console.log(ng.length ? '  目安に届かない: ' + ng.map(x => `${x.set} ${x.key}=${x.value}（目安 ${x.op} ${x.th}）`).join('、') : '  目安: すべて満たす');
    }
  }
}

function stable(o) {
  return JSON.stringify(o, null, 2) + '\n';
}

function argValue(argv, name) {
  const i = argv.indexOf(name);
  if (i < 0) return undefined;
  return i + 1 < argv.length && !argv[i + 1].startsWith('--') ? argv[i + 1] : '';
}

const USAGE = '使い方: node tests/site/klk138_score.node.js --write-baseline --label v1.3 [--compare-with v1.2]';

function main(argv) {
  try {
    if (argv.includes('--check')) {
      const gen = Gen.load();
      const all = listBaselines();
      const cur = all.filter(b => b.data && b.data.generator && b.data.generator.fingerprint === gen.fingerprint);
      if (!cur.length) {
        const labels = all.map(b => b.label).join(', ') || 'なし';
        console.log(`[SKIP] 生成側が記録済みのどの版（${labels}）とも違う。--write-baseline --label で新しい版を記録すること`);
        return 0;
      }
      if (cur.length > 1) {
        console.error('[NG] 今の生成側と指紋が一致するベースラインが複数ある: ' + cur.map(b => b.label).join(', '));
        return 1;
      }
      const base = cur[0].data;
      const withLabel = base.comparison ? base.comparison.with : undefined;
      const now = compute({ withValidation: false, label: cur[0].label, compareWith: withLabel });
      const keys = ['schema', 'version', 'generator', 'ruler', 'primary', 'ageVariant', 'reference'];
      if (base.comparison) keys.push('comparison');
      const diff = keys.filter(k => JSON.stringify(base[k]) !== JSON.stringify(now[k]));
      if (diff.length) {
        console.error(`[NG] ベースライン ${cur[0].label} が再現しない: ` + diff.join(', '));
        return 1;
      }
      console.log(`[OK] ベースライン ${base.generator.label} を再現（全体 ${now.primary.overall.rate}・合格 ${now.primary.overall.wordsPassed}/${now.primary.overall.wordsScored}）`);
      return 0;
    }
    if (argv.includes('--write-baseline')) {
      const label = argValue(argv, '--label');
      const compareWith = argValue(argv, '--compare-with');
      if (!label || !LABEL_RE.test(label)) { console.error('[NG] --label が無いか形式が違う（例 v1.3）\n' + USAGE); return 2; }
      if (compareWith !== undefined && (!compareWith || !LABEL_RE.test(compareWith))) {
        console.error('[NG] --compare-with の形式が違う（例 v1.2）\n' + USAGE); return 2;
      }
      if (compareWith !== undefined && !fs.existsSync(baselinePath(compareWith))) {
        console.error('[NG] 比較対象のベースラインが無い: baseline-' + compareWith + '.json'); return 2;
      }
      const gen = Gen.load();
      const all = listBaselines();
      const same = all.find(b => b.label === label);
      if (same && !(same.data && same.data.generator && same.data.generator.fingerprint === gen.fingerprint)) {
        console.error(`[NG] 記録済みの過去版 ${label} は上書きしない（生成側の指紋が違う）`);
        return 1;
      }
      const other = all.find(b => b.label !== label && b.data && b.data.generator && b.data.generator.fingerprint === gen.fingerprint);
      if (other) {
        console.error(`[NG] 同じ生成側が ${other.label} として記録済み。書き出さない`);
        return 1;
      }
      const b = compute({ withValidation: true, label, compareWith });
      fs.mkdirSync(BASE_DIR, { recursive: true });
      fs.writeFileSync(baselinePath(label), stable(b), 'utf8');
      console.log('wrote ' + path.relative(R.ROOT, baselinePath(label)));
      return 0;
    }
    if (argv.includes('--json')) {
      process.stdout.write(stable(compute({ withValidation: true })));
      return 0;
    }
    printTable(compute({ withValidation: true }));
    return 0;
  } catch (e) {
    console.error('[HARNESS ERROR] ' + (e && e.message ? e.message : e));
    return 2;
  }
}

process.exitCode = main(process.argv.slice(2));
