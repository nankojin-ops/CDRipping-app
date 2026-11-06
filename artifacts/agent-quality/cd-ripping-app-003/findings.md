# Review & Audit Findings

- Task ID: `cd-ripping-app-003`
- Review Round: Round 2 (Post-Remediation Verification)
- Review Date: 2026-11-06

---

## 統合指摘サマリー

| Issue ID | 重大度 | 観点 | 対象ファイル:行 | 概要 | 処置・是正状況 | 判定 |
|---|---|---|---|---|---|:---:|
| **SEC-001** | **P2 (Medium)** | 可用性 / リソース枯渇 (DoS) | `cdripper/ui/album_tag_dialog.py:161` | アートワーク選択時にメモリ全量読み込み前にサイズ検証が行われておらず、数GB超ファイル選択時に MemoryError / スラッシングのリスク | **解消済み**: `os.path.getsize(path)` による事前検査および `f.read(MAX_ARTWORK_SIZE_BYTES + 1)` 上限読み込みを実装。`tests/test_album_tag_dialog.py` (`test_on_choose_artwork_rejects_oversized_file_pre_check`) にて事前チェック動作（ファイルオープンを行わずに拒絶）を実証。 | **CLOSED** |
| **CR-001** | **P3 (Low)** | ロジック / 画像エンコードの一貫性 | `cdripper/ui/artwork_helper.py:45` | リサイズやEXIF回転後の画像オブジェクトで `img.format` が None になるため、不透過PNGの出力フォーマット（PNG vs JPEG）の揺れが生じる | **解消済み**: 透過情報（`"A" in img.mode`）の有無に基づいて一貫して PNG / RGB JPEG にエンコードするよう統一。`tests/test_artwork_helper.py` (`test_normalize_opaque_png_converts_to_jpeg`) にて検証完了。 | **CLOSED** |
| **SEC-002** | **P3 (Low)** | 入力検証 / 多層防御 | `cdripper/ui/artwork_helper.py:59` | `load_and_resize_image` の先頭ガードに `MAX_ARTWORK_SIZE_BYTES` (10MB) チェックが不足 | **解消済み**: 入力サイズ上限ガード（`len(image_bytes) > MAX_ARTWORK_SIZE_BYTES` で `None` 返却）を追加。`tests/test_artwork_helper.py` (`test_load_and_resize_image_rejects_oversized_bytes`) にて検証完了。 | **CLOSED** |
| **SEC-003** | **P3 (Low)** | リソースリーク防御 | `cdripper/pipeline/ffmpeg_encoder.py:101` | `EncoderSession` の異常終了・GC破棄時の一時カバーファイル残存リスク | **リスク受容・記録**: 現状 `rip_pipeline.py` の `try...finally` で確実に `cancel_and_cleanup` または `finish` が呼ばれており実害なし。次回リファクタリング時に対応予定。 | **ACCEPTED** |

---

## 指摘是正の詳細

### SEC-001: アートワーク画像選択時の巨大ファイル事前サイズ検査不足 (P2 - Medium)
- **処置内容**:
  `cdripper/ui/album_tag_dialog.py` の `_on_choose_artwork` において、`os.path.getsize(path)` でファイルサイズを事前取得。`MAX_ARTWORK_SIZE_BYTES` (10MB) を超過している場合は `open()` を実行せずにエラーダイアログを表示してリターンする。さらに念のため `f.read(MAX_ARTWORK_SIZE_BYTES + 1)` で読み込み量に上限を設けた。
- **検証結果**:
  `tests/test_album_tag_dialog.py::TestAlbumTagDialog::test_on_choose_artwork_rejects_oversized_file_pre_check` にて、50MBのダミーファイル選択時に `builtins.open` が一切呼ばれず、即座にエラーメッセージが表示されることを確認。PASS。

### CR-001: 不透過PNG画像正規化時の出力フォーマットの不整合 (P3 - Low)
- **処置内容**:
  `cdripper/ui/artwork_helper.py` の `normalize_artwork` において、`if "A" in img.mode or img.format == "PNG":` を `if "A" in img.mode:` に統一。透過がある場合は RGBA PNG、それ以外（不透過PNG、JPEG、WEBP、BMP、TIFF等）はすべて標準 RGB JPEG (quality=90) にエンコードされるよう一貫化。
- **検証結果**:
  `tests/test_artwork_helper.py::TestArtworkHelper::test_normalize_opaque_png_converts_to_jpeg` にて、不透過 PNG 入力が確実に RGB JPEG に正規化されることを確認。PASS。

### SEC-002: `load_and_resize_image` における入力サイズ多層防御の追加 (P3 - Low)
- **処置内容**:
  `cdripper/ui/artwork_helper.py` の `load_and_resize_image` 先頭に `if not image_bytes or len(image_bytes) > MAX_ARTWORK_SIZE_BYTES: return None` を追加。
- **検証結果**:
  `tests/test_artwork_helper.py::TestArtworkHelper::test_load_and_resize_image_rejects_oversized_bytes` にて、10MB超のバイト列に対して即座に `None` を返却することを確認。PASS。
