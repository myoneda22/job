# NotebookLM に投げる質問文

このディレクトリのファイルは、**NotebookLM への質問文そのもの**です。
そのまま `--prompt-file` に渡してください（Codex に貼るオーケストレーション指示は
[`docs/05-prompt-templates.md`](../../docs/05-prompt-templates.md) にあります）。

```bash
notebooklm ask --prompt-file prompts/notebooklm/paper-compare.md --notebook <id> --json
```

長い日本語をコマンドラインに直接書くとクォート／エンコーディングの事故が起きます。
とくに Windows では `--prompt-file` を既定にしてください（[docs/04](../../docs/04-windows-encoding.md#長いプロンプトはファイルから渡す)）。

`--prompt-file` は `ask`、プロンプトを取る `generate` 系、`source add-research` で使えます。
`source add ./file.pdf`（ファイルをソースとして**アップロード**する方）とは別物です。

| ファイル | 用途 | 対応テンプレート |
|---|---|---|
| `paper-compare.md` | 論文横断比較 | T1 |
| `video-to-spec.md` | 動画から実装仕様を抽出 | T2 |
| `quant-extract.md` | 論文からトレード戦略仕様を抽出 | T4 |
| `research-report.md` | 引用付き調査レポート | T7 |
| `error-diagnose.md` | エラーメッセージの原因調査 | T5 |
| `session-recall.md` | 過去の設計判断の想起 | T9 |

各ファイルの `<...>` は使用前に置換してください。
