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
