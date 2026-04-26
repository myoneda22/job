# flight-search-mcp

国内・国際線の **安い航空券を検索する MCP サーバー**。
Amadeus Self-Service API（無料枠あり）を利用します。

## 提供ツール

| ツール名 | 用途 |
| --- | --- |
| `search_flights` | 出発地・目的地・日付を指定して航空券を安い順に検索 |
| `find_cheapest_dates` | 同じ路線で最安となる出発/復路日を検索 |
| `inspire_destinations` | 出発地から行ける目的地を予算順に提案（インスピレーション検索） |
| `lookup_airport` | 都市名・空港名から IATA コードを検索（例: 「沖縄」→ `OKA`） |

入力は IATA 3文字コード（`HND`, `KIX` など）か、主要都市・空港の日本語/英語名（`羽田`, `Tokyo`, `関空` など）に対応しています。

## セットアップ

### 1. Amadeus API キーを取得

1. <https://developers.amadeus.com> で無料登録
2. **My Self-Service Workspace** で新規アプリを作成
3. `API Key` と `API Secret` を控える（テスト環境は無料・本番環境は有料）

### 2. インストール & ビルド

```bash
npm install
npm run build
```

### 3. Claude Code / Claude Desktop に登録

`~/.claude.json` または `claude_desktop_config.json` の `mcpServers` に追加。

```json
{
  "mcpServers": {
    "flight-search": {
      "command": "node",
      "args": ["/絶対パス/job/dist/index.js"],
      "env": {
        "AMADEUS_CLIENT_ID": "<API Key>",
        "AMADEUS_CLIENT_SECRET": "<API Secret>",
        "AMADEUS_HOSTNAME": "test.api.amadeus.com"
      }
    }
  }
}
```

本番環境（有料）を使う場合は `AMADEUS_HOSTNAME` を `api.amadeus.com` に変更してください。

### Claude Code CLI から登録する場合

```bash
claude mcp add flight-search \
  --env AMADEUS_CLIENT_ID=xxx \
  --env AMADEUS_CLIENT_SECRET=yyy \
  -- node /絶対パス/job/dist/index.js
```

## 使い方の例

Claude に以下のように依頼してみてください。

- 「6/15 羽田 → 那覇の航空券を安い順に教えて」
- 「来月、東京から台北に2人で行きたい。最安の出発日は?」
- 「7月、成田発で5万円以下で行ける海外を提案して」
- 「”セントレア” の IATA コードは?」

## 開発

```bash
npm run dev      # tsc --watch
npm start        # node dist/index.js
```

## 注意

- Amadeus テスト環境は **本番より価格データが少なく、結果が空になる場合があります**。実運用では本番キーを推奨。
- 通貨は `currency` パラメータで指定（既定 `JPY`）。Amadeus 側がサポートしない通貨は USD などにフォールバックします。
- 価格は税込・1名あたりの目安値です。実際の予約は航空会社/OTA で確認してください。
