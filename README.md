# KumiType

Cascadia Code / Monoと日本語フォントを合成するビルドシステムです。
通常・Powerline・Nerd Fonts対応の6系列と日本語7書体を組み合わせ、
6ウェイト・Normal / Italicの計504 TTF、42ファミリーを生成します。

## はじめに

Pythonと依存パッケージはuvで管理します。Pythonの既定は3.14.7です。
OS別のツール導入は[ビルドガイド](docs/BUILDING.md#ツールのインストール)を参照してください。

```sh
uv python install
uv sync --locked --extra dev
uv run --locked kumitype doctor
uv run --locked kumitype fetch
uv run --locked kumitype build-all
uv run --locked kumitype validate --all
uv run --locked kumitype package --all
```

生成TTFとレポートは`build/`、ファミリー別ZIPは`dist/`に保存します。
ソースは固定バージョンとSHA-256で管理し、取得後はオフラインで再ビルドできます。

## ドキュメント

- [ビルドガイド](docs/BUILDING.md)：ツール導入、単体・一括ビルド、Docker、オフライン利用
- [設定と見た目の調整](docs/FONT_TUNING.md)：文字幅、スケール、ベースライン
- [検証ガイド](docs/VALIDATION.md)：整合性・合字・表示サンプルの確認
- [ソースフォント](docs/FONT_SOURCES.md)：配布元、固定版、更新・手動登録
- [ライセンス](docs/LICENSES.md)：本体MITとフォントOFLの扱い
- [ドキュメント一覧](docs/README.md)：設計資料、検証状況、開発履歴

## 開発

```sh
uv run --locked pytest
uv run --locked ruff check src tests scripts
```

CIはGitHubのUbuntuランナー上でPythonのテストとLintを行います。
ディストリビューション別コンテナおよびDockerによる動作確認はCIで実行しません。
手動フルビルド用のGitHub Actionsも用意しています。

## 現在の制約

日本語グリフの元ヒンティングとIVSの完全継承は保証対象外です。
3:5幅と日本語合成斜体は未実装で、輪郭のセル幅超過はレポートに記録します。
検証状況は[検証状況](docs/ACCEPTANCE_STATUS.md)にまとめています。

旧JPBlend名で生成したTTF・ZIPは、KumiType名で再ビルドしてください。
