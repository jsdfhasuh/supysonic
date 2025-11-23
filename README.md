# Supysonic
# ===========

Supysonic 是基于 Flask 的音乐流媒体服务器,脱胎于[spl0k/supysonic](https://github.com/spl0k/supysonic)。

## 项目支持以下功能:
* 浏览 (通过文件夹或标签)
* 流式播放各种音频文件格式
* 转码
* 用户或随机播放列表
* 封面图片
* 收藏曲目/专辑和评分
* [Last.fm][lastfm] scrobbling 
* [ListenBrainz][listenbrainz] scrobbling
* Jukebox 模式
* 从 Spotify,lastfm等渠道 获取缺少的艺术家封面和专辑封面 (NEW) (保证每一张专辑和艺术家都有封面)
* 从 Spotify，lastfm等渠道 获取缺少的专辑的年份 (NEW) 
* 通过 localnfo 获取艺术家信息和专辑信息并组织专辑 (NEW) (个性化编辑艺术家信息和专辑信息，保证媒体库的整洁)
* WEB端改变并组织艺术家
* 添加一些新的 API (NEW)

## 待实现功能:
* WEB端对音乐库的管理
* WEB端分享页面的实现
* 专属播放软件 (PC端/移动端)


## 快速开始
* 当前项目建议通过 Docker 进行部署
* cd supysonic  （进入到项目地址）
* 改名config.sample 为 supysonic.conf，并填入到自己的配置
* docker build -t supysonic .
 挂载音乐文件夹运行容器
 docker run -d -p 4040:4040 -v /path/to/your/music:/music -v /path/to/your/config/supysonic.conf:/app/supysonic.conf supysonic
 

## NFO 文件格式如下

1. nfo 文件必须命名为 album.nfo 并放置在曲目文件夹中
2. nfo 文件必须是 xml 格式
3. nfo 文件必须包含以下标签:
   - `<album>`: 专辑信息的根元素。
   - `<track>`: 每个曲目都应包含在此标签中。
   - `<lock_data>`: 布尔值,表示数据是否被锁定(可选)。
   每个 `<track>` 元素中必须包含以下标签:
    - `<title>`: 曲目标题。
    - `<cdnum>`: CD 编号(如适用),必须是整数。
    - `<position>`: 曲目在 CD 中的位置。
4. 以下标签为可选但建议添加:
   - `<artist>`: 曲目艺术家。
   - `<albumartist>`: 专辑艺术家(可选)。
   - `<year>`: 专辑年份(可选)。
sample_album.nfo:
```xml
<?xml version="1.0" encoding="utf-8"?>
<album>
  <lock_data>False</lock_data>
  <track>
    <title>Many Shades Of Black</title>
    <cdnum>1</cdnum>
    <position>10</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Best For Last</title>
    <cdnum>1</cdnum>
    <position>02</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Chasing Pavements</title>
    <cdnum>1</cdnum>
    <position>03</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Cold Shoulder</title>
    <cdnum>1</cdnum>
    <position>04</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Crazy For You</title>
    <cdnum>1</cdnum>
    <position>05</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Melt My Heart To Stone</title>
    <cdnum>1</cdnum>
    <position>06</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>First Love</title>
    <cdnum>1</cdnum>
    <position>07</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Right As Rain</title>
    <cdnum>1</cdnum>
    <position>08</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Make You Feel My Love</title>
    <cdnum>1</cdnum>
    <position>09</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>My Same</title>
    <cdnum>1</cdnum>
    <position>10</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Tired</title>
    <cdnum>1</cdnum>
    <position>11</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Hometown Glory</title>
    <cdnum>1</cdnum>
    <position>12</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Chasing Pavements</title>
    <cdnum>1</cdnum>
    <position>01</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Melt My Heart To Stone</title>
    <cdnum>1</cdnum>
    <position>02</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>That's It, I Quit, I'm Moving On</title>
    <cdnum>1</cdnum>
    <position>03</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Crazy For You</title>
    <cdnum>1</cdnum>
    <position>04</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Right As Rain</title>
    <cdnum>1</cdnum>
    <position>05</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>My Same</title>
    <cdnum>1</cdnum>
    <position>06</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Make You Feel My Love</title>
    <cdnum>1</cdnum>
    <position>07</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Daydreamer</title>
    <cdnum>1</cdnum>
    <position>08</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Hometown Glory</title>
    <cdnum>1</cdnum>
    <position>09</position>
    <artist>Adele</artist>
  </track>
  <track>
    <title>Daydreamer</title>
    <cdnum>1</cdnum>
    <position>01</position>
    <artist>Adele</artist>
  </track>
  <artist>Adele</artist>
  <albumartist>Adele</albumartist>
</album>
```