# codex-chatgpt — `-p` で API キーなしの Codex を使う

Codex CLI を **OpenAI API キーなし**、ChatGPT アカウントのログインだけで動かすための
プロファイルとラッパー。`codex` の `-p / --profile` オプションを使う。

```
codex-chatgpt/
├── chatgpt.config.toml   # -p で読ませるプロファイル本体
├── bin/codex-chatgpt     # codex -p chatgpt のラッパー
├── install.sh            # プロファイルを $CODEX_HOME に配置
└── test.sh               # テスト
```

## 前提

- ChatGPT の有料プラン (Plus / Pro / Business / Enterprise)。Codex の利用枠はプランに含まれる。
- Codex CLI が profile v2 に対応していること (`npm install -g @openai/codex`)。
  `codex --help` の `-p, --profile <CONFIG_PROFILE_V2>` が目印。
  動作確認は `codex-cli 0.149.1`。

## 仕組み

2 つの機能を組み合わせているだけ。

**1. `-p` はプロファイルのファイルを重ねる**

```
-p, --profile <CONFIG_PROFILE_V2>
        Layer $CODEX_HOME/<name>.config.toml on top of the base user config
```

`codex -p chatgpt` は `~/.codex/chatgpt.config.toml` を通常の `config.toml` の上に
重ねて読む。つまり **`-p` を付けたときだけ効く設定** を分けて置ける。素の `codex` の
挙動は変わらない。

**2. `forced_login_method` が認証方法を固定する**

プロファイルに置く中身はこれだけ:

```toml
forced_login_method = "chatgpt"
```

値は `"chatgpt"` か `"api"`。`"chatgpt"` にすると、保存済みの認証が API キーだった場合に
Codex は起動を拒否する:

```
ChatGPT login is required, but an API key is currently being used. Logging out.
```

そのまま `auth.json` を破棄して、ChatGPT ログインをやり直させる。
結果として `-p chatgpt` 経由では API キーが絶対に使われない。

## インストール

```sh
./install.sh                  # ~/.codex/chatgpt.config.toml を配置
./install.sh --link ~/bin     # ラッパーの symlink も作る
```

`install.sh` は codex のバージョンが `-p` のファイル方式に対応しているか確認し、
配置した設定を `codex --strict-config` に読ませて検証する。既存のファイルや
API キーで保存済みの `auth.json` は退避してから進む。

オプション:

| オプション | 意味 |
| --- | --- |
| `--profile NAME` | プロファイル名を変える (既定 `chatgpt`) |
| `--codex-home DIR` | 配置先の Codex ホーム (既定 `~/.codex`) |
| `--link DIR` | `DIR/codex-chatgpt` に symlink を作る |

## ログイン

```sh
bin/codex-chatgpt login                # ブラウザが開く (localhost にコールバック)
bin/codex-chatgpt login --device-auth  # SSH / コンテナなどブラウザが無い環境
bin/codex-chatgpt login status         # 状態確認
```

`codex login` は `-p` を受け付けないので、ラッパーは同じ強制設定を
`-c 'forced_login_method="chatgpt"'` として渡している。

成功すると `~/.codex/auth.json` に ChatGPT のトークンが入る (`"auth_mode": "chatgpt"`)。
API キーはどこにも保存されない。

## 使う

```sh
bin/codex-chatgpt                              # 対話 TUI
bin/codex-chatgpt exec "テストの失敗を直して"      # ヘッドレス実行
bin/codex-chatgpt exec --json "変更点を要約して"   # JSONL で出力
bin/codex-chatgpt exec -s workspace-write "..."  # サンドボックス指定
```

引数はそのまま `codex` に渡るので、`codex` にできることは全部できる。

ラッパーを使わない場合は `-p` を自分で付ける:

```sh
codex -p chatgpt exec "..."
```

## 注意点

**環境変数の API キーは `forced_login_method` では止まらない。**
Codex は `auth.json` が無くても `OPENAI_API_KEY` / `CODEX_API_KEY` を認証情報として拾い、
`forced_login_method = "chatgpt"` はこの経路を塞がない (`codex doctor` の
`auth is provided by environment` で確認できる)。ラッパーはこの 2 つを
`unset` してから `codex` を起動する。素の `codex -p chatgpt` を使うなら、
API キーの環境変数を自分で外すこと。

**API キーでログイン済みだと `auth.json` が消える。**
`-p chatgpt` を付けた時点で Codex が API キーの認証を破棄する。API キーでの
Codex 利用を残したいなら `install.sh` が作るバックアップ
(`auth.json.apikey.bak-*`) から戻すか、`CODEX_HOME` を分けて使う。

**プロファイルのファイルが無くても codex は黙って起動する。**
`-p nosuch` はエラーにならず、単に何も重ならない。API キー禁止も効かない状態で
動いてしまうので、ラッパーは起動前にファイルの存在を確認している。

**CI などで使う場合。**
ChatGPT ログインは対話が必要なので、CI では一度ログインしたマシンの
`~/.codex/auth.json` をシークレットとして持ち込み、`CODEX_HOME` で指す形になる。
トークンには有効期限があるため、期限切れ時は再ログインが要る。

## テスト

```sh
./test.sh
```

偽の `codex` をスタブにして `install.sh` とラッパーの引数・環境変数の扱いを確認する。
PATH に本物の `codex` があれば、実際に設定を読ませる結合テストも走る (通信は発生しない)。
