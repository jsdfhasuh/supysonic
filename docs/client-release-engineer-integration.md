# Client Release 发布工程师对接文档

本文档面向 Android / Windows 客户端发布工程师，说明如何通过 Emosonic Server 发布客户端安装包、登记外部下载地址、查询最新版本、验证下载入口，以及客户端 APP 如何接入更新检查。

## 1. 接口概览

客户端发布接口挂载在：

```text
/client-releases
```

接口清单：

| 场景 | 方法 | 路径 | 鉴权 |
| --- | --- | --- | --- |
| 发布版本 | `POST` | `/client-releases/publish` | 需要发布 Token |
| 查询最新版本 | `GET` | `/client-releases/latest?platform=android` | 不需要 |
| 查询版本列表 | `GET` | `/client-releases?platform=android` | 不需要 |
| 下载版本 | `GET` | `/client-releases/download/<release_id>` | 不需要 |
| 浏览历史版本页面 | `GET` | `/client-releases/history?platform=android` | 不需要 Web 登录 |

发布接口支持两种模式：

| 模式 | 说明 |
| --- | --- |
| 文件上传 | 直接把 APK / Windows 安装包上传到服务器 |
| 外链登记 | 只登记已经上传到 CDN / 对象存储的下载地址 |

## 2. 服务端配置

服务端配置在 `supysonic.conf` 的 `[webapp]` 段。

```ini
[webapp]
mount_client_releases = on
release_upload_dir = /downloads/music/supysonic/client-releases
release_api_token = <RELEASE_API_TOKEN>
release_max_upload_size = 536870912
```

配置项说明：

| 配置项 | 说明 |
| --- | --- |
| `mount_client_releases` | 是否启用 `/client-releases` 接口，默认 `on` |
| `release_upload_dir` | 文件上传模式下安装包保存目录 |
| `release_api_token` | 发布接口 Token，留空会禁用发布能力 |
| `release_max_upload_size` | 最大上传大小，单位字节，默认 `536870912`，即 512 MB |

生成 Token：

```bash
openssl rand -hex 32
```

注意事项：

- 不要把真实 `release_api_token` 写入文档、代码仓库或 CI 日志。
- `release_api_token` 修改后需要重启服务才能生效。
- `release_api_token` 为空时，`POST /client-releases/publish` 返回 `503`。
- latest / list / download 接口是公开匿名接口，不依赖 Web 登录态。
- `/client-releases/history` 是面向浏览器的历史版本页面；未登录也可访问，已登录时会复用当前 Web 导航栏。

## 3. 鉴权方式

只有发布接口需要鉴权：

```text
POST /client-releases/publish
```

推荐使用请求头：

```http
X-Release-Token: <RELEASE_API_TOKEN>
```

也支持 Bearer Token：

```http
Authorization: Bearer <RELEASE_API_TOKEN>
```

当前不支持用户名密码发布。发布脚本、CI/CD 和人工发布工具都应使用独立发布 Token。

## 4. 平台与文件类型

| `platform` | 允许文件类型 |
| --- | --- |
| `android` | `apk` |
| `windows` | `exe`、`msi`、`zip` |

校验规则：

- `platform` 只支持 `android` 和 `windows`。
- Android 只能发布 `.apk`。
- Windows 只能发布 `.exe`、`.msi`、`.zip`。
- 文件上传模式会校验上传文件名扩展名。
- 外链登记模式会校验 `fileType` 或从 `downloadUrl` 扩展名推断文件类型。
- 外链 URL 只允许 `http://` 或 `https://`。

## 5. 版本规则

Android 和 Windows 统一使用 Flutter 版本规则。

| 字段 | 说明 | 示例 |
| --- | --- | --- |
| `buildName` | Flutter `buildName`，必须是三段数字版本 | `1.2.3` |
| `buildNumber` | Flutter `buildNumber`，必须是大于 0 的整数 | `45` |
| `version` | 服务端自动生成 | `1.2.3+45` |

合法示例：

```text
1.0.0+1
1.2.3+45
2.10.0+1002
```

非法示例：

```text
v1.0.0
1.0
1.0.0-beta
1.0.0+0
```

最新版本选择规则：

- 先按 `buildName` 的数字段比较，例如 `1.10.0 > 1.9.9`。
- `buildName` 相同时，再比较 `buildNumber`。
- 同一个 `platform + buildName + buildNumber` 重复发布会覆盖原记录，不会创建重复版本。

## 6. 外链登记发布

适用场景：安装包已经由 CI 上传到 CDN、对象存储或其他下载服务器，只需要在 Emosonic Server 登记版本元数据。

请求：

```http
POST /client-releases/publish
Content-Type: application/json
X-Release-Token: <RELEASE_API_TOKEN>
```

字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `platform` | 是 | `android` 或 `windows` |
| `buildName` | 是 | 例如 `1.2.3` |
| `buildNumber` | 是 | 例如 `45` |
| `downloadUrl` | 是 | 外部下载地址 |
| `fileType` | 否 | `apk` / `exe` / `msi` / `zip`，不传则从 URL 扩展名推断 |
| `releaseNotes` | 否 | 发布说明 |

Android 示例：

```bash
curl --fail-with-body -X POST "${SUPYSONIC_BASE_URL}/client-releases/publish" \
  -H "Content-Type: application/json" \
  -H "X-Release-Token: ${RELEASE_API_TOKEN}" \
  -d '{
    "platform": "android",
    "buildName": "1.2.3",
    "buildNumber": 45,
    "downloadUrl": "https://cdn.example.com/releases/android/app-1.2.3+45.apk",
    "releaseNotes": "Fix playback and login issues"
  }'
```

Windows 示例：

```bash
curl --fail-with-body -X POST "${SUPYSONIC_BASE_URL}/client-releases/publish" \
  -H "Content-Type: application/json" \
  -H "X-Release-Token: ${RELEASE_API_TOKEN}" \
  -d '{
    "platform": "windows",
    "buildName": "1.2.3",
    "buildNumber": 45,
    "downloadUrl": "https://cdn.example.com/releases/windows/Emosonic-1.2.3.msi",
    "fileType": "msi",
    "releaseNotes": "Windows installer update"
  }'
```

## 7. 文件上传发布

适用场景：发布脚本直接把安装包上传到 Emosonic Server，由服务端保存文件并生成下载入口。

请求：

```http
POST /client-releases/publish
Content-Type: multipart/form-data
X-Release-Token: <RELEASE_API_TOKEN>
```

字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `platform` | 是 | `android` 或 `windows` |
| `buildName` | 是 | 例如 `1.2.3` |
| `buildNumber` | 是 | 例如 `45` |
| `file` | 是 | 上传的安装包文件 |
| `fileType` | 否 | 不传则从文件名扩展名推断 |
| `releaseNotes` | 否 | 发布说明 |

Android APK 上传示例：

```bash
curl --fail-with-body -X POST "${SUPYSONIC_BASE_URL}/client-releases/publish" \
  -H "X-Release-Token: ${RELEASE_API_TOKEN}" \
  -F "platform=android" \
  -F "buildName=1.2.3" \
  -F "buildNumber=45" \
  -F "releaseNotes=Fix playback and login issues" \
  -F "file=@./app-release.apk"
```

Windows MSI 上传示例：

```bash
curl --fail-with-body -X POST "${SUPYSONIC_BASE_URL}/client-releases/publish" \
  -H "Authorization: Bearer ${RELEASE_API_TOKEN}" \
  -F "platform=windows" \
  -F "buildName=1.2.3" \
  -F "buildNumber=45" \
  -F "releaseNotes=Windows installer update" \
  -F "file=@./Emosonic-Setup-1.2.3.msi"
```

服务端保存规则：

- 文件保存到 `release_upload_dir/<platform>/`。
- 文件名会自动加版本号和随机前缀，避免冲突。
- 服务端会计算 `sha256` 和 `fileSize`。
- 上传文件为空会被拒绝。
- 超过 `release_max_upload_size` 会被拒绝。

## 8. 成功响应

上传发布响应示例：

```json
{
  "release": {
    "id": "5f9d3a52-6a77-4c77-bb0d-33a2d7105c65",
    "platform": "android",
    "fileType": "apk",
    "buildName": "1.2.3",
    "buildNumber": 45,
    "version": "1.2.3+45",
    "publishMode": "upload",
    "fileName": "app-release.apk",
    "fileSize": 12345678,
    "sha256": "abcdef0123456789...",
    "releaseNotes": "Fix playback and login issues",
    "downloadUrl": "/client-releases/download/5f9d3a52-6a77-4c77-bb0d-33a2d7105c65",
    "sourceDownloadUrl": null,
    "created": "2026-05-07T12:00:00",
    "updated": "2026-05-07T12:00:00"
  }
}
```

外链登记响应中：

- `publishMode` 为 `external_url`。
- `sourceDownloadUrl` 是工程师提交的外部下载地址。
- `downloadUrl` 仍然是 Emosonic Server 的统一下载入口。
- 访问 `downloadUrl` 时，服务端会重定向到 `sourceDownloadUrl`。

## 9. 查询最新版本

Android：

```bash
curl --fail-with-body "${SUPYSONIC_BASE_URL}/client-releases/latest?platform=android"
```

Windows：

```bash
curl --fail-with-body "${SUPYSONIC_BASE_URL}/client-releases/latest?platform=windows"
```

成功响应：

```json
{
  "release": {
    "platform": "android",
    "version": "1.2.3+45",
    "downloadUrl": "/client-releases/download/5f9d3a52-6a77-4c77-bb0d-33a2d7105c65",
    "sha256": "abcdef0123456789..."
  }
}
```

无可用版本时：

```json
{
  "error": "No release available"
}
```

HTTP 状态码为 `404`。

## 10. 查询版本列表

```bash
curl --fail-with-body "${SUPYSONIC_BASE_URL}/client-releases?platform=android"
```

响应格式：

```json
{
  "releases": [
    {
      "version": "1.2.3+45",
      "downloadUrl": "/client-releases/download/5f9d3a52-6a77-4c77-bb0d-33a2d7105c65"
    }
  ]
}
```

列表按最新版本优先排序。

## 11. 浏览历史版本页面

首页 `Client downloads` 卡片中的 `History` 按钮会跳转到平台对应的历史版本页：

- Android: `/client-releases/history?platform=android`
- Windows: `/client-releases/history?platform=windows`

这个页面会直接复用服务端当前版本列表，按最新优先展示，并为每个版本提供统一下载入口。

适用场景：

- QA 验证旧版本是否仍可下载。
- 支持团队手动回滚到历史安装包。
- 客户端测试人员从浏览器直接选择某个旧版本下载。

## 12. 下载验证

下载上传到 Emosonic Server 的文件：

```bash
curl --fail-with-body -L -o app-release.apk \
  "${SUPYSONIC_BASE_URL}/client-releases/download/<release_id>"
```

说明：

- 上传发布模式会直接返回本地文件。
- 外链登记模式会返回 `302` 重定向。
- 下载脚本建议使用 `-L` 跟随重定向。
- 若响应中有 `sha256`，发布脚本应在下载后校验完整性。

校验示例：

```bash
echo "${SHA256}  app-release.apk" | sha256sum -c -
```

## 13. APP 更新接入

客户端 APP 更新检查使用公开接口，不需要登录态，也不需要发布 Token。

### 13.1 更新检查流程

推荐 APP 在以下时机检查更新：

- 启动后进入主页面时检查一次。
- 用户进入“关于 / 设置 / 检查更新”页面时手动检查。
- 后台定时检查时需要避免高频请求，例如每天一次。

推荐流程：

1. APP 读取当前安装包版本：`buildName` 和 `buildNumber`。
2. APP 根据平台请求 latest 接口。
3. APP 比较服务端版本和本地版本。
4. 如果服务端版本更新，则展示更新提示。
5. 用户确认后打开 `downloadUrl`。
6. 下载完成后，按平台安装流程处理。

平台参数：

| APP 平台 | 请求参数 |
| --- | --- |
| Android | `platform=android` |
| Windows | `platform=windows` |

请求示例：

```bash
curl --fail-with-body \
  "${SUPYSONIC_BASE_URL}/client-releases/latest?platform=android"
```

### 13.2 APP 版本比较规则

服务端返回：

```json
{
  "release": {
    "buildName": "1.2.3",
    "buildNumber": 45,
    "version": "1.2.3+45",
    "downloadUrl": "/client-releases/download/5f9d3a52-6a77-4c77-bb0d-33a2d7105c65",
    "sha256": "abcdef0123456789..."
  }
}
```

APP 端比较规则必须与服务端一致：

- 先把 `buildName` 按 `.` 拆成数字比较。
- `buildName` 相同时，再比较 `buildNumber`。
- 不能直接用字符串比较版本号，否则 `1.10.0` 可能被误判小于 `1.9.9`。

伪代码：

```text
serverBuildNameParts = server.buildName.split('.').map(toInt)
localBuildNameParts = local.buildName.split('.').map(toInt)

if serverBuildNameParts > localBuildNameParts:
    hasUpdate = true
else if serverBuildNameParts == localBuildNameParts:
    hasUpdate = server.buildNumber > local.buildNumber
else:
    hasUpdate = false
```

Flutter / Dart 示例：

```dart
int compareBuildName(String left, String right) {
  final leftParts = left.split('.').map(int.parse).toList();
  final rightParts = right.split('.').map(int.parse).toList();

  for (var i = 0; i < 3; i++) {
    if (leftParts[i] != rightParts[i]) {
      return leftParts[i].compareTo(rightParts[i]);
    }
  }
  return 0;
}

bool hasNewerRelease({
  required String localBuildName,
  required int localBuildNumber,
  required String serverBuildName,
  required int serverBuildNumber,
}) {
  final nameCompare = compareBuildName(serverBuildName, localBuildName);
  if (nameCompare > 0) {
    return true;
  }
  if (nameCompare < 0) {
    return false;
  }
  return serverBuildNumber > localBuildNumber;
}
```

### 13.3 下载地址处理

接口返回的 `downloadUrl` 可能是相对路径：

```json
"downloadUrl": "/client-releases/download/5f9d3a52-6a77-4c77-bb0d-33a2d7105c65"
```

APP 端需要拼接服务端地址：

```text
absoluteDownloadUrl = SUPYSONIC_BASE_URL + downloadUrl
```

下载行为：

| 发布模式 | APP 端处理 |
| --- | --- |
| `upload` | 下载接口直接返回安装包文件 |
| `external_url` | 下载接口返回 `302`，APP 下载组件需要支持跟随重定向 |

Android 建议：

- 使用系统浏览器打开下载链接，或使用系统 DownloadManager。
- APK 安装仍需 Android 端处理“允许安装未知来源应用”的用户授权。
- 如果使用内置下载器，需要支持 HTTP 302 重定向。

Windows 建议：

- 使用默认浏览器打开下载链接，或由客户端内置下载器下载。
- 下载完成后根据文件类型打开 `.exe`、`.msi` 或 `.zip`。
- 如果是 `.zip`，APP 端需要明确后续安装/解压流程。

### 13.4 完整性校验

上传发布模式会返回 `sha256`：

```json
"sha256": "abcdef0123456789..."
```

APP 内置下载器建议下载后计算本地文件 sha256，并与服务端返回值比较。

外链登记模式目前不会生成 `sha256`，因为服务端没有下载外部文件进行计算。若外链模式也需要完整性校验，建议发布工程师把校验逻辑放在 CI 侧，或改用文件上传模式。

### 13.5 无版本和错误处理

无版本时，服务端返回：

```json
{
  "error": "No release available"
}
```

HTTP 状态码为 `404`。

APP 端建议行为：

- 自动检查时静默忽略，不弹错误。
- 用户手动点击“检查更新”时提示“当前没有可用更新”。
- 网络失败、JSON 解析失败、`400`、`500` 等错误，不应阻塞 APP 正常使用。

### 13.6 当前不支持的更新策略

当前接口只提供“最新版本查询 + 下载入口”，不包含以下策略字段：

- 强制更新
- 最低可用版本
- 灰度发布
- 渠道区分
- 更新弹窗文案分平台配置
- 多语言更新说明

如果 APP 需要强制更新或灰度策略，需要后续扩展发布模型和接口字段。当前 APP 端应按“可选更新”处理。

## 13. 常见错误

| HTTP 状态码 | 场景 | 响应示例 |
| --- | --- | --- |
| `400` | 平台不支持 | `{"error":"Invalid platform"}` |
| `400` | `buildName` 不合法 | `{"error":"Invalid buildName"}` |
| `400` | `buildNumber` 不合法 | `{"error":"Invalid buildNumber"}` |
| `400` | 外链地址不合法 | `{"error":"Invalid downloadUrl"}` |
| `400` | 文件类型不支持 | `{"error":"Invalid file type for android"}` |
| `400` | 缺少上传文件 | `{"error":"Missing upload file"}` |
| `400` | 上传目录未配置 | `{"error":"Release upload directory is not configured"}` |
| `400` | 上传超过大小限制 | `{"error":"Upload exceeds maximum size"}` |
| `403` | Token 缺失或错误 | `{"error":"Invalid release token"}` |
| `404` | 没有可用版本 | `{"error":"No release available"}` |
| `404` | 安装包文件丢失 | `{"error":"Release file is missing"}` |
| `503` | 服务端未配置 Token | `{"error":"Release token is not configured"}` |

## 14. CI/CD 推荐流程

推荐发布步骤：

1. 构建 Android APK 或 Windows 安装包。
2. 从 Flutter 版本中读取 `buildName` 和 `buildNumber`。
3. 将 `RELEASE_API_TOKEN` 配置为 CI Secret。
4. 根据产物存放方式选择文件上传发布或外链登记发布。
5. 发布后调用 latest 接口确认版本已生效。
6. 下载 `downloadUrl`，确认文件可访问。
7. 如响应中有 `sha256`，下载后做完整性校验。

CI 上传模板：

```bash
set -euo pipefail

: "${SUPYSONIC_BASE_URL:?missing SUPYSONIC_BASE_URL}"
: "${RELEASE_API_TOKEN:?missing RELEASE_API_TOKEN}"
: "${PLATFORM:?missing PLATFORM}"
: "${BUILD_NAME:?missing BUILD_NAME}"
: "${BUILD_NUMBER:?missing BUILD_NUMBER}"
: "${ARTIFACT_PATH:?missing ARTIFACT_PATH}"

publish_response="$(
  curl --fail-with-body -sS -X POST "${SUPYSONIC_BASE_URL}/client-releases/publish" \
    -H "X-Release-Token: ${RELEASE_API_TOKEN}" \
    -F "platform=${PLATFORM}" \
    -F "buildName=${BUILD_NAME}" \
    -F "buildNumber=${BUILD_NUMBER}" \
    -F "releaseNotes=${RELEASE_NOTES:-}" \
    -F "file=@${ARTIFACT_PATH}"
)"

printf '%s\n' "${publish_response}"

curl --fail-with-body -sS \
  "${SUPYSONIC_BASE_URL}/client-releases/latest?platform=${PLATFORM}"
```

环境变量建议：

| 变量 | 示例 | 说明 |
| --- | --- | --- |
| `SUPYSONIC_BASE_URL` | `https://music.example.com` | Emosonic Server 地址 |
| `RELEASE_API_TOKEN` | CI Secret | 发布 Token |
| `PLATFORM` | `android` | 发布平台 |
| `BUILD_NAME` | `1.2.3` | Flutter buildName |
| `BUILD_NUMBER` | `45` | Flutter buildNumber |
| `ARTIFACT_PATH` | `./app-release.apk` | 安装包路径 |
| `RELEASE_NOTES` | `Fix playback` | 可选发布说明 |

## 15. 发布前检查清单

| 检查项 | 要求 |
| --- | --- |
| Token | 已从安全渠道获取，未写入仓库 |
| 平台 | `android` 或 `windows` |
| 版本 | `buildName` 是 `x.y.z`，`buildNumber` 大于 0 |
| 文件类型 | Android 为 APK，Windows 为 EXE / MSI / ZIP |
| 文件签名 | Android / Windows 安装包已按平台规范签名 |
| 下载 | latest 返回的 `downloadUrl` 可访问 |
| 完整性 | 上传发布时校验 `sha256` |

## 16. 安全注意事项

- 发布接口必须走 HTTPS。
- `RELEASE_API_TOKEN` 只能放在 CI Secret 或受控密钥管理系统中。
- 不要在 shell 开启 `set -x` 时输出发布命令，避免 Token 进入日志。
- 外链登记模式只校验 URL 格式和协议，不校验外部文件内容。
- 文件上传模式会计算 `sha256`，客户端可用它做完整性校验。
- 上传目录应是服务专用目录，不要指向源码目录、系统目录或公开可写目录。
- 同版本重复发布会覆盖元数据，发布脚本应避免误用旧版本号。
