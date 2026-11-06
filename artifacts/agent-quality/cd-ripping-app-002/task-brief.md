# Task Brief

- Task ID: cd-ripping-app-002
- Title: トラック毎の全項目タグ編集機能の追加
- Requester / owner: ユーザー
- Date: 2026-11-06
- Risk level: Medium
- Target revision / initial working tree: 2897a50 (working tree clean)

## Background and goal
現状のCD Ripping Appでは、アルバム単位でAlbum名およびArtist名が入力可能であり、トラックタイトルはiTunes検索結果または "Track 01" 等のデフォルト値から一律に生成されていた。
本タスクでは、ユーザーがCDリッピング実行前にトラック毎にタグ情報を個別に確認・編集できるようにし、システムが音声ファイルに書き込む全タグ項目（title, artist, album, track, disc, date, genre, encoder）をトラック単位でカスタマイズ可能にすることを目的とする。

## In scope
1. トラック単位のタグ情報データモデルの定義・拡張（全8項目：title, artist, album, track, disc, date, genre, encoder）。
2. UI（`CDRipperAppView`）におけるトラック毎タグ編集機能の実装：
   - トラック一覧（Treeview）での選択・ダブルクリックまたは編集ボタンからのタグ編集ダイアログ（Modal Dialog）の提供。
   - ダイアログ上でシステムが書き込む全8項目（title, artist, album, track, disc, date, genre, encoder）の表示・編集・保存機能。
   - 編集されたトラック情報のTreeview（一覧）への反映表示。
3. Presenter層におけるトラックタグ状態管理の追加（初期化、個別更新、一括リセット/メタデータ適用時の連携）。
4. リッピングパイプライン（`AudioRipPipeline`）へのトラック個別タグの受け渡しと、FFmpegエンコーダへの正確なメタデータ反映。
5. 出力ファイル名への編集後タイトル・トラック番号の反映。
6. 単体テストおよび統合テストの追加・更新。

## Out of scope
- トラックごとの個別アートワーク（画像）差し替え（アルバム単位のアートワーク管理は既存仕様を維持）。
- 外部音楽タグエディタ（MusicBrainz Picard等）との連携プロトコル。
- 物理光学ドライブの挙動変更。

## Functional requirements
| Requirement ID | Requirement | Priority | Notes |
|---|---|---|---|
| REQ-001 | トラック一覧でトラックを選択し、タグ編集ダイアログを開いてシステムが書き込む全項目（title, artist, album, track, disc, date, genre, encoder）を編集できること | P1 | ダブルクリックまたは編集ボタン |
| REQ-002 | トラック毎に異なるタグ（アーティスト、アルバム、ジャンル、リリース年等）を保持し、個別保存できること | P1 | コンピレーション等に対応 |
| REQ-003 | トラック番号（track）およびディスク番号（disc）は "X/Y" 形式（またはトラック番号と総数の個別入力）で編集・検証できること | P1 | FFmpegタグ形式 "track=1/12", "disc=1/1" |
| REQ-004 | 編集したタグ情報がリッピング実行時にFFmpegエンコード引数（`-metadata`）へ正確に適用されること | P1 | 全項目反映 |
| REQ-005 | 編集後のトラックタイトルおよびトラック番号が出力ファイル名（filename_template）に安全に反映されること | P1 | NTFSサニタイズ経由 |
| REQ-006 | iTunesメタデータ取得時やTOC読み込み時に各トラックのタグ初期値が適切に生成・設定されること | P2 | 既定値からのシームレスな編集 |

## Non-functional requirements
- スレッドセーフティ: GUIスレッドとリッピングワーカースレッド間での安全なデータ参照。
- 入力値検証とサニタイズ: 空白文字、制御文字、不正な番号フォーマットに対する安全なハンドリング。
- 高DPI対応: 新規追加するダイアログが高DPI環境で適切にスケーリングすること。
- テスト網羅性: モデル、Presenter、UIダイアログ、パイプライン、統合エンコードの全層での単体・統合テスト。

## Constraints and compatibility
- Python 3.14 / Tkinter / FFmpeg 既存環境との完全互換。
- 外部サードパーティライブラリ（pip追加）なし。
- 既存の68テストが全件パスし、リグレッションがないこと。

## Acceptance criteria
| Acceptance ID | Given / When / Then or measurable condition | Verification method |
|---|---|---|
| AC-001 | トラック一覧でトラックを選択して編集ダイアログを開いた時、システムが書き込む全項目（title, artist, album, track, disc, date, genre, encoder）の現在値が表示され編集できること | 自動テスト（UI/Presenter） & 手動UI確認 |
| AC-002 | 編集ダイアログで全項目を変更して保存した時、そのトラックのタグ情報が更新され、トラック一覧の表示（title, artist等）にも即時反映されること | 自動テスト（Presenter/View） |
| AC-003 | トラック毎に異なるアルバム名・アーティスト名・年・ジャンル・エンコーダ等を設定してリッピングを実行した時、生成された各ファイルのメタデータ（ffprobe検証）に各トラックの編集値が反映されていること | 統合テスト（test_integration.py / ffprobe） |
| AC-004 | トラック番号・ディスク番号の編集（"2/10" や "1/2" など）が正しくパース・検証され、FFmpegタグに渡されること | 単体テスト（test_rip_pipeline / test_ffmpeg_encoder） |
| AC-005 | トラックタイトルにNTFS禁止文字（`\ / : * ? " < > |`）や特殊文字が含まれる場合でも、ファイル名はサニタイズされつつタグには元の文字列が保持されること | 単体テスト（test_ffmpeg_encoder / pipeline） |
| AC-006 | 既存の全68テストが一切のリグレッションなくPASSすること | `py -3 -m unittest discover` |

## Assumptions / unresolved questions
- 前提: システムが書き込むタグ項目は `title`, `artist`, `album`, `track`, `disc`, `date`, `genre`, `encoder` の8項目である。
- トラック番号・ディスク番号の入力UI: ユーザーが直感的に編集できるよう、`トラック番号 / 総トラック数`、`ディスク番号 / 総ディスク数` のように個別または "X/Y" 形式で編集可能にする。

## Existing user changes to preserve
- 作業ツリーはクリーン（変更なし）。

## Approved commands / environment restrictions
- 実行コマンド: `py -3 -m unittest discover -s tests -p "test_*.py" -v`, `py -3 -m compileall cdripper tests main.py`
- 非破壊コマンドのみ使用可能。
