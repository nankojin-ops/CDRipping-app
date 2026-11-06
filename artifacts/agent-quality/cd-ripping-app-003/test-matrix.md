# QA Test Matrix: アルバム単位メタデータ編集 & アルバムアート反映修正
- **Task ID**: `cd-ripping-app-003`
- **Revision / Context**: 実装コード盲検（要求仕様・受入条件・承認済み設計のみに基づく設計）
- **作成日**: 2026-11-06
- **設計担当**: QA Test Designer (Blind)

---

## 1. テスト設計方針 & カバレッジサマリー

### 1.1 設計方針
1. **実装コード非依存（完全盲検）**: ソースコードの内部実装に依存せず、要求仕様（AC-001 〜 AC-007）および承認済みアーキテクチャ設計（FIND-001 〜 FIND-007是正事項含む）からテスト観点を網羅。
2. **多面的な検証レベル**: Unit（ドメインモデル・正規化ロジック）、Integration（Presenter・タグ反映・イベント連携）、UI（ダイアログ・Canvas描画・排他制御）、E2E（リッピングパイプライン・FFmpeg引数連携）を分離。
3. **境界値・異常系・セキュリティ・並行性の徹底網羅**:
   - ディスク番号の数値境界、日付書式、画像フォーマット（JPEG/PNG/WEBP/BMP/CMYK/EXIF回転）。
   - 悪意ある入力（Decompression Bomb、10MB超ファイル、NULLバイト、インジェクション）。
   - UIライフサイクル（リッピング中排他、モーダル相互排他、grab_release、ヘッドレス実行）。

### 1.2 テストケース統計
- **総テストケース数**: 40 件
  - 正常系 (Normal Cases): 14 件
  - 境界値 (Boundary Cases): 9 件
  - 異常系・堅牢性 (Negative / Robustness Cases): 8 件
  - 並行性・UIライフサイクル (Concurrency / Lifecycle Cases): 6 件
  - セキュリティ・サニタイズ (Security & Sanitization Cases): 3 件
- **優先度別内訳**:
  - P0 (Critical): 8 件
  - P1 (High): 19 件
  - P2 (Medium): 11 件
  - P3 (Low): 2 件
- **テストレベル別内訳**:
  - Unit: 17 件
  - Integration: 14 件
  - UI / Integration: 7 件
  - E2E (Pipeline): 2 件

---

## 2. トレーサビリティマトリクス（受入条件 vs テストケース）

| 受入条件 / 設計要件 | 要件概要 | 該当テストID |
| :--- | :--- | :--- |
| **AC-001** | iTunes API アートワーク（JPEG含む）取得時のプレビュー表示（TclError解消） | TC-AC001-01, TC-AC001-02, TC-AC001-03, TC-AC001-04 |
| **AC-002** | アルバム単位編集ダイアログ起動と各項目表示・編集 | TC-AC002-01, TC-AC002-02, TC-AC002-03, TC-AC002-04 |
| **AC-003** | アルバム単位編集による全トラック一括反映とトラック個別情報保護 | TC-AC003-01, TC-AC003-02, TC-AC003-03, TC-AC003-04, TC-AC003-05 |
| **AC-004** | アートワーク選択（JPEG/PNG/WEBP）・正規化・クリア | TC-AC004-01, TC-AC004-02, TC-AC004-03, TC-AC004-04, TC-AC004-05 |
| **AC-005** | リッピング時の FFmpeg `-metadata album_artist="..."` 及びアートワーク埋め込み | TC-AC005-01, TC-AC005-02, TC-AC005-03, TC-AC005-04 |
| **AC-006** | 個別トラックタグ編集時の `album_artist` 保持 (FIND-001) | TC-AC006-01, TC-AC006-02, TC-AC006-03 |
| **AC-007** | 既存テストスイート全100件の完全後方互換・無回帰 | TC-REG-001, TC-REG-002, TC-REG-003, TC-REG-004 |
| **BND** | ディスク番号、文字列長、解像度、ファイルサイズの境界値 | TC-BND-001 〜 TC-BND-009 |
| **NEG** | 破損ファイル、偽装ファイル、巨大ピクセル、CMYK、不正文字 | TC-NEG-001 〜 TC-NEG-008 |
| **CONC** | リッピング中排他、ダイアログ二重起動防止、grab解放、ヘッドレス | TC-CONC-001 〜 TC-CONC-006 |
| **SEC** | コマンド引数エスケープ、パストラバーサル、リソース枯渇 | TC-SEC-001 〜 TC-SEC-003 |

---

## 3. テストマトリクス詳細仕様

### 3.1 正常系テストケース (Normal Acceptance Cases)

| テストID | 対応AC | 優先度 | レベル | 前提条件 | 入力データ | 実行手順 | 期待結果 | 自動化 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-AC001-01** | AC-001 | **P0** | Integration | iTunesClient から JPEG形式のアートワークバイト列を取得可能な状態 | 有効なJPEG画像バイナリ (300x300, JFIF) | 1. iTunes検索結果を Presenter.apply_album_metadata に渡す。<br>2. メイン画面のアートワーク描画処理をトリガーする。 | Pillow経由で PhotoImage が生成され、`TclError: data stream does not have a PNG signature` が発生せず、Canvas にアートワークが正常描画されること。 | Automated (pytest) |
| **TC-AC001-02** | AC-001 | P1 | Integration | iTunesClient から PNG形式のアートワークバイト列を取得 | 有効なPNG画像バイナリ (300x300) | 1. apply_album_metadata にPNGアートワークを渡す。<br>2. 描画をトリガー。 | 正常に PhotoImage が生成され、Canvas に描画されること。 | Automated (pytest) |
| **TC-AC001-03** | AC-001 | P1 | UI / Unit | iTunes検索結果にアートワークが存在しない | `artwork_data = None` または `b""` | 1. apply_album_metadata に画像なしデータを渡す。 | 例外が発生せず、デフォルトの「No Artwork」プレビュー描画 (`_draw_no_artwork`) が実行されること。 | Automated (pytest) |
| **TC-AC001-04** | AC-001 | P2 | Unit | 高解像度画像（例: 1400x1400） | JPEG画像 (1400x1400) | 1. `ArtworkHelper.create_photo_image` または `load_and_resize_image` を max_size=(150, 150) で呼び出す。 | アスペクト比を維持して最大 150x150 のサイズに正しくリサイズされた画像/PhotoImage が返されること。 | Automated (pytest) |
| **TC-AC002-01** | AC-002 | **P1** | UI | メイン画面が表示され、CDトラックリストが存在する状態 | なし | 1. メイン画面の「Edit Album Tags...」ボタンをクリック。 | AlbumTagEditDialog がモーダル表示され、現在の disc, total_discs, album_artist, album, date, genre, アートワークプレビューが各入力欄に初期表示されること。 | Automated (pytest/UI) |
| **TC-AC002-02** | AC-002 | P2 | UI | メイン画面表示中 | なし | 1. メイン画面のアートワーク描画 Canvas をクリック。 | 「Edit Album Tags...」ボタン押下時と同様に AlbumTagEditDialog がモーダル起動すること。 | Automated (pytest/UI) |
| **TC-AC002-03** | AC-002 | **P0** | UI / Integration | AlbumTagEditDialog 表示中 | disc=2, total=3, album_artist="Various Artists", album="Best Hits 2026", date="2026", genre="Pop" | 1. 各項目を入力。<br>2. 「OK」ボタンをクリック。 | 入力値を含む `AlbumTagData` が Presenter.update_album_tags にコールバックされ、ダイアログが正常に閉じること。 | Automated (pytest/UI) |
| **TC-AC002-04** | AC-002 | P2 | UI | AlbumTagEditDialog 表示中 | 各項目を変更 | 1. 項目を変更後、「Cancel」ボタンまたはウィンドウ閉じる（×）をクリック。 | 変更内容が破棄され、update_album_tags が呼び出されないこと。 | Automated (pytest/UI) |
| **TC-AC003-01** | AC-003 | **P0** | Integration | 複数トラック（Track 1〜10）がロード済み | AlbumTagData(disc=1, total_discs=2, album_artist="Band A", album="Album 1", date="2026", genre="Rock", artwork=bytes) | 1. `Presenter.update_album_tags(album_data)` を実行。 | 全10トラックの `TrackTagData` の disc_number, total_discs, album_artist, album, date, genre, artwork_data が一括更新されること。 | Automated (pytest) |
| **TC-AC003-02** | AC-003 | **P0** | Integration | Track 1のタイトル="Song 1", トラック番号=1, 個別artist="Guest Singer" が設定済み | AlbumTagData(album_artist="Main Artist", album="New Album") | 1. `Presenter.update_album_tags` を実行。 | Track 1 の title="Song 1", track_number=1, artist="Guest Singer" が保持され、album_artist のみが "Main Artist" に更新されること。 | Automated (pytest) |
| **TC-AC003-03** | AC-003 | **P1** | Integration | Track 1 は未編集 (`is_customized=False`)、Track 2 はユーザー編集済み (`is_customized=True`) | 新規 AlbumTagData | 1. `Presenter.update_album_tags` を実行。 | (FIND-003是正) Track 1 は `is_customized=False` が維持され、Track 2 は `is_customized=True` が維持されること（全トラック一律 True に書き換えないこと）。 | Automated (pytest) |
| **TC-AC003-04** | AC-003 | P1 | Integration | Presenter の `selected_disc` が初期値 1 | AlbumTagData(disc_number=2, total_discs=2) | 1. `Presenter.update_album_tags` を実行。 | (FIND-004是正) `Presenter.selected_disc` が 2 に同期更新されること。 | Automated (pytest) |
| **TC-AC003-05** | AC-003 | P1 | UI / Integration | メイン画面の txt_album="Old Album", txt_artist="Old Artist" | AlbumTagData(album="New Album", album_artist="New Artist") | 1. `Presenter.update_album_tags` を実行。<br>2. `PresenterEvent.ALBUM_TAGS_UPDATED` を通知。 | (FIND-006是正) メイン画面の txt_album が "New Album"、txt_artist が "New Artist" に同期更新され、Canvasの画像も同期されること。 | Automated (pytest/UI) |
| **TC-AC004-01** | AC-004 | P1 | UI / Unit | AlbumTagEditDialog 表示中 | 選択ファイル: 有効な JPEG 画像 (800x800) | 1. 「Select Artwork...」を押下しファイルを選択。 | ダイアログ内のプレビュー Canvas に画像が表示され、内部の artwork_data に正規化バイト列が設定されること。 | Automated (pytest) |
| **TC-AC004-02** | AC-004 | P1 | UI / Unit | AlbumTagEditDialog 表示中 | 選択ファイル: 有効な PNG 画像 (800x800) | 1. 「Select Artwork...」を押下し PNG ファイルを選択。 | プレビューが更新され、正常に設定されること。 | Automated (pytest) |
| **TC-AC004-03** | AC-004 | **P1** | Unit | Pillow利用可能環境 | 選択ファイル: 有効な WEBP 画像 (1000x1000) | 1. `ArtworkHelper.normalize_artwork(webp_bytes)` を呼び出す。 | (FIND-002是正) WEBP から RGB JPEG (透過時はPNG) へ再エンコード・正規化されたバイト列が返され、プレビューおよびデータに反映されること。 | Automated (pytest) |
| **TC-AC004-04** | AC-004 | P1 | UI | ダイアログにアートワークが設定済み | なし | 1. 「Clear Artwork」ボタンをクリック。 | アートワークデータが None になり、プレビュー表示が初期の「No Image」プレビューに戻ること。 | Automated (pytest/UI) |
| **TC-AC004-05** | AC-004 | P2 | Unit | EXIF Orientation タグ (例: 値=6, 90度回転) が付与された JPEG 画像 | EXIF付きJPEGバイナリ | 1. `ArtworkHelper.normalize_artwork` を実行。 | (FIND-007是正) `ImageOps.exif_transpose` が適用され、正しい向き（正位置）に回転補正された JPEG バイト列が出力されること。 | Automated (pytest) |
| **TC-AC005-01** | AC-005 | **P0** | Integration | TrackTagData(album_artist="Orchestra X", artist="Soloist Y", album="Symphony") | トラック 1 件のリッピング処理 | 1. `TrackTagData.to_metadata_dict()` を呼び出す。<br>2. エンコード引数生成ロジックを実行。 | `to_metadata_dict()` に `"album_artist": "Orchestra X"` が含まれ、FFmpeg コマンド引数に `-metadata album_artist=Orchestra X` が正確に含まれること。 | Automated (pytest) |
| **TC-AC005-02** | AC-005 | **P0** | E2E / Integration | artwork_data に有効な画像バイナリが存在する | リッピング実行パイプライン | 1. リッピング・エンコードパイプラインを実行。 | 一時画像ファイルが生成され、FFmpeg コマンド引数にアートワーク入力 (`-i temp_art.jpg`) および添付マッピング (`-map 0:a -map 1:v` または covr タグ) が付与され、処理後に一時ファイルが削除されること。 | Automated (pytest) |
| **TC-AC005-03** | AC-005 | P1 | Integration | artwork_data が None | リッピング実行パイプライン | 1. リッピング・エンコードパイプラインを実行。 | アートワーク入力引数は付与されず、音声ストリームのみで FFmpeg が正常に実行されること。 | Automated (pytest) |
| **TC-AC005-04** | AC-005 | P1 | Integration | コンピレーションCD: Track 1 (artist="Artist A", album_artist="Various Artists"), Track 2 (artist="Artist B", album_artist="Various Artists") | 複数トラックのリッピングパイプライン | 1. トラック1および2のメタデータ引数を生成。 | 各トラックで `-metadata artist="Artist A"` と `-metadata album_artist="Various Artists"` が独立して正しく生成されること。 | Automated (pytest) |
| **TC-AC006-01** | AC-006 | **P0** | UI / Integration | TrackTagData(album_artist="Initial Album Artist") | なし | 1. トラックをダブルクリックして TrackTagEditDialog を起動。 | (FIND-001是正) ダイアログに「Album Artist」入力欄が存在し、"Initial Album Artist" が表示されていること。 | Automated (pytest/UI) |
| **TC-AC006-02** | AC-006 | **P0** | UI / Integration | TrackTagEditDialog 表示中 (album_artist="Initial Album Artist") | title のみを "New Title" に変更 | 1. title を編集後、「OK」をクリックして保存。<br>2. 保存された TrackTagData を検証。 | (FIND-001是正) title="New Title" に更新されつつ、`album_artist` が空文字にならず "Initial Album Artist" として保持されること。 | Automated (pytest/UI) |
| **TC-AC006-03** | AC-006 | P1 | UI / Integration | TrackTagEditDialog 表示中 | album_artist 欄を "Updated Album Artist" に変更 | 1. album_artist を編集後、「OK」をクリック。 | 保存された TrackTagData の `album_artist` が "Updated Album Artist" に更新されること。 | Automated (pytest/UI) |

---

### 3.2 境界値テストケース (Boundary Cases)

| テストID | 観点・対象 | 優先度 | レベル | 前提条件 | 入力データ | 期待結果 | 境界値の根拠 | 自動化 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-BND-001** | ディスク番号 最小値 | P1 | Unit / UI | AlbumTagEditDialog 入力 | disc=1, total=1 | 入力検証を通過し、`disc_number=1, total_discs=1` として保存されること。 | 許容される最小の正の整数（下限値）。 | Automated (pytest) |
| **TC-BND-002** | ディスク番号 同値境界 | P1 | Unit / UI | AlbumTagEditDialog 入力 | disc=5, total=5 | 入力検証を通過し、正常に保存されること。 | disc == total の境界（最終ディスク）。 | Automated (pytest) |
| **TC-BND-003** | ディスク番号 最大値境界 | P2 | Unit / UI | AlbumTagEditDialog 入力 | (a) disc=999, total=999<br>(b) disc=1000, total=1000 | (a) は検証通過。<br>(b) は「1〜999の範囲で入力してください」などのバリデーションエラーとなること。 | 3桁ディスク番号の上限境界（999 vs 1000）。 | Automated (pytest) |
| **TC-BND-004** | ディスク番号 総数超過 | **P1** | Unit / UI | AlbumTagEditDialog 入力 | disc=3, total=2 | バリデーションエラー「ディスク番号は総ディスク数以下にしてください」が表示され保存がブロックされること。 | `disc > total` の論理不整合境界。 | Automated (pytest) |
| **TC-BND-005** | 画像最大解像度 下限境界 | P1 | Unit | Pillow正規化処理 | 1400x1400 の JPEG 画像バイナリ | `ArtworkHelper.normalize_artwork` でリサイズが行われず、1400x1400 のまま返されること。 | max_dimension=1400 の境界値。 | Automated (pytest) |
| **TC-BND-006** | 画像最大解像度 超過境界 | P1 | Unit | Pillow正規化処理 | 1401x1401 の JPEG 画像バイナリ | `ArtworkHelper.normalize_artwork` により長辺が 1400 にリサイズ（1400x1400）されて出力されること。 | max_dimension+1 の縮小発火境界。 | Automated (pytest) |
| **TC-BND-007** | 画像ファイルサイズ 上限境界 | **P1** | Unit | Pillow正規化処理 | ちょうど 10 * 1024 * 1024 バイト (10MB) の有効画像バイナリ | `MAX_ARTWORK_SIZE_BYTES` のチェックを通過し、正常に処理されること。 | 最大許容サイズ境界 (10MB)。 | Automated (pytest) |
| **TC-BND-008** | 画像ファイルサイズ 超過境界 | **P1** | Unit | Pillow正規化処理 | 10 * 1024 * 1024 + 1 バイト (10MB + 1B) の画像バイナリ | `ArtworkHelper.normalize_artwork` が安全に `None` を返すか、ダイアログで「10MB以下の画像を指定してください」と拒否されること。 | 上限超過境界によるメモリ防衛。 | Automated (pytest) |
| **TC-BND-009** | テキスト長 境界値 | P2 | Unit / UI | AlbumTagEditDialog 入力 | album_artist, album に 256文字の文字列、および 257文字の文字列 | 256文字はそのまま保存され、257文字以上は256文字に安全に切り詰められるかエラー表示されること。 | メタデータ文字列の常識的上限値。 | Automated (pytest) |

---

### 3.3 異常系・堅牢性テストケース (Negative / Robustness Cases)

| テストID | 観点・対象 | 優先度 | レベル | 前提条件 | 入力データ | 期待結果 | 異常系の根拠 | 自動化 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-NEG-001** | ディスク番号 負数・ゼロ | **P1** | Unit / UI | AlbumTagEditDialog 入力 | (a) disc=0, total=1<br>(b) disc=-1, total=2<br>(c) disc=1, total=0 | バリデーションエラーが表示され、保存処理が中断されること。 | 0以下の不正なディスク指定の排除。 | Automated (pytest) |
| **TC-NEG-002** | ディスク番号 非数値文字列 | **P1** | Unit / UI | AlbumTagEditDialog 入力 | disc="abc", total="two", "1.5" | ValueError 等でクラッシュせず、入力エラー通知が行われること。 | ユーザーの誤入力・型不一致防止。 | Automated (pytest) |
| **TC-NEG-003** | 画像バイナリ破損 (Truncated) | **P0** | Unit | Pillow正規化処理 | 先頭数十バイトのみ有効で途中で突然切断されている不正JPEGバイナリ | `ArtworkHelper.normalize_artwork` および `load_and_resize_image` が例外（PIL.UnidentifiedImageError 等）を内部で安全に捕捉し、クラッシュせず `None` を返却すること。 | 不完全ダウンロードや破損ファイルによるUI/プロセス停止防止。 | Automated (pytest) |
| **TC-NEG-004** | 0バイト空画像ファイル | P1 | Unit | Pillow正規化処理 | `b""` (長さ0のバイト列) | 例外を投げずに安全に `None` を返却すること。 | 0バイトファイル選択時の防御。 | Automated (pytest) |
| **TC-NEG-005** | 偽装画像ファイル | **P1** | Unit | Pillow正規化処理 | テキストファイルやEXEファイルのバイナリ（拡張子のみ `.jpg`） | PILの検証により画像として認識されず、例外が捕捉されて安全に `None` を返却すること。 | 拡張子偽装ファイルへの耐性。 | Automated (pytest) |
| **TC-NEG-006** | Decompression Bomb | **P0** | Unit | Pillow正規化処理 | 超巨大ピクセル画像（例: 6000x6000 = 36,000,000 ピクセル、MAX_IMAGE_PIXELS=25M 超過） | `PIL.Image.DecompressionBombError` を捕捉し、プロセスがメモリ枯渇でクラッシュすることなく `None` を返却すること。 | 画像ボムによるメモリ枯渇DoS攻撃の防御。 | Automated (pytest) |
| **TC-NEG-007** | CMYK カラープロファイル | **P1** | Unit | Pillow正規化処理 | CMYK カラーモードの JPEG 画像バイナリ | (FIND-002是正) `Image.convert("RGB")` により RGB 形式に変換されて再エンコードされ、FFmpeg MP4 エンコード時のクラッシュが防止されること。 | 印刷用画像が原因となるエンコーダ障害防止。 | Automated (pytest) |
| **TC-NEG-008** | 日付フィールドの不正文字 | P2 | Unit / UI | AlbumTagEditDialog 入力 | date="2026/13/45", "invalid_date", 長大なゴミ文字列 | 適切なフォーマット（YYYYまたはYYYY-MM-DD）にサニタイズされるか、バリデーションで警告されること。 | メタデータ汚染の防止。 | Automated (pytest) |

---

### 3.4 並行性・UIライフサイクル・排他テストケース (Concurrency & Lifecycle Cases)

| テストID | 観点・対象 | 優先度 | レベル | 前提条件 | 入力データ | 期待結果 | 根拠・障害モード | 自動化 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-CONC-001** | リッピング中ボタン無効化 | **P0** | UI / Integration | リッピング処理実行中 (`is_ripping=True`) | メイン画面表示 | メイン画面の「Edit Album Tags...」ボタンが `state="disabled"` に切り替わっていること。 | (FIND-005是正) リッピング中のタグ書き換えによる競合・不整合防止。 | Automated (pytest/UI) |
| **TC-CONC-002** | リッピング中Canvasクリックガード | **P0** | UI / Integration | リッピング処理実行中 (`is_ripping=True`) | Canvas クリックイベント | Canvas をクリックしても AlbumTagEditDialog が起動しないこと。 | ボタン無効化のすり抜け防止（Canvasクリックハンドラの排他）。 | Automated (pytest/UI) |
| **TC-CONC-003** | ダイアログ相互排他 (Album -> Track) | **P1** | UI | AlbumTagEditDialog がモーダル表示中 | トラック行のダブルクリック | TrackTagEditDialog が開かないこと（モーダルグラブによって背後のトラックリスト操作が遮断されること）。 | (FIND-005是正) ダイアログ多重起動によるフォーカス喪失や不整合防止。 | Automated (pytest/UI) |
| **TC-CONC-004** | ダイアログ相互排他 (Track -> Album) | **P1** | UI | TrackTagEditDialog がモーダル表示中 | 「Edit Album Tags...」のショートカットや呼出 | AlbumTagEditDialog が二重起動しないこと。 | 相互排他性の担保。 | Automated (pytest/UI) |
| **TC-CONC-005** | モーダルグラブの確実な解放 | **P1** | UI | AlbumTagEditDialog 表示中 | (a) OKボタン<br>(b) Cancelボタン<br>(c) ウィンドウ「×」閉じる<br>(d) Escapeキー | いかなる終了操作でも確実に `grab_release()` が実行され、親ウィンドウ（メイン画面）が操作可能に復帰すること。 | グラブ解放漏れによるアプリケーション全体の操作不能（UIフリーズ）防止。 | Automated (pytest/UI) |
| **TC-CONC-006** | ヘッドレス環境実行性 | **P0** | Unit | DISPLAY環境変数なし / Tk display なし (CI環境) | `ArtworkHelper.normalize_artwork` 呼出 | `_tkinter` や `TclError` を一切発生させず、純粋な Python/Pillow 処理として完全に動作・完結すること。 | CI/CD環境でのヘッドレステスト互換性の担保。 | Automated (pytest) |

---

### 3.5 セキュリティ・サニタイズテストケース (Security & Sanitization Cases)

| テストID | 観点・対象 | 優先度 | レベル | 前提条件 | 入力データ | 期待結果 | セキュリティ根拠 | 自動化 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-SEC-001** | FFmpeg 引数インジェクション | **P0** | Integration | FFmpeg エンコード引数構築処理 | album_artist = `Test" & calc.exe & "`<br>album = `Album; rm -rf /` | subprocess.Popen にリスト形式で安全に渡されるか、シェルエスケープが施され、外部プロセスが意図せぬコマンドを実行しないこと。 | コマンドライン引数インジェクション攻撃の防止。 | Automated (pytest) |
| **TC-SEC-002** | NULLバイト・制御文字混入 | **P1** | Unit | TrackTagData, AlbumTagData | album_artist = `"Band\x00Name\r\n"` | NULLバイト `\x00` や有害な制御文字が除去またはエスケープされて保持・出力されること。 | C言語ライブラリ（FFmpeg等）での文字列終端バグ・バッファ破損防止。 | Automated (pytest) |
| **TC-SEC-003** | 一時ファイル生成パストラバーサル | **P1** | Integration | リッピング時のアートワーク一時出力 | 特殊なファイル名や細工された入力 | 安全な `tempfile.NamedTemporaryFile` 等が使用され、ディレクトリトラバーサルが発生しないこと。 | 意図せぬファイル上書き・情報漏えい防止。 | Automated (pytest) |

---

### 3.6 回帰テストケース (Regression Cases)

| テストID | 観点・対象 | 優先度 | レベル | 前提条件 | 入力データ | 期待結果 | 回帰防止の根拠 | 自動化 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-REG-001** | 既存テストスイート全100件の実行 | **P0** | Unit / Int | 修正前の全テストスイートが存在 | `pytest tests/` 実行 | 既存100件の全テストが修正なしで 100% PASS すること（終了コード 0）。 | (AC-007) 既存全機能（SPTI, VirtualDrive, iTunes, Pipeline等）の後方互換。 | Automated (pytest) |
| **TC-REG-002** | `TrackTagData.create_default` 後方互換 | **P0** | Unit | TrackTagData クラス呼び出し | `TrackTagData.create_default(track_number=1)` | 引数変更なしで呼び出し可能であり、新フィールド `album_artist=""` が初期値として安全にセットされること。 | 既存呼び出しコードを破壊しない後方互換性。 | Automated (pytest) |
| **TC-REG-003** | `TrackTagData` の不変性 (frozen=True) | P1 | Unit | TrackTagData インスタンス | `tag.album_artist = "New"` | `FrozenInstanceError` (AttributeError) が発生し、直接変更が禁止されていること。 | ドメインモデルの不変性保証。 | Automated (pytest) |
| **TC-REG-004** | `AlbumTagData` の不変性 (frozen=True) | P1 | Unit | AlbumTagData インスタンス | `album.album = "New"` | `FrozenInstanceError` (AttributeError) が発生し、直接変更が禁止されていること。 | ドメインモデルの不変性保証。 | Automated (pytest) |

---

## 4. テストフィクスチャ & 実行要件

### 4.1 必要なテストフィクスチャ（モック & 画像データ）
1. **最小画像フィクスチャ (Base64 / バイナリインライン生成)**:
   - `valid_jpeg_bytes`: 1x1 または 100x100 の有効な RGB JPEG バイト列。
   - `valid_png_bytes`: 1x1 の有効な RGBA PNG バイト列。
   - `valid_webp_bytes`: 100x100 の WEBP バイト列。
   - `cmyk_jpeg_bytes`: CMYK モードでエンコードされた JPEG バイト列。
   - `exif_rotated_jpeg_bytes`: Orientation=6 を含む JPEG バイト列。
   - `corrupted_image_bytes`: `b"\xff\xd8\xff\xe0" + b"random_corrupted_data"`。
   - `oversized_10mb_bytes`: 10MB + 1バイトのダミーデータ。
   - `decompression_bomb_mock`: ピクセルサイズ 6000x6000 の PIL Image モック。
2. **Tkinter ヘッドレス対策**:
   - `ArtworkHelper.normalize_artwork` の単体テストは Tk 初期化を行わずに実行する。
   - UI テスト（ダイアログ、Canvas描画）は Tk ルート作成 (`tk.Tk()`) 後に `withdraw()` を呼ぶテストハーネスを使用する。

### 4.2 合否判定基準 (Pass / Fail Criteria)
- **合格条件**:
  1. TC-REG-001（既存テスト100件）がすべて PASS すること。
  2. P0 および P1 の全テストケースが実装され、すべて PASS すること。
  3. テストのスキップや不当なモック（検証対象をスルーするモック）が存在しないこと。
  4. ヘッドレス環境（Tk display なし）で正規化テストが正常実行できること。
- **不合格条件**:
  - いずれかの P0/P1 テストの失敗。
  - 既存テストの 1 件以上の失敗。
  - 実装者のコード修正により `album_artist` がリッピング出力から欠落すること。
