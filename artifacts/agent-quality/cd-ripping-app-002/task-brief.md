# Task Brief

- Task ID: cd-ripping-app-002
- Title: DAEMON Tools等の仮想ドライブおよびSPTI転送上限に起因する MMC READ CD Win32 エラー 87 (ERROR_INVALID_PARAMETER) の解消
- Requester / owner: User
- Date: 2026-11-06
- Risk level: High (ハードウェアI/O、SCSIパススルー、リッピングコア機能の安定性に直結)
- Target revision / initial working tree: 33cbad8c2e277b89eb0747cbff2c17fa98c7e1e1 (Working tree clean)

## Background and goal
ユーザーが DAEMON Tools（仮想CDドライブ）を使用してマウントしたオーディオCDからリッピングを開始した際、以下のエラーが発生した：
「MMC READ CD failed. Win32 error: 87」
（ダイアログ「Ripping failed: Ripping failed on track 1: MMC READ CD failed. Win32 error: 87」）

調査結果：
1. Win32 Error 87 は `ERROR_INVALID_PARAMETER` (不正なパラメータ)。
2. `IOCTL_CDROM_RAW_READ` が仮想ドライブ（DAEMON Toolsなど）でサポートされず（Error 1: ERROR_INVALID_FUNCTION）、`_read_cd_mmc` (`IOCTL_SCSI_PASS_THROUGH_DIRECT`, CDB 0xBE READ CD) にフォールバックする。
3. `rip_pipeline.py` において、`read_track_sectors` の `batch_size` が固定値 75（75セクタ × 2352バイト = 176,400 バイト ≈ 172.2 KB）となっている。
4. Windows のストレージスタック（SPTI）およびデバイスアダプタ（DAEMON Toolsの仮想アダプタ、USB CDドライブのUSBストレージアダプタ等）には `MaximumTransferLength` の上限が存在する。
   - DAEMON Tools 仮想ドライブ (D:): `MaximumTransferLength = 131,072 バイト` (128 KB, 最大55セクタ)
   - USB 光学ドライブ (F:): `MaximumTransferLength = 65,536 バイト` (64 KB, 最大27セクタ)
5. 75セクタ（176,400 バイト）のリクエストは `MaximumTransferLength`（131,072 バイト）を超過するため、Windows カーネル (storport / cdrom.sys) または仮想ミニポートドライバが `STATUS_INVALID_PARAMETER` (Win32 エラー 87) を返し、読み込みが失敗する。

本タスクの目的は、DAEMON Tools などの仮想CDドライブや、転送サイズ制限が厳しい USB / SATA 光学ドライブにおいて、`MaximumTransferLength` を動的に考慮し、安全なチャンクサイズ（例: 24〜27セクタ以下）に自動分割して読み込む仕組みを導入し、Win32 error 87 を完全に解消することである。

## In scope
1. `spti_drive.py` におけるアダプタ最大転送長の動的検出 (`StorageAdapterProperty`) と安全な既定値（デフォルト25セクタ = 約58.8KB、または最大転送長に応じたセクタ数）の算出。
2. `spti_drive.py` の `read_sectors_raw` および `_read_cd_mmc` において、要求セクタ数が単一転送上限を超える場合に、自動的に安全なチャンクサイズへ分割して順次読み込み・結合して返す透過的チャンク分割機構の実装。
3. `rip_pipeline.py` の `batch_size` を 25〜27 セクタ程度（約60KB、1/3秒単位）に見直し、プログレス更新の滑らかさと単一転送の安全性を両立。
4. DAEMON Tools などの仮想ドライブおよび物理ドライブでの動作確認、ユニットテスト・統合テストの追加・更新。
5. エラーハンドリングの強化（転送エラー時の詳細ログ、わかりやすいエラーメッセージ）。

## Out of scope
- DAEMON Tools 自体のドライバ内部の変更
- CCCD等のコピープロテクト解除
- GUI デザインの大幅変更

## Functional requirements
| Requirement ID | Requirement | Priority | Notes |
|---|---|---|---|
| REQ-001 | DAEMON Tools等の仮想ドライブでマウントされたオーディオCDから正常にセクタデータを読み取れること | P0 | Win32 error 87 が発生しないこと |
| REQ-002 | `spti_drive.py` が要求されたセクタ数をアダプタの安全な最大転送サイズ（`max_transfer_sectors`）以下に自動分割して読み込めること | P0 | 75セクタ以上の要求でも安全に結合して返却 |
| REQ-003 | ドライブオープン時に `StorageAdapterProperty` をクエリし、`MaximumTransferLength` に応じた適切なチャンクサイズを動的に決定すること（取得失敗時は安全な既定値 25 セクタ ≈ 58.8KB を採用） | P1 | USB(64KB)やDAEMON Tools(128KB)に対応 |
| REQ-004 | `rip_pipeline.py` のデフォルト `batch_size` を安全なサイズ（25セクタ）に設定し、進捗更新を高頻度かつ安全に行うこと | P1 | プログレス表示の体感向上 |
| REQ-005 | MMC READ CD が万一完全にサポートされないドライブやアクセス拒否時のエラーハンドリングが明確であること | P2 | 適切な例外メッセージの表示 |

## Non-functional requirements
- NFR-001: 安定性 - いかなるセクタ数要求（1セクタ〜数百セクタ）に対しても、ドライバの転送制限を超えて Win32 error 87 を発生させない。
- NFR-002: 互換性 - 物理内蔵ドライブ (SATA/ATAPI)、外付けUSBドライブ、仮想ドライブ (DAEMON Tools, Virtual CloneDrive等) のすべてで動作すること。
- NFR-003: 性能 - 小さすぎるチャンク（1セクタ単位など）によるシステムコールのオーバーヘッドを避け、25〜55セクタ程度の効率的なバッチサイズを維持すること。
- NFR-004: 保守性・テスト性 - 物理ドライブや仮想ドライブが存在しないCI環境でも、チャンク分割ロジックをユニットテストで100%検証可能とすること。

## Constraints and compatibility
- OS: Windows 10/11
- ランタイム: Python 3.10+ (環境は Python 3.14.8 利用可能)
- Win32 API: `DeviceIoControl` (`IOCTL_STORAGE_QUERY_PROPERTY`, `IOCTL_SCSI_PASS_THROUGH_DIRECT`)
- 既存テストスイートの全パスを維持。

## Acceptance criteria
| Acceptance ID | Given / When / Then or measurable condition | Verification method |
|---|---|---|
| AC-001 | DAEMON Toolsの仮想ドライブ (D:) に対し、`read_sectors_raw(0, 75)` を実行した際、Win32 error 87 が発生せず、75 * 2352 バイトのデータが正常に取得できること | 実機D:ドライブでの読み取りテスト |
| AC-002 | `read_sectors_raw` に 100 や 150 などアダプタ上限を超えるセクタ数を指定しても、透過的にチャンク分割されて正確なバイト数が返されること | ユニットテストおよび実機テスト |
| AC-003 | リッピングパイプライン (`rip_pipeline.py`) を通じてDAEMON Toolsのトラック1（または全トラック）のエンコードがエラーなく進行・完了すること | 実機D:ドライブでのリッピング実行テスト |
| AC-004 | 既存のユニットテスト・統合テスト（48テスト）がすべてパスし、回帰が発生していないこと | `python -m unittest discover tests` |
| AC-005 | チャンク分割およびアダプタプロパティ取得をカバーする新規ユニットテストが追加され、パスすること | 新規テスト実行 |

## Existing user changes to preserve
- 作業ツリーはクリーン（未コミット変更なし）。既存ファイル構造とコーディング規約を維持。

## Approved commands / environment restrictions
- Python実行: `& "C:\Users\nanko\AppData\Local\Python\bin\python.exe" <script>`
- テスト実行: `& "C:\Users\nanko\AppData\Local\Python\bin\python.exe" -m unittest discover -s tests`
- 非破壊コマンドのみを実行。
