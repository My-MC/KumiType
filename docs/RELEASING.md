# リリース手順

この文書では、固定ソースから全504 TTF・42 ZIPを検証し、下書きのGitHub Releaseを確認して公開する手順を説明します。
ワークフローは公開を行わず、公開操作は保守者が手動で行います。

[ドキュメント一覧](README.md) · [プロジェクトREADME](../README.md)

## ワークフローと安全策

| ワークフロー | 起動方法 | 結果 |
| --- | --- | --- |
| `build.yaml` | 手動の`workflow_dispatch` | `families`・`bases`・`japanese_fonts`で選択し、共通ビルドとFontBakery検査のartifactを保存 |
| `build-fonts.yaml` | `workflow_call` | `--jobs auto`でbuild → audit → HarfBuzz必須validate → package → ZIP監査 |
| `release.yaml` | `v*`タグのpush | バージョン確認、7日本語書体の並列ビルド、全数監査、来歴証明、draft作成 |
| `release.yaml` | 手動実行の`dry_run=true` | 同じ全数ビルド・監査・来歴証明とartifact保存のみ |

手動実行は`dry_run=false`を拒否します。
通常の権限は`contents: read`で、`finalize`だけがRelease書き込みと来歴証明の権限を持ちます。
同じタグの実行は直列化し、再実行時も公開済みReleaseは上書きしません。
ソースキャッシュは`config/sources.lock.toml`のハッシュで識別し、取得時にも固定ハッシュを照合します。
変換キャッシュはこの共有キャッシュの対象外です。

## バージョン更新から公開まで

1. バージョン更新PRを作成し、`config/build.yaml`の`project.version`と`pyproject.toml`の`project.version`を同じ`X.Y.Z`へ更新します。
   `uv lock`でパッケージ版に追従した`uv.lock`も更新してください。
2. `CHANGELOG.md`の`## [Unreleased]`の直下に空の次期変更用領域を残し、今回の変更を`## [X.Y.Z] - YYYY-MM-DD`へ移します。
   日付はリリース用PRで実際の日付に確定し、比較リンクも追加します。
   このワークフロー導入PRでは日付を確定しません。
3. 次のオフライン確認を実行し、CI・レビュー後にバージョン更新PRを`main`へマージします。

   ```sh
   uv run --locked python scripts/release-support.py preflight --tag vX.Y.Z --output build-release
   ```

4. マージ済みコミットを確認してタグをpushします。

   ```sh
   git switch main
   git pull --ff-only
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

5. GitHub Actionsの`Draft release`が完了するまで待ちます。
   `preflight`、7本の`build`、`finalize`がすべて成功し、`release-inventory.json`が42 ZIP・504 TTFを示すことを確認します。
6. GitHubのReleasesでdraftを開き、CHANGELOG由来のノート、42 ZIP、`SHA256SUMS`、来歴証明を確認します。
   問題がなければ手動で公開します。

タグは`vX.Y.Z`または`vX.Y.Z-rc.N`等の形式です。
`-`より前の基底版は両設定の版と一致する必要があります。
タグ実行では日付付きCHANGELOG節が必須で、`Unreleased`へフォールバックしません。

## 最初の候補版とdry-run

最初は`v0.1.0-rc.1`で候補版を作り、確認後に`v0.1.0`を作ります。
どちらも設定とCHANGELOG節の版は`0.1.0`です。
`-`を含むタグではdraftに`prerelease`フラグを付けます。
候補版・正式版とも公開は手動です。

PRブランチを検証する場合は次を使います。

```sh
gh workflow run release.yaml --ref kumi/11-release-workflow -f dry_run=true
gh run list --workflow release.yaml --branch kumi/11-release-workflow
gh run watch RUN_ID --exit-status
```

新規の`workflow_dispatch`ワークフローはGitHubの既定ブランチでの登録が必要な場合があります。
未登録による404・422のときは、タグpushや`main`への直接pushで回避せず、保守者に検証方法を相談してください。
`dry_run=true`では設定同士の版を検証し、該当する日付付き節がまだなければ`Unreleased`からノートを作ります。

## 成果物と再現性

| artifact | 内容 |
| --- | --- |
| `font-build-<jp>` | 6 ZIP、元ビルドマニフェスト、検証レポート、工程別ログ、`pipeline-timings.json` |
| `release-notes` | CHANGELOGの該当節から抽出した`release-notes.md` |
| `release-bundle` | 全42 ZIP、`SHA256SUMS`、全数集計、リリースノート |

`finalize`はZIPから設定通りの504 TTFだけを復元し、元マニフェストのハッシュ照合と`scripts/check-packages.py`の全数監査を行います。
同じ名前のZIP・フォント、欠落、余分なフォント、元マニフェストの欠落・不一致は失敗にします。
書体別レポートは別ディレクトリに保持し、集約時に上書きしません。
`SOURCE_DATE_EPOCH`はタグが指すコミット時刻で、手動実行は選択したHEADのコミット時刻です。
この値はZIPの日時に影響するため、ZIPバイト列の比較は同じ値で行います。
TTFの比較では同じソースロック・設定・ツール版の`main`ビルドを使い、ZIP内のTTF名とSHA-256を照合します。
来歴証明はコード品質や表示品質の保証ではなく、ビルド元と成果物の対応を検証するものです。

## ダウンロードと検証

公開後は例のタグを実際のものに置き換えて実行します。
検証にはGitHub CLIの認証と、来歴証明に対応した`gh`が必要です。

```sh
mkdir -p dist-download
cd dist-download
gh release download v0.1.0 --repo My-MC/KumiType --pattern '*.zip' --pattern SHA256SUMS
sha256sum --check SHA256SUMS
for archive in ./*.zip; do
  gh attestation verify "$archive" --repo My-MC/KumiType
done
```

ZIPに対する来歴証明は`actions/attest-build-provenance`で発行します。
`SHA256SUMS`は42 ZIPのファイル名順で、ZIPと同じディレクトリで検証します。

## 失敗時の再実行

1. 失敗ジョブのログと`font-build-<jp>`の`pipeline-*.stderr.log`・`pipeline-timings.json`を確認します。
2. 一時的な取得・ランナー障害なら、同じタグのワークフローを`gh run rerun RUN_ID`で再実行します。
   `finalize`を含む全工程を再実行するには`--failed`を付けません。
3. 既存draftでは`gh release upload --clobber`で同名ZIPと`SHA256SUMS`を更新します。
   公開済みReleaseなら処理は失敗するため、新しい版の修正PRとタグを用意します。
4. コード修正が必要ならPRで修正し、新しい候補版タグを使います。
   公開済みタグを移動・削除して再利用しないでください。

Releaseの削除・自動公開はワークフローの責務外です。
