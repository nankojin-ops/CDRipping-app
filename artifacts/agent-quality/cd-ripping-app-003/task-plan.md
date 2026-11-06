# Implementation Plan

- Task ID: `cd-ripping-app-003`
- Design status: Approved (Revision 2 - FIND-001〜007 反映済み)
- QA matrix status: Approved (40 test cases created)
- Base revision: `2897a50`

---

## 1. タスク一覧テーブル (Task Breakdown)

| Task | Owner agent | Scope / files | Depends on | Contract / Responsibility | Done when | Tests & Verification |
|---|---|---|---|---|---|---|
| **TASK-001** | implementer | `cdripper/domain/models.py`<br>`cdripper/ui/artwork_helper.py` (新規) | None | **ドメインモデル拡張 & アートワーク画像処理基盤契約**:<br>1. `models.py`:<br>- `AlbumTagData` (`@dataclass(frozen=True)`): `disc_number`, `total_discs`, `album_artist`, `album`, `date`, `genre`, `artwork_data`<br>- `TrackTagData`: `album_artist: str = ""` 追加、`to_metadata_dict()` に空文字除外で `"album_artist": self.album_artist.strip()` 出力、`create_default()` に引数追加（完全後方互換）<br>- `AlbumMetadata`: `album_artist: str = ""` 追加<br>2. `artwork_helper.py` (新規):<br>- `normalize_artwork(image_bytes, max_dimension=1400)`: 10MB制限, Decompression Bomb防止 (`MAX_IMAGE_PIXELS=25_000_000`), EXIF Orientation補正 (`ImageOps.exif_transpose`: FIND-007), RGB JPEG/RGBA PNG 正規化 (FIND-002)<br>- `load_and_resize_image(image_bytes, max_size=(150, 150))`<br>- `create_photo_image(image_bytes, max_size=(150, 150))` | 不変データモデルが定義され、JPEG/PNG/WEBP/BMPが安全に正規化され、Pillow経由で Tkinter PhotoImage が生成できる | `tests/test_track_tag_data.py`<br>`tests/test_artwork_helper.py` (新規)<br>- 不変性・プロパティ確認<br>- 画像正規化・縮小プレビュー<br>- EXIF回転補正 (FIND-007)<br>- 10MB超・破損・Bomb画像の遮断 |
| **TASK-002** | implementer | `cdripper/ui/tag_dialog.py` | TASK-001 | **個別トラックタグ編集ダイアログでの Album Artist 維持・編集契約**:<br>1. 「Album Artist:」入力欄 (`self.txt_album_artist`) を追加<br>2. `_load_track_data` で `track_tag.album_artist` を読み込み<br>3. `_validate_and_build_model` で `album_artist` をサニタイズして取得し `TrackTagData(..., album_artist=...)` を構築<br>4. 個別トラック編集保存時に `album_artist` が消失するバグを解消 (FIND-001) | 個別トラック編集ダイアログで `album_artist` が表示・編集でき、保存後も値が保持される | `tests/test_tag_dialog.py`<br>- `album_artist` 初期表示<br>- 入力編集・サニタイズ・保存検証<br>- 前後曲移動時の値保持確認 |
| **TASK-003** | implementer | `cdripper/ui/album_tag_dialog.py` (新規) | TASK-001 | **アルバム単位編集ダイアログコンポーネント契約**:<br>1. `AlbumTagEditDialog(tk.Toplevel)`:<br>- 6項目入力（Album Title, Album Artist, Disc No, Total Discs, Year/Date, Genre）<br>- アートワーク プレビュー Canvas (120x120), 「Choose Artwork...」ボタン, 「Clear Artwork」ボタン<br>- 画像選択時の 10MB 検証 & `normalize_artwork` による変換と即時プレビュー更新<br>- 画像クリア時のプレースホルダ描画<br>- 入力検証: `parse_and_validate_fractional_tag(..., "disc")`, `validate_date_string`, `sanitize_tag_string`<br>- モーダルライフサイクル: `transient`, `grab_set`, `protocol("WM_DELETE_WINDOW")`, 安全な `grab_release` (FIND-005) | モーダルダイアログでアルバム全項目およびアートワークの表示・編集・検証・クリア・保存が行え、確実に破棄される | `tests/test_album_tag_dialog.py` (新規)<br>- 初期値ロード<br>- 不正ディスク番号・日付のエラー遮断<br>- 画像選択・正規化・クリア検証<br>- `grab_release` ライフサイクル |
| **TASK-004** | implementer | `cdripper/ui/presenter.py` | TASK-001<br>TASK-002 | **Presenter層アルバム同期・SSOT管理拡張契約**:<br>1. `PresenterEvent.ALBUM_TAGS_UPDATED = "ALBUM_TAGS_UPDATED"` 追加<br>2. `update_album_tags(album_data: AlbumTagData)` 実装:<br>- リッピング排他ガード (`if self.is_ripping: return`)<br>- `self.selected_disc = album_data.disc_number` 同期更新 (FIND-004)<br>- `self.current_album` の合成・更新<br>- `self.track_tags` (全トラック) の一括更新: `disc_number`, `total_discs`, `album_artist`, `album`, `date`, `genre` を反映<br>- トラック固有情報 (`title`, `track_number`, `total_tracks`) の完全保護<br>- 個別アーティスト `artist` の保護: トラック固有アーティストが設定されている場合は上書きせず保護<br>- `is_customized` の保護: 一律 True にせず既存値を維持 (FIND-003)<br>- イベント通知: 各トラックの `TRACK_TAG_UPDATED` および `ALBUM_TAGS_UPDATED`<br>3. `apply_album_metadata` (iTunes検索): `normalize_artwork` 適用と各トラックへの `album_artist` 反映 | アルバム編集保存時に全トラックへ共通タグが一括反映され、トラック固有情報が保護され、イベントが発行される | `tests/test_presenter.py`<br>- 全トラック一括反映確認<br>- 個別タイトル・個別artist保護確認<br>- `is_customized` 非汚染確認 (FIND-003)<br>- `selected_disc` 更新確認 (FIND-004)<br>- リッピング中ガード確認 |
| **TASK-005** | implementer | `cdripper/ui/app_view.py` | TASK-001<br>TASK-003<br>TASK-004 | **メインView統合 & アートワーク表示不具合修正契約**:<br>1. アートワーク描画修正: `ArtworkHelper.create_photo_image` を使用し、iTunes から取得した JPEG やローカル画像が Canvas (150x150) に縮小描画されるよう修正 (AC-001)<br>2. アルバム編集トリガー追加: `ctrl_frame` に「Edit Album Tags...」ボタン追加、アートワーク Canvas クリック (`<Button-1>`) バインド (AC-002)<br>3. ダイアログ相互排他制御: `_album_dialog_instance` と `_tag_dialog_instance` の二重起動抑止・リフト (FIND-005)<br>4. リッピング中制御: `_set_ripping_ui_state` でアルバム編集ボタンを `DISABLED` 化 (FIND-005)<br>5. メイン画面同期: `ALBUM_TAGS_UPDATED` 受信時に `txt_album`, `txt_artist`, アートワーク Canvas を即時同期更新 (FIND-006) | iTunes JPEG アートワークが Canvas に表示され、アルバム編集ダイアログが排他起動し、編集内容がメイン画面に即座に反映される | `tests/test_app_view.py`<br>- JPEG アートワーク描画成功確認<br>- ダイアログ単一起動 & 相互排他 (FIND-005)<br>- リッピング中 UI ロック確認<br>- `ALBUM_TAGS_UPDATED` 受信時の UI フィールド即時更新確認 (FIND-006) |
| **TASK-006** | implementer | `cdripper/pipeline/rip_pipeline.py`<br>`tests/test_rip_pipeline.py`<br>`tests/test_integration.py` | TASK-001<br>TASK-004<br>TASK-005 | **パイプライン統合 & 全体E2E・無回帰検証契約**:<br>1. `AudioRipPipeline.rip_disc`: 手動アルバム編集後の `track_tags` から `album_artist` が FFmpeg の `-metadata album_artist="..."` に渡されることを確認<br>2. 手動設定または iTunes 取得されたアルバムアートがエンコーダセッションに渡され、一時ファイル経由で `-disposition:v:0 attached_pic` として埋め込まれることを検証 (AC-005)<br>3. 仮想CDからのリッピングによるE2E統合検証<br>4. 既存100件のテストスイート全件実行（100%成功維持: AC-007） | アルバム単位編集後のリッピングで全トラックに `album_artist` とアートワークが埋め込まれ、全テストが合格する | `tests/test_rip_pipeline.py`<br>`tests/test_integration.py`<br>`py -3 -m unittest discover -s tests -p "test_*.py" -v`<br>`py -3 -m compileall cdripper tests main.py` |

---

## 2. 受入条件 (AC) および Design Challenge 指摘 (FIND) の対応マトリクス

| 識別子 | 内容 | 対応タスク | 検証テスト |
|---|---|---|---|
| **AC-001** | iTunes APIからアルバム情報（JPEG画像含む）を取得した際、メイン画面のArtworkキャンバスに縮小されたカバーアートが正しくプレビュー表示されること | TASK-001, TASK-005 | `test_artwork_helper.py`, `test_app_view.py` |
| **AC-002** | メイン画面からアルバム編集ダイアログを開き、ディスク番号・アルバムアーティスト・アルバム・リリース日・ジャンル・アルバムアートの各項目を編集できること | TASK-003, TASK-005 | `test_album_tag_dialog.py`, `test_app_view.py` |
| **AC-003** | アルバム単位編集ダイアログで保存を実行した際、全トラックのタグ情報およびアルバムアートが一括更新され、トラック固有情報が保護されること | TASK-004 | `test_presenter.py` |
| **AC-004** | アルバム編集ダイアログからローカル画像を選択して設定またはクリアでき、プレビューおよびリッピング生成ファイルに反映されること | TASK-001, TASK-003 | `test_artwork_helper.py`, `test_album_tag_dialog.py` |
| **AC-005** | アルバム編集で設定した `album_artist` や各タグ、およびアルバムアートが生成された音声ファイルのメタデータに正しく埋め込まれること | TASK-001, TASK-004, TASK-006 | `test_ffmpeg_encoder.py`, `test_rip_pipeline.py`, `test_integration.py` |
| **AC-006** | 個別トラックタグ編集ダイアログで保存した際にも `album_artist` が保持・編集可能であること (FIND-001) | TASK-002 | `test_tag_dialog.py` |
| **AC-007** | 既存機能の無回帰（全100テストがPASSすること） | TASK-006 | 全テストスイート完走 |
| **FIND-001** | `TrackTagEditDialog` での `album_artist` 消失防止と編集対応 | TASK-002 | `test_tag_dialog.py` |
| **FIND-002** | アートワーク正規化と FFmpeg MP4 互換性保証（WEBP/BMP/CMYK対応、Decompression Bomb対策、RGB JPEG/PNG変換） | TASK-001 | `test_artwork_helper.py` |
| **FIND-003** | `update_album_tags` 実行時の一律 `is_customized=True` 付与防止 | TASK-004 | `test_presenter.py` |
| **FIND-004** | `update_album_tags` 実行時の `Presenter.selected_disc` 同期更新 | TASK-004 | `test_presenter.py` |
| **FIND-005** | `AlbumTagEditDialog` と `TrackTagEditDialog` の相互排他制御およびリッピング中排他ガード | TASK-003, TASK-005 | `test_album_tag_dialog.py`, `test_app_view.py` |
| **FIND-006** | `ALBUM_TAGS_UPDATED` 発生時のメイン画面 `txt_album` / `txt_artist` 即時同期更新 | TASK-004, TASK-005 | `test_app_view.py` |
| **FIND-007** | アートワークデコード時の EXIF Orientation 補正 (`exif_transpose`) | TASK-001 | `test_artwork_helper.py` |

---

## 3. 並列化境界 (Parallelization Boundary) とファイル衝突リスク

- **並列グループ分離**:
  - **Group A (基盤)**: TASK-001 (`models.py`, `artwork_helper.py`)
  - **Group B (UIコンポーネント)**: TASK-002 (`tag_dialog.py`) と TASK-003 (`album_tag_dialog.py`) ※TASK-001完了後に完全並列可能（ファイル分離）
  - **Group C (状態統合)**: TASK-004 (`presenter.py`) ※TASK-001, TASK-002完了後
  - **Group D (メインUI統合)**: TASK-005 (`app_view.py`) ※TASK-003, TASK-004完了後
  - **Group E (統合検証)**: TASK-006 (`test_rip_pipeline.py`, `test_integration.py`) ※TASK-005完了後
- **衝突リスク制御**:
  - 親エージェント運用規約「書き込み担当は一度に1エージェント」に従い、Task 1から順次直列にマージ・テストしていくことを基本とします。

---

## 4. 統合順序 (Integration Order) とマイルストーン

1. **Step 1: ドメイン & 画像基盤 (TASK-001)**
   - `AlbumTagData`、`TrackTagData` 拡張、`ArtworkHelper` 実装と単体テスト完了。
2. **Step 2: 個別トラックダイアログ対応 (TASK-002)**
   - `TrackTagEditDialog` で `album_artist` が編集・保持されることを確認 (FIND-001解消)。
3. **Step 3: アルバム編集ダイアログ新設 (TASK-003)**
   - `AlbumTagEditDialog` の単体動作、バリデーション、画像正規化・クリアを確認。
4. **Step 4: Presenter SSOT統合 (TASK-004)**
   - アルバム一括更新、トラック保護、`selected_disc` 同期、イベント発行を確認。
5. **Step 5: メイン画面統合 & アートワーク表示修正 (TASK-005)**
   - iTunes JPEG 表示修正、ダイアログ起動、相互排他、メイン画面同期を確認。
6. **Step 6: リッピング統合 & 全体無回帰検証 (TASK-006)**
   - 音声ファイルへのメタデータ & アートワーク埋め込み検証、全既存テストパス確認。

---

## 5. ロールバック手順と安全性考慮 (Rollback & Safety Considerations)

1. **後方互換性の維持**:
   - `TrackTagData.album_artist` はデフォルト引数 `""` を持つため、既存コードのシグネチャを一切壊しません。
   - `AlbumMetadata.album_artist` もデフォルト値 `""` であり、外部連携に破壊的影響を与えません。
2. **ロールバック手順**:
   - 新規作成ファイル (`cdripper/ui/artwork_helper.py`, `cdripper/ui/album_tag_dialog.py`, `tests/test_artwork_helper.py`, `tests/test_album_tag_dialog.py`) を削除。
   - 変更されたファイル (`cdripper/domain/models.py`, `cdripper/ui/tag_dialog.py`, `cdripper/ui/presenter.py`, `cdripper/ui/app_view.py`) を `git checkout` で戻すことで、即座に以前の正常動作リビジョンに復元可能です。
3. **ランタイム安全性**:
   - 画像デコード時のメモリ枯渇を防ぐため、`MAX_IMAGE_PIXELS = 25_000_000` (Decompression Bomb 対策) および 10MB 入力サイズ制限を徹底。
   - EXIF Orientation を補正し、不正な画像フォーマットは `None` を返して「No Artwork」に安全フォールバック。
   - Tkinter のダイアログ破棄時には `try...finally` で確実に `grab_release()` を実行し、グラブロックを防止。

---

## 6. リスクと未決事項 (Risks & Unresolved Items)

1. **Tkinter ヘッドレステスト環境**:
   - ヘッドレス環境では `tk.Tk()` 実行時に `TclError` が発生する可能性があるため、既存テスト同様 `try...except tk.TclError:` によるスキップハンドリングを徹底します。
2. **Pillow バージョン差異**:
   - `Image.Resampling.LANCZOS` と旧 `Image.LANCZOS` の両方をサポートする `getattr(Image.Resampling, "LANCZOS", Image.LANCZOS)` 互換コードを採用します。
