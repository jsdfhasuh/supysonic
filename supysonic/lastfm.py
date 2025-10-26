# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2013-2022 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

import hashlib
import logging
import requests
from bs4 import BeautifulSoup
import time
import re

logger = logging.getLogger(__name__)


class LastFm:
    def __init__(self, config, user):
        if config["api_key"] is not None and config["secret"] is not None:
            self.__api_key = config["api_key"]
            self.__api_secret = config["secret"].encode("utf-8")
            self.__enabled = True
            self.__find_json = {}
        else:
            self.__enabled = False
        self.__user = user

    def link_account(self, token):
        if not self.__enabled:
            return False, "No API key set"

        res = self.__api_request(False, method="auth.getSession", token=token)
        if not res:
            return False, "Error connecting to LastFM"
        elif "error" in res:
            return False, f"Error {res['error']}: {res['message']}"
        else:
            self.__user.lastfm_session = res["session"]["key"]
            self.__user.lastfm_status = True
            self.__user.save()
            return True, "OK"

    def unlink_account(self):
        self.__user.lastfm_session = None
        self.__user.lastfm_status = True
        self.__user.save()

    def now_playing(self, track):
        if not self.__enabled:
            return

        self.__api_request(
            True,
            method="track.updateNowPlaying",
            artist=track.album.artist.get_artist_name(),
            track=track.title,
            album=track.album.name,
            trackNumber=track.number,
            duration=track.duration,
        )

    def scrobble(self, track, ts):
        if not self.__enabled:
            return

        self.__api_request(
            True,
            method="track.scrobble",
            artist=track.album.artist.get_artist_name(),
            track=track.title,
            album=track.album.name,
            timestamp=ts,
            trackNumber=track.number,
            duration=track.duration,
        )

    def get_artistinfo(self, name, lang='en'):
        if not self.__enabled:
            return
        if 'artist_{name}' in self.__find_json:
            return self.__find_json[f'artist_{name}']
        result = self.__api_request(
            False,
            method="artist.getinfo",
            artist=name,
            lang=lang,
            autocorrect=1,
        )
        self.__find_json[f'artist_{name}'] = result
        return result

    def get_albuminfo(self, artist_name, album_name, lang='en'):
        if not self.__enabled:
            return
        album_name = album_name.replace("[DISC 1]", "")
        # 然后处理各种格式的光盘标识
        album_name = re.sub(
            r"\s*\[DISC\s*\d*\]\s*", "", album_name, flags=re.IGNORECASE
        )
        # 匹配 "Disc N" 或 "Disk N" 格式
        album_name = re.sub(
            r"\s*\b(?:Disc|Disk)\s*\d+\b\s*", "", album_name, flags=re.IGNORECASE
        )
        # 处理其他可能的变体，如 "CD N"
        album_name = re.sub(r"\s*\bCD\s*\d+\b\s*", "", album_name, flags=re.IGNORECASE)
        if f'album_{artist_name}_{album_name}' in self.__find_json:
            return self.__find_json[f'album_{artist_name}_{album_name}']
        result = self.__api_request(
            False,
            method="album.getInfo",
            artist=artist_name,
            album=album_name,
            lang=lang,
            autocorrect=1,
        )
        self.__find_json[f'album_{artist_name}_{album_name}'] = result
        if 'error' in result:
            logger.warning(
                f"Error fetching album info for {artist_name} - {album_name}: {result['message']}"
            )
            return {}
        return result

    def get_lastfm_wiki(self, url, timeout=30, retry_delay=1):
        """
        Scrape Last.fm wiki page content for an artist

        Args:
            url: URL of the Last.fm wiki page
            timeout: Request timeout in seconds (default: 30)
            retry_delay: Delay between retries in seconds (default: 1)

        Returns:
            String containing wiki content or error dictionary
        """
        try_count = 3
        start_time = time.time()
        while try_count > 0:
            # 检查总体超时
            if time.time() - start_time > timeout * 2:  # 总超时时间为请求超时的2倍
                logger.warning(f"Total operation timeout exceeded for URL: {url}")
                return ""
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                # 添加请求超时
                response = requests.get(url, headers=headers, timeout=timeout)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                # 通过类名查找元素
                wiki_content = soup.find('div', class_='wiki-content')
                if wiki_content:
                    # 获取纯文本，去除所有HTML标签
                    description = wiki_content.get_text(strip=True)
                    # 检查内容长度，避免返回空内容
                    if description and len(description.strip()) > 0:
                        return description
                    else:
                        logger.warning(f"Empty wiki content found for URL: {url}")
                        return ""
                else:
                    logger.warning(f"No wiki-content element found for URL: {url}")
                    return ""
            except requests.exceptions.Timeout:
                try_count -= 1
                logger.warning(
                    f"Request timeout for URL: {url}, retries left: {try_count}"
                )
                if try_count == 0:
                    return ""
            except requests.exceptions.RequestException as e:
                try_count -= 1
                logger.warning(
                    f"Request error for URL: {url}, error: {str(e)}, retries left: {try_count}"
                )
                if try_count == 0:
                    return ""
            except Exception as e:
                try_count -= 1
                logger.warning(
                    f"Parsing error for URL: {url}, error: {str(e)}, retries left: {try_count}"
                )
                if try_count == 0:
                    return {'error': f'Error parsing page: {str(e)}'}
            # 如果还有重试机会，等待一段时间后重试
            if try_count > 0:
                logger.info(f"Waiting {retry_delay} seconds before retry...")
                time.sleep(retry_delay)
                retry_delay *= 1.5  # 递增重试延迟时间
        return ""

    def get_wiki_year(self, wiki):
        """
        从维基百科内容中提取年份信息

        Args:
            wiki: 维基百科内容字符串

        Returns:
            提取的年份字符串，如果未找到则返回 None
        """
        if not wiki:
            return None
        # 使用正则表达式匹配年份格式 released on May 31, 2023
        match = re.search(r'released on [A-Za-z]+\s+\d{1,2},\s*(\d{4})', wiki)
        if match:
            return match.group(1)
        return None

    def __api_request(self, write, **kwargs):
        if not self.__enabled:
            return

        if write:
            if not self.__user.lastfm_session or not self.__user.lastfm_status:
                return
            kwargs["sk"] = self.__user.lastfm_session

        kwargs["api_key"] = self.__api_key

        sig_str = b""
        for k, v in sorted(kwargs.items()):
            k = k.encode("utf-8")
            v = v.encode("utf-8") if isinstance(v, str) else str(v).encode("utf-8")
            sig_str += k + v
        sig = hashlib.md5(sig_str + self.__api_secret).hexdigest()

        kwargs["api_sig"] = sig
        kwargs["format"] = "json"

        try:
            if write:
                r = requests.post(
                    "https://ws.audioscrobbler.com/2.0/", data=kwargs, timeout=5
                )
            else:
                r = requests.get(
                    "https://ws.audioscrobbler.com/2.0/", params=kwargs, timeout=5
                )
        except requests.exceptions.RequestException as e:
            logger.warning("Error while connecting to LastFM: " + str(e))
            return None

        json = r.json()
        if "error" in json:
            if json["error"] in (9, "9"):
                self.__user.lastfm_status = False
                self.__user.save()
            logger.warning("LastFM error %i: %s", json["error"], json["message"])

        return json
