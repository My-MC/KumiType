# 実装計画と進捗

仕様書の全要件を完成条件として維持する。以下の順番で実装する。

1. Pythonパッケージ、CLI、設定、OSセットアップ、Docker、CI。
2. 固定ソースロック、取得・ハッシュ検証・展開、実フォントの構造解析。
3. 静的インスタンス化、Unicode選択、輪郭変換、合成、メタデータ。
4. Plex / BIZ と Code NF / Mono NF のRegular実生成・検証。
5. 全42ファミリー・504静的TTFへの拡張。
6. バイナリ・幅・HarfBuzz・PUA検証、プレビュー、レポート。
7. ライセンス同梱ZIP、再現性、全環境の検証、利用文書。

現在: ステップ1のパッケージ、設定読み込み、対象列挙CLIを実装。
フォント取得・合成・検証・配布処理は未実装。完成は未検証。

追記: Docker/Compose、OSセットアップ、依存ロック、CI基本構成を追加。
ソース解析、全軸を固定する静的インスタンス化、SHA-256検証付き取得、
ZIP展開を実装。キャッシュ再利用・危険なパス・展開サイズ制限のテストを追加。
現時点のローカル検証: pytest 4件成功、Ruff成功。
公式ソースロック・実フォント検査・合成と後続の要件は引き続き未完了。

公式Cascadia v2407.24を実取得しSHA-256を固定。通常/PL/NFの静的TTFを
アーカイブで確認した。fetch CLIとソースレジストリ、フォント別マニフェストを追加。
日本語7系列のソースロックは未追加であり、現状のfetch対象はCascadiaのみ。

BIZ UDGothicのGoogle Fonts固定コミットからRegular/BoldとOFL文書を取得し、
個別SHA-256をソースロックに追加。日本語文字範囲・設定上書き・PUA保護・
EAWによるセル幅判定を実装。pytestは7件成功、Ruff成功。
残る日本語6系列のソース登録、実合成、全体検証は未完了。

輪郭の分解・CFF→二次曲線変換・UPM正規化・中央配置・ベースライン調整と、
元グリフIDを保持する追加合成を実装。補助面用cmap format 12に対応。
実ソースのMono NF Regular + BIZ Regularで11,105文字を追加し、
24,665グリフのTTF保存・再読み込みと「こんにちは世界」の存在を確認。
219文字に輪郭幅超過があり要調整。build/experimentalの出力は内部試験用で、
名称・ライセンスメタデータ未処理のため配布用成果物ではない。

独立ファミリー名・PostScript名・ウェイト別レガシースタイルリンクと、
両ソースの著作権/ライセンス情報を統合するメタデータ処理を追加。
必須テーブル・cmap参照・複合グリフ参照・元グリフID・PUA・
GSUB/GPOS/GDEFバイナリ保持・再保存/再読込の検証処理を追加。

build CLIを追加。単体/ファミリー全ウェイト/全スタイル指定、ソース選択、
日本語ウェイト代替警告、設定オーバーライド、合成、命名、検証、
入力/出力ハッシュ付きJSONマニフェストを接続した。

Google Fontsの固定コミットbbda7253fc363238b05d97515ca71f8ae49c4fa9から
Plex/Noto/M PLUS 1/M PLUS 2/Zen KakuのフォントとOFL文書を登録。
Plex/Zen Kakuは静的ウェイト、Noto/M PLUSは可変フォント。
doctor CLIを追加しPython/依存/外部コマンド/ディスク/出力権限を診断。
現在の環境にはhb-shape、Docker、Podmanがなく、その環境検証は未実施。
LINE Seedの固定ソース登録は未完了。

LINE Seed公式v20260828アーカイブを実取得し、SHA-256固定で登録。
TTF/OTFそれぞれThin/Regular/Bold/ExtraBoldとOFL文書を確認した。
build-all --jobsを追加。失敗をJSONレポートへ記録し、設定に従い中断する。
全504件の実生成、メモリベースの並列数制御、分割ソース結合、変換キャッシュ、
詳細レポートと残る仕様は未完了。

Plex Mono NF RegularとNoto Code SemiLight ItalicをCLIで実生成した。
後者は可変日本語フォントから350ウェイトの静的インスタンスを作成。
validate --allを追加しマニフェストハッシュ、PostScript名重複、
追加した全コードポイントの存在・セル幅、元テーブル保持を再検査する。

Cascadia公式ライセンスを固定タグから追加取得。
package --allを実装し、出力ハッシュ・検証結果を確認したTTFを
ファミリーごとのZIPへまとめ、両ソースのライセンス・著作権・
JSONマニフェスト・READMEを同梱する。再現性検証用再ビルドを実行中。

Code NF + BIZ Regularの同一入力再ビルドでSHA-256一致を確認。
全504件の4並列ビルドを開始（exec session 3602、ログは
/tmp/kumitype-full-build.log）。完了はまだ確認していない。
JSON/Markdown両形式の集計レポートを実装し、READMEを現状へ更新。

表示サンプルテキスト、オフラインHTMLプレビュー生成スクリプトと
BUILDING/ARCHITECTURE/FONT_SOURCES/FONT_TUNING/VALIDATION/LICENSESを追加。
HTML生成、Ruff、pytest 7件が成功。全ビルドはsession 3602で実行継続中。

独自作成の小規模フォントによる合成統合テストを追加。
元輪郭/ID/GSUB/PUA保持、補助面漢字、全角幅と中央配置を確認。
pytest 8件成功、Ruff成功。workflow_dispatchのフルビルドCIを追加。

CPU・使用可能メモリ・cgroup制限・設定上限に基づく並列数制御を追加。
設定のjobs:autoをCLI既定へ反映。Unicodeの個別優先指定を合成へ接続。
pytest 10件成功、Ruff成功。進行中ビルドは変更前コードで継続中。

二次曲線化テストと504対象すべてのPostScript名一意性・スタイルリンク・
両ソースCopyright保持テストを追加。pytest 12件成功、Ruff成功。
ZIPへライセンス提供元のソースマニフェスト（公式URL/版/ハッシュ）も同梱。

ソースレジストリを強化し、バージョンのパス逸脱を拒否。
ビルドは有効ロックに一致するマニフェストのみを選択し、古い版を無視する。
Cascadiaも入力ファイルのハッシュを照合する。pytest 14件とRuff成功。
進行中全ビルドは変更前コードで継続中のため、新しい照合処理は別途検証が必要。

静的インスタンスの内容ハッシュ・ウェイト・依存バージョン別キャッシュを追加。
キャッシュのハッシュ不一致時は再生成し、破損復旧テストを追加。
CFFソースではTrueTypeへ変換時に輪郭方向を反転するよう修正。
pytest 15件成功、Ruff成功。進行中の全ビルドは変更前コードで継続している。

設定の型、YAML構文、出力形式、独自名称、拡大率・オフセットの有限値、
Unicodeスカラー値・優先指定を検証するよう強化。不正な入れ子の対象指定も
明確なValueErrorで拒否する。pytest 17件成功、Ruff成功。

HarfBuzz CLIをシステム変更なしで一時展開し、Code NF+BIZ Regularと
Mono NF+Plex Regularの9記号列で元フォントと出力のシェーピング一致を確認。
比較モジュールを追加。CLI未導入時はunavailableとして未検証を明示する。

HarfBuzz比較をvalidate --allへ接続。実行ファイル指定オプションを追加し、
未導入時は未検証、実行失敗時は失敗として報告する。
Plex Mono NFで統合検証成功。pytest 18件、Ruff成功。
CIへFedora/Debian/Ubuntu/AlmaLinux/Rockyコンテナでの合成テストを追加。
CIの実実行と各OSでのフルビルドは未確認。

TTFを一時ファイルへ保存・検証後に置換し、不正出力で既存ファイルを上書きしない
保存方式へ変更。マニフェストも個別に原子的置換する。
失敗時の既存出力保護と一時ファイル削除をテスト。pytest 20件とRuff成功。
修正後コードの実ソースビルドをbuild-verificationへ別途実行中。

パッケージ化時に保存済み結果だけでなく、現在のTTFを再検証するよう強化。
改変出力とライセンス不足を拒否する統合テストを追加。
pytest 22件成功、Ruff成功。

複数日本語ソースのUnicode和集合を重複なしで取り込むmerge_manyを追加し、
font_overrides.*.subset_filesから手動指定できるよう接続。
分割ソースの補助面・重複文字テスト成功。pytest 23件、Ruff成功。
自動グループ化、異なる追加ソースライセンスの統合は未完了。

日本語ソースのカバー範囲と出力を比較するcoverage_reportを追加。
欠落コードポイント・サンプル文字欠落・文字カバー率を記録。
マニフェストへ生成日時・出力サイズ・プロセス最大RSSを追加し、
幅超過・サンプル欠落・ヒンティング/IVS制約を警告へ記録。
pytest 24件とRuff成功。実行中の旧コード生成物には新項目はまだ付いていない。

取得ハッシュ不一致時の一時ファイル削除、破損キャッシュ再取得、
ZIPシンボリックリンク拒否のテストを追加。pytest 27件、Ruff成功。
仕様書18章の受け入れ状況と残作業をACCEPTANCE_STATUS.mdに整理。

update-sourceコマンドを追加。明示指定の固定版/URL/SHA-256で1レコードを
追加・更新し、全レコードの妥当性を確認してからロックを原子的に置換。
通常ビルドやfetchはロックを変更しない。pytest 28件、Ruff成功。

import-sourceで手動取得した固定ソースをネットワークなしで登録する機能を追加。
fetchも同じ登録処理を使用する。ハッシュ不一致拒否とネットワーク未使用を検証。
pytest 29件、Ruff成功。

auditコマンドを追加し、設定全対象に対する欠落/重複/想定外/未検証を検査。
フルビルドCIへ監査を追加。pytest 31件成功、Ruff成功。

並列ビルドを同時実行数ぶんだけ投入する方式へ変更。
fail_on_error時は新規投入を停止し、実行中の結果を回収して未着手対象も
明示的な診断へ記録する。fail-fastテスト追加、pytest 32件とRuff成功。
既存の全ビルドsession 3602は以前のスケジューラで継続中。

取得ライセンス先頭でRFNを確認し、Plexの生成名をIBMJPへ変更。
旧build/Plexと実行中旧コードの生成物は配布対象外と文書化。
Cascadia Code/SourceのRFNと各ソース文書の確認結果をLICENSESへ記録。
pytest 32件、Ruff成功。

パッケージ化時に現在の生成命名とマニフェストを照合し、旧Plex名などの
古い命名を拒否するよう変更。RFN旧名の拒否テストを追加。
pytest 33件、Ruff成功。

検証へUPM/ウェイト範囲、グリフ数、空cmap、必須名前ID、hmtx数値範囲を追加。
マニフェストとのPostScript名/Typographic Family/ウェイト一致も確認する。
不正メタデータテスト追加。pytest 34件、Ruff成功。

fonts.yamlの登録を設定読み込み・対象判定・命名・出力ディレクトリへ接続。
任意日本語系列の設定追加テストを追加。pytest 35件、Ruff成功。
最新検証でBIZ/LINE Seed Mono NFのバイナリ・HarfBuzz比較成功を確認。

doctorへロック全ソースの必要バージョン・不足マニフェスト・不足ファイル・
入力ハッシュ不一致の診断を追加。pytest 36件、Ruff成功。

unicode.yamlを設定読み込みへ接続し、build.yamlの同一指定を優先して統合。
優先順位テストを追加。pytest 37件、Ruff成功。
受け入れ状況の既実装項目を更新。全ビルドは旧コードでMono PLまで継続中。

小規模のロック済みソースからbuild_one全体をネットワーク禁止下で実行する
統合テストを追加し、カバー率・独自名・出力ハッシュと検証成功を確認。
pytest 38件、Ruff成功。最新版でIBMJP Mono NF/Code NF Regularを
build-verificationへ実生成中（session 74859）。

二次曲線化済み輪郭をJSON/base64とSHA-256で保存するキャッシュを追加。
入力ハッシュ・ウェイト・UPM・セル幅・スケール・ベースライン・fontTools版で識別。
標準単一ソースビルドへ接続。複数サブセット指定時はキャッシュを使用しない。
キャッシュ有無のglyf/hmtx一致テスト成功。pytest 39件、Ruff成功。
IBMJP Mono NF/Code NF Regularの最新実生成成功を確認。

ZIP同梱ライセンスも有効ロックに一致する版のみ選び、個別ライセンス文書の
SHA-256を再確認するよう変更。輪郭キャッシュ破損時の破棄を追加検証。
pytest 40件、Ruff成功。実ソースのキャッシュ有無再ビルドはsession 98529で実行中。

実ソースBIZ Mono NFで輪郭キャッシュ使用前後のSHA-256一致を確認。
build/build-allへ--source-dir/--output-dirを追加し、レポートも指定先へ保存。
最新版の全504件をbuild-latestへ4並列で開始。旧ビルドはsession 3602で継続。
pytest 40件、Ruff成功。

validate/audit/packageとプレビューにビルド先指定を追加。
CLI監査の欠落検出と空ディレクトリの検証失敗をテスト。
pytest 42件、Ruff成功。build-verificationのHarfBuzz込み再検証を実行中。

追加サブセットソースの著作権・ライセンス・URLメタデータも生成フォントへ
統合するよう変更。追加著作権保持テスト成功。pytest 43件、Ruff成功。
別配布元のライセンス文書同梱の自動化は残作業。

validate --allで破損TTF/マニフェストがあっても残りの診断を継続し、
ファイル単位のエラーを返すよう変更。JSON/Markdown検証レポートも保存。
複数破損ファイルの継続診断テストを追加。pytest 44件、Ruff成功。

同一ファミリー/ウェイト/選択順位で補完的なカバー範囲を持つソースを自動検出。
重複TTF/OTFを除外しつつ不足範囲を追加し、各ハッシュも照合する。
分割ソース選択テスト成功。pytest 45件、Ruff成功。

継続監査: 旧ビルドとbuild-latestの両プロセスが稼働中であることをpsで確認。
最新版44/504件で欠落460件、重複エラーなし。完了を宣言しない。
設定の既知RFN再指定を拒否し、pytest 46件、Ruff成功。

追加サブセットのライセンス文書をsubset_licensesから指定し、マニフェストに
ハッシュを記録、パッケージ化時に再検証して同梱する機能を追加。
オフライン統合テストで追加ライセンスの追跡を確認。pytest 46件、Ruff成功。

ZIPも一時出力が完成してから原子的置換するよう変更。
圧縮途中失敗時に既存アーカイブを保持するテスト追加。pytest 47件、Ruff成功。
build-verificationの実フォント4件を最新版パッケージ化処理で検証中。

ワーカー起動時の実装ソースハッシュ・Python・依存バージョンを記録する機能を追加。
コード変更の追跡テスト成功。pytest 48件、Ruff成功。
現在実行中のbuild-latestプロセスにはこの追加以前のコードが読み込まれている。

本体コード用MIT LICENSEとパッケージREADME/ライセンス情報を追加。
Dockerfileもビルド時にREADME/LICENSEをコピーするよう修正。
オフラインwheel作成でsetuptools不足を検出したため、ビルド依存もロックへ追加中。
pytest 48件、Ruff成功。

旧全ビルドsession 3602が終了コード0で完了。build/build-report.jsonは
504出力・エラー0、matrix監査も504対象一致。ただし旧Plex名/CFF修正前を含むため
配布用完成の証拠にはしない。最新版build-latestは124/504で継続。
setuptools/wheelを依存ロックへ追加し、--no-build-isolationのwheel作成成功。
wheel内のCLI・エントリポイント・LICENSEを確認。

全生成物のHarfBuzz比較用スクリプトを追加。
旧ビルド504件のシェーピング比較をsession 17478で実行開始。
最新版の検証とは区別して結果を扱う。pytest 48件、Ruff成功。

旧版504件のHarfBuzz全9記号列比較が504/504成功。
最新版の検証とは区別し、旧版shaping-report.jsonへ結果を保存。
元グリフにヒント命令を持たせた合成テストで輪郭バイナリの保持を検証。
ビルド集計レポートも原子的保存へ統一。pytest 48件、Ruff成功。

最新版の生成済み7系列について、日本語ソース範囲のカバー率100%、
仕様サンプル文字の欠落なしを確認。輪郭幅超過は残るため警告を維持。
検証へ元Cascadia全グリフのhmtx不変条件を追加。改変検出テスト成功。
pytest 49件、Ruff成功。

生成済みRegularの幅超過を調査。IBMJP/BIZ/LINESeed/ZenKakuは主にA/N、
NotoはA/Nに加え半角Hにも超過があった。調査したRegularのW/Fには超過なし。
文字種別チューニング用のoverflow-report生成スクリプトを追加。
205生成物でレポート作成成功。pytest 49件、Ruff成功。

半角カナ専用のhalfwidth_kana_scaleを追加（既定1.0で既存挙動を維持）。
全角輪郭・送り幅を変更しないこと、半角カナだけの縮小をテスト。
係数を設定検証とキャッシュキーへ接続。pytest 50件、Ruff成功。
書体別の実値の決定と目視検証は未完了。

最新版233生成物・12スタイル完備19ファミリーを確認。
validateへ--require-harfbuzzを追加し、フルビルドCIでツール導入と必須検証を設定。
未導入時の誤成功を拒否するテスト追加。pytest 51件、Ruff成功。

生成マニフェストへ正規化した設定JSONのSHA-256を追加。
配布ZIPにVERSION.txtを同梱。設定ハッシュの統合テスト成功。
pytest 51件、Ruff成功。IBMJP Code全12スタイルの最新検証をsession 94664で実行中。

validateで記録済みconfig_sha256と設定内容を照合するよう追加。
設定改変を検出するオフライン統合テスト成功。pytest 51件、Ruff成功。
旧形式のマニフェストにハッシュ項目がない場合は従来検査のみ行う。

最新版Code/Code PL/Code NFは各84件完備、Monoは36件を確認。
比較用build-*/dist-*とwheelhouseをGit/Dockerコンテキストから除外し、
大きな試験成果物がコンテナビルドへ送信されるのを防止。
最新版の生成済み出力からプレビューHTMLを再生成した。

Fontconfig fc-scanで最新IBMJP Code Regularを読み、Family/Style/PostScript名が
それぞれKumiType IBMJP Code/Regular/KumiTypeIBMJPCode-Regularとなることを確認。

Playwrightブラウザでbuild-verificationの4実フォントがloadedであることを確認。
BIZ Mono NFの日本語・カナ・記号の描画をpreview.pngで目視確認した。
HTTPプレビューサーバーはsession 51005、127.0.0.1:8765で稼働中。

ブラウザでLINESeed Mono NF/IBMJP Code NFの日本語・半角カナ・括弧を目視確認。
build-verification/line-seed-preview.png、ibmjp-code-preview.pngを保存。
先のCanvas測定では4実フォントすべて半角10文字と全角5文字が117.1875pxで一致。
GUI各アプリ固有の表示確認や全書体の調整はまだ未完了。

HarfBuzz比較スクリプトへ系列フィルターを追加し、部分比較レポートを区別。
最新版Code/Code PL/Code NFの252件比較をsession 76333で開始。
Ruff成功。最新版全ビルドsession 61429は引き続き稼働。

validatorへ元Cascadiaに存在しないPUA追加の拒否を追加。
通常版へのNF専用PUA混入を検出するテスト成功。pytest 52件、Ruff成功。
最新版の生成済み全件のPUAマッピングを元Cascadiaと比較中（session 33539）。

受け入れ状況を現在の証拠へ更新。unshare -Urnはuid_map権限不足で失敗。
OS隔離とは区別し、Python監査フックでsocket接続/DNSを拒否する実ソースビルドを開始。

Python監査フックでsocket接続/DNS拒否下のBIZ Mono NF Regular生成が成功。
生成物のvalidation成功・日本語カバー率1.0を確認。OS隔離の代替証拠とするが
ネットワーク名前空間の実行成功を意味しない。
Makefileへ出力先指定付きfonts/audit/validate/verify/package/previewを追加し、
verifyが監査成功後のみ必須HarfBuzz検証へ進むコマンド展開を確認。

最新版468/504件を確認。ロック依存のRequires-Pythonを確認し、全て3.11対応。
sudo -nは認証必須のためDocker等のシステム導入による検証はできない。
Noto可変由来の350 Italic再ビルド一致検証を開始。

最新版の監査は491/504件、欠落13件。完了前の監査として終了コード1を確認。
pytest 52件とRuffを再実行して成功。Noto再現性検証session 99054と
全ビルドsession 61429は稼働中。

最新版504件生成がエラー0で完了し、auditもcomplete:true、欠落/重複/想定外なし。
Noto可変由来350 Italicの2回生成でSHA-256一致を確認。
全件validateはsession 64394で継続。全件ZIP生成と最新504件HarfBuzz比較も開始。

最新版504件の全9記号列HarfBuzz比較が504/504成功。
build-latest/shaping-report.jsonへ結果保存。validate/session 64394と
package/session 69425は稼働中。packageは全TTF再検証後にZIP出力を開始する。
ZIP検査をCIへ追加し、ZIP内TTF改変検出テストを追加。pytest 53件、Ruff成功。

Fontconfig fc-scanで最新版504件のPostScript名がマニフェストと504/504一致。
fontconfig-report.jsonへ保存。全件validateとpackageはCPU使用を伴い稼働中と確認。

全504件を集計し42ファミリー、全件の日本語ソース範囲カバー率1.0、
仕様サンプル欠落0を確認。全件プレビューとoverflow-reportを更新。
ARCHITECTUREの古いキャッシュ/分割統合未実装記述を現状へ修正。
全件validate/packageは引き続き同じプロセスで稼働中。

READMEの旧「全生成進行中」を実504件成功へ更新し、残る全件検証・環境検証と
目視調整の状況を明示。全件validate/packageは各約100%CPUで処理継続を確認。

/etc/os-releaseでホストUbuntu 26.04.1 LTSを確認し、同環境の504件ネイティブ生成を
受け入れ証拠として記録。Fedora/RHEL/Debian/Dockerの実行成功を意味しない。

先行検証の4ZIPを実点検し、各日本語ソースとCascadiaのライセンス文書の
同梱、およびZIP CRCが正常であることを確認。全42ZIPの結果とは区別する。
全件validate/session 64394とpackage/session 69425は同じ処理を継続中。

固定ソースの個別ライセンス文書7件について、実ファイルSHA-256がロックと
一致することを再確認。LINE Seedの文書は公式アーカイブ内に保持される。
全件validate/packageは同じ実行ハンドルで稼働継続中。

全42ファミリーが各12スタイル揃うことを集計確認。
TTF合計2,239,481,572 bytes。family-summary.jsonへファミリー別サイズと幅超過数を保存。
全件validate/session 64394とpackage/session 69425の実行継続を確認。

2026-11-06再確認: validate/packageプロセスは終了し、最新validation-reportの
504件すべてvalid:true、shaping:passed。dist-latestに42ZIPが存在。
ZIP在庫・CRC・TTFハッシュ・対応関係の全検査をsession 19927で実行中。
pytest 53件、Ruff成功。Docker/Podmanは引き続き未導入、Gitリポジトリも未初期化。

全ZIP検査が終了コード0で完了: Checked 42 archives, 504 fonts。
ZIP CRC、必須文書、同梱TTFのSHA-256、build-latest全出力との一対一対応が成功。
残る環境別実行・CI・全書体の目視調整は未証明のため完成扱いにしない。

プレビューへbase/weight/style絞り込みと出力名指定を追加。
7日本語系列のMono NF Regularギャラリーを生成しブラウザで読み込み確認。
pytest 53件、Ruff成功。

7系列の一覧スクリーンショットseven-families.pngを目視確認したところ、
M PLUS 1/2の半角カナに表示欠落を発見。半角カナは仕様の基本サンプル集合に
含まれておらず従来の欠落チェックでは検出できていない。原因調査・修正が必要。

M PLUS公式可変ソースに半角カナcmapもhwid機能も存在しないことを確認。
欠落する半角カナをNFKC対応の全角ソース輪郭から水平50%で生成する処理を追加。
高さと1セルadvanceを維持しderived_halfwidth_codepointsへ記録する。
既存半角グリフは変更しない。キャッシュ形式を更新し、サンプルへ半角カナを追加。
pytest 54件、Ruff成功。実M PLUSの再生成・表示再確認と影響分のZIP更新は未完。

M PLUS 1/2の半角カナ63文字すべてについて対応する全角ソースグリフの存在を確認。
実フォントRegularの修正後生成をsession 46386で実行中。
補完数を警告にも記録し、挙動をFONT_TUNINGへ明記。pytest 54件、Ruff成功。

修正M PLUS 1/2 Regularのブラウザ描画で半角カナが表示されることを目視確認。
半角カナ5文字とASCII5文字が両書体とも58.59375pxで一致。
影響する144TTFをbuild-latestへ再生成開始（/tmp/kumitype-repair-mplus.py）。
完了後に全504件の集計レポートを更新する。旧検証結果/ZIPは修正前であり要更新。

validate_allへ半角カナ全63文字の独立した存在・1セル幅検査を追加。
入力ソースにない文字の取り込み漏れも検出する。pytest 55件、Ruff成功。
M PLUS再生成session 61257は稼働中。

再生成中の全件走査で一時TTFを拾うことを確認したため、検査対象を
マニフェスト付き・非一時ファイルかつ非M PLUS系列へ絞って再検査。
M PLUS自体はsession 61257の生成完了後に検査する。

非M PLUS5系列360TTFについて半角カナ全63文字の存在・1セル幅を検査し全件成功。
M PLUS 144件の再生成はCode NFまで進行中。再生成完了済みMPlus1 Code/CodePL
24TTFを独立半角検査とHarfBuzz込みで再検証開始。

補完した半角カナのキャッシュ有無でglyf/hmtxと補完レポートが一致し、
既存半角グリフを補完しないことをテスト。pytest 56件、Ruff成功。
再生成と24件の追加検証は既存ハンドルで継続中。

M PLUS修正済み114/144件（MPlus1 60、MPlus2 54）を確認。
完了済みCode通常/PL/NF252件のHarfBuzz再比較をsession 62866で開始。
MPlus1 Code/CodePL24件の完全検証session 21060も稼働中。

半角カナ修正後Code通常/PL/NF252件のHarfBuzz比較が全件成功。
M PLUS126/144件が修正済み。残りの生成完了後に12ファミリーのZIPを更新する。

M PLUS修正144/144件の再生成が完了。最新の半角独立検査/HarfBuzz込み144件の
再検証session 68063、影響12ZIP更新session 64613を開始。
変更していない360件は従来のバイナリ検証結果を保持し、全504件の半角カナを再検査。

修正後の全504TTFに対する半角カナ全63文字の存在・1セル幅検査が504/504成功。
独立結果をhalfwidth-report.jsonへ保存。M PLUS144件のバイナリ/HarfBuzz検証と
影響12ZIP更新は既存セッション68063/64613で継続中。

Context7のuv公式ドキュメントを確認し、管理者権限なしでPython 3.11.17を導入。
.venv311へ固定依存を導入してテストを開始。比較用仮想環境もGit/Dockerから除外。
M PLUS再検証/ZIP更新は同じプロセスで継続中。

Python 3.11.17の別仮想環境で固定依存の導入、editable install、pytestが終了コード0。
最低対応Pythonでの実行互換性を確認（OSは同じUbuntuであり他OSの代替ではない）。

可変日本語ソースの使用ウェイト記録が元フォント既定値になっていた問題を修正。
輪郭生成自体は指定ウェイトで静的化していたが、今後のマニフェストも指定値を記録。
既存マニフェストとZIP内記録の更新は、実行中処理終了後に行う必要がある。
Python3.11/3.14の同一入力実生成を別出力先で比較中。pytest 56件、Ruff成功。

Python3.11.17/3.14.7のBIZ Mono NF RegularがともにSHA-256
7acb5e639ff2996cf4dc13790b40c62983b103edbb9207a2f0b20d395ed286f3で一致。
M PLUS再検証とZIP更新は各約100%CPUで稼働中。ウェイト記録更新は競合回避のため待機。

修正後MPlus1の6ZIP更新をログで確認。MPlus2の6ZIP処理と144件再検証は
同じ実行ハンドルで継続中。終了を待ってから全ZIP整合性を再検査する。

処理終了後に使用するウェイト記録訂正スクリプトを準備。
実ソースのwght軸を持つファイルを識別し、TTF自体を変更せず記録とZIP内JSONを
更新する。訂正前値と理由をreport_correctionsへ保存する。まだ実行していない。

ZIP整合性検査へ、同梱マニフェストとビルド側JSON全体の一致検査を追加。
TTFハッシュが同じでも古い/改変されたメタデータを検出するテストを追加。
pytest 56件、Ruff成功。M PLUS再検証/ZIP更新は引き続き同一ハンドルで稼働。

直近のZIPマニフェスト一致検査・ウェイト記録修正を含め、Python3.11側でも
pytest 56件とRuff成功を再確認。M PLUS再検証/ZIP更新の両プロセスは稼働継続。

M PLUS修正後12ZIPの更新処理session 64613が終了コード0で完了。
144件再検証session 68063と全504件HarfBuzz再比較session 99585は稼働継続中。

M PLUS修正144件の完全再検証が144/144成功し、全504件の検証集計へ反映。
修正後全504件HarfBuzz比較も504/504成功。ウェイト記録訂正をsession 41716で開始。
TTFは変更せず、訂正履歴付きJSONとZIP内マニフェストを更新する。

統合後のvalidation-report.jsonが504件すべてvalid:trueであることを確認。
README/受け入れ状況をM PLUS再生成・再検証・ZIP更新成功へ更新。
ウェイト記録訂正session 41716は継続中、終了後に全ZIP検査が必要。

ウェイト記録訂正session 41716が終了コード0で完了。216件に訂正履歴を保存し、
使用ウェイトが指定ウェイトと一致することを確認。TTFは変更していない。
ZIP内マニフェストも同期済み。全42ZIPの最終内容検査を開始。

最終ZIP検査が終了コード0、42ZIP/504TTFのCRC・ハッシュ・文書・マニフェスト一致成功。
旧build/distをbuild-legacy/dist-legacyへ退避し、検証済み成果物を既定build/distへ移動。
build-latest/dist-latestは相対シンボリックリンクとして以前のレポート参照を維持。

ローカル最終監査: 修正済み504TTF/42ZIP、検証集計、半角カナ検査、HarfBuzz、
ZIP内マニフェスト一致検査が成功。既定build/distへの配置後のauditも成功。
コンテナなし・sudo不可・CI実行先未設定の同一制約を繰り返し再確認。
対象OS/Docker/リモートCIの受け入れを証明するには外部環境情報が必要。

ユーザー指定によりプロジェクト表示名/パッケージメタデータをKumiType、
Pythonモジュール/CLIをkumitypeへ改名。Pythonは.python-versionの3.13.9、
依存はuv.lockへ固定し、setup/Makefile/Docker/CIをuvへ移行。
旧requirements.lockは廃止。新環境でpytest56件、Ruff、シェル構文検査成功。
以前のJPBlend名フォントは旧検証成果物として保持し、KumiType名では再生成が必要。

uv sync --locked --extra dev --offlineが成功し、パッケージName=KumiTypeを確認。
uv run --locked --offlineによる実BIZ Mono NF Regular生成・整合性検証成功。
生成名はKumiType BIZ Mono NF、PostScript名はKumiTypeBIZMonoNF-Regular。
Docker/リモートCI自体の実行は引き続き環境制約により未確認。

ユーザー指定により既定Pythonを3.13.9から3.14.7へ移行。
.python-version、Dockerベース、フルビルドCI、READMEを更新し、CIから3.13を除外。
公式Pythonイメージ3.14.7-slim-bookwormの存在を確認。
uvで3.14.7環境を再作成し、固定ロック同期、pytest56件、Ruff、CLI一覧が成功。
Dockerイメージ自体のビルド実行は既存のランタイム制約により未確認。
