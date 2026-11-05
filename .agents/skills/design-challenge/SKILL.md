---
name: design-challenge
description: Adversarially challenges an architecture proposal by testing assumptions, failure modes, security boundaries, operational risks, and simpler alternatives.
---

# Design Challenge

## 姿勢
設計を擁護するのではなく、要求に照らして反証する。指摘は具体的な成立条件と影響を伴うものに限定する。

## チャレンジ質問
- どの前提が崩れると全体が停止するか。
- リトライ・タイムアウト・二重送信・順序逆転で何が起きるか。
- 同時更新、重複要求、部分成功でデータは壊れないか。
- 権限境界・テナント境界・外部入力は正しいか。
- デプロイ途中、ロールバック、古いクライアントとの互換性はどうなるか。
- 監視できない障害、復旧不能な状態はないか。
- より単純で失敗面の少ない設計はないか。

## 出力
指摘ID、重大度、対象設計、成立条件、影響、根拠、代替案、実装前に解消すべきか、残存リスク。
