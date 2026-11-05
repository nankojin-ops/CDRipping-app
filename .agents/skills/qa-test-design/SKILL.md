---
name: qa-test-design
description: Designs implementation-blind acceptance test matrices from requirements, including normal, negative, boundary, permission, concurrency, resilience, and regression cases.
---

# QA Test Design

## 原則
実装コードを見ずに、要求と受入条件から期待動作を定義する。実装に合わせて期待値を緩めない。

## 観点
- 正常系、代表値、最小・最大・境界の直前直後
- null、空文字、欠落フィールド、不正型、異常フォーマット
- 認証なし、権限不足、他ユーザー・他テナントのデータ
- 重複要求、再試行、順序逆転、同時更新
- タイムアウト、外部依存失敗、部分成功、回復
- 大量データ、長い入力、リソース上限
- 既存機能・API互換性・データ移行後の回帰
- ログやエラーに秘密情報・個人情報が漏れないこと

## テストケース形式
- Test ID
- 対応する Requirement / Acceptance ID
- 優先度
- テストレベル
- 前提条件・fixture
- 入力・操作手順
- 期待結果
- 失敗時の期待結果
- 自動化方法 / 手動確認の理由

全受入条件に少なくとも1つの検証方法があること。網羅率の数値を根拠なく100%と宣言しない。
