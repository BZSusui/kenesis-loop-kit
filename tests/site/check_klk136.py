#!/usr/bin/env python3
"""
KLK-136 acceptance-condition checker — ブリッジの接続先をポート決め打ちにしない。

★経緯（2026-09-17・KLK-132 のフルスイートで発覚）
  生成設定画面（SCR-001）が接続先を `127.0.0.1:8765` で決め打ちしていた。画面自身は
  ブリッジから配信されているのに、稼働確認 `/health` だけは常に 8765 を叩く。そのため
  既定以外のポート（KLK_BRIDGE_PORT）で起動すると「非稼働」と判定され、
  実績カタログ・参考素材・ワンクリック生成がまとめて無効になっていた。
  **同梱の案内（はじめにお読みください.txt）がこの起動方法を勧めている**ので実害がある。

★この checker が守っているもの
  1. 画面が配信元（location.origin）から接続先を決めること
  2. file:// で開いたときだけ既定値へ倒れること（KLK-026 の開き直し案内が壊れない）
  3. 決め打ちの絶対URLが残っていないこと
  4. compare.html は file:// で開かれるので、**書き出すときに実ポートを埋める**こと
  5. ★数字の二重管理を機械照合 — make_compare の既定ポートと bridge.py の DEFAULT_PORT が一致
  6. ★実際に書き出して、指定ポートが入り埋め残しが無いこと

  実ブラウザでの確認は tests/site/e2e_klk136.node.js が担う（この checker はブラウザを使わない）。

Run: python3 tests/site/check_klk136.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import make_compare as mc  # noqa: E402

INDEX = io.open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
TEMPLATE = io.open(os.path.join(ROOT, "draft-gen", "compare_template.html"), encoding="utf-8").read()
BRIDGE = io.open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# C1-C3 生成設定画面（ブリッジ配信）
# ---------------------------------------------------------------------------
_origin_def = re.search(
    r"const BRIDGE_ORIGIN = \(location\.protocol === 'http:' \|\| location\.protocol === 'https:'\)\s*"
    r"\?\s*location\.origin\s*:\s*'http://' \+ BRIDGE_HOST;", INDEX)
check("C1 画面が配信元（location.origin）から接続先を決める",
      bool(_origin_def),
      "定義=%s" % (_origin_def.group(0)[:80].replace("\n", " ") if _origin_def else "見つからない"))

check("C2 file:// のときは既定 127.0.0.1:8765 へ倒れる（開き直し案内が壊れない）",
      "const BRIDGE_HOST = '127.0.0.1:8765';" in INDEX
      and "a.href = BRIDGE_ORIGIN + '/'" in INDEX,
      "既定値=%s / 開き直しリンク=%s"
      % ("const BRIDGE_HOST = '127.0.0.1:8765';" in INDEX,
         "a.href = BRIDGE_ORIGIN + '/'" in INDEX))

# 決め打ちの絶対URLが残っていないこと。BRIDGE_HOST の使用は「既定値の定義」と
# 「file:// 用のフォールバック」の2箇所だけであるべき（fetch から直接は使わない）
_bad_fetch = re.findall(r"fetch\(\s*'http://'\s*\+\s*BRIDGE_HOST", INDEX)
_hardcoded = [m for m in re.findall(r"'http://127\.0\.0\.1:\d+", INDEX)]
check("C3 決め打ちの絶対URLが残っていない",
      not _bad_fetch and not _hardcoded,
      "BRIDGE_HOST 直叩き=%d件 / http://127.0.0.1:port の直書き=%s"
      % (len(_bad_fetch), _hardcoded or "なし"))

# ---------------------------------------------------------------------------
# C4-C6 比較画面（file:// で開かれる＝書き出し時に埋める）
# ---------------------------------------------------------------------------
check("C4 比較画面も配信元優先で、file:// のときは埋め込み値を使う",
      "location.origin : '{{BRIDGE_ORIGIN}}'" in TEMPLATE
      and "'http://127.0.0.1:8765'" not in TEMPLATE,
      "テンプレの BASE=%s / 決め打ちの残存=%s"
      % ("location.origin : '{{BRIDGE_ORIGIN}}'" in TEMPLATE,
         "'http://127.0.0.1:8765'" in TEMPLATE))

# 純粋関数を直接突く（環境変数を実プロセスへ入れずに確かめる）
_cases = [
    ({}, "http://127.0.0.1:8765", "未指定は既定"),
    ({"KLK_BRIDGE_PORT": "8766"}, "http://127.0.0.1:8766", "指定どおり"),
    ({"KLK_BRIDGE_PORT": " 8766 "}, "http://127.0.0.1:8766", "前後の空白は無視"),
    ({"KLK_BRIDGE_PORT": "abc"}, "http://127.0.0.1:8765", "数字でなければ既定へ倒す"),
    ({"KLK_BRIDGE_PORT": "99999"}, "http://127.0.0.1:8765", "範囲外は既定へ倒す"),
    ({"KLK_BRIDGE_PORT": ""}, "http://127.0.0.1:8765", "空文字は既定へ倒す"),
]
_ng = ["%s(%s→%s 期待%s)" % (why, env.get("KLK_BRIDGE_PORT", "未設定"),
                             mc.bridge_origin(env), want)
       for env, want, why in _cases if mc.bridge_origin(env) != want]
check("C5 書き出し時のポート決定が、指定・未指定・壊れた値で正しい",
      not _ng, "不一致=%s（%d通り検証）" % (_ng or "なし", len(_cases)))

# ★数字の二重管理を機械照合する（書き写した数字は腐る）
_m = re.search(r"^DEFAULT_PORT = (\d+)", BRIDGE, re.M)
_bridge_default = int(_m.group(1)) if _m else -1
check("C6 ★既定ポートが bridge.py と一致している（二重管理の照合）",
      _bridge_default == mc.DEFAULT_BRIDGE_PORT,
      "bridge.py DEFAULT_PORT=%s / make_compare DEFAULT_BRIDGE_PORT=%s"
      % (_bridge_default, mc.DEFAULT_BRIDGE_PORT))

# ---------------------------------------------------------------------------
# C7 ★実際に書き出して確かめる（テンプレートの読みではなく成果物を見る）
# ---------------------------------------------------------------------------
_sample = os.path.join(ROOT, "samples", "01_カフェ_1カラム")
if os.path.isdir(_sample):
    _saved = os.environ.get("KLK_BRIDGE_PORT")
    try:
        os.environ["KLK_BRIDGE_PORT"] = "8766"
        html = mc.build_compare_html(_sample)
    finally:
        if _saved is None:
            os.environ.pop("KLK_BRIDGE_PORT", None)
        else:
            os.environ["KLK_BRIDGE_PORT"] = _saved
    check("C7 ★実際に書き出した compare.html に指定ポートが入り、埋め残しが無い",
          "'http://127.0.0.1:8766'" in html and "{{" not in html and ":8765'" not in html,
          "8766=%s / 埋め残し=%s / 8765の残存=%s"
          % ("'http://127.0.0.1:8766'" in html, "{{" in html, ":8765'" in html))
else:
    check("C7 ★実際に書き出した compare.html に指定ポートが入り、埋め残しが無い",
          False, "見本フォルダが見つからない: %s" % _sample)

print("=" * 78)
print("KLK-136 ブリッジの接続先をポート決め打ちにしない チェック")
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
