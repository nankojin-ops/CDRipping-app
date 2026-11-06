# Findings and Remediation Triage: Task `cd-ripping-app-004`

- Task ID: `cd-ripping-app-004`
- Date: 2026-11-06
- Gate: Gate E (指摘統合と是正トリアージ)
- Target Revision: `0a3915c` + 凍結差分 `review.diff`

---

## 1. 指摘事項統合一覧 (Consolidated Findings)

| Issue ID | 重要度 | 出典 | 対象ファイル:行 | 概要 | 是正方針 |
|---|---|---|---|---|---|
| **FIND-SEC-012** | **P2 (Medium)** | Security Reviewer | `cdripper/pipeline/rip_pipeline.py:130` | 深層ベースディレクトリ（100文字以上等）設定時、合計パス長が MAX_PATH (260文字) を超過して OS エラーを起こす可能性 | **修正**: `resolve_track_output_path` の末尾で、フルパス長が 250 文字を超える場合にファイル名ベース部を切り詰めて 255 文字以内に収める多重防護ガードを追加。 |
| **FIND-SEC-013 / CR-002** | **P3 (Low)** | Code Reviewer & Security Reviewer | `tests/test_rip_pipeline.py:380` | ディスク上既存ファイル衝突回避テストが関数ローカルのループ検証にとどまり、`AudioRipPipeline.rip_disc` 経由の結合検証になっていない | **修正**: モックドライブとモックエンコーダを用いた `AudioRipPipeline.rip_disc` 呼び出しにより、既存ファイル存在時に `_1.m4a` としてエンコーダに渡されることを検証するテストを追加。 |
| **FIND-SEC-014 / CR-001** | **P3 (Low)** | Code Reviewer & Security Reviewer | `tests/test_rip_pipeline.py:172` | `if __name__ == "__main__": unittest.main()` がファイル中間にあり、直接スクリプト実行時に後続のテストクラスがスキップされる | **修正**: `if __name__ == "__main__": unittest.main()` をファイル最末尾（ファイル末尾行）へ移動。 |
| **FIND-CR-003** | **P3 (Low)** | Code Reviewer | `cdripper/pipeline/rip_pipeline.py:118` | カスタムテンプレートで `{track_number}`（`track_num` の正式名エイリアス）が指定された場合に未定義キーとみなされる | **修正**: `fmt_kwargs` に `"track_number": trk_num` を追加して利便性を向上。 |
| **FIND-SEC-015** | **P3 (Low)** | Security Reviewer | `cdripper/pipeline/ffmpeg_encoder.py:37` | Windows予約デバイス名正規表現で `COM0` と `LPT0` が `[1-9]` のためマッチしない | **修正**: 正規表現パターンを `COM[0-9]|LPT[0-9]` に更新し、単体テストを追加。 |

---

## 2. 是正計画 (Remediation Plan)

1. `cdripper/pipeline/rip_pipeline.py`:
   - `fmt_kwargs` に `"track_number": trk_num` を追加（FIND-CR-003）。
   - `resolve_track_output_path` の返却直前に合計パス長ガード（MAX_PATH 255文字抑制）を追加（FIND-SEC-012）。
2. `cdripper/pipeline/ffmpeg_encoder.py`:
   - `sanitize_filename` の予約名正規表現を `COM[0-9]|LPT[0-9]` に更新（FIND-SEC-015）。
3. `tests/test_rip_pipeline.py`:
   - `if __name__ == "__main__": unittest.main()` をファイル最末尾へ移動（FIND-SEC-014 / CR-001）。
   - `AudioRipPipeline.rip_disc` 経由での既存ファイル衝突連番付与テスト `test_rip_disc_avoids_collision_with_existing_file_on_disk` を追加（FIND-SEC-013 / CR-002）。
   - `{track_number}` エイリアスおよび深層ベースディレクトリ（MAX_PATH抑制）のテストを追加。
4. `tests/test_ffmpeg_encoder.py`:
   - `COM0` および `LPT0` の予約名サニタイズテストを追加。
5. 是正後の再テスト・再差分作成と検証。
