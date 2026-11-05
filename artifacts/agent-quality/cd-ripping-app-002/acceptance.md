# 最終受入レポート (Final Acceptance Report)

- **Task ID**: cd-ripping-app-002
- **Title**: DAEMON Tools等の仮想ドライブおよびSPTI転送上限に起因する MMC READ CD Win32 エラー 87 (ERROR_INVALID_PARAMETER) の解消
- **Target Revision**: 33cbad8c2e277b89eb0747cbff2c17fa98c7e1e1
- **Completion Date**: 2026-11-06
- **Result**: **RELEASE APPROVED (合格・リリース承認)**

---

## 1. 根本原因と解決のサマリ

### 1.1 根本原因
ユーザーが DAEMON Tools（仮想CDドライブ）を使用してマウントしたオーディオCDからリッピングを開始した際、以下のエラーが発生していました：
`「MMC READ CD failed. Win32 error: 87」` (Win32 エラー 87 = `ERROR_INVALID_PARAMETER`)

詳細調査により判明した根本原因は以下の通りです：
1. DAEMON Tools 仮想ドライブでは `IOCTL_CDROM_RAW_READ` がサポートされない（Win32 エラー 1）ため、MMC READ CD (`IOCTL_SCSI_PASS_THROUGH_DIRECT`) にフォールバックする。
2. しかし、従来の `rip_pipeline.py` は固定値 `batch_size = 75`（75セクタ × 2352バイト = 176,400 バイト ≈ 172.2 KB）で一括読み込みを行っていた。
3. Windows ストレージスタックおよび仮想/物理アダプタには最大転送サイズ制限（`MaximumTransferLength`）が存在する：
   - DAEMON Tools (D:): `MaximumTransferLength = 131,072 バイト` (128 KB, 最大55セクタ)
   - 一般的な USB 光学ドライブ (F:): `MaximumTransferLength = 65,536 バイト` (64 KB, 最大27セクタ)
4. 75セクタ（176,400 バイト）のリクエストは DAEMON Tools の上限 128KB を超過していたため、Windows カーネルストレージスタックが `STATUS_INVALID_PARAMETER` (Win32 エラー 87) を返し、リッピング開始直後にクラッシュしていた。

### 1.2 解決策（多層防御）
1. **ハードウェア層 (`spti_drive.py`)**:
   - `StorageAdapterProperty` クエリにより、`MaximumTransferLength` および `MaximumPhysicalPages` から実効転送上限セクタ数（`_max_transfer_sectors`）を動的に検出（取得失敗時は安全な既定値 25 セクタ ≈ 58.8KB を採用）。
   - `read_sectors_raw` において「透過的チャンク分割（Transparent Chunking）」を実装。呼び出し元が 75 セクタや 150 セクタを要求しても、内部でアダプタ上限以下に自動分割して読み込み・結合して返却。
   - ループ不変量（`step >= 1`）による無限ループ防止、ショートリード Fail-Fast 検証、`RLock` 排他制御を徹底。
2. **パイプライン層 (`rip_pipeline.py`)**:
   - `read_track_sectors` の既定バッチサイズを従来の 75 セクタから **25 セクタ**（1/3秒分 = 58,800 バイト < 64KB）に変更。
   - USB (64KB) や DAEMON Tools (128KB) の転送上限内に自然に収まり、通常リッピング時の分割オーバーヘッドを排除しつつプログレス更新の滑らかさとキャンセル応答性を大幅向上。
   - `batch_size <= 0` の入力バリデーション（`ValueError` 送出）を追加し DoS リスクを完全排除。

---

## 2. 受入条件（AC）充足状況

| 受入条件 ID | 受入条件 | 検証結果 | 証跡・詳細 |
|---|---|:---:|---|
| **AC-001** | DAEMON Tools仮想ドライブ (D:) に対し、`read_sectors_raw(0, 75)` を実行した際、Win32 error 87 が発生せず、75 * 2352 バイトのデータが正常に取得できること | **PASS** | 実機 D: ドライブで 176,400 バイトの取得に完全成功（TC-E2E-001） |
| **AC-002** | `read_sectors_raw` に 100 や 150 などアダプタ上限を超えるセクタ数を指定しても、透過的にチャンク分割されて正確なバイト数が返されること | **PASS** | 実機 D: で 100 セクタ (235,200 バイト)、150 セクタ (352,800 バイト) の取得に完全成功（TC-E2E-002） |
| **AC-003** | リッピングパイプライン (`rip_pipeline.py`) を通じてDAEMON Toolsのトラック1のエンコードがエラーなく進行・完了すること | **PASS** | 実機 D: Track 1 (18,008セクタ) を AAC 256kbps (.m4a, 7.8MB) として 35倍速でリッピング完了（TC-E2E-003） |
| **AC-004** | 既存のユニットテスト・統合テスト（48テスト）がすべてパスし、回帰が発生していないこと | **PASS** | 既存48テストすべて成功、回帰ゼロ（TC-REG-001） |
| **AC-005** | チャンク分割およびアダプタプロパティ取得をカバーする新規ユニットテストが追加され、パスすること | **PASS** | 新規20テストを追加し、テストスイート全 68 テストが 100% 通過 |

---

## 3. レビューおよび監査結果

- **Code Review**: **PASS**（仕様適合、ロジック整合性、スレッドセーフティ確認済み、P0/P1/P2 指摘ゼロ）
- **Security Review**: **PASS**（メモリ安全性、Win32 API境界、型安全性確認済み。指摘 SEC-PIPE-001 を修正完了）
- **Verification Audit**: **PASS**（全 68 テスト終了コード 0、py_compile 構文エラーゼロ、実機 I/O 完全一致）
- **未解決の Critical / High 指摘**: **0 件**
- **未解決の Medium 指摘**: **0 件**

---

## 4. 変更ファイル一覧

| ファイル | 変更概要 |
|---|---|
| `cdripper/hardware/spti_drive.py` | 定数定義、`STORAGE_ADAPTER_DESCRIPTOR` 構造体、`_query_adapter_transfer_limit` 動的クエリ、`read_sectors_raw` 透過的チャンク分割、`_read_sectors_chunk` フォールバック・Fail-Fast検証、`RLock` 排他制御、`close()` 初期化 |
| `cdripper/pipeline/rip_pipeline.py` | `DEFAULT_BATCH_SECTORS = 25`、`read_track_sectors` デフォルト値変更、`batch_size <= 0` バリデーション |
| `tests/test_spti_drive.py` | アダプタプロパティ、境界値（64KB, 1MBキャップ, 1セクタ未満, 0セクタ）、端数分割、障害即時中断、排他制御テストの追加 |
| `tests/test_rip_pipeline.py` | 既定バッチサイズ 25 の検証、不正バッチサイズ（<=0）の `ValueError` 送出テストの追加 |

---

## 5. リリース判定

**判定: 合格 (RELEASE READY)**
本修正により、DAEMON Tools などの仮想CDドライブおよび転送長制限の厳しい外付け USB ドライブにおいて、ユーザーが遭遇していた「MMC READ CD failed. Win32 error: 87」は恒久的に解消され、安全・高速にリッピングが完了することを確認しました。
