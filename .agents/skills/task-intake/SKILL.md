---
name: task-intake
description: Clarifies engineering task scope, constraints, assumptions, risk, and verifiable acceptance criteria before implementation.
---

# Task Intake and Traceability

## 目的
要求を実装可能・検証可能な仕様へ変換する。曖昧さを勝手に埋めない。

## 手順
1. 目的、利用者、ユースケース、現状の問題を特定する。
2. 機能要件、非機能要件、制約、対象外を分離する。
3. 既存仕様・リポジトリ規約・互換性要件と衝突しないか確認する。
4. 曖昧な点は「仮定」「未決事項」として記録する。
5. 各要件を観測可能な受入条件へ変換する。
6. 要件IDを付け、設計・タスク・テスト・結果へ追跡できるようにする。

## 受入条件の書き方
「〜できる」だけで終わらず、前提・入力・操作・期待結果・失敗時の期待動作を含める。数値閾値は根拠がある場合だけ設定する。

## 出力
要件一覧、制約、仮定、対象外、リスク、受入条件、未決事項。
