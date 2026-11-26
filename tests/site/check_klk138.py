#!/usr/bin/env python3
"""KLK-138 言葉と色の物差し 静的チェック（Python 標準のみ）

設計: docs/designs/KLK-138.md §4.8 check_klk138.py

  C1 ruler.json が読め、schema・version（=2）・20語・各語の kind・bg・evidence（1件以上）がある
  C2 辞書なし4語の dictLabel が null、辞書あり16語が非 null
  C3 持ち出し禁止: ruler.json・baseline-v1.2.json に色コード（grid.neutrals の8値を除く）・
     キー decidedBy/note/comment/hex（grid.neutrals 内を除く）・外部の配色の出どころが無い
  C4 baseline-v1.2.json の形（20語・辞書なし4語は rate null と status・overall.rate 0〜1・ruler.sha256 一致）
  C5 palette/index.html に klk138 の文字列が無い
  C6 ずれ検査: 判定データがあれば tools/klk138_build_ruler.py --stdout と ruler.json が完全一致（無ければ SKIP）
  C7 持ち出し検査の拡張: 判定データがあれば、設計書・CHANGELOG の KLK-138 項・fixtures に判定のコメント・
     メモの本文（8文字以上の一致）と判定データの色コードが無い（無ければ SKIP）
  ※ 判定データが一部だけ欠けているときは SKIP せず FAIL（C0）

Run: python3 tests/site/check_klk138.py
Exit code 0 = all pass, 1 = at least one fail.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, "tests", "fixtures", "klk138")
RULER = os.path.join(FIX, "ruler.json")
BASELINE = os.path.join(FIX, "baseline-v1.2.json")
PALETTE = os.path.join(ROOT, "palette", "index.html")
BUILD = os.path.join(ROOT, "tools", "klk138_build_ruler.py")
DATA = os.path.join(ROOT, "tickets", "work", "KLK-138")

NO_DICT = {"エレガント", "かっこいい", "スタイリッシュ", "ダーク"}
FORBIDDEN_KEYS = {"decidedBy", "note", "comment", "hex"}
FORBIDDEN_WORDS = ("adobe", "coolors", "color hunt", "colorhunt")

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def walk_keys(o, path=""):
    """(パス, キー) を列挙する。grid.neutrals の中は除く。"""
    if isinstance(o, dict):
        for k, v in o.items():
            p = path + "." + k if path else k
            if p == "grid.neutrals":
                continue
            yield p, k
            yield from walk_keys(v, p)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk_keys(v, "%s[%d]" % (path, i))


ruler = None
ruler_text = ""
try:
    ruler_text = read(RULER)
    ruler = json.loads(ruler_text)
except (OSError, ValueError) as e:
    check("C1 ruler.json が読める", False, str(e))

# C1
if ruler is not None:
    words = ruler.get("words", {})
    bad = []
    for w, d in words.items():
        if d.get("kind") not in ("cells", "elegant", "combo"):
            bad.append(w + ":kind")
        if d.get("bg") not in ("light", "dark", "either"):
            bad.append(w + ":bg")
        if not d.get("evidence"):
            bad.append(w + ":evidence")
        if d.get("kind") == "cells" and not (d.get("cells") or {}).get("ok"):
            bad.append(w + ":cells")
    check("C1 schema・version・20語・kind/bg/evidence が揃う",
          ruler.get("schema") == "klk138-ruler" and ruler.get("version") == 2 and len(words) == 20 and not bad,
          "words=%d %s" % (len(words), " ".join(bad)))

    # C2
    wrong = [w for w, d in words.items() if (d.get("dictLabel") is None) != (w in NO_DICT)]
    check("C2 辞書なし4語は dictLabel=null、辞書あり16語は非 null", not wrong and len(words) == 20, " ".join(wrong))

# C3
baseline = None
baseline_text = ""
try:
    baseline_text = read(BASELINE)
    baseline = json.loads(baseline_text)
except (OSError, ValueError) as e:
    check("C4 baseline-v1.2.json が読める", False, str(e))

if ruler is not None:
    allowed = {n["hex"].lower() for n in ruler.get("grid", {}).get("neutrals", [])}
    name = ""
    amend = os.path.join(DATA, "amendments.json")
    if os.path.exists(amend):
        try:
            name = str(json.loads(read(amend)).get("decidedBy") or "").strip()
        except (OSError, ValueError):
            name = ""
    names = {name, re.sub(r"(さん|様|氏)$", "", name)} - {""}
    for label, text, obj in (("ruler.json", ruler_text, ruler), ("baseline-v1.2.json", baseline_text, baseline)):
        if obj is None:
            continue
        hexes = sorted({h for h in re.findall(r"#[0-9a-fA-F]{6}(?![0-9a-fA-F])", text) if h.lower() not in allowed})
        check("C3 %s に色コードが無い（無彩色・金属8値を除く）" % label, not hexes, " ".join(hexes))
        keys = sorted({p for p, k in walk_keys(obj) if k in FORBIDDEN_KEYS})
        check("C3 %s に decidedBy/note/comment/hex のキーが無い" % label, not keys, " ".join(keys))
        low = text.lower()
        hits = [w for w in FORBIDDEN_WORDS if w in low]
        check("C3 %s に外部の配色の出どころ（adobe 等）が無い" % label, not hits, " ".join(hits))
        if names:
            check("C3 %s に判定者の氏名が無い（判定データがあるときだけ）" % label, not any(n in text for n in names))
        if label == "ruler.json":
            # 無彩色・金属の8値は grid.neutrals にだけ置く
            outside = json.dumps({k: v for k, v in obj.items() if k != "grid"}, ensure_ascii=False)
            leaked = [h for h in allowed if h in outside.lower()]
            check("C3 ruler.json の無彩色・金属の値は grid.neutrals の外に無い", not leaked and len(allowed) == 8,
                  " ".join(leaked))

# C4
if baseline is not None:
    pw = (baseline.get("primary") or {}).get("words") or {}
    ov = (baseline.get("primary") or {}).get("overall") or {}
    nd_ok = all(pw.get(w, {}).get("rate", 0) is None and pw.get(w, {}).get("status") for w in NO_DICT)
    sc_ok = all(isinstance(d.get("rate"), (int, float)) for w, d in pw.items() if w not in NO_DICT)
    rate = ov.get("rate")
    sha = hashlib.sha256(ruler_text.encode("utf-8")).hexdigest()[:16] if ruler_text else ""
    check("C4 baseline の形（20語・辞書なし4語は rate null と status・overall.rate 0〜1）",
          baseline.get("schema") == "klk138-baseline" and len(pw) == 20 and nd_ok and sc_ok
          and isinstance(rate, (int, float)) and 0 <= rate <= 1 and ov.get("wordsScored") == 16,
          "words=%d rate=%s" % (len(pw), rate))
    check("C4 baseline の ruler.sha256 が現在の ruler.json と一致",
          (baseline.get("ruler") or {}).get("sha256") == sha, "%s / %s" % ((baseline.get("ruler") or {}).get("sha256"), sha))
    check("C4 baseline に rulerValidation の欄がある", "rulerValidation" in baseline)

# C5
try:
    check("C5 palette/index.html に klk138 の文字列が無い", "klk138" not in read(PALETTE).lower())
except OSError as e:
    check("C5 palette/index.html が読める", False, str(e))

# 判定データ（Git 外）。全部そろっているか、全部無いかのどちらかでなければならない（MT2）
DATA_FILES = ("klk138-judgments.json", "amendments.json", "klk138-round2.json",
              "klk138-round3.json", "klk138-round3b.json")
present = [f for f in DATA_FILES if os.path.exists(os.path.join(DATA, f))]
missing = [f for f in DATA_FILES if f not in present]
data_state = "all" if not missing else ("none" if not present else "partial")
if data_state == "partial":
    check("C0 判定データが一部だけ欠けていない（全部ある／全部無い のどちらか）", False,
          "欠けている: " + ", ".join(missing))

# C6
if data_state == "none":
    check("C6 ruler.json と生成スクリプトの出力が一致 [SKIP] 判定データが無い（Git除外）", True)
elif data_state == "all":
    proc = subprocess.run([sys.executable, BUILD, "--stdout"], capture_output=True, text=True, cwd=ROOT, timeout=60)
    check("C6 ruler.json と tools/klk138_build_ruler.py --stdout が完全一致",
          proc.returncode == 0 and proc.stdout == ruler_text,
          "rc=%d %s" % (proc.returncode, proc.stderr.strip()[:300]))

# C7 持ち出し検査の拡張（判定データがあるときだけ）:
#   設計書・CHANGELOG の KLK-138 項・tests/fixtures/klk138/ に、判定のコメント・メモの本文（8文字以上の
#   部分一致）と、判定データの色コード（変換の基準色・grid.neutrals の8値を除く）が無いこと
SNIPPET_LEN = 8
BASE_HEX = {"#ffffff", "#000000", "#ff0000", "#808080"}
ROLE_TERMS = ("サブ・アクセント", "メイン", "サブ", "アクセント", "背景")


def judgment_texts():
    texts = []
    for f in DATA_FILES:
        try:
            with open(os.path.join(DATA, f), encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        words = d.get("words")
        if isinstance(words, dict):  # 第1回: words[語].note
            texts += [str(v.get("note") or "") for v in words.values() if isinstance(v, dict)]
        elif isinstance(words, list):  # 第2回以降: words[].note
            texts += [str(v.get("note") or "") for v in words if isinstance(v, dict)]
        texts += [str(c.get("comment") or "") for c in d.get("candidates", []) if isinstance(c, dict)]
    return [t for t in texts if t.strip()]


def judgment_hexes():
    found = set()
    for f in DATA_FILES:
        try:
            found |= {h.lower() for h in re.findall(r"#[0-9a-fA-F]{6}(?![0-9a-fA-F])", read(os.path.join(DATA, f)))}
        except OSError:
            pass
    return found


def changelog_klk138():
    try:
        text = read(os.path.join(ROOT, "CHANGELOG.md"))
    except OSError:
        return ""
    i = text.find("### Added（KLK-138")
    if i < 0:
        return ""
    j = text.find("\n### ", i + 1)
    k = text.find("\n## ", i + 1)
    ends = [x for x in (j, k) if x > 0]
    return text[i:min(ends)] if ends else text[i:]


if data_state == "all":
    targets = []
    for rel in ("docs/designs/KLK-138.md",):
        try:
            targets.append((rel, read(os.path.join(ROOT, rel))))
        except OSError:
            pass
    targets.append(("CHANGELOG.md（KLK-138 項）", changelog_klk138()))
    for f in sorted(os.listdir(FIX)):
        targets.append(("tests/fixtures/klk138/" + f, read(os.path.join(FIX, f))))
    norm = lambda t: re.sub(r"\s+", "", t)
    # 語彙そのもの（代表語・役割名）は本文ではないので区切りとして扱い、断片に含めない
    vocab = sorted(set((ruler or {}).get("words", {}).keys()) | set(ROLE_TERMS), key=len, reverse=True)
    snippets = set()
    for t in judgment_texts():
        t = norm(t)
        for v in vocab:
            t = t.replace(v, "\0")
        for seg in t.split("\0"):
            for i in range(0, max(0, len(seg) - SNIPPET_LEN + 1)):
                snippets.add(seg[i:i + SNIPPET_LEN])
    allowed_hex = BASE_HEX | {n["hex"].lower() for n in (ruler or {}).get("grid", {}).get("neutrals", [])}
    bad_hex = judgment_hexes() - allowed_hex
    for label, text in targets:
        body = norm(text)
        hits = sorted({s for s in snippets if s in body})
        check("C7 %s に判定のコメント・メモの本文が無い（%d文字以上の一致）" % (label, SNIPPET_LEN), not hits,
              "一致した断片: " + " / ".join(hits[:10]))
        hx = sorted({h for h in re.findall(r"#[0-9a-fA-F]{6}(?![0-9a-fA-F])", text) if h.lower() in bad_hex})
        check("C7 %s に判定データの色コードが無い" % label, not hx, " ".join(hx))
elif data_state == "none":
    check("C7 設計書・CHANGELOG・fixtures の持ち出し検査（本文・色コード） [SKIP] 判定データが無い（Git除外）", True)

print("=" * 78)
print("KLK-138 言葉と色の物差し 静的チェック（C1-C7）")
print("=" * 78)
for name, ok, detail in results:
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", name, "" if ok or not detail else "\n       " + detail))
fails = sum(1 for _, ok, _ in results if not ok)
print("-" * 78)
print("%d/%d PASS" % (len(results) - fails, len(results)))
sys.exit(1 if fails else 0)
