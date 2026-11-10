# 検証

`kumitype validate --all` は生成TTF、マニフェストのハッシュ、グリフ参照、
元グリフID、PUA、GSUB/GPOS/GDEF、追加文字の存在と送り幅を検査します。
GSUB/GPOSは完全一致、GDEFは追加したMn/Meグリフのmark(3)分類のみを許容し、
既存グリフの分類とその他のサブテーブルは変更を許しません。
追加Mn/Meのadvance=0・GDEF分類・`zero_width_mark_codepoints`の実体一致も検査します。
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

## FontBakeryによる品質検査（G7）

```sh
uv sync --locked --extra dev
# 28対象を構築・検証（既存の完全な出力がある場合は --reuse）
uv run --locked python scripts/check-goal.py --only G7 --build-dir build-quality
# 指定ディレクトリの全TTFを検査する場合（サブセットへの自動絞り込みなし）
uv run --locked python scripts/check-fontbakery.py --build-dir build-quality
```

FontBakery **1.1.0** をロックし、`check-universal --skip-network` を使います。
universalには `opentype` プロファイルが含まれます。OTS、FreeType、ttx往復なども
省略せず、チェックIDによる実行除外は行いません。明示的なSKIP指定はネットワーク依存の
チェックに限り、最新リリースの照会に依存しない品質判定にしています。
可変フォント専用など条件が合わないチェックもFontBakery自身がSKIPとします。
書体・系列ごとのディレクトリ単位で実行し、別ファミリー混在による誤判定を防ぎます。
独立した検査を最大2プロセスで並行実行し、結果の並び順は固定します。
`fontbakery/universal-NNN.json` と `.log` に生の結果、`summary.json` に分類結果、
入力TTFのSHA-256、ツール版、許可リストのSHA-256を保存します。
実行失敗・空/未完了/件数不整合のレポート・ERROR/FATALは成功扱いしません。
同じ出力先を再利用しても生JSONは毎回作り直し、検査中のTTF変更も拒否します。
G7はG2/G4と同じ28対象の存在・設定・マニフェストハッシュ確認を前提にします。
手動フルビルドCIも独立した28対象を `build-quality/` に生成してG7を実行し、
失敗時も生レポートと結果JSONをartifactとして保存します。

### FAILの分類

- **修正**: `opentype/monospace` の `mono-bad-panose` はLatin Text/Monospaced
  （PANOSE 2/9）を設定。日本語の2セル幅は変更しません。
- **修正**: `integer_ppem_if_hinted` の `bad-flags` は、継承したCascadiaヒント用に
  head.flags bit3を設定します。
- **修正**: `opentype/STAT/ital_axis` の `no-stat` は、静的フォントにも実際の
  wght/ital値を持つSTATを生成します。Regular/Romanだけをelidableにします。
- **意図的な継承**: `arabic_high_hamza` / `mark-in-gdef`、`case_mapping` /
  `missing-case-counterparts`、`nested_components` / `found-nested-components` は
  元のCascadiaMono-Regular.ttfでも同じFAILを実測しています。既存文字のシェーピング・
  グリフID・輪郭・収録範囲を維持する方針のため、上流の構造を変更しません。
  これは当該指摘の解消を意味せず、明示した既知制限として管理します。

`config/fontbakery-allowlist.json` は**チェックIDとメッセージコードの完全一致**に
日本語の理由を必須とします。チェック全体の無条件除外・ワイルドカードは禁止です。
同じチェックで新しいFAILコードが出ればG7は失敗します。WARNは除外せず記録し、
ERROR/FATALは許可リストに関係なく失敗させます。

### WARN一覧

28対象の検査で得たチェックID／メッセージコードは以下のとおりです。
件数・該当TTF・全文は各回のJSONが根拠です（同じチェックが複数WARNを返す場合があります）。
WARNはG7の合否に直接影響しませんが、修正済みと見なさず残課題として記録します。

| チェックID | メッセージコード | 内容・扱い |
|---|---|---|
| `opentype/gdef_mark_chars` | `mark-chars` | 追加したMn/Meはゼロ幅化しGDEF mark(3)へ分類。残る指摘は変更しないCascadia由来の分類 |
| `opentype/gdef_non_mark_chars` | `non-mark-chars` | 非マーク文字のGDEF分類。元のレイアウトを保持 |
| `opentype/gdef_spacing_marks` | `spacing-mark-glyphs` | 有送りマークの分類。元のレイアウトを保持 |
| `opentype/monospace` | `bad-numberOfHMetrics` | hMetricsを3個にする推奨。日英1:2幅と元GIDを保持 |
| `opentype/monospace` | `mono-outliers` | 日本語2セル等、ASCIIと異なる送り幅 |
| `opentype/xavgcharwidth` | `xAvgCharWidth-wrong` | 文字集合追加後の平均幅。上流の値を継承 |
| `opentype/STAT/ital_axis` | `wrong-ital-axis-linkedvalue` | 修正済み: Roman（ital=0）にLinkedValue=1.0を設定。以降のレポートで0件を確認 |
| `alt_caron` | `decomposed-outline` | caronの構成。元の輪郭を保持 |
| `arabic_high_hamza` | `glyph-area` | 元Cascadiaのhamzaの面積 |
| `cjk_chws_feature` | `missing-chws-feature`, `missing-vchw-feature` | 和文の詰め・縦組み機能は移植しない |
| `contour_count` | `contour-count` | 文字ごとの推奨輪郭数との相違 |
| `file_size` | `large-font` | 日本語・NFを収録するため1 MiB推奨値超過 |
| `math_signs_width` | `width-outliers` | 元の数学記号にある幅の相違 |
| `overlapping_path_segments` | `overlapping-path-segments` | 輪郭の重複部分。元の輪郭を保持 |
| `soft_hyphen` | `softhyphen` | ソフトハイフンの有無・扱い |
| `stylisticset_description` | `missing-description` | 元Cascadiaの一部ss機能の説明名がない |
| `unreachable_glyphs` | `unreachable-glyphs` | 元GIDを保持するため未到達グリフも残す |
| `valid_glyphnames` | `legacy-long-names` | 旧PostScriptの31文字制限を超す元グリフ名 |

## 開発時の静的検査

```sh
uv sync --locked --extra dev
uv run --locked mypy src
uv run --locked ruff check src tests scripts
uv run --locked pytest
```

型チェッカーはmypyを採用しています。Python依存だけで実行でき、Node.js等の
追加実行環境を不要にして既存のuvワークフローに統一できるためです。
`check_untyped_defs = true` で注釈のない関数の内部も検査します。
FontToolsは型情報のない外部ライブラリなので、そのimportだけを例外とし、
PyYAMLには型スタブを導入しています。CIの `python (3.14.7)` で型検査します。
循環参照回避が必要な `report.doctor` → `builder.choose_donor` の遅延import以外は
既存の関数内importをモジュール先頭に整理しています。

## 改善ループの合格判定

```sh
uv run --locked python scripts/check-goal.py --only G1,G2,G3
uv run --locked python scripts/check-goal.py --only G2,G4 --build-dir build-check --reuse
# 全ゲート（G5は28対象を2回ビルド・パッケージするため時間がかかります）
uv run --locked python scripts/check-goal.py > build-goals.json
```

`--only` を省略するとG1〜G7を実行します。JSONの `goals` にstatusとevidenceを返し、
FAILが1件でもあれば終了コード1です。G7も実行し、PENDINGはありません。
ログは標準エラー、JSONは標準出力に分離します。

検証サブセットはcode-nfとmono、日本語7書体それぞれの400 normal / 700 italicの
**28対象**です（400 italic / 700 normalは含みません）。既存のTTFとマニフェストが
あれば使い、不足分のみビルドします。`--reuse` は自動ビルドを禁止し、欠落時にFAILに
します。設定・対象・TTFハッシュが古い場合もFAILです。再ビルドが必要なら専用の空の
`--build-dir` を指定してください。G2は指定ディレクトリ内の追加TTFも検査します。
ソースは事前に `kumitype fetch` で用意し、判定自体はオフラインで実行できます。

| ゲート | 判定根拠 |
|---|---|
| G1 | pytest、ruff（src tests scripts）、mypy（src）の終了コード・ログ |
| G2 | TTF実体のDSIG、JIS bit17、fontRevision、achVendID |
| G3 | 正常な合成フォントを対照に、4違反を個別注入してvalidateが対応するエラーを返すこと |
| G4 | 取り込み実輪郭幅をadvanceと比較。ゼロ幅Mn/MeはEAW W/Fなら2セル、それ以外1セルの直前領域内に収まりadvance=0であることを検査 |
| G5 | 同じ出力パスで2回クリーンビルド・ZIP生成したTTF/ZIPの相対パス一覧とSHA-256一致 |
| G6 | 外部cwdからCLIのcache-dir受付、設定lockのカナリア、list、カスタムキャッシュ実ビルドを検査 |
| G7 | FontBakery universal（OpenTypeを含む）、許可リスト外FAIL / ERROR / FATALが0 |

G4〜G6で失敗してもG1〜G3の個別結果を保持します。G5では生成先をクリーンにして
28 TTF・14 ZIPを2回作成します。インスタンス・輪郭の中間キャッシュは保持します。
G5の一時出力は作業用一時領域に
置き、source/は削除しません。G6は独立した一時設定を使い、存在しないカナリアlockが
実際に参照されるかを確認するため、既存ソースの再取得やlockの書き換えは行いません。

実入力BIZ + Mono NF Regularについて、同じ固定依存を使用したPython 3.11.17と
3.14.7の生成TTFでSHA-256一致を確認しています。これは当該入力の検証結果であり、
Dockerと全対象OS間の同等性まで確認したものではありません。
