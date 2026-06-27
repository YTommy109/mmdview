# /bump — バージョン bump & リリースタグ

引数: $ARGUMENTS（patch | minor | major）

以下の手順を実行してください。

## 1. 引数の検証

- `$ARGUMENTS` が `patch`、`minor`、`major` のいずれかであることを確認する
- それ以外の場合はエラーメッセージを表示して終了する

## 2. ブランチの検証

- 現在のブランチが `main` であることを確認する
- `main` 以外の場合はエラーメッセージを表示して終了する

## 3. バージョンの bump

- `MmdviewApp/project.yml` の `MARKETING_VERSION` から現在のバージョン（例: `1.0.0`）を読み取る
- `$ARGUMENTS` に応じて semver をインクリメントする:
  - `patch`: 1.0.0 → 1.0.1
  - `minor`: 1.0.0 → 1.1.0
  - `major`: 1.0.0 → 2.0.0
- `MmdviewApp/project.yml` の `MARKETING_VERSION` を新バージョンに書き換える

## 4. コミットとタグ

以下のコマンドを実行する:

```bash
git add MmdviewApp/project.yml
git commit -m "chore: バージョンを {旧バージョン} から {新バージョン} に更新する"
git tag "v{新バージョン}"
```

## 5. プッシュ

```bash
git push
git push --tags
```

## 6. 完了メッセージ

`v{旧バージョン} → v{新バージョン}` をリリースタグと共にプッシュしたことを報告する。
