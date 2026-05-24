# 推荐反馈后端实现说明

本文档给客户端工程师对接 `热门推荐 -> 不再推荐` 使用。

## 已实现能力

服务端已经实现用户级推荐反馈闭环：

- 客户端提交 `dislike` 后，服务端会记录当前用户对该歌曲的推荐负反馈。
- 当前用户再次请求 `getRecommendedPlaylists` 时，该歌曲会从推荐结果中过滤掉。
- 后续服务端生成新的推荐歌单时，也会排除该用户已 dislike 的歌曲。
- 客户端提交 `restore` 后，服务端会软删除该 dislike，之后推荐算法允许该歌曲重新出现。
- 反馈按用户隔离，A 用户 dislike 不影响 B 用户。

## 写入反馈接口

```text
POST /rest/setRecommendationFeedback.view
```

认证参数仍沿用现有 Subsonic 参数：

```text
u=<user>
p=<password>
```

或：

```text
u=<user>
t=<token>
s=<salt>
```

业务参数支持 query params，也兼容 JSON body。客户端当前继续用 query params 即可。

### dislike 示例

```text
POST /rest/setRecommendationFeedback.view
  ?id=<songId>
  &action=dislike
  &scope=hot_recommended
  &reason=user_dislike
  &source=emosonic
  &u=<user>
  &t=<token>
  &s=<salt>
  &v=1.16.1
  &c=emosonic
  &f=json
```

### restore 示例

```text
POST /rest/setRecommendationFeedback.view
  ?id=<songId>
  &action=restore
  &scope=hot_recommended
  &reason=user_dislike
  &source=emosonic
  &u=<user>
  &t=<token>
  &s=<salt>
  &v=1.16.1
  &c=emosonic
  &f=json
```

## 参数语义

| 参数 | 必填 | 当前支持 | 说明 |
| --- | --- | --- | --- |
| `id` | 是 | 任意非空 song id | 必须和 `getRecommendedPlaylists` 返回的 `entry.id` 一致。服务端不要求歌曲仍存在。 |
| `action` | 是 | `dislike` / `restore` | `dislike` 写入有效负反馈；`restore` 软删除有效负反馈。 |
| `scope` | 否 | `hot_recommended` | 默认 `hot_recommended`。其他 scope 当前会返回 failed。 |
| `reason` | 否 | 建议 `user_dislike` | 默认 `user_dislike`。 |
| `source` | 否 | 建议 `emosonic` | 默认 `api`。 |

## 成功响应

`dislike` 成功：

```json
{
  "subsonic-response": {
    "status": "ok",
    "version": "1.12.0",
    "recommendationFeedback": {
      "id": "<songId>",
      "action": "dislike",
      "scope": "hot_recommended"
    }
  }
}
```

`restore` 成功：

```json
{
  "subsonic-response": {
    "status": "ok",
    "version": "1.12.0",
    "recommendationFeedback": {
      "id": "<songId>",
      "action": "restore",
      "scope": "hot_recommended"
    }
  }
}
```

注意：`version` 由服务端现有 Subsonic formatter 决定，目前是 `1.12.0`。

## 失败响应

失败仍沿用 Subsonic 风格：

```json
{
  "subsonic-response": {
    "status": "failed",
    "version": "1.12.0",
    "error": {
      "code": 0,
      "message": "invalid recommendation feedback action"
    }
  }
}
```

客户端应继续把 `status=failed`、HTTP 错误、网络异常都当作同步失败，并保留 pending outbox 等待重试。

## 幂等语义

- 重复 `dislike` 同一 `(user, songId, scope)`：返回 ok，不产生重复有效记录。
- 重复 `restore` 同一 `(user, songId, scope)`：返回 ok，不产生 500。
- 歌曲已删除或不存在：仍可记录反馈并返回 ok，避免客户端无限重试。
- `restore` 后服务端保留历史记录，但标记为软删除；有效 dislike 集合里不再包含该歌曲。

## 推荐列表过滤语义

`GET /rest/getRecommendedPlaylists.view` 已接入过滤：

- 服务端按当前鉴权用户读取 `scope=hot_recommended` 的有效 dislike。
- 返回前过滤这些 song id。
- `songCount`、`duration`、`coverArt`、`entry` 都基于过滤后的结果。
- 如果过滤后为空，服务端返回空推荐歌单；JSON formatter 可能省略空 `entry` 字段。
- 过滤只影响热门推荐，不影响搜索、专辑页、歌单、收藏、历史记录和播放。

## 后续生成推荐歌单

服务端生成每日推荐歌单时也会读取当前用户 dislike 集合：

- dislike 后，新生成的推荐歌单不会再包含该歌曲。
- restore 后，后续新生成的推荐歌单允许再次包含该歌曲。
- 已经生成过的旧推荐歌单不会被物理改写；但 API 返回时仍会实时过滤，因此客户端看不到已 dislike 的歌曲。

## 数据隔离

反馈表按用户隔离：

```text
unique(user_id, song_id, scope)
```

因此：

- 用户 A dislike `song-123` 后，A 的热门推荐过滤 `song-123`。
- 用户 B 不受影响，仍可能看到 `song-123`。

## 客户端建议

- 用户点击“不再推荐”后继续本地立即隐藏，提升 UI 响应速度。
- 后端同步失败时继续保留 pending outbox。
- 撤销时发送 `restore`。
- 刷新推荐时可以继续先做本地 disliked 过滤；服务端也会过滤，二者是兜底关系。

## 联调验收

建议验证：

1. 用户 A dislike 某首推荐歌后，刷新热门推荐不再返回该歌曲。
2. 用户 B 仍可看到该歌曲。
3. 用户 A restore 后，刷新/后续生成允许该歌曲再次出现。
4. 重复 dislike 返回 ok，服务端只有一条有效记录。
5. 重复 restore 返回 ok，不报 500。
6. dislike 已删除或不存在的歌曲 ID 返回 ok。
7. 过滤后 `coverArt` 不使用已过滤歌曲的专辑封面。
8. 旧客户端继续请求 `getRecommendedPlaylists` 不崩溃。
