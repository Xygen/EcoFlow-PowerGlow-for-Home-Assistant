"""RF-002: exercise the candidate method and unchanged legacy mode selector.

These test only the actual source methods with fake coordinators and no
connection to Home Assistant, cloud services or the physical heater.
"""

from __future__ import annotations

import ast
import asyncio
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).parents[1] / "custom_components" / "ecoflow_powerglow"


def method_from_source(filename: str, class_name: str, method_name: str, globals_=None):
    tree = ast.parse((SOURCE / filename).read_text(encoding="utf-8"))
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    method = next(
        n for n in klass.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == method_name
    )
    clean = copy.deepcopy(method)
    namespace = globals_ or {}
    exec(compile(ast.fix_missing_locations(
        ast.Module(body=[ast.ClassDef(
            name="Extracted", bases=[], keywords=[],
            body=[clean], decorator_list=[]
        )], type_ignores=[])
    ), "<actual-candidate-method>", "exec"), namespace)
    return namespace["Extracted"]


@pytest.mark.parametrize("cached_run_state", [0, 1, "unavailable"])
@pytest.mark.parametrize("transport_ack", ["set_reply_matched", "broker_echo_only"])
def test_explicit_shutdown_always_dispatches_even_if_cache_says_off(
    cached_run_state, transport_ack
):
    klass = method_from_source(
        "coordinator.py", "PowerGlowCoordinator",
        "async_request_shutdown"
    )
    coordinator = klass()
    coordinator.data = {"S": {"run_state_raw": cached_run_state}}
    coordinator.devices = {"S": {}}
    coordinator.calls = []

    async def fake_writer(serial, key, value):
        coordinator.calls.append((serial, key, value))
        return transport_ack

    coordinator.async_set_parameter = fake_writer
    result = asyncio.run(coordinator.async_request_shutdown("S"))
    assert result == transport_ack
    assert coordinator.calls == [("S", "run_state_raw", 0)]


def test_failed_explicit_shutdown_is_not_reported_success():
    klass = method_from_source(
        "coordinator.py", "PowerGlowCoordinator",
        "async_request_shutdown"
    )
    coordinator = klass()

    async def fake_writer(*_args):
        raise ConnectionError("fake MQTT link down")

    coordinator.async_set_parameter = fake_writer
    with pytest.raises(ConnectionError):
        asyncio.run(coordinator.async_request_shutdown("S"))


@pytest.mark.parametrize("run_state,expected", [
    (0, []),
    (1, [("S", "run_state_raw", 0)]),
])
def test_existing_mode_select_is_unchanged(run_state, expected):
    klass = method_from_source(
        "select.py", "PowerGlowOperatingModeSelect", "async_select_option",
        {
            "OPTION_OFF": "off",
            "OPTION_SOLAR": "solar",
            "OPTION_MANUAL": "manual",
        }
    )
    selector = klass()
    calls = []

    async def fake_writer(*args):
        calls.append(args)

    selector.coordinator = SimpleNamespace(
        data={"S": {"run_state_raw": run_state, "mode_raw": 1}},
        async_set_parameter=fake_writer,
    )
    selector.serial = "S"
    asyncio.run(selector.async_select_option("off"))
    assert calls == expected


def test_normal_select_cannot_substitute_for_emergency_dispatch():
    # Both APIs must deliberately remain distinct:
    # normal user OFF may be a no-op, explicit shutdown must re-send OFF.
    normal = method_from_source(
        "select.py", "PowerGlowOperatingModeSelect", "async_select_option",
        {
            "OPTION_OFF": "off",
            "OPTION_SOLAR": "solar",
            "OPTION_MANUAL": "manual",
        }
    )()
    forced = method_from_source(
        "coordinator.py", "PowerGlowCoordinator",
        "async_request_shutdown"
    )()
    calls = []

    async def send(*args):
        calls.append(args)
        return "set_reply_matched"

    normal.coordinator = SimpleNamespace(
        data={"S": {"run_state_raw": 0, "mode_raw": 1}},
        async_set_parameter=send,
    )
    normal.serial = "S"
    forced.async_set_parameter = send
    asyncio.run(normal.async_select_option("off"))
    assert calls == []
    asyncio.run(forced.async_request_shutdown("S"))
    assert calls == [("S", "run_state_raw", 0)]
