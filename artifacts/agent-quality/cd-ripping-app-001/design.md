# Architecture Decision / Design Record

- Task ID: cd-ripping-app-001
- Status: Approved
- Target scope: CD Ripping Application with iTunes Metadata & Auto Speed Optimization

## 1. 要約 (Executive Summary)
本設計は、Windows環境において接続された光学CDドライブからオーディオCD（CD-DA）のTOC（目次・曲構成）および生PCMオーディオセクターを取得し、ドライブ性能（USB外付け／内蔵）に応じた安全・高音質読み込み倍速を自動決定した上で、iTunes Search & Lookup APIから取得したトラック情報・高解像度アートワーク画像を付与し、FFmpegを介してiTunes標準仕様に完全準拠したAAC 256kbps（およびALAC/MP3）ファイルとして出力するデスクトップGUIアプリケーションの全体アーキテクチャを定義する。

design-challenger からの反証指摘（FFmpeg stderr パイプ飽和デッドロック、一般ユーザー権限でのSPTIアクセス拒否、iTunesマルチディスク・曲数不一致、アートワーク不在時のコマンド構文破綻、端数セクター読み込み境界など）に対する具体的な保護機構をすべて設計に組み込み、実用環境およびCI環境の双方で堅牢に動作するアーキテクチャを確立した。

---

## 2. 要求・制約と仮定 (Context, Constraints & Assumptions)

### 2.1 事実と制約 (Facts & Constraints)
1. **実行環境**: Windows 10 / 11 64bit。Python 3.10+（Python 3.14利用可能）。
2. **UIフレームワーク**: Python標準ライブラリの `tkinter` / `tkinter.ttk` を使用。高DPIディスプレイに対応するため `shcore.SetProcessDpiAwareness` によるスケーリングを有効化。
3. **外部連携**: システムに導入済みの `ffmpeg` CLI を利用してエンコードおよびタグ付けを実施。
4. **ハードウェア制御**: Windows標準の Win32 / SPTI (SCSI Pass-Through Interface) API を Python `ctypes` 経由で呼び出し、光学ドライブ検出、TOC取得、倍速制御（MMC SET CD SPEED）、セクター読み込みを行う。
5. **外部API**: iTunes Search API (`https://itunes.apple.com/search`) および Lookup API (`https://itunes.apple.com/lookup`) を使用。

### 2.2 仮定と耐障害性方針 (Assumptions & Resilience)
1. **SPTI権限境界**: 一般ユーザー権限で `\\.\<DriveLetter>:` をリードオープン（`GENERIC_READ`）して `IOCTL_CDROM_RAW_READ` や `IOCTL_SCSI_PASS_THROUGH_DIRECT` を実行するが、WindowsのUAC/デバイスポリシーにより `ERROR_ACCESS_DENIED` が返る場合がある。この場合、管理者権限昇格ガイダンス（`ShellExecuteW(..., "runas", ...)`）および安全な仮想CDモードへの切替を行う。
2. **アートワーク柔軟性**: アートワークが存在しない場合やダウンロードに失敗した場合でもエンコード処理が失敗しないよう、動的なコマンドライン引数構築を行う。
3. **テスト自動化**: 物理CDドライブのない環境でも、全機能（GUI、iTunes API連携、エンコード、タグ検証）を完全に回帰テストできる仮想CDドライブ（`VirtualCDDrive`）を提供する。

---

## 3. 推奨アーキテクチャ (Proposed Architecture)

### 3.1 レイヤ構造とコンポーネント構成図
```text
+-----------------------------------------------------------------------------------+
|                            GUI Layer (Tkinter / TTK)                              |
|  - CDRipperAppView (DPI Aware, Treeview, Multi-Progress, Cover Canvas, Log View)   |
+-----------------------------------------------------------------------------------+
                                    │ (User Actions / Events)
                                    ▼
+-----------------------------------------------------------------------------------+
|                        Application / Presenter Layer                              |
|  - CDRipperPresenter (State Management, Worker Thread Lifecycle, Queue Dispatch)  |
+-----------------------------------------------------------------------------------+
             │                                   │                           │
             ▼                                   ▼                           ▼
+-------------------------+    +-------------------------+    +-----------------------------+
|    Hardware Services    |    |    Metadata Services    |    |      Pipeline Services      |
|  - ICDDrive (Interface) |    |  - IMetadataProvider    |    |  - AudioRipPipeline         |
|    ├─ WindowsSPTICDDrive|    |    ├─ ITunesApiClient   |    |    ├─ Sector Boundary Reader|
|    └─ VirtualCDDrive    |    |    └─ MockMetadataProvider   - FFmpegEncoder               |
|  - DriveSpeedOptimizer  |    +-------------------------+    |    │  ├─ Stderr Reader Thread|
+-------------------------+                                   |    │  └─ Dynamic Tag Builder|
                                                              |    └─ TempFileManager (Safe)|
                                                              +-----------------------------+
```

### 3.2 デッドロックフリーなストリーミング・スレッドモデル
```text
 [ Main UI Thread (Tkinter mainloop) ]
        │  (1) Start Rip Clicked
        ▼
   Worker Thread ─────────────────────────────────────────────────────────────+
        │                                                                     │
        ├─▶ [ Sector Boundary Reader ] (batch = min(75, remaining_sectors))   │
        │        │ Raw PCM (s16le, 44100Hz, Stereo, 2352 bytes/sector)        │
        │        ▼                                                            │
        ├─▶ [ FFmpeg Subprocess (stdin pipe) ]                                │
        │        │ stdin.write(pcm_chunk)                                     │
        │        │                                                            │
        │        ├─▶ [ Background Stderr Reader Thread ]                      │
        │        │        │ Reads stderr continuously to avoid pipe deadlock  │
        │        │        │ Parses encode progress (time=..., speed=...)      │
        │        ▼        ▼                                                   │
        │   Output File (.m4a)                                                │
        │                                                                     │
        ├─▶ Queue.put(ProgressEvent(track, percent, eta)) ────────────────────┤
        ▼                                                                     │
 [ UI Thread: root.after(50, poll_queue) ] ◀──────────────────────────────────+
        │ (Progress Bar, Speed, Log Update)
        ▼
```

---

## 4. コンポーネント責務と契約 (Component Responsibilities & Contracts)

### 4.1 コンポーネント詳細責務
1. **`cdripper.hardware.spti_drive.WindowsSPTICDDrive`**:
   - `CreateFileW` によるデバイスオープン（`GENERIC_READ | GENERIC_WRITE`、失敗時は `GENERIC_READ` にフォールバック）。
   - `IOCTL_CDROM_READ_TOC_EX` または `IOCTL_CDROM_READ_TOC` によるTOC取得。
   - セクター読み込み時、まず `IOCTL_CDROM_RAW_READ` を試行し、機能未サポート（`ERROR_INVALID_FUNCTION`）の場合は MMC `READ CD (0xBE)` を `IOCTL_SCSI_PASS_THROUGH_DIRECT` 経由で実行。
   - アクセス拒否（`ERROR_ACCESS_DENIED`）発生時は専用の `CDDriveAccessDeniedError` を送出。
2. **`cdripper.hardware.speed_optimizer.DriveSpeedOptimizer`**:
   - バス種別（USB / SATA）および最大倍速から安全倍速を決定。
   - 最大倍速未取得時はデフォルトフォールバック（USB: 8x、SATA: 16x、UNKNOWN: 8x）を適用。
   - `SET CD SPEED` 失敗時は警告ログを記録して処理を継続（非致命的）。
3. **`cdripper.pipeline.ffmpeg_encoder.FFmpegEncoder`**:
   - `subprocess.Popen` を `shell=False` で実行。
   - `stderr` のOSパイプ詰まりによるデッドロックを防止するため、専用の `stderr_reader_thread` を起動し非同期ドレインおよび進捗解析を行う。
   - アートワーク存在時のみ動的に `-i <cover> -map 1:0 -c:v copy -disposition:v:0 attached_pic` を引数配列に追加。
   - 一時ファイルは `tempfile.NamedTemporaryFile` を使い、`try...finally` で確実に削除。
4. **`cdripper.pipeline.rip_pipeline.AudioRipPipeline`**:
   - 端数セクター境界計算: `batch = min(75, remaining_sectors)` によりLead-out超過アクセスを防止。
   - キャンセル発生時は `process.terminate()` 後、プロセス終了を待機（`process.wait(timeout=3)`）してから不完全な出力ファイルを削除。
5. **`cdripper.metadata.itunes_client.ITunesApiClient`**:
   - iTunes API検索およびトラックルックアップ。
   - マルチディスク対応: `discNumber` によるグループ化・フィルタリング。
   - 演奏時間（TOCのdurationとAPIのtrackTimeMillis）の差分マッチング。
   - 高解像度アートワークURL置換: 正規表現 `re.sub(r'\d+x\d+bb\.', '1200x1200bb.', url)`。
6. **`cdripper.ui.app_view.CDRipperAppView`**:
   - Windows High-DPI対応（`SetProcessDpiAwareness(1)`）。
   - トラックリストTreeview、メタデータ手動編集/照合プレビュー、全体・個別進捗バー、リアルタイムログ。

### 4.2 インターフェース契約定義 (Interfaces)

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Callable
from cdripper.domain.models import DriveInfo, DiscTOC, AlbumMetadata, RipConfig, RipProgress

class ICDDrive(ABC):
    @abstractmethod
    def list_drives(self) -> List[DriveInfo]: ...

    @abstractmethod
    def open(self, drive_letter: str) -> bool: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def read_toc(self) -> DiscTOC: ...

    @abstractmethod
    def set_read_speed(self, speed_x: int) -> bool: ...

    @abstractmethod
    def read_sectors_raw(self, start_lba: int, sector_count: int) -> bytes: ...

class IMetadataProvider(ABC):
    @abstractmethod
    def search_albums(self, query: str, country: str = "jp", limit: int = 10) -> List[AlbumMetadata]: ...

    @abstractmethod
    def lookup_album_tracks(self, collection_id: int, country: str = "jp") -> AlbumMetadata: ...

    @abstractmethod
    def download_artwork(self, artwork_url: str, size: int = 1200) -> Optional[bytes]: ...

class IAudioEncoder(ABC):
    @abstractmethod
    def start_encoding_session(
        self,
        output_path: str,
        config: RipConfig,
        track_metadata: dict,
        artwork_bytes: Optional[bytes]
    ) -> 'EncoderSession':
        """
        標準入力ストリームと安全なstderrドレインスレッドを持つセッションを返す。
        書き込み完了時は session.finish() を呼び出す。
        """
        pass
```

---

## 5. データモデル / API / 状態遷移

### 5.1 データモデル契約 (Data Models)
```python
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

class BusType(str, Enum):
    USB = "USB"
    SATA = "SATA"
    ATAPI = "ATAPI"
    VIRTUAL = "VIRTUAL"
    UNKNOWN = "UNKNOWN"

class EncodeFormat(str, Enum):
    AAC_256K = "AAC (256kbps .m4a)"
    ALAC = "ALAC (Lossless .m4a)"
    MP3_320K = "MP3 (320kbps .mp3)"

@dataclass(frozen=True)
class DriveInfo:
    drive_letter: str            # 例: "D:"
    display_name: str            # 例: "PIONEER BD-RW BDR-XD07 (USB)"
    bus_type: BusType
    is_ready: bool
    max_read_speed_x: int        # 未取得時は 0
    recommended_speed_x: int     # 自動算出された推奨安全倍速

@dataclass(frozen=True)
class TrackTOC:
    track_number: int            # 1-based
    start_lba: int
    end_lba: int
    sector_count: int            # end_lba - start_lba
    duration_seconds: float      # sector_count / 75.0
    is_audio: bool

@dataclass(frozen=True)
class DiscTOC:
    first_track: int
    last_track: int
    total_tracks: int
    total_duration_seconds: float
    tracks: List[TrackTOC]

@dataclass
class TrackMetadata:
    track_number: int
    track_title: str
    artist_name: str
    duration_millis: int
    disc_number: int = 1

@dataclass
class AlbumMetadata:
    collection_id: int
    album_name: str
    artist_name: str
    release_year: str
    genre: str
    total_tracks: int
    total_discs: int = 1
    artwork_url: Optional[str] = None
    artwork_data: Optional[bytes] = None
    tracks: List[TrackMetadata] = field(default_factory=list)

@dataclass
class RipConfig:
    output_dir: str
    format: EncodeFormat = EncodeFormat.AAC_256K
    selected_speed_x: int = 8
    speed_mode_auto: bool = True
    filename_template: str = "{track_num:02d} - {title}.m4a"

@dataclass
class RipProgress:
    current_track: int
    total_tracks: int
    track_progress_percent: float
    overall_progress_percent: float
    current_speed_x: float
    status_text: str
    is_finished: bool = False
    error_message: Optional[str] = None
```

### 5.2 トラック終端LBA境界計算アルゴリズム
```python
def read_track_sectors(drive: ICDDrive, track: TrackTOC, on_chunk: Callable[[bytes], None]):
    remaining = track.sector_count
    current_lba = track.start_lba
    batch_size = 75  # 1秒分 = 75セクター (176,400 bytes)

    while remaining > 0:
        count = min(batch_size, remaining)
        chunk = drive.read_sectors_raw(current_lba, count)
        on_chunk(chunk)
        current_lba += count
        remaining -= count
```

### 5.3 デッドロックフリーなFFmpegエンコード実行制御
```python
class EncoderSession:
    def __init__(self, process: subprocess.Popen, temp_cover_path: Optional[str]):
        self.process = process
        self.temp_cover_path = temp_cover_path
        self.stderr_lines = []
        self._reader_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._reader_thread.start()

    def _drain_stderr(self):
        try:
            for line in iter(self.process.stderr.readline, b''):
                self.stderr_lines.append(line.decode('utf-8', errors='replace'))
        except Exception:
            pass

    def write_pcm(self, data: bytes):
        try:
            self.process.stdin.write(data)
        except (BrokenPipeError, OSError) as e:
            raise EncodingError(f"FFmpeg stdin pipe broken: {e}")

    def finish(self):
        try:
            self.process.stdin.close()
            self.process.wait(timeout=10)
        finally:
            self._cleanup_cover()
            if self.process.returncode != 0:
                err_log = "".join(self.stderr_lines[-20:])
                raise EncodingError(f"FFmpeg failed with code {self.process.returncode}:\n{err_log}")

    def cancel_and_cleanup(self, output_path: str):
        try:
            self.process.terminate()
            self.process.wait(timeout=3)
        except Exception:
            self.process.kill()
        finally:
            self._cleanup_cover()
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except OSError:
                    pass

    def _cleanup_cover(self):
        if self.temp_cover_path and os.path.exists(self.temp_cover_path):
            try:
                os.remove(self.temp_cover_path)
            except OSError:
                pass
```

### 5.4 動的コマンドライン構築とファイル名サニタイズ
```python
import re

def sanitize_filename(name: str) -> str:
    # Windows NTFS 禁止文字の置換
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', name).strip()
    # 予約語回避 (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    if re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$', sanitized, re.IGNORECASE):
        sanitized = f"_{sanitized}"
    # 末尾のピリオド・空白を除去
    sanitized = re.sub(r'[.\s]+$', '', sanitized)
    return sanitized or "Unknown"

def build_ffmpeg_args(output_path: str, format: EncodeFormat, metadata: dict, cover_path: Optional[str]) -> List[str]:
    args = [
        "ffmpeg", "-y",
        "-f", "s16le", "-ar", "44100", "-ac", "2", "-i", "pipe:0"
    ]
    if cover_path and os.path.exists(cover_path):
        args.extend(["-i", cover_path, "-map", "0:a", "-map", "1:0", "-c:v", "copy", "-disposition:v:0", "attached_pic"])
    else:
        args.extend(["-map", "0:a"])

    if format == EncodeFormat.AAC_256K:
        args.extend(["-c:a", "aac", "-b:a", "256k"])
    elif format == EncodeFormat.ALAC:
        args.extend(["-c:a", "alac"])
    elif format == EncodeFormat.MP3_320K:
        args.extend(["-c:a", "libmp3lame", "-b:a", "320k", "-id3v2_version", "3"])

    for k, v in metadata.items():
        if v:
            args.extend(["-metadata", f"{k}={v}"])

    args.append(output_path)
    return args
```

---

## 6. 非機能要件と障害モード (NFR & Failure Modes)

### 6.1 非機能要件対応
1. **応答性 (NFR-001)**:
   - 全ての重い処理（ドライブスキャン、TOC読み出し、API通信、リッピング、エンコード）は非同期ワーカースレッドで実行。
   - UIとの通信はスレッドセーフな `queue.Queue` により50ms間隔でポーリング。
2. **保守性 (NFR-002)**:
   - ハードウェア抽象化（`ICDDrive`）、API抽象化（`IMetadataProvider`）、エンコーダー抽象化（`IAudioEncoder`）によりクリーンアーキテクチャを実現。
3. **テスト容易性 (NFR-003)**:
   - `VirtualCDDrive` により、物理CDやドライブがない環境でも100%自動回帰テストが可能。
4. **堅牢性 (NFR-004)**:
   - パイプデッドロック防止、アクセス拒否時のUAC昇格案内、マルチディスク照合、端数セクター保護を実装。

### 6.2 障害モードと回復戦略 (Failure Modes & Recovery Matrix)
| 障害事象 | 根本原因 | 回復・緩和策 | ユーザー通知 |
|---|---|---|---|
| **SPTIアクセス拒否 (P0)** | Windows UAC / デバイス権限制限 (`ERROR_ACCESS_DENIED`) | 1) `IOCTL_CDROM_RAW_READ`<br>2) MMC `READ CD (0xBE)`<br>3) 昇格再起動ガイダンス<br>4) 仮想CDモードへの切替 | 「CDドライブへの直接アクセス権限がありません。管理者として再起動しますか？」 |
| **パイプ詰まりデッドロック (P0)** | FFmpeg stderrバッファ溢れ | `stderr_reader_thread` による常時ドレイン | ログウィンドウにエラー詳細を即座に出力 |
| **マルチディスク不一致 (P1)** | iTunes APIが複数ディスクの曲を返却 | `discNumber` による絞り込み + 演奏時間マッチング + UI照合確認画面 | 「ディスク構成を確認してください」とダイアログ表示 |
| **アートワーク不在 (P1)** | カバー画像未設定またはDL失敗 | 動的引数生成で `-i <cover>` を除外して音声のみエンコード | 「アートワークなしでエンコードを継続します」とログ出力 |
| **最大倍速未取得 (P1)** | ドライブが速度情報コマンドを非サポート | デフォルト安全速度（USB: 8x, 内蔵: 16x）にフォールバック、`SET CD SPEED` 失敗時は警告扱い | 「安全推奨倍速（8x）で読み込みます」と表示 |
| **端数セクターエラー (P1)** | トラック終端で固定75セクター読み込み | `batch = min(75, remaining)` による厳密な境界制御 | 境界エラーの発生を事前抑止 |

---

## 7. セキュリティ・運用・移行 (Security, Operations & Migration)

1. **コマンドインジェクション防止**:
   - `subprocess.Popen(..., shell=False)` を厳格に適用。引数はリスト形式で渡し、シェル解釈によるインジェクションを根絶。
2. **ファイル名とパストラバーサル防止**:
   - NTFS禁止文字、Windows予約語、親ディレクトリ（`..`）を `sanitize_filename` で無力化。
3. **一時ファイルの安全性**:
   - `tempfile.NamedTemporaryFile` で衝突のない一意な一時ファイルを作成し、`try...finally` で確実に消去。
4. **Windows High-DPI対応**:
   - `ctypes.windll.shcore.SetProcessDpiAwareness(1)` により高解像度環境での描画ぼやけを解消。

---

## 8. 代替案とトレードオフ (Alternatives & Trade-offs)

| 設計観点 | 採用案 | 代替案 | 採用理由・トレードオフ |
|---|---|---|---|
| **stderr処理** | **バックグラウンド別スレッドでドレイン** | `stderr=DEVNULL` またはファイルリダイレクト | **採用案の優位性**: デッドロックを回避しつつ、FFmpegのエラー発生時に直前の詳細エラーログ（20行）を取得してUIに通知可能。 |
| **ドライブアクセス** | **SPTI/RAW_READ + 昇格案内 + 仮想CD** | 外部バイナリ (CDRDAO等) バンドル | **採用案の優位性**: 外部実行ファイルの配布リスクやウイルス対策ソフトの誤検知を回避。 |
| **マルチディスク対応** | **discNumber + 演奏時間差分自動照合** | 単純なトラック番号インデックス照合 | **採用案の優位性**: 2枚組アルバムや曲順違いによるメタデータ誤適用を確実に防止。 |

---

## 9. Design challenge findings (反証指摘と解決記録)

| ID | 重大度 | 指摘内容 (Challenge) | 解決策 (Resolution / Rationale) | ステータス |
|---|---|---|---|---|
| FINDING-001 | P0 | FFmpeg標準入力ストリーミング時のstderrパイプ飽和デッドロック | `EncoderSession` 内で `stderr_reader_thread` を起動し、常時非同期ドレインと進捗パースを行う設計を追加。 | Resolved |
| FINDING-002 | P0 | 一般ユーザー権限での SPTI / RAW_READ 実行不可リスク | `IOCTL_CDROM_RAW_READ` $\rightarrow$ MMC `READ CD (0xBE)` の多重フォールバック、`ShellExecuteW(runas)` による管理者昇格案内、仮想CD切替を明記。 | Resolved |
| FINDING-003 | P1 | iTunes API と CD物理TOC のトラック数・ディスク構成不一致 | `discNumber` による絞り込み、演奏時間（duration）による差分マッチングアルゴリズム、UI照合確認画面を設計。 | Resolved |
| FINDING-004 | P1 | アートワーク非存在時のFFmpeg構文破綻と一時ファイル競合 | 動的コマンドライン引数構築、`tempfile.NamedTemporaryFile` による一意ファイル生成と `try...finally` クリーンアップを設計。 | Resolved |
| FINDING-005 | P1 | ドライブ倍速自動決定における MaxSpeed 未取得時フォールバック | デフォルト安全速度（USB: 8x、内蔵: 16x）フォールバックを定義。`SET CD SPEED` 失敗時は警告ログのみで処理続行。 | Resolved |
| FINDING-006 | P1 | トラック終端LBA境界計算（端数セクターとLead-out超過） | `batch = min(75, remaining_sectors)` による厳密な境界制御を規定し、LBA範囲外アクセスを防止。 | Resolved |
| FINDING-007 | P2 | NTFS禁止文字およびWindows予約語によるファイル生成失敗 | `sanitize_filename` による禁止文字置換および `CON/NUL/COM1` 等の予約語回避ロジックを追加。 | Resolved |
| FINDING-008 | P2 | 高解像度アートワークURL置換の脆弱性 | 正規表現 `re.sub(r'\d+x\d+bb\.', '1200x1200bb.', url)` による解像度表記揺れ・フォーマット対応を追加。 | Resolved |
| FINDING-009 | P2 | リッピングキャンセル時の一時ファイルクリーンアップ漏れ | プロセス終了待機（`process.wait(timeout=3)`）後に未完成出力ファイルを確実に削除する `cancel_and_cleanup` を設計。 | Resolved |
| FINDING-010 | P2 | High-DPIディスプレイでのGUI描画のぼやけ | `SetProcessDpiAwareness(1)` の初期化処理を追加。 | Resolved |

---

## 10. 受入条件への対応表 (Acceptance Criteria Mapping)

| 受入条件ID | 要件概要 | 設計上の対応コンポーネント | 検証方法 |
|---|---|---|---|
| **AC-001** | 光学ドライブの自動検出と選択 | `WindowsSPTICDDrive.list_drives()` / `VirtualCDDrive` / `CDRipperPresenter` | ユニットテスト（ドライブ列挙）およびUIモック検証 |
| **AC-002** | ドライブ性能に応じた読み込み倍速の自動決定・表示 | `DriveSpeedOptimizer` (USB/SATA判別式 + 未取得時フォールバック) | ユニットテスト（USB 24x $\rightarrow$ 8x、SATA 48x $\rightarrow$ 16x、未取得時8x等の境界値テスト） |
| **AC-003** | iTunes API連携（アルバム検索、曲名、アートワーク取得・反映） | `ITunesApiClient` / `MockMetadataProvider` / `discNumber`照合 | APIモックを用いたユニットテスト（高解像度URL正規表現変換、TOCマッピング） |
| **AC-004** | iTunes標準AAC 256kbps出力 & メタデータ・アートワーク付与 | `FFmpegEncoder` (stdinストリーミング + attached_pic + stderrドレイン) | テストエンコード実行後、`ffprobe` 出力解析によるタグ検証テスト |
| **AC-005** | 進捗表示（プログレスバー、ステータス、キャンセル制御） | `queue.Queue` 非同期通信 / `CDRipperAppView` / `EncoderSession.cancel_and_cleanup` | ワーカースレッド進捗シミュレーションテスト |
| **AC-006** | 物理CDなし環境での全パイプライン自動テスト可能 | `VirtualCDDrive` (合成PCMトーン + ダミーTOC) | CI自動回帰テスト（仮想CD $\rightarrow$ iTunesモック $\rightarrow$ エンコード検証） |

---

## 11. 設計上の残存リスクと運用指針 (Residual Risks)

1. **実ドライブのファームウェア差異 (低リスク)**:
   - 極めて古いドライブや特殊な外付けドライブにおいて、MMCコマンドに予期せぬ応答を返す場合がある。
   - *対応*: `ICDDrive` のすべてのSCSI/IOCTL発行箇所で例外を捕捉し、安全なフォールバックとログ出力を徹底しているため、アプリ全体の異常停止は防がれる。
2. **iTunes Search APIのレート制限 (低リスク)**:
   - 連続検索時に一時的なレート制限（HTTP 429）が発生する可能性がある。
   - *対応*: UI上で検索ボタン連打防止のデバウンス制御およびバックオフリトライを行う。
