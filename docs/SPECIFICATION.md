# 初期仕様書について

開発開始時点の設計意図と要件を記録した文書です。本文は当時の仕様として保存しており、現行の利用手順や検証状況とは異なる箇所があります。

[ドキュメント一覧](README.md) · [プロジェクトREADME](../README.md)

> [!NOTE]
> 現行のプロジェクト名はKumiType、Pythonは3.14以降を`uv`で管理します。導入・生成は[ビルドガイド](BUILDING.md)、最新の結果は[検証状況](ACCEPTANCE_STATUS.md)を参照してください。OS別の案内はツール導入手順であり、ディストリビューション別コンテナの検証CIは実施しません。

## 初期仕様の目次

- [1. プロジェクト概要](#1-プロジェクト概要)
- [2. フォントの生成対象](#2-フォントの生成対象)
- [3. 開発技術](#3-開発技術)
- [4. フォント合成の仕様](#4-フォント合成の仕様)
- [5. ファミリー名・メタデータ](#5-ファミリー名メタデータ)
- [6. ビルド設定](#6-ビルド設定)
- [7. ソースフォントの取得](#7-ソースフォントの取得)
- [8. CLI仕様](#8-cli仕様)
- [9. OS別ビルド環境](#9-os別ビルド環境)
- [10. Docker対応](#10-docker対応)
- [11. ディレクトリ構成](#11-ディレクトリ構成)
- [12. ビルド成果物](#12-ビルド成果物)
- [13. 検証・テスト](#13-検証テスト)
- [14. 自動テスト・CI](#14-自動テストci)
- [15. ライセンス対応](#15-ライセンス対応)
- [16. パフォーマンス](#16-パフォーマンス)
- [17. 開発手順](#17-開発手順)
- [18. 受け入れ条件](#18-受け入れ条件)
- [19. Codexへの実装指示](#19-codexへの実装指示)

---

# Cascadia Code / Mono 日本語合成フォント ビルドシステム開発仕様書

**文書バージョン：** 1.0  
**作成日：** 2026年11月5日  
**開発言語：** Python 3.14以降  
**対象環境：** Fedora / RHEL系 / Debian系 / Docker  
**実装担当：** Codex

---

## 1. プロジェクト概要

### 1.1 目的

Microsoftが公開しているCascadia CodeおよびCascadia Monoをベースとして、複数の日本語フォントを合成し、日本語表示に対応したプログラミング用フォントを自動生成するシステムを開発する。

生成するフォントは以下の2用途を想定する。

- **ターミナル用途**：Cascadia Monoをベースとして、合字を使用せず、文字幅とNerd Fontsの互換性を重視する。
- **コードエディター用途**：Cascadia Codeをベースとして、プログラミング合字やOpenTypeのスタイル機能を維持する。

両者とも通常版・Powerline対応版・Nerd Fonts対応版を生成する。

特定のLinuxディストリビューションに依存しない構成とし、ネイティブ実行とDocker実行で同じビルドロジックを利用する。

### 1.2 基本方針

1. Cascadiaの既存グリフおよびOpenType機能を可能な限り維持する。
2. 日本語文字に対して、選択した日本語フォントのグリフを追加する。
3. 元のフォントのライセンスと著作権表示を維持する。
4. ビルドの再現性、検証可能性、保守性を重視する。
5. すべての組み合わせを設定ファイルから自動生成できるようにする。
6. ビルド処理は非対話的に実行可能とする。
7. フォントの取得とビルド処理を分離し、オフラインビルドに対応する。

## 2. フォントの生成対象

### 2.1 Cascadiaベースフォント

以下の6系列をサポートする。

| ID | ベース | 合字 | Powerline | Nerd Fonts |
|---|---|---|---|---|
| code | Cascadia Code | 有効 | 無効 | 無効 |
| code-pl | Cascadia Code PL | 有効 | 有効 | 無効 |
| code-nf | Cascadia Code NF | 有効 | 有効 | 有効 |
| mono | Cascadia Mono | 無効 | 無効 | 無効 |
| mono-pl | Cascadia Mono PL | 無効 | 有効 | 無効 |
| mono-nf | Cascadia Mono NF | 無効 | 有効 | 有効 |

公式のCascadia Code / Mono NFを直接使用する。

Nerd Fontsのパッチャーによる二重の追加処理は行わない。

元のCascadiaが持つ `calt`、`ss01` 等の機能を維持する。

### 2.2 日本語フォント

以下の7種類に対応する。

| ID | フォント |
|---|---|
| plex | IBM Plex Sans JP |
| biz | BIZ UDGothic |
| noto | Noto Sans JP |
| line-seed | LINE Seed JP |
| mplus1 | M PLUS 1 |
| mplus2 | M PLUS 2 |
| zen-kaku | Zen Kaku Gothic New |

各フォントは独立したファミリーとして生成する。

将来的に日本語フォントの追加・削除ができるようにする。

### 2.3 ウェイト

Cascadiaの次の6ウェイトに対応する。

| スタイル | Weight |
|---|---:|
| ExtraLight | 200 |
| Light | 300 |
| SemiLight | 350 |
| Regular | 400 |
| SemiBold | 600 |
| Bold | 700 |

各ウェイトについてNormalとItalicを生成する。

ただし、日本語フォント側が対応していないウェイトについては、次の優先順位で処理する。

1. 対応する静的ウェイトを使用
2. 可変フォントから指定ウェイトを生成
3. 最も近い既存ウェイトを使用

3の場合はログとビルドレポートに記録する。

自動的な疑似Bold処理や輪郭の膨張は標準では行わない。

Italicについて、日本語フォントにItalicが存在しない場合は、標準では日本語グリフを直立させたまま使用する。

オプションとして日本語の合成斜体に対応できる設計とする。

### 2.4 生成数

すべての組み合わせを生成する。

- Cascadia：6系列
- 日本語フォント：7系列
- ウェイト：6種類
- スタイル：Normal / Italic

**合計：504個の静的TTFファイル、42ファミリー。**

ただし、入力フォントの技術的制約などで生成できない組み合わせがある場合は、黙って省略せず、明確なエラーと診断レポートを出力する。

## 3. 開発技術

### 3.1 必須技術

- Python 3.14以降
- fontTools
- pytest
- Ruff
- YAML設定ファイル処理ライブラリ

### 3.2 検証用ツール

- HarfBuzz
- Fontconfig
- FontBakery（詳細品質検証用、オプション）
- FontForge（手動検査・補助処理用、オプション）

通常のフォント合成処理はPythonとfontToolsを中心に実装する。

FontForgeを実行することを必須条件にしない。

### 3.3 ビルド方式

Cascadia側のTTFをベースにして、日本語フォントから必要なグリフを取り込む。

Cascadia側の元のグリフ・Unicodeマッピング・OpenType機能を保護する。

日本語フォントがCFF形式のアウトラインを使用している場合には、fontToolsのCu2QuPen等を利用してTrueType形式に変換する。

利用するフォントが可変フォントの場合、まず対象ウェイトの静的インスタンスを生成する。

最終出力は静的TTFとする。

可変フォント形式での合成出力は本仕様の初期対象外とする。

## 4. フォント合成の仕様

### 4.1 グリフの優先順位

Unicodeコードポイントが重複した場合は、以下の優先順位に従う。

**Cascadia優先**

- ASCII英数字
- プログラミング記号
- 既存の欧文記号
- Powerline記号
- Nerd Fontsアイコン
- OpenType合字に使用されるグリフ

**日本語フォント優先**

- ひらがな
- カタカナ
- 漢字
- 全角英数字
- 日本語句読点
- 日本語の括弧類
- 全角スペース
- 日本語関連の補助文字

UnicodeのEast Asian Widthおよび明示的な日本語文字範囲を利用して判定する。

ただし、East Asian Widthだけでグリフの置換を決定してはならない。

Ambiguous文字幅の文字や既存Cascadiaのグリフと重複する文字については、設定ファイルで個別に優先順位を指定できるようにする。

Nerd FontsとPowerlineのPrivate Use Areaについては、Cascadia側のグリフを保護する。

### 4.2 日本語文字幅

標準では以下の幅を使用する。

- ASCIIなどの半角文字：1セル
- 漢字・ひらがな・全角カタカナ：2セル
- 全角スペース：2セル

全角文字のadvance widthを半角文字の2倍に設定する。

グリフの輪郭を文字幅内で中央揃えする。

日本語グリフの実際の輪郭は、設定されたスケール係数に従って変換する。

既存Cascadiaの半角文字幅は原則変更しない。

ターミナル表示において、半角と全角が正確に整列することを重要な受け入れ条件とする。

### 4.3 オプションの文字幅

将来的なエディター向けバリエーションとして、次の幅比率を設定できるようにする。

- 1:2（標準）
- 3:5（オプション）

3:5版では、半角文字と全角文字の文字送り幅を一貫して調整する必要がある。

単に日本語のadvance widthを変更するだけの実装は禁止する。

3:5版は標準の504ファイルには含めない。

### 4.4 グリフの変換

日本語グリフに対して、次の処理を実装する。

- unitsPerEmの正規化
- グリフの拡大・縮小
- 文字送り幅の変更
- 水平方向の中央配置
- ベースライン調整
- CFFアウトラインの変換
- 必要に応じた輪郭方向の修正
- 文字幅外にはみ出すグリフの検出

これらは設定ファイルで制御する。

グリフ数がTrueTypeの仕様上限を超える場合は、明確なエラーを出力する。

日本語フォントが複数ファイルに分割されている場合にも対応する。

Unicode補助面の漢字を扱う場合は、対応するcmap形式を使用する。

異体字セレクタやIVSの完全な継承は初期版では保証対象外とし、未対応の範囲をレポートする。

### 4.5 OpenType機能の保持

Cascadiaの次のテーブルおよび機能を可能な限り保持する。

- GSUB
- GPOS
- GDEF
- cmap
- name
- OS/2
- head
- hhea / hmtx
- maxp
- post

特にCode版では、プログラミング合字を破損させないこと。

Mono版では、Code版の合字を誤って追加しないこと。

GSUB/GPOSテーブルを安易に削除する実装は禁止する。

テーブルの追加・変更後には、整合性検証を実行する。

必要に応じてOS/2のUnicode Range、コードページ情報、各種メトリクスを再計算する。

### 4.6 ヒンティング

元のCascadiaグリフのヒンティングを可能な範囲で維持する。

新規追加する日本語グリフには必ずしも元フォントと同等のヒンティングがない可能性がある。

この差についてドキュメントに明記する。

元フォントのヒンティングテーブルと矛盾するデータを生成しない。

## 5. ファミリー名・メタデータ

生成フォントは独自の名称を使用する。

仮のプロジェクト名を `JPBlend` とする。

名前の例：

- JPBlend Plex Mono NF
- JPBlend Plex Code NF
- JPBlend BIZ Mono
- JPBlend Noto Code PL

フォントファミリー名には、元のCascadiaのReserved Font Nameを使用しない。

次のメタデータを適切に設定する。

- Family Name
- Typographic Family
- Subfamily
- Typographic Subfamily
- Full Name
- PostScript Name
- Weight Class
- Style Link
- Copyright
- License
- Version

すべてのバリエーションがOS上で独立して認識されるようにする。

Regular / Bold / Italic / Bold Italicのスタイルリンクを正しく設定する。

同一名称の重複やPostScript名の衝突を許容しない。

## 6. ビルド設定

YAMLファイルで生成対象や変換パラメータを設定する。

例：

```yaml
project:
  name: JPBlend
  version: "0.1.0"

sources:
  cascadia:
    version: "2407.24"

variants:
  - code
  - code-pl
  - code-nf
  - mono
  - mono-pl
  - mono-nf

japanese_fonts:
  - plex
  - biz
  - noto
  - line-seed
  - mplus1
  - mplus2
  - zen-kaku

weights:
  - 200
  - 300
  - 350
  - 400
  - 600
  - 700

styles:
  - normal
  - italic

rendering:
  width_ratio: "1:2"
  jp_scale: 1.0
  baseline_offset: 0
  japanese_italic: upright

build:
  output_format: ttf
  jobs: auto
  fail_on_error: true
```

日本語フォントごとに設定を上書きできるようにする。

例：

```yaml
font_overrides:
  plex:
    jp_scale: 0.96
    baseline_offset: 0

  biz:
    jp_scale: 0.94
    baseline_offset: 0

  noto:
    jp_scale: 0.98
    baseline_offset: 0
```

上記の拡大率は設定例であり、実際の値は表示検証で決定する。

## 7. ソースフォントの取得

### 7.1 取得元

以下の公式配布元を使用する。

- Cascadia: https://github.com/microsoft/cascadia-code
- IBM Plex: https://github.com/IBM/plex
- BIZ UDGothic: https://fonts.google.com/specimen/BIZ+UDGothic
- Noto Sans JP: https://fonts.google.com/specimen/Noto+Sans+JP
- LINE Seed: https://github.com/line/seed
- M PLUS: https://github.com/coz-m/MPLUS_FONTS
- Zen Kaku Gothic New: https://fonts.google.com/specimen/Zen+Kaku+Gothic+New

取得URL・バージョン・チェックサムを管理する。

### 7.2 取得処理

次の機能を実装する。

- 公式の配布アーカイブを取得
- SHA-256検証
- ZIP等の展開
- フォントファイルの検出
- ファミリー名・ウェイトの解析
- 複数サブセットの検出
- 可変フォントの判定
- ソースフォントのキャッシュ
- ライセンスファイルの保存

`latest`を無条件で参照してはならない。

固定バージョンのソースロックファイルを使用する。

ソース更新は明示的なコマンドで行う。

### 7.3 オフラインビルド

すべてのソースフォントとPython依存パッケージが準備されている場合、ネットワーク接続なしでビルドできるようにする。

`fetch`以外のビルド処理では、ネットワークアクセスを必要としない。

取得できないフォントについては手動配置も許可する。

入力ファイルが不足している場合は、不足したファイルと必要なバージョンを表示する。

## 8. CLI仕様

Pythonパッケージとして次のコマンドを提供する。

コマンド名：

`jpblend`

### 8.1 一覧表示

```bash
jpblend list
```

使用可能なCascadia系列、日本語フォント、ウェイト、スタイルを表示する。

### 8.2 ソース取得

```bash
jpblend fetch
```

ロックファイルに従ってソースフォントを取得する。

### 8.3 単体ビルド

```bash
jpblend build \
  --base mono-nf \
  --jp plex \
  --weight 400 \
  --style normal
```

指定された1ファイルを生成する。

### 8.4 ファミリー単位のビルド

```bash
jpblend build \
  --base code-nf \
  --jp noto \
  --all-weights \
  --all-styles
```

指定されたファミリーの全スタイルを生成する。

### 8.5 全組み合わせ

```bash
jpblend build-all
```

すべての組み合わせを生成する。

デフォルト設定では504個のファイルを生成する。

### 8.6 並列ビルド

```bash
jpblend build-all --jobs 4
```

CPU数と利用可能メモリを考慮して並列数を制御する。

メモリ不足を防ぐため、大きなフォントを扱う処理の同時実行数を制限できるようにする。

### 8.7 検証

```bash
jpblend validate --all
```

### 8.8 パッケージ化

```bash
jpblend package --all
```

### 8.9 診断

```bash
jpblend doctor
```

Python、fontTools、HarfBuzz、ソースフォント、ディスク空き容量、権限、Docker利用状況などを確認する。

## 9. OS別ビルド環境

### 9.1 Red Hat系

対象：

- Fedora Linux 44 / 45
- AlmaLinux 10
- Rocky Linux 10
- RHEL 10
- 対応可能なCentOS Stream

Fedoraでの基本インストール例：

```bash
sudo dnf install -y \
  python3 \
  python3-pip \
  git \
  curl \
  unzip \
  fontconfig \
  harfbuzz-devel
```

Python仮想環境を作成する。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

実行：

```bash
jpblend doctor
jpblend fetch
jpblend build-all
jpblend validate --all
```

RHEL系では、HarfBuzzのCLIツールやその他の補助パッケージの所在がリポジトリ構成によって異なる。

オプションのパッケージが利用できない場合は、コアのフォント合成まで停止させないこと。

FedoraとRHEL系の差を考慮し、READMEに個別の注意事項を記載する。

### 9.2 Debian系

対象：

- Debian 13
- Ubuntu 24.04 LTS
- Ubuntu 26.04 LTS
- その他のサポート可能なDebian系

インストール：

```bash
sudo apt update

sudo apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  git \
  curl \
  unzip \
  fontconfig \
  libharfbuzz-bin
```

Python環境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

実行：

```bash
jpblend doctor
jpblend fetch
jpblend build-all
jpblend validate --all
```

ネイティブ環境では、システムPythonへ直接pipでインストールせず、仮想環境を標準とする。

### 9.3 環境依存性の排除

次の条件を満たすこと。

- Pythonの処理はディストリビューションに依存しない。
- ファイルパスにOS固有の固定値を使用しない。
- 外部コマンド呼び出しは必要最小限にする。
- FontForgeへの依存を必須としない。
- Python依存ライブラリはロックファイルで固定する。
- ネイティブ環境とDockerで同じCLIを使用する。

## 10. Docker対応

### 10.1 Dockerfile

プロジェクトルートにDockerfileを用意する。

Debianベースの公式Pythonイメージを使用する。

初期実装ではPython 3.13系のDebianベースを想定する。

配布時にはベースイメージをバージョンまたはdigestで固定する。

Dockerイメージに、Python依存ライブラリと検証に必要なシステムパッケージをインストールする。

ソースフォントは原則としてDockerイメージに組み込まない。

ホスト側からボリュームマウントして利用する。

### 10.2 Dockerビルド

```bash
docker build -t jpblend-builder:local .
```

### 10.3 Docker実行

プロジェクトルートで以下を実行する。

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/work" \
  -w /work \
  jpblend-builder:local \
  jpblend build-all
```

出力先はホストの`build/`ディレクトリとする。

実行ユーザーのUID/GIDを引き継ぎ、生成ファイルがroot所有になることを防ぐ。

SELinuxが有効なRed Hat系のホストでは、適切なボリュームラベルを設定する。

Docker実行コマンドについては、SELinux対応を含むラッパースクリプトも用意する。

### 10.4 Docker Compose

`compose.yaml`を提供する。

次の操作に対応する。

```bash
docker compose build
docker compose run --rm builder jpblend doctor
docker compose run --rm builder jpblend fetch
docker compose run --rm builder jpblend build-all
docker compose run --rm builder jpblend validate --all
```

ホストのUID/GIDを設定可能とする。

SELinux環境でのボリュームラベルを考慮する。

### 10.5 Podman

必須対象はDockerだが、Red Hat系LinuxではPodmanでも同様に実行できることが望ましい。

Docker固有のAPIには依存しない。

Podmanで実行可能な場合は、その手順をREADMEへ記載する。

### 10.6 Dockerとネイティブの同等性

同じソースフォント、設定、Python依存バージョンを使用した場合に、生成されるフォントの内容が同等となること。

生成物について、ビルド時刻などによる不必要な差異を最小限にする。

再現性の検証では、同じ入力に対するSHA-256の一致を目標とする。

## 11. ディレクトリ構成

以下を基本構造とする。

```text
jpblend/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── pyproject.toml
├── requirements.lock
├── Dockerfile
├── compose.yaml
├── Makefile
├── .gitignore
├── .dockerignore
│
├── config/
│   ├── build.yaml
│   ├── fonts.yaml
│   ├── unicode.yaml
│   └── sources.lock.toml
│
├── src/
│   └── jpblend/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── downloader.py
│       ├── source_registry.py
│       ├── font_inspector.py
│       ├── font_converter.py
│       ├── glyph_selector.py
│       ├── glyph_transform.py
│       ├── merger.py
│       ├── metadata.py
│       ├── builder.py
│       ├── validator.py
│       ├── packager.py
│       └── report.py
│
├── scripts/
│   ├── setup-fedora.sh
│   ├── setup-rhel.sh
│   ├── setup-debian.sh
│   └── docker-build.sh
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fixtures/
│   └── rendering/
│
├── source/
│   ├── cascadia/
│   └── japanese/
│
├── cache/
├── build/
├── dist/
│
├── docs/
│   ├── BUILDING.md
│   ├── ARCHITECTURE.md
│   ├── FONT_SOURCES.md
│   ├── FONT_TUNING.md
│   ├── VALIDATION.md
│   └── LICENSES.md
│
└── .github/
    └── workflows/
        ├── test.yaml
        └── build.yaml
```

`source/`、`cache/`、`build/`、`dist/`は基本的にGit管理対象外とする。

ただし、テスト用の小さなフォントフィクスチャは適切なライセンスの下で管理する。

## 12. ビルド成果物

出力例：

```text
build/
├── Plex/
│   ├── Code/
│   ├── CodePL/
│   ├── CodeNF/
│   ├── Mono/
│   ├── MonoPL/
│   └── MonoNF/
│
├── BIZ/
├── Noto/
├── LINESeed/
├── MPlus1/
├── MPlus2/
└── ZenKaku/
```

各ディレクトリに、ウェイト・スタイル別のTTFを保存する。

ファイル名には生成フォントのファミリー名、ウェイト、スタイルを含める。

`dist/`にはファミリー単位のZIPを出力する。

例：

```text
dist/
├── JPBlend-Plex-CodeNF.zip
├── JPBlend-Plex-MonoNF.zip
├── JPBlend-BIZ-CodeNF.zip
└── ...
```

ZIPには、次のファイルを含める。

- TTFファイル
- README
- 元フォントのライセンス情報
- Copyright情報
- バージョン情報
- ソースフォントの出典
- ビルド設定・チェックサムの情報

生成したファイルには、ソースフォントと設定を追跡できるマニフェストを付ける。

## 13. 検証・テスト

### 13.1 バイナリ検証

fontToolsを利用して、次の項目を検査する。

- TTFが正常に読み込めること
- 必須テーブルが存在すること
- cmapが破損していないこと
- グリフ参照が正常であること
- グリフ数が仕様の範囲内であること
- メトリクスに不正値がないこと
- ファミリー名とスタイル名が正しいこと
- フォントファイルを書き戻しても破損しないこと

### 13.2 日本語検証

次の文字列を使用する。

```text
あいうえお
アイウエオ
漢字日本語
こんにちは世界
プログラミング
設定ファイル
括弧「」『』
句読点。、・
全角文字１２３
半角文字123
```

フォントにグリフが存在するか検査する。

すべての日本語フォントについて、ソース側の文字カバー範囲と生成物の範囲を比較する。

欠落した文字について一覧を出力する。

### 13.3 文字幅検証

次の配置を検査する。

```text
1234567890
あいうえお
漢字漢字漢
ABCDEFGHIJ
```

半角10文字と全角5文字の送り幅が等しくなることを確認する。

ただし、各文字の実際の描画幅とセル幅は区別して扱う。

全角スペース、半角カタカナ、罫線、Ambiguous文字についても個別のテストを行う。

### 13.4 合字検証

次の文字列を確認する。

```text
!=
==
===
=>
->
<=
>=
&&
||
```

Code版では、対応する合字が適切に有効化されること。

Mono版では、通常の複数文字として表示されること。

HarfBuzzによるシェーピング結果を、元のCascadiaと比較する。

### 13.5 Nerd Fonts検証

NF版では、元のCascadia NFに含まれるNerd Fontsグリフが失われていないこと。

PL版ではPowerlineグリフを維持すること。

通常版にNF専用グリフを誤って追加しないこと。

PUA領域のコードポイントとグリフの対応関係を比較する。

### 13.6 表示テスト

少なくとも次のアプリケーションでテストできるサンプルを提供する。

- VS Code
- JetBrains IDE
- GNOME Terminal / Ptyxis
- Windows Terminal
- その他のHarfBuzz対応ターミナル

自動テストとは別に、スクリーンショットを比較できるサンプルHTMLや検証用テキストを生成する。

### 13.7 テストレポート

JSON形式とMarkdown形式でビルドレポートを生成する。

内容：

- 生成日時
- ソースバージョン
- ソースのSHA-256
- 使用したウェイト
- 文字カバー率
- 出力ファイル数
- エラー・警告
- 各種検証結果

## 14. 自動テスト・CI

GitHub Actionsに対応する。

### 14.1 テスト

次の環境をテスト対象とする。

- Fedora系コンテナ
- Debian系コンテナ
- プロジェクトのDockerイメージ

処理：

1. Python依存のインストール
2. RuffによるLint
3. pytestによるユニットテスト
4. 小規模フォントを使用した合成テスト
5. 生成TTFの検証
6. Dockerのビルドテスト

### 14.2 フルビルド

手動実行可能なGitHub Actionsを用意する。

フルビルドでは、利用可能なソースフォントを用いてすべての組み合わせを生成する。

ライセンスおよび配布方針が確認されるまでは、生成したフォントを自動的に公開Releaseへ添付しない。

### 14.3 キャッシュ

Python依存ライブラリとソースフォントのキャッシュに対応する。

キャッシュの内容はハッシュ検証する。

## 15. ライセンス対応

Cascadia Codeおよび日本語フォントの各ライセンスを確認する。

SIL OFL 1.1の条件に従う。

特に以下に注意する。

- Reserved Font Nameを生成フォント名に使用しない
- 元の著作権表示を削除しない
- ライセンス文書を同梱する
- 合成フォントの変更履歴を残す
- 再配布条件を満たす

各ソースフォントのライセンスやRFNを確認してから合成・配布する。

法的に問題となる不明点がある場合は、ビルドレポートに警告を記録する。

## 16. パフォーマンス

日本語フォントは多数のグリフを持つため、メモリ使用量に注意する。

次の対策を実装する。

- 必要なグリフのみを抽出する
- 変換済みソースをキャッシュする
- ファミリー単位で処理する
- 不必要なフォント再読み込みを避ける
- 並列数を調整可能にする
- 一時ファイルを適切に削除する

処理時間、最大メモリ使用量、出力ファイルサイズを計測できるようにする。

## 17. 開発手順

以下の順番で実装する。

### Phase 1：開発環境とCLI

- Pythonパッケージの作成
- CLIの作成
- YAML設定の読み込み
- Fedora / Debianセットアップスクリプト
- Dockerfile / Compose
- GitHub Actionsの基本設定

### Phase 2：ソースフォント管理

- ソースレジストリ
- ダウンロード処理
- ロックファイル
- SHA-256検証
- フォント解析
- 静的ウェイト生成

### Phase 3：グリフ合成

- Unicode判定
- グリフ抽出
- unitsPerEm調整
- 文字幅調整
- グリフ合成
- OpenTypeテーブルの保持
- メタデータ設定

### Phase 4：単体生成の完成

以下の4種類を最優先で完成させる。

- Mono NF + IBM Plex Sans JP
- Code NF + IBM Plex Sans JP
- Mono NF + BIZ UDGothic
- Code NF + BIZ UDGothic

それぞれRegularで生成し、動作検証する。

### Phase 5：全組み合わせ対応

- 日本語フォント7種類への拡張
- Cascadiaの通常・PL・NF対応
- 6ウェイト対応
- Italic対応
- 合計504ファイルの生成

### Phase 6：品質改善

- HarfBuzz検証
- 日本語文字幅の検証
- ベースライン調整
- プレビュー生成
- FontBakeryによる追加検証
- レポート作成

### Phase 7：パッケージ化

- ZIP生成
- ライセンス同梱
- README完成
- 再現性確認
- GitHub Actionsの整備

## 18. 受け入れ条件

プロジェクトは、以下の条件を満たした時点で完成とする。

- [ ] Fedora環境でネイティブビルドできる
- [ ] AlmaLinux / Rocky / RHEL系でビルドできる
- [ ] Debian環境でビルドできる
- [ ] Ubuntu環境でビルドできる
- [ ] Dockerからビルドできる
- [ ] ソースのオフラインビルドに対応する
- [ ] 計42ファミリーを生成できる
- [ ] 計504ファイルの静的TTFを生成できる
- [ ] 日本語表示が正常である
- [ ] 半角と全角の幅が正しく揃う
- [ ] Cascadia Codeの合字が維持される
- [ ] Cascadia Monoに合字が追加されない
- [ ] NF版のNerd Fontsグリフが維持される
- [ ] PL版のPowerlineグリフが維持される
- [ ] フォント名が重複しない
- [ ] fontToolsによる読み込み・書き戻しが成功する
- [ ] 必要なライセンス情報が維持される
- [ ] pytestによる自動テストが成功する
- [ ] GitHub ActionsのCIが成功する
- [ ] READMEに環境ごとの手順が記載される

未実装項目や制約がある場合は、隠さず最終レポートに記録する。

## 19. Codexへの実装指示

この仕様書に基づいて、フォント合成ビルドシステムを実装してください。

単なるサンプルスクリプトではなく、実際に継続利用できるPythonプロジェクトとして構築してください。

実装に際しては、次の条件を守ってください。

1. 最初に実装計画を作成し、順番に開発すること。
2. 実際のソースフォントの構造を検査し、仕様との差異を確認すること。
3. 元のCascadiaのOpenType機能の保持を最優先すること。
4. 日本語フォントの形式・ウェイトの違いを適切に吸収すること。
5. Dockerとネイティブ実行で同じPythonコードを使用すること。
6. 公式フォントの既存グリフを不必要に変更しないこと。
7. ソースフォントの再取得なしに再ビルドできるようにすること。
8. テストや検証なしで生成成功と判断しないこと。
9. 実装に利用した技術、ライブラリ、制約を記録すること。
10. ドキュメント、テスト、Docker構成を含めて実装を完了すること。

フォント合成部分については、既存のPlemolJPやUDEV Gothicなどの実装を参考にして構いません。ただし、既存コードのライセンスを遵守し、必要に応じて独立した実装を作成してください。

元のCascadiaが持つ合字、スタイルセット、Nerd Fontsの動作が維持されることを最も重視します。

**最終的には、利用者が`jpblend fetch`と`jpblend build-all`を実行するだけで、必要な合成フォントを一括生成できる状態にしてください。**
