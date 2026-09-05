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
  - 自己完結（外部URL・読み込む先の欠損）＝ NFR-005。※下層ページへの誘導リンク（§4.3 moreLink）は「これから作るページ」なので存在を求めない
  - **compare.html の機能同等性**（幅切替・🔄。1案でも落とさない）＝ KLK-092
  - **composition との一致**（並び・連番・型・見出し）＝ KLK-088。併置 instruction.json と突き合わせる

使い方:
  python3 tools/verify-mockup.py mockups/2026-09-04_案件名
  python3 tools/verify-mockup.py samples/01_カフェ_1カラム --quiet
  python3 tools/verify-mockup.py mockups/*/          # 複数まとめて
  python3 tools/verify-mockup.py mockups/x --strict  # 「注意」も違反として扱う（生成直後の検証用）

exit 0 = 問題なし（「注意」だけなら 0）/ 1 = 違反あり / 2 = 使い方の誤り

違反と注意の別:
  違反 = 生成が壊れている（並び・連番・読み込む先・機能の欠落）
  注意 = 指示書と食い違うが、生成後に 🔄 で変えたのなら正常なもの（型・見出し）
"""
import glob
import json
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
    # ★実体が要るのは「いま読み込むもの」だけ（KLK-088 の実機検証で誤検出して気づいた）。
    #   src= の画像・スクリプト、<link> のCSS、compare.html から各案への相対リンクは必ず在るべき。
    #   一方 <a href="/menu/"> のような**下層ページへの誘導**（§4.3 の moreLink）は、
    #   これから作るページを指すプレースホルダなので、存在しなくて当たり前。
    #   ここを一律に「参照先がありません」と言うと、正しい生成物が毎回赤くなる。
    for u in re.findall(r'src="(?!https?:|#|data:)([^"]+)"', html):
        target = os.path.normpath(os.path.join(os.path.dirname(path), u.split("?")[0]))
        if not os.path.exists(target):
            out.append("読み込む先がありません（src）: %s" % u)
    for tag in re.findall(r"<link\b[^>]*>", html, re.I):
        m = re.search(r'href="(?!https?:|#|data:)([^"]+)"', tag)
        if not m:
            continue
        target = os.path.normpath(os.path.join(os.path.dirname(path), m.group(1).split("?")[0]))
        if not os.path.exists(target):
            out.append("読み込む先がありません（link）: %s" % m.group(1))
    # 同じフォルダの .html への相対リンク（compare.html → index-*.html 等）は在るべき
    for u in re.findall(r'href="(?!https?:|#|data:|mailto:|tel:|/)([^"]+\.html)"', html):
        target = os.path.normpath(os.path.join(os.path.dirname(path), u.split("?")[0]))
        if not os.path.exists(target):
            out.append("リンク先の生成物がありません: %s" % u)
    return out


def check_composition(folder, path, html, notices=None):
    """生成物が併置 instruction.json の composition どおりか照合する（KLK-088）。

    ★ここがこの機能の「規約が効いたか」の判定。
      並び・連番・個別設定は**指示書と突き合わせないと**確かめようがない。
      composition の無い指示書・instruction.json が無いフォルダでは何も言わない（fail-open）。
    """
    out = []
    if notices is None:
        notices = []
    ins = os.path.join(folder, "instruction.json")
    if not os.path.isfile(ins):
        return out
    try:
        with open(ins, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return out
    comp = data.get("composition")
    if not isinstance(comp, list) or not comp:
        return out

    # 期待する番地列（出現順に -01 -02 -03）
    seen = {}
    expected = []
    for e in comp:
        k = (e or {}).get("key")
        if not k:
            continue
        seen[k] = seen.get(k, 0) + 1
        expected.append("%s-%02d" % (k, seen[k]))

    addrs = bridge.list_page_addrs(html)
    body = [a for a in addrs if a.rsplit("-", 1)[0] not in ("NAV", "MV", "FOOTER")]
    # SEARCH は HERO/NAV へ埋め込む方式で独立セクションを出さない（§12.1.3(7)）
    expected_wo_search = [a for a in expected if not a.startswith("SEARCH-")]

    if body != expected_wo_search:
        out.append("composition と並びが違う: 期待 %s / 実際 %s"
                   % (",".join(expected_wo_search), ",".join(body)))
        return out   # 並びが違うなら以降の照合は意味が薄い

    # 番地の一意性（連番が重複すると 🔄 部分再生成が止まる）
    dup = sorted({a for a in addrs if addrs.count(a) > 1})
    if dup:
        out.append("番地が重複している: %s" % ",".join(dup))

    # ★型と見出しは「生成後に 🔄 で変えられる」ので、違反ではなく**注意**として出す（KLK-089）。
    #   並び・連番は 🔄 では変わらないので違反のまま。
    #   ここを一律「違反」にすると、意図的に型を入れ替えたフォルダが毎回赤くなり、
    #   やがて警告そのものが信用されなくなる（KLK-080・KLK-088 と同じ学び）。
    #   生成直後の検証で厳しく見たいときは --strict を使う。
    for addr, e in zip(expected_wo_search, [x for x in comp if x.get("key") != "SEARCH"]):
        want = (e or {}).get("type")
        if not want:
            continue
        got = bridge.read_section_markers(html, addr)
        if got != [want]:
            notices.append(
                "%s の型が指示書と違う: 指示書 %s / 実際 %s"
                "（生成後に 🔄 で変えたのなら正常。生成直後なら指示が無視されている）"
                % (addr, want, got or "読めず"))

    for addr, e in zip(expected_wo_search, [x for x in comp if x.get("key") != "SEARCH"]):
        want = (e or {}).get("heading")
        if not want:
            continue
        start, end = bridge.find_target_section(html, addr)
        if start is None:
            continue
        if want not in html[start:end]:
            notices.append(
                "%s に指示書の見出しが無い: %s"
                "（生成後に 🔄 で作り直したのなら文言が変わることがある）" % (addr, want))
    return out


def check_compare(folder):
    """compare.html が案数に応じた機能を備えているか（KLK-092）。

    ★1案でも幅切替と 🔄 は要る。compare.html を作らないと**その2機能が丸ごと失われる**
      （理恵さんの指摘で判明）。ここは「機能を落としていないか」の番人。
    """
    out = []
    single = os.path.isfile(os.path.join(folder, "index.html"))
    multi = sorted(glob.glob(os.path.join(folder, "index-*.html")))
    cmp_path = os.path.join(folder, "compare.html")
    if not (single or multi):
        return out
    if not os.path.isfile(cmp_path):
        out.append("compare.html がありません（幅切替と 🔄 セクション再生成が使えない状態）")
        return out
    html = open(cmp_path, encoding="utf-8").read()

    # 幅切替（案数によらず要る）
    for needle, label in (('name="vw"', "幅切替の隠しラジオ"),
                          ("vw375", "375px プリセット"),
                          ("vw768", "768px プリセット")):
        if needle not in html:
            out.append("compare.html に%sがありません" % label)
    # 🔄 セクション再生成（案数によらず要る）
    for needle, label in (('id="regen-addr"', "番地セレクタ"),
                          ('id="regen-btn"', "再生成ボタン"),
                          ("/sections?folder=", "セクション一覧の取得")):
        if needle not in html:
            out.append("compare.html に%sがありません（🔄 が使えない）" % label)

    if single and not multi:
        # 単案: 案切替は無し・index.html を指す・letter は空文字
        if 'name="variant"' in html:
            out.append("単案なのに案切替のラジオがあります")
        if 'data-variants="1"' not in html:
            out.append('単案なのに data-variants="1" がありません（JS が letter を誤る）')
        if 'src="index.html"' not in html:
            out.append("単案の iframe が index.html を指していません")
        if "index-a.html" in html:
            out.append("単案なのに index-a.html を参照しています（404 になる）")
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
        return [], [("(フォルダ)", "生成物（index-*.html / index.html）が見つかりません")], []
    findings = []
    notices = []
    for f in files:
        for w in check_file(f):
            findings.append((os.path.basename(f), w))
        # KLK-088: composition との照合（指示書があるときだけ）
        html = open(f, encoding="utf-8").read()
        n = []
        for w in check_composition(folder, f, html, n):
            findings.append((os.path.basename(f), w))
        for w in n:
            notices.append((os.path.basename(f), w))
    # KLK-092: compare.html の機能同等性（フォルダ単位で1回）
    for w in check_compare(folder):
        findings.append(("compare.html", w))
    return files, findings, notices


def main(argv):
    args = [a for a in argv if not a.startswith("-")]
    quiet = "--quiet" in argv or "-q" in argv
    # ★--strict: 「注意」も違反として扱う（KLK-089）。
    #   生成直後の検証（見本の作り直し等）では、指示書との食い違いは
    #   「スキルが指示を無視した」ことを意味するので厳しく見たい。
    strict = "--strict" in argv
    if not args:
        print(__doc__)
        return 2

    total_files = 0
    total_findings = 0
    total_notices = 0
    for folder in args:
        folder = folder.rstrip("/")
        if not os.path.isdir(folder):
            print("[SKIP] フォルダがありません: %s" % folder)
            continue
        files, findings, notices = check_folder(folder)
        if strict:
            findings = findings + notices
            notices = []
        n = len(files or [])
        total_files += n
        total_findings += len(findings)
        total_notices += len(notices)
        head = "%s（%d ファイル）" % (folder, n)
        if findings:
            print("[NG] " + head)
        elif notices:
            print("[注意] " + head)
        elif not quiet:
            print("[OK] " + head)
        for name, w in findings:
            print("       %-14s %s" % (name, w))
        for name, w in notices:
            print("  (注意) %-14s %s" % (name, w))

    print("-" * 70)
    tail = "%d ファイル / 違反 %d 件" % (total_files, total_findings)
    if total_notices:
        tail += " / 注意 %d 件（--strict で違反として扱えます）" % total_notices
    print(tail)
    return 1 if total_findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
