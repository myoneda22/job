#!/usr/bin/env python3
"""不自然な日本語の機械検出。

機械的に判定できるパターンだけを報告する。網羅はしないし誤検出もする。
出力は「候補」であって確定ではない。必ず原文を読んで採否を決めること。

主述のねじれ、論理の飛躍、語彙選択、段落構成は検出できない。人が読むこと。

使い方:
    python3 detect.py FILE [FILE ...]
    cat draft.md | python3 detect.py -
    python3 detect.py draft.md --json
    python3 detect.py draft.md --only notation,grammar
    python3 detect.py draft.md --min-severity warn

終了コード: error が1件でもあれば 1、それ以外は 0。
"""

import argparse
import json
import re
import sys

SEVERITIES = {"error": 3, "warn": 2, "info": 1}
CATEGORIES = ("grammar", "translationese", "ai", "notation", "structure")

# (id, category, severity, regex, message, suggestion)
RULES = [
    # ---- 層1: 文法 ----
    ("ra-nuki", "grammar", "error",
     r"(?:見|観|出|着|寝|居|似|煮|来|閉じ|生き|起き|降り|借り|信じ|感じ|過ぎ|落ち|飽き|"
     r"食べ|決め|止め|辞め|集め|始め|続け|受け|付け|開け|閉め|変え|考え|教え|覚え|"
     r"数え|答え|与え|加え|逃げ|投げ|調べ|比べ|並べ)れ(?=る|ま[すせ]|な[いくかけ]|た|て|ちゃ|よ)",
     "ら抜き言葉。書き言葉では避ける", "「〜られる」にする"),

    ("sa-ire", "grammar", "error",
     r"(?:読ま|行か|書か|聞か|歌わ|使わ|買わ|言わ|思わ|願わ|待た|持た|立た|勝た|"
     r"飲ま|休ま|住ま|込ま|帰ら|作ら|送ら|取ら|座ら|入ら|やら|振ら|走ら)さ(?=せて|せます|せた|せる)",
     "さ入れ言葉。五段動詞に不要な「さ」", "「〜せて」にする（例: 読まさせて→読ませて）"),

    ("keigo-double", "grammar", "error",
     r"おっしゃられ|お[一-龠ぁ-ん]{1,4}になられ|ご[一-龠]{1,6}になられ|"
     r"拝(?:見|読|聴|借)させていただ|お伺いさせていただ|お召し上がりになら",
     "二重敬語", "敬語は一語に一つ（例: お伺いさせていただきます→伺います）"),

    ("itadaku", "grammar", "info",
     r"させていただ",
     "「させていただく」。相手の許可・恩恵が実際にない場面では過剰",
     "「〜します」「〜いたします」で足りないか確認する"),

    ("tari-single", "grammar", "info",
     r"たり、(?:[^。]{1,30})(?<!たり)(?:し|する|した|です|ます)。",
     "「たり」が片側だけの可能性", "並列の「たり」は繰り返す（〜たり〜たりする）"),

    ("double-negative", "grammar", "info",
     r"な(?:い|く)(?:わけ|こと)(?:では|じゃ)ない|できないわけではない",
     "二重否定。読みにくい", "肯定で言い切れないか確認する"),

    # ---- 層2: 翻訳調 ----
    ("pronoun-head", "translationese", "warn",
     r"(?:^|(?<=[。！？]))(?:私は|私たちは|我々は|あなたは|あなたが|それは|それらは|これらは|彼は|彼らは|彼女は)",
     "文頭の代名詞。日本語は主語を省くのが標準",
     "文脈から復元できるなら落とす"),

    ("koto-ga-dekiru", "translationese", "warn",
     r"ことができ",
     "「〜することができる」は冗長", "「〜できる」にする"),

    ("wo-okonau", "translationese", "warn",
     r"を(?:行|おこな)(?:う|い|っ|え|わ)|を実施(?:する|し|さ)",
     "サ変名詞＋「を行う／を実施する」は冗長", "動詞にする（検討を行う→検討する）"),

    ("toiu", "translationese", "warn",
     r"という(?:こと|点|もの|形|わけ|意味|事実)",
     "「という」の水増し", "多くの場合そのまま削れる"),

    ("ni-oite", "translationese", "warn",
     r"における|において(?:は|も|の)?",
     "硬い漢語の水増し", "「〜の」「〜での」で足りないか確認する"),

    ("ni-kanshite", "translationese", "info",
     r"に関(?:して|しまして|する|しては)",
     "「〜に関して」", "「〜について」「〜の」で足りることが多い"),

    ("kanou-desu", "translationese", "warn",
     r"が可能(?:です|である|だ|となり|になり)",
     "「〜が可能です」", "「〜できます」にする"),

    ("motte-iru", "translationese", "warn",
     r"を(?:持って|もって)(?:い|お)|を有(?:して|し|する)",
     "have の直訳", "「〜があります」「〜を備えています」"),

    ("one-of-the", "translationese", "warn",
     r"の(?:うちの)?(?:一|１|ひと)つ(?:です|である|だ|に|で)",
     "one of the の直訳", "「〜の一つです」に縮めるか、丸ごと削って断定する"),

    ("juuyou-desu", "translationese", "info",
     r"することが(?:重要|大切|必要)(?:です|である|だ)",
     "it is important to の直訳", "「〜してください」「〜する必要があります」"),

    ("sonzai", "translationese", "warn",
     r"が存在(?:する|します|し、|して)",
     "there is の直訳", "「〜があります」"),

    ("teikyou", "translationese", "info",
     r"を提供(?:する|します|し、|して)",
     "provide の直訳になりがち", "具体的な動詞にできないか確認する"),

    ("moshi", "translationese", "info",
     r"もし[^。]{0,25}(?:場合|なら|たら|れば|ければ)",
     "「もし」と条件形の重複", "どちらか一方で足りる"),

    ("plural-tachi", "translationese", "warn",
     r"(?:ユーザー|ユーザ|データ|ファイル|情報|企業|システム|サーバー|サーバ|項目|要素|製品|機能|課題|問題|要件)たち",
     "英語の複数形の直訳", "「〜たち」を外す。数が重要なら具体的な数を書く"),

    ("inanimate-subject", "translationese", "info",
     r"(?:本記事|この記事|本稿|本書|本ツール|このツール|本サービス|このデータ|このグラフ)(?:は|が)[^。]{0,30}(?:教え|示し|可能にし|提供し|help)",
     "無生物主語＋他動詞", "「〜では〜を説明します」「〜から〜がわかります」に直す"),

    ("no-chain", "translationese", "warn",
     r"(?:[一-龠ァ-ヶーぁ-ん]{1,10}の){3}",
     "助詞「の」が3連続。係り受けが読めない", "語順を変えるか、動詞に開く"),

    # ---- 層3: AI文体 ----
    ("ai-ikaga", "ai", "error",
     r"いかがでし(?:た|ょう)",
     "SEO記事・AI文体の定型", "丸ごと削る"),

    ("ai-matome", "ai", "info",
     r"^(?:まとめると|総括すると|結論から(?:言う|申し上げる)と|要するに)",
     "水増しの前置き", "本当に結論を先に書くなら前置きは不要"),

    ("ai-hedge", "ai", "warn",
     r"と言えるでしょう|ではないでしょうか|と言っても過言では|と考えられます|"
     r"傾向があ(?:る|り)ます|一般的には[^。]{0,20}とされ",
     "断定回避の癖。根拠があるならぼかさない",
     "根拠があれば断定する。本当に不確かなら根拠のなさを明示する"),

    ("ai-zehi", "ai", "warn",
     r"ぜひ(?:参考|お試し|ご覧|チェック)|してみてください(?:ね)?。",
     "AI・記事の定型の締め", "丸ごと削る"),

    ("ai-point", "ai", "info",
     r"重要な(?:ポイント|点)(?:は|です|として)|押さえておきたい",
     "内容の薄い強調", "重要なら位置と具体性で示す"),

    ("ai-mite-ikou", "ai", "info",
     r"見ていき(?:ま|ましょう)|解説していきます|説明していきます",
     "冗長な宣言", "本題に入る"),

    ("ai-emotion", "ai", "info",
     r"素晴らし|大変興味深|驚くべき|嬉しいことに|残念ながら",
     "感情の演出", "事実と数字で示す"),

    ("ai-buzzword", "ai", "info",
     r"シームレス|包括的|多角的|抜本的|本質的に|に他ならない|密接に関(?:係|連)",
     "内容の薄い語", "具体的に何を指すか書けるなら書く。書けないなら文ごと不要"),

    ("ai-empty-verb", "ai", "info",
     r"(?:を|の)(?:活用|最適化|効率化|推進|実現|構築)(?:する|し|します|を図)",
     "空語になりやすい動詞", "何をどうするのか具体的に書く"),

    ("excl-mark", "ai", "info",
     r"[！!]",
     "感嘆符。実務文書・応募書類では原則使わない", "削る"),

    # ---- 層4: 表記 ----
    ("kana-kudasai", "notation", "error",
     r"(?:て|で)下さい",
     "補助動詞の「下さい」", "「〜てください」とひらがなで書く"),

    ("kana-koto", "notation", "warn",
     r"[うくぐすつぬぶむるいたなの]事(?:が|を|は|に|で|も|の|、|。)",
     "形式名詞の「事」", "「こと」とひらがなで書く"),

    ("kana-dekiru", "notation", "warn",
     r"出来(?:る|ます|ない|た|なかっ|れ|ま[せし])",
     "「出来る」", "「できる」とひらがなで書く"),

    ("kana-tame", "notation", "warn",
     r"(?:の|る|た|い|な)為(?:に|の|、|。|で)",
     "形式名詞の「為」", "「ため」とひらがなで書く"),

    ("kana-you", "notation", "warn",
     r"(?:の|る|た|な)様(?:な|に|で|だ|です)",
     "形式名詞の「様」", "「よう」とひらがなで書く"),

    ("kana-toori", "notation", "info",
     r"(?:の|る|た)通り",
     "形式名詞の「通り」", "「とおり」とひらがなで書く"),

    ("kana-tokoro", "notation", "info",
     r"(?:する|した|ある|ない|いる)所(?:が|を|は|に|で|、)",
     "形式名詞の「所」", "「ところ」とひらがなで書く"),

    ("kana-hou", "notation", "info",
     r"(?:の|る|た)方が(?:いい|良い|よい|早い|多い)",
     "形式名詞の「方」", "「ほう」とひらがなで書く"),

    ("kana-nai", "notation", "warn",
     r"(?:で|が|は|も|に|り|け)無い",
     "補助形容詞の「無い」", "「ない」とひらがなで書く"),

    ("kana-toiu", "notation", "warn",
     r"と言う(?:こと|点|もの|の|、|意味)",
     "形式の「と言う」", "実際の発話でなければ「という」"),

    ("kana-conj", "notation", "info",
     r"或いは|殆ど|予め|凡そ|尚、|但し|従って、|逆に、?|敢えて|勿論|沢山|全て(?:が|を|の)?|"
     r"出る杭|是非(?:とも)?、|毎に|於いて|依って",
     "接続詞・副詞の漢字表記", "公用文では原則ひらがな（あるいは／ほとんど／あらかじめ 等）"),

    ("zenkaku-alnum", "notation", "warn",
     r"[Ａ-Ｚａ-ｚ０-９]",
     "全角英数字", "半角にする"),

    ("ellipsis", "notation", "info",
     r"\.\.\.|。。。|・・・",
     "三点リーダーの表記", "「……」（2つ重ね）にする"),

    ("halfwidth-tilde", "notation", "info",
     r"(?<![\w/:])~(?![\w/])",
     "半角チルダ", "全角の「〜」にする"),

    ("halfwidth-kana", "notation", "warn",
     r"[｡-ﾟ]",
     "半角カタカナ", "全角にする"),

    ("space-before-punct", "notation", "info",
     r"[ 　]+[、。]",
     "句読点の前の空白", "削る"),
]

COMPILED = [
    (rid, cat, sev, re.compile(pat), msg, sug)
    for rid, cat, sev, pat, msg, sug in RULES
]

FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`]*`")
URL = re.compile(r"https?://\S+")
MD_NONBODY = re.compile(r"^\s*(#{1,6}\s|[-*+]\s|\d+\.\s|>|\||!\[|\[!)")

POLITE_END = re.compile(r"(?:です|ます|ました|ません|でした|ください|ましょう|でしょう|ですね)$")
PLAIN_END = re.compile(r"(?:である|だった|ではない|だ|した|する|いる|ある|ない|れる|られる|なる|た|う|い)$")


def mask(line):
    """コード・URL を同じ長さの空白に置き換える（列番号を保つため）。"""
    def blank(m):
        return " " * (m.end() - m.start())
    return URL.sub(blank, INLINE_CODE.sub(blank, line))


def visual_len(s):
    """全角を2、半角を1として数えた長さではなく、文字数を返す。

    日本語の一文の長さは文字数で数えるのが慣例なので、そのまま len を使う。
    """
    return len(s)


def split_sentences(text):
    """。！？ で文を分割する。位置（開始オフセット）付きで返す。"""
    out = []
    start = 0
    for m in re.finditer(r"[。！？!?]+", text):
        out.append((start, text[start:m.end()]))
        start = m.end()
    if text[start:].strip():
        out.append((start, text[start:]))
    return out


def sentence_style(sent):
    """敬体 / 常体 / 不明 を返す。"""
    body = sent.rstrip("。！？!?　 ")
    if not body:
        return None
    if POLITE_END.search(body):
        return "polite"
    if PLAIN_END.search(body):
        return "plain"
    return None


def check_file(path, text, opts):
    findings = []
    lines = text.split("\n")
    in_fence = False
    body_lines = []          # (lineno, masked_body_text)

    for i, raw in enumerate(lines, 1):
        if FENCE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        masked = mask(raw)

        for rid, cat, sev, rx, msg, sug in COMPILED:
            for m in rx.finditer(masked):
                if not m.group(0).strip():
                    continue
                findings.append({
                    "path": path, "line": i, "col": m.start() + 1,
                    "id": rid, "category": cat, "severity": sev,
                    "text": m.group(0), "message": msg, "suggestion": sug,
                })

        if not MD_NONBODY.match(raw) and raw.strip():
            body_lines.append((i, masked))

    # ---- 構造チェック（本文行のみ） ----
    endings = []
    styles = {"polite": 0, "plain": 0}
    style_lines = {"polite": [], "plain": []}

    for lineno, body in body_lines:
        for _, sent in split_sentences(body):
            s = sent.strip()
            if not s:
                continue
            n = visual_len(s.rstrip("。！？!?"))
            if n > 100:
                findings.append({
                    "path": path, "line": lineno, "col": 1,
                    "id": "long-sentence", "category": "structure", "severity": "warn",
                    "text": s[:20] + "…", "message": f"一文が{n}字。原則として分割する",
                    "suggestion": "接続助詞の切れ目で2文に割る",
                })
            elif n > 60:
                findings.append({
                    "path": path, "line": lineno, "col": 1,
                    "id": "long-sentence", "category": "structure", "severity": "info",
                    "text": s[:20] + "…", "message": f"一文が{n}字。分割を検討",
                    "suggestion": "読点3つ以上なら分割の候補",
                })
            commas = s.count("、")
            if commas >= 4:
                findings.append({
                    "path": path, "line": lineno, "col": 1,
                    "id": "many-commas", "category": "structure", "severity": "info",
                    "text": s[:20] + "…", "message": f"読点が{commas}個。係り受けが追いにくい",
                    "suggestion": "文を分割する",
                })

            st = sentence_style(s)
            if st:
                styles[st] += 1
                style_lines[st].append(lineno)

            tail = s.rstrip("。！？!? ")[-4:]
            endings.append((lineno, tail))

    # 文末の3連続
    for j in range(2, len(endings)):
        a, b, c = endings[j - 2][1], endings[j - 1][1], endings[j][1]
        if a and a == b == c:
            findings.append({
                "path": path, "line": endings[j][0], "col": 1,
                "id": "repeated-ending", "category": "structure", "severity": "info",
                "text": c, "message": f"同じ文末「{c}」が3文連続",
                "suggestion": "語尾を変えるか、文を統合する",
            })

    # 敬体・常体の混在
    if styles["polite"] and styles["plain"]:
        minor = "plain" if styles["plain"] <= styles["polite"] else "polite"
        label = {"polite": "敬体（ですます）", "plain": "常体（である）"}
        findings.append({
            "path": path, "line": style_lines[minor][0], "col": 1,
            "id": "style-mix", "category": "structure", "severity": "warn",
            "text": "",
            "message": (f"敬体{styles['polite']}文 / 常体{styles['plain']}文が混在。"
                        f"少数派は{label[minor]}（初出 {path}:{style_lines[minor][0]}）"),
            "suggestion": "どちらかに統一する。見出し・箇条書きの体言止めは対象外",
        })

    # 読点・句点の混在（ファイル単位）
    stripped = "\n".join(
        l for l in lines if not FENCE.match(l)
    )
    if "、" in stripped and "，" in stripped:
        findings.append({
            "path": path, "line": 1, "col": 1,
            "id": "comma-mix", "category": "notation", "severity": "error",
            "text": "", "message": "読点「、」と「，」が混在",
            "suggestion": "横書きは「、」に統一する",
        })
    if "。" in stripped and "．" in stripped:
        findings.append({
            "path": path, "line": 1, "col": 1,
            "id": "period-mix", "category": "notation", "severity": "error",
            "text": "", "message": "句点「。」と「．」が混在",
            "suggestion": "「。」に統一する",
        })

    # カタカナ長音の混在
    for short, long_ in [("サーバ", "サーバー"), ("ユーザ", "ユーザー"),
                         ("コンピュータ", "コンピューター"), ("プリンタ", "プリンター"),
                         ("ブラウザ", "ブラウザー"), ("フォルダ", "フォルダー")]:
        n_long = stripped.count(long_)
        n_short = stripped.count(short) - n_long
        if n_long and n_short > 0:
            findings.append({
                "path": path, "line": 1, "col": 1,
                "id": "choon-mix", "category": "notation", "severity": "warn",
                "text": short, "message": f"「{short}」と「{long_}」が混在（{n_short}件 / {n_long}件）",
                "suggestion": "どちらかに統一する",
            })

    return findings


def main():
    ap = argparse.ArgumentParser(description="不自然な日本語の機械検出")
    ap.add_argument("files", nargs="+", help="対象ファイル。- で標準入力")
    ap.add_argument("--json", action="store_true", help="JSON で出力")
    ap.add_argument("--only", default="", help=f"カテゴリを絞る（カンマ区切り）: {','.join(CATEGORIES)}")
    ap.add_argument("--min-severity", default="info", choices=list(SEVERITIES),
                    help="この深刻度以上だけ出す（既定: info）")
    opts = ap.parse_args()

    only = {c.strip() for c in opts.only.split(",") if c.strip()}
    if only - set(CATEGORIES):
        ap.error(f"未知のカテゴリ: {', '.join(sorted(only - set(CATEGORIES)))}")
    floor = SEVERITIES[opts.min_severity]

    all_findings = []
    for path in opts.files:
        if path == "-":
            text, name = sys.stdin.read(), "<stdin>"
        else:
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except OSError as e:
                print(f"読み込めません: {path}: {e}", file=sys.stderr)
                continue
            name = path
        all_findings.extend(check_file(name, text, opts))

    all_findings = [
        f for f in all_findings
        if SEVERITIES[f["severity"]] >= floor and (not only or f["category"] in only)
    ]
    all_findings.sort(key=lambda f: (f["path"], f["line"], f["col"],
                                     -SEVERITIES[f["severity"]], f["id"]))

    if opts.json:
        json.dump(all_findings, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        for f in all_findings:
            hit = f'「{f["text"]}」' if f["text"] else ""
            print(f'{f["path"]}:{f["line"]}:{f["col"]}: {f["severity"]} '
                  f'[{f["category"]}/{f["id"]}] {hit}{f["message"]}')
            if f["suggestion"]:
                print(f'    → {f["suggestion"]}')
        counts = {}
        for f in all_findings:
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1
        summary = " / ".join(f"{k} {counts[k]}" for k in ("error", "warn", "info") if k in counts)
        print(f"\n計 {len(all_findings)} 件" + (f"（{summary}）" if summary else ""), file=sys.stderr)
        print("※ これは候補。誤検出を含むので原文を読んで採否を決めること。", file=sys.stderr)

    return 1 if any(f["severity"] == "error" for f in all_findings) else 0


if __name__ == "__main__":
    sys.exit(main())
