"""EcoFlow consumer API used by the PowerGlow integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import IOT_API_BASE, POWERGLOW_PREFIX
from .ecoflow.enhanced_auth import enhanced_login, get_enhanced_credentials
from .parser import extract_powerglow_reports, parse_powerglow_detail_response

_LOGGER = logging.getLogger(__name__)

_DEVICE_LIST_PATH = "/iot-service/user/device"
_PROVIDER_DEVICE_LIST_PATH = "/provider-service/user/device/list"
_DEVICE_DETAIL_PATH = "/provider-service/user/device/detail"
_POWEROCEAN_PRODUCT_TYPES = frozenset({"83", "85", "86", "87"})


class PowerGlowApiClient:
    """Small async client for account login, discovery, and detail polling."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._token = ""
        self._user_id = ""
        self._base_url = IOT_API_BASE
        self._consumer_base_url: str | None = None

    @property
    def user_id(self) -> str:
        return self._user_id

    async def async_login(self) -> None:
        result = await enhanced_login(self._session, self._email, self._password)
        if result is None:
            raise ConnectionError("EcoFlow login failed")
        self._token = result["token"]
        self._user_id = result["user_id"]
        self._base_url = result.get("base_url", IOT_API_BASE)

    async def async_get_mqtt_credentials(self) -> dict[str, Any]:
        credentials = await get_enhanced_credentials(
            self._session, self._token, base_url=self._base_url
        )
        if not credentials:
            raise ConnectionError("EcoFlow MQTT credentials unavailable")
        return credentials

    async def async_discover_powerglows(self) -> dict[str, dict[str, Any]]:
        """Return child PowerGlow records keyed by heating-rod serial number."""
        account_devices = await self._async_get_account_devices()
        direct = {
            item["sn"]: item
            for item in account_devices
            if item["sn"].upper().startswith(POWERGLOW_PREFIX)
        }
        parents = await self._async_get_powerocean_parents(account_devices)
        found: dict[str, dict[str, Any]] = {}
        for parent in parents:
            detail = await self.async_get_device_detail(parent["sn"], parent["product_type"])
            if not detail:
                continue
            for serial in extract_powerglow_reports(detail):
                if serial.upper().startswith(POWERGLOW_PREFIX):
                    found[serial] = {
                        "serial": serial,
                        "name": direct.get(serial, {}).get(
                            "name", "EcoFlow PowerGlow"
                        ),
                        "parent_sn": parent["sn"],
                        "product_type": parent["product_type"],
                    }
        return found

    async def async_get_device_detail(self, serial: str, product_type: str) -> dict[str, Any] | None:
        headers = self._headers(product_type)
        for base_url in self._consumer_base_urls():
            try:
                async with self._session.get(
                    f"{base_url}{_DEVICE_DETAIL_PATH}",
                    params={"sn": serial},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    response.raise_for_status()
                    body = await response.json()
                    if str(body.get("code", "0")) == "0" and isinstance(body.get("data"), dict):
                        self._consumer_base_url = base_url
                        return body
            except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
                _LOGGER.debug("PowerOcean detail request failed via %s: %s", base_url, exc)
        return None

    async def async_read_powerglow(self, device: dict[str, Any]) -> dict[str, Any]:
        detail = await self.async_get_device_detail(device["parent_sn"], device["product_type"])
        if not detail:
            raise ConnectionError("PowerGlow detail unavailable")
        return parse_powerglow_detail_response(detail, device["serial"])

    async def _async_get_account_devices(self) -> list[dict[str, str]]:
        """Return normalized bound/shared devices from the app account."""
        async with self._session.get(
            f"{self._base_url}{_DEVICE_LIST_PATH}",
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            response.raise_for_status()
            data = (await response.json()).get("data", {})
        result: list[dict[str, str]] = []
        seen: set[str] = set()
        for group_name in ("bound", "share"):
            group = data.get(group_name, {}) if isinstance(data, dict) else {}
            if not isinstance(group, dict):
                continue
            for key, value in group.items():
                values = value if isinstance(value, list) else [value]
                for item in values:
                    if not isinstance(item, dict):
                        continue
                    serial = str(item.get("sn") or key).upper()
                    if not serial or serial in seen:
                        continue
                    seen.add(serial)
                    result.append(
                        {
                            "sn": serial,
                            "name": str(
                                item.get("deviceName")
                                or item.get("productName")
                                or serial
                            ),
                            "product_type": str(
                                item.get("productType")
                                or item.get("product_type")
                                or ""
                            ),
                        }
                    )
        return result

    async def _async_get_powerocean_parents(
        self, account_devices: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        for base_url in self._consumer_base_urls():
            try:
                async with self._session.get(
                    f"{base_url}{_PROVIDER_DEVICE_LIST_PATH}",
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    response.raise_for_status()
                    body = await response.json()
                parents = _extract_powerocean_devices(body)
                if parents:
                    self._consumer_base_url = base_url
                    return parents
            except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
                _LOGGER.debug("PowerOcean discovery failed via %s: %s", base_url, exc)

        # Some EcoFlow accounts expose the PowerOcean in the normal app device
        # list but return an empty provider list. The product-type value from
        # the app list is also valid for the consumer-detail request.
        return [
            {"sn": item["sn"], "product_type": item["product_type"]}
            for item in account_devices
            if item["product_type"] in _POWEROCEAN_PRODUCT_TYPES
        ]

    def _headers(self, product_type: str = "") -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._token}"}
        if product_type:
            headers["product-type"] = product_type
        return headers

    def _consumer_base_urls(self) -> tuple[str, ...]:
        candidates = (
            self._consumer_base_url,
            self._base_url,
            IOT_API_BASE,
            "https://api-a.ecoflow.com",
        )
        return tuple(dict.fromkeys(filter(None, candidates)))


def _extract_powerocean_devices(value: Any) -> list[dict[str, str]]:
    """Find PowerOcean records in regional provider-list response shapes."""
    found: dict[str, dict[str, str]] = {}

    def visit(nested: Any) -> None:
        if isinstance(nested, dict):
            serial = str(nested.get("sn") or "")
            product_type = str(
                nested.get("productType") or nested.get("product_type") or ""
            )
            if serial and product_type in _POWEROCEAN_PRODUCT_TYPES:
                found[serial] = {"sn": serial, "product_type": product_type}
            for child in nested.values():
                visit(child)
        elif isinstance(nested, list):
            for child in nested:
                visit(child)

    visit(value)
    return list(found.values())
