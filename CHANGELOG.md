# Changelog

## 0.1.0 (開発中)

- Cascadia通常/PL/NFと日本語7系列の固定ソース取得を追加。
- 元のグリフIDとOpenTypeテーブルを保持する静的TTF合成を追加。
- 日本語輪郭のUPM正規化、中央配置、幅設定、ベースライン調整を追加。
- 独自ファミリー名、著作権・ライセンス統合、検証、マニフェスト、ZIPを追加。
- Docker、OSセットアップ、CI、表示サンプルを追加。
- G1〜G7の根拠付きJSON判定スクリプトを追加。
- 生成フォントのDSIGを削除し、JIS/Japanコードページbit17、ベンダーID `NONE`、
  project.version由来のfontRevisionを設定。validatorでも各違反をエラー化。
- CIのruff対象を `src tests scripts` に統一。
- 対応Pythonを3.14以降に変更し、Python 3.11のCIを削除（3.14未満はActive Support終了のため）。

- 幅超過する日本語取り込み輪郭を1セル／2セル内へ水平縮小（既定有効）。
  `fit_overflow`・片側余白`fit_margin`、`fitted_codepoints`と縮小後の超過記録を追加。
  輪郭キャッシュを新形式に切り替え、設定変更時の古い輪郭の再利用を防止。

- 設定の `sources.lock` と入出力パスを全コマンドで統一し、明示したCLI指定だけで上書き。
  外部cwdからの実行と `paths.cache` / `--cache-dir` による両キャッシュの移動に対応。
- doctorのreadinessを選択したフォント・ライセンスに限定し、未選択ソースは情報表示。
- ZIPの順序・日時（`SOURCE_DATE_EPOCH` 対応）・権限を固定し、同梱マニフェストから
  実行時刻・所要時間・ピークRSS・ローカルパスを除外。配布用の設定ハッシュは
  パス非依存に再計算し、ソース/ライセンスのハッシュとビルド側の診断情報は保持。
- 別配置・別ソース/キャッシュ保存先のZIP一致を検証し、入れ子の既存ソースパス解決と
  Dockerでマウントした設定の参照（`KUMITYPE_CONFIG`）を修正。
- パッケージ監査を配布用マニフェストに対応させ、外部cwdとZIP再現性の回帰テストを追加。

- HTTPS取得に接続15秒・読み取り60秒の分離タイムアウト、アドレス別接続試行、
  最大3回の指数バックオフと標準エラーへの進捗表示を追加。
- manifest v2に展開済みファイルハッシュと文字範囲表現を導入し、再fetch時の
  不要な展開・解析を省略。解析はTTFを基本とし、従来OTFを選ぶLINE Seedは維持。
- ロックIDを可読化し、全設定ウェイトで未使用のPlex Thin/Medium、
  Zen Kaku Black/Mediumを除外。既存キャッシュと旧manifest読み取りを維持。
- mypyとPyYAML型定義をdev依存へ追加し、関数内部も含めたsrc型チェックをCIに追加。
  型注釈とimport配置を整理し、合成処理の挙動は変更しない。

- FontBakery 1.1.0をdev依存に固定し、universal（OpenTypeを含む）の生JSON・
  日本語理由付き許可リスト・WARN一覧を追加。G7で許可以外のFAILとERROR/FATALを検出。
- 品質検査で判明したPANOSE、整数PPEMフラグ、静的wght/ital STATを修正。
  上流由来の既知制限はチェックID＋メッセージコードの完全一致でのみ管理。
- 手動フルビルドCIに28対象のG7と検査レポートのartifact保存を追加。

全504対象・全アプリの検証までを保証するものではありません。
