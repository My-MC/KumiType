# Changelog

## 0.1.0 (開発中)

- Cascadia通常/PL/NFと日本語7系列の固定ソース取得を追加。
- 元のグリフIDとOpenTypeテーブルを保持する静的TTF合成を追加。
- 日本語輪郭のUPM正規化、中央配置、幅設定、ベースライン調整を追加。
- 独自ファミリー名、著作権・ライセンス統合、検証、マニフェスト、ZIPを追加。
- Docker、OSセットアップ、CI、表示サンプルを追加。
- G1〜G7の根拠付きJSON判定スクリプトを追加（fontbakeryはPENDING）。
- 生成フォントのDSIGを削除し、JIS/Japanコードページbit17、ベンダーID `NONE`、
  project.version由来のfontRevisionを設定。validatorでも各違反をエラー化。
- CIのruff対象を `src tests scripts` に統一。
- 対応Pythonを3.14以降に変更し、Python 3.11のCIを削除（3.14未満はActive Support終了のため）。

- 幅超過する日本語取り込み輪郭を1セル／2セル内へ水平縮小（既定有効）。
  `fit_overflow`・片側余白`fit_margin`、`fitted_codepoints`と縮小後の超過記録を追加。
  輪郭キャッシュを新形式に切り替え、設定変更時の古い輪郭の再利用を防止。

受け入れ条件の全検証はまだ完了していません。
