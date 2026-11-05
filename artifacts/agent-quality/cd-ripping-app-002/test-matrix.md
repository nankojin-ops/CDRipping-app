# テストマトリクス（Test Matrix）: SPTI転送長制限および仮想ドライブ対応 (Win32 エラー 87 解消)

- **タスクID**: cd-ripping-app-002
- **作成日**: 2026-11-06
- **設計者**: QA Test Designer (実装ブラインド)
- **対象受入条件**: AC-001 〜 AC-005
- **対象コンポーネント**: `WindowsSPTICDDrive`, `_query_adapter_transfer_limit`, `read_sectors_raw`, `_read_sectors_chunk`, `close`, `rip_pipeline.read_track_sectors`

---

## 1. テスト概要と設計方針
1. **多層テスト戦略**:
   - ハードウェア抽象化層（プロパティ取得・透過的チャンク分割・フォールバック・整合性検証・スレッドセーフ）を Unit / Integration で徹底的に検証。
   - パイプライン層（バッチサイズ変更、端数処理、キャンセル応答性）を Unit / Integration で検証。
   - 実機 DAEMON Tools 仮想ドライブ（D:）での E2E / Manual 検証により AC-001, AC-002, AC-003 を確定。
   - 既存48テストの全通過確認により回帰（AC-004）を防止。
2. **境界値・極限値の網羅**:
   - 0セクタ、負値、1セクタ、ステップ境界直前・直後、巨大セクタ数。
   - MaximumTransferLength / MaximumPhysicalPages の組み合わせ（極小、極大、無効値）。
3. **異常系・障害・堅牢性**:
   - `DeviceIoControl` 失敗時の既定値フォールバック。
   - Win32 エラー 1 (`ERROR_INVALID_FUNCTION`) / 87 (`ERROR_INVALID_PARAMETER`) からの MMC READ CD フォールバック。
   - `ERROR_ACCESS_DENIED` (5) 時のフォールバック阻止と即時例外送出。
   - ショートリード / 超過リードに対する Fail-Fast 検証。

---

## 2. 受入条件（AC）トレーサビリティマトリクス

| 受入条件 ID | 受入条件サマリ | カバーするテスト ID |
|---|---|---|
| **AC-001** | DAEMON Tools仮想ドライブで `read_sectors_raw(0, 75)` 実行時に Win32 error 87 が発生せず正常取得できる | TC-IO-002, TC-IO-003, TC-CHUNK-003, TC-E2E-001 |
| **AC-002** | 100や150など上限超過セクタ数を指定しても透過的にチャンク分割され正確なバイト数が返される | TC-CHUNK-003, TC-CHUNK-004, TC-CHUNK-005, TC-CHUNK-012, TC-E2E-002 |
| **AC-003** | パイプライン経由でDAEMON Toolsトラック1等のエンコードがエラーなく進行・完了する | TC-PIPE-001, TC-PIPE-002, TC-PIPE-003, TC-PIPE-004, TC-PIPE-005, TC-E2E-003 |
| **AC-004** | 既存ユニット/統合テスト（48テスト）がすべてパスし、回帰がない | TC-REG-001 |
| **AC-005** | チャンク分割およびアダプタプロパティ取得をカバーする新規ユニットテストが追加されパスする | TC-PROP-001 〜 TC-PROP-010, TC-CHUNK-001 〜 TC-CHUNK-012, TC-IO-001 〜 TC-IO-008, TC-LIFE-001 〜 TC-LIFE-002, TC-CONC-001 〜 TC-CONC-002 |

---

## 3. テストマトリクス一覧

### カテゴリ 1: アダプタプロパティ取得と実効転送上限算出 (`_query_adapter_transfer_limit`)

| テスト ID | 対応AC | 優先度 | レベル | 前提条件 | 入力 / テストデータ | 実行手順 | 期待結果 | 異常系・境界値・設計根拠 |
|---|---|---|---|---|---|---|---|---|
| **TC-PROP-001** | AC-005 | P1 | Unit | ドライブハンドルがオープン状態 | `MaximumTransferLength = 131,072` (128KB, DAEMON Tools相当), `MaximumPhysicalPages = 0` | `_query_adapter_transfer_limit()` を呼び出す | 戻り値が `55` であること (`131072 // 2352 = 55`) | DAEMON Tools 仮想ドライブの代表値検証 |
| **TC-PROP-002** | AC-005 | P1 | Unit | ドライブハンドルがオープン状態 | `MaximumTransferLength = 65,536` (64KB, 外付けUSB相当), `MaximumPhysicalPages = 0` | `_query_adapter_transfer_limit()` を呼び出す | 戻り値が `27` であること (`65536 // 2352 = 27`) | USB 光学ドライブの代表値検証 |
| **TC-PROP-003** | AC-005 | P1 | Unit | ドライブハンドルがオープン状態 | `MaximumTransferLength = 131,072`, `MaximumPhysicalPages = 9` (page_limit = (9-1)*4096 = 32,768) | `_query_adapter_transfer_limit()` を呼び出す | 戻り値が `13` であること (`32768 // 2352 = 13`) | PhysicalPages による制限が TransferLength より厳しい場合の min 選択検証 |
| **TC-PROP-004** | AC-005 | P2 | Unit | ドライブハンドルがオープン状態 | `MaximumTransferLength = 65,536`, `MaximumPhysicalPages = 2` (page_limit = 4,096) | `_query_adapter_transfer_limit()` を呼び出す | 戻り値が `1` であること (`4096 // 2352 = 1`) | PhysicalPages 極小境界値。`MIN_TRANSFER_SECTORS` (1) の下限保証 |
| **TC-PROP-005** | AC-005 | P2 | Unit | ドライブハンドルがオープン状態 | `MaximumTransferLength = 131,072`, `MaximumPhysicalPages = 1` | `_query_adapter_transfer_limit()` を呼び出す | 戻り値が `55` であること (page_limit 計算が行われず TransferLength が採用される) | `MaximumPhysicalPages <= 1` の条件分岐検証 |
| **TC-PROP-006** | AC-005 | P1 | Unit | ドライブハンドルがオープン状態 | `MaximumTransferLength = 1,048,576` (1MB, 高速SATA等), `MaximumPhysicalPages = 0` | `_query_adapter_transfer_limit()` を呼び出す | 戻り値が `75` であること (`MAX_TRANSFER_SECTORS_CAP` でキャップ) | 上限キャップ定数 `MAX_TRANSFER_SECTORS_CAP` (75) の強制適用検証 |
| **TC-PROP-007** | AC-005 | P1 | Unit | ドライブハンドルがオープン状態 | `MaximumTransferLength = 2,000` (< 2352), `MaximumPhysicalPages = 0` | `_query_adapter_transfer_limit()` を呼び出す | 戻り値が `DEFAULT_FALLBACK_SECTORS` (25) であること | 1セクタ長未満の異常値に対する安全なフォールバック |
| **TC-PROP-008** | AC-005 | P2 | Unit | ドライブハンドルがオープン状態 | `MaximumTransferLength = 2,352` (ちょうど1セクタ), `MaximumPhysicalPages = 0` | `_query_adapter_transfer_limit()` を呼び出す | 戻り値が `1` であること (`2352 // 2352 = 1`) | ちょうど1セクタ長の境界値検証 |
| **TC-PROP-009** | AC-005 | P1 | Unit | ドライブハンドルがオープン状態 | IOCTL クエリが Win32 エラー（ERROR_NOT_SUPPORTED 等）で失敗 | `_query_adapter_transfer_limit()` を呼び出す | 例外が外部に漏れず、戻り値が `DEFAULT_FALLBACK_SECTORS` (25) であること | プロパティクエリ非対応ドライブに対する Fail-Safe 検証 |
| **TC-PROP-010** | AC-005 | P2 | Unit | ドライブハンドルがオープン状態 | `MaximumTransferLength = 0` または負値 | `_query_adapter_transfer_limit()` を呼び出す | 戻り値が `DEFAULT_FALLBACK_SECTORS` (25) であること | 不正値・ゼロ値に対する堅牢性検証 |

---

### カテゴリ 2: 透過的チャンク分割読み込み (`read_sectors_raw`)

| テスト ID | 対応AC | 優先度 | レベル | 前提条件 | 入力 / テストデータ | 実行手順 | 期待結果 | 異常系・境界値・設計根拠 |
|---|---|---|---|---|---|---|---|---|
| **TC-CHUNK-001** | AC-002, AC-005 | P1 | Unit | ドライブオープン済み, `_max_transfer_sectors = 25` | `start_lba = 100`, `sector_count = 20` | `read_sectors_raw(100, 20)` を実行 | `_read_sectors_chunk(100, 20)` が 1 回のみ呼び出され、`20 * 2352` バイトの結合データが返ること | 単一チャンク処理（`sector_count <= step`）の正常系パス |
| **TC-CHUNK-002** | AC-002, AC-005 | P1 | Unit | ドライブオープン済み, `_max_transfer_sectors = 25` | `start_lba = 0`, `sector_count = 25` | `read_sectors_raw(0, 25)` を実行 | `_read_sectors_chunk(0, 25)` が 1 回のみ呼び出され、`25 * 2352` バイトが返ること | ちょうどステップ境界値（`sector_count == step`）の境界値検証 |
| **TC-CHUNK-003** | AC-001, AC-002, AC-005 | P0 | Unit | ドライブオープン済み, `_max_transfer_sectors = 25` | `start_lba = 0`, `sector_count = 75` | `read_sectors_raw(0, 75)` を実行 | `_read_sectors_chunk` が `(0, 25)`, `(25, 25)`, `(50, 25)` の 3 回順次呼び出され、全 `75 * 2352` バイトが結合されて返ること | AC-001 の要求仕様（75セクタの安全な3分割）の完全検証 |
| **TC-CHUNK-004** | AC-002, AC-005 | P1 | Unit | ドライブオープン済み, `_max_transfer_sectors = 25` | `start_lba = 10`, `sector_count = 60` | `read_sectors_raw(10, 60)` を実行 | `_read_sectors_chunk` が `(10, 25)`, `(35, 25)`, `(60, 10)` の 3 回呼び出され、端数 10 セクタを含め計 `60 * 2352` バイトが返ること | 端数セクタを含む分割ループの境界値検証 |
| **TC-CHUNK-005** | AC-002, AC-005 | P1 | Unit | ドライブオープン済み, `_max_transfer_sectors = 55` (DAEMON Tools上限) | `start_lba = 0`, `sector_count = 150` | `read_sectors_raw(0, 150)` を実行 | `(0, 55)`, `(55, 55)`, `(110, 40)` の 3 回呼び出され、計 `150 * 2352` バイトが返ること | AC-002 の要求（150セクタの大規模転送）の透過的分割検証 |
| **TC-CHUNK-006** | AC-002, AC-005 | P2 | Unit | ドライブオープン済み | `start_lba = 0`, `sector_count = 0` | `read_sectors_raw(0, 0)` を実行 | I/O は一切実行されず、即座に空バイト列 `b""` が返ること | 境界値: 0 セクタ |
| **TC-CHUNK-007** | AC-002, AC-005 | P2 | Unit | ドライブオープン済み | `start_lba = 0`, `sector_count = -1` (または -10) | `read_sectors_raw(0, -1)` を実行 | 即座に空バイト列 `b""` が返ること | 異常系境界値: 負数セクタ数 |
| **TC-CHUNK-008** | AC-002, AC-005 | P2 | Unit | ドライブオープン済み, `_max_transfer_sectors = 25` | `start_lba = 0`, `sector_count = 1` | `read_sectors_raw(0, 1)` を実行 | `_read_sectors_chunk(0, 1)` が 1 回呼び出され、`2352` バイトが返ること | 最小単位 1 セクタの境界値検証 |
| **TC-CHUNK-009** | AC-002, AC-005 | P2 | Unit | ドライブオープン済み, `_max_transfer_sectors = 1` | `start_lba = 0`, `sector_count = 5` | `read_sectors_raw(0, 5)` を実行 | `(0, 1)`, `(1, 1)`, `(2, 1)`, `(3, 1)`, `(4, 1)` の 5 回呼び出され、計 `5 * 2352` バイトが返ること | 極小ステップ `step = 1` におけるループ不変量と分割正当性検証 |
| **TC-CHUNK-010** | AC-005 | P1 | Unit | ドライブ未オープン（`_handle is None`） | `start_lba = 0`, `sector_count = 25` | `read_sectors_raw(0, 25)` を実行 | `CDDriveNotFoundError` が送出されること | 未初期化・未オープン状態での堅牢性検証 |
| **TC-CHUNK-011** | AC-005 | P1 | Unit | ドライブオープン済み, `_max_transfer_sectors = 25` | `sector_count = 75`。2回目のチャンク `(25, 25)` で `CDDriveReadError` を模擬発生させる | `read_sectors_raw(0, 75)` を実行 | 直ちに `CDDriveReadError` が送出され、3回目のチャンク `(50, 25)` は呼び出されないこと | 途中障害発生時の Fail-Fast およびリソース漏れ防止検証 |
| **TC-CHUNK-012** | AC-002, AC-005 | P1 | Unit | ドライブオープン済み, `_max_transfer_sectors = 2` | `sector_count = 5`。各チャンクに異なる一意の識別データ（例: チャンク番号プレフィックス）を返却 | `read_sectors_raw(0, 5)` を実行 | 結合されたデータが先頭チャンクから末尾チャンクまで順序通り欠損・重複なく結合されていること | データの順序性とデータ整合性（Data Integrity）検証 |

---

### カテゴリ 3: チャンク読み込み・フォールバック・整合性検証 (`_read_sectors_chunk`)

| テスト ID | 対応AC | 優先度 | レベル | 前提条件 | 入力 / テストデータ | 実行手順 | 期待結果 | 異常系・境界値・設計根拠 |
|---|---|---|---|---|---|---|---|---|
| **TC-IO-001** | AC-005 | P1 | Unit | ドライブオープン済み, `_supports_raw_read = True` | `start_lba = 0`, `sector_count = 25`。Raw Read が成功するモック | `_read_sectors_chunk(0, 25)` を実行 | `IOCTL_CDROM_RAW_READ` が実行され、MMC READ CD は呼ばれずデータが返る。`_supports_raw_read` は `True` を維持 | Raw Read 対応通常ドライブでの正常系パス |
| **TC-IO-002** | AC-001, AC-005 | P0 | Unit | ドライブオープン済み, `_supports_raw_read = True` | `start_lba = 0`, `sector_count = 25`。Raw Read が Win32 Error 1 (`ERROR_INVALID_FUNCTION`) で失敗、MMC READ CD が成功するモック | `_read_sectors_chunk(0, 25)` を実行 | 1. Raw Read 失敗検知<br>2. `_supports_raw_read` が `False` に更新<br>3. 直ちに MMC READ CD が実行され、正常データが返ること | DAEMON Tools等の仮想ドライブで Raw Read 非対応時の自動フォールバック検証 |
| **TC-IO-003** | AC-001, AC-005 | P1 | Unit | ドライブオープン済み, `_supports_raw_read = True` | `start_lba = 0`, `sector_count = 25`。Raw Read が Win32 Error 87 (`ERROR_INVALID_PARAMETER`) で失敗、MMC READ CD が成功するモック | `_read_sectors_chunk(0, 25)` を実行 | 同様に `_supports_raw_read` が `False` に更新され、MMC READ CD で正常データが返ること | パラメータ不整合エラー時のフォールバック検証 |
| **TC-IO-004** | AC-005 | P1 | Unit | ドライブオープン済み, `_supports_raw_read = False` (フォールバック済み状態) | `start_lba = 25`, `sector_count = 25` | `_read_sectors_chunk(25, 25)` を実行 | `IOCTL_CDROM_RAW_READ` の呼び出しをスキップし、最初から MMC READ CD が呼び出されること | 不要な Raw Read 呼び出しを回避する最適化の検証 |
| **TC-IO-005** | AC-005 | P1 | Unit | ドライブオープン済み, `_supports_raw_read = True` | `start_lba = 0`, `sector_count = 25`。Raw Read が Win32 Error 5 (`ERROR_ACCESS_DENIED`) で失敗 | `_read_sectors_chunk(0, 25)` を実行 | MMC READ CD へフォールバックせず、直ちに `CDDriveAccessDeniedError` が送出されること。`_supports_raw_read` は `True` のままであること | 権限不足エラーを機能不全と誤認してフォールバックしない安全設計の検証 |
| **TC-IO-006** | AC-005 | P1 | Unit | ドライブオープン済み, `_supports_raw_read = False` | `start_lba = 0`, `sector_count = 25`。MMC READ CD がエラーで失敗 | `_read_sectors_chunk(0, 25)` を実行 | `CDDriveReadError` が送出されること | フォールバック先でもI/O失敗した場合の例外送出検証 |
| **TC-IO-007** | AC-005 | P1 | Unit | ドライブオープン済み | `start_lba = 0`, `sector_count = 25`。I/O 戻り値が `24 * 2352` バイト（1セクタ不足のショートリード） | `_read_sectors_chunk(0, 25)` を実行 | `len(data) != 25 * 2352` を検知し、直ちに `CDDriveReadError` が送出されること | 不完全読み取りに対する Fail-Fast 整合性検証 |
| **TC-IO-008** | AC-005 | P2 | Unit | ドライブオープン済み | `start_lba = 0`, `sector_count = 25`。I/O 戻り値が `26 * 2352` バイト（超過リード） | `_read_sectors_chunk(0, 25)` を実行 | `CDDriveReadError` が送出されること | バッファ超過・データ破壊に対する Fail-Fast 検証 |

---

### カテゴリ 4: ライフサイクル・状態管理・スレッドセーフ (`close` / `RLock`)

| テスト ID | 対応AC | 優先度 | レベル | 前提条件 | 入力 / テストデータ | 実行手順 | 期待結果 | 異常系・境界値・設計根拠 |
|---|---|---|---|---|---|---|---|---|
| **TC-LIFE-001** | AC-005 | P1 | Unit | ドライブオープン済み, `_supports_raw_read = False`, `_max_transfer_sectors = 55` | なし | `drive.close()` を呼び出す | 1. ハンドルがクローズされる<br>2. `_max_transfer_sectors` が `DEFAULT_FALLBACK_SECTORS` (25) にリセットされる<br>3. `_supports_raw_read` が `True` にリセットされること | ドライブクローズ時の状態完全初期化の保証 |
| **TC-LIFE-002** | AC-005 | P2 | Unit | ドライブクローズ済み | なし | 連続して `drive.close()` を呼び出す | 例外が発生せず安全に終了すること | `close()` の冪等性（Idempotency）検証 |
| **TC-CONC-001** | AC-005 | P1 | Integration | ドライブオープン済み | 5本のスレッドから同一ドライブインスタンスに対して異なる LBA の `read_sectors_raw` (75セクタ) を同時に呼び出す | 並行実行を完了させる | デッドロックやデータ破壊、競合例外が発生せず、全スレッドが期待通りのデータを取得できること | `threading.RLock` による排他制御とスレッドセーフ性の検証 |
| **TC-CONC-002** | AC-005 | P2 | Integration | ドライブオープン済み | スレッドAで `read_sectors_raw` 実行中に、スレッドBから `close()` を呼び出す | 並行実行 | デッドロックせず、安全にクローズまたはクローズ後例外がハンドリングされること | 並行クローズ操作における安定性検証 |

---

### カテゴリ 5: リッピングパイプライン層 (`rip_pipeline.read_track_sectors`)

| テスト ID | 対応AC | 優先度 | レベル | 前提条件 | 入力 / テストデータ | 実行手順 | 期待結果 | 異常系・境界値・設計根拠 |
|---|---|---|---|---|---|---|---|---|
| **TC-PIPE-001** | AC-003, AC-005 | P1 | Unit | ドライブおよびトラックモック準備完了 | トラック長: 100セクタ, `batch_size` 引数省略 (既定値) | `read_track_sectors(drive, track, on_chunk)` を実行 | ドライブの `read_sectors_raw` が 25 セクタずつ 4 回呼び出されること (`DEFAULT_BATCH_SECTORS = 25` の適用確認) | パイプライン層の既定バッチサイズ変更検証 |
| **TC-PIPE-002** | AC-003, AC-005 | P1 | Unit | ドライブおよびトラックモック準備完了 | トラック長: 77セクタ (25の倍数でない端数あり) | `read_track_sectors(drive, track, on_chunk)` を実行 | `read_sectors_raw` が 25, 25, 25, 2 の順で計 4 回呼び出され、全 77 セクタが `on_chunk` に渡されること | トラック末尾の端数バッチ処理の正確性検証 |
| **TC-PIPE-003** | AC-003, AC-005 | P1 | Unit | ドライブおよびトラックモック準備完了 | トラック長: 10セクタ (< 25セクタ) | `read_track_sectors(drive, track, on_chunk)` を実行 | `read_sectors_raw` が 1 回 (10セクタ) のみ呼び出され、正常に完了すること | バッチサイズ未満の極小トラック処理検証 |
| **TC-PIPE-004** | AC-003, AC-005 | P1 | Unit | ドライブおよびトラックモック準備完了, キャンセルトークン準備 | トラック長: 100セクタ。1回目のチャンクコールバックで `cancel_token.cancel()` を発効 | `read_track_sectors` を実行 | 2回目のチャンク読み込み前にループが速やかに中断され、3回目以降の読み込みが発生しないこと | バッチサイズ縮小（25セクタ/0.33秒）に伴うユーザーキャンセル応答性の向上検証 |
| **TC-PIPE-005** | AC-003, AC-005 | P1 | Unit | ドライブモックで `read_sectors_raw` が `CDDriveReadError` を送出する設定 | トラック長: 100セクタ | `read_track_sectors` を実行 | `CDDriveReadError` がパイプライン上位へ適切に伝播され、クラッシュしないこと | パイプライン層のエラー伝播検証 |

---

### カテゴリ 6: 回帰テストおよび実機・手動検証 (Regression & E2E / Manual)

| テスト ID | 対応AC | 優先度 | レベル | 前提条件 | 入力 / テストデータ | 実行手順 | 期待結果 | 異常系・境界値・設計根拠 |
|---|---|---|---|---|---|---|---|---|
| **TC-REG-001** | AC-004 | P0 | Regression | リポジトリの現行環境 | 既存テストスイート | `python -m unittest discover tests` を実行 | 既存の全 48 テストが PASS すること（スキップ・エラー・アサーション失敗がゼロ） | AC-004: 既存機能への無影響・完全回帰防止 |
| **TC-E2E-001** | AC-001 | P0 | E2E / Manual | Windows環境、DAEMON Tools で音楽CD（.cue / .iso / .mdx）を D: ドライブにマウント済み | `start_lba = 0`, `sector_count = 75` | 実機 D: ドライブに対して `drive.read_sectors_raw(0, 75)` を実行 | Win32 error 87 が発生せず、`75 * 2352 = 176,400` バイトの生データが正常に取得できること | AC-001: ユーザー報告の根本原因（Win32 error 87）解消の直接検証 |
| **TC-E2E-002** | AC-002 | P0 | E2E / Manual | Windows環境、DAEMON Tools D: ドライブ | `sector_count = 100` および `sector_count = 150` | 実機 D: ドライブに対して `read_sectors_raw(0, 100)` および `read_sectors_raw(100, 150)` を実行 | Win32 error 87 が発生せず、それぞれ `100 * 2352`, `150 * 2352` バイトのデータが正確に取得できること | AC-002: アダプタ上限（55セクタ）を超える任意セクタ数での実機動作保証 |
| **TC-E2E-003** | AC-003 | P0 | E2E / Manual | Windows環境、DAEMON Tools D: ドライブ | トラック 1 または CD 全体 | アプリケーションの UI またはリッピングパイプラインを実行してリッピングを開始する | トラック 1 のリッピングがエラー（Win32 error 87）なく進行し、FLAC等の音声ファイルとして正常に出力・完了すること | AC-003: アプリケーションとしての主要ユースケースの完全動作検証 |
