# KumiType

Cascadia Code / Monoと日本語フォントを合成し、コードエディター・ターミナル向けのフォントを生成するビルドシステムです。
通常版・Powerline版・Nerd Fonts版に対応し、ソースの固定版とSHA-256を使ったオフライン再ビルドができます。

[ドキュメント一覧](docs/README.md) · [プロジェクトREADME](README.md)

## 生成できるフォント

Cascadiaの種類を「ベース系列」、合成に使う日本語フォントを「日本語書体」、両者の組み合わせを「ファミリー」と呼びます。

| 構成 | 種類・生成数 |
| --- | --- |
| ベース系列 | 6種類：`code` / `code-pl` / `code-nf` / `mono` / `mono-pl` / `mono-nf` |
| 日本語書体 | 7種類：IBM Plex Sans JP / BIZ UDGothic / Noto Sans JP / LINE Seed JP / M PLUS 1 / M PLUS 2 / Zen Kaku Gothic New |
| ウェイト | 6種類：200 / 300 / 350 / 400 / 600 / 700 |
| スタイル | 2種類：Normal / Italic |
| 出力 | 6 × 7 × 6 × 2 = **504 TTF**、**42ファミリー・42 ZIP** |

## クイックスタート

Python **3.14以降**と依存パッケージは`uv`で管理します。固定版は`.python-version`（3.14.7）と`uv.lock`を参照してください。
OS別のツール導入は[ビルドガイド](docs/BUILDING.md#ツールのインストール)にまとめています。以下はリポジトリのルートで実行します。

1. Pythonと開発・検証用の依存を準備し、環境を診断します。取得前は`doctor`の`sources_ready`が`false`でも、次の取得手順へ進めます。

   ```sh
   uv python install
   uv sync --locked --extra dev
   uv run --locked kumitype doctor
   ```

2. 固定ソースを取得し、全504本を生成します。

   ```sh
   uv run --locked kumitype fetch
   uv run --locked kumitype build-all
   ```

3. 全数の欠落・整合性を検証し、ファミリー別ZIPを作成します。

   ```sh
   uv run --locked kumitype audit
   uv run --locked kumitype validate --all --require-harfbuzz
   uv run --locked kumitype package --all
   ```

生成TTFとレポートは`build/`、ZIPは`dist/`に保存します。HarfBuzz必須検証には`hb-shape`が必要です。
1ファミリー（既定12本）だけなら、次のように並列生成できます。

```sh
uv run --locked kumitype build --family mono-nf/biz --jobs auto
```

複数指定や対象限定の検証・ZIP作成は[ファミリーを指定してビルドする](docs/BUILDING.md#ファミリーを指定してビルドする)を参照してください。

> [!NOTE]
> 8コアVMでの全数実測は生成約26分、監査・検証・パッケージ化を含めて計約2時間16分です。ハードウェア、キャッシュ、並列数で変わります。

## ドキュメント案内

| 目的 | 文書 |
| --- | --- |
| 導入・生成・オフライン利用 | [ビルドガイド](docs/BUILDING.md) |
| 文字幅・スケール・ベースラインの調整 | [フォント調整](docs/FONT_TUNING.md) |
| HarfBuzz・パッケージ・ゴール判定 | [検証ガイド](docs/VALIDATION.md) |
| 固定ソースの取得・更新・手動登録 | [ソースフォント](docs/FONT_SOURCES.md) |
| MIT / OFL・再配布条件 | [ライセンス](docs/LICENSES.md) |
| タグ・候補版・draft公開・来歴証明 | [リリース手順](docs/RELEASING.md) |
| 設計・検証記録・初期仕様 | [ドキュメント一覧](docs/README.md) |

## 開発者向け

### テスト・静的検査

Pythonのテスト、Lint、型検査を実行します。

```sh
uv run --locked pytest -q
uv run --locked ruff check src tests scripts
uv run --locked mypy src
```

### ゴール判定（`G1`〜`G7`）

`scripts/check-goal.py`は項目別の`PASS` / `FAIL`と根拠を標準出力へJSONで返します。既定の生成対象は`code-nf` / `mono` × 日本語7書体 × Regular（400 Normal）/ Bold Italic（700 Italic）の28 TTFです。

| ゲート | 確認内容 |
| --- | --- |
| `G1` | テスト・Lint・型検査 |
| `G2` | 実フォントのメタデータ契約 |
| `G3` | 不正メタデータを注入した際の検出 |
| `G4` | 取り込み輪郭のセル幅超過 |
| `G5` | クリーン再生成したTTF・ZIPの再現性 |
| `G6` | 外部作業ディレクトリ・設定ロック・キャッシュのCLI契約 |
| `G7` | FontBakeryと既知FAIL許可リスト |

全ゲートを実行します（フォントの生成・再生成を伴い、時間がかかります）。

```sh
uv run --locked python scripts/check-goal.py --only G1,G2,G3,G4,G5,G6,G7
```

全数検証の記録は[検証状況](docs/ACCEPTANCE_STATUS.md)、ゲートの使い分けは[検証ガイド](docs/VALIDATION.md#改善ループの合格判定)を参照してください。
通常のCIはUbuntuランナーでPythonのテスト・Lint・型検査を実行します。手動フルビルド用のGitHub Actionsもありますが、ディストリビューション別コンテナやDockerの検証CIではありません。

## 既知の制約

- 日本語側の元ヒンティング・OpenType機能・IVSの完全継承は保証対象外です。
- 3:5幅と日本語合成斜体は未実装です。
- 輪郭のセル幅超過は既定で水平縮小します。設定で無効化した場合は超過が残り得ます。
- 旧JPBlend名のTTF・ZIPはKumiType名で再ビルドしてください。

検証範囲と配布時の注意は[検証状況と既知の制約](docs/ACCEPTANCE_STATUS.md)にまとめています。
