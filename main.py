"""
YouTube Music Downloader
"""

import hashlib
import itertools
import json
import logging
import re
import sys
import time
import subprocess

from http.cookiejar import MozillaCookieJar
from pathlib import Path

from requests import get, post, Session, utils
from requests.models import HTTPError

YTMUSIC_URL = "https://music.youtube.com"
INNERTUBE_API_KEY = "AIzaSyC9XL3ZjWddXya6X74dJoCTL-WEYFDNX30"

INNERTUBE_CLIENT_NAME = "WEB_REMIX"
INNERTUBE_CLIENT_VERSION = "0.1"

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)\
    Chrome/91.0.4472.101 Safari/537.36"

class Source:
    """
        signature_timestamp
        yt_player_function_transform
        yt_player_object_transform
    """
    def __init__(self, video_id):
        log = logging.getLogger("Source")
        url = f"{YTMUSIC_URL}/watch?v={video_id}"
        headers = {
            "origin": YTMUSIC_URL,
            "user-agent": USER_AGENT,
        }
        log.info(" Downloading Response...")
        response = self.__get_response(log, url, headers)
        log.info(" Response Downloaded")
        js_url = self.__get_js_url(response)
        yt_player = self.__get_yt_player(js_url)
        self.signature_timestamp = self.__get_signature_timestamp(yt_player)
        yt_player_function_name = self.__get_yt_player_function_name(yt_player)
        yt_player_function = self.__get_yt_player_function(yt_player, yt_player_function_name)
        yt_player_object_name = self.__get_yt_player_object_name(yt_player_function)
        yt_player_object = self.__get_yt_player_object(yt_player, yt_player_object_name)
        self.yt_player_function_transform =\
            self.__get_yt_player_function_transform(yt_player_function)
        self.yt_player_object_transform = self.__get_yt_player_object_transform(yt_player_object)

    @staticmethod
    def __get_response(log, url, headers):
        try:
            response = get(
                url=url,
                headers=headers,
                timeout=4
            ).content.decode("UTF-8")
        except HTTPError:
            log.error(" Response Downloading Failed")
            sys.exit()
        return response

    @staticmethod
    def __get_js_url(response):
        pattern = r"(/s/player/[\w\d]+/[\w\d_/.]+/base\.js)"
        js_url = re.compile(pattern).search(response)
        js_url = YTMUSIC_URL + js_url.group(0)
        return js_url

    @staticmethod
    def __get_yt_player(js_url):
        try:
            yt_player = get(url=js_url, timeout=4)
        except HTTPError:
            sys.exit()
        yt_player = yt_player.content.decode("UTF-8")
        return yt_player

    @staticmethod
    def __get_signature_timestamp(yt_player):
        pattern = r"signatureTimestamp[:=](\d+)"
        signature_timestamp = re.compile(pattern).search(yt_player).group(1)
        return signature_timestamp

    @staticmethod
    def __get_yt_player_function_name(yt_player):
        pattern =\
            r'(?P<sig>[a-zA-Z0-9$]+)\s*=\s*function\(\s*a\s*\)\s*{\s*a\s*=\s*a\.split\(\s*""\s*\)'
        yt_player_function_name = re.compile(pattern).search(yt_player).group(1)
        return yt_player_function_name

    @staticmethod
    def __get_yt_player_function(yt_player, yt_player_function_name):
        pattern = r"%s=function\(\w\){[a-z=\.\(\"\)]*;(.*);(?:.+)};" % yt_player_function_name
        yt_player_function = re.compile(pattern).search(yt_player).group(0)
        return yt_player_function

    @staticmethod
    def __get_yt_player_function_transform(yt_player_function):
        pattern = r"{\w=\w\.split\(\"\"\);(.*);return\s\w\.join\(\"\"\)};"
        yt_player_function_transform = re.compile(pattern).search(yt_player_function).group(1)\
            .split(";")
        return yt_player_function_transform

    @staticmethod
    def __get_yt_player_object_name(yt_player_function):
        pattern = r"\w+\.\w+\(\w\,\w\)"
        yt_player_object_name = re.compile(pattern).search(yt_player_function).group().split(".")\
            [0]
        return yt_player_object_name

    @staticmethod
    def __get_yt_player_object(yt_player, yt_player_object_name):
        pattern = r"var\s*%s={([\S\s]*?)};" % yt_player_object_name
        yt_player_object = re.compile(pattern).search(yt_player).group(0)
        return yt_player_object

    @staticmethod
    def __get_yt_player_object_transform(yt_player_object):
        pattern = r"{([\S\s]*?)};"
        yt_player_object_transform = re.compile(pattern).search(yt_player_object).group(1)\
            .replace("\n", " ").split(", ")
        return yt_player_object_transform

class Player:
    """
        download_url
        thumbnail_url
    """
    def __init__(self, video_id, source, itag):
        log = logging.getLogger("Player")
        session = Session()
        if itag == 141:
            cookies_txt = Path("./cookies.txt")
            if cookies_txt.is_file():
                with open("cookies.txt", "r") as file:
                    data = file.read().replace("#HttpOnly_", "")
                with open("cookies.txt", "w") as file:
                    file.write(data)
                session.cookies = MozillaCookieJar("cookies.txt")
                session.cookies.load(ignore_discard=True, ignore_expires=True)
            else:
                logging.error("Provide cookies.txt")
                sys.exit()
        url = f"{YTMUSIC_URL}/youtubei/v1/player?key={INNERTUBE_API_KEY}"
        data = {
            "videoId": video_id,
            "context": {
                "client": {
                    "clientName": INNERTUBE_CLIENT_NAME,
                    "clientVersion": INNERTUBE_CLIENT_VERSION,
                }
            },
            "playbackContext": {
                "contentPlaybackContext": {
                    "signatureTimestamp": source.signature_timestamp,
                }
            }
        }
        authorization = self.__get_authorization(session, itag)
        headers = {
            "origin": YTMUSIC_URL,
            "user-agent": USER_AGENT,
            "authorization": authorization
        }
        log.info(" Downloading Response...")
        response = self.__get_response(log, session, url, data, headers)
        log.info(" Response Downloaded")
        if itag == 141:
            session.cookies.save(ignore_discard=True, ignore_expires=True)
        session.close()
        log.info(" Generating Download & Thumbnail URL...")
        signature_cipher = self.__get_signature_cipher(response, itag)
        signature_cipher_s = signature_cipher["s"]
        signature_cipher_url = signature_cipher["url"]
        transform_map = self.__get_transform_map(source.yt_player_object_transform)
        sig = self.__get_sig(source.yt_player_function_transform, signature_cipher_s,
            transform_map)
        self.download_url = self.__get_download_url(signature_cipher_url, sig)
        log.info(" Download URL Generated")
        self.thumbnail_url = self.__get_thumbnail_url(response)
        log.info(" Thumbnail URL Generated")

    @staticmethod
    def __get_authorization(session, itag):
        if itag == 141:
            current_time = str(int(time.time()))
            sapisid = session.cookies.__dict__["_cookies"][".youtube.com"]["/"]["SAPISID"].value
            sapisidhash = hashlib.sha1(" ".join([current_time, sapisid, YTMUSIC_URL]).encode())\
                .hexdigest()
            authorization = f"SAPISIDHASH {current_time}_{sapisidhash}"
            return authorization
        return None

    @staticmethod
    def __get_response(log, session, url, data, headers):
        try:
            response = session.post(
                url=url,
                data=json.dumps(data),
                headers=headers,
                timeout=4
            ).json()
        except HTTPError:
            log.error(" Response Downloading Failed")
            sys.exit()
        return response

    @staticmethod
    def __get_signature_cipher(response, itag):
        signature_cipher_s_pattern = r"s=(.*)&sp=sig&"
        signature_cipher_url_pattern = r"&sp=sig&url=(.*)"
        adaptive_formats = response["streamingData"]["adaptiveFormats"]
        for adaptive_format in adaptive_formats:
            if adaptive_format["itag"] == itag:
                signature_cipher = adaptive_format["signatureCipher"]
                signature_cipher_s = re.compile(signature_cipher_s_pattern)\
                    .search(signature_cipher)
                signature_cipher_s = utils.unquote(signature_cipher_s.group(1))
                signature_cipher_url = re.compile(signature_cipher_url_pattern)\
                    .search(signature_cipher)
                signature_cipher_url = utils.unquote(signature_cipher_url.group(1))
        if not signature_cipher_s or not signature_cipher_url:
            sys.exit()
        signature_cipher = {"s": signature_cipher_s, "url": signature_cipher_url}
        return signature_cipher

    @staticmethod
    def __reverse(_a, _):
        return _a[::-1]

    @staticmethod
    def __splice(_a, _b):
        return _a[_b:]

    @staticmethod
    def __swap(_a, _b):
        _r = _b % len(_a)
        return list(itertools.chain([_a[_r]], _a[1:_r], [_a[0]], _a[_r+1:]))

    def __map_function(self, yt_player_object):
        pattern_function_list = (
            (r"{\w\.reverse\(\)}", self.__reverse),
            (r"{\w\.splice\(0,\w\)}", self.__splice),
            (r"{var\s\w=\w\[0\];\w\[0\]=\w\[\w%\w.length\];\w\[\w\]=\w}", self.__swap),
            (r"{var\s\w=\w\[0\];\w\[0\]=\w\[\w%\w.length\];\w\[\w\%\w.length\]=\w}", self.__swap)
        )
        for pattern, function in pattern_function_list:
            if re.compile(pattern).search(yt_player_object):
                return function
        return None

    def __get_transform_map(self, yt_player_object_transform):
        transform_map = {}
        for i in yt_player_object_transform:
            name, yt_player_object = i.split(":", 1)
            transform_map[name] = self.__map_function(yt_player_object)
        return transform_map

    @staticmethod
    def __parse_function(function):
        patterns = [
            r"\w+\.(\w+)\(\w,(\d+)\)",
            r"\w+\[(\"\w+\")\]\(\w,(\d+)\)"
        ]
        for pattern in patterns:
            regex = re.compile(pattern).search(function)
            if regex:
                name, arg = regex.groups()
                return name, int(arg)
        return None

    def __get_sig(self, yt_player_function_transform, signature_cipher_s,\
            transform_map):
        sig = list(signature_cipher_s)
        for function in yt_player_function_transform:
            name, arg = self.__parse_function(function)
            sig = transform_map[name](sig, arg)
        sig = "".join(sig)
        return sig

    @staticmethod
    def __get_download_url(signature_cipher_url, sig):
        download_url = f"{signature_cipher_url}&sig={sig}"
        return download_url

    @staticmethod
    def __get_thumbnail_url(response):
        thumbnail_url = response["videoDetails"]["thumbnail"]["thumbnails"][0]\
            ["url"].split("=")[0]
        return thumbnail_url

class Next:
    """
        title
        artist_name
        album_name
        album_id
        year
    """
    def __init__(self, video_id):
        log = logging.getLogger("Next")
        url = f"{YTMUSIC_URL}/youtubei/v1/next?key={INNERTUBE_API_KEY}"
        data = {
            "videoId": video_id,
            "context": {
                "client": {
                    "clientName": INNERTUBE_CLIENT_NAME,
                    "clientVersion": INNERTUBE_CLIENT_VERSION,
                }
            }
        }
        headers = {
            "origin": YTMUSIC_URL,
        }
        log.info(" Downloading Response...")
        response = self.__get_response(log, url, data, headers)
        log.info(" Response Downloaded")
        playlist_panel_video_renderer = response["contents"]\
            ["singleColumnMusicWatchNextResultsRenderer"]["tabbedRenderer"]\
                ["watchNextTabbedResultsRenderer"]["tabs"][0]["tabRenderer"]["content"]\
                    ["musicQueueRenderer"]["content"]["playlistPanelRenderer"]["contents"][0]\
                        ["playlistPanelVideoRenderer"]
        self.title = self.__get_title(playlist_panel_video_renderer)
        self.artist = self.__get_artist(playlist_panel_video_renderer)
        album = self.__get_album(playlist_panel_video_renderer)
        self.album_name = album["name"]
        self.album_id = album["id"]
        self.year = self.__get_year(playlist_panel_video_renderer)

    @staticmethod
    def __get_response(log, url, data, headers):
        try:
            response = post(
                url=url,
                data=json.dumps(data),
                headers=headers,
                timeout=4
            ).json()
        except HTTPError:
            log.error(" Response Downloading Failed")
            sys.exit()
        return response

    @staticmethod
    def __get_title(playlist_panel_video_renderer):
        title = playlist_panel_video_renderer["title"]["runs"][0]["text"]
        return title

    @staticmethod
    def __get_artist(playlist_panel_video_renderer):
        runs = playlist_panel_video_renderer["longBylineText"]["runs"]
        artist = []
        j = 0
        for i in range(0, len(runs) - 4, 2):
            artist.append(runs[i]["text"])
            j = j + 1
        return artist

    @staticmethod
    def __get_album(playlist_panel_video_renderer):
        name = playlist_panel_video_renderer["longBylineText"]["runs"][-3]["text"]
        _id = playlist_panel_video_renderer["longBylineText"]["runs"][-3]["navigationEndpoint"]\
            ["browseEndpoint"]["browseId"]
        album = {"name": name, "id": _id}
        return album

    @staticmethod
    def __get_year(playlist_panel_video_renderer):
        year = playlist_panel_video_renderer["longBylineText"]["runs"][-1]["text"]
        return year

class Browse:
    """
        album_track_index
        album_track_count
    """
    def __init__(self, _next):
        url = f"{YTMUSIC_URL}/youtubei/v1/browse?key={INNERTUBE_API_KEY}"
        headers = {
            "origin": YTMUSIC_URL,
        }
        data = {
            "browseId": "",
            "context": {
                "client": {
                    "clientName": INNERTUBE_CLIENT_NAME,
                    "clientVersion": INNERTUBE_CLIENT_VERSION,
                }
            }
        }
        album_track = self.__get_album_track(_next.album_id, _next.title, url, data, headers)
        self.album_track_index = album_track["index"]
        self.album_track_count = album_track["count"]

    @staticmethod
    def __get_response(log, _id, url, data, headers):
        data.update({"browseId": _id})
        try:
            response = post(
                url=url,
                data=json.dumps(data),
                headers=headers,
                timeout=4
            ).json()
        except HTTPError:
            log.error(" Response Downloading Failed")
            sys.exit()
        return response

    def __get_album_track(self, album_id, title, url, data, headers):
        log = logging.getLogger("Browse Album Track")
        log.info(" Downloading Response...")
        response = self.__get_response(log, album_id, url, data, headers)
        log.info(" Response Downloaded")
        mutations = response["frameworkUpdates"]["entityBatchUpdate"]["mutations"]
        for i in mutations:
            if "musicTrack" in i["payload"]:
                if i["payload"]["musicTrack"]["title"] == title:
                    index = i["payload"]["musicTrack"]["albumTrackIndex"]
        count = mutations[-1]["payload"]["musicAlbumRelease"]["trackCount"]
        album_track = {
            "index": index,
            "count": count,
        }
        return album_track

def download(player, _next, browse=None):
    """Download"""
    title = f"{_next.title}".replace("/", "-")
    if len(_next.artist) == 1:
        artist = _next.artist[0]
    else:
        artist = ", ".join(_next.artist[:-1]) + " & " + _next.artist[-1]
    logging.info(" Downloading Track...")
    # response = get(player.download_url)
    # open(f"{title}", "wb").write(response.content)
    Path(f"{_next.album_name}").mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-i", f"{player.download_url}",
        "-i", f"{player.thumbnail_url}",
        "-map", "0", "-map", "1",
        "-disposition:1", "attached_pic",
        "-metadata", f"title={_next.title}",
        "-metadata", f"artist={artist}",
        "-metadata", f"album={_next.album_name}",
        "-metadata", f"date={_next.year}",
        "-metadata:g", f'encoder_tool=" "',
        # "-metadata", f"track={browse.album_track_index}/{browse.album_track_count}",
        "-codec", "copy", "-f", "mp4",
        f"{_next.album_name}/{title}.m4a"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    logging.info(" Track Downloaded")

def main(video_id, itag):
    """Main"""
    if itag not in (140, 141):
        sys.exit()
    source = Source(video_id)
    player = Player(video_id, source, itag)
    _next = Next(video_id)
    # browse = Browse(_next)
    # download(player, _next, browse)
    download(player, _next)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(sys.argv[-2], int(sys.argv[-1]))
