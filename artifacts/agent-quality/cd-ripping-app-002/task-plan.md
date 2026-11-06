# Implementation Plan

- Task ID: cd-ripping-app-002
- Design status: Approved (Revision 2 - CHALLENGE-001〜008 解消済み)
- QA matrix status: Approved (全38ケース設計完了)

## 1. タスク一覧テーブル

| Task | Owner agent | Scope / files | Depends on | Contract | Done when | Tests |
|---|---|---|---|---|---|---|
| **TASK-001** | implementer | `cdripper/domain/models.py`<br>`cdripper/domain/validation.py` (新規) | None | **ドメインモデル & バリデーション契約**:<br>1. `TrackTagData` (`@dataclass(frozen=True)`):<br>- `track_number: int`, `total_tracks: int`, `disc_number: int`, `total_discs: int`<br>- `title: str`, `artist: str`, `album: str`, `date: str`, `genre: str`, `encoder: str`, `is_customized: bool = False`<br>- プロパティ: `track_tag_value` ("X/Y"), `disc_tag_value` ("X/Y")<br>- メソッド: `to_metadata_dict()` (空タグ除外: CHALLENGE-008)<br>- ファクトリ: `create_default(...)`<br>2. `validation.py`:<br>- `sanitize_tag_string(val, max_len=256)` (制御文字/ヌル除去: CHALLENGE-004)<br>- `parse_and_validate_fractional_tag(val, field)` (1〜999, 0/負数遮断: CHALLENGE-004) | モデルが不変かつ空タグ除外辞書変換でき、バリデーションヘルパーが不正値を遮断して正常な数値を返す | `tests/test_track_tag_data.py` (新規)<br>- 不変性確認<br>- プロパティ書式<br>- 空タグ除外<br>- バリデーション境界値（0/0, 負数, 制御文字） |
| **TASK-002** | implementer | `cdripper/pipeline/rip_pipeline.py` | TASK-001 | **Pipeline契約拡張**:<br>1. `rip_disc` に `track_tags: Optional[Dict[int, TrackTagData]] = None` を追加（後方互換性100%維持）<br>2. `track_tags` 最優先解決（SSOT priority）<br>3. `config.filename_template.format(track_num=tag.track_number, ...)` で必ず整数を渡し `ValueError` クラッシュを防止（CHALLENGE-001）<br>4. `safe_title = sanitize_filename(tag.title)` でファイル名生成、タグには元の生文字列を保持<br>5. `tag.to_metadata_dict()` をエンコーダへ渡す | `track_tags` 指定時に各トラックの個別タグがFFmpeg引数に渡され、整数トラック番号でファイル名生成される。未指定時は既存挙動と同一 | `tests/test_rip_pipeline.py`<br>- 個別タグ優先適用<br>- 整数ファイル名生成<br>- 後方互換性（`track_tags=None`）<br>- 空タグ除外検証 |
| **TASK-003** | implementer | `cdripper/ui/tag_dialog.py` (新規) | TASK-001 | **UI Dialog契約**:<br>1. `TrackTagEditDialog(tk.Toplevel)`:<br>- 8項目入力（Title, Artist, Album, Track No/Total, Disc No/Total, Date, Genre, Encoder）<br>- 前後ナビ（`< Prev`, `Next >`、境界無効化、移動時検証）<br>- `parse_and_validate_fractional_tag` & `sanitize_tag_string` による入力検証<br>- 保存時に `is_customized=True` を付与しコールバック呼び出し<br>- 安全なモーダルライフサイクル（`transient`, `grab_set`, `try...finally: grab_release()`, `WM_DELETE_WINDOW`: CHALLENGE-005） | ダイアログで8項目の表示・編集・検証・保存が行え、破棄時に確実にモーダルが解放される | `tests/test_tag_dialog.py` (新規)<br>- 初期値バインド<br>- 不正入力エラー表示<br>- 前後ナビゲーション<br>- `grab_release()` ライフサイクル |
| **TASK-004** | implementer | `cdripper/ui/presenter.py` | TASK-001<br>TASK-002 | **Presenter契約拡張**:<br>1. SSOT状態管理: `self.track_tags: Dict[int, TrackTagData] = {}`, `self.is_ripping: bool = False` (CHALLENGE-002, CHALLENGE-006)<br>2. TOC読込時: デフォルト `TrackTagData` 自動生成<br>3. メタデータ適用時: 手動編集トラック保護判定と反映<br>4. API: `get_track_tag`, `get_all_track_tags`, `has_customized_tracks`, `update_track_tag`, `sync_album_artist_to_uncustomized`<br>5. イベント: `PresenterEvent.TRACK_TAG_UPDATED`<br>6. `start_ripping`: `is_ripping` ガード、`dict(self.track_tags)` のスナップショット受け渡し（CHALLENGE-007）、完了時解除 | PresenterがタグのSSOTとして動作し、更新イベント通知、未編集トラック連動、リッピング排他ガードが機能する | `tests/test_presenter.py`<br>- タグ初期化・個別更新<br>- SSOT連動更新<br>- `is_ripping` 重複起動抑止<br>- スレッドセーフティ |
| **TASK-005** | implementer | `cdripper/ui/app_view.py` | TASK-003<br>TASK-004 | **View層契約拡張**:<br>1. 排他制御: `_set_ripping_ui_state(is_ripping)` でリッピング中は全UIコントロール（Drive, Virtual CD, Read Speed, Album/Artist, Search, Treeview, Edit, Start Rip）を一括 `DISABLED` 化、Cancelのみ `NORMAL`（CHALLENGE-002）<br>2. ダイアログ起動 & シングルトン管理（`_tag_dialog_instance`: CHALLENGE-005）<br>3. Treeviewダブルクリック & 「Edit Track Tags...」ボタン追加<br>4. 手動編集上書き確認プロンプト（`askyesno`: CHALLENGE-003）<br>5. `TRACK_TAG_UPDATED` 受信時のTreeview即時反映<br>6. Album/Artist 入力欄の未編集トラック連動（CHALLENGE-006） | ダブルクリック/ボタンで編集ダイアログが単一起動し、編集保存後にTreeviewが即時更新され、リッピング中の全UI操作が無効化される | `tests/test_app_view.py`<br>- ダイアログ単一起動<br>- 排他UI制御（全無効化/復元）<br>- 上書き確認ダイアログ分岐<br>- Treeview表示更新 |
| **TASK-006** | implementer | `tests/test_integration.py` | TASK-001<br>TASK-002<br>TASK-003<br>TASK-004<br>TASK-005 | **E2E & 全回帰テスト契約**:<br>1. 仮想CDからのリッピングでトラック毎に異なる全項目タグを設定して実行<br>2. ffprobe による全8項目（title, artist, album, track, disc, date, genre, encoder）の個別タグ埋め込み検証（AC-003）<br>3. NTFS禁止文字を含むタイトルのサニタイズファイル名と完全タグ保持検証（AC-005）<br>4. 既存68テストを含む全テストスイートの完走（AC-006） | 全単体テスト・E2E統合テストが100%成功し、リグレッションが一切ない | `py -3 -m unittest discover -s tests -p "test_*.py" -v`<br>`py -3 -m compileall cdripper tests main.py` |

## 2. Parallelization boundary（並列化境界）

- **完全独立境界**:
  - Group A (基盤): TASK-001 (Domain & Validation)
  - Group B (下流サービス & ダイアログ): TASK-002 (Pipeline) と TASK-003 (UI Dialog)
  - Group C (状態統合): TASK-004 (Presenter)
  - Group D (UI統合): TASK-005 (View)
  - Group E (品質検証): TASK-006 (E2E & Regression)
- **ファイル競合リスクの排除**:
  - 変更対象ファイルが完全に分離されている。
  - 「書き込み担当は一度に1エージェント」の原則を厳格に順守し、TASK-001から順次直列にマージ・テストしていく。

## 3. Integration order（統合順序）

1. **Step 1: Domain & Validation (TASK-001)**
2. **Step 2: Pipeline Integration (TASK-002)**
3. **Step 3: UI Dialog Component (TASK-003)**
4. **Step 4: Presenter Layer (TASK-004)**
5. **Step 5: View Layer Integration (TASK-005)**
6. **Step 6: E2E Integration & Full Regression (TASK-006)**

## 4. Rollback / migration considerations（ロールバック考慮）

- `AudioRipPipeline.rip_disc` の引数 `track_tags` は `Optional[Dict[int, TrackTagData]] = None` として定義されるため、既存コードや外部呼び出し元への破壊的影響はゼロ。
- インメモリSSOT設計のため、DBマイグレーション等は発生しない。
- 障害発生時は、追加ファイルを削除し差分をロールバックすることで即座にリビジョン `2897a50` に復元可能。

## 5. Risks / unresolved items

- **Tkinter ヘッドレスCI環境**: `try...except tk.TclError` によるスキップハンドリングを徹底。
- **ffprobe 実行環境**: FFmpeg/ffprobe バイナリが存在する場合にフルタグ検証を実行。
- **前後曲ナビゲーション仕様**: `< Prev`, `Next >` 移動時は現在の入力値を自動検証＆保存して遷移する。
