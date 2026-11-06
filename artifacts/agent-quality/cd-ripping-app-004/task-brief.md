# Task Brief: CD Ripping App - Output Directory Hierarchy and Disc Numbering in Track Filenames

- Task ID: `cd-ripping-app-004`
- Date: 2026-11-06
- Status: In Progress
- Risk Level: Medium

---

## 1. 背景と要求の整理

### ユーザー要求
1. リッピング時、アルバムアーティスト→アルバムという階層でフォルダを作成するようにして欲しい。
2. トラック名の先頭にCD番号を出力して欲しい（`1-01 トラック名` みたいな形式）。
3. 完成したら、GitHubへコミット＆プッシュして欲しい。

### 目的
リッピング実行時に、指定した出力先ルートディレクトリ配下に「アルバムアーティスト / アルバム」という構造のサブディレクトリを自動作成し、整理された形で音声ファイルを保存する。また、複数枚組CDや通常のCDにおいてディスク番号とトラック番号が一目で分かるよう、ファイル名のプレフィックスを `{disc_number}-{track_num:02d} {title}{ext}` 形式とする。

---

## 2. 要件定義

### 2.1 機能要件 (Functional Requirements)
- **FR-001 (ディレクトリ階層の構築)**:
  - リッピング開始時またはファイル保存時、`RipConfig.output_dir` の下に `<Album Artist>/<Album>/` という階層を作成する。
  - アルバムアーティストおよびアルバム名の決定優先順位:
    1. トラックタグデータ（`TrackTagData`）内の `album_artist` / `album`。
    2. アルバムメタデータ（`AlbumMetadata`）内の `album_artist`（未設定なら `artist_name`） / `album_name`。
    3. いずれも空または未設定の場合はそれぞれ `"Unknown Artist"` / `"Unknown Album"` をフォールバックとする。
  - 各ディレクトリ名（フォルダ名）は Windows NTFS および各種OSで不正となる文字（`\ / : * ? " < > |`、制御文字、末尾ドット・空白、Windows予約デバイス名など）を無害化する（既存の `sanitize_filename` 等を活用）。
  - パストラバーサル文字（`..` や絶対パス指定）により `output_dir` の外にファイルが出力されないよう保護する。

- **FR-002 (トラックファイル名へのCD番号付与)**:
  - ファイル名の命名規則を `{disc_number}-{track_num:02d} {title}{ext}` とする。
    - 例: Disc 1, Track 1, Title "Come Together" -> `1-01 Come Together.m4a`
    - 例: Disc 2, Track 12, Title "The End" -> `2-12 The End.mp3`
  - `disc_number` は `TrackTagData.disc_number` または `rip_disc` 引数の `disc_number`（デフォルト1）を使用する。
  - `track_num` は 2桁ゼロパディング（`01`, `02`, ...）とする。
  - `title` は既存通り `sanitize_filename` でサニタイズされた安全な曲名。
  - `RipConfig` の `filename_template` デフォルト値を更新しつつ、フォーマット引数として `disc_number` を渡す。また、カスタムテンプレート利用時にも安全にフォーマット可能とする。

- **FR-003 (GitHubコミット＆プッシュ)**:
  - 実装、テスト、すべてのレビュー・監査ゲートをクリアした後、クリーンな作業ツリーでGitコミットを作成し、リモートリポジトリ（GitHub）へプッシュする。

### 2.2 非機能要件 (Non-Functional Requirements)
- **NFR-001 (セキュリティ・ファイルパス保護)**:
  - パストラバーサル防止（`..` や危険な文字の排除）。
  - Windows予約デバイス名（CON, PRN, AUX, NUL, COM1..9, LPT1..9, CONIN$, CONOUT$ 等）のフォルダ名・ファイル名禁止。
  - パス長制約（Windows MAX_PATH / 260文字制限）を考慮した長さ制御。
- **NFR-002 (堅牢性と整合性)**:
  - 同一ディレクトリ内でのファイル名衝突時の自動連番付与（`seen_output_paths` / `collision_idx`）がディレクトリ階層化後も正しく機能すること。
  - エンコード失敗時やユーザーキャンセル時の中間ファイル削除処理（`cancel_and_cleanup`）が正しいパスを対象に動作すること。
  - スレッドセーフティの維持。
- **NFR-003 (互換性と無回帰)**:
  - 既存の全123テストおよびUI動作にリグレッションを発生させない。

---

## 3. 受入条件 (Acceptance Criteria)

- **AC-001**: リッピング時、出力先として `<output_dir>/<Album Artist>/<Album>/` のディレクトリが自動作成され、トラックファイルがその中に格納されること。
- **AC-002**: アルバムアーティストおよびアルバム名が空または未設定の場合、それぞれ `"Unknown Artist"`、`"Unknown Album"` という安全なフォルダ名がフォールバックとして使用されること。
- **AC-003**: アルバムアーティスト名やアルバム名にWindows禁止文字（`/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`）や末尾の空白・ドットが含まれる場合、安全にサニタイズされてフォルダが作成され、エラーで停止しないこと。またパストラバーサル（`../` 等）が防止されること。
- **AC-004**: 生成されるトラックのファイル名が `{disc_number}-{track_num:02d} {title}{ext}` 形式（例: `1-01 Track Name.m4a`）となること。
- **AC-005**: 複数枚組のディスクにおいて、指定された `disc_number`（例: 2）がファイル名のプレフィックス（例: `2-01 Track Name.m4a`）に正しく反映されること。
- **AC-006**: リッピングキャンセル時やエンコード異常終了時に、指定フォルダ内の仕掛かりファイルが適切にクリーンアップされること。
- **AC-007**: 既存のユニットテスト・統合テスト（および新仕様に合わせて更新されたテスト）が全件合格し、リグレッションがないこと。
- **AC-008**: すべての品質ゲート（設計、実装、QA、レビュー、監査）を通過した状態でGitHubにコミット＆プッシュが完了すること。

---

## 4. 対象範囲と対象外

### 対象範囲
- `cdripper/domain/models.py` (`RipConfig` のデフォルト設定)
- `cdripper/pipeline/rip_pipeline.py` (フォルダ階層作成とファイル名生成ロジック)
- 関連テストコード (`tests/test_rip_pipeline.py`, `tests/test_integration.py` 等)
- 品質ゲート記録 (`artifacts/agent-quality/cd-ripping-app-004/`)
- Gitコミット & プッシュ

### 対象外
- UI画面上の出力先パス入力欄（ユーザーが指定するベース出力先ディレクトリ自体の変更は不要）
- SPTIドライブ読み込み低レイヤロジックの改変
- FFmpegエンコードパラメータの改変
