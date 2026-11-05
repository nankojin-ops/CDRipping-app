---
name: verification-audit
description: Independently audits exact-revision build, test, type-check, lint, and acceptance evidence using non-destructive project commands.
---

# Verification Audit

## 対象一致性
レビュー対象revisionと実行対象revisionを確認する。対象差分が変わった場合、古い結果を流用せず再実行を要求する。

## コマンド選定
README、CI、package scripts、Makefile、pyproject等で定義された正式コマンドを使う。実行前に非破壊であることを確認する。デプロイ、migration、データ削除、本番接続、外部書き込み、課金操作は実行しない。

## 証跡
コマンド、環境、開始・終了、終了コード、pass / fail / skip、ログ、未実施理由を記録する。成功の文章だけでは認定しない。

## 偽陽性の確認
- テストが対象コードを実行しているか
- assertionが無効化されていないか
- 過剰なmock・stubで実処理を迂回していないか
- skip / quarantine / xfailが隠されていないか
- エラーをcatchしてテストを成功扱いしていないか
- 検査対象のファイル・revisionが合っているか

## 判定
PASS / FAIL / INCOMPLETEを使用する。未実施や環境制約はPASSに含めない。
