# -*- coding: utf-8 -*-
"""
A4テンプレートの回帰検知（DADS-002）。

B5対応で spec.py / build_template.py を改修するにあたり、既存のA4版の出力が
変わっていないことを機械的に確認する。

    python build/regress.py                    # 基準と比較。差分があれば終了コード 1
    python build/regress.py --update-baseline  # 現在の出力を基準として保存し直す

基準は dist/.baseline/DADS_A4_Portrait_Template.pptx。
比較は **zip 内のパート単位**で行い、zip に埋まる更新日時は無視する
（同一内容でもファイル全体の SHA256 は毎回変わるため。DADS-001 で確認済みの挙動）。

--update-baseline は「A4を意図的に変更した」ときにだけ人間が実行する。
差分が出たときに安易に基準を更新すると、この検査は意味を失う。
"""
import os
import sys
import zipfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CURRENT = os.path.join(BASE, "dist", "DADS_A4_Portrait_Template.pptx")
BASELINE = os.path.join(BASE, "dist", ".baseline", "DADS_A4_Portrait_Template.pptx")


def parts(path):
    """zip 内のパート名 -> バイト列。更新日時は読まない。"""
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


def compare(baseline_path, current_path):
    base, cur = parts(baseline_path), parts(current_path)
    only_base = sorted(set(base) - set(cur))
    only_cur = sorted(set(cur) - set(base))
    changed = sorted(n for n in set(base) & set(cur) if base[n] != cur[n])
    return only_base, only_cur, changed


def main(argv):
    if "--update-baseline" in argv:
        if not os.path.exists(CURRENT):
            print(f"[エラー] 出力がありません: {CURRENT}")
            return 1
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        with open(CURRENT, "rb") as src, open(BASELINE, "wb") as dst:
            dst.write(src.read())
        print(f"基準を更新しました: {os.path.relpath(BASELINE, BASE)}")
        return 0

    if not os.path.exists(BASELINE):
        print(f"[エラー] 基準がありません: {BASELINE}")
        print("        初回は --update-baseline で作成してください。")
        return 1
    if not os.path.exists(CURRENT):
        print(f"[エラー] 出力がありません: {CURRENT}")
        print("        先に build_template.py を実行してください。")
        return 1

    only_base, only_cur, changed = compare(BASELINE, CURRENT)
    total = len(parts(BASELINE))

    if not (only_base or only_cur or changed):
        print(f"[OK] A4は基準と一致しています（{total} パート）。")
        return 0

    print(f"[NG] A4が基準から変化しています（{total} パート中）")
    for n in only_base:
        print(f"  - 消えたパート: {n}")
    for n in only_cur:
        print(f"  + 増えたパート: {n}")
    for n in changed:
        print(f"  * 中身が変わったパート: {n}")
    print()
    print("A4を変更する意図がなければ実装の誤りです。")
    print("意図した変更であれば --update-baseline で基準を更新してください。")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
