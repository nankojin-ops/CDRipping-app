# Review / QA Findings Register

- Task ID: cd-ripping-app-002
- Review round: 1
- Target revision: 2897a50
- Frozen diff path: artifacts/agent-quality/cd-ripping-app-002/review.diff

| Issue ID | Source agent | Severity | Location | Reproduction / evidence | Impact | Root cause | Fix / disposition | Retest | Status |
|---|---|---|---|---|---|---|---|---|---|
| FIND-001 | code-reviewer | P2 | `cdripper/ui/presenter.py#L195` | release_year="Unknown Year" のアルバムを適用後にダイアログ保存 | ValueError: Invalid date format: 'Unknown Year' が発生し保存不可 | 非4桁西暦文字列をそのままdateにセットしている | 4桁数字以外の年代表記は空文字 "" にサニタイズして設定 | `test_apply_metadata_with_invalid_year_formats` PASS | RESOLVED |
| FIND-002 | code-reviewer | P2 | `cdripper/ui/tag_dialog.py#L210` | txt_track_total を空欄にして保存 | タグが "5/1" に強制変換される | trk_total == 0 の時に max(1, trk_total) で 1 に潰している | 0 の場合はそのまま 0 を渡し、単一番号 "X" を維持 | `test_save_empty_track_total_preserves_single_number` PASS | RESOLVED |
| FIND-003 | code-reviewer | P2 | `cdripper/ui/tag_dialog.py#L251` | 未変更のまま < Prev / Next > で曲送り | 未編集トラックがすべて is_customized=True に化ける | ナビゲーション移動時に差分判定せず無条件保存している | 現在のタグと比較し差分がある場合のみ保存して遷移 | `test_navigation_without_modification_preserves_uncustomized` PASS | RESOLVED |
| SEC-008 | security-reviewer | P2 | `cdripper/pipeline/ffmpeg_encoder.py#L31` | sanitize_filename("CON .") | 予約名チェックがバイパスされ "CON" が返る | ドット・空白除去処理が予約名判定の後にある | ドット・空白除去を予約名照合の前に実行する | `test_sanitize_filename_reserved_with_trailing_spaces_and_dots` PASS | RESOLVED |
| SEC-009 | security-reviewer | P2 | `cdripper/pipeline/ffmpeg_encoder.py#L30` | sanitize_filename("Track\nName") | 制御文字が残りWindowsファイル作成時にOSError | 置換正規表現に制御文字範囲（\x00-\x1f\x7f）が含まれていない | 置換正規表現を [\x00-\x1f\x7f\\/*?:"<>|] に拡張 | `test_sanitize_filename_control_characters_replaced` PASS | RESOLVED |
| SEC-010 | security-reviewer | P2 | `cdripper/ui/presenter.py#L240` | メイン画面のAlbum/Artist入力欄に制御文字や長大文字列をペースト | 未編集トラックに未サニタイズ文字列が反映される | sync_album_artist_to_uncustomized で sanitize_tag_string を呼んでいない | sanitize_tag_string を適用してからモデルに反映 | `test_sync_album_artist_sanitization` PASS | RESOLVED |
| FIND-004 | code-reviewer | P3 | `cdripper/ui/tag_dialog.py#L262` | track_number がトラック一覧に含まれない状態でナビゲーション呼出 | ValueError: x is not in list リスク | インデックス取得前の存在チェックが欠落 | if self.track_number not in track_nums: return ガードを保存前に配置 | `test_navigation_with_invalid_track_number_safe_guard` PASS | RESOLVED |
| FIND-005 | code-reviewer | P3 | `cdripper/domain/models.py#L177` | TrackTagData.create_default(title="   ") | タイトルが空文字 "" になる | bool("   ") が True のため strip 後評価が抜けている | title=title.strip() if (title and title.strip()) else ... に修正 | `test_create_default_whitespace_title_fallback` PASS | RESOLVED |
| SEC-011 | security-reviewer | P3 | `cdripper/pipeline/rip_pipeline.py#L147` | 複数トラックで同一トラック番号が設定された場合 | 先行トラックの出力ファイルが後続トラックで上書きされる | ファイル名重複チェックの欠落 | seen_output_paths で同一セッション内の出力パス重複を検出し `_1.m4a` サフィックスでユニーク化 | `test_rip_disc_avoids_output_file_collision` PASS | RESOLVED |

## Disagreements / adjudication
- なし。全指摘（P2: 6件, P3: 3件）を是正対象として採用し、実装修正およびテスト追加を完了。

## Accepted risks
- なし。

## Round summary
- P0: 0
- P1: 0
- P2: 0 (6 resolved)
- P3: 0 (3 resolved)
- Open: 0
- Closed with evidence: 9
