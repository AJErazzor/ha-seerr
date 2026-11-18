"""End-to-end tests against a fake Seerr API."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.seerr_requests.const import (
    CONF_EXTERNAL_URL, CONF_NOTIFY_SERVICES, CONF_WEBHOOK_ID, DOMAIN,
)

URL = "http://seerr.local:5055"
API = f"{URL}/api/v1"

REQ_MOVIE = {
    "id": 11, "status": 1, "type": "movie", "is4k": False,
    "createdAt": "2026-11-18T09:00:00.000Z",
    "media": {"tmdbId": 693134, "mediaType": "movie"},
    "requestedBy": {"displayName": "Bob", "avatar": "/avatarproxy/abc"},
    "seasons": [],
}
REQ_TV = {
    "id": 12, "status": 1, "type": "tv", "is4k": True,
    "createdAt": "2026-11-18T08:00:00.000Z",
    "media": {"tmdbId": 95396, "tvdbId": 371980, "mediaType": "tv"},
    "requestedBy": {"displayName": "Sue", "avatar": "https://gravatar.com/x"},
    "seasons": [{"seasonNumber": 1}, {"seasonNumber": 2}],
}
MOVIE = {"title": "Dune: Part Two", "releaseDate": "2024-02-27", "overview": "Paul...",
         "posterPath": "/p.jpg", "backdropPath": "/b.jpg", "externalIds": {"imdbId": "tt15239678"}}
TV = {"name": "Severance", "firstAirDate": "2022-02-17", "overview": "Mark...",
      "posterPath": "/s.jpg", "backdropPath": "/sb.jpg", "externalIds": {"tvdbId": 371980, "imdbId": "tt11280740"}}


REQ_APPROVED = {
    "id": 20, "status": 2, "type": "movie", "is4k": False,
    "createdAt": "2026-11-17T08:00:00.000Z",
    "media": {"tmdbId": 693134, "mediaType": "movie", "status": 3, "downloadStatus": []},
    "requestedBy": {"displayName": "Bob"}, "modifiedBy": {"displayName": "A.J."},
}
REQ_DOWNLOADING = {
    "id": 21, "status": 2, "type": "tv", "is4k": False,
    "createdAt": "2026-11-17T09:00:00.000Z",
    "media": {"tmdbId": 95396, "mediaType": "tv", "status": 3, "downloadStatus": [{"size": 10, "sizeLeft": 5}]},
    "requestedBy": {"displayName": "Sue"}, "modifiedBy": {"displayName": "A.J."},
    "seasons": [{"seasonNumber": 1}],
}
REQ_PARTIAL = {**REQ_DOWNLOADING, "id": 22, "media": {**REQ_DOWNLOADING["media"], "status": 4, "downloadStatus": []}}


def mock_api(aioclient_mock, pending, processing=()):
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API}/status", json={"version": "3.5.2"})
    aioclient_mock.get(f"{API}/request/count", json={"total": 5, "pending": len(pending), "approved": 3})
    aioclient_mock.get(f"{API}/request?filter=pending", json={"pageInfo": {}, "results": pending})
    aioclient_mock.get(f"{API}/request?filter=processing", json={"pageInfo": {}, "results": list(processing)})
    aioclient_mock.get(f"{API}/movie/693134", json=MOVIE)
    aioclient_mock.get(f"{API}/tv/95396", json=TV)
    aioclient_mock.post(f"{API}/request/11/approve", json={"id": 11, "status": 2})
    aioclient_mock.post(f"{API}/request/12/decline", json={"id": 12, "status": 3})


def make_entry(hass, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Seerr",
        data={CONF_URL: URL, CONF_API_KEY: "k", CONF_EXTERNAL_URL: "https://seerr.example.com",
              CONF_VERIFY_SSL: True, CONF_WEBHOOK_ID: "hookid"},
        options=options or {},
    )
    entry.add_to_hass(hass)
    return entry


async def test_config_flow(hass: HomeAssistant, aioclient_mock):
    mock_api(aioclient_mock, [])
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with patch("custom_components.seerr_requests.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: URL + "/", CONF_API_KEY: "k", CONF_EXTERNAL_URL: "", CONF_VERIFY_SSL: True})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_URL] == URL
    assert result["data"][CONF_WEBHOOK_ID]


async def test_config_flow_bad_key(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(f"{API}/status", json={"version": "3.5.2"})
    aioclient_mock.get(f"{API}/request/count", status=401)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: URL, CONF_API_KEY: "bad", CONF_VERIFY_SSL: True})
    assert result["errors"] == {"base": "invalid_auth"}


async def test_sensor_and_actions(hass: HomeAssistant, aioclient_mock):
    mock_api(aioclient_mock, [REQ_MOVIE, REQ_TV], [REQ_APPROVED, REQ_DOWNLOADING, REQ_PARTIAL, REQ_MOVIE])
    entry = make_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.seerr_pending_requests")
    assert state is not None, hass.states.async_entity_ids()
    assert state.state == "2"
    reqs = state.attributes["requests"]
    movie, tv = reqs
    assert movie["title"] == "Dune: Part Two" and movie["year"] == "2024"
    assert movie["requested_by_avatar"] == "https://seerr.example.com/avatarproxy/abc"
    assert movie["backdrop"] == "https://image.tmdb.org/t/p/w1280/b.jpg"
    assert movie["seerr_url"] == "https://seerr.example.com/movie/693134"
    assert movie["imdb_url"].endswith("tt15239678/") and movie["tvdb_url"] is None
    assert tv["seasons"] == [1, 2] and tv["is4k"] and tv["tvdb_url"].endswith("371980")
    assert movie["status"] == "pending" and movie["approved_by"] is None

    approved = hass.states.get("sensor.seerr_approved_requests")
    assert approved is not None, hass.states.async_entity_ids()
    # A pending request that slipped into the processing list is ignored.
    assert approved.state == "3"
    a, d, p = approved.attributes["requests"]
    assert (a["status"], a["approved_by"], a["title"]) == ("approved", "A.J.", "Dune: Part Two")
    assert d["status"] == "downloading" and d["title"] == "Severance"
    assert p["status"] == "partially_available"

    events = []
    hass.bus.async_listen(f"{DOMAIN}_request_actioned", lambda e: events.append(e))
    mock_api(aioclient_mock, [REQ_TV])
    await hass.services.async_call(DOMAIN, "approve", {"request_id": 11}, blocking=True)
    await hass.async_block_till_done()
    assert any(c[0] == "POST" and str(c[1]).endswith("/request/11/approve") for c in aioclient_mock.mock_calls)
    assert hass.states.get("sensor.seerr_pending_requests").state == "1"
    assert events and events[0].data["title"] == "Dune: Part Two"

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_notifications(hass: HomeAssistant, aioclient_mock):
    notify_calls = async_mock_service(hass, "notify", "mobile_app_pixel")
    mock_api(aioclient_mock, [REQ_MOVIE])
    entry = make_entry(hass, {CONF_NOTIFY_SERVICES: ["notify.mobile_app_pixel"]})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    # First run seeds the backlog without notifying.
    assert notify_calls == []

    new_events = []
    hass.bus.async_listen(f"{DOMAIN}_new_request", lambda e: new_events.append(e))
    mock_api(aioclient_mock, [REQ_MOVIE, REQ_TV])
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert len(notify_calls) == 1
    data = notify_calls[0].data
    assert data["title"] == "New TV request"
    assert data["message"] == "Sue requested Severance (2022) · Seasons 1–2, 4K"
    actions = [a["action"] for a in data["data"]["actions"]]
    assert actions[1].endswith("DECLINE_12")
    assert data["data"]["image"].endswith("/s.jpg")
    assert len(new_events) == 1

    # Tap Decline on the phone.
    mock_api(aioclient_mock, [REQ_MOVIE])
    hass.bus.async_fire("mobile_app_notification_action", {"action": actions[1]})
    await hass.async_block_till_done()
    assert any(str(c[1]).endswith("/request/12/decline") for c in aioclient_mock.mock_calls)
    last = notify_calls[-1].data
    assert last["message"] == "❌ Declined: Severance"
    assert not any(c.data.get("message") == "clear_notification" for c in notify_calls)

    # Movie approved in the Seerr UI -> nothing to clear (it was never notified).
    # Add a new one, notify, then it disappears -> its notification is cleared.
    req13 = {**REQ_MOVIE, "id": 13}
    mock_api(aioclient_mock, [REQ_MOVIE, req13])
    await entry.runtime_data.coordinator.async_refresh(); await hass.async_block_till_done()
    mock_api(aioclient_mock, [REQ_MOVIE])
    await entry.runtime_data.coordinator.async_refresh(); await hass.async_block_till_done()
    assert notify_calls[-1].data == {"message": "clear_notification", "data": {"tag": "seerr_request_13"}}
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_options_flow(hass: HomeAssistant, aioclient_mock):
    mock_api(aioclient_mock, [])
    async_mock_service(hass, "notify", "mobile_app_pixel")
    entry = make_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_NOTIFY_SERVICES: ["notify.mobile_app_pixel"], "scan_interval": 30})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["scan_interval"] == 30


def test_brand_images():
    """The Seerr icon and logos ship inside the integration (HA 2026.3+ shows them)."""
    from pathlib import Path

    from PIL import Image

    brand = Path(__file__).parent.parent / "custom_components" / DOMAIN / "brand"
    sizes = {
        "icon.png": (256, 256),
        "icon@2x.png": (512, 512),
        "logo.png": (None, 256),
        "logo@2x.png": (None, 512),
        "dark_logo.png": (None, 256),
        "dark_logo@2x.png": (None, 512),
    }
    for name, (width, height) in sizes.items():
        with Image.open(brand / name) as im:
            assert im.mode == "RGBA", name
            assert im.height == height, name
            if width:
                assert im.width == width, name
