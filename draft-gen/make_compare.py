#!/usr/bin/env python3
"""compare.html を固定テンプレートから書き出す（KLK-103）。

★なぜこれが要るか
  compare.html の JS（約160行）は**デザインではなく道具立て**で、どの生成物でも
  中身は同じ。にもかかわらず毎回 LLM に書き起こさせていたため、
  KLK-079/080/081/092 で積み上げた振る舞いが**作り直しのたびに落ちた**。
  2026-09-07 の見本作り直しでは6項目中4項目が欠落した（KLK-102）:
    型セレクタ本体 / 現在と違う型だけ送る / typeApplied=false の扱い / 見本ガード
  固定テンプレートにすれば、この種の欠落が**構造的に起きない**。
  あわせて生成する行数が減る（compare.html は出力全体の約25%）。

使い方:
    python3 draft-gen/make_compare.py mockups/2026-09-07_案件名
    python3 draft-gen/make_compare.py mockups/2026-09-07_案件名 --folder samples/01_見本

設計:
  - 決定論。同じ入力から同じ出力（LLM を介さない）。
  - 純関数を先に置き、副作用（読み書き）は末尾に隔離する。テストは純関数を突く。
  - 入力は生成物フォルダの instruction.json と、実在する index ファイル。
    **指示書が無くても動く**（案件名はフォルダ名から復元・fail-soft）。
"""
import datetime
import glob
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(ROOT, "draft-gen", "compare_template.html")

LETTERS = ("a", "b", "c")
LETTER_LABELS = {"a": "案A", "b": "案B", "c": "案C"}
DEFAULT_COLORS = {"main": "#6b7f4e", "sub": "#4a5936",
                  "accent": "#c98a3c", "bg": "#faf8f3"}
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


# ---------------------------------------------------------------------------
# 純関数
# ---------------------------------------------------------------------------
def esc(value):
    """HTML テキストとして安全にする。

    案件名・業種・テイストは人間の自由入力なので、必ず通す。
    """
    return html.escape("" if value is None else str(value), quote=True)


def safe_color(value, fallback):
    """#rrggbb 以外は既定色へ落とす（CSS への注入面を作らない）。"""
    if isinstance(value, str) and HEX_RE.match(value.strip()):
        return value.strip()
    return fallback


def find_variant_files(folder):
    """フォルダにある案のファイルを、`a`/`b`/`c` の順で返す。

    3案なら index-a/b/c.html、単案なら index.html。
    返却: [(letter, filename), …]。単案の letter は "" （案の切替が無い）。
    """
    multi = []
    for L in LETTERS:
        name = "index-%s.html" % L
        if os.path.isfile(os.path.join(folder, name)):
            multi.append((L, name))
    if multi:
        return multi
    if os.path.isfile(os.path.join(folder, "index.html")):
        return [("", "index.html")]
    return []


def read_instruction(folder):
    """instruction.json を読む。無い・壊れていても落ちない（fail-soft）。"""
    p = os.path.join(folder, "instruction.json")
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def project_name_from_folder(folder):
    """`2026-09-07_案件名` から案件名を復元する（指示書が無いときの保険）。"""
    base = os.path.basename(os.path.normpath(folder))
    m = re.match(r"^\d{4}-\d{2}-\d{2}_(.+)$", base)
    return m.group(1) if m else base


def date_from_folder(folder):
    base = os.path.basename(os.path.normpath(folder))
    m = re.match(r"^(\d{4}-\d{2}-\d{2})_", base)
    if m:
        return m.group(1)
    return datetime.date.today().isoformat()


def build_context(folder, instruction, files, data_folder=None):
    """テンプレートへ差し込む値を組み立てる（副作用なし）。"""
    meta = instruction.get("meta") if isinstance(instruction.get("meta"), dict) else {}
    industry = instruction.get("industry") if isinstance(instruction.get("industry"), dict) else {}
    layout = instruction.get("layout") if isinstance(instruction.get("layout"), dict) else {}
    colors = instruction.get("colors") if isinstance(instruction.get("colors"), dict) else {}

    n = len(files)
    project = meta.get("project") or project_name_from_folder(folder)

    ctx = {
        "PROJECT": esc(project),
        "DATE": esc(meta.get("createdAt", "")[:10] or date_from_folder(folder)),
        "VARIANTS": str(n),
        "VARIANT_COUNT": "%d案" % n,
        "TITLE_SUFFIX": "（%d案）" % n if n > 1 else "",
        "INDUSTRY": esc(industry.get("resolved") or industry.get("preset") or "未指定"),
        "COLUMNS": esc(layout.get("columns") or "1col"),
        "TASTE": esc(instruction.get("taste") or "未指定"),
        "ATARI": esc(instruction.get("atari") or "standard"),
        "FOLDER": esc(data_folder or folder.rstrip("/")),
    }
    for key, fallback in DEFAULT_COLORS.items():
        ctx[key.upper()] = safe_color(colors.get(key), fallback)

    ctx["RADIOS"] = render_radios(files)
    ctx["SEG"] = render_seg(files)
    ctx["THUMBSTRIP"] = render_thumbstrip(files)
    ctx["PRINT_BUTTONS"] = render_print_buttons(files)
    ctx["PANES"] = render_panes(files)
    return ctx


def render_radios(files):
    """案切替の隠しラジオ。単案では出さない（切り替える先が無い）。"""
    if len(files) <= 1:
        return "  <!-- 単案なので案切替のラジオは無い（幅切替は下にある・§13） -->"
    out = []
    for i, (L, _) in enumerate(files):
        checked = " checked" if i == 0 else ""
        out.append('  <input class="vswitch" type="radio" name="variant" id="r%s"%s>' % (L, checked))
    return "\n".join(out)


def render_seg(files):
    if len(files) <= 1:
        return ""
    labels = "\n".join('      <label for="r%s">%s</label>' % (L, LETTER_LABELS[L])
                       for L, _ in files)
    return '    <div class="seg">\n%s\n    </div>' % labels


def render_thumbstrip(files):
    if len(files) <= 1:
        return ""
    rows = []
    for L, fn in files:
        rows.append(
            '      <div class="vthumb v%s"><label for="r%s"><div class="mini">'
            '<div class="bar"></div><div class="body"></div></div></label>\n'
            '        <div class="cap"><span>%s</span>'
            '<a href="%s" target="_blank" class="full">原寸 ↗</a></div></div>'
            % (L, L, LETTER_LABELS[L], fn))
    return '    <div class="thumbstrip">\n%s\n    </div>' % "\n".join(rows)


def render_print_buttons(files):
    if len(files) <= 1:
        fn = files[0][1] if files else "index.html"
        return ('    <a class="tb-btn print-btn" href="%s" target="_blank">'
                '🖨 印刷 / PDFで保存</a>' % fn)
    return "\n".join(
        '    <a class="tb-btn print-btn print-%s" href="%s" target="_blank">'
        '🖨 %sを印刷 / PDFで保存</a>' % (L, fn, LETTER_LABELS[L])
        for L, fn in files)


def render_panes(files):
    if len(files) <= 1:
        fn = files[0][1] if files else "index.html"
        return ('    <div class="pane" id="paneA">'
                '<iframe src="%s" title="デザインラフ プレビュー"></iframe></div>' % fn)
    return "\n".join(
        '    <div class="pane" id="pane%s"><iframe src="%s" title="%s プレビュー"></iframe></div>'
        % (L.upper(), fn, LETTER_LABELS[L])
        for L, fn in files)


def render(template, ctx):
    """プレースホルダを埋める。**埋め残しがあれば例外**（黙って壊れた HTML を出さない）。"""
    out = template
    for k, v in ctx.items():
        out = out.replace("{{%s}}" % k, v)
    left = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", out)))
    if left:
        raise ValueError("テンプレートに埋め残しがあります: %s" % ", ".join(left))
    return out


def build_compare_html(folder, data_folder=None, template=None):
    """フォルダを見て compare.html の中身を返す（書き込みはしない）。"""
    files = find_variant_files(folder)
    if not files:
        raise ValueError("案のファイル（index-a.html / index.html）が見つかりません: %s" % folder)
    if template is None:
        with open(TEMPLATE_PATH, encoding="utf-8") as fh:
            template = fh.read()
    ctx = build_context(folder, read_instruction(folder), files, data_folder)
    return render(template, ctx)


# ---------------------------------------------------------------------------
# 副作用
# ---------------------------------------------------------------------------
def write_compare(folder, data_folder=None):
    """compare.html を書き出してパスを返す。"""
    body = build_compare_html(folder, data_folder)
    path = os.path.join(folder, "compare.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    data_folder = None
    for a in argv[1:]:
        if a.startswith("--folder="):
            data_folder = a.split("=", 1)[1]
    if not args:
        print(__doc__)
        return 2
    rc = 0
    for folder in args:
        try:
            p = write_compare(folder, data_folder)
            n = len(find_variant_files(folder))
            print("[OK] %s を書き出しました（%d案）" % (p, n))
        except (ValueError, OSError) as exc:
            print("[NG] %s: %s" % (folder, exc), file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
