#!/usr/bin/env node
/*
 * KLK-138 言葉と色の物差し — ベースラインの採点 CLI（Node 標準のみ）
 *
 *   node tests/site/klk138_score.node.js                    # 日本語の表を表示
 *   node tests/site/klk138_score.node.js --json             # JSON を標準出力へ
 *   node tests/site/klk138_score.node.js --write-baseline   # tests/fixtures/klk138/baseline-v1.2.json に書き出す
 *   node tests/site/klk138_score.node.js --check            # 再現確認
 *
 * 終了コード: 0=正常（得点率がいくつでも 0）／1=再現確認の不一致／2=ハーネス異常
 * 設計: docs/designs/KLK-138.md §4.7・§4.8
 */
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const R = require('./klk138_ruler.js');
const Gen = require('./klk138_generator.js');

const BASELINE = path.join(R.ROOT, 'tests', 'fixtures', 'klk138', 'baseline-v1.2.json');
const LABEL = 'v1.2';
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
  return pals.map(p => {
    const res = R.scorePalette(word, p, ruler, { age });
    return { seed, scheme: p.scheme, verdict: res.verdict, points: res.points, roles: rolesStr(res), penalties: res.penalties };
  });
}

function compute({ withValidation }) {
  const ruler = R.loadRuler();
  const gen = Gen.load();
  const passMin = ruler.scoring.wordPassMin;
  const words = Object.keys(ruler.words);
  const scored = words.filter(w => ruler.words[w].dictLabel);
  for (const w of scored) {
    if (!gen.hasLabel(ruler.words[w].dictLabel)) throw new Gen.HarnessError('辞書ラベルが生成側に無い: ' + ruler.words[w].dictLabel);
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
  for (const seed of REF_SEEDS) for (const w of scored) {
    const pals = scoreWord(gen, ruler, w, seed, 0);
    refAll = refAll.concat(pals);
    for (const p of pals) {
      const a = bySchemeAcc[p.scheme] || (bySchemeAcc[p.scheme] = { sum: 0, count: 0 });
      a.sum += p.points; a.count++;
    }
  }
  const bySchemes = {};
  for (const k of Object.keys(bySchemeAcc).sort()) bySchemes[k] = { rate: R.r4(bySchemeAcc[k].sum / bySchemeAcc[k].count), count: bySchemeAcc[k].count };
  const reference = { seeds: REF_SEEDS, overall: { rate: R.r4(R.rateOf(refAll)), palettes: refAll.length }, bySchemes };

  const out = {
    schema: 'klk138-baseline',
    version: 1,
    generator: { file: 'palette/index.html', label: LABEL, fingerprint: gen.fingerprint, initialSeed: gen.initialSeed },
    ruler: { version: ruler.version, sha256: rulerSha() },
    primary, ageVariant, reference,
  };
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
  console.log(`\n  全体の合格率（16語・${o.palettes}案の平均）: ${pct(o.rate)}   合格した語: ${o.wordsPassed} / ${o.wordsScored}`);
  console.log('\n[辞書なし] 採点しない（分母に入れない）');
  for (const w of Object.keys(words)) if (words[w].rate === null) console.log(`  ${words[w].status}  ${w}`);
  console.log('\n[追加条件 B0-age]（参考行。分母に入れない）');
  for (const w of Object.keys(b.ageVariant)) {
    const a = b.ageVariant[w];
    console.log(`  ${w}（大人かわいい・age=${a.age}）: ${pct(a.rate)}  ${a.palettes.map(p => SYM[p.verdict]).join('')}`);
  }
  console.log(`\n[参考条件 B1] シード ${b.reference.seeds[0]}〜${b.reference.seeds[b.reference.seeds.length - 1]} × 16語 × 3案 = ${b.reference.overall.palettes}案: ${pct(b.reference.overall.rate)}`);
  for (const k of Object.keys(b.reference.bySchemes)) {
    const s = b.reference.bySchemes[k];
    console.log(`  ${pct(s.rate).padStart(6)}  出現 ${String(s.count).padStart(4)}  ${k}`);
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

function main(argv) {
  try {
    if (argv.includes('--check')) {
      if (!fs.existsSync(BASELINE)) { console.error('[NG] ' + path.relative(R.ROOT, BASELINE) + ' が無い'); return 1; }
      const base = JSON.parse(fs.readFileSync(BASELINE, 'utf8'));
      const gen = Gen.load();
      if (base.generator.fingerprint !== gen.fingerprint) {
        console.log(`[SKIP] 生成側が ${base.generator.label} から変わった。新しいベースラインを別ファイルで記録すること`);
        return 0;
      }
      const now = compute({ withValidation: false });
      const keys = ['schema', 'version', 'generator', 'ruler', 'primary', 'ageVariant', 'reference'];
      const diff = keys.filter(k => JSON.stringify(base[k]) !== JSON.stringify(now[k]));
      if (diff.length) {
        console.error('[NG] ベースラインが再現しない: ' + diff.join(', '));
        return 1;
      }
      console.log(`[OK] ベースライン ${base.generator.label} を再現（全体 ${now.primary.overall.rate}・合格 ${now.primary.overall.wordsPassed}/${now.primary.overall.wordsScored}）`);
      return 0;
    }
    if (argv.includes('--write-baseline')) {
      const b = compute({ withValidation: true });
      fs.mkdirSync(path.dirname(BASELINE), { recursive: true });
      fs.writeFileSync(BASELINE, stable(b), 'utf8');
      console.log('wrote ' + path.relative(R.ROOT, BASELINE));
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
