#!/usr/bin/env python3
"""生成物フォルダを規約に照らして検査する（KLK-080）。

なぜあるか:
  KLK-072〜076 で4回続けて「規約は正しいのに生成物が違う」を、30分かけて再生成し目視で拾った。
  KLK-076 で samples/ の実物検査を自動化し、KLK-080 でそれを**任意の生成物フォルダ**へ広げた。
  見本を作り直すとき（第5期）や、型を入れ替えたあとの確認に、そのまま使える。

見るもの（機械検査できるものだけ・判定できないものは黙る）:
  - §3.0  極端な横長比率 / min-height だけで高さを決めたアタリ
  - §12.1.3 masonry・mosaic の大小混在と最終行の充填
  - §8.1  2カラム/3カラムでの画像と本文の横並び
  - 型マーカーが1セクションに2つ以上付いていないか
  - 番地の一意性（重複・特定できないブロック）
  - 自己完結（外部URL・相対参照の欠損）＝ NFR-005

使い方:
  python3 tools/verify-mockup.py mockups/2026-09-04_案件名
  python3 tools/verify-mockup.py samples/01_カフェ_1カラム --quiet
  python3 tools/verify-mockup.py mockups/*/          # 複数まとめて

exit 0 = 問題なし / 1 = 違反あり / 2 = 使い方の誤り
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "draft-gen"))
try:
    import bridge
except Exception as exc:  # pragma: no cover - 依存はローカルのみ
    print("draft-gen/bridge.py を読み込めません: %s" % exc, file=sys.stderr)
    sys.exit(2)


def check_file(path):
    """1ファイルを検査して警告のリストを返す。"""
    out = []
    html = open(path, encoding="utf-8").read()
    addrs = bridge.list_page_addrs(html)
    if not addrs:
        out.append("番地（<span class=\"pin\">）が1つも見つかりません")
        return out

    for addr in addrs:
        start, info = bridge.find_target_section(html, addr)
        if start is None:
            out.append("%s: セクションのブロックを特定できません（%s）" % (addr, info))
            continue
        out.extend(bridge.find_quality_warnings(html, addr))

    # 自己完結（NFR-005）— localhost は例外（🔄 のブリッジ呼び出し）
    for u in re.findall(r'https?://[^"\'\s)]+', html):
        if re.match(r"https?://(127\.0\.0\.1|localhost)(:|/)", u) or "w3.org" in u:
            continue
        out.append("外部URLがあります: %s" % u)
    for u in re.findall(r'(?:src|href)="(?!https?:|#|data:|mailto:|tel:)([^"]+)"', html):
        target = os.path.normpath(os.path.join(os.path.dirname(path), u.split("?")[0]))
        if not os.path.exists(target):
            out.append("参照先がありません: %s" % u)
    return out


def check_folder(folder):
    """フォルダ内の index-*.html / index.html を検査する。"""
    files = sorted(glob.glob(os.path.join(folder, "index-*.html")))
    if not files:
        single = os.path.join(folder, "index.html")
        if os.path.isfile(single):
            files = [single]
    if not files:
        # 呼び出し側と形をそろえる（(ファイル名, 警告) のタプル）
        return [], [("(フォルダ)", "生成物（index-*.html / index.html）が見つかりません")]
    findings = []
    for f in files:
        for w in check_file(f):
            findings.append((os.path.basename(f), w))
    return files, findings


def main(argv):
    args = [a for a in argv if not a.startswith("-")]
    quiet = "--quiet" in argv or "-q" in argv
    if not args:
        print(__doc__)
        return 2

    total_files = 0
    total_findings = 0
    for folder in args:
        folder = folder.rstrip("/")
        if not os.path.isdir(folder):
            print("[SKIP] フォルダがありません: %s" % folder)
            continue
        files, findings = check_folder(folder)
        n = len(files or [])
        total_files += n
        total_findings += len(findings)
        head = "%s（%d ファイル）" % (folder, n)
        if findings:
            print("[NG] " + head)
            for name, w in findings:
                print("       %-14s %s" % (name, w))
        elif not quiet:
            print("[OK] " + head)

    print("-" * 70)
    print("%d ファイル / 違反 %d 件" % (total_files, total_findings))
    return 1 if total_findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
