# 検証

`kumitype validate --all` は生成TTF、マニフェストのハッシュ、グリフ参照、
元グリフID、PUA、GSUB/GPOS/GDEF、追加文字の存在と送り幅を検査します。
検証失敗や対象がない場合は終了コード1を返します。
DSIGの残存、OS/2.ulCodePageRange1のbit17未設定、achVendIDが `NONE` 以外、
head.fontRevisionとバージョンの不一致もエラーです。`validate()` の
`project_version` で期待バージョンを指定でき、省略時はインストール済み
KumiTypeのproject.versionを使います。ビルド時は設定のproject.versionを渡します。
OpenTypeの16.16固定小数点に丸め、0.1.0は0.100（読取値0.100006103515625）です。
一般にはmajor.minorPP（minorは0〜9、patchは2桁）に変換し、衝突を避けるため
2桁以上のminor・3桁以上のpatchは拒否します。validate/packageの再検証は
各マニフェストに記録されたproject.versionを期待値に使います。

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
マニフェストは配布用の正規化（実行時刻・所要時間・ピークRSS除外）後に比較します。
除外対象以外の設定・ソース・チェックサムの差異は引き続きエラーです。
フルビルドCIでもこの検査を実行します。

ブラウザで7系列のRegularだけ比較する例:

```sh
python scripts/generate-preview.py --build-dir build-latest --base mono-nf --weight 400 --style normal --output regular-gallery.html
```

半角カナはソース由来の取り込み一覧と独立してU+FF61–U+FF9Fの全63文字を
検査し、欠落または1セル以外のadvanceをエラーにします。

## 改善ループの合格判定

```sh
uv run --locked python scripts/check-goal.py --only G1,G2,G3
uv run --locked python scripts/check-goal.py --only G2,G4 --build-dir build-check --reuse
# 全ゲート（G5は28対象を2回ビルド・パッケージするため時間がかかります）
uv run --locked python scripts/check-goal.py > build-goals.json
```

`--only` を省略するとG1〜G7を実行します。JSONの `goals` にstatusとevidenceを返し、
FAILが1件でもあれば終了コード1です。未実装のG7のみPENDING（終了コードに影響なし）。
ログは標準エラー、JSONは標準出力に分離します。

検証サブセットはcode-nfとmono、日本語7書体それぞれの400 normal / 700 italicの
**28対象**です（400 italic / 700 normalは含みません）。既存のTTFとマニフェストが
あれば使い、不足分のみビルドします。`--reuse` は自動ビルドを禁止し、欠落時にFAILに
します。設定・対象・TTFハッシュが古い場合もFAILです。再ビルドが必要なら専用の空の
`--build-dir` を指定してください。G2は指定ディレクトリ内の追加TTFも検査します。
ソースは事前に `kumitype fetch` で用意し、判定自体はオフラインで実行できます。

| ゲート | 判定根拠 |
|---|---|
| G1 | pytestとruff（src tests scripts）の終了コード・ログ |
| G2 | TTF実体のDSIG、JIS bit17、fontRevision、achVendID |
| G3 | 正常な合成フォントを対照に、4違反を個別注入してvalidateが対応するエラーを返すこと |
| G4 | マニフェストの取り込み一覧に対して、実輪郭のxMax−xMinとadvanceを全件比較 |
| G5 | 同じ出力パスで2回クリーンビルド・ZIP生成したTTF/ZIPの相対パス一覧とSHA-256一致 |
| G6 | 外部cwdからCLIのcache-dir受付、設定lockのカナリア、list、カスタムキャッシュ実ビルドを検査 |
| G7 | fontbakery（後続実装までPENDING） |

G4〜G6で失敗してもG1〜G3の個別結果を保持します。G5では生成先をクリーンにして
28 TTF・14 ZIPを2回作成します。インスタンス・輪郭の中間キャッシュは保持します。
G5の一時出力は作業用一時領域に
置き、source/は削除しません。G6は独立した一時設定を使い、存在しないカナリアlockが
実際に参照されるかを確認するため、既存ソースの再取得やlockの書き換えは行いません。

実入力BIZ + Mono NF Regularについて、同じ固定依存を使用したPython 3.11.17と
3.14.7の生成TTFでSHA-256一致を確認しています。これは当該入力の検証結果であり、
Dockerと全対象OS間の同等性まで確認したものではありません。
