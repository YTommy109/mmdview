import pytest
from playwright.sync_api import Page, expect


def test_zoom_in_button_increases_zoom(viewer_page: Page):
    viewer_page.locator("#zoom-in").click()
    expect(viewer_page.locator("#zoom-label")).to_have_text("125%")


def test_zoom_out_button_decreases_zoom(viewer_page: Page):
    viewer_page.locator("#zoom-out").click()
    expect(viewer_page.locator("#zoom-label")).to_have_text("75%")


def test_label_click_resets_zoom(viewer_page: Page):
    viewer_page.locator("#zoom-in").click()
    viewer_page.locator("#zoom-in").click()
    expect(viewer_page.locator("#zoom-label")).to_have_text("150%")
    viewer_page.locator("#zoom-label").click()
    expect(viewer_page.locator("#zoom-label")).to_have_text("100%")


def test_zoom_clamped_at_maximum(viewer_page: Page):
    for _ in range(10):
        viewer_page.locator("#zoom-in").click()
    expect(viewer_page.locator("#zoom-label")).to_have_text("200%")
    expect(viewer_page.locator("#zoom-in")).to_be_disabled()


def test_zoom_clamped_at_minimum(viewer_page: Page):
    for _ in range(10):
        viewer_page.locator("#zoom-out").click()
    expect(viewer_page.locator("#zoom-label")).to_have_text("50%")
    expect(viewer_page.locator("#zoom-out")).to_be_disabled()


def test_zoom_stored_in_localstorage(viewer_page: Page):
    viewer_page.locator("#zoom-in").click()
    value = viewer_page.evaluate("localStorage.getItem('mmdview.viewer.zoom')")
    assert float(value) == pytest.approx(1.25)


def test_zoom_restored_from_localstorage(browser, server_url):
    """localStorage に保存されたズーム値がページリロード後に復元されること。"""
    context = browser.new_context()
    page1 = context.new_page()
    page1.goto(f"{server_url}/?window_id=e2e")
    page1.wait_for_load_state("networkidle")
    page1.locator("#zoom-in").click()
    page1.locator("#zoom-in").click()
    expect(page1.locator("#zoom-label")).to_have_text("150%")

    page2 = context.new_page()
    page2.goto(f"{server_url}/?window_id=e2e")
    page2.wait_for_load_state("networkidle")
    expect(page2.locator("#zoom-label")).to_have_text("150%")

    context.close()


def test_keyboard_cmd_equals_zooms_in(viewer_page: Page):
    viewer_page.keyboard.press("Meta+=")
    expect(viewer_page.locator("#zoom-label")).to_have_text("125%")


def test_keyboard_cmd_minus_zooms_out(viewer_page: Page):
    viewer_page.keyboard.press("Meta+-")
    expect(viewer_page.locator("#zoom-label")).to_have_text("75%")


def test_ctrl_wheel_zooms_in(viewer_page: Page):
    diagram = viewer_page.locator("#diagram-wrap")
    diagram.scroll_into_view_if_needed()
    viewer_page.mouse.move(*diagram.bounding_box().values())
    viewer_page.keyboard.down("Control")
    viewer_page.mouse.wheel(0, -100)
    viewer_page.keyboard.up("Control")
    label_text = viewer_page.locator("#zoom-label").inner_text()
    zoom = int(label_text.replace("%", ""))
    assert zoom > 100
