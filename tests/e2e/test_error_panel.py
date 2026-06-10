from playwright.sync_api import Browser, expect


def test_error_panel_shows_detailed_message(browser: Browser, server_url, tmp_path):
    """構文エラー時にエラーパネルへ詳細メッセージ（行番号付き）を表示する。

    mermaid.parseError は最後にプレーンオブジェクトを渡してくるため、
    そのまま表示すると "[object Object]" になる（regression test）。
    """
    from backend.services.window_registry import window_registry

    broken = tmp_path / "broken.mmd"
    broken.write_text("stateDiagram-v2\n  [*] --> \n  A --> B\n", encoding="utf-8")
    window_registry.create("e2e-err", str(broken))
    context = browser.new_context()
    try:
        page = context.new_page()
        page.goto(f"{server_url}/?window_id=e2e-err")
        panel = page.locator("#mmd-error")
        expect(panel).to_be_visible()
        expect(panel).not_to_contain_text("[object Object]")
        expect(panel).to_contain_text("Parse error on line")
        expect(page.locator("#diagram-wrap")).to_be_hidden()
    finally:
        context.close()
        window_registry.remove("e2e-err")
