# Seerr Requests for Home Assistant

See, approve and reject [Seerr](https://seerr.dev) requests from Home Assistant — on a dashboard card or straight from a phone notification. Works with Seerr 3.x, Jellyseerr and Overseerr.

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=AJErazzor&repository=ha-seerr&category=integration)

## What you get

- **Pending requests sensor** — `sensor.seerr_pending_requests`, the number waiting, with every request (title, year, who, when, poster, fanart, summary, links) in its attributes.
- **Approved requests sensor** — `sensor.seerr_approved_requests`, approved requests that aren't in your library yet, each with a status: `approved`, `downloading` or `partially_available`, and who approved it.
- **Phone notifications** with the poster and **Approve / Decline** buttons. Tapping a button does the job; no automations needed. The notification clears itself if the request is handled somewhere else.
- **Dashboard card** — fanart background (optional), poster, who requested it and when, summary, TMDB / IMDb / TVDB / Open in Seerr links, and Approve / Reject buttons. Reject needs two taps. A second section, **Approved · on its way**, lists approved requests with their status until they're fully available.
- **Actions** `seerr_requests.approve` and `seerr_requests.decline` for your own automations and scripts.
- **Events** `seerr_requests_new_request` and `seerr_requests_request_actioned` for your own automations.
- **Instant updates** through Seerr's webhook, with regular checking as a fallback.

## Install

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/AJErazzor/ha-seerr`, type **Integration**.
2. Search HACS for **Seerr Requests**, download it, and restart Home Assistant.
3. **Settings → Devices & services → Add integration → Seerr Requests.**
   - **Seerr URL**: how Home Assistant reaches Seerr, e.g. `http://192.168.1.50:5055`
   - **API key**: Seerr → Settings → General
   - **External URL** (optional): the address you use on your phone, e.g. `https://seerr.example.com`. Used for "Open in Seerr" links and avatars.

The card is installed with the integration — you don't need to add a dashboard resource.

## Set up notifications and instant updates

Open the integration → **Configure**:

- **Send phone notifications to** — pick one or more `notify.mobile_app_…` phones.
- **Check Seerr every** — fallback polling interval (default 60 seconds).

The options screen also shows your **webhook URL**. In Seerr go to **Settings → Notifications → Webhook**, turn it on, paste that URL, tick *Request Pending Approval* (and any others you like), and save. New requests then show up in Home Assistant within a second or two. The webhook only accepts calls from your local network, so use Home Assistant's local address.

> Seerr has a single webhook. If you also use Home Assistant's built-in Seerr integration, it uses the same webhook slot — use one or the other for the webhook.

On first setup, requests already waiting are **not** sent as notifications (so you don't get a flood); only new ones are.

## The card

Add a card → search **Seerr Requests**. Everything can be set in the visual editor, or in YAML:

```yaml
type: custom:seerr-requests-card
entity: sensor.seerr_pending_requests
title: Seerr requests
show_pending: true    # "Waiting for approval" section
show_approved: true   # "Approved · on its way" section
# approved_entity: sensor.seerr_approved_requests   # found automatically
show_fanart: true     # fanart background; false = compact rows
show_summary: true    # plot summary, 3 lines with "more"
show_links: true      # TMDB / IMDb / TVDB / Open in Seerr
max_items: 0          # 0 = show all
```

Tap the "2 hours ago" time to see the exact date and time.

## Actions and events

```yaml
action: seerr_requests.approve
data:
  request_id: 42
```

`seerr_requests_new_request` fires once per new request with the same fields as the sensor's `requests` list. `seerr_requests_request_actioned` fires after an approve or decline with `request_id`, `action`, `title` and `source` (`service` or `notification`).

## Troubleshooting

- **Cannot connect** — check Home Assistant can reach the Seerr URL (try it in a browser on the same network).
- **No notifications** — check the phone is selected under Configure, and that the companion app is allowed to show notifications.
- **Card not found after updating** — refresh the browser (or clear the app's frontend cache).
