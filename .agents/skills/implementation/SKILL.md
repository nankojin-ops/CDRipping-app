---
name: implementation
description: Implements approved engineering tasks with minimal scoped changes, project conventions, meaningful tests, and reproducible evidence.
---

# Implementation Protocol

## 開始前
- 既存差分とユーザー変更を確認する。
- 承認済み設計・契約・タスク境界・受入条件を読む。
- 不明点や矛盾を記録し、勝手に仕様を確定しない。

## 実装中
- 最小の変更で受入条件を満たす。
- 既存の命名・レイヤー・エラー処理・DI・テスト規約を守る。
- 例外・境界値・権限・競合・リソース解放を考慮する。
- 変更に対応したテストを追加する。
- 無関係なリファクタリングや依存追加を混ぜない。
- 既存テストを削除・無効化・弱体化して合格させない。

## 完了時
- 変更ファイルと意図を列挙する。
- 実行したコマンド・終了コード・未実施項目を記録する。
- 既知の制約、残存リスク、設計との差異を開示する。
- 自己レビューを最終合格判定として扱わない。
