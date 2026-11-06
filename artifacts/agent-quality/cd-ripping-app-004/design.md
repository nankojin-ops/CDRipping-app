# Architecture Design Document: Task `cd-ripping-app-004` (Revised)
**出力フォルダ階層化 (`<Album Artist>/<Album>/`) および トラックファイル名へのCD番号付与 (`{disc_number}-{track_num:02d} {title}{ext}`)**

- **Task ID**: `cd-ripping-app-004`
- **Revision**: Rev 2 (Design Challenge Feedback Applied)
- **Status**: Approved for Implementation Planning
- **Target Components**:
  - `cdripper/domain/models.py` (`RipConfig`)
  - `cdripper/pipeline/rip_pipeline.py` (`resolve_track_output_path`, `AudioRipPipeline`)
  - `tests/test_rip_pipeline.py`, `tests/test_integration.py`

---

## 1. 要約 (Executive Summary)

本設計は、CDリッピング時に出力先ルートディレクトリ配下に `<Album Artist>/<Album>/` のディレクトリ階層を自動構築し、生成されるトラックファイル名を `{disc_number}-{track_num:02d} {title}{ext}`（例: `1-01 Come Together.m4a`）とする要求（FR-001, FR-002）を実現するものである。

Design Challenge（CHALLENGE-001〜006）における反証をすべて反映し、Windows環境におけるパス正規化（`normcase`）、UNC/異ドライブ時の例外防御、空タグ時の AC-002 準拠（`"Unknown Artist"` / `"Unknown Album"`）、ファイルシステム上の既存ファイル衝突防止（`os.path.exists` 併用）、MAX_PATH (260文字) 制約対策、テンプレートの型安全・構文安全を強化した。

---

## 2. 要求・制約と仮定 (Requirements, Constraints & Assumptions)

### 2.1 要求トレース
- **FR-001 (ディレクトリ階層の構築)**:
  - `<output_dir>/<Album Artist>/<Album>/` 構造を作成。
  - 優先順位: `TrackTagData` ＞ `AlbumMetadata` ＞ フォールバック (`"Unknown Artist"` / `"Unknown Album"`)。
  - サニタイズおよびパストラバーサル防止。
- **FR-002 (トラックファイル名へのCD番号付与)**:
  - `{disc_number}-{track_num:02d} {title}{ext}` 形式の命名規則。
  - `disc_number` は `TrackTagData.disc_number` ＞ `rip_disc` 引数 `disc_number` ＞ `1` の順でバインド。
  - `track_num` は2桁ゼロパディング。
  - カスタムテンプレートの後方互換性維持。
- **FR-003 (GitHubコミット＆プッシュ)**:
  - 全ゲート通過後にクリーンな状態でGitコミット＆プッシュ。

### 2.2 反証指摘への設計対応 (Design Challenge Resolutions)
1. **CHALLENGE-001 (P1: Windows パストラバーサル防御の堅牢化)**:
   - `os.path.normcase` で大小文字差分を正規化。
   - `os.path.commonpath` 実行部を `try...except ValueError:` で囲み、UNC パスや異ドライブ時も安全に `base_output_dir` にフォールバック。
2. **CHALLENGE-002 (P1: AC-002 準拠の明示的フォールバック)**:
   - `sanitize_filename` の戻り値が空または `"Unknown"` の場合、アーティストは `"Unknown Artist"`、アルバムは `"Unknown Album"` に明示的に変換。
3. **CHALLENGE-003 (P1: 既存ファイルとの衝突・上書き防止)**:
   - `seen_output_paths` に加え、ディスク上の `os.path.exists(candidate)` を衝突判定条件に組み込み、過去セッションの既存ファイルをサイレント上書きしない。
4. **CHALLENGE-004 (P2: MAX_PATH 制限対策)**:
   - `max_component_length` のデフォルト値を 60 文字とし、パス長オーバーフローを防止。
5. **CHALLENGE-005 (P2: テンプレート型安全とフォーマット後サニタイズ)**:
   - `disc_number` および `track_number` を必ず `int` 型に変換して辞書にバインド。
   - フォーマット例外は `Exception` 全般を捕捉して安全にフォールバック。
   - フォーマット後のベースファイル名に対してもサニタイズを実施。
6. **CHALLENGE-006 (P2: 既存統合テスト更新仕様)**:
   - `tests/test_integration.py` のファイル探索パスおよびアサーション期待値を新仕様に合わせて更新。

---

## 3. 推奨アーキテクチャ (Proposed Architecture)

### 3.1 コンポーネント関係図 (Component Diagram)

```mermaid
graph TD
    UI[CDRipperPresenter] -->|start_ripping(RipConfig)| Pipeline[AudioRipPipeline]
    Pipeline -->|resolve_track_output_path| Resolver[Path Resolution & Sanitizer]
    Resolver -->|sanitize_filename| Sanitizer[FFmpegEncoder.sanitize_filename]
    Resolver -->|normcase & commonpath & ValueError catch| Security[Path Traversal Guard]
    Pipeline -->|seen_output_paths & os.path.exists| Collision[Collision Avoidance Engine]
    Pipeline -->|os.makedirs| FS[File System / Storage]
    Pipeline -->|start_encoding_session| Encoder[FFmpegEncoder]
    Encoder -->|subprocess & cancel_and_cleanup| Session[EncoderSession]
```

---

## 4. 詳細契約仕様 (Detailed Contracts)

### 4.1 `resolve_track_output_path` (`cdripper/pipeline/rip_pipeline.py`)

```python
def resolve_track_output_path(
    base_output_dir: str,
    disc_number: int,
    track_number: int,
    track_title: str,
    album_artist: Optional[str] = None,
    album_name: Optional[str] = None,
    ext: str = ".m4a",
    filename_template: str = "{disc_number}-{track_num:02d} {title}{ext}",
    max_component_length: int = 60,
) -> str:
    """
    Resolve hierarchical output path: <base_output_dir>/<safe_artist>/<safe_album>/<safe_filename>
    with strict sanitization, path traversal prevention, and safe template substitution.
    """
    # 1. 厳格な型変換
    try:
        disc_num = max(1, int(disc_number))
    except (ValueError, TypeError):
        disc_num = 1

    try:
        trk_num = max(1, int(track_number))
    except (ValueError, TypeError):
        trk_num = 1

    # 2. CHALLENGE-002: 空・空白・不正記号時の明示的フォールバック (AC-002)
    raw_artist = (album_artist or "").strip()
    safe_artist = sanitize_filename(raw_artist, max_length=max_component_length)
    if not safe_artist or safe_artist == "Unknown":
        safe_artist = "Unknown Artist"

    raw_album = (album_name or "").strip()
    safe_album = sanitize_filename(raw_album, max_length=max_component_length)
    if not safe_album or safe_album == "Unknown":
        safe_album = "Unknown Album"

    raw_title = (track_title or "").strip()
    safe_title = sanitize_filename(raw_title, max_length=max_component_length)
    if not safe_title or safe_title == "Unknown":
        safe_title = f"Track {trk_num:02d}"

    # 3. CHALLENGE-001: Windows ドライブ・大文字小文字・UNC 安全なパストラバーサル防御
    abs_base = os.path.normcase(os.path.abspath(base_output_dir))
    target_dir = os.path.abspath(os.path.join(base_output_dir, safe_artist, safe_album))
    norm_target = os.path.normcase(target_dir)

    try:
        common = os.path.commonpath([abs_base, norm_target])
        if common != abs_base:
            target_dir = os.path.abspath(base_output_dir)
    except ValueError:
        # ドライブ不一致やUNCパス時の安全なフォールバック
        target_dir = os.path.abspath(base_output_dir)

    # 4. CHALLENGE-005: 安全なテンプレートフォーマットとサニタイズ
    safe_ext = ext if ext.startswith(".") else f".{ext}"
    fmt_kwargs = {
        "disc_number": disc_num,
        "track_num": trk_num,
        "title": safe_title,
        "ext": safe_ext,
    }
    try:
        filename = filename_template.format(**fmt_kwargs)
    except Exception:
        filename = f"{disc_num}-{trk_num:02d} {safe_title}{safe_ext}"

    if not filename.endswith(safe_ext):
        filename = f"{filename}{safe_ext}"

    # ファイル名自体のNTFS禁止文字除去
    base_name, f_ext = os.path.splitext(filename)
    safe_base = sanitize_filename(base_name, max_length=max_component_length)
    filename = f"{safe_base}{f_ext}"

    return os.path.join(target_dir, filename)
```

### 4.2 `RipConfig` (`cdripper/domain/models.py`)

```python
@dataclass
class RipConfig:
    """Configuration options for a ripping session."""
    output_dir: str
    format: EncodeFormat = EncodeFormat.AAC_256K
    selected_speed_x: int = 8
    speed_mode_auto: bool = True
    filename_template: str = "{disc_number}-{track_num:02d} {title}{ext}"
```

### 4.3 衝突回避と上書き防止 (`AudioRipPipeline.rip_disc`)

```python
output_path = resolve_track_output_path(
    base_output_dir=config.output_dir,
    disc_number=eff_disc_num,
    track_number=eff_track_num,
    track_title=eff_title,
    album_artist=eff_album_artist,
    album_name=eff_album,
    ext=config.format.extension,
    filename_template=config.filename_template,
)

# CHALLENGE-003: 同一セッション内およびファイルシステム上の既存ファイルとの衝突回避
if output_path in seen_output_paths or os.path.exists(output_path):
    base, fext = os.path.splitext(output_path)
    collision_idx = 1
    candidate = f"{base}_{collision_idx}{fext}"
    while candidate in seen_output_paths or os.path.exists(candidate):
        collision_idx += 1
        candidate = f"{base}_{collision_idx}{fext}"
    output_path = candidate

seen_output_paths.add(output_path)
```

---

## 5. テスト改修方針 (`tests/test_integration.py`)

### 5.1 `test_full_virtual_rip_pipeline`
- 出力先ディレクトリを `os.path.join(self.test_dir, "The Beatles", "Abbey Road")` で探索するように更新。
- 生成されるファイル名が `1-01 Come Together.m4a` および `1-02 Something.m4a` であることを検証。

### 5.2 `test_custom_track_tags_full_e2e_ffprobe_verification`
- 出力先ディレクトリを `os.path.join(self.test_dir, "Custom Album Artist", "Custom Album Title")` で探索するように更新。
- ファイル名が `1-01 Custom Track 01.m4a` であることを検証。

---

## 6. 受入条件マトリクス (Traceability Matrix)

| AC ID | 要件概要 | 設計対応 | 検証方法 |
|---|---|---|---|
| **AC-001** | 出力先として `<output_dir>/<Album Artist>/<Album>/` が自動作成されトラックが格納されること | `resolve_track_output_path` + `os.makedirs` | 単体・統合テスト |
| **AC-002** | アルバムアーティストおよびアルバム名が未設定の場合、`"Unknown Artist"` / `"Unknown Album"` が使用されること | CHALLENGE-002 フォールバック | 単体テスト |
| **AC-003** | Windows禁止文字や末尾ドット・空白がサニタイズされ、トラバーサルが防止されること | `sanitize_filename` + `commonpath` + `normcase` | 単体テスト |
| **AC-004** | トラックファイル名が `{disc_number}-{track_num:02d} {title}{ext}` 形式となること | `RipConfig` デフォルト更新 | 単体テスト |
| **AC-005** | 複数枚組CDで `disc_number=2` がファイル名先頭（`2-01 ...`）に反映されること | `disc_number` バインド | 単体テスト |
| **AC-006** | キャンセル時やエンコード異常終了時に仕掛かりファイルがクリーンアップされること | `cancel_and_cleanup` | 単体テスト |
| **AC-007** | 既存ユニットテスト・統合テスト全件合格 (リグレッションなし) | 互換性維持 + E2E更新 | 全件テスト実行 |
| **AC-008** | 品質ゲート全通過後の Git コミット＆プッシュ | オーケストレーション | Git 操作 |
