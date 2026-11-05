---
name: independent-code-review
description: Performs a skeptical, read-only code review against specifications and frozen diffs, finding correctness bugs, edge cases, regressions, and maintainability risks.
---

# Independent Code Review

## 独立性
実装者の説明・意図・自己評価は結論の根拠にしない。仕様・設計・差分・実コード・テストで判断する。ファイルを変更しない。

## 観点
1. 要件・受入条件との対応
2. ロジック・状態遷移・データ整合性
3. 境界値、null、異常入力、例外、タイムアウト
4. 認証・認可・テナント境界
5. 並行性、競合、二重実行、冪等性
6. エラー処理、リソース解放、再試行
7. 後方互換性、スキーマ/API変更、回帰
8. 性能、メモリ、N+1、無駄なI/O
9. 保守性、責務、重複、過剰な複雑性
10. テストの妥当性、実際に通るコードパス、偽陽性

## Finding基準
P0: 重大なデータ損失・漏えい・停止。P1: 主要機能破壊・権限不備・重大回帰。P2: 条件付き不具合・重要な境界値や保守性問題。P3: 軽微な改善。

各指摘には場所、条件、期待/実際、根拠、影響、根本原因、修正案、再テストを含める。意見だけの指摘は出さない。

## No Findingの場合
確認したファイル・観点・確認方法・未確認範囲・残存リスクを記録する。「問題なし」の一言で終えない。
