import time as ttime

import requests

from bluesky_queueserver.manager.tests.test_general import re_manager  # noqa F401
from bluesky_queueserver.server.tests.conftest import (  # noqa F401
    SERVER_ADDRESS,
    SERVER_PORT,
    add_plans_to_queue,
    fastapi_server,
)


def _request_to_json(request_type, path, **kwargs):
    resp = getattr(requests, request_type)(f"http://{SERVER_ADDRESS}:{SERVER_PORT}{path}", **kwargs).json()
    return resp


def test_http_server_ping_handler(re_manager, fastapi_server):  # noqa F811
    resp = _request_to_json("get", "/")
    assert resp["msg"] == "RE Manager"
    assert resp["manager_state"] == "idle"
    assert resp["plans_in_queue"] == 0
    assert resp["running_plan_uid"] is None
    assert resp["worker_environment_exists"] is False


def test_http_server_get_queue_handler(re_manager, fastapi_server):  # noqa F811
    resp = _request_to_json("get", "/get_queue")
    assert resp["queue"] == []
    assert resp["running_plan"] == {}


def test_http_server_list_allowed_plans_and_devices(re_manager, fastapi_server):  # noqa F811
    resp = _request_to_json("get", "/list_allowed_plans_and_devices")
    assert isinstance(resp["allowed_plans"], dict)
    assert len(resp["allowed_plans"]) > 0
    assert isinstance(resp["allowed_devices"], dict)
    assert len(resp["allowed_devices"]) > 0


def test_http_server_add_to_queue_handler(re_manager, fastapi_server):  # noqa F811
    resp1 = _request_to_json("post", "/add_to_queue", json={"plan": {"name": "count", "args": [["det1", "det2"]]}})
    assert resp1["name"] == "count"
    assert resp1["args"] == [["det1", "det2"]]
    assert "plan_uid" in resp1

    resp2 = _request_to_json("get", "/get_queue")
    assert resp2["queue"] != []
    assert len(resp2["queue"]) == 1
    assert resp2["queue"][0] == resp1
    assert resp2["running_plan"] == {}


def test_http_server_pop_from_queue_handler(re_manager, fastapi_server, add_plans_to_queue):  # noqa F811

    resp1 = _request_to_json("get", "/get_queue")
    assert resp1["queue"] != []
    assert len(resp1["queue"]) == 3
    assert resp1["running_plan"] == {}

    resp2 = _request_to_json("post", "/pop_from_queue", json={})
    assert resp2["name"] == "count"
    assert resp2["args"] == [["det1", "det2"]]
    assert "plan_uid" in resp2


def test_http_server_create_environment_handler(re_manager, fastapi_server):  # noqa F811
    resp1 = _request_to_json("post", "/create_environment")
    assert resp1 == {"success": True, "msg": ""}

    ttime.sleep(2)  # TODO: API needed to test if environment initialization is finished. Use delay for now.

    resp2 = _request_to_json("post", "/create_environment")
    assert resp2 == {"success": False, "msg": "Environment already exists."}


def test_http_server_close_environment_handler(re_manager, fastapi_server):  # noqa F811
    resp1 = _request_to_json("post", "/create_environment")
    assert resp1 == {"success": True, "msg": ""}

    ttime.sleep(2)  # TODO: API needed to test if environment initialization is finished. Use delay for now.

    resp2 = _request_to_json("post", "/close_environment")
    assert resp2 == {"success": True, "msg": ""}

    ttime.sleep(3)  # TODO: API needed to test if environment is closed. Use delay for now.

    resp3 = _request_to_json("post", "/close_environment")
    assert resp3 == {"success": False, "msg": "Environment does not exist."}


def test_http_server_process_queue_handler(re_manager, fastapi_server, add_plans_to_queue):  # noqa F811
    resp1 = _request_to_json("post", "/process_queue")
    assert resp1 == {"success": False, "msg": "RE Worker environment does not exist."}

    resp2 = _request_to_json("post", "/create_environment")
    assert resp2 == {"success": True, "msg": ""}
    resp2a = _request_to_json("get", "/get_queue")
    assert len(resp2a["queue"]) == 3
    assert resp2a["running_plan"] == {}

    ttime.sleep(2)  # TODO: API needed to test if environment initialization is finished. Use delay for now.

    resp3 = _request_to_json("post", "/process_queue")
    assert resp3 == {"success": True, "msg": ""}

    ttime.sleep(1)
    # The plan is currently being executed. 'get_queue' is expected to return currently executed plan.
    resp4 = _request_to_json("get", "/get_queue")
    assert len(resp4["queue"]) == 2
    assert resp4["running_plan"]["name"] == "count"  # Check name of the running plan

    ttime.sleep(25)  # Wait until all plans are executed

    resp4 = _request_to_json("get", "/get_queue")
    assert len(resp4["queue"]) == 0
    assert resp2a["running_plan"] == {}


def test_http_server_re_pause_continue_handlers(re_manager, fastapi_server):  # noqa F811
    resp1 = _request_to_json("post", "/create_environment")
    assert resp1 == {"success": True, "msg": ""}

    ttime.sleep(2)  # TODO: API needed to test if environment initialization is finished. Use delay for now.

    resp2 = _request_to_json(
        "post",
        "/add_to_queue",
        json={"plan": {"name": "count", "args": [["det1", "det2"]], "kwargs": {"num": 10, "delay": 1}}},
    )
    assert resp2["name"] == "count"
    assert resp2["args"] == [["det1", "det2"]]
    assert "plan_uid" in resp2

    resp3 = _request_to_json("post", "/process_queue")
    assert resp3 == {"success": True, "msg": ""}
    ttime.sleep(3.5)  # Let some time pass before pausing the plan (fractional number of seconds)
    resp3a = _request_to_json("post", "/re_pause", json={"option": "immediate"})
    assert resp3a == {"msg": "", "success": True}
    ttime.sleep(1)  # TODO: API is needed
    resp3b = _request_to_json("get", "/get_queue")
    assert len(resp3b["queue"]) == 0  # The plan is paused, but it is not in the queue
    assert resp3b["running_plan"] != {}  # Running plan is set

    resp4 = _request_to_json("post", "/re_continue", json={"option": "abort"})
    assert resp4 == {"msg": "", "success": True}

    ttime.sleep(15)  # TODO: we need to wait for plan completion

    resp4a = _request_to_json("get", "/get_queue")
    assert len(resp4a["queue"]) == 1  # The plan is back in the queue
    assert resp4a["running_plan"] == {}


def test_http_server_close_print_db_uids_handler(re_manager, fastapi_server, add_plans_to_queue):  # noqa F811
    resp1 = _request_to_json("post", "/create_environment")
    assert resp1 == {"success": True, "msg": ""}

    ttime.sleep(2)  # TODO: API needed to test if environment initialization is finished. Use delay for now.

    resp2 = _request_to_json("post", "/process_queue")
    assert resp2 == {"success": True, "msg": ""}

    ttime.sleep(15)

    resp2a = _request_to_json("get", "/get_queue")
    assert len(resp2a["queue"]) == 0
    assert resp2a["running_plan"] == {}


def test_http_server_clear_queue_handler(re_manager, fastapi_server, add_plans_to_queue):  # noqa F811
    resp1 = _request_to_json("get", "/get_queue")
    assert len(resp1["queue"]) == 3

    resp2 = _request_to_json("post", "/clear_queue")
    assert resp2["success"] is True
    assert resp2["msg"] == "Plan queue is now empty."

    resp3 = _request_to_json("get", "/get_queue")
    assert len(resp3["queue"]) == 0


def test_http_server_plan_history(re_manager, fastapi_server):  # noqa F811
    # Select very short plan
    plan = {"plan": {"name": "count", "args": [["det1", "det2"]]}}
    _request_to_json("post", "/add_to_queue", json=plan)
    _request_to_json("post", "/add_to_queue", json=plan)
    _request_to_json("post", "/add_to_queue", json=plan)

    _request_to_json("post", "/create_environment")
    ttime.sleep(2)

    _request_to_json("post", "/process_queue")
    ttime.sleep(5)

    resp1 = _request_to_json("get", "/get_history")
    assert len(resp1["history"]) == 3
    assert resp1["history"][0]["name"] == "count"

    resp2 = _request_to_json("post", "/clear_history")
    assert resp2["success"] is True

    resp3 = _request_to_json("get", "/get_history")
    assert resp3["history"] == []
