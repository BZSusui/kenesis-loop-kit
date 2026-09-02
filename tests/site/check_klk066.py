#!/usr/bin/env python3
"""
KLK-066 acceptance-condition checker (static + 純関数の実行 / no browser required).

Verifies C1-C10 from docs/designs/KLK-066.md §4.4 / §9:
登録後に取り込み待ち画像・提案JSONが残り、表示が実態とずれる不具合の修正。

  縦串 ブリッジ  draft-gen/bridge.py     （pending_groups / pending_display_name / 片付け）
  縦串 スキル    catalog-import/SKILL.md （再変換の抑止・sourceFile の記録）

★この checker が守っているもの:
  `.pending/` の `pnd-X.webp` と `pnd-X.png` は**同じ画像の2表現**である。
  この前提が崩れると「画像1枚なのに2件」と表示され、登録後も残骸が積み上がり、
  取り込みのたびに再変換されて**同一画像の二重登録**を誘発する（実際に cat-0054 と
  cat-0056 がバイト単位で同一という事故が起きた）。

Run: python3 tests/site/check_klk066.py
Exit code 0 = all static checks pass, 1 = at least one fail.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE_SRC = open(os.path.join(ROOT, "draft-gen", "bridge.py"), encoding="utf-8").read()
SKILL = open(os.path.join(ROOT, ".claude", "skills", "catalog-import", "SKILL.md"), encoding="utf-8").read()

sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
import bridge  # noqa: E402

results = []


def check(name, passed, detail):
    results.append((name, bool(passed), detail))


# ---------------------------------------------------------------------------
# C1-C2 純関数（実行して検証）
# ---------------------------------------------------------------------------
pg = getattr(bridge, "pending_groups", None)
pd = getattr(bridge, "pending_display_name", None)

if pg is None:
    check("C1 pending_groups が basename でグループ化する", False, "未定義")
else:
    g = pg(["pnd-X.webp", "pnd-X.png", "pnd-Y.jpg", "pnd-Z.webp", "", None])
    ok = (set(g.keys()) == {"pnd-X", "pnd-Y", "pnd-Z"}
          and g["pnd-X"] == ["pnd-X.png", "pnd-X.webp"]
          and g["pnd-Y"] == ["pnd-Y.jpg"]
          and pg([]) == {} and pg(None) == {})
    check("C1 pending_groups が basename でグループ化する（不正値は無視）", ok, "groups=%s" % g)

if pd is None:
    check("C2 pending_display_name が png > jpg > webp の順で代表を選ぶ", False, "未定義")
else:
    ok = (pd(["pnd-X.webp", "pnd-X.png"]) == "pnd-X.png"
          and pd(["pnd-Y.webp", "pnd-Y.jpg"]) == "pnd-Y.jpg"
          and pd(["pnd-Z.webp"]) == "pnd-Z.webp"
          and pd([]) is None)
    check("C2 pending_display_name が png > jpg > webp の順で代表を選ぶ", ok,
          "png優先=%r / jpg優先=%r / webpのみ=%r"
          % (pd(["pnd-X.webp", "pnd-X.png"]), pd(["pnd-Y.webp", "pnd-Y.jpg"]), pd(["pnd-Z.webp"])))

# ---------------------------------------------------------------------------
# C3-C7 ブリッジ（計数・片付けの順序と範囲）
# ---------------------------------------------------------------------------
_i = BRIDGE_SRC.find("def _pending_names_count")
CNT = BRIDGE_SRC[_i:BRIDGE_SRC.find("def _purge_pending_siblings")] if _i >= 0 else ""
check(
    "C3 _pending_names_count がグループ化を使っている（同一画像を二重に数えない）",
    "pending_groups(raw)" in CNT and "pending_display_name(g)" in CNT,
    "groups=%s / display_name=%s" % ("pending_groups(raw)" in CNT, "pending_display_name(g)" in CNT),
)

_i = BRIDGE_SRC.find("def _catalog_commit")
_FULL = BRIDGE_SRC[_i:BRIDGE_SRC.find("def _generate(self)")] if _i >= 0 else ""
_ds = _FULL.find('"""', _FULL.find('"""') + 3)
CBODY = _FULL[_ds + 3:] if _ds > 0 else _FULL
i_replace = CBODY.find("os.replace(tmp")
i_purge_sib = CBODY.find("_purge_pending_siblings(")
i_purge_prop = CBODY.find("_purge_proposals()")
check(
    "C4 片付けが os.replace（登録の確定）より後に行われる",
    i_replace >= 0 and i_purge_sib > i_replace and i_purge_prop > i_replace,
    "os.replace=%d / 兄弟削除=%d / 提案削除=%d" % (i_replace, i_purge_sib, i_purge_prop),
)
_i = BRIDGE_SRC.find("def _purge_pending_siblings")
SIB = BRIDGE_SRC[_i:BRIDGE_SRC.find("def _purge_proposals")] if _i >= 0 else ""
_i = BRIDGE_SRC.find("def _purge_proposals")
PROP = BRIDGE_SRC[_i:BRIDGE_SRC.find("def _catalog_pending", _i)] if _i >= 0 else ""
check(
    "C5 片付けの失敗を握りつぶす（登録を巻き戻さない）",
    "except OSError as exc" in SIB and "except OSError as exc" in PROP
    and "raise" not in SIB and "raise" not in PROP,
    "兄弟側の握りつぶし=%s / 提案側の握りつぶし=%s / raise なし=%s"
    % ("except OSError as exc" in SIB, "except OSError as exc" in PROP,
       "raise" not in SIB and "raise" not in PROP),
)
check(
    "C6 提案JSON（*.proposal.json）を全削除する",
    bool(PROP) and 'n.endswith(".proposal.json")' in PROP and "os.remove(" in PROP,
    "全走査=%s / 削除=%s" % ('n.endswith(".proposal.json")' in PROP, "os.remove(" in PROP),
)
check(
    "C7 削除対象が catalog/.pending/ 配下に限定されている（catalog/img/ を消さない）",
    bool(SIB) and "catalog_pending_dir" in SIB and "is_safe_catalog_name(n)" in SIB
    and "os.path.dirname(os.path.abspath(path))" in SIB
    and "catalog_img_dir" not in SIB and "catalog_img_dir" not in PROP,
    "pending限定=%s / 安全名=%s / 配下確認=%s / img_dir 非参照=%s"
    % ("catalog_pending_dir" in SIB, "is_safe_catalog_name(n)" in SIB,
       "os.path.dirname(os.path.abspath(path))" in SIB,
       "catalog_img_dir" not in SIB and "catalog_img_dir" not in PROP),
)

# ---------------------------------------------------------------------------
# C8 sourceFile の受理（純関数）
# ---------------------------------------------------------------------------
vp = bridge.validate_proposal
good = {"schema": "klk-catalog-proposal", "version": 1,
        "items": [{"file": "pnd-X.png", "sourceFile": "pnd-X.webp"}]}
bad = {"schema": "klk-catalog-proposal", "version": 1,
       "items": [{"file": "pnd-X.png", "sourceFile": "../../etc/passwd"}]}
nokey = {"schema": "klk-catalog-proposal", "version": 1, "items": [{"file": "pnd-X.png"}]}
check(
    "C8 validate_proposal が sourceFile を任意で受理し、危険な名前を弾く",
    vp(good)[0] is True and vp(bad)[0] is False and vp(nokey)[0] is True,
    "正常=%s / 危険=%s / 省略可=%s" % (vp(good)[0], vp(bad)[0], vp(nokey)[0]),
)

# ---------------------------------------------------------------------------
# C9-C10 スキル
# ---------------------------------------------------------------------------
check(
    "C9 SKILL.md に「png が既にあれば再変換しない」が明記されている",
    "`sips` を実行しない" in SKILL and "KLK-066" in SKILL,
    "明記=%s" % ("`sips` を実行しない" in SKILL),
)
check(
    "C10 SKILL.md に sourceFile を書く指示があり、提案の例にも含まれる",
    "`sourceFile`（変換元の webp 名）を書く" in SKILL and '"sourceFile"' in SKILL,
    "指示=%s / 例=%s"
    % ("`sourceFile`（変換元の webp 名）を書く" in SKILL, '"sourceFile"' in SKILL),
)

print("=" * 78)
print("KLK-066 取り込み待ちの残留物と表示ずれの修正 静的チェック")
print("対象: bridge.py（グループ計数・登録後の片付け）/ catalog-import SKILL")
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
