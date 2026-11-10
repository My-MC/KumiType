# 検証

この文書では、生成TTFの整合性・シェーピング・配布ZIP・品質を検査する手順と、結果の読み方がわかります。
実施済みの検証と保証範囲は[検証状況と既知の制約](ACCEPTANCE_STATUS.md)にまとめています。

[ドキュメント一覧](README.md) · [プロジェクトREADME](../README.md)

## 検証の全体像

| 検査 | 目的 | 使用するコマンド・スクリプト | 合格の目安 |
|---|---|---|---|
| TTF・マニフェスト | バイナリ・ハッシュ・幅・メタデータを検査します | `kumitype validate --all` | 全対象が有効です |
| HarfBuzz | 元Cascadiaと既存文字のシェーピングを比較します | `kumitype validate --all --require-harfbuzz`、`scripts/check-shaping.py` | 全対象・9サンプルで一致します |
| 対象の完全性 | 設定の対象と生成物を照合します | `kumitype audit` | 欠落・重複・想定外・未検証出力がありません |
| 配布ZIP | CRC・同梱物・ビルド出力との対応を検査します | `scripts/check-packages.py` | 全ZIPが監査に合格します |
| ゴール判定 | `G1`〜`G7`の根拠付き判定をまとめます | `scripts/check-goal.py` | 選択したゲートがすべて `PASS` です |
| FontBakery | universal（OpenTypeを含みます）の品質検査を行います | `scripts/check-fontbakery.py`、`G7` | 未許可 `FAIL` / `ERROR` / `FATAL` が0件です |
| 目視 | 実アプリで整列・字面・合字を確認します | `scripts/generate-preview.py`、`tests/rendering/sample.txt` | 意図した表示になっています |

Cascadiaの6種類を「ベース系列」、日本語の7種類を「日本語書体」、両者の組み合わせを「ファミリー」と呼びます。
以下のコマンドは、Python 3.14以降と固定ソースを準備したプロジェクトルートで実行します。
導入・取得・全数ビルドは[ビルドガイド](BUILDING.md)を参照してください。

> [!NOTE]
> 通常のゴール判定は28本のサブセットであり、全504本の検証ではありません。
> PR #5時点の全数検証（504 TTF・42 ZIP・HarfBuzz 4536比較・FontBakery 84本）と、PR #6の結合文字修正後の28本検証は区別してください。
> 全数の初回パイプラインは8コアVMで生成約26分、検証・パッケージを含め計約2時間16分でした。

## TTFとマニフェストの検証

### 目的

`kumitype validate --all` は、生成TTF、マニフェストのハッシュ、グリフ参照、元グリフID、PUA、追加文字の存在と送り幅を検査します。
`GSUB` / `GPOS` は完全一致を要求します。
`GDEF` は追加した `Mn` / `Me` グリフの `mark(3)` 分類だけを許容し、既存分類と他のサブテーブルの変更は拒否します。
追加マークの送り幅 `0`、分類、`merge.zero_width_mark_codepoints` と実体の一致も検査します。

### コマンド

生成済みTTF全件の整合性を検査します。

```sh
uv run --locked kumitype validate --all --build-dir build-latest
```

### 結果の見方

検証失敗や対象なしの場合は終了コード `1` です。
半角カナは取り込み一覧とは独立に `U+FF61`〜`U+FF9F` の全63文字を検査し、欠落または1セル以外の送り幅をエラーにします。
次のメタデータ違反もエラーです。

| 検査対象 | 期待値 |
|---|---|
| `DSIG` | 改変後のフォントには存在しません |
| `OS/2.ulCodePageRange1` | JIS/Japanのbit 17を設定します |
| `OS/2.achVendID` | `NONE` です |
| `head.fontRevision` | `project.version` から変換した値と一致します |

`fontRevision` は `major.minorPP`（minorは1桁、patchは2桁）をOpenTypeの16.16固定小数点に丸めます。
`0.1.0` は `0.100`、読み取り値は `0.100006103515625` です。
衝突を避けるため、2桁以上のminorと3桁以上のpatchは拒否します。
Python APIの `validate()` は `project_version` で期待値を指定でき、省略時はインストール済みKumiTypeのバージョンを使います。
ビルド時は設定の `project.version`、`validate` / `package` の再検証時はマニフェスト内の値を使います。

## HarfBuzzによるシェーピング比較

### 目的

元Cascadiaと9種類の記号列を比較し、グリフID・位置・送り幅が一致するか確認します。
配布前やCIでは、HarfBuzz未導入を成功と取り違えないよう必須化します。

### コマンド

`hb-shape` を明示して、整合性検査とシェーピング比較を実行します。

```sh
uv run --locked kumitype validate --all --build-dir build-latest --harfbuzz hb-shape --require-harfbuzz
```

生成済みスナップショットのシェーピングだけを比較する場合は、次を実行します。

```sh
uv run --locked python scripts/check-shaping.py --build-dir build-latest --harfbuzz hb-shape
```

特定のベース系列だけを比較する場合は、`--base` を繰り返し指定します。

```sh
uv run --locked python scripts/check-shaping.py --build-dir build-latest --harfbuzz hb-shape --base code --base code-pl --base code-nf
```

### 結果の見方

`validate` の `shaping.status=unavailable` は、HarfBuzzが利用できない状態です。
`--require-harfbuzz` なしではバイナリ検証の成功と分けて表示し、指定時は失敗にします。

単独スクリプトは `shaping-report.json` をビルド先に保存します。
部分比較は `shaping-report-code-code-pl-code-nf.json` のような別名です。
未導入・比較失敗・対象なしの場合は終了コード `1` です。
これはバイナリ・ライセンス・完全性監査の代わりではありません。

## 対象の完全性と配布ZIPの監査

### 目的

`kumitype audit` は、設定の全対象とマニフェストを照合します。
単純なファイル数ではなく、各 `base` / `japanese` / `weight` / `style` の欠落・重複・想定外・未検証出力を検出します。
ZIP監査では、CRC、同梱文書、TTFのSHA-256、ビルド出力との一対一対応を確認します。

### コマンド

生成済み出力の完全性を監査し、パッケージ化してZIPを独立に検査します。

```sh
uv run --locked kumitype audit --build-dir build-latest
uv run --locked kumitype package --all --build-dir build-latest --output-dir dist-latest
uv run --locked python scripts/check-packages.py --build-dir build-latest --dist-dir dist-latest
```

### 結果の見方

`audit` は、設定の全対象が完全な場合のみ終了コード `0` です。
TTF本体の再検証は別途 `validate` で実行します。

ZIP内のマニフェストは配布用に正規化して比較します。
実行時刻・所要時間・ピークRSS・ローカル保存先を除外し、配布用の設定ハッシュをパス非依存に再計算します。
それ以外の設定・ソース・ライセンス・チェックサムの差異は引き続きエラーです。
手動フルビルドCIでもZIP監査を実行します。

## 改善ループのゴール判定（`G1`〜`G7`）

### 目的

各ゲートの判定と根拠をJSONで保存し、失敗原因を追跡できるようにします。

| ゲート | 判定根拠 |
|---|---|
| `G1` | pytest、Ruff（`src tests scripts`）、mypy（`src`）の終了コードとログです |
| `G2` | TTF実体の `DSIG`、JIS bit 17、`fontRevision`、`achVendID` です |
| `G3` | 正常対照に4違反を個別注入し、`validate` が対応するエラーを返すことです |
| `G4` | 取り込み実輪郭がセル内に収まることです。ゼロ幅 `Mn` / `Me` はEAWに応じた直前1セル・2セル領域と送り幅 `0` を検査します |
| `G5` | 同じ出力パスへ2回クリーン生成したTTF・ZIPの相対パス一覧とSHA-256の一致です |
| `G6` | 外部作業ディレクトリ、全CLIの `--cache-dir` 受付、設定ロックのカナリア、カスタムキャッシュによる実ビルドです |
| `G7` | FontBakery universalの未許可 `FAIL` / `ERROR` / `FATAL` が0件であることです |

### コマンド

メタデータ関連のゲートだけを実行します。

```sh
uv run --locked python scripts/check-goal.py --only G1,G2,G3
```

既存の完全なサブセットを再利用し、メタデータと輪郭幅を検査します。

```sh
uv run --locked python scripts/check-goal.py --only G2,G4 --build-dir build-check --reuse
```

全ゲートを実行し、標準出力のJSONを保存します（`G5` は2回の生成・パッケージ化で時間がかかります）。

```sh
uv run --locked python scripts/check-goal.py > build-goals.json
```

### 結果の見方

`--only` を省略すると `G1`〜`G7` を実行します。
JSONの `goals` に `status` と `evidence` を返し、`FAIL` が1件でもあれば終了コード `1` です。
全ゲートが実装済みで、未実装を示す `PENDING` はありません。
ログは標準エラー、JSONは標準出力に分離します。
後段の失敗があっても、他のゲートの結果を保持します。

既定サブセットは `code-nf` / `mono` × 日本語7書体 × `400 normal` / `700 italic` の **28対象**です。
`400 italic` / `700 normal` は含みません。
既存のTTFとマニフェストを使い、不足分だけビルドします。
`--reuse` は自動ビルドを禁止し、欠落時に失敗します。
設定・対象・TTFハッシュが古い場合も失敗するため、再生成には専用の空の `--build-dir` を使ってください。
`G2` / `G4` は指定ディレクトリ内の追加TTFも検査します。
固定ソース取得後は、判定自体をオフラインで実行できます。

`G5` は作業用一時領域で28 TTF・14 ZIPを2回クリーン生成します。
インスタンス・輪郭の中間キャッシュは保持し、`source/` は削除しません。
`G6` は独立した一時設定と存在しないカナリアロックを使い、既存ソースの再取得やロックの書き換えは行いません。

## FontBakeryによる品質検査（`G7`）

### 目的

固定したFontBakery **1.1.0** の `check-universal --skip-network` で品質を検査します。
universalはOpenTypeプロファイルを含み、OTS・FreeType・ttx往復なども省略しません。
チェックIDによる実行除外は行わず、明示的なSKIP指定はネットワーク依存チェックに限ります。
可変フォント専用など条件が合わないチェックは、FontBakery自身が `SKIP` とします。

### コマンド

開発依存を同期し、28対象を構築して `G7` を実行します（既存の完全な出力には `--reuse` を付けます）。

```sh
uv sync --locked --extra dev
uv run --locked python scripts/check-goal.py --only G7 --build-dir build-quality
```

指定ディレクトリ内の全TTFを検査する場合は、サブセットへ自動で絞り込まない単独スクリプトを実行します。

```sh
uv run --locked python scripts/check-fontbakery.py --build-dir build-quality
```

### 結果の見方

ファミリーごとのディレクトリ単位で実行し、無関係なファミリーの混在による誤判定を防ぎます。
独立した検査を最大2プロセスで並行実行し、結果の並び順は固定します。
`fontbakery/universal-NNN.json` と `.log` に生結果、`summary.json` に分類結果・入力TTFのSHA-256・ツール版・許可リストのSHA-256を保存します。

実行失敗、空・未完了・件数不整合のレポート、`ERROR` / `FATAL` は成功扱いしません。
同じ出力先でも生JSONは毎回作り直し、検査中のTTF変更も拒否します。
`G7` は28対象の存在・設定・マニフェストハッシュの確認を前提とします。
手動フルビルドCIも独立した28対象を `build-quality/` に生成して検査し、失敗時も生レポートと結果JSONをartifactとして保存します。

### 修正済みの指摘

| チェックID | メッセージコード | 対応 |
|---|---|---|
| `opentype/monospace` | `mono-bad-panose` | PANOSEをLatin Text / Monospaced（2 / 9）に設定します。日本語の2セル幅は保持します |
| `integer_ppem_if_hinted` | `bad-flags` | 継承したCascadiaヒント用に `head.flags` bit 3を設定します |
| `opentype/STAT/ital_axis` | `no-stat` | 静的フォントにも実際の `wght` / `ital` 値を持つ `STAT` を生成します。Regular / Romanだけをelidableにします |
| `opentype/STAT/ital_axis` | `wrong-ital-axis-linkedvalue`（WARN） | PR #6でRoman（`ital=0`）に `LinkedValue=1.0` を設定し、28本の検査で0件を確認しました |
| `opentype/gdef_mark_chars` | `mark-chars`（WARNの一部） | PR #6で追加 `Mn` / `Me` をゼロ幅化して `mark(3)` に分類しました。28本のWARN中に取り込みグリフ `kumitype.` を含むものは0件でした。Cascadia由来の指摘は残ります |

### FAILの許可リスト

次の3組は、元の `CascadiaMono-Regular.ttf` でも同じ `FAIL` を実測しています。
既存文字のシェーピング・グリフID・輪郭・収録範囲を維持するための既知制限であり、解消済みではありません。

| チェックID | メッセージコード | 許可する理由 |
|---|---|---|
| `arabic_high_hamza` | `mark-in-gdef` | 上流由来の `U+0674` と `GDEF` 分類を継承し、既存のアラビア語シェーピングを変更しません |
| `case_mapping` | `missing-case-counterparts` | 固定ソースの文字集合を保持し、未収録の大小文字を新規に創作しません |
| `nested_components` | `found-nested-components` | 元グリフID・輪郭・ヒンティング・レイアウトを保持するため、既存の入れ子複合グリフを分解しません |

`config/fontbakery-allowlist.json` はチェックIDとメッセージコードの**完全一致**と、日本語の理由を必須とします。
チェック全体の無条件除外・ワイルドカードは禁止です。
同じチェックに新しい `FAIL` コードが出れば `G7` は失敗し、`ERROR` / `FATAL` は許可リストに関係なく失敗します。

### WARN一覧

次の表はPR #5の28対象で記録した19組を基に、PR #6での修正状況を追記したものです。
`cjk_chws_feature` の2コードはそれぞれ1組です。
`wrong-ital-axis-linkedvalue` はPR #6後には0件であり、現在も残るWARNとは区別しています。
件数・該当TTF・全文は、各回の生JSONを根拠にしてください。

| チェックID | メッセージコード | 内容・扱い |
|---|---|---|
| `opentype/gdef_mark_chars` | `mark-chars` | 追加マークは修正済みです。変更しないCascadia由来の分類が残ります |
| `opentype/gdef_non_mark_chars` | `non-mark-chars` | 元の非マーク文字の分類を保持します |
| `opentype/gdef_spacing_marks` | `spacing-mark-glyphs` | 元の有送りマークの分類を保持します |
| `opentype/monospace` | `bad-numberOfHMetrics` | hMetricsを3個にする推奨より、日英1:2幅と元グリフIDの保持を優先します |
| `opentype/monospace` | `mono-outliers` | 日本語2セルなど、ASCIIと異なる送り幅です |
| `opentype/xavgcharwidth` | `xAvgCharWidth-wrong` | 文字追加後も上流の平均幅を継承します |
| `opentype/STAT/ital_axis` | `wrong-ital-axis-linkedvalue` | PR #6で修正済みです（28本で0件） |
| `alt_caron` | `decomposed-outline` | 元のcaronの輪郭構成を保持します |
| `arabic_high_hamza` | `glyph-area` | 元Cascadiaのhamzaの面積です |
| `cjk_chws_feature` | `missing-chws-feature`, `missing-vchw-feature` | 和文の詰め・縦組み機能は移植しません |
| `contour_count` | `contour-count` | 推奨輪郭数との相違です |
| `file_size` | `large-font` | 日本語・NF収録で1 MiBの推奨値を超えます |
| `math_signs_width` | `width-outliers` | 元の数学記号の幅の相違です |
| `overlapping_path_segments` | `overlapping-path-segments` | 元輪郭の重複部分を保持します |
| `soft_hyphen` | `softhyphen` | ソフトハイフンの有無・扱いです |
| `stylisticset_description` | `missing-description` | 元Cascadiaの一部 `ss` 機能に説明名がありません |
| `unreachable_glyphs` | `unreachable-glyphs` | 元グリフIDの保持のため未到達グリフも残します |
| `valid_glyphnames` | `legacy-long-names` | 元グリフ名が旧PostScriptの31文字制限を超えます |

WARNは `G7` の合否に直接影響しませんが、修正済みの項目以外は残課題として記録します。

## 開発時のテスト・静的検査

### 目的

Pythonの回帰テスト、Lint、型検査で実装の整合性を確認します。
型チェッカーはPython依存だけで既存のuv運用に統一できるmypyです。

### コマンド

開発依存を同期して、テスト・Lint・型検査を実行します。

```sh
uv sync --locked --extra dev
uv run --locked pytest -q
uv run --locked ruff check src tests scripts
uv run --locked mypy src
```

### 結果の見方

いずれも終了コード `0` を確認します。
mypyは `check_untyped_defs = true` で注釈のない関数内部も検査します。
型情報のないFontToolsのimportだけを例外とし、PyYAMLには型スタブを導入しています。
通常CIの `python (3.14.7)` でも実行します。

## プレビューと実アプリの目視確認

### 目的

自動検査とは別に、字面・整列・句読点・括弧・カナ・罫線・アイコン・結合文字を確認します。

### コマンド

全出力のHTMLプレビューを生成します。

```sh
uv run --locked python scripts/generate-preview.py --build-dir build-latest --output preview.html
```

日本語7書体のRegularを同じベース系列で比較する場合は、次を実行します。

```sh
uv run --locked python scripts/generate-preview.py --build-dir build-latest --base mono-nf --weight 400 --style normal --output regular-gallery.html
```

### 結果の見方

1. ビルド先に生成したHTML（この例では `build-latest/preview.html` または `build-latest/regular-gallery.html`）をブラウザで開き、変更前後のスクリーンショットを比較します。
2. `tests/rendering/sample.txt` をVS Code、JetBrains IDE、GNOME Terminal / Ptyxis、Windows Terminalなどの対象アプリで表示します。
3. 生成ファミリーを選び、半角10文字と全角5文字の整列、句読点・括弧・カナ・罫線・アイコンを確認します。
4. Code系のベース系列では合字を有効化し、Mono系では合字が現れないことを確認します。

PR #5時点の全数HarfBuzz比較は実施済みですが、各GUI・Windows / macOS実機・Dockerでの検証は未実施です。
PR #6では結合文字の変更前後を `hb-view` のPNGで比較しています。
これらは全アプリでの表示品質や、日本語ドナーのアンカー配置の完全継承を保証するものではありません。
