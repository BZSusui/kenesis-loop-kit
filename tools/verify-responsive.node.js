#!/usr/bin/env node
/*
 * tools/verify-responsive.node.js — 生成物を**実際に描いて**レイアウトの崩れを見つける (KLK-118)
 *
 * なぜ要るか:
 *   既存の検査（verify-mockup.py / bridge.find_quality_warnings）は **CSS の宣言**を読む。
 *   「`aspect-ratio:16/7` と書いてある」は捕まえられるが、
 *   「4/3 と書いてあるのに実際は細長く描かれている」「768px で画面からはみ出す」は捕まえられない。
 *   実ユーザーから 768px での崩れの指摘があり（2026-09-11）、**描いて測る**検査を足した。
 *
 * 見るもの（すべて実測。CSS の文字列は読まない）:
 *   A 横スクロール      documentElement.scrollWidth が画面幅を超える
 *   B 親からのはみ出し   要素が自分の属する .sec の左右をはみ出す
 *   C 箱からのあふれ     要素の中身が自分の箱から溢れる（scrollWidth > clientWidth）
 *   D アタリの比率逸脱   アタリ枠の実測 w/h が §3.0 の許容帯から外れる
 *   E 横並びの重なり      同じ親の横並びのきょうだいが左右に重なる（隣の中身を隠す）
 *   F 短いラベルの窮屈な折り返し  「アクセス」が「アクセ／ス」になるような詰まり方
 *
 *   ★F を足した経緯（KLK-122）: KLK-118 で「はみ出してはいないが窮屈な箇所は検出できない」と
 *     申し送った件。見本03 のナビが 768px で 40px まで潰れ、4文字が2行に折れていた。
 *     **箱の高さ÷行高では測れない**（ボタンの上下余白で2行に見える）。
 *     Range で**文字が実際に何行に折れたか**を数え、1行に入る文字数で判定する。
 *
 *   ★E を足した経緯（KLK-118）: 見本03 の ACCESS で、地図が自分の列(332px)を超えて 385px になり、
 *     右隣の情報パネルに重なって「住所」が「主所」に見えていた。A〜D はどれも
 *     「.sec からのはみ出し」「箱からのあふれ」なので、**セクションの内側で起きる重なり**を
 *     1つも捕まえられなかった。目視で気づいた崩れは、検査に足す。
 *
 *   ★意図的な横スクロール（`overflow-x:auto`／`scroll` の中身）は B・C から除く。
 *     pat-slider・sns-slider・sns-reels・voice-slider・staff-hscroll・モバイルの表などは
 *     はみ出して正しい。ここを除かないと本物の崩れが埋もれる。
 *
 * 使い方:
 *   node tools/verify-responsive.node.js <html...> [--width=768] [--report] [--json=<path>]
 *   node tools/verify-responsive.node.js samples/*&#47;index*.html --width=768
 *
 *   --report  判定せず、測った値の分布だけ出す（閾値を決めるとき用）
 *   --json    結果を JSON で保存する（型ごとの集計に使う）
 *
 * 終了コード: 0=崩れなし / 1=崩れあり / 2=ハーネス異常 / 3=環境理由でSKIP（Chrome 無し）
 */
'use strict';
const { spawn } = require('node:child_process');
const net = require('node:net');
const path = require('node:path');
const fs = require('node:fs');

const { spawnSync } = require('node:child_process');

// ★型プールの正は draft-gen/bridge.py（規約 §12.1.x の写し）。ここで持ち直すとドリフトするので
//   実行時に読み出す。読めなければ型の特定を諦める（比率の例外判定が緩くなる旨を警告する）。
function loadPools(root) {
  const py = `
import importlib.util, json, os
spec = importlib.util.spec_from_file_location("b", os.path.join(${JSON.stringify('ROOT_PLACEHOLDER')}, "draft-gen", "bridge.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(json.dumps({k: list(v) for k, v in m.SECTION_TYPE_POOLS.items()}, ensure_ascii=False))
`.replace('ROOT_PLACEHOLDER', root);
  const r = spawnSync('python3', ['-c', py], { encoding: 'utf8' });
  if (r.status !== 0) return null;
  try { return JSON.parse(r.stdout); } catch { return null; }
}

const args = process.argv.slice(2);
const files = args.filter(a => !a.startsWith('--'));
const opt = k => { const a = args.find(x => x.startsWith('--' + k + '=')); return a ? a.split('=').slice(1).join('=') : null; };
const WIDTH = parseInt(opt('width') || '768', 10);
const REPORT = args.includes('--report');
const JSON_OUT = opt('json');

const CHROME = process.env.KLK_CHROME
  || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Chromium.app/Contents/MacOS/Chromium'].find(p => fs.existsSync(p));
if (!CHROME) { console.log('SKIP: ヘッドレス Chrome が見つかりません'); process.exit(3); }
if (!files.length) { console.error('使い方: node tools/verify-responsive.node.js <html...> [--width=768]'); process.exit(2); }

const sleep = ms => new Promise(r => setTimeout(r, ms));
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
function cdpClient(ws) {
  let id = 0; const pend = new Map();
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { const { res, rej } = pend.get(m.id); pend.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
  });
  return (method, params = {}) => new Promise((res, rej) => { const i = ++id; pend.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
}

// ---------------------------------------------------------------------------
// ページ内で走らせる測定。返すのは「事実」だけ。判定はこちら側でやる
// （閾値を測定側に埋め込むと、閾値を変えるたびに測り直しになる）
// ---------------------------------------------------------------------------
const PROBE = (width, pools) => `(() => {
  const W = ${width};
  const POOLS = ${JSON.stringify(pools || {})};
  const out = { width: W, scrollWidth: document.documentElement.scrollWidth, sections: [], overflow: [], atari: [], overlap: [], cramped: [] };

  // セクションの型を読む。**ブリッジと同じやり方**（番地→プール→セクションHTMLを語境界で検索）。
  //   マーカーはクラス名・data属性・CSS のどこに現れるか決まっていないため、
  //   クラス名だけを見ると取りこぼす（実測で空になった）。
  const SECS = Array.from(document.querySelectorAll('.sec'));
  const addrOf = sec => { const p = sec.querySelector('.pin'); return p ? p.textContent.trim() : (sec.id || ''); };
  const typeCache = new Map();
  const typeOf = sec => {
    if (typeCache.has(sec)) return typeCache.get(sec);
    const addr = addrOf(sec);
    const prefix = addr.replace(/-\\d+$/, '');
    const pool = POOLS[prefix] || [];
    const html = sec.outerHTML;
    const markers = pool.filter(m => new RegExp('(?<![A-Za-z0-9-])' + m.replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&') + '(?![A-Za-z0-9-])').test(html));
    const famEl = sec.querySelector('[class*="m-"]');
    const fam = famEl ? ((famEl.className || '').toString().split(/\\s+/).find(c => /^m-[a-z]+$/.test(c)) || '') : '';
    const t = { fam, marker: markers.join(','), addr: addr, prefix: prefix };
    typeCache.set(sec, t);
    return t;
  };
  for (const s of SECS) { const t = typeOf(s); out.sections.push({ addr: t.addr, fam: t.fam, marker: t.marker }); }

  // 意図的な横スクロール（overflow-x:auto/scroll）の中は対象外
  const inScroller = el => {
    for (let p = el.parentElement; p; p = p.parentElement) {
      const ov = getComputedStyle(p).overflowX;
      if (ov === 'auto' || ov === 'scroll') return true;
    }
    return false;
  };
  const secOf = el => el.closest('.sec');
  const label = el => {
    const cls = (el.className || '').toString().trim().split(/\\s+/).slice(0, 3).join('.');
    return el.tagName.toLowerCase() + (cls ? '.' + cls : '');
  };

  for (const el of document.body.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    if (inScroller(el)) continue;
    const sec = secOf(el);
    const t = sec ? typeOf(sec) : { fam: '', marker: '' };
    const base = { tag: label(el), addr: sec ? addrOf(sec) : '', fam: t.fam, marker: t.marker };

    // B 親（.sec）からのはみ出し
    if (sec) {
      const sr = sec.getBoundingClientRect();
      if (r.right > sr.right + 1 || r.left < sr.left - 1) {
        out.overflow.push(Object.assign({ kind: 'sec', left: Math.round(r.left), right: Math.round(r.right),
          secLeft: Math.round(sr.left), secRight: Math.round(sr.right) }, base));
        continue;   // 親からはみ出しているなら、画面外かどうかは同じ原因
      }
    }
    // A' 画面右端からのはみ出し（.sec の外にある要素も拾う）
    if (r.right > W + 1 || r.left < -1) {
      out.overflow.push(Object.assign({ kind: 'viewport', left: Math.round(r.left), right: Math.round(r.right) }, base));
      continue;
    }
    // C 中身が自分の箱からあふれる（文字の食み出し・詰まり）
    if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) {
      const ov = getComputedStyle(el).overflowX;
      if (ov !== 'auto' && ov !== 'scroll') {
        out.overflow.push(Object.assign({ kind: 'content', clientW: el.clientWidth, scrollW: el.scrollWidth }, base));
      }
    }
  }

  // E 横並びのきょうだいの重なり（同じ親・同じ行にいる要素同士）
  //   ★「重ねることが定義の型」は除く。MV overlap / ABOUT img-overlap / ACCESS map-overlay は
  //     §12.1.3 が「せり出し…の重なり」「情報カードを重ねる」と定めており、重なって正しい。
  //     個々の要素でも transform で意図的にずらしているものは除く（同上の手段）。
  const OVERLAP_BY_DESIGN = new Set(['overlap', 'img-overlap', 'map-overlay']);
  const designedOverlap = sec => {
    if (!sec) return false;
    const ms = String(typeOf(sec).marker || '').split(',');
    return ms.some(m => OVERLAP_BY_DESIGN.has(m));
  };
  for (const parent of document.body.querySelectorAll('*')) {
    if (designedOverlap(secOf(parent))) continue;
    const kids = Array.from(parent.children).filter(k => {
      const r = k.getBoundingClientRect();
      const s = getComputedStyle(k);
      return r.width > 1 && r.height > 1 && s.position === 'static' && s.transform === 'none';
    });
    if (kids.length < 2) continue;
    const disp = getComputedStyle(parent).display;
    if (disp !== 'grid' && disp !== 'flex' && disp !== 'inline-grid' && disp !== 'inline-flex') continue;
    for (let i = 0; i < kids.length - 1; i++) {
      const a = kids[i].getBoundingClientRect();
      for (let j = i + 1; j < kids.length; j++) {
        const b = kids[j].getBoundingClientRect();
        // 縦に離れていれば重なりではない（折り返した別の行）
        if (a.bottom <= b.top + 1 || b.bottom <= a.top + 1) continue;
        const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        if (ox > 1) {
          const sec = secOf(kids[i]);
          const tt = sec ? typeOf(sec) : { fam: '', marker: '' };
          out.overlap.push({ tag: label(kids[i]) + ' × ' + label(kids[j]),
            addr: sec ? addrOf(sec) : '', fam: tt.fam, marker: tt.marker,
            px: Math.round(ox), a: Math.round(a.left) + '..' + Math.round(a.right),
            b: Math.round(b.left) + '..' + Math.round(b.right) });
        }
      }
    }
  }

  // F 短いラベルの窮屈な折り返し
  //   短いラベル（8文字以内）が、1行6文字も入らない幅に詰められて2行以上に折れている状態。
  //   ★padding を含む箱の高さで割ると誤検出する。Range で行box の数を数える。
  for (const el of document.body.querySelectorAll('*')) {
    if (el.children.length) continue;                 // 末端のテキストだけ
    const txt = (el.textContent || '').trim();
    if (!txt || txt.length > 8) continue;             // 長い文は折り返して当然
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const rg = document.createRange();
    rg.selectNodeContents(el);
    const tops = new Set(Array.from(rg.getClientRects())
      .filter(x => x.width > 0 && x.height > 0).map(x => Math.round(x.top)));
    if (tops.size < 2) continue;                      // 折れていない
    const fs = parseFloat(getComputedStyle(el).fontSize) || 14;
    // 1行に入る文字数。日本語は約1文字=1em なのでこの近似でよい。
    //   ★英字ラベルは1文字が 1em より狭いので容量を多めに見積もる＝**見落とす側**に外れる。
    //     誤検出でうるさくなるより、取りこぼす側に倒している（生成物の文言は日本語が主）。
    const cpl = r.width / fs;
    if (cpl >= 6) continue;                           // 6文字は入る＝窮屈ではない
    const sec = secOf(el);
    const tt = sec ? typeOf(sec) : { fam: '', marker: '' };
    out.cramped.push({ tag: label(el), addr: sec ? addrOf(sec) : '', fam: tt.fam, marker: tt.marker,
      text: txt, lines: tops.size, w: Math.round(r.width), fs: Math.round(fs), cpl: +cpl.toFixed(1) });
  }

  // D アタリ枠の実測比率
  for (const el of document.querySelectorAll('[class*="atari"], .film .cell')) {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const sec = secOf(el);
    const t = sec ? typeOf(sec) : { fam: '', marker: '' };
    out.atari.push({
      tag: label(el), addr: sec ? addrOf(sec) : '', fam: t.fam, marker: t.marker,
      w: Math.round(r.width), h: Math.round(r.height),
      ratio: +(r.width / r.height).toFixed(3),
      inFilm: !!el.closest('.film'),
      isHero: !!el.closest('.m-hero') && !el.closest('.film'),
    });
  }
  return JSON.stringify(out);
})()`;

// ---------------------------------------------------------------------------
// アタリ比率の許容帯（§3.0）
//
// ★「期待値からの倍率」ではなく**絶対の帯**で見る。理由:
//   規約 §3.0 が認める形は 4/3（既定）・1/1（人物・SNSサムネ）・3/2（panel-band の帯）で、
//   理恵さんの指示は「3:4(4:3) から大きく逸脱して細長くなったもの」＝**縦横どちらの 3:4 も可**。
//   つまり許される形は 0.75〜1.333 の帯であって、1つの期待値ではない。
//   倍率で見ると「1.333 の 1.5倍 = 2.0 まで可」となり、16/9(1.778) のような
//   規約が明確に否定している平たさを通してしまう（実測で確認・KLK-118）。
//
// ★混在型（pat-mosaic / pat-masonry / sns-masonry）は**個々のタイルを見ない**（理恵さん判断・A案）。
//   この3型は「大小混在タイルを敷き詰める」型で、§12.1.3 が
//   横長 2×1・大 2×2・縦長 1×2・小 1×1 の組合せを定めている。
//   grid-auto-rows が列幅の約0.75倍なので、設計上の比率はおよそ {0.5, 1.333, 2.67}。
//   実測（47タイル）も 0.55 / 1.13〜1.22 / 1.92〜1.97 / 2.49 に収まり、
//   そこから外れたのは 4.057 と 5.143 だけだった。**上限だけ**を見る帯にしてある。
//
// 帯の数値はすべて 116 ファイルの実測から決めた（書き写しではない）。
const MIXED_TILE_MARKERS = new Set(['pat-mosaic', 'pat-masonry', 'sns-masonry']);
function ratioBand(a) {
  if (a.isHero) return null;                            // HERO 全面ビジュアルは比率の対象外（§3.0）
  if (a.inFilm) return { lo: 1.35, hi: 1.65, why: 'panel-band の帯 3/2' };
  for (const m of String(a.marker).split(',')) {
    if (MIXED_TILE_MARKERS.has(m)) return { lo: 0.40, hi: 3.00, why: '混在タイル（上限のみ）' };
  }
  return { lo: 0.68, hi: 1.47, why: '3:4〜4:3（1:1 を含む）' };
}

const POOLS = loadPools(path.join(__dirname, '..'));
if (!POOLS) console.error('[注意] bridge.py から型プールを読めませんでした。型の特定を伴う判定（比率の例外）が緩くなります。');

(async () => {
  let chrome;
  const findings = [];
  const measured = [];
  try {
    const port = await freePort();
    const profile = fs.mkdtempSync('/tmp/klk-resp-');
    chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars',
      '--force-prefers-reduced-motion', `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
    if (!await waitHttp(`http://127.0.0.1:${port}/json/version`)) { console.error('[HARNESS ERROR] Chrome CDP が起きない'); process.exit(2); }

    for (const f of files) {
      const url = 'file://' + path.resolve(f);
      const t = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
      const ws = new WebSocket(t.webSocketDebuggerUrl);
      await new Promise(r => ws.addEventListener('open', r));
      const send = cdpClient(ws);
      await send('Emulation.setDeviceMetricsOverride', { width: WIDTH, height: 1000, deviceScaleFactor: 1, mobile: false });
      await send('Page.enable');
      await send('Page.navigate', { url });
      await sleep(700);
      const res = await send('Runtime.evaluate', { expression: PROBE(WIDTH, POOLS), returnByValue: true });
      ws.close(); await fetch(`http://127.0.0.1:${port}/json/close/${t.id}`);
      if (!res.result || typeof res.result.value !== 'string') { console.error(`[WARN] 測定できません: ${f}`); continue; }
      const o = JSON.parse(res.result.value);
      o.file = f;
      measured.push(o);
    }
  } catch (e) {
    console.error('[HARNESS ERROR] ' + (e && e.stack || e));
    process.exitCode = 2;
  } finally {
    try { chrome && chrome.kill(); } catch {}
  }
  if (process.exitCode === 2) process.exit(2);

  // ---- 判定 --------------------------------------------------------------
  for (const o of measured) {
    if (o.scrollWidth > o.width + 1) {
      findings.push({ file: o.file, kind: 'page-scroll', detail: `scrollWidth=${o.scrollWidth} > ${o.width}` });
    }
    for (const x of o.overflow) {
      findings.push({ file: o.file, kind: x.kind === 'content' ? 'content-overflow' : 'overflow',
        addr: x.addr, fam: x.fam, marker: x.marker, tag: x.tag,
        detail: x.kind === 'content' ? `中身 ${x.scrollW}px > 箱 ${x.clientW}px`
              : x.kind === 'sec' ? `${x.left}..${x.right} / sec ${x.secLeft}..${x.secRight}`
              : `${x.left}..${x.right} / 画面 0..${o.width}` });
    }
    for (const x of (o.overlap || [])) {
      findings.push({ file: o.file, kind: 'overlap', addr: x.addr, fam: x.fam, marker: x.marker, tag: x.tag,
        detail: `${x.px}px 重なる（${x.a} と ${x.b}）` });
    }
    for (const x of (o.cramped || [])) {
      findings.push({ file: o.file, kind: 'cramped', addr: x.addr, fam: x.fam, marker: x.marker, tag: x.tag,
        detail: `「${x.text}」が ${x.lines}行（幅 ${x.w}px / ${x.fs}px ＝ 1行 ${x.cpl} 文字）` });
    }
    for (const a of o.atari) {
      const b = ratioBand(a);
      if (!b) continue;
      if (a.ratio < b.lo || a.ratio > b.hi) {
        findings.push({ file: o.file, kind: 'atari-ratio', addr: a.addr, fam: a.fam, marker: a.marker, tag: a.tag,
          detail: `実測 ${a.w}x${a.h} = ${a.ratio}（許容 ${b.lo}〜${b.hi}／${b.why}）` });
      }
    }
  }

  if (JSON_OUT) fs.writeFileSync(JSON_OUT, JSON.stringify({ width: WIDTH, measured, findings }, null, 1));

  if (REPORT) {
    // 閾値を決めるための分布（判定しない）
    const rows = [];
    for (const o of measured) for (const a of o.atari) {
      const b = ratioBand(a);
      if (!b) continue;
      rows.push({ f: o.file, marker: a.marker, tag: a.tag, ratio: a.ratio, exp: `${b.lo}〜${b.hi}`,
        factor: +(a.ratio > b.hi ? a.ratio / b.hi : a.ratio < b.lo ? a.ratio / b.lo : 1).toFixed(2) });
    }
    rows.sort((x, y) => y.factor - x.factor);
    console.log(`アタリ ${rows.length} 件の「期待比率に対する倍率」分布（幅 ${WIDTH}px）`);
    const buckets = {};
    for (const r of rows) { const b = r.factor >= 2 ? '2.0以上' : r.factor >= 1.5 ? '1.5〜2.0' : r.factor >= 1.25 ? '1.25〜1.5' : r.factor >= 0.8 ? '0.8〜1.25' : r.factor >= 0.5 ? '0.5〜0.8' : '0.5未満'; buckets[b] = (buckets[b] || 0) + 1; }
    for (const k of ['2.0以上', '1.5〜2.0', '1.25〜1.5', '0.8〜1.25', '0.5〜0.8', '0.5未満']) if (buckets[k]) console.log(`  ${k.padEnd(10)} ${buckets[k]} 件`);
    console.log('\n--- 逸脱の大きい順 20件 ---');
    for (const r of rows.slice(0, 20)) console.log(`  ${String(r.factor).padStart(5)}倍  ${r.tag}  実測${r.ratio} 期待${r.exp}  [${r.marker}]  ${r.f}`);
    console.log('\n--- 縮んだ側 10件 ---');
    for (const r of rows.slice(-10)) console.log(`  ${String(r.factor).padStart(5)}倍  ${r.tag}  実測${r.ratio} 期待${r.exp}  [${r.marker}]  ${r.f}`);
    process.exit(0);
  }

  console.log(`実描画レイアウト検査（幅 ${WIDTH}px・${measured.length} ファイル）`);
  if (!findings.length) { console.log('崩れは見つかりませんでした。'); process.exit(0); }
  const byKind = {};
  for (const x of findings) (byKind[x.kind] = byKind[x.kind] || []).push(x);
  const NAMES = { 'page-scroll': '画面に横スクロールが出る', 'overflow': 'はみ出し', 'content-overflow': '中身が箱からあふれる', 'atari-ratio': 'アタリの比率逸脱', 'overlap': '横並びの重なり', 'cramped': '短いラベルの窮屈な折り返し' };
  for (const k of Object.keys(byKind)) {
    console.log(`\n■ ${NAMES[k] || k}（${byKind[k].length}件）`);
    for (const x of byKind[k].slice(0, 40)) {
      console.log(`  ${(x.marker || '-').padEnd(20)} ${(x.addr || '-').padEnd(12)} ${x.tag || ''}  ${x.detail}`);
      console.log(`      ${x.file}`);
    }
    if (byKind[k].length > 40) console.log(`  … ほか ${byKind[k].length - 40} 件`);
  }
  console.log(`\n合計 ${findings.length} 件`);
  process.exit(1);
})();
