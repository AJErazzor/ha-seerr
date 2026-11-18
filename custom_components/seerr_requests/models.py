"""Turn raw Seerr API data into the flat request records the card and
notifications use. Kept free of Home Assistant imports so it is easy to test."""

from __future__ import annotations

from typing import Any

TMDB_IMAGE = "https://image.tmdb.org/t/p"


def _image(path: str | None, size: str) -> str | None:
    if not path:
        return None
    if path.startswith("http"):
        return path
    return f"{TMDB_IMAGE}/{size}{path}"


def _absolute(base: str, path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith(("http://", "https://")):
        return path
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def season_text(seasons: list[int]) -> str:
    """'Season 2', 'Seasons 1–3' or 'Seasons 1, 3, 5'."""
    if not seasons:
        return ""
    seasons = sorted(set(seasons))
    if len(seasons) == 1:
        return f"Season {seasons[0]}"
    if seasons == list(range(seasons[0], seasons[-1] + 1)):
        return f"Seasons {seasons[0]}–{seasons[-1]}"
    return "Seasons " + ", ".join(str(s) for s in seasons)


def build_request(
    raw: dict[str, Any], details: dict[str, Any], external_url: str
) -> dict[str, Any]:
    """Flatten one Seerr request plus its TMDB details."""
    media = raw.get("media") or {}
    media_type = raw.get("type") or media.get("mediaType") or "movie"
    tmdb_id = media.get("tmdbId")

    title = details.get("title") or details.get("name") or f"TMDB #{tmdb_id}"
    date = details.get("releaseDate") or details.get("firstAirDate") or ""
    year = date[:4] if len(date) >= 4 else None

    external_ids = details.get("externalIds") or {}
    imdb_id = external_ids.get("imdbId") or media.get("imdbId")
    tvdb_id = external_ids.get("tvdbId") or media.get("tvdbId")

    user = raw.get("requestedBy") or {}
    requested_by = (
        user.get("displayName")
        or user.get("username")
        or user.get("jellyfinUsername")
        or user.get("plexUsername")
        or user.get("email")
        or "Unknown"
    )

    seasons = sorted(
        s["seasonNumber"]
        for s in raw.get("seasons") or []
        if isinstance(s, dict) and s.get("seasonNumber") is not None
    )

    kind = "tv" if media_type == "tv" else "movie"
    return {
        "id": raw.get("id"),
        "type": kind,
        "title": title,
        "year": year,
        "overview": details.get("overview") or "",
        "poster": _image(details.get("posterPath"), "w342"),
        "backdrop": _image(details.get("backdropPath"), "w1280"),
        "requested_by": requested_by,
        "requested_by_avatar": _absolute(external_url, user.get("avatar")),
        "requested_at": raw.get("createdAt"),
        "is4k": bool(raw.get("is4k")),
        "seasons": seasons if kind == "tv" else [],
        "tmdb_id": tmdb_id,
        "tmdb_url": f"https://www.themoviedb.org/{kind}/{tmdb_id}" if tmdb_id else None,
        "imdb_url": f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None,
        "tvdb_url": (
            f"https://thetvdb.com/dereferrer/series/{tvdb_id}"
            if tvdb_id and kind == "tv"
            else None
        ),
        "seerr_url": f"{external_url.rstrip('/')}/{kind}/{tmdb_id}" if tmdb_id else None,
    }
