# KLK-098 使い方マニュアル（HTML）を unittest スイートへ束ねるラッパー（tester所有）。
# - 静的＋実物突き合わせ: tests/site/check_klk098.py（C0-C29）
# - 追加: マニュアルが**配布物の規律**（外部依存ゼロ）と**社外秘の不記載**を守ること、
#   および README との役割分担が崩れていないことを検査する。
import io
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_CHECKER = ROOT / "tests" / "site" / "check_klk098.py"
MANUAL = ROOT / "使い方マニュアル.html"
README = ROOT / "README.md"


class TestKLK098Static(unittest.TestCase):
    """check_klk098.py（外部依存ゼロ・社外秘不記載・実物との一致）が全PASSすること。"""

    def test_static_checks_pass(self):
        proc = subprocess.run(
            ["python3", str(STATIC_CHECKER)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            "check_klk098.py failed:\n" + proc.stdout + proc.stderr,
        )


class TestKLK098SelfContained(unittest.TestCase):
    """マニュアルは生成物と同じ規律（外部依存ゼロ）に従うこと。

    配布先はネットワークが制限された社内環境かもしれない。
    CDN を1本でも足すと、その環境で崩れて表示される。
    """

    def test_no_network_references(self):
        m = MANUAL.read_text(encoding="utf-8")
        for pat, label in (
            (r'<link\b[^>]*\bhref=', "<link href>"),
            (r'<script\b[^>]*\bsrc=', "<script src>"),
            (r"<(iframe|object|embed)\b", "埋め込み要素"),
        ):
            with self.subTest(label):
                self.assertIsNone(re.search(pat, m, re.I),
                                  "マニュアルに %s がある（外部依存ゼロに違反）" % label)
        # ★localhost は「外部」ではない（ブリッジの画面を開く案内で本文に出る）。
        #   守りたいのは「外のネットワークへ出て行かないこと」。
        #   ここを一緒に弾くと、正しい案内が書けなくなる（実際に落ちた）。
        outside = [u for u in re.findall(r"https?://[^\s\"'<>]+", m)
                   if not re.match(r"https?://(127\.0\.0\.1|localhost)(:|/|$)", u)]
        self.assertFalse(outside, "マニュアルに外部URLがある: %s" % outside[:3])


class TestKLK098NoConfidentialContent(unittest.TestCase):
    """マニュアルはクライアント説明にも使う想定のため、社外秘を載せないこと。

    カタログ（catalog/）は社外秘のご実績を含み、上長承認の条件が
    「社内でのみ使用することを徹底」であるため、実在のエントリを書いてはならない。
    """

    def test_no_catalog_file_references(self):
        m = MANUAL.read_text(encoding="utf-8")
        self.assertNotIn("catalog/img", m)
        self.assertNotIn("catalog.json", m)

    def test_defers_handling_judgement_to_the_responsible_person(self):
        """取り扱いの可否をマニュアルが独断で書かず、確認先を案内していること。"""
        m = MANUAL.read_text(encoding="utf-8")
        self.assertIn("AI利用管理責任者", m)


class TestKLK098DocumentRoles(unittest.TestCase):
    """README とマニュアルの役割分担が崩れていないこと。

    どちらか一方だけを更新すると、受け取った人が読む内容が食い違う
    （README が34件ぶん遅れた KLK-090 と同じ失敗）。
    """

    def test_readme_links_to_manual(self):
        self.assertIn("使い方マニュアル.html", README.read_text(encoding="utf-8"))

    def test_manual_links_back_to_readme(self):
        self.assertGreaterEqual(MANUAL.read_text(encoding="utf-8").count("README.md"), 3)

    def test_manual_is_packaged(self):
        pkg = (ROOT / "tools" / "make-package.sh").read_text(encoding="utf-8")
        self.assertIn("使い方マニュアル.html", pkg,
                      "マニュアルがパッケージに含まれていない")


class TestKLK098ManualIsActuallyServed(unittest.TestCase):
    """★ブリッジを実際に起動して、マニュアルへのリンクが**本当に開けるか**を確かめる。

    最初の実装はファイルシステム上のパスだけを見ており、
    実運用（ブリッジが `/` で画面を配信する）を検証していなかったため、
    理恵さんの環境でリンクが `{"error": "not found"}` になった。
    ルーティング表の静的検査だけでは（書き方を変えれば）すり抜けるので、
    ここでは**実際に HTTP で取りに行く**。
    """

    PORT = 8794

    @classmethod
    def setUpClass(cls):
        import os
        import subprocess
        import time
        import urllib.error
        import urllib.request
        env = dict(os.environ, KLK_BRIDGE_PORT=str(cls.PORT))
        cls.proc = subprocess.Popen(
            ["python3", str(ROOT / "draft-gen" / "bridge.py")],
            cwd=str(ROOT), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        cls.up = False
        for _ in range(50):                      # 最大5秒待つ
            try:
                urllib.request.urlopen(
                    "http://127.0.0.1:%d/health" % cls.PORT, timeout=0.4).read()
                cls.up = True
                break
            except (urllib.error.URLError, OSError):
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except Exception:
            cls.proc.kill()

    def _get(self, path):
        """ブラウザと同じく **percent-encode して** 取りに行く。

        日本語を含むパスは、ブラウザが必ず encode して送る。生の UTF-8 では
        urllib が送信そのものに失敗するので、ここは encode が正しい形であり、
        同時にブリッジ側の unquote 経路を通す検査にもなっている。
        """
        import urllib.parse
        import urllib.request
        url = "http://127.0.0.1:%d%s" % (self.PORT, urllib.parse.quote(path))
        with urllib.request.urlopen(urllib.request.Request(url), timeout=5) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()

    def test_bridge_started(self):
        self.assertTrue(self.up, "ブリッジが起動しなかった（この検査自体が空振りしている）")

    def test_manual_link_opens_through_bridge(self):
        """生成画面に書いてある href が、ブリッジ経由で本当に 200 を返すこと。"""
        if not self.up:
            self.skipTest("ブリッジ未起動")
        ui = (ROOT / "draft-gen" / "index.html").read_text(encoding="utf-8")
        hrefs = set(re.findall(r'<a[^>]*href="([^"]*使い方マニュアル\.html)"', ui))
        self.assertTrue(hrefs, "生成画面にマニュアルへのリンクが無い")
        for h in hrefs:
            # 画面は `/` で配信されるので `../x` は `/x` に解決する
            url = "/" + h.lstrip("./")
            with self.subTest(url):
                status, ctype, body = self._get(url)
                self.assertEqual(status, 200, "%s が %d を返した" % (url, status))
                self.assertIn("text/html", ctype)
                self.assertIn("<title>Kenesis Loop Kit 使い方マニュアル</title>",
                              body.decode("utf-8", "replace"),
                              "%s がマニュアルの中身を返していない" % url)

    def test_every_local_link_on_the_screen_opens(self):
        """★生成画面のローカルリンク**すべて**が、ブリッジ経由で開けること。

        マニュアルのリンクを直したとき、同じ形の壊れ方が
        「もっと探す → 実績カタログを開く」(`catalog.html`) にも残っていた。
        **1本ずつ検査を足していては同じ穴を繰り返す**ので、
        画面上のローカルリンクを列挙して全部叩く。
        """
        if not self.up:
            self.skipTest("ブリッジ未起動")
        ui = (ROOT / "draft-gen" / "index.html").read_text(encoding="utf-8")
        skip = ("http://", "https://", "mailto:", "javascript:", "data:", "#")
        links = sorted({h for h in re.findall(r'href="([^"]+)"', ui)
                        if not h.startswith(skip)})
        self.assertTrue(links, "画面にローカルリンクが無い（検査が空振りしている）")
        for h in links:
            url = "/" + h.lstrip("./") if not h.startswith("/") else h
            with self.subTest(h):
                status, ctype, _ = self._get(url)
                self.assertEqual(
                    status, 200,
                    "画面のリンク %s（→ %s）がブリッジ経由で %d を返した。"
                    "ブリッジに配信口が必要です" % (h, url, status))
                self.assertIn("text/html", ctype)

    def test_every_local_link_exists_as_a_file(self):
        """同じリンクが、ファイルとして開いた場合(file://)にも解決すること。

        href は1本で両方の経路に耐えなければならない。
        """
        ui = (ROOT / "draft-gen" / "index.html").read_text(encoding="utf-8")
        skip = ("http://", "https://", "mailto:", "javascript:", "data:", "#")
        import os
        for h in sorted({h for h in re.findall(r'href="([^"]+)"', ui)
                         if not h.startswith(skip)}):
            with self.subTest(h):
                p = os.path.normpath(os.path.join(str(ROOT), "draft-gen", h))
                self.assertTrue(os.path.isfile(p),
                                "画面のリンク %s がファイルとして解決しない（%s）" % (h, p))

    def test_ascii_alias_also_opens(self):
        """ASCII だけの別名 /manual も開けること（encode に依存しない逃げ道）。"""
        if not self.up:
            self.skipTest("ブリッジ未起動")
        status, ctype, body = self._get("/manual")
        self.assertEqual(status, 200)
        self.assertIn("Kenesis Loop Kit 使い方マニュアル", body.decode("utf-8", "replace"))

    def test_unknown_path_still_404(self):
        """配信口を足したことで、他のパスの 404 が壊れていないこと。"""
        if not self.up:
            self.skipTest("ブリッジ未起動")
        import urllib.error
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._get("/klk098-does-not-exist")
        self.assertEqual(cm.exception.code, 404)


class TestKLK101ScreenLinksOpenInNewTab(unittest.TestCase):
    """生成画面から別画面へ渡るリンクは、すべて別タブで開くこと（理恵さんのご指示）。

    設定を途中まで入力した状態で同じタブに遷移すると、**入力が失われる**。
    マニュアル・配色ジェネレーターは別タブだったのに、実績カタログだけ
    同じタブで開いていた（KLK-101）。1本ずつ直していては揃わないので、
    画面上のローカルリンクを列挙して**全部**に要求する。
    """

    def _links(self):
        ui = (ROOT / "draft-gen" / "index.html").read_text(encoding="utf-8")
        skip = ("http://", "https://", "mailto:", "javascript:", "data:", "#")
        out = []
        for m in re.finditer(r"<a\b[^>]*?>", ui, re.S):
            tag = m.group(0)
            href = re.search(r'href="([^"]+)"', tag)
            if not href or href.group(1).startswith(skip):
                continue
            out.append((href.group(1), tag))
        return out

    def test_links_found(self):
        self.assertTrue(self._links(), "画面にローカルリンクが無い（検査が空振りしている）")

    def test_all_open_in_new_tab(self):
        for href, tag in self._links():
            with self.subTest(href):
                self.assertIn('target="_blank"', tag,
                              "%s が別タブで開かない。入力途中の設定が失われます" % href)

    def test_all_have_noopener(self):
        """別タブで開くリンクには rel="noopener" を付ける（開いた側から元タブを触らせない）。"""
        for href, tag in self._links():
            with self.subTest(href):
                self.assertIn("noopener", tag, "%s に rel=noopener が無い" % href)

    def test_js_does_not_strip_target(self):
        """ブリッジ稼働時に href を差し替える JS が、target を消していないこと。

        `catalogLink` は probeHealth 成功時に href を `/catalog` へ差し替える。
        そのとき target まで書き換えると、別タブ指定が静かに失われる。
        """
        ui = (ROOT / "draft-gen" / "index.html").read_text(encoding="utf-8")
        self.assertNotRegex(
            ui, r"catalogLink[^;]*?\.target\s*=",
            "JS が catalogLink の target を書き換えている（別タブ指定が失われます）")
        for bad in (".target = ''", '.target = ""', ".removeAttribute('target')",
                    '.removeAttribute("target")'):
            self.assertNotIn(bad, ui, "JS が target を外している: %s" % bad)


if __name__ == "__main__":
    unittest.main()
