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
