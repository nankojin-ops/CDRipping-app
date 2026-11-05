# Antigravity Quality-Gated Orchestration Pack

親エージェント + Subagent 構成向けの、品質ゲート付き反復開発テンプレートです。

## このパックで変えること

- 親エージェントを唯一のオーケストレーター／品質ゲート責任者にする。
- 設計者と設計チャレンジャーを分け、実装前に設計の弱点を洗い出す。
- QAテスト設計者には実装コードを見せず、要求から先にテスト観点を作らせる。
- 実装完了後に変更を凍結し、コードレビュー・セキュリティレビュー・検証監査を独立したSubagentで並列実行する。
- 指摘をIssue台帳で追跡し、修正後に回帰テストと再レビューを強制する。
- 3回の修正サイクルで解決しない場合は、無理に合格させず人間へエスカレーションする。

## ディレクトリ

```text
.agents/
  AGENTS.md                    # 親エージェントの常時ルール
  agents/                      # カスタムSubagent定義
    system-architect.md
    design-challenger.md
    tech-lead.md
    implementer.md
    qa-test-designer.md
    qa-engineer.md
    code-reviewer.md
    security-reviewer.md
    verification-auditor.md
  skills/                      # Agent Skills
    task-intake/
    architecture-design/
    design-challenge/
    implementation-planning/
    implementation/
    qa-test-design/
    qa-execution/
    independent-code-review/
    security-review/
    verification-audit/
    remediation-triage/

START_PROMPT.md                # 親エージェントへの起動指示
TEMPLATES/                     # タスクごとに複製する記録テンプレート
```

## 導入手順

1. ZIPを展開し、中身を対象リポジトリのルートへコピーします。
2. 既存の `.agents/AGENTS.md` がある場合は上書きせず、今回の内容を既存ルールへ統合してください。既存の `AGENTS.md` / `GEMINI.md` も同様に保護してください。
3. 既存の `.agents/agents/` や `.agents/skills/` と名前が重複するファイルは、差分を確認して統合してください。
4. Antigravity App / CLI の Agent Manager で `.agents/agents/` 配下のSubagentが検出されることを確認します。Skillsは `.agents/skills/<skill-name>/SKILL.md` に配置されます。
5. 親エージェントに `START_PROMPT.md` の内容を渡し、対象タスクを記入して開始します。
6. 最初の1〜2タスクは、親エージェントがSubagentを呼び分けているか、レビュアーが読み取り専用で動くか、実行証跡が保存されるかを確認してください。

## 実装上の前提・注意

- カスタムSubagent定義のパスは `.agents/agents/<name>.md` を採用しています。公式ドキュメント上、カスタムSubagentのMarkdown定義はAntigravity App / CLIでサポートされています。IDE拡張のみの環境では、Subagent定義の自動検出可否を実環境で確認し、必要なら既存のSubagent機構を維持してSkillsと常時ルールだけを導入してください。
- Skillsは `.agents/skills/` を使います。
- 2026年10月19日以降、旧 `.agents/workflows/` は実行対象としてインデックスされません。旧Workflow中心の構成が残っている場合は `/migrate-workflows` でAgent Skillsへ移行してください。
- このパックはモデルの具体名を固定せず、`model: pro` または `model: inherit` のティア指定を使います。`pro` が利用できない環境では `inherit` に置き換えてください。
- コードレビュアー・セキュリティレビュアーは `view_file` / `grep_search` / `find_by_name` のみ、QAエンジニアとAuditorは読み取り系ツール + `run_command` のみを許可し、ファイル編集を持たせない構成です。親エージェントがレビュー対象の `review.diff` を事前に生成し、ファイルとして渡してください。自動テストの追加・修正は実装者に戻します。
- Auditorには `run_command` を許可しますが、実行対象はビルド・テスト・Lint等の非破壊コマンドに限定します。デプロイ、DB変更、データ削除、外部サービスへの書き込みは禁止です。
- Subagentは親の会話履歴を引き継がない独立コンテキストで起動されるため、親は必ず仕様・受入条件・設計資料・対象ファイル・対象差分・依頼事項を明示して渡してください。
- `artifacts/agent-quality/<task-id>/` は品質記録の保存先の標準例です。既存の `docs/`, `engineering/`, `artifacts/` 規約がある場合はそちらに合わせてください。

## 推奨モデル割り当て

| Agent | 初期設定 | 理由 |
|---|---|---|
| system-architect | `pro` | 要件・設計判断 |
| design-challenger | `pro` | 反証・代替案の生成 |
| tech-lead | `inherit` | プロジェクト固有の計画作成 |
| implementer | `inherit` | 親の既定モデルと整合 |
| qa-test-designer | `pro` | 実装非依存のテスト観点設計 |
| qa-engineer | `pro` | 独立テスト実行・異常系検証 |
| code-reviewer | `pro` | 独立した深い差分レビュー |
| security-reviewer | `pro` | セキュリティ観点の反証 |
| verification-auditor | `pro` | テスト証跡の監査 |

`pro` / `inherit` はモデル名ではなくモデルティアです。利用できない場合は `inherit` を使ってください。レビューの品質はモデルティアだけでなく、独立コンテキスト、読み取り専用権限、明確な受入条件、実行証跡で担保します。

## 公式ドキュメント

- Agent Skills: https://antigravity.google/docs/skills
- Custom Subagents: https://antigravity.google/docs/subagents?tab=cli
- Rules: https://antigravity.google/docs/rules
- Workflows to Skills migration: https://antigravity.google/docs/migration/workflows-to-skills
