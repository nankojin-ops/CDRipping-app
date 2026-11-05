# 実行Runbook（親エージェント向け）

## 1. 作業記録を作る

`artifacts/agent-quality/<task-id>/` を作り、`TEMPLATES/` を複製する。`review.diff` と `logs/` をこの配下へ保存する。

## 2. Subagentの呼び出し順

| 段階 | Subagent | workspaceの考え方 | 変更権限 |
|---|---|---|---|
| 設計 | system-architect | inherit（既存コードを読む） | なし |
| 反証 | design-challenger | inherit、新規コンテキスト | なし |
| 計画 | tech-lead | inherit | なし |
| QA先行設計 | qa-test-designer | inherit、新規コンテキスト。実装ソースを渡さない | なし |
| 実装 | implementer | inherit。書き込み担当は原則1体 | 実装範囲のみ |
| テスト | qa-engineer | inherit。レビュー前に完了させる | 読み取り + 非破壊コマンド |
| レビュー | code-reviewer | inherit、変更凍結後 | 読み取り専用 |
| セキュリティ | security-reviewer | inherit、変更凍結後 | 読み取り専用 |
| 監査 | verification-auditor | inherit、変更凍結後 | 読み取り + 非破壊コマンド |

※ `inherit` は同一ワークスペースのスナップショットを確認する用途の推奨値です。並列で書き込みを行う場合は、別worktree等の分離方式と統合作業を別途設計してください。

## 3. レビューの独立性

レビュアーへ渡すもの：task brief、受入条件、承認済み設計、テストマトリクス、対象revision、review.diff、関連ソース、QAログ。

レビュアーへ渡さないもの：実装者の自己評価、意図の説明、親が先に付けた「問題なし」の結論。QAエンジニアにも実装者の自己評価を渡さず、テストマトリクスと実行対象だけを渡す。

## 4. レビュー結果の処理

- 各FindingにユニークIDを割り当てる。
- 根拠がない指摘は追加情報を要求する。
- 重複Findingは根本原因単位で統合する。
- 修正後は対象テスト + 回帰テストを再実行する。
- 変更差分を更新し、修正箇所と依存箇所を再レビューする。
- 修正中に新たな書き込みを許すため、再レビュー時も再度差分を凍結する。

## 5. 最終判定

`acceptance.md` の各欄を埋める。P0 / P1がゼロでも、必須テスト未実施や監査対象revision不一致ならPASSにしない。
