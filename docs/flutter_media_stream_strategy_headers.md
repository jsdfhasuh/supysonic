# Flutter 媒体推流策略头对接文档

本文档面向 Flutter 客户端工程师，说明 Emosonic Server 在 `/rest/stream.view` 推流响应中返回的媒体信息与播放策略响应头。

这是一份接口契约文档。当前服务端已在 `/rest/stream.view` 和 `/rest/stream` 上实现 `EmoSonic-*` 响应头、`variant=flac_no_picture`、HEAD 探测和静态文件 range 支持；客户端可以按本文档接入播放链路、缓存策略和 `just_audio`。

本文档里的 `EmoSonic-*` 都是服务端返回的响应头。客户端请求参数只表达期望，例如 `format=mp3`、`maxBitRate=320`、`variant=flac_no_picture`；客户端最终拿到的实际媒体流以响应头里的 `Output-*` 和 `EmoSonic-Stream-Variant` 为准。

## 1. 背景

部分高规格音频文件本身可以正常解码，但因为容器内带有大尺寸内嵌封面或附加流，可能导致 Windows / Android 播放后端表现不稳定。

典型场景：

```text
96kHz / 24-bit FLAC + PNG attached picture
```

客户端真正需要的不是一段展示文案，而是播放策略信号：

- 当前文件是否有 attached picture。
- 是否存在服务端无损清理版。
- 是否应该优先请求兼容 variant。
- 原始文件和兼容 variant 的缓存 key 是否能区分。

## 2. 播放入口

当前 Subsonic 推流入口：

```http
GET /rest/stream.view?id=<trackId>&u=<user>&p=<password>&c=<client>
```

等价路径：

```http
GET /rest/stream?id=<trackId>&u=<user>&p=<password>&c=<client>
```

推荐客户端在创建 `AudioSource` 前先做一次轻量探测：

```http
HEAD /rest/stream.view?id=<trackId>&u=<user>&p=<password>&c=<client>
```

如果运行环境、服务端或代理对 `HEAD` 支持不好，探测可以退化为 `GET Range: bytes=0-0`：

```http
GET /rest/stream.view?id=<trackId>&u=<user>&p=<password>&c=<client>
Range: bytes=0-0
```

`GET Range: bytes=0-0` 更接近播放器后端的真实播放请求。服务端理想情况下返回 `206 Partial Content` 和完整媒体响应头：

```http
HTTP/1.1 206 Partial Content
Content-Length: 1
Content-Range: bytes 0-0/123456789
Accept-Ranges: bytes
EmoSonic-Output-Content-Length: 123456789
```

注意：`206 Partial Content` 的 `Content-Length` 表示本次响应 body 长度。对于 `Range: bytes=0-0`，它通常是 `1`，不是完整媒体文件大小。客户端要从 `Content-Range: bytes 0-0/<total>` 读取总大小；如果服务端返回 `EmoSonic-Output-Content-Length`，也可以直接使用该值作为当前输出流的完整字节数。

如果代理忽略 range 返回 `200 OK`，客户端仍可读取响应头后立即关闭连接，不能把这次探测当作完整媒体缓存。

如果 `HEAD` 和 `GET Range: bytes=0-0` 都探测失败，客户端默认走原始直推，不要因为探测失败就强制下载清理。后续可以考虑增加 JSON 版 `mediaInfo` 接口，避免 Flutter 播放后端隐藏响应头的问题。

## 3. 响应头契约

HTTP header 名称大小写不敏感。本文档用 `EmoSonic-Source-Attached-Picture-Count` 这类规范写法展示；客户端实现和自动化测试应按大小写不敏感处理，实际读取时可以统一使用 lowercase，例如 `emosonic-source-attached-picture-count`。

### 3.1 Source 媒体基础信息

| Header | 示例 | 说明 |
| --- | --- | --- |
| `EmoSonic-Source-Container` | `flac` | 原始文件容器格式 |
| `EmoSonic-Source-Audio-Codec` | `flac` | 原始音频 codec |
| `EmoSonic-Source-Audio-Sample-Rate` | `96000` | 原始采样率，单位 Hz |
| `EmoSonic-Source-Audio-Bit-Depth` | `24` | 原始位深 |
| `EmoSonic-Source-Audio-Channels` | `2` | 原始声道数 |
| `EmoSonic-Source-Audio-Bitrate` | `2867904` | 原始音频码率，单位 bit/s |
| `EmoSonic-Source-Audio-Duration-Ms` | `180000` | 原始文件时长，单位 ms |

`Source-*` 字段始终描述原始媒体文件。

### 3.2 Output 媒体基础信息

| Header | 示例 | 说明 |
| --- | --- | --- |
| `EmoSonic-Output-Container` | `mp3` | 当前响应实际输出容器 |
| `EmoSonic-Output-Audio-Codec` | `mp3` | 当前响应实际输出 codec |
| `EmoSonic-Output-Audio-Sample-Rate` | `44100` | 当前响应实际输出采样率，未知时省略 |
| `EmoSonic-Output-Audio-Bit-Depth` | `16` | 当前响应实际输出位深，未知时省略 |
| `EmoSonic-Output-Audio-Channels` | `2` | 当前响应实际输出声道数，未知时省略 |
| `EmoSonic-Output-Audio-Bitrate` | `320000` | 当前响应实际输出码率，单位 bit/s |
| `EmoSonic-Output-Audio-Duration-Ms` | `180000` | 当前响应实际输出时长，单位 ms |
| `EmoSonic-Output-Content-Length` | `123456789` | 当前输出流完整字节数，未知时省略 |

`Output-*` 字段描述当前 HTTP 响应真正推给客户端的音频流。

直推原始文件时，`Output-*` 通常与 `Source-*` 一致。请求 `variant=flac_no_picture` 时，`Output-*` 描述清理版 FLAC。发生转码时，`Output-*` 描述转码后的目标格式。

服务端不要猜测无法确定的输出信息。实时转码时如果只能确定格式和目标码率，就只返回 `EmoSonic-Output-Container`、`EmoSonic-Output-Audio-Codec`、`EmoSonic-Output-Audio-Bitrate`、`EmoSonic-Output-Audio-Duration-Ms`；采样率、位深、声道数、完整字节数只有能从转码配置或缓存文件准确确认时才返回。

### 3.3 Source 内嵌封面与附加流信息

| Header | 示例 | 说明 |
| --- | --- | --- |
| `EmoSonic-Source-Stream-Count` | `2` | 原始文件总流数量 |
| `EmoSonic-Source-Audio-Stream-Count` | `1` | 原始文件音频流数量 |
| `EmoSonic-Source-Attached-Picture-Count` | `1` | 原始文件内嵌封面数量 |
| `EmoSonic-Source-Attached-Picture-Codec` | `png` | 第一张原始内嵌封面格式 |
| `EmoSonic-Source-Attached-Picture-Width` | `4000` | 第一张原始内嵌封面宽度 |
| `EmoSonic-Source-Attached-Picture-Height` | `4000` | 第一张原始内嵌封面高度 |

关键字段是：

```text
EmoSonic-Source-Attached-Picture-Count
```

客户端可以用它判断这首歌是否可能不适合直接交给系统播放后端。

### 3.4 Output 附加流信息

| Header | 示例 | 说明 |
| --- | --- | --- |
| `EmoSonic-Output-Stream-Count` | `1` | 当前响应输出总流数量，未知时省略 |
| `EmoSonic-Output-Audio-Stream-Count` | `1` | 当前响应输出音频流数量，未知时省略 |
| `EmoSonic-Output-Attached-Picture-Count` | `0` | 当前响应输出内嵌封面数量，未知时省略 |
| `EmoSonic-Output-Attached-Picture-Codec` | `png` | 当前响应第一张内嵌封面格式，未知或无图时省略 |
| `EmoSonic-Output-Attached-Picture-Width` | `4000` | 当前响应第一张内嵌封面宽度，未知或无图时省略 |
| `EmoSonic-Output-Attached-Picture-Height` | `4000` | 当前响应第一张内嵌封面高度，未知或无图时省略 |

客户端判断当前拿到的流是否适合播放时，优先看 `Output-*`。客户端判断原始文件是否需要兼容处理时，看 `Source-*`。

### 3.5 后端能力信息

| Header | 示例 | 说明 |
| --- | --- | --- |
| `EmoSonic-Sanitized-Available` | `true` | 服务端是否可以为当前 track 提供无损清理 variant |
| `EmoSonic-Transcode-Available` | `true` | 是否存在转码方案 |
| `EmoSonic-Preferred-Compatible-Variant` | `flac_no_picture` | 推荐兼容 variant |
| `EmoSonic-Stream-Variant` | `original` | 当前响应实际返回的 stream variant |

`EmoSonic-Sanitized-Available: true` 表示服务端可以为当前 track 提供 sanitized variant，不要求该 variant 已经预生成或已经在缓存中。服务端可以在客户端真正请求 `variant=flac_no_picture` 时按需生成。

客户端应把 `EmoSonic-Sanitized-Available: true` 理解为“可以尝试请求兼容 variant”，不要理解为“清理版文件已经存在且一定返回成功”。真正请求 variant 后，仍以状态码判断结果：`404` 表示当前 track 没有这个 variant，`500` 表示生成或缓存读取失败。

第一版建议只承诺 FLAC attached picture 清理：

```text
EmoSonic-Preferred-Compatible-Variant: flac_no_picture
```

兼容 variant 统一使用 `variant` 参数：

```http
GET /rest/stream.view?id=<trackId>&variant=flac_no_picture&u=<user>&p=<password>&c=<client>
```

`stripPicture=true` 不作为推荐参数。后续如果增加 `mp3_320`、`aac_256`、`flac_no_picture` 等变体，统一走 `variant=<name>` 更容易扩展。

`variant` 参数不可用时，服务端状态码语义必须稳定：

| 状态码 | 场景 | 客户端建议 |
| --- | --- | --- |
| `400 Bad Request` | `variant` 参数值不受支持，例如 `variant=unknown` | 移除该参数，按原始流或已知 variant 重试 |
| `404 Not Found` | `variant` 值合法，但当前 track 没有这个 variant，例如无法提供 `flac_no_picture` | 回退原始流、本地清理，或请求普通转码兜底 |
| `500 Internal Server Error` | variant 生成失败或缓存文件损坏 | 不要无限重试；回退原始流或转码，并记录服务端错误 |

同一个 URL 的 `HEAD` 和 `GET Range: bytes=0-0` 探测应该返回一致的状态码，区别只在是否返回响应体。

`EmoSonic-Stream-Variant` 必须随每次响应返回：

- 原始流：`EmoSonic-Stream-Variant: original`
- 清理版：`EmoSonic-Stream-Variant: flac_no_picture`
- 转码流：`EmoSonic-Stream-Variant: transcode`

客户端可以用这个头做日志、缓存和播放问题定位。

`flac_no_picture` 的语义：返回无损清理后的 FLAC，移除 attached picture，不改变音频数据。

清理版响应也必须返回完整媒体信息头。其中：

- `EmoSonic-Source-Attached-Picture-Count` 保留原始文件的值。
- `EmoSonic-Output-Attached-Picture-Count` 必须变成 `0`。
- `EmoSonic-Stream-Variant` 必须是 `flac_no_picture`。
- `EmoSonic-Sanitized-Fingerprint` 必须描述当前清理版文件。
- `EmoSonic-Media-Fingerprint` 仍可描述原始文件。

客户端可以用这些头确认服务端确实返回了清理版。

### 3.6 缓存一致性信息

| Header | 示例 | 说明 |
| --- | --- | --- |
| `ETag` | `"track-id-original-or-version"` | HTTP 缓存标识 |
| `Last-Modified` | `Sat, 16 May 2026 06:00:00 GMT` | 源文件修改时间 |
| `EmoSonic-Media-Fingerprint` | `sha256:<hex>` | 原始文件 fingerprint |
| `EmoSonic-Sanitized-Fingerprint` | `sha256:<hex>` | sanitized variant fingerprint |

客户端缓存必须区分：

- 原始 FLAC，可能包含 attached picture。
- 清理版 FLAC，不包含 attached picture。

如果 `EmoSonic-Sanitized-Fingerprint` 存在，客户端应将它作为兼容 variant 的缓存身份之一。

### 3.7 Range 与最终播放 URL

交给 `just_audio` 的最终播放 URL 应支持：

- `Accept-Ranges: bytes`
- `Content-Length`
- `Content-Range`
- 标准 HTTP range 请求，例如 `Range: bytes=0-0`

这不是只针对清理版的优化项，而是面向实际播放链路的能力要求。Windows WinRT、Android ExoPlayer 以及 `just_audio` 的 seek、恢复播放、预加载和缓存探测都可能依赖 range。

客户端用 `GET Range: bytes=0-0` 探测总大小时，不要读取 `206` 响应里的 `Content-Length` 作为完整媒体大小。正确来源是 `Content-Range` 的 `/total` 部分，或服务端额外返回的 `EmoSonic-Output-Content-Length`。

原始静态文件直推和 `flac_no_picture` 服务端缓存文件必须支持 range。特别是 `flac_no_picture` 如果由服务端生成缓存文件，就应该按普通静态媒体文件返回，强制带上 `Accept-Ranges: bytes` 和 `Content-Length`。

实时 ffmpeg pipe 转码如果无法支持 range，不应作为需要稳定 seek / 恢复 / 预加载场景的默认最终播放 URL。若服务端希望转码结果也作为稳定播放 URL，应生成或缓存转码文件后再按静态媒体方式返回；否则客户端应把实时转码视为播放兜底，而不是完整缓存与精确 seek 方案。

## 4. 示例

### 4.1 原始 FLAC 带 PNG attached picture

请求：

```http
HEAD /rest/stream.view?id=6f1c...&u=alice&p=***&c=flutter-android
```

响应头示例：

```http
HTTP/1.1 200 OK
Content-Type: audio/flac
Accept-Ranges: bytes
EmoSonic-Source-Container: flac
EmoSonic-Source-Audio-Codec: flac
EmoSonic-Source-Audio-Sample-Rate: 96000
EmoSonic-Source-Audio-Bit-Depth: 24
EmoSonic-Source-Audio-Channels: 2
EmoSonic-Source-Audio-Bitrate: 2867904
EmoSonic-Source-Audio-Duration-Ms: 180000
EmoSonic-Source-Stream-Count: 2
EmoSonic-Source-Audio-Stream-Count: 1
EmoSonic-Source-Attached-Picture-Count: 1
EmoSonic-Source-Attached-Picture-Codec: png
EmoSonic-Source-Attached-Picture-Width: 4000
EmoSonic-Source-Attached-Picture-Height: 4000
EmoSonic-Output-Container: flac
EmoSonic-Output-Audio-Codec: flac
EmoSonic-Output-Audio-Sample-Rate: 96000
EmoSonic-Output-Audio-Bit-Depth: 24
EmoSonic-Output-Audio-Channels: 2
EmoSonic-Output-Audio-Bitrate: 2867904
EmoSonic-Output-Audio-Duration-Ms: 180000
EmoSonic-Output-Content-Length: 123999999
EmoSonic-Output-Stream-Count: 2
EmoSonic-Output-Audio-Stream-Count: 1
EmoSonic-Output-Attached-Picture-Count: 1
EmoSonic-Output-Attached-Picture-Codec: png
EmoSonic-Output-Attached-Picture-Width: 4000
EmoSonic-Output-Attached-Picture-Height: 4000
EmoSonic-Sanitized-Available: true
EmoSonic-Transcode-Available: true
EmoSonic-Preferred-Compatible-Variant: flac_no_picture
EmoSonic-Stream-Variant: original
EmoSonic-Media-Fingerprint: sha256:111111...
EmoSonic-Sanitized-Fingerprint: sha256:222222...
```

客户端应改用：

```http
GET /rest/stream.view?id=6f1c...&variant=flac_no_picture&u=alice&p=***&c=flutter-android
```

### 4.2 清理版 FLAC

请求：

```http
GET /rest/stream.view?id=6f1c...&variant=flac_no_picture&u=alice&p=***&c=flutter-android
```

响应头示例：

```http
HTTP/1.1 200 OK
Content-Type: audio/flac
Content-Length: 123456789
Accept-Ranges: bytes
EmoSonic-Source-Container: flac
EmoSonic-Source-Audio-Codec: flac
EmoSonic-Source-Audio-Sample-Rate: 96000
EmoSonic-Source-Audio-Bit-Depth: 24
EmoSonic-Source-Audio-Channels: 2
EmoSonic-Source-Audio-Bitrate: 2867904
EmoSonic-Source-Audio-Duration-Ms: 180000
EmoSonic-Source-Stream-Count: 2
EmoSonic-Source-Audio-Stream-Count: 1
EmoSonic-Source-Attached-Picture-Count: 1
EmoSonic-Source-Attached-Picture-Codec: png
EmoSonic-Source-Attached-Picture-Width: 4000
EmoSonic-Source-Attached-Picture-Height: 4000
EmoSonic-Output-Container: flac
EmoSonic-Output-Audio-Codec: flac
EmoSonic-Output-Audio-Sample-Rate: 96000
EmoSonic-Output-Audio-Bit-Depth: 24
EmoSonic-Output-Audio-Channels: 2
EmoSonic-Output-Audio-Bitrate: 2867904
EmoSonic-Output-Audio-Duration-Ms: 180000
EmoSonic-Output-Content-Length: 123456789
EmoSonic-Output-Stream-Count: 1
EmoSonic-Output-Audio-Stream-Count: 1
EmoSonic-Output-Attached-Picture-Count: 0
EmoSonic-Sanitized-Available: true
EmoSonic-Transcode-Available: true
EmoSonic-Preferred-Compatible-Variant: flac_no_picture
EmoSonic-Stream-Variant: flac_no_picture
EmoSonic-Media-Fingerprint: sha256:111111...
EmoSonic-Sanitized-Fingerprint: sha256:222222...
```

清理版应该按普通静态媒体文件返回，必须支持 `Content-Length` 和 `Accept-Ranges: bytes`。`just_audio`、Windows WinRT、Android ExoPlayer 在 seek、预加载和恢复播放时可能依赖 range。

服务端不应把 `flac_no_picture` 实现成不可 seek 的实时 pipe 输出。更稳的方式是先生成或复用缓存中的 sanitized 文件，再用普通静态文件响应返回。

### 4.3 转码输出流

请求：

```http
GET /rest/stream.view?id=6f1c...&format=mp3&maxBitRate=320&u=alice&p=***&c=flutter-android
```

响应头示例：

```http
HTTP/1.1 200 OK
Content-Type: audio/mpeg
EmoSonic-Source-Container: flac
EmoSonic-Source-Audio-Codec: flac
EmoSonic-Source-Audio-Sample-Rate: 96000
EmoSonic-Source-Audio-Bit-Depth: 24
EmoSonic-Source-Audio-Channels: 2
EmoSonic-Source-Audio-Bitrate: 2867904
EmoSonic-Source-Audio-Duration-Ms: 180000
EmoSonic-Source-Attached-Picture-Count: 1
EmoSonic-Output-Container: mp3
EmoSonic-Output-Audio-Codec: mp3
EmoSonic-Output-Audio-Bitrate: 320000
EmoSonic-Output-Audio-Duration-Ms: 180000
EmoSonic-Stream-Variant: transcode
EmoSonic-Transcode-Available: true
EmoSonic-Media-Fingerprint: sha256:111111...
```

转码响应必须用 `Output-*` 描述实际推给客户端的流。上例没有返回 `EmoSonic-Output-Audio-Sample-Rate`、`EmoSonic-Output-Audio-Bit-Depth`、`EmoSonic-Output-Audio-Channels`，表示服务端当前不能准确确认这些输出参数。

### 4.4 无 attached picture 的普通音频

响应头示例：

```http
HTTP/1.1 200 OK
Content-Type: audio/flac
EmoSonic-Source-Container: flac
EmoSonic-Source-Audio-Codec: flac
EmoSonic-Source-Audio-Sample-Rate: 44100
EmoSonic-Source-Audio-Bit-Depth: 16
EmoSonic-Source-Audio-Channels: 2
EmoSonic-Source-Attached-Picture-Count: 0
EmoSonic-Output-Container: flac
EmoSonic-Output-Audio-Codec: flac
EmoSonic-Output-Audio-Sample-Rate: 44100
EmoSonic-Output-Audio-Bit-Depth: 16
EmoSonic-Output-Audio-Channels: 2
EmoSonic-Output-Attached-Picture-Count: 0
EmoSonic-Sanitized-Available: false
EmoSonic-Transcode-Available: true
EmoSonic-Stream-Variant: original
EmoSonic-Media-Fingerprint: sha256:333333...
```

客户端可以直接播放原始 URL。

## 5. 客户端决策流程

推荐流程：

1. 对 `/rest/stream.view` 发 `HEAD`，读取 `EmoSonic-*` 响应头。
2. 如果 `HEAD` 探测失败，用 `GET Range: bytes=0-0` 再探测一次。
3. 如果两种探测都失败，默认走原始直推，不要因为探测失败就强制下载清理。
4. 如果 `EmoSonic-Source-Attached-Picture-Count == 0`，直接在线流播放。
5. 如果 `EmoSonic-Source-Attached-Picture-Count > 0` 且 `EmoSonic-Sanitized-Available == true`，请求 `variant=flac_no_picture`。
6. 如果 `variant=flac_no_picture` 返回 `404`，回退原始流、本地清理或普通转码；返回 `500` 时记录服务端错误后回退，不要无限重试。
7. 如果原始直推播放失败，再进入兼容重试流程，请求 `variant=flac_no_picture` 或普通转码。
8. 缓存时明确区分 original 与 sanitized variant。

伪代码：

```dart
Future<Uri> resolvePlayableStreamUri(Uri originalUri) async {
  final info = await probeStreamHeadersOrNull(originalUri);
  if (info == null) {
    return originalUri;
  }

  final pictureCount = int.tryParse(
    info.headers['emosonic-source-attached-picture-count'] ?? '0',
  ) ?? 0;

  final sanitizedAvailable =
      info.headers['emosonic-sanitized-available'] == 'true';

  final preferredVariant =
      info.headers['emosonic-preferred-compatible-variant'];

  if (pictureCount > 0 &&
      sanitizedAvailable &&
      preferredVariant == 'flac_no_picture') {
    return originalUri.replace(
      queryParameters: {
        ...originalUri.queryParameters,
        'variant': 'flac_no_picture',
      },
    );
  }

  return originalUri;
}
```

## 6. 缓存策略

客户端当前如果只按 `songId` 做播放缓存，就不能同时保存 original、sanitized、transcode 多个版本。

推荐两种策略选一种：

| 策略 | 缓存 key | 说明 |
| --- | --- | --- |
| 简化策略 | `songId` | 只缓存最终用于播放的版本；如果服务端推荐 sanitized，就只缓存 sanitized |
| 完整策略 | `songId + variant + fingerprint` | original、sanitized、transcode 可同时存在，定位和复用更准确 |

如果客户端只关心稳定播放，第一版可以采用简化策略：当 `flac_no_picture` 可用时，只缓存 sanitized 版本。

如果后续要支持“下载原始文件”和“播放兼容版本”并存，必须扩展缓存 key：

```text
<songId>:<variant>:<fingerprint>
```

## 7. Flutter / just_audio 注意事项

如果 Flutter 直接把 URL 交给 `just_audio`，Dart 层不一定能读取播放后端内部请求的响应头。

因此推荐：

- 在创建 `AudioSource` 前，由业务 HTTP client 主动探测媒体头。
- `HEAD` 探测失败时，退化为 `GET Range: bytes=0-0`。
- Range 探测返回 `206` 时，完整大小读取 `Content-Range` 的 `/total` 或 `EmoSonic-Output-Content-Length`，不要读取 `Content-Length`。
- 探测完成后再决定最终播放 URL。
- 播放 URL 一旦选定，交给 `just_audio` 的应该是支持 `Accept-Ranges: bytes` 的 original 或 sanitized variant 最终 URL。
- 客户端缓存 key 应包含 `trackId`、variant、fingerprint。
- 如果 `HEAD` 和 `GET Range: bytes=0-0` 都探测失败，先播放原始 URL；只有播放失败后再走兼容重试。

不要依赖播放器后端自动暴露这些响应头。

## 8. 待客户端工程师评审的问题

- Flutter 当前网络层是否能稳定发 `HEAD` 并读取自定义响应头。
- 是否需要服务端额外提供 JSON 版 `mediaInfo` 接口，避免依赖推流接口响应头。
- 客户端第一版缓存策略采用“只缓存最终播放版本”，还是扩展为 `songId + variant + fingerprint`。
- 对 Windows / Android 两端，是否都按相同策略处理 attached picture。
