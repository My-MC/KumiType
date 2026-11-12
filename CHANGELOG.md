# Changelog

この文書では、KumiTypeの利用者・保守者に関係する追加・変更・修正・削除を確認できます。
[Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)に沿って整理し、未リリースの変更は `Unreleased` にまとめます。

[ドキュメント一覧](docs/README.md) · [プロジェクトREADME](README.md)

## [Unreleased]

`project.version` は現在 `0.1.0` です。
Cascadiaの6種類を「ベース系列」、日本語の7種類を「日本語書体」、両者の組み合わせを「ファミリー」と呼びます。

### 追加

- `validate`・`package`に共通の`--jobs N|auto`を追加し、TTF検証・ファミリーZIP生成をプロセス並列化しました。レポート順序とZIP再現性は維持します。
- `make release`と`scripts/release.py`で同じ対象選択のbuild→audit→HarfBuzz必須validate→package→check-packagesを実行し、工程別の経過時間・CPU時間・終了コードを`pipeline-timings.json`へ保存します。

- `build`・`list`・`validate`・`audit`・`package`で共通の`--base`・`--jp`・`--weight`・`--style`・`--family`による対象選択を追加しました。
  繰り返し・カンマ区切り、ファミリーの`base/jp`形式と出力名、次元同士の積集合に対応します。
- 選択対象の並列ビルド、ファミリー一覧と本数のJSON表示、対象限定の検証・完全性監査、全ウェイト・全スタイルが揃ったファミリーだけのZIP作成を追加しました。
- Makefileの`BASE`・`JP`・`FAMILY`・`WEIGHT`・`STYLE`と、手動ビルドCIの`families`・`bases`・`japanese_fonts`入力を追加しました。

- Cascadiaの通常・PL・NFを含む6ベース系列と日本語7書体について、固定ソース取得・SHA-256検証・オフライン登録・明示更新を追加しました。
- 元グリフID、既存輪郭、`GSUB` / `GPOS` を保持する静的TTF合成を追加しました。日本語輪郭のUPM正規化・中央配置・送り幅設定・ベースライン調整、半角カナの派生と倍率調整、文字ごとの収録元指定、分割ソースの補完に対応します。
- 独自ファミリー名、著作権・ライセンスメタデータの統合、追加ライセンスのハッシュ確認と同梱、検証マニフェスト、ファミリー別ZIPを追加しました。
- 全対象ビルド、対象の完全性監査、HarfBuzz比較、配布ZIP監査、HTMLプレビューと表示サンプルを追加しました。
- Docker・OS別セットアップ手順・GitHub Actions・利用者／開発者向けドキュメントを追加しました。
- [`G1`〜`G7` の根拠付きJSON判定](docs/VALIDATION.md#改善ループのゴール判定g1g7)を追加しました。既定28対象の不足分ビルド、`--only` / `--build-dir` / `--reuse`、欠落・設定差異・出力ハッシュ不一致の検出に対応します（[PR #1](https://github.com/My-MC/KumiType/pull/1)〜[PR #5](https://github.com/My-MC/KumiType/pull/5)）。
- `fit_overflow` / `fit_margin`、縮小済み文字の `merge.fitted_codepoints`、丸め後の `merge.overflow_codepoints` を追加しました（[PR #2](https://github.com/My-MC/KumiType/pull/2)）。
- `paths.cache` / `--cache-dir` によるインスタンス・輪郭キャッシュの移動と、外部作業ディレクトリからの実CLI検査を追加しました（[PR #3](https://github.com/My-MC/KumiType/pull/3)）。
- HTTPS取得に接続15秒・読み取り60秒の分離タイムアウト、アドレス別接続試行によるIPv4フォールバック、最大3回の指数バックオフ、標準エラーへのバイト進捗表示を追加しました。恒久的HTTPエラー・ハッシュ不一致は再試行しません（[PR #4](https://github.com/My-MC/KumiType/pull/4)）。
- mypyとPyYAML型スタブを開発依存へ追加し、関数内部も含む `src` の型検査をCIと `G1` に追加しました（[PR #4](https://github.com/My-MC/KumiType/pull/4)）。
- FontBakery **1.1.0** を開発依存に固定し、universal（OpenTypeを含みます）の検査、生JSON・ログ・入力／許可リストのSHA-256、WARN一覧を追加しました。`G7` は日本語理由付きの完全一致許可リスト外の `FAIL` と、すべての `ERROR` / `FATAL` を失敗にします。手動フルビルドCIにも28対象の検査とartifact保存を追加しました（[PR #5](https://github.com/My-MC/KumiType/pull/5)）。
- 追加結合文字の `merge.zero_width_mark_codepoints` と `GDEF` の `mark(3)` 登録を追加しました。validatorは追加分類だけを許容し、既存分類と他サブテーブルの変更を検出します。`G4` も送り幅 `0` と直前の基準セル領域を検査します（[PR #6](https://github.com/My-MC/KumiType/pull/6)）。

### 変更

- `build`の未指定次元を設定済みの全値に変更しました。
  **旧`build --base X --jp Y`は400 Normalの1本でしたが、現在は既定12本を並列生成します。**
  従来の1本だけなら`--weight 400 --style normal`を明示してください。
- `--all-weights`・`--all-styles`は非推奨とし、警告を出して無視します。
  `build-all`はセレクタなしの`build`と同等として残しています。
- ビルドレポートは今回の選択対象の結果と選択条件・対象数を記録し、他ファミリーの既存出力は保持します。
  `list --json`は対象配列だけでなく、`selectors`・`families`・`family_count`・`target_count`・`targets`を持つオブジェクトを返します。
- `validate`と`package`の`--all`必須を廃止しました。
  セレクタなしの全出力処理と既存の`--all`は引き続き使用できます。

- 対応環境をPython **3.14以降**に統一しました（[PR #1](https://github.com/My-MC/KumiType/pull/1)）。
- CIのRuff対象を `src tests scripts` に統一しました（[PR #1](https://github.com/My-MC/KumiType/pull/1)）。
- 全CLIの設定ロック `sources.lock` と入出力パスの解決を統一し、明示したCLI引数だけで設定値を上書きするようにしました。`doctor` のreadiness判定は、選択したフォントとライセンスに限定しました（[PR #3](https://github.com/My-MC/KumiType/pull/3)）。
- ZIPのエントリ順序・UTC日時・権限・圧縮を固定し、`SOURCE_DATE_EPOCH` に対応しました。同梱マニフェストから実行時刻・所要時間・ピークRSS・ローカル保存先を除外し、配布用の設定ハッシュをパス非依存に再計算します。入力・ライセンスのハッシュとビルド側の診断情報は保持します（[PR #3](https://github.com/My-MC/KumiType/pull/3)）。
- ソースマニフェストをv2にし、ロック全項目、展開済みファイル・ライセンス、フォント一覧と各ハッシュを照合するようにしました。一致する再取得ではネットワーク・展開・解析・マニフェスト書き換えを省略します。不正／不完全なJSONは再処理します。文字集合を `codepoint_ranges` に圧縮し、旧 `codepoints` の読み取り互換性は維持します（[PR #4](https://github.com/My-MC/KumiType/pull/4)）。
- ロックIDを `plex-bold` / `noto-variable` などの可読名に整理しました。解析は原則TTFに限定し、従来OTFを選ぶLINE Seedは明示設定で維持しました。全42ドナー選択の入力ハッシュと28サブセットTTFのハッシュが変更前後で一致しています（[PR #4](https://github.com/My-MC/KumiType/pull/4)）。
- 型注釈とimport配置を整理し、循環参照回避に必要な遅延importを除いてモジュール先頭へ移動しました（[PR #4](https://github.com/My-MC/KumiType/pull/4)）。
- 輪郭キャッシュの形式・キーを更新し、縮小設定や結合文字の配置方式が異なる古い輪郭の再利用を防止しました（[PR #2](https://github.com/My-MC/KumiType/pull/2)、[PR #6](https://github.com/My-MC/KumiType/pull/6)）。
- README・文書一覧・ビルド・ソース・ライセンス・設計・検証状況を、目的別見出し、表、番号付き手順、統一ナビゲーションで整理しました。初期仕様書は冒頭の注記と目次のみ整えました（[PR #7](https://github.com/My-MC/KumiType/pull/7)）。
- 検証ガイドを「目的 → コマンド → 結果の見方」に統一し、輪郭調整ガイドに設定キー表とセル配置図を追加しました。この変更履歴も分類別に整理しました。

### 修正

- Linuxの使用可能メモリを回収可能なページキャッシュを含む`MemAvailable`で見積もるようにし、cgroup v1/v2の現在グループ・祖先の上限も考慮します。既定のワーカー見積もりを実測最大RSS 464 MiBから余裕を持たせた768 MiBへ変更し、決定した並列数と根拠を標準エラーへ表示します。
- packageの完全再検証は、同じTTF SHA-256と現在のbuilder provenanceを持つ成功記録がある場合のみ省略します。記録なし・不一致は従来検証へ戻り、実際のZIP格納バイトもハッシュ照合します。手動フルビルドCIの並列数を`auto`に統一しました。

- 生成フォントから `DSIG` を除去し、JIS/Japanコードページbit 17、ベンダーID `NONE`、`project.version` 由来の `head.fontRevision` を設定しました。validatorで4種類の個別違反を検出し、16.16固定小数点の丸めとマニフェストに基づく再検証を統一しました（[PR #1](https://github.com/My-MC/KumiType/pull/1)）。
- セル幅を超える日本語取り込み輪郭を、既定で1セル・2セル内へ水平縮小するようにしました。Ambiguous・Neutral・半角カナにも適用し、最終二次曲線で判定します。縦座標・ベースライン・送り幅・Cascadia由来の輪郭・非超過輪郭は保持します（[PR #2](https://github.com/My-MC/KumiType/pull/2)）。
- 保存先が異なる場合のZIP非一致、入れ子の既存ソースパス解決、Dockerでのマウント先設定参照を修正しました。`KUMITYPE_CONFIG` と明示 `--config` の優先順位、配布用マニフェストとZIP監査を回帰テストで確認します（[PR #3](https://github.com/My-MC/KumiType/pull/3)）。
- HTTPSからHTTPへのリダイレクトを接続前に拒否するようにしました（[PR #4](https://github.com/My-MC/KumiType/pull/4)）。
- FontBakeryで判明したPANOSE、整数PPEM用 `head.flags` bit 3、静的フォントの `wght` / `ital` 値を持つ `STAT` を修正しました。`STAT` 生成時のMac用name追加も抑止しました（[PR #5](https://github.com/My-MC/KumiType/pull/5)）。
- 日本語ドナー由来の `Mn` / `Me` 結合文字をゼロ幅化し、EAW `W` / `F` なら直前2セル、それ以外なら直前1セルへ重ねるようにしました。縦座標と非マーク文字は保持し、日本語ドナーの `GPOS` アンカーは移植しません（[PR #6](https://github.com/My-MC/KumiType/pull/6)）。
- Roman側の静的 `STAT` の `ital=0` に `LinkedValue=1.0` を設定しました。28本のFontBakery検査で `wrong-ital-axis-linkedvalue` は0件です（[PR #6](https://github.com/My-MC/KumiType/pull/6)）。

### 削除

- Python 3.11のCIを削除しました（[PR #1](https://github.com/My-MC/KumiType/pull/1)）。
- 設定ウェイトで未使用のPlex Thin / MediumとZen Kaku Black / Mediumの4ロックレコードを除外しました。既存ソース・キャッシュ・ライセンスレコードは削除していません（[PR #4](https://github.com/My-MC/KumiType/pull/4)）。
- OSディストリビューション別のコンテナ検証CIを削除し、通常のPython CIと手動フルビルドCIに整理しました。OS別手順とDocker構成は残しています。

## 検証状況

PR #5の実装コミット `8ba5206dfad32d89f90499af92f6a01e2ebaeef6` では、全504 TTF・42 ZIPの検証、HarfBuzzの4536比較、全546成果物の2回生成時のSHA-256一致、全42ファミリーを覆う84本のFontBakery検査を完了し、`G1`〜`G7` はすべて `PASS` でした。
FontBakeryの既知の許可 `FAIL` とWARNは残っています。
PR #6では結合文字修正後の28本で `G1`〜`G7` とHarfBuzz検証を再確認していますが、全504本の再検証ではありません。

> [!NOTE]
> これらは対象コミット・入力・設定に対する記録です。
> GUI各アプリ、Windows / macOS実機、Dockerでの動作確認や、全アプリでの表示品質まで保証するものではありません。
> 根拠と範囲は[検証状況と既知の制約](docs/ACCEPTANCE_STATUS.md)、再実行手順は[検証ガイド](docs/VALIDATION.md)を参照してください。

[Unreleased]: https://github.com/My-MC/KumiType/compare/919e353...HEAD
