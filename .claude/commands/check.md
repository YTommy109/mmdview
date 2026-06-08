# /check — 品質チェック

以下を順番に実行して結果を報告してください。

1. **Ruff lint**
   ```bash
   uv run task lint
   ```

2. **Ruff format check**
   ```bash
   uv run ruff format --check .
   ```

3. **ty 型チェック**
   ```bash
   uv run task typecheck
   ```

4. **ユニット + 統合テスト（カバレッジ付き）**
   ```bash
   uv run task test
   ```

問題が見つかった場合は修正してから再実行してください。すべて通過したら「✅ チェック完了」と報告してください。
