---
name: architecture-design
description: Produces and evaluates system architecture, component boundaries, data and API contracts, failure handling, security, and non-functional requirements.
---

# Architecture Design

## 設計原則
- 要件・制約・既存構造から設計し、流行や好みで技術を追加しない。
- コンポーネント責務と依存方向を明示し、循環依存を避ける。
- API・イベント・データモデル・状態遷移・エラー契約を曖昧にしない。
- タイムアウト、リトライ、冪等性、部分障害、整合性を検討する。
- 認証・認可・信頼境界・データ保護を設計に含める。
- 監視、ログ、トレース、運用、移行、ロールバックを検討する。
- 可用性・性能・拡張性は要求から必要水準を導く。

## 出力
設計概要、構成図、責務、契約、データフロー、障害時動作、セキュリティ、運用、代替案、トレードオフ、受入条件への対応表。
