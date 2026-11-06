# Architecture Decision / Design Record

- Task ID: cd-ripping-app-003
- Status: Approved (Challenged & Revised)
- Target scope: アルバム単位メタデータ編集（ディスク番号、アルバムアーティスト、アルバム名、リリース日、ジャンル、アルバムアート）と全トラック一括反映、およびiTunes API取得時のアルバムアート反映不具合修正

---

## 1. Context and constraints

### 1.1 事実 (Facts)
1. **iTunes API アートワーク反映不具合の根本原因**:
   - `cdripper/metadata/itunes_client.py` は iTunes Search/Lookup API から `1200x1200bb.jpg` (JPEG) のバイナリデータを取得している。
   - `cdripper/ui/app_view.py#L250-L260` において、`tk.PhotoImage(data=b64)` を直接呼び出している。
   - 標準 Tkinter の `tk.PhotoImage` は PNG/GIF/PPM のみをサポートしており、JPEG データを渡すと `TclError: data stream does not have a PNG signature` が発生し、例外ハンドラで `_draw_no_artwork()` に遷移していた。
   - 高解像度画像（1200x1200等）を Canvas（150x150）の描画領域に縮小（アスペクト比維持のリサイズ・サムネイル化）するロジックが存在しなかった。
2. **既存のメタデータタグ体系とFFmpegマッピング**:
   - `cdripper/domain/models.py` の `TrackTagData` は現在 8 項目 (`title`, `artist`, `album`, `track`, `disc`, `date`, `genre`, `encoder`) を保持している。
   - `album_artist` フィールドが存在せず、FFmpeg への出力引数 (`to_metadata_dict()`) にも `-metadata album_artist="..."` が含まれていない。
   - iTunes API の `_parse_album_item` では `collection` オブジェクトの `artistName`（アルバムアーティストに相当）を取得しているが、各トラックのメタデータとは分離管理されていない。
3. **リッピングパイプラインの動作**:
   - `AudioRipPipeline.rip_disc` (`cdripper/pipeline/rip_pipeline.py`) は、`album.artwork_data` をエンコーダセッション `FFmpegEncoder.start_encoding_session` に渡し、一時ファイル書き出し経由で FFmpeg に `-disposition:v:0 attached_pic` として渡している。
   - 手動でアルバム情報を入力・編集した場合、`album` が `None` であってもアルバムアートを設定・適用する手段を設ける必要がある。
4. **実行環境制約**:
   - Python 3.10+ (Python 3.14 対応)。
   - サードパーティライブラリとして画像処理ライブラリ `Pillow` (PIL) が利用可能（新規の外部パッケージ依存追加は禁止）。
   - 既存の全100件のテストスイートが一切のリグレッションなく成功すること。

### 1.2 前提と運用ポリシー (Assumptions & Policies)
1. **SSOT (Single Source of Truth) の整合性**:
   - Presenter の `track_tags: Dict[int, TrackTagData]` が各トラックのメタデータ SSOT であり続ける。
   - アルバム単位の編集が行われた場合、全トラックの該当項目を一括更新する。
2. **個別トラック情報の完全保護 (Protection of Track-Specific Data)**:
   - アルバム単位編集（`update_album_tags`）が実行された際、トラック固有の情報である `title`（曲名）、`track_number`（トラック番号）、`total_tracks`（総トラック数）、および個別トラックの `artist` は絶対に上書き・破壊してはならない。
3. **アルバムアーティスト (`album_artist`) の位置づけ**:
   - アルバム全体の代表アーティスト（例: "Various Artists", "The Beatles" 等）。
   - MP4/M4A では `aART` アトム、MP3 では ID3v2 `TPE2` フレームとして FFmpeg の `-metadata album_artist="..."` により標準的に書き込まれる。
4. **スレッド安全性と不変性**:
   - `TrackTagData` および新規追加する `AlbumTagData` はすべて `@dataclass(frozen=True)` とし、参照整合性を保証する。

---

## 2. Proposed architecture & Design Challenge 反映

### 2.1 Design Challenge への是正反映事項
Gate A 反証フェーズ（`design-challenger`）で検出された重大指摘を設計へ完全に組み込む：

1. **FIND-001是正 (TrackTagEditDialogにおけるalbum_artist維持・編集対応)**:
   - `TrackTagEditDialog` に「Album Artist:」エントリを追加し、既存の `album_artist` を表示・編集可能とする。
   - 保存時（`_validate_and_build_model`）に `album_artist` を引き継ぎ・反映し、個別トラック編集で `album_artist` が消失するバグを未然に防止する。
2. **FIND-002是正 (アートワークの正規化とFFmpeg MP4互換性保証)**:
   - `ArtworkHelper.normalize_artwork(image_bytes, max_dimension=1400) -> Optional[bytes]` を導入。
   - ユーザー選択またはiTunes取得画像（WEBP/BMP/CMYK JPEG含む）を、Decompression Bomb検証・EXIF回転補正を経て、標準的な **RGB JPEG (または透過時PNG)** に再エンコード・正規化（長辺最大1400px、品質90）したバイナリとして保持する。
   - これにより、FFmpeg MP4 (`covr`) のエンコードエラーを根絶し、埋め込みファイルサイズを適正化（200〜400KB）する。
3. **FIND-003是正 (過剰な is_customized=True 付与の防止)**:
   - `update_album_tags` 実行時、全トラックを一律 `is_customized=True` にせず、個別編集フラグは個別トラック編集（タイトルや個別アーティストが変更された場合）のみで付与する。
   - アルバム共通項目（アルバム名・年等）が変更された後でも、iTunes検索によるトラック名自動補完を阻害しない。
4. **FIND-004是正 (Presenter.selected_disc の同期更新)**:
   - `update_album_tags` 内で `self.selected_disc = album_data.disc_number` を確実に更新し、マルチディスクでのiTunes再マッチングやリッピング引数の不整合を防止する。
5. **FIND-005是正 (Dialog相互排他とリッピング中排他ガード)**:
   - `app_view.py` において、`AlbumTagEditDialog` と `TrackTagEditDialog` の二重起動を相互排他制御し、グラブロック（UI無応答）を防止する。リッピング中は両ダイアログ起動を抑止。
6. **FIND-006是正 (メイン画面 txt_album / txt_artist との整合)**:
   - `ALBUM_TAGS_UPDATED` 時にメイン画面の `self.txt_album` および `self.txt_artist` を即座に同期更新する。
7. **FIND-007是正 (EXIF Orientation 補正)**:
   - 画像デコード時に `PIL.ImageOps.exif_transpose` を適用し、スマホ撮影画像等の横転を防止。

---

## 3. Component specifications

### 3.1 Domain Models (`cdripper/domain/models.py`)

#### `AlbumTagData` (新規)
```python
@dataclass(frozen=True)
class AlbumTagData:
    """Immutable data object for album-level metadata and artwork."""
    disc_number: int = 1
    total_discs: int = 1
    album_artist: str = ""
    album: str = ""
    date: str = ""
    genre: str = ""
    artwork_data: Optional[bytes] = None
```

#### `TrackTagData` (拡張・完全後方互換)
```python
@dataclass(frozen=True)
class TrackTagData:
    track_number: int
    total_tracks: int
    disc_number: int
    total_discs: int
    title: str
    artist: str
    album: str
    date: str
    genre: str
    album_artist: str = ""   # 追加 (後方互換デフォルト引数)
    encoder: str = "CD Ripping App (iTunes Compatible)"
    is_customized: bool = False

    def to_metadata_dict(self) -> Dict[str, str]:
        raw = {
            "title": self.title.strip(),
            "artist": self.artist.strip(),
            "album_artist": self.album_artist.strip(),
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
        album_artist: str = "",
        encoder: str = "CD Ripping App (iTunes Compatible)",
        is_customized: bool = False,
    ) -> "TrackTagData":
        return cls(
            track_number=track_number,
            total_tracks=max(1, total_tracks),
            disc_number=disc_number,
            total_discs=max(1, total_discs),
            title=title.strip() if (title and title.strip()) else f"Track {track_number:02d}",
            artist=artist.strip() if (artist and artist.strip()) else "Unknown Artist",
            album=album.strip() if (album and album.strip()) else "Unknown Album",
            date=date.strip(),
            genre=genre.strip(),
            album_artist=album_artist.strip(),
            encoder=encoder.strip(),
            is_customized=is_customized,
        )
```

#### `AlbumMetadata` (拡張)
`album_artist: str = ""` フィールドを追加。

---

### 3.2 Artwork Helper (`cdripper/ui/artwork_helper.py` - 新規)
Pillow を用いた堅牢な画像正規化・縮小・表示ヘルパー。

```python
"""Helper utilities for safely decoding, normalizing, and rendering artwork images."""
from __future__ import annotations

from io import BytesIO
from typing import Optional, Tuple
from PIL import Image, ImageOps, ImageTk

MAX_ARTWORK_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
MAX_IMAGE_PIXELS = 25_000_000             # Decompression Bomb protection
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}


def normalize_artwork(image_bytes: bytes, max_dimension: int = 1400) -> Optional[bytes]:
    """
    Validate, fix EXIF orientation, and normalize artwork to RGB JPEG (or RGBA PNG).
    Guarantees compatibility with FFmpeg MP4 covr atom and prevents bloated rips.
    (FIND-002, FIND-007)
    """
    if not image_bytes or len(image_bytes) > MAX_ARTWORK_SIZE_BYTES:
        return None

    try:
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
        bio = BytesIO(image_bytes)
        img = Image.open(bio)
        img.verify()

        bio.seek(0)
        img = Image.open(bio)
        if img.format not in ALLOWED_IMAGE_FORMATS:
            return None

        # Fix EXIF orientation (FIND-007)
        img = ImageOps.exif_transpose(img)

        # Scale down if exceeds max_dimension
        w, h = img.size
        if max(w, h) > max_dimension:
            scale = max_dimension / max(w, h)
            new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
            resample = getattr(Image.Resampling, "LANCZOS", Image.LANCZOS)
            img = img.resize(new_size, resample=resample)

        out_buf = BytesIO()
        if "A" in img.mode or img.format == "PNG":
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            img.save(out_buf, format="PNG", optimize=True)
        else:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(out_buf, format="JPEG", quality=90, optimize=True)

        return out_buf.getvalue()
    except Exception:
        return None


def load_and_resize_image(image_bytes: bytes, max_size: Tuple[int, int] = (150, 150)) -> Optional[Image.Image]:
    """Decode and thumbnail image for preview rendering."""
    if not image_bytes:
        return None
    try:
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
        bio = BytesIO(image_bytes)
        img = Image.open(bio)
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")
        resample = getattr(Image.Resampling, "LANCZOS", Image.LANCZOS)
        img.thumbnail(max_size, resample=resample)
        return img
    except Exception:
        return None


def create_photo_image(image_bytes: bytes, max_size: Tuple[int, int] = (150, 150)) -> Optional[ImageTk.PhotoImage]:
    """Create Tkinter PhotoImage from image bytes safely."""
    pil_img = load_and_resize_image(image_bytes, max_size)
    if pil_img is None:
        return None
    try:
        return ImageTk.PhotoImage(pil_img)
    except Exception:
        return None
```

---

### 3.3 Presenter Layer (`cdripper/ui/presenter.py`)

1. **PresenterEvent 追加**: `ALBUM_TAGS_UPDATED = "ALBUM_TAGS_UPDATED"`
2. **`update_album_tags(album_data: AlbumTagData)` 実装**:
   - リッピング排他ガード。
   - `self.selected_disc = album_data.disc_number` を更新 (FIND-004)。
   - `self.current_album` の合成・更新 (`album_name`, `album_artist`, `release_year`, `genre`, `disc_number`, `total_discs`, `artwork_data`)。
   - 各トラック (`self.track_tags`) への一括更新：
     - `disc_number`, `total_discs`, `album_artist`, `album`, `date`, `genre` を一括反映。
     - 個別トラックの `title`, `track_number`, `total_tracks` を保護。
     - 個別アーティスト `artist`：トラック固有の編集がされていない、または "Unknown Artist" の場合のみ `album_artist` を反映し、個別アーティストが既に設定されているトラックは保護。
     - 過剰な `is_customized=True` の一律付与を避け、既存の `is_customized` を維持 (FIND-003)。
   - イベントディスパッチ:
     - 全トラックの `PresenterEvent.TRACK_TAG_UPDATED`
     - `PresenterEvent.ALBUM_TAGS_UPDATED` (payload: album_data)
3. **`apply_album_metadata` (iTunes連携時) の拡張**:
   - `album.artwork_data` 取得後に `normalize_artwork` を通して正規化。
   - `album_artist` を各トラックの `TrackTagData` に設定。

---

### 3.4 UI Layer

#### 1. `AlbumTagEditDialog` (`cdripper/ui/album_tag_dialog.py` - 新規)
- モーダルダイアログ (`tk.Toplevel`)。
- 入力項目:
  - Album Title (`txt_album`)
  - Album Artist (`txt_album_artist`)
  - Disc No / Total Discs (`txt_disc_no`, `txt_disc_total`)
  - Year / Date (`txt_date`)
  - Genre (`txt_genre`)
  - Artwork Preview Canvas (120x120), "Choose Artwork..." ボタン, "Clear Artwork" ボタン
- 入力検証:
  - `parse_and_validate_fractional_tag(..., "disc")`
  - `validate_date_string`
  - `sanitize_tag_string`
  - 画像ファイル選択時: `filedialog.askopenfilename`, ファイルサイズ <= 10MB 検証, `normalize_artwork` による変換とプレビュー更新
- ライフサイクル:
  - `transient(parent)`, `protocol("WM_DELETE_WINDOW", self._safe_close)`, Escキーバインド
  - 単一インスタンス管理、二重オープン防止、`grab_set()` と `grab_release()` の完全防御

#### 2. `TrackTagEditDialog` (`cdripper/ui/tag_dialog.py` - 修正)
- 「Album Artist:」入力欄 (`txt_album_artist`) を追加。
- `_load_track_data` で `track_tag.album_artist` を読み込み。
- `_validate_and_build_model` で `album_artist` を取得・サニタイズして渡し、消去バグを解消 (FIND-001)。

#### 3. `CDRipperAppView` (`cdripper/ui/app_view.py` - 修正)
- メイン画面 `ctrl_frame` に「Edit Album Tags...」ボタンを追加。
- アートワーク Canvas クリックでアルバム編集ダイアログを起動。
- アートワーク描画処理を Pillow (`ArtworkHelper.create_photo_image`) に置き換え、iTunes取得のJPEG画像も正しくプレビュー表示。
- `ALBUM_TAGS_UPDATED` 受信時に `txt_album`, `txt_artist`, およびアートワーク Canvas を即時更新。
- ダイアログ相互排他制御（`_album_dialog` と `_track_dialog`）。

---

## 4. Acceptance Criteria & Verification Mapping

| AC ID | 内容 | 検証方法 |
|---|---|---|
| **AC-001** | iTunes APIからアルバム情報（JPEG画像含む）を取得した際、メイン画面のArtworkキャンバスに縮小されたカバーアートが正しくプレビュー表示されること | `test_app_view.py` / `test_artwork_helper.py`: JPEGバイナリをモックし、METADATA_LOADEDでCanvasに描画されることを確認 |
| **AC-002** | メイン画面からアルバム編集ダイアログを開き、ディスク番号・アルバムアーティスト・アルバム・リリース日・ジャンル・アルバムアートの各項目を編集できること | `test_album_tag_dialog.py`: 各エントリの初期ロード、入力値検証、エラー表示を検証 |
| **AC-003** | アルバム単位編集ダイアログで保存を実行した際、全トラックのタグ情報（disc, album_artist, album, date, genre）およびアルバムアートが一括更新され、トラック固有情報が保護されること | `test_presenter.py`: `update_album_tags` 後の全 `track_tags` および `current_album` の同期、トラック名・個別artistの保持を検証 |
| **AC-004** | アルバム編集ダイアログからローカル画像（JPEG/PNG/WEBP）を選択して設定またはクリアでき、プレビューおよびリッピング生成ファイルに反映されること | `test_album_tag_dialog.py`, `test_artwork_helper.py`: 画像の正規化・クリアの動作確認 |
| **AC-005** | アルバム編集で設定した `album_artist` や更新された各タグ、およびアルバムアートが生成された音声ファイルのメタデータに正しく埋め込まれること | `test_ffmpeg_encoder.py`, `test_rip_pipeline.py`: `-metadata album_artist="..."` と一時カバー画像の埋め込みを確認 |
| **AC-006** | 個別トラックタグ編集ダイアログで保存した際にも `album_artist` が保持されること (FIND-001) | `test_tag_dialog.py`: 個別編集保存後も `album_artist` が消去されないことを確認 |
| **AC-007** | 既存機能の無回帰（全100テストがPASSすること） | `py -3 -m unittest discover` で全テストPASSを確認 |
