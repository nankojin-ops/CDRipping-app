# Findings Register: Task cd-ripping-app-002

- Target Revision: 33cbad8c2e277b89eb0747cbff2c17fa98c7e1e1
- Date: 2026-11-06
- Total Findings: 11
  - P0: 0
  - P1: 3 (Resolved: 3)
  - P2: 5 (Resolved: 5)
  - P3: 3 (Resolved / Validated: 3)
- Unresolved Critical / High: 0
- Status: **ALL RESOLVED / CLOSED**

---

## Findings Details

### FIND-001 (Design Challenge)
- **Severity**: P1 (High)
- **Component**: `cdripper.hardware.spti_drive.WindowsSPTICDDrive._query_adapter_transfer_limit`
- **Condition**: USB光学ドライブ等で `MaximumPhysicalPages` が小さく設定されている環境（例: 16ページ=64KB）。
- **Impact**: 物理ページ上限（Scatter/Gather List上限）超過により、Win32 エラー 87 (`ERROR_INVALID_PARAMETER`) が再発する。
- **Remediation**:
  `max_bytes = desc.MaximumTransferLength` に対し、`if desc.MaximumPhysicalPages > 1: max_bytes = min(max_bytes, (desc.MaximumPhysicalPages - 1) * 4096)` を適用し、実効上限セクタ数を算出。
- **Verification Evidence**: `test_query_adapter_transfer_limit_page_bound` PASS
- **Status**: **RESOLVED**

### FIND-002 (Design Challenge)
- **Severity**: P1 (High)
- **Component**: `cdripper.hardware.spti_drive.WindowsSPTICDDrive._read_sectors_chunk`
- **Condition**: 仮想ドライブやUSBドライブで `IOCTL_CDROM_RAW_READ` が 1 や 50 以外のエラーコード（87, 22, 31等）を返した場合。
- **Impact**: フォールバック判定が限定的だと MMC READ CD へのフォールバックが失敗するか、毎チャンク無駄な再試行を繰り返す。
- **Remediation**:
  `ERROR_ACCESS_DENIED` 以外の任意のエラーで直ちに `self._supports_raw_read = False` に更新し、恒久的に MMC READ CD へフォールバック。
- **Verification Evidence**: `test_raw_read_fallback_on_any_error` PASS
- **Status**: **RESOLVED**

### FIND-003 (Design Challenge)
- **Severity**: P1 (High)
- **Component**: `cdripper.hardware.spti_drive.WindowsSPTICDDrive.read_sectors_raw`
- **Condition**: 万一 `_max_transfer_sectors` が 0 または負数の場合。
- **Impact**: `chunk = min(remaining, self._max_transfer_sectors)` で `chunk <= 0` となり、`while remaining > 0` が無限ループしてプロセスが完全ハングする。
- **Remediation**:
  `step = max(MIN_TRANSFER_SECTORS, self._max_transfer_sectors)` を保証し、ループ不変量 `step >= 1` を厳格に維持。
- **Verification Evidence**: `test_read_sectors_raw_infinite_loop_prevention` PASS
- **Status**: **RESOLVED**

### FIND-004 (Design Challenge)
- **Severity**: P2 (Medium)
- **Component**: `cdripper.hardware.spti_drive.WindowsSPTICDDrive._read_sectors_chunk`
- **Condition**: 読み取り時にショートリード（不完全データ長）が発生した場合。
- **Impact**: 要求長未満の不完全なデータがエンコーダに渡る、または無駄な後続I/Oが行われる。
- **Remediation**:
  `_read_sectors_chunk` の内部で `len(data) != expected_bytes` を即座に検証（Fail-Fast）し、不一致時は `CDDriveReadError` を送出。
- **Verification Evidence**: `test_read_sectors_chunk_incomplete_data_raises` PASS
- **Status**: **RESOLVED**

### FIND-005 (Design Challenge)
- **Severity**: P2 (Medium)
- **Component**: `cdripper.hardware.spti_drive.WindowsSPTICDDrive.read_sectors_raw`
- **Condition**: チャンク結合時のメモリ管理。
- **Impact**: `bytearray` と `bytes(buffer)` の多重コピーによるGC負荷。
- **Remediation**:
  `chunks = []; chunks.append(chunk_data); return b"".join(chunks)` を採用し、最速・最小メモリで結合。
- **Verification Evidence**: `test_read_sectors_raw_transparent_chunking` PASS
- **Status**: **RESOLVED**

### FIND-006 (Design Challenge)
- **Severity**: P2 (Medium)
- **Component**: `cdripper.hardware.spti_drive.WindowsSPTICDDrive`
- **Condition**: マルチスレッド環境での同時アクセス。
- **Impact**: リッピング中に別スレッドからドライブオープン・クローズが行われた場合のハンドル競合。
- **Remediation**:
  `threading.RLock` によるドライブ操作の排他制御。
- **Verification Evidence**: `test_concurrent_read_sectors_raw` PASS (4スレッド並行検証)
- **Status**: **RESOLVED**

### FIND-007 (Design Challenge)
- **Severity**: P2 (Medium)
- **Component**: `cdripper.hardware.spti_drive.WindowsSPTICDDrive.close`
- **Condition**: ドライブクローズ後の状態。
- **Impact**: ドライブ切替時に前回ドライブの転送上限やキャッシュフラグが残留する。
- **Remediation**:
  `close()` メソッド内で `_max_transfer_sectors = DEFAULT_FALLBACK_SECTORS` および `_supports_raw_read = True` をリセット。
- **Verification Evidence**: `test_close_resets_state` PASS
- **Status**: **RESOLVED**

### FIND-008 (Design Challenge)
- **Severity**: P3 (Low)
- **Component**: `cdripper.hardware.spti_drive.WindowsSPTICDDrive._query_adapter_transfer_limit`
- **Condition**: ドライバが返したバイト数が記述子サイズ未満の場合。
- **Impact**: 未初期化メモリ読み取りリスク。
- **Remediation**:
  `bytes_returned.value >= ctypes.sizeof(STORAGE_ADAPTER_DESCRIPTOR)` のサイズ検証を追加。
- **Verification Evidence**: `test_query_adapter_transfer_limit_short_descriptor` PASS
- **Status**: **RESOLVED**

### SEC-PIPE-001 (Security Review)
- **Severity**: P2 (Medium)
- **Component**: `cdripper.pipeline.rip_pipeline.read_track_sectors`
- **Condition**: `batch_size <= 0`（0 または負数）が渡された場合。
- **Impact**: ループステップが進まず無限ループとなり CPU 100% の DoS が発生するリスク。
- **Remediation**:
  関数の先頭で `if batch_size <= 0: raise ValueError(...)` を追加。
- **Verification Evidence**: `test_read_track_sectors_invalid_batch_size` PASS
- **Status**: **RESOLVED**

### REV-001 (Code Review)
- **Severity**: P3 (Low)
- **Component**: `cdripper.hardware.spti_drive.WindowsSPTICDDrive._query_adapter_transfer_limit`
- **Condition**: `MaximumPhysicalPages == 1` の場合の動作確認。
- **Status**: **VALIDATED (実害なし・設計準拠)**

### REV-002 (Code Review)
- **Severity**: P3 (Low)
- **Component**: `cdripper.hardware.spti_drive.WindowsSPTICDDrive.read_sectors_raw`
- **Condition**: `sector_count <= 0` の早期空バイト返却の動作確認。
- **Status**: **VALIDATED (Python stream 仕様準拠)**
