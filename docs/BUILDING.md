# ビルド

Python 3.11以降と仮想環境を使用します。OS別のセットアップスクリプトと
Docker/Compose/Podmanの利用手順はREADMEにあります。

```sh
kumitype fetch
kumitype build-all --jobs 4
kumitype validate --all
kumitype package --all
```

uvでPythonと依存を準備します。

```sh
uv python install
uv sync --locked --extra dev
uv run --locked kumitype fetch
uv run --locked kumitype build-all
```

オフライン利用の前には、対象環境でPython・依存・ビルドバックエンドをキャッシュしてください。

```sh
uv sync --locked --extra dev
uv sync --locked --extra dev --offline
uv run --locked --offline kumitype build-all
```

ソースフォントもfetchで事前準備が必要です。環境が準備済みならビルド自体はネットワークを使用しません。

並列数の既定値autoはCPU数と使用可能メモリ（cgroup制限を含む）で制限します。
`build.worker_memory_mb`（既定2048）で1処理あたりの見積メモリ、
`build.max_jobs`で同時処理数の上限を設定できます。
CLIの--jobsもメモリ上限内で実行されます。

出力先と入力配置先を指定できます:

```sh
kumitype build-all --jobs 4 --source-dir source --output-dir build-latest
```

既定の出力先はbuild/です。異なるコード版の比較では別ディレクトリを指定してください。

```sh
kumitype audit --build-dir build-latest
kumitype validate --all --build-dir build-latest
kumitype package --all --build-dir build-latest --output-dir dist-latest
python scripts/generate-preview.py --build-dir build-latest
```

Makefileでも同じCLIを使用します:

```sh
make fonts BUILD_DIR=build-latest JOBS=4
make verify BUILD_DIR=build-latest HARFBUZZ=hb-shape
make package BUILD_DIR=build-latest DIST_DIR=dist-latest
```

verifyは先に全対象の完全性を監査し、成功した場合のみHarfBuzz必須の検証へ進みます。
