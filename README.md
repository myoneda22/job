# job

## natural-japanese スキル

不自然な日本語（翻訳調、AI文体、冗長表現、表記ゆれ、文法の誤り）を検出して直すための Claude Code スキル。

```
.claude/skills/natural-japanese/
├── SKILL.md                    # ワークフローと最頻出15パターン
├── references/
│   ├── grammar.md              # 層1: 文法・敬語（ら抜き、二重敬語、主述のねじれ）
│   ├── translationese.md       # 層2: 翻訳調（直訳構造、代名詞過剰、無生物主語）
│   ├── ai-style.md             # 層3: AI/LLM文体（水増し、断定回避、空語）
│   ├── notation.md             # 層4: 表記（漢字ひらがな配分、句読点、英数字）
│   └── sources.md              # 出典と検証状況
└── scripts/
    ├── detect.py               # 機械検出（依存なし・Python 3のみ）
    ├── selftest.py             # ルール表の回帰テスト
    └── fixtures/               # テスト用の文例
```

### 使い方

Claude Code で「この文章を校正して」「翻訳調を直して」と頼めばスキルが起動する。検出器だけを単体で使うこともできる。

```bash
python3 .claude/skills/natural-japanese/scripts/detect.py draft.md
cat draft.md | python3 .claude/skills/natural-japanese/scripts/detect.py -
python3 .claude/skills/natural-japanese/scripts/detect.py draft.md --json
python3 .claude/skills/natural-japanese/scripts/detect.py draft.md --only notation --min-severity warn
```

`error` が1件でもあれば終了コード 1 を返すので、CI にも組み込める。

### 注意

検出器は機械的に判定できるパターンだけを出す。網羅もしないし誤検出もある。出力は候補であり、採否は原文を読んで決めること。主述のねじれ・論理の飛躍・段落構成は検出できない。

規範の出典と検証状況は `references/sources.md` に書いてある。一次資料（文化庁・文化審議会の告示および建議）の本文は、スキル作成時の実行環境からアクセスできなかったため未検証。細部の判断が問題になる場面では原典を確認すること。
