# Verification Evidence

- Task ID: cd-ripping-app-001
- Target revision: f55a791
- Environment: Windows 11 (64-bit), Python 3.14.8, FFmpeg 8.1.1, Tkinter (Tk 8.6)
- Auditor: verification-auditor

| Check | Command | Exit code | Pass | Fail | Skip | Log path | Result / notes |
|---|---|---:|---:|---:|---:|---|---|
| Build / Compile | `py -3 -m compileall cdripper tests main.py` | 0 | 42 | 0 | 0 | console | 全Pythonファイル構文・コンパイル正常 |
| Unit tests (Models) | `py -3 -m unittest tests/test_models.py` | 0 | 4 | 0 | 0 | console | イミュータブルモデル・例外設計PASS |
| Unit tests (Speed) | `py -3 -m unittest tests/test_speed_optimizer.py` | 0 | 5 | 0 | 0 | console | USB/SATA/不明フォールバック/maxキャップPASS |
| Unit tests (Virtual Drive) | `py -3 -m unittest tests/test_virtual_drive.py` | 0 | 4 | 0 | 0 | console | 仮想TOC・PCMストリーミング・エラー注入PASS |
| Unit tests (SPTI Drive) | `py -3 -m unittest tests/test_spti_drive.py` | 0 | 5 | 0 | 0 | console | 64bit HANDLE型付け/ドライブ文字検証/TOC境界PASS |
| Unit tests (iTunes API) | `py -3 -m unittest tests/test_itunes_client.py` | 0 | 11 | 0 | 0 | console | URL置換/マルチディスク/SSRF遮断/10MB制限PASS |
| Unit tests (FFmpeg Encoder) | `py -3 -m unittest tests/test_ffmpeg_encoder.py` | 0 | 11 | 0 | 0 | console | NTFSサニタイズ/予約名/CONIN$/stderrドレインPASS |
| Unit tests (Pipeline) | `py -3 -m unittest tests/test_rip_pipeline.py` | 0 | 2 | 0 | 0 | console | min(75, remaining) 端数境界/キャンセル停止PASS |
| Unit tests (Presenter) | `py -3 -m unittest tests/test_presenter.py` | 0 | 3 | 0 | 0 | console | 非同期キュー/ドライブ選択/0件耐性PASS |
| Unit tests (App View) | `py -3 -m unittest tests/test_app_view.py` | 0 | 2 | 0 | 0 | console | High-DPI初期化/エラー時ボタン状態復帰PASS |
| E2E Integration tests | `py -3 -m unittest tests/test_integration.py` | 0 | 1 | 0 | 0 | console | 実FFmpegエンコード + ffprobeによるタグ検証PASS |
| **All Automated Tests** | `py -3 -m unittest discover -s tests -p "test_*.py" -v` | **0** | **48** | **0** | **0** | console | **全48テスト完全成功 (所要時間 1.1s)** |

## Acceptance criteria traceability
| AC ID | Test ID / manual check | Result | Evidence |
|---|---|---|---|
| AC-001 | TC-DRV-01 〜 TC-DRV-05 | PASS | ドライブ一覧表示、選択、未挿入/アクセス拒否例外捕捉、仮想CD切替確認 |
| AC-002 | TC-SPD-01 〜 TC-SPD-05 | PASS | USB 8x、SATA 16x、最大速度上限キャップ、動的減速を確認 |
| AC-003 | TC-MET-01 〜 TC-MET-08 | PASS | iTunes Search/Lookup API、1200x1200bb高解像度画像、マルチディスク、アートワークCanvasプレビュー確認 |
| AC-004 | TC-ENC-01 〜 TC-ENC-08 | PASS | FFmpeg AAC 256kbps出力、ffprobeタグ検証(Title/Artist/Album/Track)、NTFS/予約名サニタイズ確認 |
| AC-005 | TC-RIP-01 〜 TC-RIP-06 | PASS | 進捗通知、min(75, remaining) 端数セクター境界計算、非同期キャンセル、stderrドレインによるデッドロック防止確認 |
| AC-006 | TC-MCK-01 〜 TC-MCK-04 | PASS | 物理CD不要のVirtualCDDriveによる完全自動E2Eリッピング〜エンコード検証確認 |

## Skipped / not run and reason
- TC-DRV-06 (リッピング中の物理トレイイジェクト・USB抜去): 物理的ハードウェア切断が必要なため手動テスト。
- TC-NFR-01 (高DPI環境での実画面目視確認): SetProcessDpiAwarenessは自動検証済み。実ディスプレイ目視は手動確認。

## Flaky tests / test quality concerns
- なし（全48テストが決定論的・高速・安定にパス）。

## Auditor verdict: PASS
