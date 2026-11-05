---
name: remediation-triage
description: Consolidates independent review and QA findings, assigns severity and owners, identifies root causes, and controls remediation and re-review loops.
---

# Remediation Triage and Fix Loop

## 統合
- 同じ根本原因の指摘は重複統合し、元の報告IDを保持する。
- 根拠のない意見と、再現可能な欠陥を区別する。
- P0-P3を付け、影響・発生条件・修正範囲を明確にする。

## 修正
- P0 / P1は必ず修正。
- P2は原則修正。残す場合は影響、回避策、承認者を記録。
- P3は対応 / 非対応と理由を記録。
- 根本原因を直し、再発防止テストを追加する。

## 再検証
- 修正Issueに対応するテストと回帰テストを再実行する。
- 変更差分を更新し、該当ファイルと依存箇所を再レビューする。
- 修正による新規不具合を探す。
- 同じ根本原因が繰り返される場合は設計へ戻す。
- 3サイクルで合格しなければ人間へエスカレーションする。
