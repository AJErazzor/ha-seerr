"""Pending requests sensor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SeerrConfigEntry
from .const import DOMAIN
from .coordinator import SeerrCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: SeerrConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [SeerrPendingSensor(coordinator, entry), SeerrProcessingSensor(coordinator, entry)]
    )


class SeerrRequestsSensor(CoordinatorEntity[SeerrCoordinator], SensorEntity):
    """Base: a count of requests, with the list in the attributes."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "requests"
    # The request list (summaries, artwork links) is too big to keep in history.
    _unrecorded_attributes = frozenset({"requests"})

    def __init__(self, coordinator: SeerrCoordinator, entry: SeerrConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{self._key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Seerr",
            manufacturer="Seerr",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.external_url,
            sw_version=coordinator.data.version if coordinator.data else None,
        )

    _key = ""
    _key_label = ""

    def _requests(self) -> list[dict[str, Any]]:
        return getattr(self.coordinator.data, self._key) if self.coordinator.data else []

    @property
    def native_value(self) -> int:
        return len(self._requests())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if not data:
            return {}
        return {
            "kind": self._key_label,
            "requests": self._requests(),
            "seerr_url": self.coordinator.external_url,
        }


class SeerrPendingSensor(SeerrRequestsSensor):
    """Requests waiting for approval; also carries Seerr's request totals."""

    _key = "pending"
    _key_label = "pending"
    _attr_translation_key = "pending_requests"
    _attr_icon = "mdi:movie-open-plus"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if not data:
            return {}
        counts = data.counts or {}
        return {
            "kind": self._key_label,
            "requests": data.pending,
            "seerr_url": self.coordinator.external_url,
            "total": counts.get("total"),
            "approved": counts.get("approved"),
            "declined": counts.get("declined"),
            "processing": counts.get("processing"),
            "available": counts.get("available"),
        }


class SeerrProcessingSensor(SeerrRequestsSensor):
    """Approved requests that aren't fully in the library yet."""

    _key = "processing"
    _key_label = "approved"
    _attr_translation_key = "processing_requests"
    _attr_icon = "mdi:progress-download"
