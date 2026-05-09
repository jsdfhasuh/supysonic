import logging

import requests

logger = logging.getLogger(__name__)


class DiscogsClient:
    def __init__(self, config, request_get=None):
        self.config = config or {}
        self.request_get = request_get or requests.get

    def is_enabled(self):
        enabled = self.config.get("enabled", False)
        if isinstance(enabled, str):
            enabled = enabled.lower() in ("1", "yes", "true", "on")
        return bool(enabled and self.config.get("token"))

    def search_album(self, artist_name, album_name):
        if not self.is_enabled():
            return {}

        api_url = str(self.config.get("api_url") or "https://api.discogs.com").rstrip("/")
        headers = {
            "Authorization": f"Discogs token={self.config.get('token')}",
            "User-Agent": str(self.config.get("user_agent") or "Supysonic/1.0"),
        }
        params = {
            "artist": artist_name,
            "release_title": album_name,
            "type": "release",
            "per_page": 1,
        }
        try:
            response = self.request_get(
                f"{api_url}/database/search",
                headers=headers,
                params=params,
                timeout=10,
            )
        except requests.exceptions.RequestException as exc:
            logger.warning("Discogs album search failed: %s", exc)
            return {}

        if response.status_code == 429:
            logger.warning("Discogs album search rate limited")
            return {}
        if response.status_code != 200:
            logger.warning("Discogs album search returned HTTP %s", response.status_code)
            return {}

        data = response.json()
        results = data.get("results") or []
        return results[0] if results else {}
