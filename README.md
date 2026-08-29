# job — Gemini 連携

就活（27卒/28卒・帰国子女/バイリンガル向け）ワークフロー用の Gemini 連携。
4つの入り口があり、いずれも同じクライアントを共有します。

| 機能 | モジュール | 用途 |
| --- | --- | --- |
| 汎用 Gemini クライアント | `gemini_link.gemini` | 生成・ストリーミング・function calling・検索グラウンディング・JSON スキーマ出力・リトライ |
| 就活リサーチ | `gemini_link.shukatsu` | 企業の新卒採用を調査し、Airtable の「備考」欄用テキストに整形（検索経由／URL指定の2通り） |
| Claude ↔ Gemini 相互チェック | `gemini_link.compare` | 同じ質問を両モデルに投げ、食い違いを検出 |
| MCP サーバー | `gemini_link.mcp_server` | Claude Code から Gemini をツールとして呼ぶ |

コアライブラリの依存パッケージは **ゼロ**（標準ライブラリの `urllib` のみ）です。
MCP サーバーだけが `mcp` を必要とします。

## セットアップ

```bash
cp .env.example .env      # .env は .gitignore 済み
$EDITOR .env              # GEMINI_API_KEY を記入
pip install -e '.[mcp,dev]'
```

APIキーは環境変数または `.env` からのみ読み込みます。コードには一切埋め込みません。
キーは `x-goog-api-key` ヘッダで送られるため URL やログに残らず、
`Settings.describe()` や MCP の `gemini_status` では常にマスクされます。

キーの発行・再発行: <https://aistudio.google.com/apikey>

## CLI

```bash
python -m gemini_link.cli status                      # 設定確認（キーはマスク）
python -m gemini_link.cli models                      # このキーで見えるモデル一覧
python -m gemini_link.cli ask "質問" [--stream]        # 単発生成
python -m gemini_link.cli search "28卒 締切"           # 検索グラウンディング付き回答（出典URL付き）
python -m gemini_link.cli read-urls "何が書いてある？" --url https://...  # 指定ページだけを読ませる
python -m gemini_link.cli compare "質問" [--search]    # Claude と突き合わせ
python -m gemini_link.cli company "サイバーエージェント" --grad-year 2028
python -m gemini_link.cli company "A社" --url https://a.co.jp/recruit/   # 検索せずページを読む
python -m gemini_link.cli batch companies.txt --json  # 複数社を一括
```

`compare` は不一致を検出したとき終了コード 1 を返すので、シェルスクリプトから
「食い違ったら止める」使い方ができます。

## 就活リサーチ

`company` は意図的に **2回** API を呼びます。Google 検索グラウンディングと
JSON スキーマ出力はサーバー側で排他のため、1回目で出典付きの調査結果を取得し、
2回目でそれを固定スキーマに整形します。2回目は1回目が取得した内容しか見ないので、
裏取りのない推測が構造化データに混入しません。

出力される備考欄テキストの例:

```
【28卒採用｜2026-08-29時点・Gemini調査】
・採用状況: 2028年卒(28卒)の本選考エントリーを実施
・エントリー時期: 2026年3月1日から受付開始、締切は2026年5月31日
・選考フロー: ES→Webテスト→面接3回
・英語/帰国子女: TOEIC730以上が目安で帰国子女枠あり
・情報の確度: high
・出典: https://...
```

「不明」の項目は行ごと省かれます。全項目が不明なら確度は `low` に落とされ、
モデルの自己申告より優先されます（要手動確認と明記）。

### 検索が使えないときの経路（`--url`）

検索グラウンディングのクォータは別枠で、無料枠では先に尽きます（下記「モデル選択」参照）。
その場合は `--url` で読ませたいページを直接指定できます。`url_context` ツールを使う経路で、
**こちらは検索クォータの影響を受けません**（実測で 429 にならないことを確認済み）。

```bash
python -m gemini_link.cli company "A社" \
  --url https://a.co.jp/recruit/ --url https://a.co.jp/news/2026/
```

**この経路には必ず踏むべき安全確認があります。** ページ取得に失敗しても Gemini は
エラーを返さず、学習データの記憶から流暢な回答を作ります。グラウンディングされた回答と
見分けがつきません（実測で確認: 取得失敗した `example.com` の内容を、自信ありげに要約しました）。

そのため、取得ステータス（`urlRetrievalStatus`）が全URLで成功でない限り、
`research_company_from_urls()` は結果を返さず `RetrievalError` を投げます。
`GeminiResponse.require_retrieval()` が同じ判定を行い、未知のステータス文字列は
成功と見なしません（fail-closed）。CLI は警告を stderr に出して終了コード 1 を返します。

裏を返すと、明示的に「取得できなければ記憶で補うな」と指示すれば正直に申告します
（実測で確認済み）。各プロンプトにその指示を入れてありますが、それは補助であって、
信頼の根拠はあくまで取得ステータスの検証です。

このモジュールは Airtable への書き込みは行いません。整形済みテキストと JSON を返すだけなので、
書き込みは既存の Airtable MCP / スキル側の責務です。

```python
from gemini_link.shukatsu import research_company

r = research_company("サイバーエージェント", grad_year=2028)
print(r.to_remarks(max_chars=800))   # 備考欄へ
print(r.sources)                      # 出典URL
```

## Claude ↔ Gemini 相互チェック

両モデルに同じ質問を並列で投げ、判定側には **どちらの回答がどのモデルのものか伏せて**
（「回答A」「回答B」として）突き合わせさせます。ベンダーへの肩入れを防ぐためです。

判定は `agree` / `partial` / `conflict` の3値で、不一致点を最初に表示します。
`ANTHROPIC_API_KEY` が未設定でも失敗せず、Gemini 単独の結果を返したうえで
「相互検証できていません」と明示します。

## MCP サーバー（Claude Code から使う）

```bash
cp .mcp.json.example .mcp.json
```

公開ツール:

- `gemini_generate` — 素の生成
- `gemini_search` — Google 検索グラウンディング付き回答（出典URL付き）
- `gemini_second_opinion` — Claude の回答案を Gemini が独立にレビュー
- `gemini_research_company` — 就活リサーチ（検索経由。備考テキスト＋構造化JSON）
- `gemini_read_urls` — 指定ページだけを読ませて回答（取得失敗時は警告を返す）
- `gemini_research_company_from_urls` — 就活リサーチ（URL指定。検索クォータ不要）
- `gemini_list_models` / `gemini_status`

各ツールはブロッキング HTTP をワーカースレッドに退避するので、
Gemini の応答待ちで MCP のイベントループが止まりません。

## モデル選択

既定は `gemini-3.7-flash`。`GEMINI_MODEL` か `--model` で上書きできます。

実測で判明した注意点が2つあります。

1. **`ListModels` に出ていても使えるとは限りません。** `gemini-2.5-flash` は一覧に
   出ますが、新しく発行したキーで `generateContent` を呼ぶと 404
   （"no longer available to new users"）を返します。`models` コマンドの出力は
   候補であって保証ではありません。
2. **検索グラウンディングのクォータは通常の生成とは別枠です。** 無料枠ではこちらが
   先に尽き、素の生成は成功するのにグラウンディング付きだけ 429 になります。
   この場合エラーメッセージがその旨を明示します。
3. **`url_context` は検索クォータの影響を受けません。** 同じキーで、`google_search` が
   429 を返す状況でも `url_context` は 200 を返します。検索が使えないときの代替経路として
   `--url` を用意しているのはこのためです。ただし取得成功は別問題で、上記の
   「検索が使えないときの経路」の安全確認が必須です。

## Thinking の扱い

Gemini 3 系は `thinkingLevel`、2.5 系は数値の `thinkingBudget` を取り、
取り違えると 400 になります。クライアントがモデル名から自動で振り分けます
（`thinking_budget` を明示すればそちらが優先）。

thinking が出力予算を食い尽くして本文が空になる事故は起きがちなので、
その場合は「思考トークンに何トークン使ったか」と対処法（`max_output_tokens` を上げる／
`thinking_level='low'`）を含む例外を投げます。

## ネットワーク障害の扱い

読み取りタイムアウトや接続リセットは、生の socket 例外として素通しせず、
リトライ対象のステータス（504）に変換して通常のバックオフ経路に載せます。
`url_context` の呼び出しは実測で 50〜140 秒かかるため、これは例外ではなく通常の事象です。
既定のタイムアウトはそれに合わせて 180 秒にしてあります（`GEMINI_TIMEOUT` で変更可）。

## テスト

```bash
pytest
```

122件、すべてネットワーク不要です。`FakeTransport` が HTTP 層を差し替えるので、
リクエスト組み立て・リトライ・パースの実処理をキーなしで検証します。
MCP SDK が未導入の環境では MCP のテストのみスキップされます。

## 検証状況

実際の API に対して確認済み:

- `status` / `models` / `ask` / `ask --stream`
- JSON スキーマ出力（`company` の構造化ステップ）
- `url_context` が検索クォータの影響を受けないこと（`google_search` が 429 の状況で 200）
- **`url_context` でのページ取得成功**。`https://www.iana.org/help/example-domains` が
  `URL_RETRIEVAL_STATUS_SUCCESS` を返し、要約もページ内容と一致しました。
- **取得失敗時のガード**。同じ実行で `https://example.com/` は
  `URL_RETRIEVAL_STATUS_ERROR` となり、`grounded: false` として報告され、終了コード 1 に
  なりました（`example.com` は個別に Google のフェッチャーを弾いているようです）。
- 取得失敗時に、明示指示がなければ Gemini が記憶から回答してしまうこと。
  これが `require_retrieval()` の設計根拠です。
- タイムアウトがきれいなエラーになること。

**未検証**: 検索グラウンディングを使う経路（`search`、`company` の検索版、`gemini_search`、
`gemini_research_company`）。グラウンディング専用クォータが尽きており一貫して 429 になるためで、
コード側の問題ではありません（素の生成は同じモデル・同じキーで成功します）。
`--url` を使う経路はこの制約を受けないので、当面はそちらが実用的な代替になります。

## 無料枠の制限（実測）

無料枠は想像よりかなり狭く、開発中に両方とも使い切りました。

- 通常生成: `generate_content_free_tier_requests` が **20リクエスト**（モデル単位）。
  超えると 429 で、エラーに `retryDelay`（実測 約60秒）が付きます。クライアントはこれを
  尊重してバックオフします。
- 検索グラウンディング: 別枠で、こちらが先に尽きます。

実運用（653社の定期更新など）では課金の有効化が事実上必須です。
