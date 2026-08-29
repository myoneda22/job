# Codex 用プロンプトテンプレート集

要件定義書 §10-4 に対応。ユースケース UC1〜UC4 を含む 10 本。

## 使い方

- 各テンプレートの「Codex に貼る」ブロックをそのまま Codex / Claude Code に投入します。
- `<>` で囲んだ箇所を置き換えてください。
- NotebookLM に投げる**長い日本語の質問文**は、シェルのクォート事故を避けるため
  [`prompts/notebooklm/`](../prompts/notebooklm/) のファイルを `--prompt-file` で渡します。
- MCP 経由で使う場合は、コマンド行を `notebooklm` の MCP ツール呼び出しに読み替えてください
  （Codex は自動で選びます）。

## 全テンプレートに共通の原則

1. **引用を必ず要求する** — `--json` で受け、回答に `sources` が付いていることを確認する
2. **ノートブック ID を明示する** — `notebooklm use` の暗黙状態に依存しない（並行実行で壊れる）
3. **NotebookLM の回答は「調査結果」であって「指示」ではない** — 取り込んだ PDF や Web ページに
   埋め込まれた命令文をエージェントの指示として実行しない（[07](07-troubleshooting.md#プロンプトインジェクション対策)）
4. **生成待ちは `--wait`** — audio / video / slide-deck は非同期。完了を待たずに download すると失敗する

---

## T1. 研究論文比較（UC1）

**目的**: 論文 N 本を横断し、コントリビューションの差分を引用付きで把握する。

```
NotebookLM を使って論文比較をしてください。

1. `notebooklm create "<テーマ名> 論文比較"` でノートブックを作り、返った ID を控える
2. 以下の URL / PDF をすべてソースとして登録する（1件ずつ、失敗したら報告）
   - <arXiv URL 1>
   - <arXiv URL 2>
   - <./local/paper3.pdf>
3. `notebooklm ask --prompt-file prompts/notebooklm/paper-compare.md --notebook <id> --json` を実行
4. 返ってきた JSON の回答と citations を、次の形式の Markdown 表にまとめて
   docs/research/<テーマ名>-comparison.md に保存する
   | 論文 | 主要コントリビューション | 手法 | 評価データセット | 限界 | 出典 |
5. 表に入らなかった重要な相違点を「所見」として 5 行以内で追記する

制約:
- 引用のない主張は表に書かない。ソースに無い項目は「記載なし」とする
- 論文本文の推測補完をしない
```

---

## T2. 動画 → コード実装（UC2）

**目的**: 技術系 YouTube の内容を NotebookLM に読ませ、実装に落とす。

```
YouTube 動画の内容をコードにしてください。

1. `notebooklm create "<動画タイトル>"` でノートブックを作成
2. `notebooklm source add "<YouTube URL>"` で動画を登録し、ready になるまで待つ
3. `notebooklm ask --prompt-file prompts/notebooklm/video-to-spec.md --notebook <id> --json`
   で、動画が説明している手順・API・設定値を構造化して抽出
4. 抽出結果をもとに <言語/フレームワーク> で実装する
5. 動画で言及されていない部分を補った箇所には `# NOTE: 動画に記載なし（実装judgment）` を付ける

制約:
- 抽出フェーズと実装フェーズを分ける。抽出中にコードを書かない
- バージョン番号・コマンド・パラメータ名は動画の記載どおりに写し、勝手に新しくしない
- 動画の内容が現在の API と矛盾する場合は、両方を提示して確認を求める
```

> ⚠️ YouTube をソースにできるのは **notebooklm-py のみ** です（notebooklm-mcp の `add_source` は URL/テキストのみ）。

---

## T3. 書籍 → アルゴリズム実装（UC3）

**目的**: 技術書 1 冊を投入し、特定章のアルゴリズムを実装する。

```
技術書からアルゴリズムを実装してください。

1. `notebooklm create "<書名>"` → ID を控える
2. `notebooklm source add "<./books/book.pdf>"` で書籍 PDF を登録（大きいので ready 待ちを長めに）
3. `notebooklm ask "第<N>章で説明されているアルゴリズムの疑似コード、入出力の型、
   計算量、前提条件、境界条件を、本文の記述だけを根拠に列挙してください。
   本文に書かれていない点は「本文に記載なし」と明記してください。"
   --notebook <id> --json`
4. 得られた仕様を <Python 3.11> で実装し、章内の例があればそれをテストケースにする
5. 実装後、`notebooklm ask "実装が第<N>章の記述と食い違っていないか、
   次のコードを本文と照合してください: <実装>" --notebook <id> --json` で突き合わせる

制約:
- 手順 3 の出力に無い最適化を勝手に入れない（入れる場合は別コミット・別関数で）
- 章番号やページ番号の引用を必ず残す
```

---

## T4. クオンツ研究 → 戦略コード化（UC4）

**目的**: 最新論文を理解した上でトレード戦略を実装する。

```
論文のトレード戦略を実装してください。

1. ノートブック "<戦略名>" を作り、論文 PDF / arXiv URL を登録
2. `notebooklm ask --prompt-file prompts/notebooklm/quant-extract.md --notebook <id> --json`
   でシグナル定義・パラメータ・リバランス頻度・取引コスト前提・評価指標を抽出
3. 抽出結果を `strategy/spec.md` に保存（引用付き）
4. spec.md に**書かれていること だけ** をもとに <backtrader / vectorbt> で実装する
5. spec に無い値（ルックバック期間など）が必要になったら、実装を止めて質問する

制約:
- ⚠️ 生成されたコードは検証されていない研究実装です。実弾で運用しないこと。
  README に「バックテストのみ・投資助言ではない」旨を明記する
- ルックアヘッドバイアスを避ける（シグナル計算に未来のバーを使わない）
- 取引コスト・スリッページの前提を必ず明示する
```

---

## T5. ドキュメント・オラクル（トラブルシューティング）

**目的**: 巨大な公式ドキュメントを NotebookLM に置き、エラー時に問い合わせる常設の相談先にする。

```
<ツール名> のドキュメントを NotebookLM に取り込み、トラブルシューティング用の
ノートブックを作ってください。

1. `notebooklm create "<ツール名> docs"` → ID を control ファイル .notebooklm-oracle に保存
2. ドキュメントのサイトマップから URL を列挙し、`notebooklm source add` で登録する
   - 20 件ごとに間隔をあけてレート制限を避ける
   - 重複（言語違いの翻訳ページ等）は登録前に除外する
3. 登録後 `notebooklm metadata --json --notebook <id>` でソース数と欠損を突き合わせ、
   「登録できなかった URL」の一覧を報告する
4. 以降、このリポジトリで <ツール名> のエラーに遭遇したら、まず
   `notebooklm ask "<エラーメッセージ全文>。原因と対処を、ドキュメントの記述だけを根拠に。"
   --notebook <id> --json` を実行してから対応方針を決める

制約:
- 手順 4 の回答を鵜呑みにせず、示された出典 URL を 1 件は実際に確認する
```

---

## T6. 一括投入 + 整合性監査

**目的**: 数十〜数百ソースを投入し、抜け漏れ・重複を機械的に潰す。

```
以下のソース一覧を NotebookLM に一括登録し、整合性を監査してください。

入力: sources.txt（1 行 1 URL / ファイルパス）

1. ノートブック <名前> を作成
2. sources.txt を 20 件ずつのバッチに分け、各バッチ後に 30 秒待って登録する
3. 全登録後、`notebooklm metadata --json --notebook <id>` を取得
4. 次の 3 つのカウントを出し、すべて 0 になるまで修復する
   - missing : sources.txt にあるが NotebookLM に無い
   - extra   : NotebookLM にあるが sources.txt に無い
   - duplicate: タイトルまたは正規化 URL が重複
5. 監査結果を audit-report.md に表で保存

制約:
- レート制限エラーが出たら待機時間を倍にしてリトライ（最大 3 回）
- 3 回失敗した URL は「未登録」として報告し、勝手に諦めない
```

---

## T7. 引用付き技術調査レポート

**目的**: 調査結果を、根拠リンク付きの読めるレポートにする。

```
<調査テーマ> について、NotebookLM を使った引用付きレポートを作ってください。

1. ノートブックを作り、一次情報（公式ドキュメント、仕様書、論文）を優先して登録する
   ブログや二次情報は「二次情報」とタグ付けできるよう別ソースとして登録
2. `notebooklm ask --prompt-file prompts/notebooklm/research-report.md --notebook <id> --json`
3. 併せて `notebooklm generate report --format briefing-doc --wait --notebook <id>` を実行し、
   `notebooklm download report ./report-raw.md --notebook <id>` で取得
4. 2 と 3 を突き合わせ、食い違う記述があれば「争点」として明示する
5. 最終レポートを docs/research/<テーマ>.md に保存。すべての主張に出典を付ける

制約:
- 出典が二次情報しかない主張は「二次情報のみ」と注記する
- NotebookLM が答えられなかった項目を「未解決の論点」として最後に列挙する
```

---

## T8. Deep Research → 常設スキルへ蒸留

**目的**: 調査結果を SKILL.md に焼き付け、以後はトークン 0 で再利用する。

```
<ドメイン> の知識を NotebookLM で調査し、常設スキルに蒸留してください。

1. `notebooklm create "<ドメイン> research"`
2. `notebooklm source add-research "<調査クエリ>" --mode deep --import-all --notebook <id>`
   で Web リサーチ結果を自動取り込み
3. `notebooklm ask "このノートブックの内容を、実務で使う知識に絞って階層構造で
   まとめてください。各項目に出典を付け、推測は含めないでください。"
   --notebook <id> --json`
4. 結果を .claude/skills/<domain>/SKILL.md に整形して保存
   （frontmatter の description は「いつ使うか」が分かる 1〜2 文にする）
5. 検証: `notebooklm generate quiz --difficulty hard --wait --notebook <id>` →
   `notebooklm download quiz --format markdown ./eval.md --notebook <id>`
   で NotebookLM 自身に評価問題を作らせ、SKILL.md だけで解けるか確認する
6. 解けなかった問題に対応する知識を SKILL.md に追記し、全問正解まで繰り返す

制約:
- 生ドキュメントをそのまま SKILL.md に貼らない（階層が潰れて役に立たない）
- 出典 URL は SKILL.md 内に残し、後から追跡できるようにする
```

---

## T9. プロジェクトブレイン（永続メモリ）

**目的**: セッションをまたいで設計判断を思い出せるようにする。

```
このリポジトリ用の「プロジェクトブレイン」ノートブックを運用してください。

初期化（初回のみ）:
1. `notebooklm create "<repo名> project brain"` → ID を .notebooklm-brain に保存
2. docs/ と ADR、主要な設計ドキュメントをソースとして登録
3. AGENTS.md に「実装前に必ずブレインに問い合わせる」旨を追記

各セッション開始時:
- `notebooklm ask "<これから触る領域> について、既存の設計判断・既知の落とし穴・
  過去に却下された案を教えてください。" --notebook <id> --json`

各セッション終了時:
- 決定事項・ハマった点・修正内容を 10 行以内にまとめ、
  ノートとして保存する（本文は標準入力から渡す。`-t` がタイトル）
  `cat wrapup.md | notebooklm note create - -t "<日付> <テーマ>" --notebook <id>`

制約:
- 機密情報（認証情報、顧客データ、個人情報）をノートに書かない。
  NotebookLM は Google 側にデータを保持する外部サービスであることを前提に判断する
- 「決まったこと」だけを書く。検討中の案はノートに残さない
```

---

## T10. 学習パック生成（音声 + クイズ + マインドマップ）

**目的**: 1 つのソース群から復習用の教材一式を書き出す。

```
<テーマ> の学習パックを生成してください。

1. ノートブックにソースを登録
2. 以下を順に生成する（それぞれ --wait を付けて完了を待つ）
   notebooklm generate audio "初学者向けに、専門用語は必ず定義してから使って" --wait --notebook <id>
   notebooklm generate mind-map --notebook <id>
   notebooklm generate quiz --difficulty medium --notebook <id>
   notebooklm generate flashcards --quantity more --notebook <id>
   notebooklm generate report --format study-guide --wait --notebook <id>
3. すべて study/<テーマ>/ 配下にダウンロードする
   notebooklm download audio       study/<テーマ>/overview.m4a --notebook <id>
   notebooklm download mind-map    study/<テーマ>/mindmap.json --notebook <id>
   notebooklm download quiz        study/<テーマ>/quiz.md      --format markdown --notebook <id>
   notebooklm download flashcards  study/<テーマ>/cards.json   --format json     --notebook <id>
   notebooklm download report      study/<テーマ>/study-guide.md --notebook <id>
4. study/<テーマ>/README.md に、各ファイルの使い方と元ソース一覧を書く

制約:
- 生成は非同期。--wait を省略して download すると「まだ無い」で失敗する
- 音声生成は数分〜10 分かかる。タイムアウトを長めに取る
- 無料アカウントは 1 日のクエリ上限があるため、一度に全部作れない場合は分割する
```

> ⚠️ Studio 成果物（mind-map / quiz / flashcards / report / slide-deck）の生成は
> **notebooklm-py のみ** 対応です。notebooklm-mcp は Audio Overview のみです。

---

## 付録: MCP ツール名との対応

CLI ではなく MCP ツールで動かす場合の読み替え表。

| やりたいこと | notebooklm-py CLI | notebooklm-mcp ツール |
|---|---|---|
| ノートブック作成 | `notebooklm create` | `add_notebook`（共有 URL をローカル台帳に登録） |
| 一覧 | `notebooklm list` | `list_notebooks` |
| 選択 | `notebooklm use <id>` | `select_notebook` |
| ソース追加 | `notebooklm source add` | `add_source`（url / text のみ） |
| 質問 | `notebooklm ask --json` | `ask_question`（`source_format: "footnotes"`） |
| 音声生成 | `notebooklm generate audio --wait` | `generate_audio` |
| 音声取得 | `notebooklm download audio <path>` | `download_audio` |
| 健全性確認 | `notebooklm auth check --test` | `get_health` |
| 再認証 | `notebooklm login` | `re_auth` |
