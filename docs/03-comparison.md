# notebooklm-py と notebooklm-mcp の比較 / 推奨根拠

要件定義書 §10-2 に対応。情報源は両プロジェクトの上流 README・docs（2026-08 時点）。
いずれも **非公式・MIT ライセンス** のコミュニティプロジェクトです。

## 結論（先に）

**notebooklm-py を primary に推奨します。** 要件定義書 6.1 は notebooklm-mcp を primary と
していますが、以下 2 点でそのままでは要件を満たせません。

1. **FR-003（ソース追加: URL / PDF / YouTube / テキスト / Google Drive）が未達。**
   notebooklm-mcp v2 の `add_source` は `type=url` と `type=text` のみで、
   ローカル PDF・YouTube・Google Drive を登録できません。
   要件の中核ユースケース UC2（動画→コード実装）・UC3（書籍丸ごと）が成立しません。
2. **FR-005（Mind Map / Study Guide / FAQ / Quiz 生成）が未達。**
   notebooklm-mcp が生成できる Studio 成果物は Audio Overview のみです。

notebooklm-py は上記をすべてカバーし、かつ MCP サーバーも同梱しているため、
「Codex から MCP で繋ぐ」という要件 FR-006 も同じ形で満たせます。

**ただし notebooklm-mcp を選ぶ理由もあります** — 後述の[使い分け](#使い分けの指針)を参照。

---

## 比較表

| 観点 | **notebooklm-py**（推奨） | **notebooklm-mcp** |
|---|---|---|
| 提供元 | teng-lin | PleasePrompto |
| 実装言語 / 要件 | Python 3.10–3.14 | TypeScript / Node.js 18+ |
| 配布 | PyPI `notebooklm-py` | npm `notebooklm-mcp` |
| **NotebookLM の叩き方** | 内部 RPC API を直接呼ぶ | 実 Chrome を Patchright で自動操作し DOM を読む |
| 接続形態 | CLI / Python API / MCP / REST | MCP のみ（stdio / Streamable-HTTP） |
| MCP ツール数 | 33（`[mcp]` extra） | 22 程度（`full`）／ `minimal` で 5 まで削減可 |
| **ソース追加 (FR-003)** | URL, YouTube, ローカルファイル（PDF/Word/EPUB/音声/動画/画像）, Google Drive, 貼り付けテキスト | **URL とテキストのみ** |
| **生成物 (FR-005)** | audio, video, slide-deck, infographic, quiz, flashcards, report(briefing-doc / study-guide / blog), data-table, mind-map | **Audio Overview のみ** |
| エクスポート形式 | M4A（音声）, MP4, PDF, PPTX, PNG, CSV, JSON, Markdown, HTML | 音声ファイル |
| 引用 | `ask --json` で構造化取得 | `source_format` = none / inline / footnotes / json（DOM 抽出） |
| 認証方式 | 対話ログイン / ブラウザ Cookie 取込 / **master-token** | `setup_auth`（可視 Chrome で 1 回ログイン）→ 永続プロファイル |
| 無人運用 | ◎ master-token が期限切れを自己修復 | △ 初回のみディスプレイ必須（`xvfb-run`）、以後は永続プロファイル頼み |
| 速度 | 速い（HTTP RPC） | 遅い（DOM 待ち + 既定でステルスタイピング 160–240 WPM） |
| 並行性 | プロファイル分離で複数エージェント並走 | `MAX_SESSIONS`（既定 10）ブラウザセッション |
| ステルス / フィンガープリント保護 | なし（API 直叩き） | ◎ Patchright による指紋維持 |
| Windows | cp932 文字化けは CLI 起動時に `PYTHONUTF8=1` 自動設定。App-Bound Encryption / `spawn UNKNOWN` の既知問題あり | WSL2+WSLg 対応（WSL1 不可）。Chrome 起動失敗時は `BROWSER_CHANNEL=chromium` |
| 主な壊れ方 | Google が内部 RPC を変えると壊れる | Google が UI/DOM を変えると壊れる |
| ライセンス | MIT | MIT |

---

## 判断根拠の詳細

### 1. 要件充足度が決定的な差

[01-requirements.md の FR 充足表](01-requirements.md#機能要件-fr-の充足状況) の通り、
FR-003（高）と FR-005（中）で差がつきます。とくに FR-003 は高優先度かつ
UC2 / UC3 の前提なので、ここが欠けると要件定義書のユースケースが成立しません。

### 2. 「トークン削減」への効き方が違う

NFR「Codex 単体比 70% 以上削減」は、**NotebookLM 側で読ませた分だけ効く** 数字です。
本キットで効かせられるのはむしろ **エージェント側の固定コスト** です。

| 接続方式 | 常時載るツール定義 | 備考 |
|---|---|---|
| notebooklm-py CLI（Skill / AGENTS.md） | **0** | Bash から直接叩く。最小 |
| notebooklm-mcp `minimal` プロファイル | 5 ツール | Q&A 中心ならこれで足りる |
| notebooklm-mcp `full`（既定） | 22 ツール | |
| notebooklm-py MCP | 33 ツール | 機能は最多だがツール定義も最多 |

**推奨:** 日常運用は 3-B（CLI 直叩き）、対話でノートブック操作を任せたいときだけ MCP、
という二段構えが最もトークン効率が良くなります。

### 3. 壊れたときの直り方

- notebooklm-py: 内部 RPC の仕様変更に追随する必要があり、上流のリリースを待つことになる。
  ただし `--json` の出力契約が安定しているため、自分の側のスクリプトは壊れにくい。
- notebooklm-mcp: UI 変更時は `src/notebooklm/selectors.ts` の修正で直ることが多く、
  ローカルで応急処置しやすい。一方で「引用パネルが空」など**静かに劣化する**failure mode がある。

どちらも非公式である以上、**業務クリティカルな経路に単独で置かない**のが前提です。

### 4. セキュリティ面

- notebooklm-mcp は要件 §5 が挙げる「ブラウザフィンガープリント保護」に唯一対応します
  （Patchright によるステルス + 永続指紋）。Google の自動化検知を避けたい場合の利点です。
- notebooklm-py は内部 API を直接叩くため、そもそもブラウザ指紋の問題が発生しません。
  代わりに、取得した Cookie / master-token の保管が最重要になります。
- 両者とも認証情報は平文でローカルに保存されます（暗号化ストアはありません）。

---

## 使い分けの指針

| 状況 | 選択 |
|---|---|
| 要件定義書どおり全 FR を満たしたい | **notebooklm-py** |
| PDF / YouTube / Drive をソースに入れる | **notebooklm-py**（mcp では不可） |
| Mind Map / Quiz / Study Guide / スライドが要る | **notebooklm-py** |
| CI・サーバーで無人実行したい | **notebooklm-py**（master-token） |
| 処理速度・バッチ量が重要 | **notebooklm-py**（RPC 直叩き） |
| Google の自動化検知を避けたい / 指紋保護が要件 | **notebooklm-mcp** |
| 内部 RPC が変わって py が動かない期間の回避策が欲しい | **notebooklm-mcp**（壊れ方が独立している） |
| Node しか入れられない環境 | **notebooklm-mcp** |
| エージェントのコンテキストを最小にしたい | **notebooklm-py の CLI 直叩き**（ツール定義 0） |

両方入れて `notebooklm`（py, primary）と `notebooklm-browser`（mcp, フォールバック）の
2 サーバー構成にするのも有効です。その場合は
[02-setup-codex.md のバイナリ名衝突の注意](02-setup-codex.md#3-a-mcp-サーバーとして登録対話利用向け)
を必ず確認してください。

---

## トークン効率の実際

「70% 削減」は前提条件次第で大きく変わるため、導入後に自分の環境で実測することを勧めます。

### 測り方

1. **ベースライン**: 対象ドキュメントを Codex に直接読ませ、消費トークンを記録
2. **オフロード後**: 同じ問いを `notebooklm ask --json` に投げ、返ってきた回答だけを Codex に渡す
3. 比較する

### 削減が効く条件

- ソースの総量が大きいほど効く（書籍 1 冊、論文 10 本、動画文字起こしなど）
- 同じソースに何度も問い合わせるほど効く（ソース投入は 1 回で済む）
- 逆に、**小さいファイルを 1 回読むだけなら MCP のツール定義分だけ損** になります

### 効かせるための設定

```bash
# MCP を使うなら、必要なツールだけに絞る
NOTEBOOKLM_PROFILE=minimal npx notebooklm-mcp@latest

# 日常運用は CLI 直叩き（ツール定義 0）
notebooklm ask "..." --notebook <id> --json
```

---

## 参考

- notebooklm-py: https://github.com/teng-lin/notebooklm-py （[MCP ガイド](https://github.com/teng-lin/notebooklm-py/blob/main/docs/mcp-guide.md) / [CLI リファレンス](https://github.com/teng-lin/notebooklm-py/blob/main/docs/cli-reference.md)）
- notebooklm-mcp: https://github.com/PleasePrompto/notebooklm-mcp （[設定](https://github.com/PleasePrompto/notebooklm-mcp/blob/main/docs/configuration.md) / [ツール](https://github.com/PleasePrompto/notebooklm-mcp/blob/main/docs/tools.md)）

> 補足: 2026 年 7 月に Google は NotebookLM を **Gemini Notebook** へリブランドしましたが、
> 同一プロダクトであり既存リンクはリダイレクトされます。両ライブラリとも動作は変わりません。
