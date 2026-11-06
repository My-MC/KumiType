# 検証

`kumitype validate --all` は生成TTF、マニフェストのハッシュ、グリフ参照、
元グリフID、PUA、GSUB/GPOS/GDEF、追加文字の存在と送り幅を検査します。
検証失敗や対象がない場合は終了コード1を返します。

`python scripts/generate-preview.py` で `build/preview.html` を生成します。
ブラウザで開いてスクリーンショットを保存し、変更前後を比較してください。
これは目視確認用であり、自動テストの代わりにはなりません。

`tests/rendering/sample.txt` をVS Code、JetBrains IDE、GNOME Terminal/Ptyxis、
Windows Terminal、HarfBuzz対応ターミナルで表示してください。
各アプリで生成ファミリーを選択し、半角10文字と全角5文字の整列、
句読点・括弧・カナ・罫線・アイコンを確認します。
Codeでは合字を有効化し、Monoでは合字が現れないことを確認します。

HarfBuzzシェーピング比較と各GUIでの目視確認はまだ実施していません。

`kumitype validate --all --harfbuzz /path/to/hb-shape` でHarfBuzzを指定できます。
導入済みの場合は元Cascadiaと9種類の記号列を比較し、グリフID・位置・送りが
一致することを確認します。未導入の場合はshaping.status=unavailableを返し、
バイナリ検証の成功とは分けて表示します。

`kumitype audit` は設定の全対象とマニフェストを照合し、欠落・対象重複・
想定外の対象・未検証出力を報告します。単純なファイル数一致ではなく、
各base/japanese/weight/styleが揃うことを確認します。完全な場合のみ終了コード0です。
TTF本体の再検証は別途validateを実行してください。

生成済みスナップショット全件のシェーピングだけを比較する場合:

```sh
python scripts/check-shaping.py --build-dir build-latest --harfbuzz /path/to/hb-shape
```

結果はshaping-report.jsonへ保存します。未導入・比較失敗・対象なしの場合は
終了コード1です。これはバイナリ・ライセンス・完全性の監査とは別の検査です。

配布前の検証やCIでは `--require-harfbuzz` を付けると、HarfBuzz未導入も失敗として
扱います。フルビルドCIはCLIツールを導入し、このオプションで検証します。

生成済みの系列のみ確認する場合は `--base code --base code-pl --base code-nf` のように
複数指定できます。部分比較レポートは全件比較とは別のファイルへ保存します。

ZIP生成後は `python scripts/check-packages.py --build-dir build-latest --dist-dir dist-latest`
でCRC、同梱文書、TTFのSHA-256、ビルド出力との一対一対応を確認できます。
フルビルドCIでもこの検査を実行します。

ブラウザで7系列のRegularだけ比較する例:

```sh
python scripts/generate-preview.py --build-dir build-latest --base mono-nf --weight 400 --style normal --output regular-gallery.html
```

半角カナはソース由来の取り込み一覧と独立してU+FF61–U+FF9Fの全63文字を
検査し、欠落または1セル以外のadvanceをエラーにします。

実入力BIZ + Mono NF Regularについて、同じ固定依存を使用したPython 3.11.17と
3.14.7の生成TTFでSHA-256一致を確認しています。これは当該入力の検証結果であり、
Dockerと全対象OS間の同等性まで確認したものではありません。
