#!/usr/bin/env python3
"""
KLK-061 acceptance-condition checker (static / no browser required).

Verifies H1-H9 from docs/designs/KLK-061.md §4 / §9:
「画面と仕様が、実装の現実と食い違っていないこと」を機械的に守る。

  縦串 SCR-001  draft-gen/index.html   （見本サイトURL 欄の未対応明示・sampleUrls の実装維持）
  縦串 SCR-004  draft-gen/catalog.html （自動タグ付けパネルの文言）
  縦串 仕様     docs/SPEC.md           （REQ-102 / REQ-202 / 画面一覧 SCR-003）

本 checker は「嘘の再発」を検出するためのもの。文言そのものを完全一致で固定すると
言い回しの改善すらできなくなるため、**意味の核となるキーワードの有無**で判定する。

★後続チケット（A-1 見本サイトURL の本実装）を行う際は、H1/H2 が意図的に FAIL する。
  そのとき本 checker の H1/H2 を「実装済み」の検証へ更新すること（注記の消し忘れ防止装置を兼ねる）。

Run: python3 tests/site/check_klk061.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INDEX = open(os.path.join(ROOT, "draft-gen", "index.html"), encoding="utf-8").read()
CATHTML = open(os.path.join(ROOT, "draft-gen", "catalog.html"), encoding="utf-8").read()
SPEC = open(os.path.join(ROOT, "docs", "SPEC.md"), encoding="utf-8").read()

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# A-1 見本サイトURL（SCR-001）
# ---------------------------------------------------------------------------
# 見本URL欄を含むセクション（sample-url の前後）を切り出して判定する。
_i = INDEX.find('class="sample-url"')
SEG_URL = INDEX[max(0, _i - 400):_i + 1200] if _i >= 0 else ""

check(
    "H1 SCR-001 の見本URL欄に「生成に反映されない」旨の明示がある",
    "反映されません" in SEG_URL and "対応予定" in SEG_URL,
    "『反映されません』=%s / 『対応予定』=%s" % ("反映されません" in SEG_URL, "対応予定" in SEG_URL),
)

# 旧 placeholder の約束表現（「傾向を参考にします」）が消えていること
check(
    "H2 SCR-001 の placeholder から「傾向を参考にします」という約束表現が消えている",
    "傾向を参考にします" not in INDEX,
    "旧約束表現の残存=%s" % ("傾向を参考にします" in INDEX),
)

# 後方互換: 生成指示書へ sampleUrls を載せる実装は維持されていること（後続の本実装で使う）
check(
    "H3 生成指示書に references.sampleUrls を載せる実装が維持されている（後方互換）",
    "sampleUrls" in INDEX and re.search(r"sampleUrls\s*:\s*sampleUrls", INDEX) is not None,
    "sampleUrls 出現=%d箇所 / references への格納=%s"
    % (INDEX.count("sampleUrls"), re.search(r"sampleUrls\s*:\s*sampleUrls", INDEX) is not None),
)

# 現時点の代替手段（実績サムネ）への導線が案内されていること
check(
    "H1b 未対応の案内が、いま使える代替手段（参考サムネイル）を示している",
    "参考にする素材" in SEG_URL or "サムネイル" in SEG_URL,
    "代替手段の案内=%s" % ("参考にする素材" in SEG_URL or "サムネイル" in SEG_URL),
)

# ---------------------------------------------------------------------------
# A-4 自動タグ付けパネル（SCR-004）
# ---------------------------------------------------------------------------
_m = re.search(r'<div class="at-head">(.*?)</div>', CATHTML, re.S)
AT_HEAD = _m.group(1) if _m else ""
_m = re.search(r'<div class="at-body" id="autotagBody">(.*?)</div>', CATHTML, re.S)
AT_BODY = _m.group(1) if _m else ""

# KLK-064 で実態が変わった: 確認・修正は **Claude Code のチャットではなく SCR-004 の画面**で行う
# （ブリッジ経由は AI が提案を書くだけ・承認は画面・登録は Python）。H4/H5b を新実態へ更新する。
check(
    "H4 SCR-004 の見出しが「この画面で確認・修正してから登録」の実態を示している（KLK-064 で更新）",
    "この画面で確認・修正" in AT_HEAD,
    "at-head=%r" % AT_HEAD.strip()[:80],
)
check(
    "H5 SCR-004 に旧文言「登録前に確認・修正できます」が残っていない",
    "登録前に確認・修正できます" not in CATHTML,
    "旧文言の残存=%s" % ("登録前に確認・修正できます" in CATHTML),
)
check(
    "H5b SCR-004 の本文が「この下に一覧で表示」＝画面完結であることを明示している（KLK-064 で更新）",
    "この下に一覧で表示" in AT_BODY and "この画面には表示されません" not in AT_BODY,
    "新文言=%s / 旧文言(チャット前提)の残存=%s"
    % ("この下に一覧で表示" in AT_BODY, "この画面には表示されません" in AT_BODY),
)
check(
    "H6 SCR-004 の「承認前に確定しません」保証は維持されている（実際に守られている真実）",
    "承認前に確定しません" in AT_BODY,
    "保証の記載=%s" % ("承認前に確定しません" in AT_BODY),
)

# ---------------------------------------------------------------------------
# SPEC（REQ-102 / REQ-202 / 画面一覧 SCR-003）
# ---------------------------------------------------------------------------
def spec_row(req_id):
    m = re.search(r"^\|\s*%s\s*\|.*$" % re.escape(req_id), SPEC, re.M)
    return m.group(0) if m else ""


ROW_102 = spec_row("REQ-102")
ROW_202 = spec_row("REQ-202")
ROW_SCR003 = spec_row("SCR-003")

check(
    "H7 SPEC REQ-102 の備考に「生成には未反映」が書かれている",
    bool(ROW_102) and "未反映" in ROW_102,
    "REQ-102 行の長さ=%d / 未反映=%s" % (len(ROW_102), "未反映" in ROW_102),
)
check(
    "H8 SPEC REQ-202 の備考に「未実装」と実質の履歴 `mockups/` が書かれている",
    bool(ROW_202) and "未実装" in ROW_202 and "mockups/" in ROW_202,
    "未実装=%s / mockups/=%s" % ("未実装" in ROW_202, "mockups/" in ROW_202),
)
check(
    "H9 SPEC 画面一覧の SCR-003 行に未実装の明記がある",
    bool(ROW_SCR003) and "未実装" in ROW_SCR003,
    "SCR-003 行=%r" % ROW_SCR003[:110],
)

print("=" * 78)
print("KLK-061 UI文言を実態へ／SPEC を現状に追従 静的チェック")
print("対象: SCR-001（見本URL）/ SCR-004（自動タグ付けパネル）/ SPEC（REQ-102・REQ-202・SCR-003）")
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
