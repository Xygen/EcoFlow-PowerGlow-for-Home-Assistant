"""Pure, offline contract tests for the opt-in device-scoped shutdown action.

Run the exact _request_shutdown function body from the candidate services.py
with fake registries and an in-memory coordinator. No HA Core, MQTT or heater.
"""
from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "custom_components" / "ecoflow_powerglow" / "services.py"
DOMAIN = "ecoflow_powerglow"


class ServiceValidationError(Exception):
    pass


class HomeAssistantError(Exception):
    pass


class ConfigEntryState:
    LOADED = "loaded"


class FakeCoordinator:
    def __init__(self, *, connected=True, status="set_reply_matched"):
        self.devices = {"TEST_DEVICE": {"parent_sn": "TEST_PARENT"}}
        self.connected = connected
        self.status = status
        self.calls = []

    async def async_request_shutdown(self, serial):
        self.calls.append(serial)
        if not self.connected:
            raise ConnectionError("offline test MQTT disconnected")
        return self.status


def load_request_handler(*, device=None):
    text = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    method = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_request_shutdown"
    )
    import copy

    clean = copy.deepcopy(method)
    clean.args.args[0].annotation = None
    clean.args.args[1].annotation = None
    clean.returns = None
    namespace = {
        "DOMAIN": DOMAIN,
        "dr": SimpleNamespace(async_get=lambda hass: SimpleNamespace(
            async_get=lambda device_id: hass.registry.get(device_id)
        )),
        "ConfigEntryState": ConfigEntryState,
        "ServiceValidationError": ServiceValidationError,
        "HomeAssistantError": HomeAssistantError,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(
        body=[clean], type_ignores=[]
    )), "<candidate-services>", "exec"), namespace)
    return namespace["_request_shutdown"]


def environment(*, state=ConfigEntryState.LOADED, domain=DOMAIN,
                valid_device=True, connected=True, status="set_reply_matched",
                duplicated=False):
    coordinator = FakeCoordinator(connected=connected, status=status)
    entry = SimpleNamespace(
        domain=domain, state=state, runtime_data=coordinator
    )
    device = SimpleNamespace(
        identifiers={(DOMAIN, "TEST_DEVICE")},
        config_entries={"e1", "e2"} if duplicated else {"e1"},
    )
    hass = SimpleNamespace(
        registry={"device42": device} if valid_device else {},
        config_entries=SimpleNamespace(
            async_get_entry=lambda entry_id: entry if entry_id in (
                {"e1", "e2"} if duplicated else {"e1"}
            ) else None
        ),
    )
    call = SimpleNamespace(data={"device_id": "device42"})
    return hass, call, coordinator


@pytest.mark.parametrize("result", ["set_reply_matched", "broker_echo_only"])
def test_forced_shutdown_requests_off_even_when_cached_off(result):
    # The service never consults a cached run_state_raw at all.
    run = load_request_handler()
    hass, call, coordinator = environment(status=result)
    response = asyncio.run(run(hass, call))
    assert response == {
        "transport_evidence": result, "physical_shutdown_verified": False
    }
    assert coordinator.calls == ["TEST_DEVICE"]


def test_unknown_device_fails_closed():
    run = load_request_handler()
    hass, call, coordinator = environment(valid_device=False)
    with pytest.raises(ServiceValidationError, match="not found"):
        asyncio.run(run(hass, call))
    assert coordinator.calls == []


@pytest.mark.parametrize("domain,state", [
    ("another_domain", ConfigEntryState.LOADED),
    (DOMAIN, "not_loaded"),
])
def test_unrelated_or_unloaded_config_cannot_be_addressed(domain, state):
    run = load_request_handler()
    hass, call, coordinator = environment(domain=domain, state=state)
    with pytest.raises(ServiceValidationError, match="exactly one"):
        asyncio.run(run(hass, call))
    assert coordinator.calls == []


def test_ambiguous_device_does_not_accidentally_target_multiple_entries():
    run = load_request_handler()
    hass, call, coordinator = environment(duplicated=True)
    with pytest.raises(ServiceValidationError, match="exactly one"):
        asyncio.run(run(hass, call))
    assert coordinator.calls == []


def test_transport_failure_is_not_silently_reported_as_shutdown():
    run = load_request_handler()
    hass, call, coordinator = environment(connected=False)
    with pytest.raises(HomeAssistantError, match="MQTT"):
        asyncio.run(run(hass, call))
    assert coordinator.calls == ["TEST_DEVICE"]


def test_wrong_device_identifier_fails_closed():
    run = load_request_handler()
    hass, call, coordinator = environment()
    hass.registry["device42"].identifiers = {("other_integration", "TEST_DEVICE")}
    with pytest.raises(ServiceValidationError, match="exactly one"):
        asyncio.run(run(hass, call))
    assert coordinator.calls == []


def test_schema_service_registration_is_opt_in():
    text = (ROOT / "custom_components" / "ecoflow_powerglow" / "__init__.py").read_text()
    service = SOURCE.read_text(encoding="utf-8")
    assert "async def async_setup(" in text
    assert "async_register_services(hass)" in text
    assert "SERVICE_REQUEST_SHUTDOWN = \"request_shutdown\"" in service
    assert "SupportsResponse.OPTIONAL" in service
    assert "vol.Required(\"device_id\")" in service
