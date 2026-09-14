#!/usr/bin/env python3
"""
KLK-116 acceptance-condition checker — 配色ジェネレーターの配色をモック生成画面へ自動で渡す。

★経緯（2026-09-11・実ユーザーのフィードバック）
  「ムードジェネレーターで作った配色をモック生成画面にコピペする手間が気になる」。
  SCR-001 には貼り付け解析が既にあったので、足りなかったのは**タブ間の経路**だけ。
  ローカルブリッジ配信時は両画面が同一オリジン（KLK-019）なので、
  BroadcastChannel（開いているタブへ即時）＋ localStorage（後から開くタブへ保管）で渡す。

★この checker が守っているもの
  S. 仕組みが両画面に備わっていること（送るボタン・送信関数・受信関数・UI）
  C. 名前の一致 — schema / version / channel / key を両ファイルから**パースして**比較する
     （片方だけ変えると黙って届かなくなる。文字列の有無ではなく値を突き合わせる）
  G. 壊さないこと — 既存の貼り付け経路・innerHTML 非導入（KLK-014 S5）・注入対策
  M. マニュアルに一文がある

  動的な挙動（受理/拒否の純粋関数）は tests/site/smoke_klk116.node.js、
  実効果（ブリッジ実起動＋ヘッドレス Chrome で別タブへ届く）は tests/site/e2e_klk116.node.js が見る。

Run: python3 tests/site/check_klk116.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PALETTE = io.open(os.path.join(ROOT, "palette", "index.html"), encoding="utf-8").read()
SCR = io.open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
MANUAL = io.open(os.path.join(ROOT, "使い方マニュアル.html"), encoding="utf-8").read()
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


def const_value(src, name):
    """`const NAME = 'x';` / `= 1;` の値を返す（純粋関数・wrapper が使う）。無ければ None。"""
    m = re.search(r"const\s+%s\s*=\s*('([^']*)'|\"([^\"]*)\"|(\d+))\s*;" % re.escape(name), src)
    if not m:
        return None
    if m.group(4) is not None:
        return int(m.group(4))
    return m.group(2) if m.group(2) is not None else m.group(3)


CONSTS = ("HANDOFF_SCHEMA", "HANDOFF_VERSION", "HANDOFF_CHANNEL", "HANDOFF_KEY")

# ---------------------------------------------------------------------------
# S. 仕組み
# ---------------------------------------------------------------------------
check("S1 palette に「モック生成画面へ送る」ボタン（.send-gen）がある",
      'class="send-gen"' in PALETTE and "モック生成画面へ送る" in PALETTE,
      "send-gen=%s 文言=%s" % ('class="send-gen"' in PALETTE, "モック生成画面へ送る" in PALETTE))

check("S2 palette の送信は BroadcastChannel と localStorage の両方に載せる",
      "function sendHandoff" in PALETTE
      and "new BroadcastChannel(HANDOFF_CHANNEL)" in PALETTE
      and "localStorage.setItem(HANDOFF_KEY" in PALETTE,
      "sendHandoff=%s channel=%s storage=%s" % (
          "function sendHandoff" in PALETTE,
          "new BroadcastChannel(HANDOFF_CHANNEL)" in PALETTE,
          "localStorage.setItem(HANDOFF_KEY" in PALETTE))

check("S3 palette の payload は微調整後の値から作る（currentPatterns 由来・純粋関数 handoffPayloadOf）",
      "function handoffPayloadOf" in PALETTE
      and "sendHandoff(handoffPayloadOf(currentPatterns[+btn.dataset.p]))" in PALETTE,
      "関数=%s 呼び出し=%s" % ("function handoffPayloadOf" in PALETTE,
                              "sendHandoff(handoffPayloadOf(currentPatterns[+btn.dataset.p]))" in PALETTE))

check("S4 SCR-001 が受信する（BroadcastChannel＋storage イベント）",
      "function setupHandoffReceiver" in SCR
      and "new BroadcastChannel(HANDOFF_CHANNEL)" in SCR
      and "addEventListener('storage'" in SCR
      and "setupHandoffReceiver();" in SCR,
      "receiver=%s channel=%s storage=%s init呼び出し=%s" % (
          "function setupHandoffReceiver" in SCR, "new BroadcastChannel(HANDOFF_CHANNEL)" in SCR,
          "addEventListener('storage'" in SCR, "setupHandoffReceiver();" in SCR))

check("S5 受信値は acceptHandoff で検証（schema/version 一致・normalizeHex 通過のみ採用）",
      "function acceptHandoff" in SCR
      and "payload.schema !== HANDOFF_SCHEMA" in SCR
      and "payload.version !== HANDOFF_VERSION" in SCR
      and re.search(r"function acceptHandoff.*?normalizeHex\(src\[k\]\)", SCR, re.S) is not None,
      "関数=%s schema=%s version=%s normalizeHex=%s" % (
          "function acceptHandoff" in SCR, "payload.schema !== HANDOFF_SCHEMA" in SCR,
          "payload.version !== HANDOFF_VERSION" in SCR,
          re.search(r"function acceptHandoff.*?normalizeHex\(src\[k\]\)", SCR, re.S) is not None))

check("S6 開く前に届いていた分は黙って変えず「届いています［反映する］」を出す",
      "function readStoredHandoff" in SCR
      and "HANDOFF_CONSUMED_KEY" in SCR
      and 'id="handoffApply"' in SCR
      and "配色が届いています" in SCR,
      "stored=%s consumed=%s button=%s 文言=%s" % (
          "function readStoredHandoff" in SCR, "HANDOFF_CONSUMED_KEY" in SCR,
          'id="handoffApply"' in SCR, "配色が届いています" in SCR))

check("S7 反映は既存の setColorRole / colorMode='pasted' / render() を通す（生成指示書スキーマ不変）",
      re.search(r"function applyHandoff.*?setColorRole\(k, accepted\.colors\[k\]\).*?colorMode = 'pasted';.*?render\(\);",
                SCR, re.S) is not None,
      "applyHandoff の流れ=%s" % (re.search(r"function applyHandoff.*?render\(\);", SCR, re.S) is not None))

# ---------------------------------------------------------------------------
# C. 名前の一致（値をパースして比較）
# ---------------------------------------------------------------------------
pv = {c: const_value(PALETTE, c) for c in CONSTS}
sv = {c: const_value(SCR, c) for c in CONSTS}
check("C1 4定数が両画面に定義されている",
      all(v is not None for v in pv.values()) and all(v is not None for v in sv.values()),
      "palette=%s scr=%s" % (pv, sv))
check("C2 4定数の値が両画面で一致する（片方だけ変えると届かなくなる）",
      pv == sv and all(v is not None for v in pv.values()),
      "palette=%s scr=%s" % (pv, sv))
check("C3 schema 名と version が想定どおり",
      pv["HANDOFF_SCHEMA"] == "klk-palette-handoff" and pv["HANDOFF_VERSION"] == 1,
      "schema=%s version=%s" % (pv["HANDOFF_SCHEMA"], pv["HANDOFF_VERSION"]))

# ---------------------------------------------------------------------------
# G. 壊さないこと
# ---------------------------------------------------------------------------
check("G1 既存の貼り付け経路（pasteBox / pasteImport / parsePalette）が残っている（フォールバック）",
      'id="pasteBox"' in SCR and 'id="pasteImport"' in SCR and "function parsePalette" in SCR,
      "pasteBox=%s pasteImport=%s parsePalette=%s" % (
          'id="pasteBox"' in SCR, 'id="pasteImport"' in SCR, "function parsePalette" in SCR))

check("G2 SCR-001 に innerHTML を導入していない（KLK-014 S5）・受信表示は textContent",
      ".innerHTML" not in SCR and "msg.textContent = text || ''" in SCR,
      "innerHTML=%s textContent=%s" % (".innerHTML" in SCR, "msg.textContent = text || ''" in SCR))

check("G3 palette の送信は例外を握って false を返す（file:// 直開きで壊れない）",
      re.search(r"function sendHandoff.*?try \{ localStorage\.setItem.*?\} catch \(e\) \{\}.*?try \{ const ch = new BroadcastChannel.*?\} catch \(e\) \{\}.*?return ok;",
                PALETTE, re.S) is not None,
      "try/catch 2段=%s" % (re.search(r"function sendHandoff.*?return ok;", PALETTE, re.S) is not None))

check("G4 送れない環境ではコピー経路へ誘導する文言がある",
      "「CSS変数をコピー」で貼り付けてください" in PALETTE,
      "誘導文=%s" % ("「CSS変数をコピー」で貼り付けてください" in PALETTE))

check("G5 palette の既存コピーボタン（.css-copy）と copyTextOf はそのまま",
      'class="css-copy"' in PALETTE and "function copyTextOf" in PALETTE and "function cssVarsOf" in PALETTE,
      "css-copy=%s copyTextOf=%s" % ('class="css-copy"' in PALETTE, "function copyTextOf" in PALETTE))

# ---------------------------------------------------------------------------
# M. マニュアル
# ---------------------------------------------------------------------------
check("M1 使い方マニュアルの③に「モック生成画面へ送る」の一文がある",
      "モック生成画面へ送る" in MANUAL and "貼り付けでも入ります" in MANUAL,
      "送る=%s フォールバック言及=%s" % ("モック生成画面へ送る" in MANUAL, "貼り付けでも入ります" in MANUAL))

print("=" * 78)
print("KLK-116 配色ジェネレーター → モック生成画面 受け渡し チェック")
print("=" * 78)
failed = 0
for name, passed, detail in results:
    status = "PASS" if passed else "FAIL"
    if not passed:
        failed += 1
    print("[%s] %s" % (status, name))
    print("        %s" % detail)
print("-" * 78)
print("%d checks, %d failed" % (len(results), failed))
sys.exit(1 if failed else 0)
