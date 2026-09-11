#!/usr/bin/env node
/*
 * KLK-116 動的スモークテスト（tester所有・Node.js標準のみ・ブラウザ不要）
 *
 * 配色ジェネレーター（palette/index.html）→ モック生成画面（draft-gen/index.html）への
 * 受け渡しについて、両画面の**純粋関数**を切り出して機械検証する。
 *   送信側: handoffPayloadOf(p)   … 1案 → { schema, version, colors:{main,sub,accent,bg}, sentAt }
 *   受信側: acceptHandoff(payload) … 検証して { colors, matched, sentAt } か null
 *
 *   D1 往復: palette が作った payload を SCR-001 がそのまま受理し、4色が #rrggbb で一致する
 *   D2 妨害: schema 違い / version 違い は null（何も変えない）
 *   D3 妨害: 壊れた hex は落とし、正しい色だけ採用。全部壊れていれば null
 *   D4 3桁 #abc は #aabbcc に展開、#なし6桁も受理（normalizeHex の既存規約 KLK-028 と整合）
 *   D5 sentAt が数値でない/欠けていれば 0 扱い（保管分の新旧判定が壊れない）
 *   D6 定数（schema/version/channel/key）が両画面で一致する
 *
 * 実行: node tests/site/smoke_klk116.node.js
 * 終了コード: 0=全PASS / 1=FAILあり / 2=ハーネス異常
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const PALETTE = fs.readFileSync(path.join(ROOT, 'palette', 'index.html'), 'utf8');
const SCR001 = fs.readFileSync(path.join(ROOT, 'draft-gen', 'index.html'), 'utf8');

function sliceBetween(src, start, end, label) {
  const i = src.indexOf(start);
  const j = src.indexOf(end);
  if (i < 0 || j < 0 || j <= i) {
    console.error('[HARNESS ERROR] ' + label + ' のスライスマーカーが見つかりません');
    process.exit(2);
  }
  return src.slice(i, j);
}

// palette: 既存 smoke_klk004 と同じ区間（const KEYWORDS 〜 function render() の直前）
const paletteSlice = sliceBetween(PALETTE, 'const KEYWORDS = {', '\nfunction render() {', 'palette/index.html');
// SCR-001: 既存 smoke_klk028 と同じ区間（const COLUMN_KEYS 〜 function render() の直前）
const scrSlice = sliceBetween(SCR001, 'const COLUMN_KEYS', '\nfunction render() {', 'draft-gen/index.html');

const results = [];
function check(name, ok, detail) { results.push([name, !!ok, detail || '']); }

let P, S;
try {
  // それぞれ別スコープで評価し、公開したい関数だけ取り出す
  P = new Function(paletteSlice + `
    return { handoffPayloadOf, hslToHex, ROLE_KEYS,
             HANDOFF_SCHEMA, HANDOFF_VERSION, HANDOFF_CHANNEL, HANDOFF_KEY };`)();
  S = new Function(scrSlice + `
    return { acceptHandoff, normalizeHex, ROLE_KEYS,
             HANDOFF_SCHEMA, HANDOFF_VERSION, HANDOFF_CHANNEL, HANDOFF_KEY };`)();
} catch (e) {
  console.error('[HARNESS ERROR] スライスの評価に失敗: ' + e.message);
  process.exit(2);
}

// palette の1案の形（HSL の3つ組 × 4役）を模す
const pattern = { main: [210, .6, .5], sub: [210, .2, .9], accent: [28, .8, .55], bg: [40, .1, .97] };

// D1 往復
const payload = P.handoffPayloadOf(pattern, 1700000000000);
const acc = S.acceptHandoff(payload);
const expect = {};
P.ROLE_KEYS.forEach(k => { expect[k] = P.hslToHex(pattern[k][0], pattern[k][1], pattern[k][2]).toLowerCase(); });
check('D1 palette の payload を SCR-001 が受理し 4色が一致する',
  acc && acc.matched.length === 4 && P.ROLE_KEYS.every(k => acc.colors[k] === expect[k]) && acc.sentAt === 1700000000000,
  JSON.stringify(acc && acc.colors));
check('D1b payload の色は常に #rrggbb 単色（グラデ等が混じらない）',
  P.ROLE_KEYS.every(k => /^#[0-9a-f]{6}$/i.test(payload.colors[k])), JSON.stringify(payload.colors));

// D2 妨害: schema / version
const wrongSchema = Object.assign({}, payload, { schema: 'klk-something-else' });
const wrongVersion = Object.assign({}, payload, { version: 2 });
check('D2 schema が違えば null（何も変えない）', S.acceptHandoff(wrongSchema) === null);
check('D2b version が違えば null', S.acceptHandoff(wrongVersion) === null);
check('D2c null / 文字列 / colors 無し も null',
  S.acceptHandoff(null) === null && S.acceptHandoff('x') === null &&
  S.acceptHandoff({ schema: S.HANDOFF_SCHEMA, version: S.HANDOFF_VERSION }) === null);

// D3 妨害: 壊れた hex
const partlyBroken = Object.assign({}, payload, { colors: { main: '#12345', sub: 'red', accent: payload.colors.accent, bg: '<img>' } });
const a3 = S.acceptHandoff(partlyBroken);
check('D3 壊れた hex は落ち、正しい色だけ採用される',
  a3 && a3.matched.length === 1 && a3.matched[0] === 'accent' && a3.colors.main === null && a3.colors.bg === null,
  JSON.stringify(a3));
const allBroken = Object.assign({}, payload, { colors: { main: 'x', sub: '', accent: null, bg: 'javascript:alert(1)' } });
check('D3b 全部壊れていれば null', S.acceptHandoff(allBroken) === null);

// D4 normalizeHex の既存規約と整合
const shortHex = Object.assign({}, payload, { colors: { main: '#ABC', sub: '444850', accent: '#00ff00', bg: '#FFFFFF' } });
const a4 = S.acceptHandoff(shortHex);
check('D4 #ABC→#aabbcc / #なし6桁 受理 / 大文字→小文字',
  a4 && a4.colors.main === '#aabbcc' && a4.colors.sub === '#444850' && a4.colors.accent === '#00ff00' && a4.colors.bg === '#ffffff',
  JSON.stringify(a4 && a4.colors));

// D5 sentAt
const noSent = Object.assign({}, payload); delete noSent.sentAt;
const badSent = Object.assign({}, payload, { sentAt: 'now' });
check('D5 sentAt が欠けている/数値でない → 0 扱い',
  S.acceptHandoff(noSent).sentAt === 0 && S.acceptHandoff(badSent).sentAt === 0);
check('D5b palette 側は now 未指定なら Date.now() を入れる',
  typeof P.handoffPayloadOf(pattern).sentAt === 'number' && P.handoffPayloadOf(pattern).sentAt > 1600000000000);

// D6 定数の一致（乖離すると届かない）
check('D6 schema/version/channel/key が両画面で一致する',
  P.HANDOFF_SCHEMA === S.HANDOFF_SCHEMA && P.HANDOFF_VERSION === S.HANDOFF_VERSION &&
  P.HANDOFF_CHANNEL === S.HANDOFF_CHANNEL && P.HANDOFF_KEY === S.HANDOFF_KEY,
  `palette=${P.HANDOFF_SCHEMA}/${P.HANDOFF_VERSION}/${P.HANDOFF_CHANNEL}/${P.HANDOFF_KEY} scr=${S.HANDOFF_SCHEMA}/${S.HANDOFF_VERSION}/${S.HANDOFF_CHANNEL}/${S.HANDOFF_KEY}`);

let failed = 0;
console.log('KLK-116 受け渡しの純粋関数 スモーク');
for (const [name, ok, detail] of results) {
  if (!ok) failed++;
  console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? '\n        ' + detail : ''}`);
}
console.log(`${results.length} checks, ${failed} failed`);
process.exit(failed ? 1 : 0);
