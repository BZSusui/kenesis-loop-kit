#!/usr/bin/env python3
"""KLK-138 言葉と色の物差し（ruler.json）を判定データから生成する。Python 標準のみ。

設計: docs/designs/KLK-138.md §4.2・§4.3

  python3 tools/klk138_build_ruler.py            # tests/fixtures/klk138/ruler.json を書き出す
  python3 tools/klk138_build_ruler.py --stdout   # 書かずに標準出力へ（ずれ検査 C6 用）
  python3 tools/klk138_build_ruler.py --report   # 食い違い・孤立判定の報告（書き出しはしない）

入力（Git 外）: tickets/work/KLK-138/ の
  klk138-judgments.json（第1回）・amendments.json（補正（v4））・klk138-round2.json・
  klk138-round3.json・klk138-round3b.json・verification-2026-11-24.md（外部照合の番号と記号）・
  judge.html（無彩色・金属8マスのシート用近似値）
無ければ「判定データが無い」と表示して終了コード 2。

★ 出力に入れてよいのは、マスの ID と○△、背景の明暗、規則、閾値と根拠（回・案ID・補正の版）だけ。
  判定データの色コード・メモやコメントの本文・判定者の氏名・外部の配色は入れない。
  書き出し前に持ち出し検査を行い、見つかれば書かずに終了コード 1。
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "tickets", "work", "KLK-138")
OUT = os.path.join(ROOT, "tests", "fixtures", "klk138", "ruler.json")

INPUTS = {
    "round1": "klk138-judgments.json",
    "amendments": "amendments.json",
    "round2": "klk138-round2.json",
    "round3": "klk138-round3.json",
    "round3b": "klk138-round3b.json",
    "verification": "verification-2026-11-24.md",
    "judge": "judge.html",
}

# 代表語 → 生成側の辞書ラベル（make_round2.js の DICT と同じ16語）。辞書に無い4語は None。
# 第2段で辞書を作り替えたら、ここを直して再生成する（合格範囲は変えない）。
DICT = {
    "かわいい": "かわいい", "やさしい": "優しい", "ナチュラル": "ナチュラル", "温もりのある": "温かい",
    "元気": "元気", "情熱的な": "情熱", "ポップ": "ポップ", "レトロ": "レトロ", "さわやか": "さわやか",
    "清潔感のある": "清潔", "上品": "上品", "誠実・信頼感のある": "誠実", "知的": "知的",
    "高級感": "高級", "シンプル": "シンプル", "和風": "和風",
    "エレガント": None, "かっこいい": None, "スタイリッシュ": None, "ダーク": None,
}

COMBO = {"かっこいい": "cool", "スタイリッシュ": "stylish", "シンプル": "simple"}

# 蛍光の扱い（補正 v3 neon.byWord）
NEON_POLICY = {"元気": "allow", "ポップ": "allow", "情熱的な": "accentOnly"}

# 外部照合（verification-2026-11-24.md）の行番号。記号はファイルから読む
EXTERNAL = {
    "かわいい": [16], "やさしい": [23], "ナチュラル": [22], "温もりのある": [1, 2], "元気": [15],
    "情熱的な": [3], "ポップ": [24], "レトロ": [21], "さわやか": [6, 7], "清潔感のある": [4, 5],
    "上品": [10], "エレガント": [10, 11], "誠実・信頼感のある": [8, 9], "知的": [25],
    "かっこいい": [13, 14], "スタイリッシュ": [14], "高級感": [10, 12], "シンプル": [18],
    "和風": [19], "ダーク": [20],
}

SYM = {"ok": "○", "maybe": "△", "ng": "×"}


def thr(value, status, basis, gap=None):
    d = {"value": value, "status": status, "basis": basis}
    if gap is not None:
        d["gap"] = gap
    return d


def side(value, source, verdict):
    return {"value": value, "source": source, "verdict": verdict}


THRESHOLDS = {
    "bgLightMinL": thr(0.80, "設計値",
                       "OKLCH L。格子の pale は 0.88〜0.93、生成側の明るい背景は 0.87〜1.00（第2回120案）。"
                       "暗い側 0.18〜0.27 との間で、どちらにも当たらない値"),
    "bgDarkMaxL": thr(0.40, "設計値",
                      "OKLCH L。格子の dark は 0.27〜0.42、生成側の暗い背景は 0.18〜0.27（第2回120案）"),
    "neon": thr({"sMin": 0.60, "vMin": 0.90, "hueRanges": [[50, 200], [280, 345]]}, "補正v3の仮ルール",
                "HSV。補正v3 neon.draftRule をそのまま採用。第2回で判定者が蛍光と名指しした色をすべて検出"),
    "warmVivid": thr({"hueMax": 100, "hueMin": 330, "cMin": 0.10}, "設計値",
                     "OKLCH。h<=100 または h>=330 かつ C>=0.10。外部照合の「鮮やかな暖色」の定義と同じ。"
                     "C<0.10 のアース・ダル寄りの暖色は数えない（補正v3 warmAccent）"),
    "elegant": {
        "hueMin": thr(288, "判定由来（中点）",
                      "メインの OKLCH h がこの値以上なら紫〜ローズ系。○の端と×の中点",
                      {"okSide": side(307, "第3回 A1 ほか", "ok"), "otherSide": side(270, "第3回 X2", "ng")}),
        "hueMax": thr(15, "未検証",
                      "メインの OKLCH h がこの値以下でも紫〜ローズ系。×の判定が無く、○の端に余裕を足した設計値",
                      {"okSide": side(1, "第3回 X1", "ok")}),
        "mainCOkMax": thr(0.106, "補正v4の仮ルール",
                          "紫〜ローズ系メインの OKLCH C がこの値以下なら○、超えて mainCMax 以下なら△。"
                          "補正v4 の仮の値（中点）がギャップの内側なので採用",
                          {"okSide": side(0.092, "第3回追加 P4", "ok"),
                           "otherSide": side(0.120, "第3回追加 P1", "maybe")}),
        "mainCMax": thr(0.15, "補正v3の仮ルール",
                        "紫〜ローズ系メインの OKLCH C がこの値を超えると×。補正v3 の仮の値がギャップの内側なので採用",
                        {"maybeSide": side(0.120, "第3回追加 P1", "maybe"),
                         "otherSide": side(0.179, "第3回追加 P2", "ng")}),
        "beige": thr({"cMin": 0.02, "cMax": 0.10, "hMin": 30, "hMax": 100, "lMin": 0.70}, "設計値",
                     "OKLCH。0.02<=C<0.10 かつ 30<=h<=100 かつ L>=0.70。ベージュ系メイン"
                     "（第3回 A3・A4、追加 B1・B2）はすべて内側。C の範囲は外部照合の「ベージュ系」と同じ"),
        "darkPointMaxL": thr(0.52, "判定由来（中点）",
                             "サブかアクセントの OKLCH L がこの値以下なら「濃い一点」あり",
                             {"okSide": side(0.35, "第3回 A3（0.23）・追加 B1・B2（0.35）", "ok"),
                              "otherSide": side(0.69, "第3回 A4（濃い一点の無い案の最も暗い色）", "maybe")}),
        "darkBgMaxL": thr(0.35, "補正v3の仮ルール",
                          "背景の OKLCH L がこの値未満なら暗い背景。暗い背景の案は 0.23〜0.28（第3回 V1、"
                          "追加 P5・P6・P7。うち○は P7 の 0.28）、明るい背景は 0.95 以上",
                          {"darkSide": side(0.28, "第3回追加 P7", "ok"),
                           "lightSide": side(0.95, "第3回・追加の明るい背景の○案", "ok")}),
        "darkBgAccentMinL": thr(0.85, "補正v3の仮ルール",
                                "暗い背景のときアクセントの OKLCH L がこの値以上で可（満たさなければ△）。"
                                "補正v3 の値がギャップの内側なので採用。追加 P5（0.92）は満たすが△（メインの明るさ）",
                                {"okSide": side(0.89, "第3回追加 P7", "ok"),
                                 "otherSide": side(0.78, "第3回 V1（0.78）・追加 P6（0.75）", "maybe")}),
        "darkBgMainMinL": thr(0.41, "補正v4の仮ルール",
                              "暗い背景のときメインの OKLCH L がこの値以上で可（満たさなければ△）。明るい背景には適用しない"
                              "（追加 P4 は明るい背景でメイン L 0.396 が○）。補正v4 の仮の値（中点）がギャップの内側なので採用",
                              {"okSide": side(0.479, "第3回追加 P7", "ok"),
                               "otherSide": side(0.335, "第3回追加 P5（第3回 V1・追加 P6 も同値）", "maybe")}),
    },
    "combo": {
        "vividCMin": thr(0.10, "設計値", "OKLCH C>=0.10 を「鮮やか」と数える（外部照合の「鮮やか」と同じ境目）"),
        "chromaticCMin": thr(0.04, "設計値", "OKLCH C>=0.04 を有彩色として色相のまとまりに数える"),
        "hueGapDeg": thr(45, "設計値", "有彩色の h を並べ、隣との差がこの値を超えるところで区切った群の数を「色相のまとまり」とする"),
        "monoMain": thr({"cMax": 0.06, "lMax": 0.40}, "設計値", "メインが C<0.06 または L<=0.40 ならモノトーン基調"),
        "pastelMain": thr({"lMin": 0.70, "cMin": 0.04}, "設計値", "メインが L>=0.70 かつ C>=0.04 ならパステルのメイン"),
        "creamBg": thr({"lMin": 0.85, "cMin": 0.02, "cMax": 0.10, "hueMax": 100, "hueMin": 330}, "設計値",
                       "背景が L>=0.85 かつ 0.02<=C<0.10 かつ（h<=100 または h>=330）ならクリームの背景"),
        "pureBlack": thr({"lMax": 0.20, "cMax": 0.02}, "設計値", "L<0.20 かつ C<0.02 を純黒とする"),
        "simpleMetalCells": thr(["n-gold"], "改訂（規則と根拠の矛盾の修正）",
                                "シンプルで金属として扱うマス。単色では銀と淡いグレーを区別できないため金のみ。"
                                "銀を含めると第2回シンプル G1・G2（○）の淡いグレーのメインが×になり、根拠と矛盾していた"),
    },
}

COMBO_EVIDENCE = {
    "かっこいい": "規則: モノトーン基調で○。鮮やかな暖色アクセントは弱い減点で△。蛍光・パステルのメイン・"
                  "カラフル（鮮やか2色以上かつ色相3群以上）は×",
    "スタイリッシュ": "規則: かっこいいの規則に加え、クリームの背景は×",
    "シンプル": "規則: 鮮やか0・色相2群以下・純黒なし・金なしで○。蛍光・鮮やか2色以上・メインが金のマスは×。"
                "第1回で金・銀だけ×（残り△）だった。単色では銀と淡いグレーを区別できないため、金属の×は金だけに適用",
}

def _elegant_evidence(t):
    """エレガントの規則の要約。数値は THRESHOLDS から組み立てる（文と閾値がずれないように）。"""
    return ("規則: 型A（メインが紫〜ローズ系。C<=%g で○・%g 以下で△・超えると×。暗い背景ではアクセント "
            "L>=%g とメイン L>=%g で○、満たさなければ△）／型B（ベージュ系に濃い一点）。どちらでもなければ×"
            "（濃紺＋金は男性的＝×）" % (t["mainCOkMax"]["value"], t["mainCMax"]["value"],
                                    t["darkBgAccentMinL"]["value"], t["darkBgMainMinL"]["value"]))


ELEGANT_EVIDENCE = _elegant_evidence(THRESHOLDS["elegant"])


def die(msg, code):
    print(msg, file=sys.stderr)
    sys.exit(code)


def load_inputs():
    paths = {k: os.path.join(DATA, v) for k, v in INPUTS.items()}
    missing = [INPUTS[k] for k, p in paths.items() if not os.path.exists(p)]
    if missing:
        die("[判定データが無い] tickets/work/KLK-138/ に次が無い（Git除外）: " + ", ".join(missing), 2)
    data = {}
    for k in ("round1", "amendments", "round2", "round3", "round3b"):
        with open(paths[k], encoding="utf-8") as f:
            data[k] = json.load(f)
    with open(paths["verification"], encoding="utf-8") as f:
        data["verification"] = f.read()
    with open(paths["judge"], encoding="utf-8") as f:
        data["judge"] = f.read()
    return data


def parse_neutrals(judge_html):
    m = re.search(r"const NEUTRALS = \[(.*?)\n\];", judge_html, re.S)
    if not m:
        die("[判定データが無い] judge.html の NEUTRALS が読めない", 2)
    out = []
    for key, name, hx in re.findall(r"\['(\w+)',\s*'([^']+)',\s*'(#[0-9a-fA-F]{6})'", m.group(1)):
        out.append({"key": key, "name": name, "hex": hx.lower()})
    if len(out) != 8:
        die("[判定データが無い] judge.html の NEUTRALS が8件でない", 2)
    return out


def parse_verification(md):
    """外部照合の表から {番号: 記号} を取り出す（数値・本文は写さない）。"""
    out = {}
    for line in md.splitlines():
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) >= 8 and cols[0].isdigit():
            out[int(cols[0])] = cols[6]
    return out


def ids(lst):
    return sorted({c["id"] for c in lst})


def tone_summary(cell_ids, tones, hues):
    parts = []
    for t in tones:
        n = sum(1 for h in hues if "%s-%03d" % (t, h) in cell_ids)
        if n == len(hues):
            parts.append("%s 全色相" % t)
        elif n:
            parts.append("%s %d色相" % (t, n))
    neutrals = sorted(c[2:] for c in cell_ids if c.startswith("n-"))
    if neutrals:
        parts.append("無彩色・金属 " + "・".join(neutrals))
    return "、".join(parts)


def round_marks(cands, word):
    rows = sorted((c["source"], c["verdict"]) for c in cands if c["word"] == word)
    return "・".join("%s %s" % (s, SYM[v]) for s, v in rows)


def build(data):
    r1 = data["round1"]
    am = data["amendments"]
    tones = [{"key": t["key"], "name": t["name"], "s": t["s"], "l": t["l"]} for t in r1["grid"]["tones"]]
    tone_keys = [t["key"] for t in tones]
    hues = [h["h"] for h in r1["grid"]["hues"]]
    neutrals = parse_neutrals(data["judge"])
    ext = parse_verification(data["verification"])
    amw = am["words"]
    av = am.get("version")
    warm_words = set(am.get("warmAccent", {}).get("words", []))

    words = {}
    for word in DICT:
        src = r1["words"][word]
        ok = set(ids(src["ok"]))
        maybe = set(ids(src["maybe"]))
        evidence = []
        if word in COMBO:
            kind = "combo"
        elif word == "エレガント":
            kind = "elegant"
        else:
            kind = "cells"
        d = {"kind": kind, "dictLabel": DICT[word], "bg": src["bg"]}
        if kind == "cells":
            amd_ev = []
            ok_when = []
            a = amw.get(word, {})
            if "conditional" in a:
                ct = set(a["conditional"]["tones"])
                m = re.search(r"age\s*>=\s*([0-9.]+)", a["conditional"]["passWhen"])
                age_min = float(m.group(1))
                cond_cells = sorted(c for c in maybe if c.split("-")[0] in ct)
                ok_when.append({"cells": cond_cells, "ageMin": age_min})
                amd_ev.append("%s の△は age>=%s でメイン可（大人かわいい）" % ("/".join(sorted(ct)), age_min))
            if "accentOnly" in a:
                amd_ev.append("%s は差し色のみ（△のまま）" % "/".join(a["accentOnly"]["tones"]))
            if "okToMaybe" in a:
                hs = set(a["okToMaybe"]["hues"])
                moved = sorted(c for c in ok if not c.startswith("n-") and int(c.split("-")[1]) in hs)
                ok -= set(moved)
                maybe |= set(moved)
                amd_ev.append("色相 %s の○ %dマスを△へ" % ("・".join(str(h) for h in sorted(hs)), len(moved)))
            if word == "高級感":
                amd_ev.append("第1回の高級感のマスだけを使う。旧エレガントの判定は食い違いの確認にだけ使う")
            d["cells"] = {"ok": sorted(ok), "maybe": sorted(maybe)}
            if ok_when:
                d["okWhen"] = ok_when
            evidence.append({"source": "第1回判定", "summary": "○%dマス（%s）、△%dマス、背景 %s" % (
                len(ok), tone_summary(ok, tone_keys, hues), len(maybe), src["bg"])})
            if amd_ev:
                evidence.append({"source": "補正v%s" % av, "summary": "。".join(amd_ev)})
        elif kind == "elegant":
            d["bg"] = "either"
            evidence.append({"source": "補正v%s" % av, "summary": "第1回・第2回の判定は高級感寄りだったため高級感の根拠へ移し、"
                             "エレガントを再定義（紫〜ローズ系の明るい／くすんだ配色、ベージュ系＋濃い一点、女性的）"})
            evidence.append({"source": "第3回判定", "summary": round_marks(data["round3"]["candidates"], word)})
            evidence.append({"source": "第3回追加判定", "summary": round_marks(data["round3b"]["candidates"], word)})
            evidence.append({"source": "規則", "summary": ELEGANT_EVIDENCE})
        else:
            d["comboType"] = COMBO[word]
            evidence.append({"source": "第1回判定", "summary": "○0マス・△%dマス（マスでは区別できないため使わない）" % len(maybe)})
            evidence.append({"source": "規則", "summary": COMBO_EVIDENCE[word]})
        d["neonPolicy"] = NEON_POLICY.get(word, "standard")
        d["warmAccentPolicy"] = "weak" if word in warm_words else "none"
        if word in warm_words:
            evidence.append({"source": "補正v%s" % av, "summary": "鮮やかな暖色アクセントは弱い減点（○→△）"})
        if word == "ダーク":
            evidence.append({"source": "補正v%s" % av, "summary": "補正なし。第1回のマスどおり・背景 dark"})
        r2 = round_marks(data["round2"]["candidates"], word)
        if r2:
            label = "第2回判定（高級感の根拠へ移した旧エレガント）" if word == "エレガント" else "第2回判定"
            evidence.append({"source": label, "summary": r2})
        if word == "高級感":
            evidence.append({"source": "第2回判定（旧エレガント・参考）",
                             "summary": round_marks(data["round2"]["candidates"], "エレガント")})
        ex = ["#%d %s" % (n, ext.get(n, "—")) for n in EXTERNAL.get(word, [])]
        if ex:
            evidence.append({"source": "外部照合", "summary": "・".join(ex)})
        d["evidence"] = evidence
        words[word] = d

    def ver(k, keys):
        return {kk: data[k][kk] for kk in keys if kk in data[k]}

    ruler = {
        "schema": "klk138-ruler",
        "version": 2,
        "judgedBy": "判定者（人間）",
        "sources": {
            "round1": ver("round1", ["schema", "version", "exportedAt"]),
            "round2": ver("round2", ["schema", "version", "exportedAt"]),
            "round3": ver("round3", ["schema", "version", "exportedAt"]),
            "round3b": ver("round3b", ["schema", "version", "exportedAt"]),
            "amendments": ver("amendments", ["schema", "version"]),
        },
        "scoring": {"points": {"ok": 1, "maybe": 0.5, "ng": 0}, "wordPassMin": 0.75},
        "grid": {"tones": tones, "hues": hues, "toneLightnessWeight": 2, "neutrals": neutrals},
        "thresholds": THRESHOLDS,
        "words": words,
    }
    return ruler


def dumps(ruler):
    return json.dumps(ruler, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def leak_check(text, ruler, amendments):
    """持ち出し検査。問題の一覧を返す（空なら合格）。"""
    problems = []
    allowed = {n["hex"].lower() for n in ruler["grid"]["neutrals"]}
    for hx in re.findall(r"#[0-9a-fA-F]{6}(?![0-9a-fA-F])", text):
        if hx.lower() not in allowed:
            problems.append("色コード " + hx)
    name = str(amendments.get("decidedBy") or "").strip()
    cands = {name, re.sub(r"(さん|様|氏)$", "", name)} - {""}
    for c in cands:
        if c in text:
            problems.append("判定者の氏名（amendments.json decidedBy）")
            break
    low = text.lower()
    for w in ("adobe", "color hunt", "colorhunt", "coolors"):
        if w in low:
            problems.append("外部の配色の出どころ: " + w)
    return problems


def report(data, ruler):
    r1 = data["round1"]["words"]
    tone_keys = [t["key"] for t in ruler["grid"]["tones"]]
    hues = ruler["grid"]["hues"]
    print("=" * 72)
    print("KLK-138 --report（Git には書かない。人間の確認用）")
    print("=" * 72)
    lux_ok, lux_maybe = set(ids(r1["高級感"]["ok"])), set(ids(r1["高級感"]["maybe"]))
    ele_ok, ele_maybe = set(ids(r1["エレガント"]["ok"])), set(ids(r1["エレガント"]["maybe"]))
    print("\n[1] 高級感（第1回）と旧エレガント（第1回）の食い違い")
    for label, a in (("高級感だけ○", sorted(lux_ok - ele_ok)), ("旧エレガントだけ○", sorted(ele_ok - lux_ok)),
                     ("高級感だけ△", sorted(lux_maybe - ele_maybe)), ("旧エレガントだけ△", sorted(ele_maybe - lux_maybe))):
        print("  %s: %d  %s" % (label, len(a), " ".join(a)))
    print("  背景: 高級感=%s／旧エレガント=%s" % (r1["高級感"]["bg"], r1["エレガント"]["bg"]))

    print("\n[2] 孤立した判定（同じトーンの12色相で1マスだけ判定が違う）")
    found = 0
    for word in DICT:
        w = r1[word]
        ok, maybe = set(ids(w["ok"])), set(ids(w["maybe"]))
        for t in tone_keys:
            st = []
            for h in hues:
                cid = "%s-%03d" % (t, h)
                st.append("ok" if cid in ok else "maybe" if cid in maybe else "none")
            for i, s in enumerate(st):
                others = st[:i] + st[i + 1:]
                if len(set(others)) == 1 and others[0] != s:
                    found += 1
                    print("  %s: %s-%03d は %s（同じ行の他11色相は %s）" % (word, t, hues[i], s, others[0]))
    if not found:
        print("  なし")
    print("\n※ 原本を正として物差しはそのまま使う。")


def main(argv):
    data = load_inputs()
    ruler = build(data)
    text = dumps(ruler)
    problems = leak_check(text, ruler, data["amendments"])
    if problems:
        die("[持ち出し検査 NG] 書き出しを中止した: " + "; ".join(sorted(set(problems))), 1)
    if "--report" in argv:
        report(data, ruler)
        return 0
    if "--stdout" in argv:
        sys.stdout.write(text)
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote " + os.path.relpath(OUT, ROOT) + "（20語・持ち出し検査 OK）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
