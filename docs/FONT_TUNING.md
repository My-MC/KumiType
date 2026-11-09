# 日本語輪郭の調整

config/build.yamlのrenderingまたはfont_overridesの各日本語IDへ
jp_scaleとbaseline_offsetを設定します。baseline_offsetは出力UPMの単位です。
全角は既存Cascadiaスペースの2倍、半角カナは1倍のadvanceです。
輪郭幅がadvanceを超える取り込み文字は、既定で水平方向のみ縮小して中央配置します。
Ambiguous/Neutralなどの1セル文字と全角2セル文字に同じ規則を適用します。
縦方向・ベースライン・advanceとCascadia由来の輪郭は変えません。

- `rendering.fit_overflow`: 既定`true`。`false`で自動縮小を無効化できます。
- `rendering.fit_margin`: 片側余白のセル幅に対する割合（既定`0.02`、`0 <= 値 < 0.5`）。
  縮小後の目標輪郭幅は`advance * (1 - 2 * fit_margin)`です。
  セル内に既に収まる輪郭を、余白確保のためだけに縮小することはありません。

各書体の`font_overrides`にも同じ設定を指定できます。半角カナ派生の水平50%変換と
`halfwidth_kana_scale`・`jp_scale`を適用した後に超過を判定します。
JSONの`merge.fitted_codepoints`は縮小した文字、`overflow_codepoints`は
変換・丸め後も超過する文字です。新しい設定とキャッシュ形式の版をキーに含め、
旧輪郭キャッシュは再利用しません。

標準jp_scale=1.0は未調整値です。プレビューを使って各書体の高さ・字面・
ベースラインを比較してください。3:5と日本語合成斜体は現在エラーになります。

文字ごとの優先指定はbuild.yamlのunicode_overridesへ16進コードポイントを
文字列キーとして指定します。値はcascadiaまたはjapaneseです。
PUAは上書き指定に関わらずCascadiaを保護します。

分割された追加ソースはfont_overridesの各系列にsubset_filesのパス一覧を
指定できます。選択した主ソースに続けて追加し、重複文字は先のソースを保持します。
追加ファイルのSHA-256も出力マニフェストへ記録します。
同一ファミリー・ウェイトの補完的な分割範囲は自動選択にも対応します。
追加ソースは同一ファミリー・同一ウェイト・同一ライセンスの静的ファイルを
指定してください。追加ファイルの著作権・ライセンスメタデータは統合します。
追加配布元のライセンス文書の自動同梱にはまだ対応していません。

build.yamlと同じディレクトリのunicode.yamlを自動で読み込みます。
同じコードポイントをbuild.yamlにも指定した場合はbuild.yaml側を優先します。

追加配布元のライセンス文書はfont_overrides.*.subset_licensesへパス一覧で
指定できます。ビルド時にSHA-256を記録し、ZIP生成時に再照合して同梱します。

`python scripts/check-overflow.py --build-dir build-latest` は超過コードポイントの
Unicode名・幅クラス・文字種をoverflow-report.jsonへ記録します。
全角の超過とAmbiguous/Neutral/半角カナの超過を区別して調整してください。
advanceの整列と実輪郭のはみ出しは別の検査です。

半角カナだけ輪郭を調整する場合はrenderingまたは各書体のfont_overridesへ
halfwidth_kana_scaleを指定します（既定1.0）。全角文字とadvanceは変更せず、
半角カナ輪郭だけにjp_scaleと乗算します。実際の設定値は目視確認後に決めてください。
キャッシュキーにもこの係数を含めるため、設定変更後の古い輪郭は再利用しません。

選択書体に半角カナのUnicodeマッピングがない場合は、対応する全角文字の輪郭を
水平方向50%に変換して1セルに配置します。別書体からの補完は行いません。
補完したコードポイントをderived_halfwidth_codepointsへ記録し、警告も出します。
元から半角グリフがある場合はその輪郭を優先します。
