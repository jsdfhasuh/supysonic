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
    return {}


def get_musicbrainz_album(mb_album_id: str) -> dict:
    """
    通过 MusicBrainz 的 MBID 获取专辑详细信息
    """
    url = f"https://musicbrainz.org/ws/2/release/{mb_album_id}?fmt=json&inc=artists+labels+recordings+release-groups"
    try:
        resp = requests.get(
            url, timeout=10, headers={"User-Agent": "Supysonic/1.0 (your@email.com)"}
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"MusicBrainz album info fetch failed: {e}")
    return {}


def search_musicbrainz_album(artist_name: str, album_name: str) -> dict:
    """
    通过艺术家名和专辑名搜索 MusicBrainz，获取专辑信息
    """
    query = f'artist:"{artist_name}" AND release:"{album_name}"'
    url = f'https://musicbrainz.org/ws/2/release/?query={requests.utils.quote(query)}&fmt=json'
    try:
        resp = requests.get(
            url, timeout=10, headers={"User-Agent": "Supysonic/1.0 (your@email.com)"}
        )
        if resp.status_code == 200:
            data = resp.json()
            # 通常第一个结果就是最相关的
            if data.get("releases"):
                return data["releases"][0]
    except Exception as e:
        print(f"MusicBrainz album search failed: {e}")
    return {}


if __name__ == "__main__":
    # Example usage
    # Replace with a valid MusicBrainz MBID for testing
    # mbid = "02ab59c9-f687-43da-9fa4-dda73c2f2d38"
    # album_info = get_musicbrainz_album(mbid)
    artist_name = 'BOL4'
    album_name = '사춘기집Ⅱ 꽃 본 나비'
    result = search_musicbrainz_album(artist_name, album_name)
    pass
