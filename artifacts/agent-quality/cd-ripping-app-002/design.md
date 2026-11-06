# Architecture Decision / Design Record

- Task ID: cd-ripping-app-002
- Status: Approved
- Target scope: トラック毎の全項目タグ編集機能のアーキテクチャ設計 (Revision 2)

## Context and constraints

### 1. 事実と制約
1. **システムが書き込む8項目タグ**:
   `cdripper/pipeline/rip_pipeline.py#L122-L131` に準拠：
   - `title`: トラック名 (str)
   - `artist`: トラックアーティスト名 (str)
   - `album`: アルバム名 (str)
   - `track`: トラック番号および総トラック数 (FFmpeg形式: "X/Y")
   - `disc`: ディスク番号および総ディスク数 (FFmpeg形式: "X/Y")
   - `date`: リリース年または日付 (str)
   - `genre`: 音楽ジャンル (str)
   - `encoder`: エンコーダ識別名 (既定: `"CD Ripping App (iTunes Compatible)"`)
2. **実行・ビルド制約**:
   - Python 3.10+（Python 3.14完全準拠）。外部サードパーティライブラリ（pip追加）は一切使用不可。
   - 既存の全68テストが一切のリグレッションなく100%成功すること。
3. **NTFSファイル名規則とタグの分離**:
   - ファイル名テンプレート: `RipConfig.filename_template = "{track_num:02d} - {title}{ext}"`
   - `track_num` には必ず整数（`int`）が渡されなければならない（CHALLENGE-001）。
   - `title` は `sanitize_filename()` を通過してファイル名化され、タグ値には元の完全な文字列（Unicode / 絵文字 / 特殊記号）が維持されなければならない。

### 2. 前提と運用ポリシー
1. **状態同期ポリシー**:
   - TOC読み込み時、またはiTunesメタデータ適用時に、各トラックのデフォルト `TrackTagData` が自動生成される。
   - ユーザーがダイアログで手動編集を行った場合、そのトラックは `is_customized = True` となる。
   - 再度iTunes検索結果を適用しようとした際、`is_customized == True` のトラックが存在する場合は確認プロンプトを表示する（CHALLENGE-003）。
2. **コンピレーション・オムニバス盤の完全許容**:
   - トラック毎に異なる `artist`、`album`、`genre`、`date` を個別に保持できる。

## Proposed architecture

### コンポーネント構成図
```text
+-----------------------------------------------------------------------------------+
|                            GUI Layer (Tkinter / TTK)                              |
|  - CDRipperAppView                                                                |
|    ├─ _set_ripping_ui_state(is_ripping: bool) [排他制御: CHALLENGE-002]           |
|    ├─ _tag_dialog_instance: Optional[TrackTagEditDialog] [シングルトン: CHALLENGE-005]|
|    └─ Treeview (Double-Click & Edit Button Action)                                |
|  - TrackTagEditDialog                                                             |
|    ├─ 8-Field Form (Number/Total Split, Regex Validation: CHALLENGE-004)          |
|    ├─ Safe grab_release() lifecycle (try...finally, protocol WM_DELETE_WINDOW)    |
|    └─ Navigation (< Prev, Next >)                                                 |
+-----------------------------------------------------------------------------------+
                                    │ (User Edit Action / Save)
                                    ▼
+-----------------------------------------------------------------------------------+
|                        Application / Presenter Layer                              |
|  - CDRipperPresenter [SSOT: track_tags: CHALLENGE-006]                           |
|    ├─ track_tags: Dict[int, TrackTagData] (1-based index)                         |
|    ├─ is_ripping: bool [Presenter並行実行ガード: CHALLENGE-002]                    |
|    ├─ update_track_tag(track_number, tag_data)                                    |
|    ├─ sync_album_artist_to_uncustomized(album, artist) [SSOT連動]                 |
|    └─ has_customized_tracks() -> bool                                             |
+-----------------------------------------------------------------------------------+
                                    │ (Start Rip with dict copy of frozen models)
                                    ▼
+-----------------------------------------------------------------------------------+
|                          Pipeline Services Layer                                  |
|  - AudioRipPipeline                                                               |
|    └─ rip_disc(..., track_tags: Optional[Dict[int, TrackTagData]] = None)        |
|         │                                                                         |
|         ├─ Resolve TrackTagData (SSOT priority)                                   |
|         ├─ Format filename using tag.track_number (int) -> NO TYPE ERROR          |
|         ├─ Generate safe_title via sanitize_filename(tag.title)                   |
|         ├─ Build metadata_dict (strip empty tags: CHALLENGE-008)                  |
|         ▼                                                                         |
|  - FFmpegEncoder.start_encoding_session(output_path, config, metadata_dict, ...)   |
+-----------------------------------------------------------------------------------+
                                    │
                                    ▼
+-----------------------------------------------------------------------------------+
|                           Domain Models Layer                                     |
|  - TrackTagData (@dataclass(frozen=True): CHALLENGE-007)                          |
|    ├─ track_number: int, total_tracks: int (CHALLENGE-001)                        |
|    ├─ disc_number: int, total_discs: int                                          |
|    ├─ title: str, artist: str, album: str, date: str, genre: str, encoder: str    |
|    ├─ is_customized: bool (CHALLENGE-003)                                         |
|    ├─ track_tag_value -> "X/Y"                                                    |
|    ├─ disc_tag_value -> "X/Y"                                                     |
|    └─ to_metadata_dict() -> Dict[str, str] (strips empty strings)                 |
+-----------------------------------------------------------------------------------+
```

## Component responsibilities and dependency direction

| コンポーネント | 所在ファイル | 責務と不変条件 |
|---|---|---|
| `TrackTagData` | `cdripper/domain/models.py` | **不変値オブジェクト (`frozen=True`)**。<br>全8項目の保持。トラック/ディスクの整数値とタグ文字列の明確な分離。空文字除外辞書変換。手動編集フラグ `is_customized` の保持。 |
| `AudioRipPipeline` | `cdripper/pipeline/rip_pipeline.py` | `track_tags` を最優先データソースとして解決。<br>`tag.track_number`（`int`）を用いた安全なファイル名生成。空タグの除外。 |
| `CDRipperPresenter` | `cdripper/ui/presenter.py` | **タグデータのSSOT（Single Source of Truth）保持者**。<br>TOC・iTunesメタデータ同期、`track_tags` の状態更新、リッピング中の多重実行防止ガード（`is_ripping`）、手動カスタマイズ追跡。 |
| `CDRipperAppView` | `cdripper/ui/app_view.py` | メイン画面UI。<br>リッピング中の全コンポーネント一括排他制御（`_set_ripping_ui_state`）。手動編集上書き確認プロンプト。ダイアログのシングルトン起動管理。 |
| `TrackTagEditDialog` | `cdripper/ui/tag_dialog.py` | モーダルダイアログ。<br>厳格な入力値検証（正規表現、範囲、NULL/改行サニタイズ、256文字制限）。安全なモーダルライフサイクル（`grab_release()` 漏洩防止）。前後曲ナビゲーション。 |

- 依存矢印は常に `UI -> Presenter -> Pipeline / Domain` の単方向を維持する。

## API / event / data contracts

### 1. 不変ドメインモデル契約: `TrackTagData`
```python
from dataclasses import dataclass, replace
from typing import Dict, Optional

@dataclass(frozen=True)
class TrackTagData:
    """
    Immutable tag metadata for an individual audio track.
    guarantees mathematical thread-safety across UI and background worker threads.
    """
    track_number: int            # 1-based track index (Strictly int for filename template)
    total_tracks: int            # Total tracks count on disc
    disc_number: int             # 1-based disc index
    total_discs: int             # Total discs count
    title: str                   # Track title
    artist: str                  # Artist name
    album: str                   # Album title
    date: str                    # Release year/date (e.g., "2024")
    genre: str                   # Music genre
    encoder: str = "CD Ripping App (iTunes Compatible)"
    is_customized: bool = False  # Tracked for overwrite confirmation

    @property
    def track_tag_value(self) -> str:
        """FFmpeg track tag formatted as 'X/Y' or 'X'."""
        return f"{self.track_number}/{self.total_tracks}" if self.total_tracks > 0 else str(self.track_number)

    @property
    def disc_tag_value(self) -> str:
        """FFmpeg disc tag formatted as 'X/Y' or 'X'."""
        return f"{self.disc_number}/{self.total_discs}" if self.total_discs > 0 else str(self.disc_number)

    def to_metadata_dict(self) -> Dict[str, str]:
        """Convert to FFmpeg metadata dictionary, stripping empty tags."""
        raw = {
            "title": self.title.strip(),
            "artist": self.artist.strip(),
            "album": self.album.strip(),
            "track": self.track_tag_value,
            "disc": self.disc_tag_value,
            "date": self.date.strip(),
            "genre": self.genre.strip(),
            "encoder": self.encoder.strip(),
        }
        return {k: v for k, v in raw.items() if v}

    @classmethod
    def create_default(
        cls,
        track_number: int,
        total_tracks: int,
        title: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        disc_number: int = 1,
        total_discs: int = 1,
        date: str = "",
        genre: str = "",
        encoder: str = "CD Ripping App (iTunes Compatible)",
        is_customized: bool = False,
    ) -> "TrackTagData":
        return cls(
            track_number=track_number,
            total_tracks=max(1, total_tracks),
            disc_number=disc_number,
            total_discs=max(1, total_discs),
            title=title.strip() if title else f"Track {track_number:02d}",
            artist=artist.strip() if artist else "Unknown Artist",
            album=album.strip() if album else "Unknown Album",
            date=date.strip(),
            genre=genre.strip(),
            encoder=encoder.strip(),
            is_customized=is_customized,
        )
```

### 2. Presenter 契約拡張: `CDRipperPresenter`
- 状態:
  - `self.track_tags: Dict[int, TrackTagData] = {}`
  - `self.is_ripping: bool = False`
- 公開メソッド:
  - `get_track_tag(self, track_number: int) -> Optional[TrackTagData]`
  - `get_all_track_tags(self) -> Dict[int, TrackTagData]`
  - `has_customized_tracks(self) -> bool`
  - `update_track_tag(self, track_number: int, tag_data: TrackTagData) -> None`
  - `sync_album_artist_to_uncustomized(self, album: str, artist: str) -> None`
- イベント:
  - `PresenterEvent.TRACK_TAG_UPDATED = "TRACK_TAG_UPDATED"` (payload: `(track_number, tag_data)`)

### 3. Pipeline 契約拡張: `AudioRipPipeline.rip_disc`
```python
def rip_disc(
    self,
    drive: ICDDrive,
    toc: DiscTOC,
    album: Optional[AlbumMetadata],
    config: RipConfig,
    progress_callback: Callable[[RipProgress], None],
    cancel_event: threading.Event,
    disc_number: int = 1,
    track_tags: Optional[Dict[int, TrackTagData]] = None,
) -> None:
```

## State transitions and error semantics

1. **初期状態（CD未挿入）**: `track_tags` は空。編集不可。
2. **TOCロード完了**: 全トラックの `TrackTagData` をデフォルト値で初期生成。編集可能。
3. **iTunesメタデータ取得完了**: 取得したタイトル、アーティスト名、アルバム名、ジャンル、年、トラック番号、ディスク番号で各トラックの `TrackTagData` を更新。手動編集トラックが存在する場合は上書き確認プロンプトを表示。
4. **タグ個別編集**: ダイアログで入力検証（トラック/ディスク番号の書式、制御文字除去など）。保存で Presenter と Treeview を更新し `is_customized=True`。
5. **リッピング実行中**: `_set_ripping_ui_state(True)` によりUI全操作を無効化（Cancelのみ有効）。`dict(self.track_tags)` のスナップショットをワーカースレッドへ渡す。

## Security and trust boundaries

- **NTFSファイルシステム保護**: トラックタイトルに `\ / : * ? " < > |` や Windows 予約語が含まれていても、`sanitize_filename()` によりファイル名は安全にエスケープ。内部タグにはユーザー入力の完全な文字列が保持される。
- **ファイル名フォーマット安全性**: ファイル名フォーマット `{track_num:02d}` には必ず `tag.track_number`（`int`）が渡されるため、書式例外は物理的に発生しない。
- **入力サニタイズ**: `sanitize_tag_string()` により制御文字・ヌルバイトを除去し、最大256文字に制限。
- **コマンドインジェクション防止**: `subprocess.Popen(args, shell=False)` による配列渡しを厳格に維持。

## Reliability, performance, observability, and operations

- **完全スレッドセーフティ**: `TrackTagData` を不変オブジェクト（`frozen=True`）とし、浅いコピーでも競合状態を完全に排除。
- **包括的UI排他**: リッピング中のドライブ再オープンやメタデータ再適用をUIおよびPresenterの両層で完全にガード。
- **モーダル安全ライフサイクル**: ダイアログ破棄時に確実に `grab_release()` を実行し、親ウィンドウのイベントループ固着を防止。

## Migration / compatibility / rollback

- デフォルト引数 `track_tags: Optional[Dict[int, TrackTagData]] = None` により、既存のテスト・呼び出し元と100%後方互換性を維持。
- ロールバック時は追加モデル・ダイアログの削除およびパイプライン引数削除で容易に復元可能。

## Alternatives and trade-offs

- **案A (Treeviewインライン編集)**: 画面外の残り6項目（アルバム、年、ジャンル、エンコーダ等）が編集できないため却下。
- **案B (常設サイドパネル)**: 既存画面サイズ（800x600）を過度に圧迫するため却下。
- **案C (モーダルダイアログ `TrackTagEditDialog`)**: 全8項目を網羅し、明快な操作性と高DPI対応、バリデーションを提供できるため採用。

## Design challenge findings
| ID | Severity | Challenge (反証内容) | Resolution / rationale (解消策と設計根拠) | Status |
|---|---|---|---|---|
| **CHALLENGE-001** | **Critical (P0)** | `TrackTagData.track` が文字列（"1/12"）の場合、`filename_template`（`{track_num:02d}`）で `ValueError` クラッシュが発生する。 | `TrackTagData` に `track_number: int`, `total_tracks: int`, `disc_number: int`, `total_discs: int` を厳格な整数型フィールドとして保持。ファイル名生成には `custom_tag.track_number`（`int`）を渡し、FFmpegタグにはプロパティ `track_tag_value`（"1/12"）を渡すよう分離。 | **Resolved** |
| **CHALLENGE-002** | **High (P1)** | リッピング中に Drive選択、Refresh、Virtual CD Mode、iTunes検索、Editボタンが操作可能であり、SPTハンドル切断やUI不整合が発生する。 | `_set_ripping_ui_state(is_ripping)` を新設し、リッピング中は全コントロールを一括 `DISABLED` 化（Cancelのみ `NORMAL`）。Presenterにも `is_ripping` ガードを実装。 | **Resolved** |
| **CHALLENGE-003** | **High (P1)** | 手動編集後にiTunes検索・メタデータ適用やTOC再読込を行うと、ユーザーの編集内容が無断で上書き消失する。 | `TrackTagData` に `is_customized: bool` を導入。手動編集トラックが存在する場合は、上書き前に `messagebox.askyesno` による明示的確認ダイアログを表示。 | **Resolved** |
| **CHALLENGE-004** | **High (P1)** | "0/0", 負数, 改行文字, ヌル文字, 256文字超過入力に対するバリデーションが未定義。 | `sanitize_tag_string()`（制御文字・ヌル除去、256文字制限）および `parse_and_validate_fractional_tag()`（正規表現による1〜999の整数チェック、ゼロ・負数遮断）の契約を確立。 | **Resolved** |
| **CHALLENGE-005** | **Medium (P2)** | ダブルクリック連打等によるダイアログの多重起動リスクと、モーダル `grab_release()` の漏洩リスク。 | AppViewで `_tag_dialog_instance` のシングルトン管理（多重起動時は前面化）。ダイアログ破棄時に `try...finally` で `grab_release()` を確実に実行。 | **Resolved** |
| **CHALLENGE-006** | **Medium (P2)** | メイン画面の Album/Artist 入力欄とトラック個別タグの SSOT（真実の情報源）が曖昧。 | SSOTを Presenterの `track_tags` に統一。メイン画面の Album/Artist 変更時は未カスタマイズトラックへ即時連動させ、パイプラインでは `track_tags` を最優先参照。 | **Resolved** |
| **CHALLENGE-007** | **Medium (P2)** | 浅いコピー（shallow copy）によるマルチスレッド競合リスク。 | `TrackTagData` を `@dataclass(frozen=True)`（完全不変オブジェクト）化。UIでの編集時は常に新インスタンスを生成代入し、辞書コピーだけで数学的に安全なスレッドセーフティを実現。 | **Resolved** |
| **CHALLENGE-008** | **Low (P3)** | 空文字タグの出力仕様（空文字を渡すか、除外するか）の未定義。 | `to_metadata_dict()` において、空白文字のみの項目は辞書から自動除外（空タグはFFmpeg `-metadata` に出力しない）する仕様を明文化。 | **Resolved** |

## Acceptance criteria mapping

| Acceptance ID | 要件・受入条件 | 設計対応要素 | 検証方法 |
|---|---|---|---|
| **AC-001** | トラック一覧でトラックを選択して編集ダイアログを開いた時、システムが書き込む全8項目（title, artist, album, track, disc, date, genre, encoder）の現在値が表示され編集できること | `TrackTagEditDialog` の8項目入力フィールドと初期値バインド | 単体テスト（ダイアログ初期化・表示検証） & 手動UI確認 |
| **AC-002** | 編集ダイアログで全項目を変更して保存した時、そのトラックのタグ情報が更新され、トラック一覧の表示（title, artist等）にも即時反映されること | `Presenter.update_track_tag()` と Treeview 行更新ロジック、`is_customized=True` 付与 | 単体テスト（Presenter/View連携テスト） |
| **AC-003** | トラック毎に異なるアルバム名・アーティスト名・年・ジャンル・エンコーダ等を設定してリッピングを実行した時、生成された各ファイルのメタデータ（ffprobe検証）に各トラックの編集値が反映されていること | `AudioRipPipeline.rip_disc` の `track_tags` 適用とFFmpeg引数構築 | 統合テスト（`test_integration.py` / ffprobeタグ検証） |
| **AC-004** | トラック番号・ディスク番号の編集（"2/10" や "1/2" など）が正しくパース・検証され、FFmpegタグに渡されること（"0/0" や負数は遮断されること） | `parse_and_validate_fractional_tag()` と `TrackTagData.track_tag_value` | 単体テスト（バリデーション境界値テスト） |
| **AC-005** | トラックタイトルにNTFS禁止文字（`\ / : * ? " < > |`）や特殊文字が含まれる場合でも、ファイル名はサニタイズされつつタグには元の文字列が保持され、整数型トラック番号でファイル名生成されること | `tag.track_number`（`int`）と `sanitize_filename(tag.title)` の適用 | 単体テスト（パイプライン出力パスおよびメタデータ辞書検証） |
| **AC-006** | 既存の全68テストが一切のリグレッションなくPASSすること | 後方互換性設計（デフォルト引数 `track_tags=None`） | `py -3 -m unittest discover -v` |

## Residual risks / open questions

- **残存リスク**:
  - なし（反証指摘 CHALLENGE-001〜008 の解消により、設計上の重大リスクはすべて排除完了）。
- **未決事項**:
  - 前後曲ナビゲーション（`[ < Prev Track ]`, `[ Next Track > ]`）はダイアログ下部に配置し、未保存の変更がある場合は自動保存または確認を挟んでスムーズに連続編集できる仕様として採用する。
