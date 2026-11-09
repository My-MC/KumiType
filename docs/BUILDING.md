# ビルドガイド

[ドキュメント一覧](README.md) · [プロジェクトREADME](../README.md)

## ツールのインストール

OSの選択肢は、ビルドに必要なツールを導入するための案内です。
ディストリビューションごとのコンテナCIを前提としません。
PythonとPythonパッケージは、システムのPythonではなくuvで管理します。

| 環境 | セットアップスクリプト |
| --- | --- |
| Fedora | `bash scripts/setup-fedora.sh` |
| AlmaLinux / Rocky Linux / RHEL | `bash scripts/setup-rhel.sh` |
| Debian / Ubuntu | `bash scripts/setup-debian.sh` |

各スクリプトはシステムツールを導入し、uvでPythonと依存環境を準備します。
システムツールの導入にはsudo権限が必要です。RHEL系のHarfBuzz CLIは
有効なリポジトリによって提供状況が異なります。未導入でも合成は実行できます。

uvが導入済みの場合、Python環境だけを準備するには次を実行します。

```sh
uv python install
uv sync --locked --extra dev
uv run --locked kumitype doctor
```

Pythonの版は`.python-version`、依存バージョンは`uv.lock`で固定しています。

## フォントの取得と生成

```sh
uv run --locked kumitype fetch
uv run --locked kumitype build --base mono-nf --jp plex --weight 400 --style normal
uv run --locked kumitype build --base code-nf --jp noto --all-weights --all-styles
uv run --locked kumitype build-all --jobs 4
```

生成対象と変換設定は`config/build.yaml`、ソースのURL・固定版・SHA-256は
`config/sources.lock.toml`にあります。既定の生成先は`build/`です。
並列数autoはCPUと使用可能メモリに基づき制限されます。
`build.worker_memory_mb`と`build.max_jobs`で上限を調整できます。

## 検証とパッケージ化

```sh
uv run --locked kumitype audit
uv run --locked kumitype validate --all
uv run --locked kumitype package --all
```

ZIPは`dist/`に保存します。HarfBuzz必須の検証や表示確認は[検証ガイド](VALIDATION.md)を参照してください。
別の生成先を使う場合は、build-allの`--output-dir`と、検証・パッケージ化の
`--build-dir`に同じパスを指定します。

## 設定・パス・キャッシュ

全コマンドが `--config` の `sources.lock` を使用します。`--lock` を明示した
場合だけ上書きし、`fetch`・`import-source`・`update-source`・`doctor`・
`build` / `build-all`・`package` で同じロックを参照します。

設定で入出力先とキャッシュを指定できます（以下は既定値）。

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

相対パスは設定ファイルのディレクトリが基準です。ただし `config/` 内に設定を
置く通常構成では、その親をプロジェクトルートとします。CLIで明示した相対パス
（`--lock`、`--source-dir`、`--cache-dir`、`--output-dir`、`--build-dir`、
`import-source --file`）や `subset_files` / `subset_licenses` も同じ基準で解決します。
絶対パスはそのまま使います。実行時のcwdには依存しません。

全コマンドで `--cache-dir` を受け付けます。取得物はその直下、静的インスタンスは
`instances/`、変換済み輪郭は `outlines/` に保存します。検査系コマンドはこの指定で
キャッシュを書き込みません。

リポジトリ外から実行する例（先に `uv sync` を実行済みの場合）:

```sh
/path/to/KumiType/.venv/bin/kumitype --config /path/to/KumiType/config/build.yaml build --base mono --jp biz --cache-dir cache-custom
/path/to/KumiType/.venv/bin/kumitype --config /path/to/KumiType/config/build.yaml validate --all
/path/to/KumiType/.venv/bin/kumitype --config /path/to/KumiType/config/build.yaml package --all
```

`doctor` の `sources_ready` は選択した対象に必要なCascadia・日本語ドナー・ライセンス
のみで判定します。未選択のソースは `sources` に情報として残し、`required: false` と
表示します。必須フォントの欠落・改変、テキストライセンスのハッシュ不一致は失敗扱いです。

## 再現可能なZIP

同じ入力・設定・依存・実装と同じパス構成で、TTFとZIPのSHA-256を再現できます。
ZIPはエントリ名順、Unix通常ファイル `0644`、固定の圧縮レベルで作成し、入力の
mtime・権限を取り込みません。日時は既定で1980-01-01 00:00:00 UTCです。
`SOURCE_DATE_EPOCH` を整数秒で指定するとUTCで反映します。ZIPの表現範囲
（1980〜2107年）外は端に丸め、秒は2秒単位で切り捨てます。不正な値はエラーです。

ZIP内のマニフェストでは `generated_at`、`duration_seconds`、
`process_peak_rss_kib` を除外し、キー順を固定します。ビルド出力側のJSONは実測値を
保持します。入力パスや実装・依存の識別子は追跡用に残すため、異なる配置や依存版を
またぐZIP一致まで保証するものではありません。

## オフライン利用

接続可能な環境で、Python・依存・フォントソースを準備してください。

```sh
uv python install
uv sync --locked --extra dev
uv run --locked kumitype fetch
uv sync --locked --extra dev --offline
uv run --locked --offline kumitype build-all
```

`source/`と`cache/`を保持すれば再ダウンロードは不要です。

## Docker / Compose / Podmanで手動実行

Dockerは任意のローカル実行方法です。CIの動作確認対象にはしていません。

```sh
docker build -t kumitype-builder:local .
scripts/docker-build.sh kumitype build-all
KUMITYPE_UID=$(id -u) KUMITYPE_GID=$(id -g) docker compose run --rm builder kumitype doctor
```

ラッパーはホストのUID/GIDを引き継ぎ、SELinux有効時に`:z`を付けます。
Podmanを使う場合は`CONTAINER_RUNTIME=podman scripts/docker-build.sh kumitype build-all`とします。

## Makefile

```sh
make fonts JOBS=4
make verify HARFBUZZ=hb-shape
make package
```

`BUILD_DIR`・`DIST_DIR`で保存先を指定できます。verifyは完全性監査に成功した後、
HarfBuzz必須の検証を実行します。
