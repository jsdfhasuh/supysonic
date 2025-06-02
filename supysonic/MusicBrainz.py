import requests

import requests


def get_musicbrainz_album_image_info(mb_album_id: str) -> dict:
    url = f"https://coverartarchive.org/release/{mb_album_id}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"MusicBrainz cover download failed: {e}")
    return None
