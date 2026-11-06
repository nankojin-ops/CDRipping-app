# QA Test Matrix

- Task ID: cd-ripping-app-002
- Designed before implementation: Yes
- Source-code-blind: Yes

## 1. テストマトリクスサマリー

| カテゴリ | ケース数 | P0 (Critical) | P1 (High) | P2 (Medium) | P3 (Low) | 自動化区分 |
|---|---|---|---|---|---|---|
| 1. ダイアログ起動・初期表示 (META) | 4 | 0 | 2 | 2 | 0 | 自動 (pytest / unittest UI) |
| 2. メタデータ編集・保存・反映 (EDIT) | 3 | 1 | 2 | 0 | 0 | 自動 (Unit / Integration) |
| 3. 前後ナビゲーション (NAV) | 4 | 0 | 2 | 2 | 0 | 自動 (Integration / UI) |
| 4. 数値境界値・バリデーション (VAL) | 6 | 1 | 3 | 2 | 0 | 自動 (Unit / Property) |
| 5. 文字列サニタイズ・OS安全性 (SAN) | 5 | 3 | 2 | 0 | 0 | 自動 (Unit / Integration) |
| 6. SSOT連動・競合調停 (SSOT) | 4 | 1 | 3 | 0 | 0 | 自動 (Integration / UI) |
| 7. リッピング・FFmpeg・ffprobe (RIP) | 5 | 2 | 3 | 0 | 0 | 自動 (Integration / ffprobe) |
| 8. 排他制御・モーダル制御 (STATE) | 6 | 2 | 4 | 0 | 0 | 自動 (Integration / UI) |
| 9. 回帰テスト (REG) | 1 | 1 | 0 | 0 | 0 | 自動 (unittest discover) |
| **合計** | **38** | **11** | **21** | **6** | **0** | **100% 自動化可能** |

---

## 2. 詳細テストマトリクス

### カテゴリ 1: ダイアログ起動・初期表示 (AC-001)

| Test ID | AC / Req | 優先度 | レベル | 前提条件 | 入力 / 手順 | 期待結果 | 根拠 / リスク | 自動化区分 |
|---|---|---|---|---|---|---|---|---|
| **TC-META-001** | AC-001 | P1 | Integration / UI | CD読込完了。Treeviewにトラック1〜10が表示。Track 2を選択中。 | 「Edit Metadata」ボタン押下（またはダブルクリック）。 | `TrackTagEditDialog` がモーダル起動し、Track 2 の全8項目（Track No, Total, Disc No, Total, Title, Artist, Album, Date, Genre, Encoder）が正確に初期表示される。 | 編集対象トラックとダイアログ表示内容の不一致による誤編集防止。 | Automated (unittest / UI) |
| **TC-META-002** | AC-001 | P2 | Unit / UI | Treeviewでトラックが一切選択されていない。 | 「Edit Metadata」ボタンを押下。 | ダイアログは開かず、ステータスバーまたは警告ダイアログで「トラックを選択してください」が表示される（またはボタンが非活性）。例外クラッシュしない。 | 未選択状態でのIndexError / NoneType例外防止。 | Automated (UI) |
| **TC-META-003** | AC-001 | P2 | Unit / UI | Treeviewで複数トラックが選択されている。 | 「Edit Metadata」ボタンを押下。 | 最初のトラックが開くか、単一選択を促すメッセージが表示され、複数ダイアログの重複起動や内部整合性破壊が発生しない。 | 複数選択時のインデックス解決破綻防止。 | Automated (UI) |
| **TC-META-004** | AC-001 | P1 | Unit / Integration | TrackTagDataモデルに全メタデータ（Title, Artist, Album, Date, Genre, Track, Disc, Encoder）が格納されている。 | ダイアログ起動時のフィールドマッピング関数を実行。 | 各Entryウィジェットにモデルの値が完全に一致してロードされる。 | フィールド抜け、型変換エラーの防止。 | Automated (Unit) |

### カテゴリ 2: メタデータ編集・保存・反映 (AC-002)

| Test ID | AC / Req | 優先度 | レベル | 前提条件 | 入力 / 手順 | 期待結果 | 根拠 / リスク | 自動化区分 |
|---|---|---|---|---|---|---|---|---|
| **TC-EDIT-001** | AC-002 | P0 | Integration | Track 1 ダイアログ表示中。初期値：Title="Old Title", Artist="Old Artist"。 | Titleを "New Title"、Artistを "New Artist"、Genreを "Jazz" に編集し「Save」押下。 | 1. ダイアログが正常終了する。<br>2. 内部データモデルのTrack 1が更新される。<br>3. `is_customized` フラグが `True` になる。<br>4. TreeviewのTrack 1行の表示（Title, Artist）が即座に更新される。 | メタデータ変更がモデルとUI表示に正確に反映される中核要件。 | Automated (Integration) |
| **TC-EDIT-002** | AC-002 | P1 | Unit / UI | Track 1 ダイアログ表示中。各項目を編集。 | 「Cancel」ボタンを押下（またはダイアログを閉じる）。 | 1. ダイアログが閉じる。<br>2. 内部データモデルは一切変更されない（ロールバック）。<br>3. Treeviewの表示も変更されない。<br>4. `is_customized` フラグは変更前の状態を維持する。 | キャンセル操作による意図しない状態変更の防止。 | Automated (UI) |
| **TC-EDIT-003** | AC-002 | P1 | Integration | Track 1 ダイアログ表示中。 | Artist, Genre, Date を空文字にして「Save」押下。 | 保存が正常完了する。空文字列としてモデルに格納され、エラーにならない。 | 任意タグ項目が空でも正しく許容されることの担保。 | Automated (Unit) |

### カテゴリ 3: 前後ナビゲーション (AC-001)

| Test ID | AC / Req | 優先度 | レベル | 前提条件 | 入力 / 手順 | 期待結果 | 根拠 / リスク | 自動化区分 |
|---|---|---|---|---|---|---|---|---|
| **TC-NAV-001** | AC-001 | P1 | Integration / UI | Track 2 (全10曲中) のダイアログ表示中。Titleを "Modified Track 2" に変更。 | 「Next >」ボタンを押下。 | Track 2 の編集内容が自動保存（または保存確認経由で保存）され、ダイアログの内容が Track 3 のメタデータ表示にスムーズに切り替わる。ウィンドウは再生成されず内容が更新される。 | 連続編集ユースケースにおけるデータ消失防止および画面チラつき抑制。 | Automated (UI) |
| **TC-NAV-002** | AC-001 | P1 | Integration / UI | Track 2 のダイアログ表示中。 | 「< Prev」ボタンを押下。 | Track 1 のメタデータ表示に切り替わり、全フィールドが Track 1 の情報で再読み込みされる。 | 前方ナビゲーションの双方向性担保。 | Automated (UI) |
| **TC-NAV-003** | AC-001 | P2 | Unit / UI | Track 1 (先頭トラック) のダイアログ表示中。 | 「< Prev」ボタンの状態確認および押下試行。 | 「< Prev」ボタンが `state=DISABLED` であること（または押下してもインデックスエラーにならず Track 1 に留まる）。 | 先頭境界での IndexError (Index -1) 防止。 | Automated (UI) |
| **TC-NAV-004** | AC-001 | P2 | Unit / UI | Track 10 (末尾トラック) のダイアログ表示中。 | 「Next >」ボタンの状態確認および押下試行。 | 「Next >」ボタンが `state=DISABLED` であること（または押下してもインデックスエラーにならず Track 10 に留まる）。 | 末尾境界での IndexError (Index >= len) 防止。 | Automated (UI) |

### カテゴリ 4: 数値境界値・バリデーション (AC-004)

| Test ID | AC / Req | 優先度 | レベル | 前提条件 | 入力 / 手順 | 期待結果 | 根拠 / リスク | 自動化区分 |
|---|---|---|---|---|---|---|---|---|
| **TC-VAL-001** | AC-004 | P1 | Unit | ダイアログ起動中。 | Track No に "0"、Track Total に "0" を入力し「Save」押下。 | バリデーションエラー通知が表示され、保存が拒否される（Track No >= 1 が必須）。ゼロ除算や不正トラック番号を遮断。 | オーディオメタデータ規格上、トラック番号0は不正。 | Automated (Unit) |
| **TC-VAL-002** | AC-004 | P1 | Unit | ダイアログ起動中。 | Track No に "-5", "abc", "1.5", "1/2/3" を入力し「Save」押下。 | エラーダイアログが表示され、保存拒否。フォーカスが不正な入力欄に留まる。 | 不正な文字列・負数・小数によるパーサー破壊防止。 | Automated (Unit) |
| **TC-VAL-003** | AC-004 | P0 | Unit | ダイアログ起動中。 | Track No = "1", Track Total = "0" を入力し「Save」押下。 | ゼロ除算エラー (`ZeroDivisionError`) が発生せず、バリデーションエラーとして適切に拒否される。 | "1/0" 形式による内部計算・文字列フォーマット時のクラッシュ防止。 | Automated (Unit) |
| **TC-VAL-004** | AC-004 | P2 | Unit | ダイアログ起動中。 | Track No に "1000", "99999999999999999999" を入力し「Save」押下。 | 上限値チェック（1〜999）によりエラー拒否される。 | 巨大数値によるUIレイアウト崩れ、ファイル名フォーマット崩壊の防止。 | Automated (Unit) |
| **TC-VAL-005** | AC-004 | P2 | Unit | ダイアログ起動中。 | Track No = "15", Track Total = "10" を入力し「Save」押下。 | トラック番号がトータルを超過している警告またはエラーが表示される。 | CD規格および論理的整合性の担保。 | Automated (Unit) |
| **TC-VAL-006** | AC-004 | P2 | Unit | ダイアログ起動中。 | Date に "abcd", "-2020", "20", "99999" を入力し「Save」押下。 | 有効な西暦（4桁数字等、または空）以外はバリデーションエラーとして拒否される。 | ID3/Vorbisタグの年フォーマット破綻防止。 | Automated (Unit) |

### カテゴリ 5: 文字列サニタイズ・OS安全性 (AC-005)

| Test ID | AC / Req | 優先度 | レベル | 前提条件 | 入力 / 手順 | 期待結果 | 根拠 / リスク | 自動化区分 |
|---|---|---|---|---|---|---|---|---|
| **TC-SAN-001** | AC-005 | P0 | Unit / Integration | ダイアログ起動中。 | Title に制御文字混入文字列 `"Track\nTitle\r\nWith\tTabs\0andNull"` を入力して保存。 | 制御文字（`\r`, `\n`, `\t`, `\0`）が安全に空白置換または除去される。FFmpeg引数やファイルシステム呼び出し時にエラーやインジェクションが発生しない。 | コマンドラインインジェクション、NULLバイト攻撃、ログ/UI崩れ防止。 | Automated (Unit) |
| **TC-SAN-002** | AC-005 | P1 | Unit | ダイアログ起動中。 | Title に 300 文字の超長大文字列（`"A" * 300`）を入力して保存。 | エラー拒否されるか、仕様で定義された最大長（256文字）に安全に切り詰められる。 | Windows のパス長制限およびファイル名長制限によるOS例外防止。 | Automated (Unit) |
| **TC-SAN-003** | AC-005 | P0 | Unit / Integration | Track 1 の Title を `AC/DC: What "Is" *This* <Rock>? | Yes\No` に編集・保存。 | 出力ファイル名生成関数およびタグ生成を実行。 | 1. タグメタデータ（FFmpeg `-metadata title=...`）には元の記号がそのまま保持される。<br>2. 生成ファイル名では禁止文字（`\ / : * ? " < > |`）が安全な代替文字（アンダースコア `_`）に変換される。<br>3. ファイル作成時に `OSError` が発生しない。 | NTFSファイルシステム制約の遵守と、音楽タグ本来の表記保持の両立。 | Automated (Unit/Integration) |
| **TC-SAN-004** | AC-005 | P0 | Unit / Integration | Track 1 の Title を Windows予約デバイス名 `"CON"`, `"PRN"`, `"AUX"`, `"NUL"`, `"COM1"`, `"LPT1"`, `"CONIN$"` に編集・保存。 | 出力ファイル名生成関数を実行。 | プレフィックス（`01 - _CON.m4a` 等）または予約名エスケープ処理により、Windows予約デバイスへの書き込み衝突が確実に防止され、正常にファイルが作成できる。 | Windows OSがハングアップまたはアクセス拒否する重大障害の防止。 | Automated (Unit/Integration) |
| **TC-SAN-005** | AC-005 | P1 | Unit | Track 1 の Title を `"Trailing Dot."` や `"Trailing Space "` に編集。 | ファイル名サニタイズ関数を実行。 | 末尾のピリオドおよび空白が除去または置換され、Windowsで開けないファイルが生成されない。 | Windowsのファイル名末尾ピリオド/スペース禁止仕様への準拠。 | Automated (Unit) |

### カテゴリ 6: SSOT連動・競合調停 (AC-002, AC-006)

| Test ID | AC / Req | 優先度 | レベル | 前提条件 | 入力 / 手順 | 期待結果 | 根拠 / リスク | 自動化区分 |
|---|---|---|---|---|---|---|---|---|
| **TC-SSOT-001** | AC-002 | P1 | Integration | Track 1 は手動編集済み (`is_customized=True`)。Track 2〜10 は未編集 (`is_customized=False`)。 | メイン画面の「Artist」入力欄を変更。 | 1. 未編集の Track 2〜10 の Artist は即時連動更新される。<br>2. 手動編集済みの Track 1 の Artist は変更されず維持される。 | Single Source of Truth 原則と個別編集保護の整合性担保。 | Automated (Integration) |
| **TC-SSOT-002** | AC-002 | P1 | Integration | Track 1〜10 すべて未編集 (`is_customized=False`)。 | メイン画面の「Album」入力欄を変更。 | 全トラック (1〜10) の Album が連動して更新される。Treeviewの表示も連動する。 | 未編集トラックに対する一括更新機能の保証。 | Automated (Integration) |
| **TC-SSOT-003** | AC-006 | P1 | Integration / UI | Track 1 が手動編集済み (`is_customized=True`)。 | メイン画面でiTunesメタデータ適用を実行。確認ダイアログで「No」を選択。 | 1. 手動編集済み Track 1 のメタデータは一切上書きされず保護される。<br>2. 未編集のトラックには最新のiTunesメタデータが適用される。<br>3. Track 1 の `is_customized` は `True` を維持する。 | ユーザーが入力したメタデータの意図しない喪失防止。 | Automated (UI/Integration) |
| **TC-SSOT-004** | AC-006 | P1 | Integration / UI | Track 1 が手動編集済み (`is_customized=True`)。 | 同上で確認ダイアログで「Yes（すべて上書き）」を選択。 | 1. Track 1 を含む全トラックが最新のiTunesメタデータで上書きされる。<br>2. Track 1 の `is_customized` がリセット（`False`）される。 | 明示的な全更新要求に対する完全適用保証。 | Automated (UI/Integration) |

### カテゴリ 7: リッピング・FFmpeg・ffprobe (AC-003, AC-004, AC-005)

| Test ID | AC / Req | 優先度 | レベル | 前提条件 | 入力 / 手順 | 期待結果 | 根拠 / リスク | 自動化区分 |
|---|---|---|---|---|---|---|---|---|
| **TC-RIP-001** | AC-005 | P0 | Integration | Track 3 のトラック番号を 5、Title を `"Symphony No. 5"` に編集。 | 出力ファイル名フォーマット関数を実行。 | 出力ファイル名が `05 - Symphony No. 5.m4a`（拡張子は選択形式）となり、`{track_num:02d} - {title}{ext}` 形式でゼロ埋め2桁フォーマットされる（整数型 `track_number` によるクラッシュ回避）。 | 出力命名規則 AC-005 の厳密な遵守。 | Automated (Unit) |
| **TC-RIP-002** | AC-003 | P0 | Integration / API | Track 1 (title="Song A", artist="Band B", album="Record C", date="2024", track="1/10", disc="1/1", genre="Rock", encoder="Custom Enc"). | リッピング時の FFmpeg コマンド引数リスト構築関数を実行。 | コマンド引数リストに以下が正確に含まれる：<br>`-metadata`, `title=Song A`<br>`-metadata`, `artist=Band B`<br>`-metadata`, `album=Record C`<br>`-metadata`, `date=2024`<br>`-metadata`, `track=1/10`<br>`-metadata`, `disc=1/1`<br>`-metadata`, `genre=Rock`<br>`-metadata`, `encoder=Custom Enc`<br>（リスト形式で渡され、シェル文字列結合されていないこと）。 | シェルインジェクション脆弱性の防止と全8項目の確実なタグ付け。 | Automated (Unit) |
| **TC-RIP-003** | AC-003 | P1 | Unit / Integration | Track 1 の date, genre が空文字（`""`）。 | FFmpeg 引数構築関数を実行。 | 空の項目（`-metadata genre=` 等）は引数リストから自動除外される。 | 不正な空タグ引数によるFFmpeg警告やエンコーダエラーの防止。 | Automated (Unit) |
| **TC-RIP-004** | AC-003 | P1 | E2E / Integration | 仮想CDドライブ経由で Track 1 を編集（Title="TestTitle", Artist="TestArtist", Genre="Electronic", Date="2025"）。リッピング実行（AACエンコード）。 | 生成された `.m4a` ファイルに対し `ffprobe -show_entries format_tags -of json` を実行。 | 出力JSONの `format.tags` に：<br>`"title": "TestTitle"`<br>`"artist": "TestArtist"`<br>`"genre": "Electronic"`<br>`"date": "2025"`<br>が含まれており、実ファイルにタグが恒久記録されている。 | 出力メディアファイルにおけるメタデータ実効性の最終確認。 | Automated (E2E/ffprobe) |
| **TC-RIP-005** | AC-003 | P1 | Integration | Track 1 (Title="Track One") と Track 2 (Title="Track Two") を連続リッピング。 | 各トラックのリッピング引数と出力先パスを検証。 | 各トラックの引数が完全に分離されており、前のトラックのメタデータが次のトラックに漏洩・残留しない。 | ループ処理における状態リーク防止。 | Automated (Integration) |

### カテゴリ 8: 排他制御・モーダル制御 (AC-001)

| Test ID | AC / Req | 優先度 | レベル | 前提条件 | 入力 / 手順 | 期待結果 | 根拠 / リスク | 自動化区分 |
|---|---|---|---|---|---|---|---|---|
| **TC-STATE-001** | AC-001 | P0 | Integration / UI | CD読込完了。待機状態。 | 「Start Ripping」ボタンを押下してリッピング処理を開始。 | 1. メイン画面の「Edit Tags」ボタン、トラックTreeview、全入力Entry、フォーマット選択、ドライブ選択等の全UIコントロールが `state=DISABLED` になる。<br>2. リッピング実行中にダイアログを起動することはできない。 | リッピング中の並行変更によるレースコンディション・データ破壊防止。 | Automated (UI) |
| **TC-STATE-002** | AC-001 | P1 | Integration / UI | メタデータ編集ダイアログが開いている状態。 | 親ウィンドウ（メイン画面）のTreeviewやボタンをクリック。 | 親ウィンドウの操作が `grab_set()` により完全にブロックされ、親ウィンドウ側のイベントは反応しない。 | モーダル排他制御の遵守。 | Automated (UI) |
| **TC-STATE-003** | AC-001 | P1 | Integration / UI | 既にダイアログが開いている状態。 | 再度ダイアログオープンを要求。 | ダイアログが重複して開かず、既存のダイアログが `lift()`, `focus_force()` されて最前面化する（シングルトン制御）。 | ウィンドウ乱立によるフォーカス喪失およびメモリリーク防止。 | Automated (UI) |
| **TC-STATE-004** | AC-001 | P1 | Integration / UI | ダイアログが開いているモーダル状態。 | キーボードの `Esc` キーを押下。 | 1. ダイアログが閉じる（編集は破棄）。<br>2. `grab_release()` が確実に呼ばれ、親ウィンドウのフリーズや操作不能が発生しない。<br>3. メイン画面にフォーカスが復帰する。 | モーダル脱出経路の安全性保証。 | Automated (UI) |
| **TC-STATE-005** | AC-001 | P1 | Integration / UI | ダイアログが開いているモーダル状態。 | ウィンドウタイトルバーの「×」ボタンをクリック。 | 1. `WM_DELETE_WINDOW` プロトコルハンドラが作動。<br>2. `grab_release()` 呼び出し後に `destroy()` され、親ウィンドウが正常操作可能に復帰する。 | 「×」閉じ時の親ウィンドウ永久ロック防止。 | Automated (UI) |
| **TC-STATE-006** | AC-001 | P1 | Integration / UI | リッピング処理実行中（TC-STATE-001の状態）。 | リッピングが正常完了（またはエラー/ユーザー中断）。 | 完了通知後、無効化されていたUIコントロールがすべて安全に `state=NORMAL` に復帰する。 | ジョブ終了後のUIロック固着バグ防止。 | Automated (UI) |

### カテゴリ 9: 回帰テスト (AC-006)

| Test ID | AC / Req | 優先度 | レベル | 前提条件 | 入力 / 手順 | 期待結果 | 根拠 / リスク | 自動化区分 |
|---|---|---|---|---|---|---|---|---|
| **TC-REG-001** | AC-006 | P0 | Regression | 新規変更コードが適用された作業ツリー。 | `py -3 -m unittest discover -s tests -p "test_*.py" -v` を実行。 | 既存の全68テストが **0 failure, 0 error** で PASS すること。 | 既存安定機能の完全保護と非デグレ検証。 | Automated (unittest discover) |

---

## 3. Coverage gaps / not applicable
- トラックごとの個別カバーアート差し替え: 今回スコープ外（アルバム単位のアートワークを維持）。
- 外部音楽タグエディタ連携: 今回スコープ外。

## 4. Test data and environment
- OS: Windows 11 / 10
- Python 3.14.8
- FFmpeg 8.1.1 (ffmpeg, ffprobe)
- Tkinter (Tk 8.6)

## 5. Manual verification required
- 実ディスプレイ高DPI環境（125%, 150%スケーリング）でのダイアログ文字欠け・レイアウト目視確認。
