# Review / QA Findings Register

- Task ID: cd-ripping-app-001
- Review round: 2 (Re-review)
- Target revision: f7611f8
- Frozen diff path: artifacts/agent-quality/cd-ripping-app-001/review.diff

| Issue ID | Source agent | Severity | Location | Reproduction / evidence | Impact | Root cause | Fix / disposition | Retest | Status |
|---|---|---|---|---|---|---|---|---|---|
| FIND-001 (REV-001) | code-reviewer | P1 | cdripper/ui/app_view.py, presenter.py | TOC未読み込み時にStart Ripping押下 | ボタンがDISABLEDのまま恒久ロック | エラー時にボタン状態を復元していない | app_viewの_on_start_ripガードおよびERROR受信時のボタンNORMAL復帰実装 | test_app_view.py | CLOSED |
| FIND-002 (REV-002) | code-reviewer | P1 | cdripper/ui/app_view.py, itunes_client.py | CD未読み込み時にiTunesメタデータ適用 | AttributeError: 'NoneType' has no 'tracks' | toc is None のガード欠落 | itunes_clientおよびapp_viewでtoc is None時の安全なトラック表示実装 | test_itunes_client.py | CLOSED |
| FIND-003 (REV-003) | code-reviewer | P1 | cdripper/ui/app_view.py | iTunes検索からアルバム適用 | Canvasにアートワーク画像が描画されない | METADATA_LOADED受信時の画像描画処理欠落 | PhotoImageを生成しCanvasに描画・参照保持実装 | test_app_view.py | CLOSED |
| FIND-004 (SEC-001) | security-reviewer | P1 | cdripper/metadata/itunes_client.py | download_artworkにfile://等のURL | SSRF / ローカルファイル漏洩 | URLスキームのホワイトリスト検証欠落 | urlparseでhttp/httpsのみ許可実装 | test_itunes_client.py | CLOSED |
| FIND-005 (SEC-003) | security-reviewer | P1 | cdripper/hardware/spti_drive.py | 64ビットWindowsでSPTI実行 | 64ビットHANDLE切り捨て・ポインタ破損 | ctypesのrestype/argtypes未定義 | kernel32関数のrestype/argtypes明示的定義実装 | test_spti_drive.py | CLOSED |
| FIND-006 (REV-004) | code-reviewer | P2 | cdripper/ui/app_view.py | 検索ダイアログで検索実行 | UIスレッド同期通信によるフリーズ | ダイアログでの直接ブロッキングI/O | 検索ダイアログ内でのスレッド非同期検索実装 | test_app_view.py | CLOSED |
| FIND-007 (REV-005) | code-reviewer | P2 | cdripper/hardware/speed_optimizer.py | 低速ドライブ(4x等)の倍速計算 | 推奨倍速が最大速度を超える | max_speedによる上限キャップ漏れ | min(rec, max_speed) を適用実装 | test_speed_optimizer.py | CLOSED |
| FIND-008 (REV-006) | code-reviewer | P2 | cdripper/hardware/spti_drive.py | 実機でのlist_drives | バス種別が常にUNKNOWN/0固定 | StorageDevicePropertyクエリ未実装 | IOCTL_STORAGE_QUERY_PROPERTYによるUSB/SATA判別実装 | test_spti_drive.py | CLOSED |
| FIND-009 (SEC-002) | security-reviewer | P2 | cdripper/metadata/itunes_client.py | 巨大アートワークURL | メモリ枯渇・DoS | レスポンスボディサイズ無制限読み込み | MAX_ARTWORK_SIZE(10MB)上限でread実装 | test_itunes_client.py | CLOSED |
| FIND-010 (SEC-004) | security-reviewer | P2 | cdripper/hardware/spti_drive.py | open("PhysicalDrive0") | 任意物理デバイス直接オープン | ドライブ文字構文検証欠落 | ^[a-zA-Z]:$ 正規表現チェック実装 | test_spti_drive.py | CLOSED |
| FIND-011 (SEC-005) | security-reviewer | P2 | cdripper/hardware/spti_drive.py | LastTrack=100のTOC | IndexErrorでクラッシュ | TrackData配列サイズ境界チェック欠落 | 1 <= FirstTrack <= LastTrack <= 99 バリデーション実装 | test_spti_drive.py | CLOSED |
| FIND-012 (SEC-006) | security-reviewer | P3 | cdripper/pipeline/ffmpeg_encoder.py | 曲名"CONIN$"のファイル作成 | Windows予約名エラー | CONIN$/CONOUT$のサニタイズ漏れ | 予約語パターンにCONIN$/CONOUT$追加実装 | test_ffmpeg_encoder.py | CLOSED |
| FIND-013 (SEC-007) | security-reviewer | P3 | cdripper/pipeline/ffmpeg_encoder.py | cancel_and_cleanup実行 | stdinファイル記述子未解放 | 明示的stdin.close漏れ | cancel_and_cleanupでstdin.close実行実装 | test_ffmpeg_encoder.py | CLOSED |
| FIND-014 (REV-007) | code-reviewer | P3 | cdripper/pipeline/ffmpeg_encoder.py | PNGアートワークの一時ファイル保存 | 常に拡張子.jpg固定 | 画像フォーマット判定欠落 | マジックバイト判定で.png/.jpgを付与実装 | test_ffmpeg_encoder.py | CLOSED |
| FIND-015 (REV-008) | code-reviewer | P3 | cdripper/ui/app_view.py | Virtual/UNKNOWNドライブ選択 | SATA Internalと誤表示 | 二値判定ロジック | BusTypeに応じた適切なラベル表示実装 | test_app_view.py | CLOSED |

## Disagreements / adjudication
なし。全15件すべて実装完了。

## Accepted risks
なし。

## Round summary
- P0: 0
- P1: 0 (5件すべて解消)
- P2: 0 (6件すべて解消)
- P3: 0 (4件すべて解消)
- Open: 0
- Closed with evidence: 15
