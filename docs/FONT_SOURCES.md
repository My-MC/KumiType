# ソースフォント

正確なURL、バージョンとSHA-256はconfig/sources.lock.tomlに記録しています。
CascadiaはMicrosoft公式v2407.24の通常/PL/NFを使用します。
Plex、BIZ、Noto、M PLUS 1/2、Zen KakuはGoogle Fonts公式リポジトリの
固定コミットを使用します。LINE SeedはLINE公式v20260828を使用します。

latestの自動追従は行いません。更新はロックファイルを明示的に変更し、
新しい配布物のハッシュとライセンスを確認してからfetchを実行します。
明示的な更新には以下のコマンドを使用します。

明示的な更新コマンド（ネットワーク取得は行わずロックのみ変更）:

```sh
kumitype update-source --id SOURCE_ID --version PINNED_VERSION \
  --url https://OFFICIAL_HOST/path/font.ttf --sha256 VERIFIED_SHA256 \
  --format ttf --filename font.ttf
kumitype fetch
```

URLとハッシュは公式配布物から確認してください。latestや不正な版・ハッシュは
拒否します。更新後は合成とライセンスの検証を再実施してください。

手動取得した公式アーカイブやフォントはオフラインで登録できます:

```sh
kumitype import-source --id SOURCE_ID --file /path/to/official-artifact
```

ロックに登録済みのSHA-256と一致するファイルのみを受け入れ、展開・解析して
マニフェストを生成します。個別ライセンス文書も対応するIDで登録してください。

新しい日本語系列を追加する場合は、build.yamlと同じディレクトリのfonts.yamlへ
ID・family・outputを登録し、build.yamlのjapanese_fontsへIDを追加します。
outputは生成フォントに使用可能な独自の英数字名を指定してください。
対応するソースロックIDは系列IDそのもの、または系列IDにハイフンを続けた名前を
使用します。ライセンス文書は系列ID-licenseで登録します。
既存系列を削除する場合はjapanese_fontsから除外します。

同じ系列・ファミリー・ウェイト・選択優先度の複数ファイルに補完的な文字範囲が
ある場合は、追加カバーを持つファイルを自動選択します。カバー範囲が同じ
TTF/OTFの重複は追加しません。任意の追加指定にはsubset_filesも使えます。


## 取得・再実行の動作

- HTTPSのみを受け付け、SHA-256で検証してからキャッシュへ原子的に確定します。
- 接続（TCP/TLS）は15秒、接続後の読み取りは60秒のタイムアウトです。
  DNSが返す各アドレスを順に短い接続タイムアウトで試すため、IPv6接続が
  タイムアウトしてもIPv4へ進みます（DNS解決時間自体はOSの設定に依存します）。
- 一時的なネットワーク障害とHTTP 408/429/500/502/503/504は最大3回、
  1秒→2秒の指数バックオフで再試行します。ハッシュ不一致や恒久的なHTTPエラーは
  再試行しません。取得試行・バイト数・再試行待機は標準エラーに表示します。
  Python API `downloader.fetch` の `connect_timeout` / `read_timeout` /
  `attempts` / `backoff` で変更できます。
- manifest v2はロックの全フィールドと展開済みファイル一覧・SHA-256を照合し、
  一致する場合は再展開・フォント再解析・manifestの書き換えを行いません。
  ライセンスを含むファイルの欠損・改変、ロック変更、不正なmanifestは再処理します。
  旧manifestは初回だけ再解析して移行します。SHA-256キーのキャッシュは継続利用します。
- 通常はTTFだけを解析し、文字集合を包含範囲 `codepoint_ranges: [[始点, 終点], ...]`
  として保存します。`locked_manifests` は従来の `codepoints` 配列を復元し、
  旧形式のmanifestも引き続き読めます。
- **LINE Seedは例外**です。従来の `choose_donor` は同順位のパス順でOTFを選ぶため、
  出力バイナリを維持する目的でロックに `font_format = "otf"` を明示しています。
  LINE SeedまでTTFへ切り替える変更は行っていません。

## ロックIDと必要なウェイト

IDは `plex-bold` / `plex-extralight` / `zen-kaku-light` のような可読名に統一し、
可変フォントには `noto-variable` / `mplus1-variable` / `mplus2-variable` を使用します。
ID変更後も `kumitype fetch` は既存のSHA-256キャッシュからオフラインで再配置できます。
旧IDのインストール済みファイルは削除せず、現行ロックから参照しないだけです。

設定の全ウェイト（200/300/350/400/600/700）で `choose_donor` の選択を確認し、
Plex Thin/Medium と Zen Kaku Black/Medium の4レコードだけを除外しました。
350ではPlex Light、200/350ではZen Kaku Light、600ではZen Kaku Boldを使う
既存の最近傍選択は変えていません。ライセンスレコードはすべて保持しています。
