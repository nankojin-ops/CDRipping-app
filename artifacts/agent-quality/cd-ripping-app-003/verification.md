# Verification Evidence

- Task ID: `cd-ripping-app-003`
- Target Revision: `2897a50` + cd-ripping-app-003 変更セット（作業ツリー差分）
- Review Round: Round 2 (Post-Remediation Verification)
- Environment: Windows 11 (64-bit), Python 3.14.0, FFmpeg 8.1.1, Tkinter (Tk 8.6), Pillow 11.x
- Auditor: 親エージェント & Independent Verification Auditor

---

## 1. 非破壊コマンド実行結果サマリー (Round 2)

| Check | Command | Exit code | Pass | Fail | Skip | Log path / Output summary | Result / notes |
|---|---|---:|---:|---:|---:|---|---|
| Build / Compile | `py -3 -m compileall cdripper tests main.py` | 0 | - | 0 | 0 | 全パッケージ構文チェック完了 (エラーなし) | **PASS** |
| Unit: ArtworkHelper | `py -3 -m unittest tests/test_artwork_helper.py -v` | 0 | 15 | 0 | 0 | Ran 15 tests in 0.204s (SEC-002, CR-001, FIND-002, FIND-007, Bomb検証含む) | **PASS** |
| Unit / UI: AlbumTagDialog | `py -3 -m unittest tests/test_album_tag_dialog.py -v` | 0 | 7 | 0 | 0 | Ran 7 tests in 0.463s (SEC-001事前チェック, AC-002, AC-004, BND, NEG検証含む) | **PASS** |
| Unit: TrackTagData & Validation | `py -3 -m unittest tests/test_track_tag_data.py -v` | 0 | 15 | 0 | 0 | Ran 15 tests in 0.002s (AC-005, REG-002, REG-003, REG-004検証含む) | **PASS** |
| Unit / UI: TrackTagDialog | `py -3 -m unittest tests/test_tag_dialog.py -v` | 0 | 9 | 0 | 0 | Ran 9 tests in 0.579s (AC-006, FIND-001消去バグ解消検証含む) | **PASS** |
| Unit / Int: Presenter | `py -3 -m unittest tests/test_presenter.py -v` | 0 | 6 | 0 | 0 | Ran 6 tests in 0.234s (AC-003, FIND-003, FIND-004一括更新・保護検証含む) | **PASS** |
| Unit / UI: AppView | `py -3 -m unittest tests/test_app_view.py -v` | 0 | 4 | 0 | 0 | Ran 4 tests in 0.325s (AC-001 TclError解消, FIND-005, FIND-006検証含む) | **PASS** |
| Unit / Int: Pipeline | `py -3 -m unittest tests/test_rip_pipeline.py -v` | 0 | 5 | 0 | 0 | Ran 5 tests in 0.108s (AC-005 album_artist & artwork埋め込み検証含む) | **PASS** |
| Full Regression Suite | `py -3 -m unittest discover -s tests -p "test_*.py" -v` | 0 | 123 | 0 | 0 | **Ran 123 tests in 2.354s (全123テスト100%成功)** | **PASS** |

---

## 2. 是正指摘（SEC-001, CR-001, SEC-002）の再検証エビデンス

| Issue ID | 重大度 | 是正内容 | 検証テスト | 判定 |
|---|---|---|---|:---:|
| **SEC-001** | P2 | 巨大ファイル選択時のメモリ枯渇DoS防止のため、`os.path.getsize(path)` で事前判定し `open()` を呼ばずにエラー表示 | `tests/test_album_tag_dialog.py::TestAlbumTagDialog::test_on_choose_artwork_rejects_oversized_file_pre_check` | **PASS** |
| **CR-001** | P3 | リサイズ・EXIF回転後の不透過PNG画像が JPEG ではなく一貫して処理されるようアルファチャンネル有無判定に統一 | `tests/test_artwork_helper.py::TestArtworkHelper::test_normalize_opaque_png_converts_to_jpeg` | **PASS** |
| **SEC-002** | P3 | `load_and_resize_image` 入力引数への 10MB 超過ガード追加による多層防御 | `tests/test_artwork_helper.py::TestArtworkHelper::test_load_and_resize_image_rejects_oversized_bytes` | **PASS** |

---

## 3. 受入条件トレーサビリティ (AC-001 〜 AC-007)

| AC ID | 要件内容 | 検証方法 | 実績 | 判定 |
|---|---|---|---|:---:|
| **AC-001** | iTunes APIからアルバム情報（JPEG画像含む）を取得した際、メイン画面のArtworkキャンバスに縮小されたカバーアートが正しくプレビュー表示されること (TclError解消) | `tests/test_app_view.py` (`test_jpeg_artwork_rendering_no_tcl_error`), `tests/test_artwork_helper.py` (`test_normalize_valid_jpeg`, `test_scale_down_exceeds_max_dimension`) | Pillow経由でアスペクト比維持のサムネイル化と ImageTk.PhotoImage への安全変換が行われ、`_draw_no_artwork()` に倒れず Canvas (150x150) に縮小描画されることを確認。 | **PASS** |
| **AC-002** | メイン画面からアルバム編集ダイアログを開き、ディスク番号・アルバムアーティスト・アルバム・リリース日・ジャンル・アルバムアートの各項目を編集できること | `tests/test_album_tag_dialog.py` (`test_dialog_field_mapping`, `test_save_valid_data_invokes_callback`, `test_safe_close_releases_grab`), `tests/test_app_view.py` | メイン画面「Edit Album Tags...」および Canvas クリックから `AlbumTagEditDialog` が起動し、全6項目およびアートワークの初期ロード、編集、保存、グラブ解放が動作することを確認。 | **PASS** |
| **AC-003** | アルバム単位編集ダイアログで保存を実行した際、全トラックのタグ情報およびアルバムアートが一括更新され、トラック固有情報が保護されること | `tests/test_presenter.py` (`test_update_album_tags_batch_update_and_protection`, `test_update_album_tags_preserves_customized_flags`), `tests/test_app_view.py` (`test_album_tags_updated_syncs_ui_entries`) | `update_album_tags` により全トラックの disc, album_artist, album, date, genre が更新され、個別 title, track_number, 個別 artist, `is_customized` フラグが保護され、メイン画面 UI に即時同期されることを確認。 | **PASS** |
| **AC-004** | アルバム編集ダイアログからローカル画像（JPEG/PNG/WEBP）を選択して設定またはクリアでき、プレビューおよびリッピング生成ファイルに反映されること | `tests/test_artwork_helper.py` (`test_normalize_valid_png`, `test_normalize_webp_converts_to_jpeg`, `test_normalize_cmyk_converts_to_rgb`, `test_normalize_exif_orientation_correction`), `tests/test_album_tag_dialog.py` (`test_clear_artwork_resets_data`) | WEBP/BMP/CMYK から RGB JPEG (透過時はPNG) への正規化、EXIF 回転補正、クリアボタンによるプレースホルダ復帰を確認。 | **PASS** |
| **AC-005** | アルバム編集で設定した `album_artist` や各タグ、およびアルバムアートが生成された音声ファイルのメタデータに正しく埋め込まれること | `tests/test_track_tag_data.py` (`test_album_artist_in_metadata_dict`), `tests/test_rip_pipeline.py` (`test_rip_pipeline_embeds_album_artist_and_artwork`) | `to_metadata_dict` に `"album_artist"` が出力され、`AudioRipPipeline` から FFmpeg セッションに `-metadata album_artist="..."` と一時カバー画像が渡されることを確認。 | **PASS** |
| **AC-006** | 個別トラックタグ編集ダイアログで保存した際にも `album_artist` が保持・編集可能であること (FIND-001) | `tests/test_tag_dialog.py` (`test_dialog_field_mapping_includes_album_artist`, `test_save_preserves_album_artist_on_title_edit`, `test_save_updates_edited_album_artist`) | `TrackTagEditDialog` に「Album Artist:」が追加され、曲名編集時にも値が消失せず保持・編集できることを確認。 | **PASS** |
| **AC-007** | 既存機能の無回帰 | `py -3 -m unittest discover -s tests -p "test_*.py" -v` | 既存100テストを含む全123テストが100%成功（リグレッションなし）。 | **PASS** |
