# Implementation Plan

- Task ID: cd-ripping-app-001
- Design status: Approved
- QA matrix status: Pending QA Test Designer

| Task | Owner agent | Scope / files | Depends on | Contract | Done when | Tests |
|---|---|---|---|---|---|---|
| **TASK-001** | implementer | `cdripper/domain/__init__.py`<br>`cdripper/domain/models.py`<br>`cdripper/domain/exceptions.py` | なし | 全データクラス（`DriveInfo`, `TrackTOC`, `DiscTOC`, `TrackMetadata`, `AlbumMetadata`, `RipConfig`, `RipProgress`, `BusType`, `EncodeFormat`）および例外階層の定義 | 型定義・不変性（frozen）・バリデーションが正しく動作すること | `tests/test_models.py` |
| **TASK-002** | implementer | `cdripper/hardware/__init__.py`<br>`cdripper/hardware/interface.py`<br>`cdripper/hardware/virtual_drive.py` | TASK-001 | ドライブ制御基底 `ICDDrive` およびCI/テスト用 `VirtualCDDrive`（無音・トーンPCM生成、仮想TOC）の実装 | 物理ドライブ不在下で仮想TOC取得・RAWセクター読み出しが正確に行えること | `tests/test_virtual_drive.py` |
| **TASK-003** | implementer | `cdripper/hardware/speed_optimizer.py` | TASK-001 | バス種別（USB/SATA）とドライブ性能に応じた最適安全倍速算出ロジックおよび最大速度未取得時フォールバック | USB/SATA/未取得/例外時の安全倍速（8x/16x）が期待通り算出されること（FINDING-005解決） | `tests/test_speed_optimizer.py` |
| **TASK-004** | implementer | `cdripper/hardware/spti_drive.py` | TASK-001<br>TASK-002<br>TASK-003 | Win32 SPTI / `IOCTL_CDROM_RAW_READ` / MMC `READ CD (0xBE)` による実ドライブ制御、`GENERIC_READ` フォールバック、アクセス拒否検知 | デバイス列挙、TOC取得、RAWセクター読み出し、`ERROR_ACCESS_DENIED` 発生時の例外送出が検証されること（FINDING-002解決） | `tests/test_spti_drive.py` |
| **TASK-005** | implementer | `cdripper/metadata/__init__.py`<br>`cdripper/metadata/interface.py`<br>`cdripper/metadata/itunes_client.py`<br>`cdripper/metadata/mock_provider.py` | TASK-001 | `IMetadataProvider`、iTunes Search/Lookup API、マルチディスク (`discNumber`) フィルタ、TOC演奏時間差分マッチング、高解像度URL正規表現置換 (`1200x1200bb`)、モックプロバイダー | アルバム検索、曲名マッチング、高解像度画像URL置換、アートワークDL、モック動作がテストされること（FINDING-003, FINDING-008解決） | `tests/test_itunes_client.py` |
| **TASK-006** | implementer | `cdripper/pipeline/__init__.py`<br>`cdripper/pipeline/interface.py`<br>`cdripper/pipeline/ffmpeg_encoder.py` | TASK-001 | `IAudioEncoder`、`FFmpegEncoder`、動的引数生成、Windowsファイル名サニタイズ (`sanitize_filename`)、`stderr_reader_thread` によるデッドロック防止、一時ファイル安全管理 | 大量stderr時のパイプデッドロック回避、アートワーク有無の動的切替、一時ファイル確実消去、キャンセル時のプロセス終了・ファイル削除が確認できること（FINDING-001, 004, 007, 009解決） | `tests/test_ffmpeg_encoder.py` |
| **TASK-007** | implementer | `cdripper/pipeline/rip_pipeline.py` | TASK-001<br>TASK-002<br>TASK-006 | `AudioRipPipeline`、`read_track_sectors`（`min(75, remaining)` 境界制御）、進捗通知、キャンセル中断制御 | トラック端数セクターでの境界超過が防止され、仮想CDからのストリーミングエンコードが完走すること（FINDING-006解決） | `tests/test_rip_pipeline.py` |
| **TASK-008** | implementer | `cdripper/ui/__init__.py`<br>`cdripper/ui/presenter.py` | TASK-001<br>TASK-003<br>TASK-004<br>TASK-005<br>TASK-007 | `CDRipperPresenter`、ワーカースレッド制御、`queue.Queue` イベントディスパッチ、状態管理（IDLE/SCANNING/READY/RIPPING/FINISHED）、UAC昇格ハンドリング | UIスレッドをブロックせず、非同期進捗通知、ドライブ選択、メタデータ照合、キャンセルが協調動作すること | `tests/test_presenter.py` |
| **TASK-009** | implementer | `cdripper/ui/app_view.py` | TASK-001<br>TASK-008 | `CDRipperAppView` (Tkinter/TTK)、Windows High-DPIスケーリング、ドライブ/倍速設定、トラックTreeview、メタデータ照合、アートワークCanvas、進捗バー、ログText、検索ダイアログ | 高DPIで美しく描画され、ユーザー操作がPresenterに伝達され、50msキューポーリングで進捗とログが更新されること（FINDING-010解決） | `tests/test_app_view.py` |
| **TASK-010** | implementer | `cdripper/__main__.py`<br>`main.py`<br>`tests/test_integration.py` | TASK-001 〜 TASK-009 | エントリーポイントおよび全体E2E統合テスト（仮想CD $\rightarrow$ iTunesモック $\rightarrow$ FFmpeg実エンコード $\rightarrow$ ffprobeによるAAC 256kbps/タグ/アートワーク埋め込み検証） | `python main.py` でアプリ起動可能、かつ全自動テスト（E2Eタグ検証含む）がグリーンであること | `tests/test_integration.py` |

## Parallelization boundary
- Phase 1: TASK-001 (Domain Layer)
- Phase 2 (独立並列): TASK-002/003 (Hardware), TASK-005 (Metadata), TASK-006 (FFmpeg Pipeline)
- Phase 3 (順次): TASK-004 (SPTI), TASK-007 (Rip Pipeline)
- Phase 4: TASK-008 (Presenter)
- Phase 5: TASK-009 (App View)
- Phase 6: TASK-010 (Entry point & E2E)

## Integration order
1. ドメインモデル & 例外定義
2. 仮想ドライブ & 速度最適化 & メタデータ & FFmpegエンコーダー
3. SPTI実ドライブ & リッピングパイプライン
4. プレゼンター & UIビュー
5. エントリーポイント & E2E統合テスト

## Rollback / migration considerations
- 既存の `.agents/`, `START_PROMPT.md`, `README.md`, `RUNBOOK.md`, `manifest.json`, `TEMPLATES/` は完全保護。
- 各TASKごとにgitコミットを作成。
- リッピング中断・失敗時は `cancel_and_cleanup` により不完全ファイルを即時自動削除。

## Risks / unresolved items
- CI/テスト環境では `VirtualCDDrive` を用いて物理CD不在環境でも100%自動検証。
- FFmpeg未インストール時は起動時ガードで分かりやすいエラーを提示。
