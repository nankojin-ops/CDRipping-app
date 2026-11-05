---
name: implementation-planning
description: Breaks approved technical designs into sequenced engineering tasks, interface contracts, ownership boundaries, dependencies, and testable completion criteria.
---

# Implementation Planning

## 手順
1. 既存コードの責務と変更点を照合する。
2. タスクをレビュー可能な小さな単位へ分割する。
3. 依存関係と安全な並列化境界を明記する。
4. API / 型 / DB / イベント契約を先に固める。
5. データ移行、後方互換性、ロールバックを検討する。
6. 各タスクに対象ファイル候補・テスト責務・完了条件を付ける。
7. スコープ外のリファクタリングを切り離す。

## 出力
タスクID、目的、責務、依存、対象、契約、完了条件、テスト、リスク、順序。
