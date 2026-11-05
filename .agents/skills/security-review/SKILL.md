---
name: security-review
description: Audits application and infrastructure changes for authentication, authorization, injection, secrets, privacy, dependency, configuration, and data-protection vulnerabilities.
---

# Security Review

## 攻撃面
- 入力境界：SQL / command / template / path / HTML / deserialization / SSRF / open redirect
- 認証：session、token、MFA、失効、期限、credential storage
- 認可：最小権限、IDOR、tenant isolation、role escalation
- Web境界：CSRF、CORS、CSP、cookie属性、output encoding
- データ：PII、secret、暗号化、鍵管理、ログ、バックアップ、削除
- 可用性：rate limit、resource exhaustion、expensive query、queue flooding
- サプライチェーン：依存パッケージ、lockfile、脆弱設定、過剰権限

## 判断
攻撃者、前提条件、到達可能な入力、悪用手順、影響、根拠を説明する。実際に悪用可能か不明な場合は可能性と不確実性を分ける。

## 出力
P0-P3のFinding、推奨緩和策、再検証方法、未確認観点。確認していない領域を安全と断言しない。
