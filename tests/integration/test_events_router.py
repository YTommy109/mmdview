from fastapi.routing import APIRoute


def test_events_route_is_registered():
    from backend.main import app

    paths = [r.path for r in app.routes if isinstance(r, APIRoute)]
    assert "/events" in paths


def test_events_route_has_get_method():
    from backend.main import app

    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == "/events":
            assert "GET" in route.methods
            return
    assert False, "/events route not found"


def test_events_route_accepts_window_id_param():
    from backend.main import app

    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == "/events":
            param_names = [p.name for p in route.dependant.query_params]
            assert "window_id" in param_names, f"window_id not in query params: {param_names}"
            return
    assert False, "/events route not found"
