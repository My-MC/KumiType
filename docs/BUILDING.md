# ビルドガイド

ツールの導入から、ソース取得・フォント生成・検証・ZIP作成までを説明します。保存先の変更、オフライン利用、任意のコンテナ実行も案内します。

[ドキュメント一覧](README.md) · [プロジェクトREADME](../README.md)

## ツールのインストール

Python **3.14以降**と依存パッケージは、システムのPythonではなく`uv`で管理します。OS別の案内はツール導入用であり、ディストリビューション別コンテナCIを前提としません。

| 環境 | セットアップスクリプト |
| --- | --- |
| Fedora | `scripts/setup-fedora.sh` |
| AlmaLinux / Rocky Linux / RHEL | `scripts/setup-rhel.sh` |
| Debian / Ubuntu | `scripts/setup-debian.sh` |

1. リポジトリのルートで、使用するOSのスクリプトを実行します。次はDebian / Ubuntuの例です。

   ```sh
   bash scripts/setup-debian.sh
   ```

   各スクリプトはシステムツールを導入し、`uv`でPythonと依存環境を準備します。システムツールの導入には`sudo`権限が必要です。RHEL系のHarfBuzz CLIは、有効なリポジトリによって提供状況が異なります。未導入でも合成はできますが、HarfBuzz必須検証には`hb-shape`が必要です。

2. `uv`が導入済みでPython環境だけを準備する場合は、固定版をインストールして診断します。

   ```sh
   uv python install
   uv sync --locked --extra dev
   uv run --locked kumitype doctor
   ```

   Pythonの固定版は`.python-version`、依存版は`uv.lock`にあります。ソース取得前は`doctor`の`sources_ready`が`false`でも、次の取得手順へ進めます。

## フォントの取得と生成

ベース系列・日本語書体・ファミリーの用語は[プロジェクトREADME](../README.md#生成できるフォント)に従います。

1. 固定版とSHA-256を持つソースを取得します。

   ```sh
   uv run --locked kumitype fetch
   ```

2. 少数から試す場合は、1本または1ファミリーの全ウェイト・全スタイルを生成します。次の2つは選択肢です。

   ```sh
   uv run --locked kumitype build --base mono-nf --jp plex --weight 400 --style normal
   uv run --locked kumitype build --family code-nf/noto --jobs auto
   ```

3. 全504本が必要な場合は、CPUとメモリに合わせた並列数で一括生成します。

   ```sh
   uv run --locked kumitype build-all --jobs auto
   ```

生成対象と変換設定は`config/build.yaml`、ソースのURL・固定版・SHA-256は`config/sources.lock.toml`にあります。既定の生成先は`build/`です。

### 並列数の決まり方

`build` / `build-all` / `validate` / `package`は共通の`--jobs N|auto`を使用します。
未指定時は`build.jobs`（既定`auto`）に従います。`auto`はCPU数を希望値とし、
明示した`N`もCPU・メモリ・設定上限のすべてで制限します。
実際のワーカー数は次の最小値（最低1）です。

- 希望値（`auto`なら論理CPU数）
- 論理CPU数
- `floor(使用可能メモリ × 0.8 / (build.worker_memory_mb × 1024²))`
- `build.max_jobs`（設定した場合）

Linuxでは`/proc/meminfo`の`MemAvailable`を使用します。ページキャッシュは回収可能なので、
`MemFree`や空き物理ページ数だけで見積もらず、`drop_caches`の実行も不要です。
取得不能・不正値の場合だけ`SC_AVPHYS_PAGES × SC_PAGE_SIZE`にフォールバックします。
cgroup v1/v2では現在のグループと祖先の`limit − usage`でも上限を掛けます。
cgroup内のページキャッシュは安全側にusageへ含めるため、制約の厳しいコンテナでは並列数が下がる場合があります。
取得情報が全くない場合は2 GiBとして計算します。

ワーカーあたりの既定見積もりは**768 MiB**です。504本の実測ピークRSSの中央値424 MiB・
最大464 MiBに余裕を持たせ、さらに上記の80%制限を併用しています。
将来ソースフォントが大きくなった場合やOOMが起きる環境では値を増やしてください。

```yaml
build:
  jobs: auto
  worker_memory_mb: 768
  max_jobs: 8  # 任意。省略すると設定による上限なし
```

`--jobs 1`で逐次実行、`--jobs 6`で最大6並列などを指定できます。
標準エラーに`workers`・`requested`・`cpus`・`available_memory_mib`・`memory_limit`・
`worker_memory_mb`・`max_jobs`を表示するため、明示値が減らされた理由も確認できます。
標準出力のJSON形式は変更しません。
`validate`はTTF単位、`package`はファミリー単位のプロセス並列です。
検証結果・重複PostScript名の判定は入力順に集約し、ZIPのエントリ順・日時・権限・圧縮設定は固定します。

### 一括実行と時間計測

```sh
make release JOBS=auto
make release FAMILY=mono-nf/biz JOBS=4 BUILD_DIR=build-biz DIST_DIR=dist-biz
# 設定ファイルと出力先も明示できる同等のスクリプト
uv run --locked python scripts/release.py --config config/build.yaml --jobs auto
```

build → audit → HarfBuzz必須validate → package → check-packagesを実行します。
`BASE`・`JP`・`FAMILY`は全工程で同じ選択範囲を使用します。完全ファミリーが必要なため、
`WEIGHT`・`STYLE`による部分リリースは開始前にエラーにします。
各工程のコマンド・終了コード・経過秒を`build/pipeline-timings.json`に保存し、
標準出力・標準エラーは`build/pipeline-<工程>.stdout.log` / `.stderr.log`へ保存します。
`BUILD_DIR`を変更した場合はその配下です。失敗した工程で停止し、そこまでの計測も残します。
既存出力を削除しないので、部分リリースの監査には選択対象だけを含む専用のbuild/distを推奨します。

packageでは、TTFの実バイトのSHA-256がマニフェストと一致し、保存済み`validation`が成功・errors空、
`builder`が現在の実装SHA-256・Python版・依存版と完全一致する場合だけ完全再検証を省略します。
名前・ファミリー・ウェイトの軽量チェックと、実際にZIPへ入れるバイトのSHA-256確認は常に行います。
記録欠落・不正・provenance不一致は従来の`validate()`へ戻り、TTFハッシュ不一致でも完全再検証を実行しますが、成功しても不一致自体は救済せず拒否します。
再利用時はビルド時のベース比較結果を信頼し、ソースフォントの再検証やHarfBuzzの再実行はしません。
HarfBuzz必須の配布前確認は前段の`validate --require-harfbuzz`が担います。
マニフェストはローカルの信頼済みビルド記録であり、第三者がTTFと記録を同時に改ざんできる状況への署名検証ではありません。


## ファミリーを指定してビルドする

`build`・`list`・`validate`・`audit`・`package`は同じ対象選択オプションを使います。
省略した次元は設定済みの全値を選択し、指定した次元同士は積集合で絞り込みます。
同じオプションの繰り返しとカンマ区切りは、どちらも複数値の指定です。

| オプション | 値と例 |
| --- | --- |
| `--family` | `mono-nf/biz`、または出力名 `"KumiType BIZ Mono NF"`。大文字小文字・空白・ハイフンの差を許容します。 |
| `--base` | `code,mono`、または `--base code --base mono`。 |
| `--jp` | `config/fonts.yaml`のID（例：`biz,plex`）。 |
| `--weight` | `400,700`など、`config/build.yaml`にあるウェイト。 |
| `--style` | `normal,italic`など、設定済みのスタイル。 |

未知値や積集合が0件となる指定は、選択可能な値を示して失敗します。
`--family mono-nf/biz --base code`は0件です。
選択オプションは設定自体を書き換えません。
`build`は`--jobs`、メモリ上限、`build.fail_on_error`を使い、選択範囲を並列生成します。
他ファミリーの既存出力は削除しません。
`build-report.json`と`build-report.md`は今回の結果で置き換え、選択条件と対象数を記録します。

1. `list`で1ファミリー・12本になることを確認します。

   ```sh
   uv run --locked kumitype list --family mono-nf/biz
   uv run --locked kumitype list --family "KumiType BIZ Mono NF" --json
   ```

   JSONは`selectors`・`family_count`・`target_count`・`families`・`targets`を持つオブジェクトです。

2. 同じファミリーを生成し、完全性監査・HarfBuzz必須検証・ZIP作成まで実行します。

   ```sh
   uv run --locked kumitype build --family mono-nf/biz --jobs auto
   uv run --locked kumitype audit --family mono-nf/biz
   uv run --locked kumitype validate --family mono-nf/biz --require-harfbuzz
   uv run --locked kumitype package --family mono-nf/biz
   ```

3. 必要に応じて複数ファミリー、日本語書体だけ、ウェイトを指定します。
   次の各行は独立した選択例です。

   ```sh
   uv run --locked kumitype build --family mono-nf/biz,code/plex --jobs auto
   uv run --locked kumitype build --family mono-nf/biz --family mono/plex --jobs auto
   uv run --locked kumitype build --jp biz --jobs auto
   uv run --locked kumitype list --base code,mono --jp plex,noto --weight 400,700 --json
   uv run --locked kumitype build --base code,mono --jp plex,noto --weight 400,700 --jobs auto
   uv run --locked kumitype validate --base code,mono --jp plex,noto --weight 400,700 --require-harfbuzz
   uv run --locked kumitype audit --base code,mono --jp plex,noto --weight 400,700
   ```

`package`はファミリー単位です。
そのファミリーの設定済み全ウェイト・全スタイル（既定12本）のTTFとマニフェストが必要で、不足時は不足一覧を表示します。
`--weight`・`--style`を使う部分パッケージはエラーになります。
設定自体がウェイト・スタイルを絞っている場合は、その設定の全数が必要です。
`validate`はセレクタなし、または`--all`で既存全出力を検証します。
`--all`とセレクタを併用した場合はセレクタで絞り込みます。
`audit`はセレクタなしの場合だけ設定全体の完全性を判定します。
`build-all`はセレクタなしの`build`と同等です。
旧`build --base X --jp Y`は400 Normalの1本でしたが、現在は既定12本を生成します。
1本だけなら`--weight 400 --style normal`を明示してください。
旧`--all-weights`・`--all-styles`は非推奨で、警告を出して無視します。

手動GitHub Actionsの`Full font build`でも、`families`・`bases`・`japanese_fonts`に同じカンマ区切り値を指定できます。
全欄が空なら全数、指定時はその積集合だけを生成・監査・検証・パッケージ化します。
部分実行のFontBakery検査も生成済みファミリーだけを対象にし、全体監査用`check-goal.py`の対象は変更しません。

## 検証とパッケージ化

全504本の生成後に、完全性監査・HarfBuzz必須検証・ファミリー別ZIP作成を順に実行します。

```sh
uv run --locked kumitype audit
uv run --locked kumitype validate --all --require-harfbuzz
uv run --locked kumitype package --all
```

ZIPは`dist/`に保存します。
配布用マニフェストとその`config_sha256`からは、実行時の`build.jobs`・
`build.worker_memory_mb`・`build.max_jobs`・`build.fail_on_error`を除外します。
これらの値の追加・削除・変更や並列度を変えた再ビルドでも、フォント内容・実装・入力が同じならZIPは一致します。
`build.output_format`など内容に関わる設定と未知の将来設定は保持し、元のbuildマニフェストには実行設定も残します。
少数ビルドでは`audit`にも同じセレクタを渡してください。
表示確認・ZIP監査・ゴール判定の詳細は[検証ガイド](VALIDATION.md)を参照してください。

別の生成先を使う場合は、`build-all`の`--output-dir`と、検証・パッケージ化の`--build-dir`に同じパスを指定します。`package`の`--output-dir`はZIPの保存先です。

> [!NOTE]
> 8 vCPU / 約15 GiB VMの全504本実測（変換キャッシュ保持、`drop_caches`なし）は、`auto`＝8並列で **21分30秒**です。build 12分56秒、audit 2秒、HarfBuzz必須validate 7分23秒、package 32秒、check-packages 38秒でした。`jobs=7`・`worker_memory_mb=640`・`max_jobs=7`・`fail_on_error=false`で空の出力先へ再生成しても、TTF 504本・ZIP 42個のSHA-256は全一致し、総時間は24分33秒でした。入力・ホスト負荷・キャッシュで変わるため保証値ではありません。

## 設定・パス・キャッシュ

### ロックと保存先

全コマンドは`--config`で選んだ設定の`sources.lock`を使用します。`--lock`を明示した場合だけ上書きします。取得・登録・更新・診断・生成・検証・パッケージ化で同じロックを参照できます。

次は設定内の既定の保存先です。

```yaml
sources:
  lock: config/sources.lock.toml
  cascadia:
    version: "2407.24"
paths:
  source: source
  cache: cache
  build: build
  dist: dist
```

相対パスは設定ファイルのディレクトリを基準にします。ただし`config/`内の通常構成では、その親をプロジェクトルートとします。実行時の作業ディレクトリには依存しません。

| パスの種類 | 解決方法 |
| --- | --- |
| 設定の保存先、`subset_files` / `subset_licenses` | 設定から決まるプロジェクトルートを基準にします。 |
| CLIの`--lock` / `--source-dir` / `--cache-dir` / `--output-dir` / `--build-dir`、`import-source --file` | 相対指定は同じプロジェクトルートを基準にします。 |
| 絶対パス | そのまま使用します。 |

### キャッシュ

全サブコマンドは`--cache-dir`を受け付けます。取得物はその直下、静的インスタンスは`instances/`、変換済み輪郭は`outlines/`に保存します。検査系コマンドはこの指定でキャッシュを書き込みません。

`doctor`の`sources_ready`は選択した対象に必要なCascadia・日本語ドナー・ライセンスだけで判定します。未選択のソースは`sources`に情報として残り、`required: false`と表示します。必須フォントの欠落・改変、テキストライセンスのハッシュ不一致は失敗扱いです。

### リポジトリ外からの実行

依存とソースの準備後、絶対パスで設定を指定すれば、別の作業ディレクトリから生成・検証・パッケージ化できます。次の`/path/to/KumiType`は実際の配置先に置き換えてください。

```sh
/path/to/KumiType/.venv/bin/kumitype --config /path/to/KumiType/config/build.yaml build --base mono --jp biz --cache-dir cache-custom
/path/to/KumiType/.venv/bin/kumitype --config /path/to/KumiType/config/build.yaml validate --all
/path/to/KumiType/.venv/bin/kumitype --config /path/to/KumiType/config/build.yaml package --all
```

## 再現可能なZIP

同じ入力・設定・依存・実装なら、プロジェクトの配置先やソース・キャッシュの保存先を変えてもTTFとZIPのSHA-256を再現できます。異なる依存版をまたぐ一致は保証しません。

| 項目 | 規則 |
| --- | --- |
| エントリ | 名前順、Unix通常ファイル`0644`、固定の圧縮レベルです。入力の更新日時・権限は取り込みません。 |
| 日時 | 既定は1980-01-01 00:00:00 UTCです。`SOURCE_DATE_EPOCH`を整数秒で指定するとUTCで反映します。 |
| 日時の丸め | ZIPの範囲（1980〜2107年）外は端に丸め、秒は2秒単位で切り捨てます。不正な値はエラーです。 |
| 配布JSON | 実測値とローカル保存先を除き、キー順を固定します。 |

ZIP内のマニフェストと`sources/*.json`では、`generated_at`、`duration_seconds`、`process_peak_rss_kib`、ローカル保存先（`path`、`paths`、`sources.lock`、`subset_files`、`subset_licenses`）、内部キー`_project_root`を除外します。

`config_sha256`は配布用設定から再計算します。ソース・追加ライセンスのSHA-256、URL、固定版、実装・依存の識別子は保持します。ビルド出力側のJSONは、元のパス・設定ハッシュ・実測値を保持します。

## オフライン利用

1. 接続可能な環境でPython・依存・固定ソースを準備します。

   ```sh
   uv python install
   uv sync --locked --extra dev
   uv run --locked kumitype fetch
   ```

2. 準備済みの環境をオフラインで再利用し、一括生成します。

   ```sh
   uv sync --locked --extra dev --offline
   uv run --locked --offline kumitype build-all
   ```

`source/`と`cache/`を保持すれば再ダウンロードは不要です。

## Docker / Compose / Podmanで手動実行

Dockerは任意のローカル実行方法です。CIの動作確認対象にはしていません。コンテナの`KUMITYPE_CONFIG=/work/config/build.yaml`により、マウントしたプロジェクトの設定を参照します。明示的な`--config`はこの環境変数より優先します。

1. ローカル用のビルダーイメージを作成します。

   ```sh
   docker build -t kumitype-builder:local .
   ```

2. ラッパーで一括生成するか、Composeで環境を診断します。次の2つは用途別の例です。

   ```sh
   scripts/docker-build.sh kumitype build-all
   KUMITYPE_UID=$(id -u) KUMITYPE_GID=$(id -g) docker compose run --rm builder kumitype doctor
   ```

ラッパーはホストのUID / GIDを引き継ぎ、SELinux有効時に`:z`を付けます。Podmanを使う場合はランタイムを指定して生成します。

```sh
CONTAINER_RUNTIME=podman scripts/docker-build.sh kumitype build-all
```

## Makefile

同じ生成・完全性監査とHarfBuzz必須検証・パッケージ化を`make`経由で順に実行できます。

```sh
make fonts JOBS=4
make verify HARFBUZZ=hb-shape
make package
```

`BUILD_DIR`と`DIST_DIR`で保存先を指定できます。`verify`は完全性監査に成功した後、HarfBuzz必須検証を実行します。

`BASE`・`JP`・`FAMILY`・`WEIGHT`・`STYLE`は`fonts`・`audit`・`validate`・`package`へ同じセレクタを渡します。
`package`では`WEIGHT`・`STYLE`は使えません。

```sh
make fonts BASE=mono-nf JP=biz,plex JOBS=auto
make fonts FAMILY="KumiType BIZ Mono NF"
make verify FAMILY=mono-nf/biz
make package FAMILY=mono-nf/biz
```
