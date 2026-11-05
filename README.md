# CD Ripping Application (iTunes 互換 高音質リッピングツール)

Windows環境において、光学ドライブからオーディオCD（CD-DA）の楽曲を取り込み、**iTunes（Apple Music）標準と同一のエンコード形式・タグ情報・高解像度アートワーク**を付与して出力するデスクトップGUIアプリケーションです。

ドライブの性能や接続バス（外付けUSB / 内蔵SATA）に応じた**最適な読み込み倍速の自動決定ロジック**や、**iTunes Search APIからアルバム情報をワンクリックで取得・反映する機能**を備えています。

---

## 🌟 主な特徴

1. **iTunes 完全準拠のエンコード & タグ情報 (iTunes Plus 仕様)**
   - **標準フォーマット**: AAC 256kbps (`.m4a`, 44.1kHz, Stereo)
   - **選択可能なフォーマット**: ALAC（Apple Lossless 可逆圧縮 `.m4a`）/ MP3 320kbps (`.mp3`)
   - **メタデータアトム**: 曲名（Title）、アーティスト（Artist）、アルバム（Album）、発売年（Year）、ジャンル（Genre）、トラック番号/総トラック数（Track）、ディスク番号（Disc）、高解像度ジャケット画像（Cover Art / `attached_pic`）を iTunes 仕様アトムとして正確に埋め込みます。

2. **ドライブ性能に応じた読み込み倍速の自動最適化 (Auto Speed Optimization)**
   - **外付け USB ドライブ**: 共振や振動ジッター、バスパワー電圧降下を抑制する安定倍速（公称最大倍速の 1/3、**推奨 8x**）を自動設定。
   - **内蔵 SATA ドライブ**: 強固に固定された環境向けに、低騒音・高精度を両立する安定倍速（**推奨 16x**）を自動設定。
   - **低速ドライブ上限キャップ**: ドライブの物理最大速度を超えない安全制御を担保。
   - **Adaptive Speed Down（段階的減速）**: メディアの傷や読み取りエラーを検知した場合、自動的に速度を落として（24x → 16x → 12x → 8x → 4x → 1x）リトライします。

3. **iTunes Search & Lookup API 連携ボタン**
   - 画面の「**Search iTunes...**」ボタンから、アルバム名やアーティスト名で Apple iTunes Store データベースを非同期検索。
   - トラック一覧、曲名、アーティスト、ジャンル、発売年、および **高解像度（1200x1200bb）ジャケット写真** を取得し、画面の Canvas プレビューに即時反映。
   - CDの物理トラック数や演奏時間（Duration）との差分マッチング、マルチディスク（Disc 1 / Disc 2）の絞り込みに対応。

4. **デッドロックフリー & ストリーミング安全パイプライン**
   - PCM生音声セクターをディスクに書き込まず、FFmpeg の標準入力（`stdin` パイプ）へダイレクトにストリーミング（SSD摩耗防止・高速化）。
   - 専用の別スレッドによる `stderr` ドレインにより、OS パイプバッファ溢れによる永久フリーズ（デッドロック）を完全に防止。
   - トラック終端の端数セクター境界計算（`min(75, remaining)`）により、CD Lead-out 領域の超過アクセスエラーを事前抑止。
   - Windows NTFS 禁止文字（`\ / : * ? " < > |`）や Windows 予約デバイス名（`CON`, `PRN`, `AUX`, `NUL`, `CONIN$`, `CONOUT$` 等）の自動サニタイズ。

5. **デスクトップ GUI & 仮想CDモード (Virtual CD Mode)**
   - Python 標準の Tkinter / TTK による軽快なネイティブ操作感（Windows High-DPI スケーリング対応）。
   - **物理CDドライブや音楽CDがない環境でも、「Virtual CD Mode」ボタンを押すことで模擬CD（PCMサイン波）を用いた全機能のテスト・シミュレーションが可能**。

---

## 💻 動作環境

- **OS**: Windows 10 / 11 (64-bit)
- **言語 / ランタイム**: Python 3.10 以上 (Python 3.14 動作確認済み)
- **外部依存ツール**: [FFmpeg](https://ffmpeg.org/) (システム PATH に登録されている必要があります)
  - `ffmpeg` および `ffprobe` を使用します。

---

## 🚀 クイックスタート

### 1. リポジトリのクローン
```bash
git clone https://github.com/nankojin-ops/CDRipping-app.git
cd CDRipping-app
```

### 2. FFmpeg の確認
FFmpeg がインストールされ、PATH が通っているか確認します：
```powershell
ffmpeg -version
```

### 3. アプリケーションの起動
```powershell
py -3 main.py
```
*(または `python main.py`)*

---

## 📖 操作手順

```text
+--------------------------------------------------------------------------+
| 1. ドライブ選択       | 接続されたCD/DVDドライブを選択 (または Virtual CD) |
| 2. 倍速自動表示       | ドライブ種別に応じた推奨倍速（例: 8x）が自動表示   |
| 3. iTunes検索ボタン   | 「Search iTunes...」でアルバムを検索して情報反映   |
| 4. 出力設定           | フォーマット (AAC 256k / ALAC / MP3) と保存先確認  |
| 5. リッピング開始     | 「Start Ripping」をクリックして自動取り込み        |
+--------------------------------------------------------------------------+
```

1. **ドライブと倍速の確認**:
   - 画面上部のドロップダウンに PC に接続されている光学ドライブが一覧表示されます。
   - ドライブを選択すると、そのドライブの性能に応じた最適な推奨読み込み倍速が自動的に設定・表示されます。
   - 実CDがない場合は「**Virtual CD Mode**」ボタンを押してください。
2. **iTunes から CD 情報を取得**:
   - 「**Search iTunes...**」ボタンを押します。
   - 検索ダイアログにアルバム名またはアーティスト名を入力して「Search」をクリック。
   - 候補一覧から該当アルバムを選択し「Apply Selected Album」を押すと、全トラック名と高解像度アートワーク画像がメイン画面に反映されます。
3. **エンコード形式の選択**:
   - デフォルトは iTunes 標準の `AAC (256kbps .m4a)` です。
   - 必要に応じて `ALAC (Lossless .m4a)` や `MP3 (320kbps .mp3)` を選択できます。
4. **リッピングの実行**:
   - 「**Start Ripping**」ボタンを押すと、トラックごとの進捗バーおよび全体進捗バーがリアルタイムで更新されながら順次エンコードされます。
   - 途中で「Cancel」を押した場合は、エンコード中の不完全なファイルは自動的に安全消去されます。

---

## 🧪 自動テストの実行

本プロジェクトは、48件のユニットテスト、ハードウェアモックテスト、および実 FFmpeg / ffprobe を用いた E2E タグ検証テストを含んでいます。

```powershell
py -3 -m unittest discover -s tests -p "test_*.py" -v
```

全 48 テストが約 1.1 秒で実行され、すべてパス（Pass: 48, Fail: 0）することを確認できます。

---

## 📁 ディレクトリ構成

```text
CDRipping-app/
├── cdripper/                     # コアアプリケーションパッケージ
│   ├── domain/                   # ドメインモデル・例外定義
│   │   ├── models.py             # DriveInfo, DiscTOC, TrackMetadata 等
│   │   └── exceptions.py         # カスタム例外階層
│   ├── hardware/                 # 光学ドライブハードウェア制御
│   │   ├── interface.py          # ICDDrive 抽象基底クラス
│   │   ├── spti_drive.py         # Win32 SPTI / IOCTL 実ドライブ制御
│   │   ├── speed_optimizer.py    # ドライブ倍速自動最適化ロジック
│   │   └── virtual_drive.py      # テスト用仮想CDドライブ (PCMトーン生成)
│   ├── metadata/                 # メタデータ取得サービス
│   │   ├── interface.py          # IMetadataProvider 抽象基底クラス
│   │   ├── itunes_client.py      # Apple iTunes Search & Lookup API クライアント
│   │   └── mock_provider.py      # テスト・オフライン用モックプロバイダー
│   ├── pipeline/                 # 音声取り込み & エンコードパイプライン
│   │   ├── interface.py          # IAudioEncoder 抽象基底クラス
│   │   ├── ffmpeg_encoder.py     # FFmpeg stdin ストリーミング & タグ埋め込み
│   │   └── rip_pipeline.py       # 端数セクター制御・リッピング統括
│   └── ui/                       # プレゼンテーション層
│       ├── presenter.py          # 非同期ワーカースレッド & イベント制御
│       └── app_view.py           # Tkinter High-DPI デスクトップ GUI
├── tests/                        # 自動テストスイート (計48テスト)
│   ├── test_models.py
│   ├── test_virtual_drive.py
│   ├── test_speed_optimizer.py
│   ├── test_spti_drive.py
│   ├── test_itunes_client.py
│   ├── test_ffmpeg_encoder.py
│   ├── test_rip_pipeline.py
│   ├── test_presenter.py
│   ├── test_app_view.py
│   └── test_integration.py       # 実FFmpeg/ffprobe E2Eタグ検証
├── artifacts/agent-quality/      # 品質ゲート監査記録・受入判定書
├── main.py                       # アプリケーション起動エントリーポイント
├── README.md                     # 本ドキュメント (システム説明)
└── README_AGENTS.md              # 開発エージェント・オーケストレーション規約説明
```

---

## 🛡️ 品質保証とセキュリティ

本ツールは、以下の品質ゲート（オーケストレーション規約）に合格してリリースされています：
- **コマンドインジェクション対策**: `subprocess` 起動において `shell=False` を厳格に適用し、引数をリスト形式で渡すことでインジェクションを根絶。
- **SSRF・ローカルファイル漏洩対策**: アートワーク画像ダウンロード時の URL スキームを `http`/`https` に限定し、`file://` や内部ネットワークアクセスを遮断。10MB レスポンスサイズ制限を適用。
- **64bit ポインタ安全性**: Windows 64-bit 環境における Win32 API (`ctypes`) の `HANDLE` 型付け（`wintypes.HANDLE`）を厳格化。
- **パストラバーサル防止**: NTFS 禁止文字および予約語（`CON`, `PRN`, `AUX`, `NUL`, `CONIN$`, `CONOUT$` 等）の完全サニタイズ。
- **全受入条件のトレーサビリティ**: 詳細な監査記録は [`artifacts/agent-quality/cd-ripping-app-001/`](./artifacts/agent-quality/cd-ripping-app-001/) に保存されています。
