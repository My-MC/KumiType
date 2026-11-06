# KumiType

Cascadiaと日本語フォントの合成ビルドシステム。開発中です。
固定ソース取得・単体/全対象ビルド・検証・ZIP生成に対応しています。
全504件・42ファミリーの実生成とHarfBuzz比較は成功しています。
全504件の初回バイナリ検証と42ファミリーのZIP生成は成功しています。
追加表示確認で見つかったM PLUSの半角カナ欠落を修正し、影響する144件の再生成・再検証も成功しました。
修正後12ZIPは更新済みです。使用ウェイト記録の訂正と全42ZIPの最終検査も成功しています。
Ubuntu以外の環境別検証とリモートCIの実行確認は未完了です。

Pythonと依存パッケージはuvで管理します。`.python-version`でPython 3.14.7、`uv.lock`で依存を固定しています。
uv未導入の場合は公式インストーラーで導入してください。

```sh
uv python install
uv sync --locked --extra dev
uv run --locked kumitype list
uv run --locked pytest
```

Fedoraでは `scripts/setup-fedora.sh`、AlmaLinux / Rocky / RHEL 10では
`scripts/setup-rhel.sh`、Debian / Ubuntuでは `scripts/setup-debian.sh` を使用できます。
RHEL系のHarfBuzz CLIは有効なリポジトリによって提供状況が異なります。

```sh
docker build -t kumitype-builder:local .
scripts/docker-build.sh kumitype list
KUMITYPE_UID=$(id -u) KUMITYPE_GID=$(id -g) docker compose run --rm builder kumitype list
```

ラッパーはSELinux有効時にボリュームへ `:z` を付加します。
Podmanでは `CONTAINER_RUNTIME=podman scripts/docker-build.sh kumitype list` を使用します。
コンテナ実行環境での動作は未検証です。

実装計画は [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) を参照してください。

標準の操作（取得以降のビルド処理はネットワークを使用しません）:

```sh
uv run --locked kumitype doctor
uv run --locked kumitype fetch
uv run --locked kumitype build --base mono-nf --jp plex --weight 400 --style normal
uv run --locked kumitype build-all --jobs 4
uv run --locked kumitype validate --all
uv run --locked kumitype package --all
```

設定は `config/build.yaml`、公式ソースのURL・固定バージョン・SHA-256は
`config/sources.lock.toml` にあります。生成物は `build/`、ZIPは `dist/` へ出力します。
日本語グリフは元のヒンティングを継承しません。IVSの継承は保証対象外です。
幅超過はJSONマニフェストへ記録します。3:5幅と日本語合成斜体は未実装です。

現在の受け入れ状況は [docs/ACCEPTANCE_STATUS.md](docs/ACCEPTANCE_STATUS.md) に記録します。
Fedora/RHEL/Debian/Ubuntu/DockerのフルビルドとGitHub Actionsの実行結果は未確認です。
生成できたことだけで配布品質を保証するものではありません。目視確認用サンプルと
既知の幅超過は [docs/VALIDATION.md](docs/VALIDATION.md) と
[docs/FONT_TUNING.md](docs/FONT_TUNING.md) を参照してください。

旧JPBlend/jpblendからKumiType/kumitypeへ改名しました。既存の生成TTF・ZIPは旧名の検証成果物であり、新名称では再ビルドが必要です。
