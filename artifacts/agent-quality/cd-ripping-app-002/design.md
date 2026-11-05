# アーキテクチャ設計書: SPTI転送長制限および仮想ドライブ対応 (Win32 エラー 87 解消) [確定版]

- **Task ID**: cd-ripping-app-002
- **Author**: system-architect & design-challenger (Consolidated)
- **Status**: Approved (Gate A Cleared with Challengers Addressed)
- **Target Component**: `cdripper.hardware.spti_drive`, `cdripper.pipeline.rip_pipeline`
- **Target Revision**: 33cbad8c2e277b89eb0747cbff2c17fa98c7e1e1

---

## 1. 要約 (Executive Summary)

本設計は、DAEMON Tools などの仮想CDドライブや転送長制限の厳しい USB 光学ドライブにおいて発生していた「MMC READ CD failed. Win32 error: 87 (ERROR_INVALID_PARAMETER)」を恒久的に解消するためのアーキテクチャ刷新案である。

根本原因は、パイプラインから要求される単一転送サイズ（75セクタ = 176,400 バイト ≈ 172.3KB）が、DAEMON Tools 仮想ミニポートドライバの最大転送長（131,072 バイト = 128KB、最大55セクタ）および外付け USB ドライブの最大転送長（65,536 バイト = 64KB、最大27セクタ）を超過していることにある。

本設計では**多層防御 (Defense in Depth)** および **Fail-Fast** のアプローチを採用し、Design Challenge の全指摘（FIND-001〜008）を反映した強固な設計とする：
1. **ハードウェア抽象化層 (`WindowsSPTICDDrive`)**:
   - `IOCTL_STORAGE_QUERY_PROPERTY` (`StorageAdapterProperty`) により、`MaximumTransferLength` および **`MaximumPhysicalPages`** の両方を考慮した実効最大転送バイト数を動的に算出（取得失敗時や異常値時は安全な既定値 25セクタ = 58,800 バイトを採用）。
   - `read_sectors_raw` において「**透過的チャンク分割 (Transparent Chunking)**」を導入。ループ不変量（`step >= 1`）を保証し無限ループを完全排除。`b"".join(chunks)` による最小コピー結合。
   - `_read_sectors_chunk` 内でチャンク単位の長さ検証（Fail-Fast）を徹底。
   - `IOCTL_CDROM_RAW_READ` が `ERROR_ACCESS_DENIED` 以外で失敗した場合は、直ちに `_supports_raw_read = False` に更新して MMC READ CD (0xBE) へ恒久フォールバック。
   - `threading.RLock` によるスレッドセーフなI/Oおよび状態管理。`close()` での完全な状態初期化。
2. **パイプライン層 (`rip_pipeline.py`)**:
   - `batch_size` の既定値を従来の 75 セクタから **25 セクタ**（1/3秒単位 = 58,800 バイト < 64KB）に変更。
   - USB (64KB) や仮想ドライブ (128KB) の単一転送上限内に自然に収めることで、通常処理時のチャンク分割オーバーヘッド（メモリ連結）をゼロにしつつ、UI プログレス更新頻度の向上（1Hz → 3Hz）とユーザーキャンセル応答性の向上（1.0秒 → 0.33秒）を両立する。

---

## 2. 要求・制約と仮定 (Requirements, Constraints, and Assumptions)

### 2.1 事実 (Facts)
1. **Win32 Error 87 の本質**: `ERROR_INVALID_PARAMETER`。SPTI (`IOCTL_SCSI_PASS_THROUGH_DIRECT`) 発行時、`DataTransferLength` がドライバ（storport.sys / ミニポート）の `MaximumTransferLength` または `(MaximumPhysicalPages - 1) * PAGE_SIZE` を超えると返される。
2. **実測値**:
   - DAEMON Tools (D:): `MaximumTransferLength = 131,072 バイト` (128KB, 55セクタ相当), `MaximumPhysicalPages = 17`
   - 一般的な USB 光学ドライブ (F:): `MaximumTransferLength = 65,536 バイト` (64KB, 27セクタ相当), `MaximumPhysicalPages = 16`
3. **CD-DA 規格**: 1セクタ = 2,352 バイト (44.1kHz, 16-bit signed stereo)。75セクタ = 1秒 = 176,400 バイト。
4. **RAW_READ 非対応**: DAEMON Tools などの仮想CDドライブでは `IOCTL_CDROM_RAW_READ` がサポートされず `ERROR_INVALID_FUNCTION` (1) を返すため、常に MMC READ CD (0xBE) へのフォールバックが発生する。

### 2.2 制約と不変条件 (Constraints and Invariants)
1. **インターフェース不変**: `ICDDrive.read_sectors_raw(start_lba: int, sector_count: int) -> bytes` のシグネチャと契約を厳格に維持。
2. **ループ不変量**: チャンク分割ループにおいて、ステップ幅は必ず `step >= 1` かつ `step <= max_transfer_sectors` であり、有限回の反復で終了すること。
3. **完全性不変量**: `_read_sectors_chunk` は、必ず要求セクタ数 × 2352 バイトの完全なデータを返すか、例外を送出するかの二者択一であり、不完全なデータを返却しない。

---

## 3. 推奨アーキテクチャ詳細

### 3.1 `cdripper.hardware.spti_drive.WindowsSPTICDDrive`

#### 定数定義
```python
DEFAULT_FALLBACK_SECTORS = 25  # 約57.4KB (< 64KB USB境界)
MIN_TRANSFER_SECTORS = 1
MAX_TRANSFER_SECTORS_CAP = 75  # 1秒分 (176.4KB)
CDDA_SECTOR_SIZE = 2352
PAGE_SIZE = 4096

# Win32 IOCTL & Query IDs
IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
StorageAdapterProperty = 1
PropertyStandardQuery = 0
```

#### クラス構造
```python
class STORAGE_ADAPTER_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("Version", ctypes.c_ulong),
        ("Size", ctypes.c_ulong),
        ("MaximumTransferLength", ctypes.c_ulong),
        ("MaximumPhysicalPages", ctypes.c_ulong),
        ("AlignmentMask", ctypes.c_ulong),
        ("AdapterUsesPio", ctypes.c_ubyte),
        ("AdapterScansDown", ctypes.c_ubyte),
        ("CommandQueueing", ctypes.c_ubyte),
        ("AcceleratedTransfer", ctypes.c_ubyte),
        ("BusType", ctypes.c_ubyte),
        ("BusMajorVersion", ctypes.c_ushort),
        ("BusMinorVersion", ctypes.c_ushort),
        ("SrbType", ctypes.c_ubyte),
        ("AddressType", ctypes.c_ubyte),
    ]
```

#### 内部メソッド実装仕様

1. **`_query_adapter_transfer_limit(self) -> int`** (FIND-001, FIND-008 対応)
   - `STORAGE_PROPERTY_QUERY` (`StorageAdapterProperty`) を発行。
   - `DeviceIoControl` が成功し、かつ返却バイト数が `sizeof(STORAGE_ADAPTER_DESCRIPTOR)` 以上であることを確認。
   - 実効最大転送バイト数の計算:
     ```python
     max_bytes = desc.MaximumTransferLength
     if desc.MaximumPhysicalPages > 1:
         page_limit = (desc.MaximumPhysicalPages - 1) * PAGE_SIZE
         if page_limit > 0:
             max_bytes = min(max_bytes, page_limit)

     if max_bytes < CDDA_SECTOR_SIZE:
         return DEFAULT_FALLBACK_SECTORS

     max_sectors = max_bytes // CDDA_SECTOR_SIZE
     return max(MIN_TRANSFER_SECTORS, min(MAX_TRANSFER_SECTORS_CAP, max_sectors))
     ```
   - いかなる例外時も `DEFAULT_FALLBACK_SECTORS` (25) を安全に返す。

2. **`read_sectors_raw(self, start_lba: int, sector_count: int) -> bytes`** (FIND-003, FIND-005, FIND-006 対応)
   - 入力検証:
     ```python
     if sector_count <= 0:
         return b""
     if not self._handle or self._handle == INVALID_HANDLE_VALUE:
         raise CDDriveNotFoundError("Drive is not open.")
     ```
   - 排他ロック `with self._lock:` 内で実行。
   - 透過的チャンク分割ループ:
     ```python
     step = max(MIN_TRANSFER_SECTORS, self._max_transfer_sectors)
     if sector_count <= step:
         return self._read_sectors_chunk(start_lba, sector_count)

     chunks: List[bytes] = []
     remaining = sector_count
     current_lba = start_lba

     while remaining > 0:
         chunk_size = min(remaining, step)
         chunk_data = self._read_sectors_chunk(current_lba, chunk_size)
         chunks.append(chunk_data)
         current_lba += chunk_size
         remaining -= chunk_size

     return b"".join(chunks)
     ```

3. **`_read_sectors_chunk(self, start_lba: int, sector_count: int) -> bytes`** (FIND-002, FIND-004 対応)
   - `self._supports_raw_read` が True の場合、`IOCTL_CDROM_RAW_READ` を試行。
     - 成功時: `data = bytes(buffer.raw[:bytes_ret.value])`
     - 失敗時:
       - `err == ERROR_ACCESS_DENIED` -> `raise CDDriveAccessDeniedError(...)`
       - それ以外の任意のエラー（1, 87, 22, 50等） -> `self._supports_raw_read = False` に更新し、MMC READ CD を実行。
   - `self._supports_raw_read` が False の場合: 最初から MMC READ CD (`_read_cd_mmc`) を実行。
   - **Fail-Fast 検証**:
     ```python
     expected_bytes = sector_count * CDDA_SECTOR_SIZE
     if len(data) != expected_bytes:
         raise CDDriveReadError(
             f"Incomplete sector read at LBA {start_lba}: expected {expected_bytes} bytes, got {len(data)} bytes"
         )
     return data
     ```

4. **`close(self) -> None`** (FIND-007 対応)
   - ロック内でハンドルをクローズし、以下を初期化：
     `self._max_transfer_sectors = DEFAULT_FALLBACK_SECTORS`
     `self._supports_raw_read = True`

---

### 3.2 `cdripper.pipeline.rip_pipeline`

#### 定数定義
```python
DEFAULT_BATCH_SECTORS = 25  # 1/3秒分 (58,800 bytes)
```

#### `read_track_sectors` シグネチャ
```python
def read_track_sectors(
    drive: ICDDrive,
    track: TrackTOC,
    on_chunk: Callable[[bytes], None],
    cancel_token: Optional[threading.Event] = None,
    batch_size: int = DEFAULT_BATCH_SECTORS,
) -> None:
```
- デフォルトバッチサイズを 75 から 25 に更新。
- これにより、DAEMON Tools (上限55) および USB ドライブ (上限27) において単一転送で処理され、分割オーバーヘッドなしに高速実行可能。
- プログレス更新頻度は 3Hz となり、キャンセル時の遅延も最大 0.33 秒へ改善。

---

## 4. 受入条件へのトレーサビリティ

| Acceptance ID | 受入条件 | 設計上の保証 |
|---|---|---|
| **AC-001** | DAEMON Tools仮想ドライブ (D:) で `read_sectors_raw(0, 75)` が Win32 error 87 を出さずに成功 | 内部で 55 セクタ以下（25〜55）に透過的分割 |
| **AC-002** | 100 や 150 セクタの要求でも正確なバイト数（count * 2352）が返る | `step` 制御ループと `b"".join(chunks)` |
| **AC-003** | リッピングパイプライン経由でDAEMON Tools上のトラックが正常にエンコード完了する | `batch_size = 25` + 透過的チャンク分割 |
| **AC-004** | 既存48テストがすべてパスし回帰なし | 既存契約の維持と下位互換性 |
| **AC-005** | アダプタ情報取得・フォールバック・チャンク分割の新規ユニットテストがパス | `test_spti_drive.py` に包括的テスト追加 |
