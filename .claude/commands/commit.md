# /commit — コミット提案

`git diff --staged` を確認し、Conventional Commits 形式で日本語コミットメッセージを提案してください。

フォーマット:
```
<type>: <変更内容を動詞で始める日本語>

[body: 必要な場合のみ]
```

type の選択:
- `feat`: 新機能
- `fix`: バグ修正
- `chore`: ビルド・設定・依存関係
- `docs`: ドキュメントのみ
- `refactor`: 機能変更なしのコード整理
- `test`: テストの追加・修正

メッセージを提案したら、確認後に `git commit -m "..."` を実行してください。
