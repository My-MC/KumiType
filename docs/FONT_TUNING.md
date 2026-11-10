# 日本語輪郭の調整

この文書では、日本語輪郭の大きさ・ベースライン・セル内への縮小を設定する方法と、半角カナ・結合文字の扱いがわかります。
Cascadiaの6種類を「ベース系列」、日本語の7種類を「日本語書体」、両者の組み合わせを「ファミリー」と呼びます。

[ドキュメント一覧](README.md) · [プロジェクトREADME](../README.md)

## 設定キーの一覧

`config/build.yaml` の `rendering` が共通設定です。
`font_overrides` の日本語書体IDごとの設定が、共通設定より優先されます。
表の既定値は、キーを省略したときの値です。

| キー | 既定値 | 意味 | 例 |
|---|---|---|---|
| `rendering.jp_scale` | `1.0` | UPM正規化に乗算する輪郭倍率です。正の有限数を指定します | `jp_scale: 0.98` |
| `rendering.baseline_offset` | `0` | 出力UPM単位の縦方向移動量です。正なら上へ移動します | `baseline_offset: 20` |
| `rendering.halfwidth_kana_scale` | `1.0` | 半角カナ輪郭だけに `jp_scale` と乗算する倍率です。送り幅は変えません | `halfwidth_kana_scale: 0.95` |
| `rendering.fit_overflow` | `true` | セルをはみ出す取り込み輪郭だけを水平方向に縮小します | `fit_overflow: false` |
| `rendering.fit_margin` | `0.02` | 縮小時の片側余白の基準幅に対する割合です。`0 <= 値 < 0.5` です | `fit_margin: 0.01` |
| `rendering.width_ratio` | `"1:2"` | 半角と全角の送り幅比です。現在は `"1:2"` のみ対応します | `width_ratio: "1:2"` |
| `rendering.japanese_italic` | `upright` | 日本語輪郭を立体のまま使用します。合成斜体は未対応です | `japanese_italic: upright` |
| `font_overrides` | `{}` | 日本語書体ID単位で共通設定を上書きします | `font_overrides: {biz: {jp_scale: 0.98}}` |
| `unicode_overrides` | `{}`（隣接ファイルとの合成前） | 16進コードポイントの文字列キーに `cascadia` または `japanese` を指定します。PUAは上書きできません | `unicode_overrides: {"3001": japanese}` |
| `font_overrides.<ID>.subset_files` | `[]`（明示追加なし） | 選択した主ソース・自動選択の分割ソースに続けて読む静的ファイルです | `subset_files: [source/extra/part.ttf]` |
| `font_overrides.<ID>.subset_licenses` | `[]` | 追加配布元のライセンス文書です。ハッシュを記録し、ZIPに同梱します | `subset_licenses: [source/extra/OFL.txt]` |

`config/build.yaml` と同じディレクトリの `unicode.yaml` は自動で読み込みます。
同じコードポイントを両方に指定した場合は、`config/build.yaml` 側が優先されます。

次のYAML例は、共通設定と `biz` だけの上書きを示します（既存の設定に該当キーを統合してください）。

```yaml
rendering:
  width_ratio: "1:2"
  jp_scale: 1.0
  baseline_offset: 0
  halfwidth_kana_scale: 1.0
  fit_overflow: true
  fit_margin: 0.02
  japanese_italic: upright
font_overrides:
  biz:
    jp_scale: 0.98
    baseline_offset: 20
unicode_overrides:
  "3001": japanese
```

> [!NOTE]
> `jp_scale: 1.0` は個別の見た目を調整していない値です。
> 例の倍率・移動量は推奨値ではなく、プレビューで高さ・字面・ベースラインを比較して決めてください。
> 幅比 `3:5` と日本語の合成斜体は現在エラーになります。

## 1セル・2セルへの水平縮小

### 送り幅と輪郭幅の違い

1セルは、既存Cascadiaのスペースの送り幅です。
通常の取り込み文字はEast Asian Widthが `W` / `F` なら2セル、それ以外は1セルの送り幅を持ちます（結合文字は次節の例外です）。
Ambiguous（`A`）の文字も1セルなので、ドナーの輪郭が全角相当の場合は縮小が必要です。
既存Cascadiaの輪郭・送り幅をこの規則で変更することはありません。

次の図は、1セル扱いのAmbiguous文字を日本語ドナーから取り込む場合の概念図です（実際の収録元は文字選択規則に依存します）。

```text
cell = Cascadiaのスペース送り幅

取り込み前の輪郭:   <------ 全角相当の字面 ------>
出力の送り幅:       |--------- 1セル ---------|
縮小・中央配置後:   |  <--- 輪郭 --->         |  advance = cell
全角 W/F の場合:    |--------- 2セル -------------------|  advance = 2 * cell

超過時の目標輪郭幅 = 基準幅 * (1 - 2 * fit_margin)
```

`fit_overflow: true` のとき、セルからはみ出す輪郭だけを水平方向に縮小して中央配置します。
セル内に既に収まる輪郭を、余白確保のためだけに縮小することはありません。
縦座標・ベースライン・送り幅は、この水平縮小では変えません。

### 変換の順序と記録

1. ドナーのUPMを出力UPMに正規化し、`jp_scale` と `baseline_offset` を適用します。
2. 半角カナには、必要な派生の水平50%変換と `halfwidth_kana_scale` を適用します。
3. cubicからquadraticへの変換と丸めを済ませた最終輪郭で、セルからのはみ出しを判定します。
4. 超過する輪郭にだけ `fit_overflow` / `fit_margin` を適用します。

出力マニフェストの `merge.fitted_codepoints` は縮小した文字、`merge.overflow_codepoints` は変換・丸め後も超過する文字です。
設定値とキャッシュ形式の版を輪郭キャッシュのキーに含めるため、設定変更後に古い輪郭を再利用しません。

## 結合文字（`Mn` / `Me`）のゼロ幅化

日本語ドナーから追加するUnicode一般カテゴリ `Mn` / `Me` は、送り幅を `0` にして直前の文字へ重ねます。
East Asian Widthが `W` / `F` なら基準幅は2セル、それ以外（Ambiguousを含みます）は1セルです。
基準セル内で通常と同じ水平縮小・中央配置を行ってから、基準幅だけ左へ移動します。

次の図は、結合文字の原点が直前文字の右端に来るときの配置です。

```text
文字列の例: a + U+030F（結合二重アクサングラーブ）、か + U+3099（結合濁点）

                     結合文字の原点 x=0
1セル基準:   [-cell -------- 0]    輪郭中心 x=-cell/2、advance=0
2セル基準:   [-2*cell ------- 0]    輪郭中心 x=-cell、advance=0
次の文字:                       → 結合文字によるカーソル移動はありません
```

縦座標と設定済みベースラインは、この左移動では変えません。
基準幅を超える輪郭には `fit_overflow` / `fit_margin` を適用し、余白は送り幅 `0` ではなく基準幅に対する割合で計算します。
空輪郭の結合文字も送り幅は `0` です。

追加したマークを `GDEF.GlyphClassDef` の `mark(3)` に登録し、`merge.zero_width_mark_codepoints` へ記録します。
既存の `GDEF` 分類・他のサブテーブル・`GSUB` / `GPOS` は変更しません。
Cascadia由来の結合文字と、非結合Ambiguous文字の1セル縮小方針も変更しません。

> [!WARNING]
> 日本語ドナーの `GPOS` アンカーは移植しません。
> 固定セル基準の重ね合わせなので、任意の直前文字や複数マークに対する精密なアンカー配置を保証するものではありません。

## 半角カナと追加ソース

### 半角カナの派生

選択した日本語書体に半角カナのUnicodeマッピングがない場合は、対応する全角文字の輪郭を水平方向50%に変換して1セルへ配置します。
別の日本語書体からの補完は行わず、元から半角グリフがある場合はその輪郭を優先します。
派生したコードポイントを `merge.derived_halfwidth_codepoints` へ記録し、警告も出します。
`halfwidth_kana_scale` は全角文字と送り幅を変えず、半角カナ輪郭だけを調整します。

### 分割ソースとライセンス

同一ファミリー・同一ウェイトの補完的な分割範囲は、自動選択にも対応します。
さらに追加する場合は `font_overrides.<ID>.subset_files` に指定し、重複文字は先のソースを優先します。
同一ファミリー・同一ウェイト・同一ライセンスの静的ファイルを指定してください。

追加ファイルのSHA-256と著作権・ライセンスメタデータも記録・統合します。
追加配布元のライセンス文書は自動探索しないため、`subset_licenses` に明示してください。
ビルド時のSHA-256をZIP生成時に再照合して同梱します。
相対パスは設定のプロジェクトルート基準です（詳細は[ビルドガイド](BUILDING.md)を参照してください）。

## 調整と確認の手順

1. 設定を変更し、専用の出力先へ対象ファミリーをビルドします。
2. 輪郭超過レポートとプレビューを作成します。
3. 送り幅の整列とは別に、輪郭のはみ出し・高さ・ベースライン・結合文字の重なりを確認します。

次のコマンドは、`biz` と `mono` のRegularを生成し、超過レポートとHTMLプレビューを作成します。

```sh
uv run --locked kumitype build --base mono --jp biz --weight 400 --style normal --output-dir build-tuning
uv run --locked python scripts/check-overflow.py --build-dir build-tuning
uv run --locked python scripts/generate-preview.py --build-dir build-tuning --base mono --weight 400 --style normal --output tuning-preview.html
```

`overflow-report.json` でUnicode名・幅クラス・文字種を確認し、全角とAmbiguous・Neutral・半角カナの超過を区別します。
`build-tuning/tuning-preview.html` をブラウザで開き、変更前後を比較してください。
自動検証・HarfBuzz比較・配布前の検査は[検証ガイド](VALIDATION.md)を参照してください。
