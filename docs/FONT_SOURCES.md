# ソースフォント

この文書は、KumiTypeが使用するソースフォントの配布元・固定バージョンと、取得・更新・登録の手順をまとめたものです。正確なURL・バージョン・SHA-256は `config/sources.lock.toml` に記録しています。

[ドキュメント一覧](README.md) · [プロジェクトREADME](../README.md)

## 配布元と固定バージョン

`latest` の自動追従は行いません。更新はロックファイルを明示的に変更し、新しい配布物のハッシュとライセンスを確認してから取得を実行します。

| ソース | 配布元 | 固定方法 |
| --- | --- | --- |
| Cascadia | Microsoft 公式 | `v2407.24`(通常/PL/NF) |
| IBM Plex / BIZ / Noto / M PLUS 1 / M PLUS 2 / Zen Kaku | Google Fonts 公式リポジトリ | 固定コミット |
| LINE Seed | LINE 公式 | `v20260828` |

## ロックIDの命名規則

ロックIDは `plex-bold` / `plex-extralight` / `zen-kaku-light` のような可読名に統一し、可変フォントには `noto-variable` / `mplus1-variable` / `mplus2-variable` を使用します。ID変更後も `kumitype fetch` は既存のSHA-256キャッシュからオフラインで再配置できます。旧IDでインストール済みのファイルは削除されず、現行ロックから参照されないだけです。

## ソースの更新手順

`latest` や不正な版・ハッシュは拒否されます。URLとSHA-256は公式配布物から確認し、次の手順で明示的に更新してください。例の`PINNED_VERSION`、`VERIFIED_SHA256`、URLは、実際に確認した値へ置き換えてください。

1. 公式配布物から固定版・URL・SHA-256を確認します。
2. ロックファイルの1レコードだけを更新します(この操作はネットワーク取得を行いません)。

    ```sh
    uv run --locked kumitype update-source --id plex-bold --version PINNED_VERSION \
      --url https://OFFICIAL_HOST/path/font.ttf --sha256 VERIFIED_SHA256 \
      --format ttf --filename font.ttf
    ```

    `--id` には可読なロックIDを、`--format` には `zip` / `ttf` / `otf` / `text` のいずれかを指定します。`--filename` は任意で、省略時は `<ID>.<format>` という名前で保存されます。`--id` / `--version` / `--url` / `--sha256` / `--format` は必須です。

3. ロックに従って取得・展開します。

    ```sh
    uv run --locked kumitype fetch
    ```

4. 更新後は合成とライセンスの検証を再実施します。

## 手動取得したアーカイブの登録

手動で取得した公式アーカイブやフォントは、ネットワークなしで登録できます。

```sh
uv run --locked kumitype import-source --id cascadia --file /path/to/official-artifact
```

`--id` にはロックに登録済みのIDを指定します。ロックに登録済みのSHA-256と一致するファイルのみを受け入れ、展開・解析してマニフェストを生成します。個別ライセンス文書も対応するID(例: `plex-license`)で登録してください。

## 日本語書体の追加・削除

新しい日本語書体を追加する場合は、次の手順で登録します。

1. `build.yaml` と同じディレクトリの `fonts.yaml` に、書体ID・`family`・`output` を登録します。`output` は生成フォントに使用可能な独自の英数字名を指定してください。
2. `build.yaml` の `japanese_fonts` に書体IDを追加します。
3. 対応するソースロックIDは、書体IDそのもの、または書体IDにハイフンを続けた可読名(例: `plex-bold`)を使用します。ライセンス文書は `<書体ID>-license`(例: `plex-license`)で登録します。

既存の日本語書体を削除する場合は `japanese_fonts` から除外します。

同じ日本語書体・入力フォントのファミリー・ウェイト・選択優先度の複数ファイルに補完的な文字範囲がある場合は、追加カバーを持つファイルを自動選択します。カバー範囲が同じTTF/OTFの重複は追加しません。任意の追加指定には `subset_files` も使えます。

## 取得・再実行の動作

- HTTPSのみを受け付け、SHA-256で検証してからキャッシュへ原子的に確定します。
- 接続(TCP/TLS)は15秒、接続後の読み取りは60秒のタイムアウトです。DNSが返す各アドレスを順に短い接続タイムアウトで試すため、IPv6接続がタイムアウトしてもIPv4へ進みます(DNS解決時間自体はOSの設定に依存します)。
- 一時的なネットワーク障害とHTTP 408/429/500/502/503/504は最大3回、1秒→2秒の指数バックオフで再試行します。ハッシュ不一致や恒久的なHTTPエラーは再試行しません。取得試行・バイト数・再試行待機は標準エラーに表示します。タイムアウトや再試行回数は、Python API `downloader.fetch` の `connect_timeout` / `read_timeout` / `attempts` / `backoff` で変更できます。
- マニフェストv2はロックの全フィールドと展開済みファイル一覧・SHA-256を照合し、一致する場合は再展開・フォント再解析・マニフェストの書き換えを行いません。ライセンスを含むファイルの欠損・改変、ロック変更、不正なマニフェストは再処理します。旧マニフェストは初回だけ再解析して移行します。SHA-256キーのキャッシュは継続利用します。
- 通常はTTFだけを解析し、文字集合を包含範囲 `codepoint_ranges: [[始点, 終点], ...]` として保存します。`locked_manifests` は従来の `codepoints` 配列を復元し、旧形式のマニフェストも引き続き読めます。
- **LINE Seedは例外**です。従来の `choose_donor` は同順位のパス順でOTFを選ぶため、出力バイナリを維持する目的でロックに `font_format = "otf"` を明示しています。LINE SeedまでTTFへ切り替える変更は行っていません。

## ウェイトごとのドナー選択

設定の全ウェイト(200/300/350/400/600/700)で `choose_donor` の選択を確認済みで、既存の最近傍選択は変更していません。

| 日本語書体 | ウェイト | 最近傍で選択されるドナー |
| --- | --- | --- |
| Plex | 350 | Plex Light |
| Zen Kaku | 200 / 350 | Zen Kaku Light |
| Zen Kaku | 600 | Zen Kaku Bold |

ロックから除外しているレコードは Plex Thin / Plex Medium / Zen Kaku Black / Zen Kaku Medium の4件のみで、ライセンスレコードはすべて保持しています。
