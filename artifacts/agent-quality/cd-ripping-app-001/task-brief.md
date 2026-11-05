# Task Brief

- Task ID: cd-ripping-app-001
- Title: CD Ripping Application with iTunes Metadata & Auto Speed Optimization
- Requester / owner: User
- Date: 2026-11-05
- Risk level: Medium
- Target revision / initial working tree: 0754816 (Initial commit with orchestration framework)

## Background and goal
ユーザーからCDのリッピングツール（オーディオCDの取り込みアプリケーション）の開発が求められている。
iTunesと同等のエンコード（AAC/ALAC/MP3等、デフォルトはiTunes標準のAAC 256kbps）およびメタデータタグ（アーティスト、アルバム、曲名、トラック番号、ディスク番号、アートワーク画像等）を付与し、ドライブの性能に応じた最適な読み込み倍速を決定するロジック、およびiTunes APIからCDメタデータを取得・適用するGUIボタンを備えたアプリケーションを提供する。

## In scope
1. ドライブ検出およびCD-TOC（目次・トラック構成・演奏時間）の読み取り（Windows SPTI / WMI 対応、CD未挿入時/開発検証用のシミュレーション・モックモード搭載）
2. ドライブ性能に応じた倍速自動決定ロジック（外付けドライブ・内蔵ドライブの最大速度、読み取り安定性・エラー低減を考慮した最適速度の算出およびMMC速度制御インターフェース）
3. iTunes Search / Lookup APIと連携したメタデータ検索機能（アルバム名・アーティスト名またはTOC情報による検索、検索結果のトラックリスト・アートワークの取得・プレビュー・適用）
4. iTunes互換のオーディオエンコードおよびタグ情報埋め込み（FFmpeg連携によるAAC 256kbps m4a、ALAC、MP3。タイトル、アーティスト、アルバム、年、ジャンル、トラック番号/総トラック数、ディスク番号、高解像度アートワーク画像の埋め込み）
5. デスクトップGUIインターフェース（Tkinterによる使いやすい画面構成、ドライブ選択、トラック選択、iTunes情報取得ボタン、エンコード設定、倍速表示・設定、リッピング進捗プログレスバー、ログ表示）
6. 自動テストおよび検証スクリプト群（ユニットテスト、APIモックテスト、エンコードテスト、タグ検証テスト）

## Out of scope
- 商用コピープロテクト（CCCD等の違法回避）の解除
- CD-Rへの書き込み（ライティング機能）
- macOS / Linux 特有の独自ドライバ実装（Windows環境を主対象とするが、コアロジックはクロスプラットフォーム考慮）

## Functional requirements
| Requirement ID | Requirement | Priority | Notes |
|---|---|---|---|
| REQ-001 | 接続されているCD/DVD/BDドライブの自動検出と選択 | P1 | WMIおよびWindows API (SPTI) を使用 |
| REQ-002 | オーディオCDのトラック一覧（トラック番号、長さ、LBA等）の取得 | P1 | 実ドライブおよびテスト用仮想/モックモード対応 |
| REQ-003 | ドライブの性能に応じた読み込み倍速の自動決定 | P1 | 最大速度と安定性を考慮したアルゴリズム |
| REQ-004 | iTunes Search & Lookup APIからのCDアルバム/楽曲メタデータ取得ボタン | P1 | アルバム名/キーワード検索、曲名一覧、アートワーク取得 |
| REQ-005 | 取得したメタデータのトラックリストへの自動/手動マッピングとプレビュー | P1 | トラック数の一致確認、編集可能 |
| REQ-006 | iTunes互換エンコード（AAC 256kbps .m4a、ALAC、MP3）の実装 | P1 | FFmpeg連携による高音質エンコード |
| REQ-007 | iTunes互換タグ（タイトル、アーティスト、アルバム、トラック番号、アートワーク等）の埋め込み | P1 | M4A/MP3メタデータアトムへの正確な書き込み |
| REQ-008 | リッピングの実行制御と進捗表示（進捗バー、ステータス表示、キャンセル対応） | P1 | バックグラウンドスレッドでの実行 |

## Non-functional requirements
- NFR-001: 応答性 - UIスレッドをブロックせず、重い処理（API通信、リッピング、エンコード）は非同期実行する。
- NFR-002: 保守性 - ドライブ制御、API連携、エンコード処理、UIをモジュール分離する。
- NFR-003: テスト容易性 - 光学ドライブや物理CDがないCI/テスト環境でも、モックとユニットテストで全機能の動作を検証できる。
- NFR-004: 堅牢性 - ネットワークエラー、ドライブ未挿入、読み取りエラー等の例外を捕捉し、ユーザーに適切なエラーメッセージを表示する。

## Constraints and compatibility
- OS: Windows 10/11
- ランタイム: Python 3.10+ (環境は Python 3.14.8 利用可能)
- 外部ツール: FFmpeg (システムに導入済み)
- UIフレームワーク: Python Tkinter (標準ライブラリ、Windows環境で追加インストール不要で動作)

## Acceptance criteria
| Acceptance ID | Given / When / Then or measurable condition | Verification method |
|---|---|---|
| AC-001 | アプリ起動時、接続されている光学ドライブが一覧表示され、ドライブが選択可能であること | ユニットテストおよびUIテスト |
| AC-002 | ドライブ性能（例: USB外付けドライブ 24x、内蔵 48x等）に基づき、安定読み込み倍速が自動決定・表示されること | ユニットテスト（速度計算ロジック） |
| AC-003 | 「iTunesからCD情報を取得」ボタンをクリックした際、検索ダイアログ/検索フォームからアルバムを検索し、トラック名・アーティスト・アルバム・アートワークが取得されUIに反映されること | ユニットテスト（APIクライアント + モック/実通信） |
| AC-004 | iTunes標準エンコード（AAC 256kbps m4a）で出力され、iTunes仕様のタグ情報（Track, Title, Artist, Album, Cover Art等）がファイルに正確に埋め込まれていること | エンコード実行＆ffprobeによるメタデータ検証テスト |
| AC-005 | リッピング実行時、トラックごとの進捗状況と完了状態がUIに適切にフィードバックされること | 進行テストおよびUIモックテスト |
| AC-006 | 物理ドライブにCDが挿入されていない環境でもテスト用モード/モックデータでリッピング〜エンコードの一連の流れがテスト可能であること | 自動回帰テストスイート |

## Assumptions / unresolved questions
- 物理オーディオCDが常に挿入されているとは限らないため、テスト容易性と実ドライブ操作の両方を満たす「CDRipperEngine」抽象化レイヤを設ける。
- ドライブの倍速設定は、Windows SPTI (SCSI Pass-Through) 経由の SET CD SPEED コマンドおよび推奨安全速度のフォールバック計算を実装する。

## Existing user changes to preserve
- `.agents/` ディレクトリおよび `START_PROMPT.md`, `README.md`, `RUNBOOK.md`, `manifest.json`, `TEMPLATES/` を保持する。

## Approved commands / environment restrictions
- Python実行: `py -3 <script>` または `python <script>`
- テスト実行: `py -3 -m unittest discover tests` または `pytest`
- ビルド・Lint: `py -3 -m flake8` または `py -3 -m py_compile`
- 非破壊コマンドのみを実行。外部への不要な書き込みやシステム破壊コマンドは禁止。
