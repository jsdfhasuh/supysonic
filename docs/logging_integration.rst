Supysonic 日志接入指南
=======================

本文档面向部署、运维、客户端联调和后续服务端开发人员，说明 Supysonic
的 Web/Daemon 日志如何开启、文件如何路由，以及如何接入 ``/rest/stream``
独立日志。

开启文件日志
------------

Web 服务日志由 ``[webapp]`` 配置控制：

.. code-block:: ini

   [webapp]
   log_dir = /log/web
   log_level = INFO
   log_backup_count = 7
   log_rotate = true

推荐配置 ``log_dir``。设置后，Supysonic 会在该目录下创建分类日志文件。
如果没有设置 ``log_dir``，但设置了旧配置 ``log_file``，服务端会使用
``log_file`` 的父目录作为分类日志目录。

如果 ``log_dir`` 和 ``log_file`` 都为空，Web 日志只输出到控制台。
Docker 部署下可用：

.. code-block:: bash

   docker logs --tail 300 my_supysonic

Daemon 日志由 ``[daemon]`` 配置控制：

.. code-block:: ini

   [daemon]
   log_dir = /log/daemon
   log_level = INFO
   log_backup_count = 7
   log_rotate = true

Web 日志文件
------------

配置 ``[webapp].log_dir`` 后，Web 侧会写入这些文件：

.. list-table::
   :header-rows: 1

   * - 文件
     - 内容
   * - ``supysonic.log``
     - Web 总日志，包含 INFO 及以上的分类日志汇总。
   * - ``access.log``
     - 所有 HTTP 请求的结构化访问日志，包括 REST、Web 页面、Socket 摘要。
   * - ``stream.log``
     - ``/rest/stream`` 和 ``/rest/stream.view`` 的独立结构化请求日志。
   * - ``api.log``
     - Subsonic REST API 错误、失败和关键 API 事件。
   * - ``emo.log``
     - EmoSonic 播放、WebSocket 和客户端状态事件。
   * - ``metadata.log``
     - 元数据编辑、审核和写回相关事件。
   * - ``scanner.log``
     - 扫描器、watcher 和扫描任务事件。
   * - ``task.log``
     - 后台任务管理器事件。
   * - ``web.debug.log``
     - 仅 ``log_level = DEBUG`` 时创建，保存 Web DEBUG 级别日志。

日志轮转默认按天切分，保留数量由 ``log_backup_count`` 控制。
``log_rotate = false`` 时使用普通文件追加。

Stream 独立日志
---------------

``stream.log`` 只记录路径以 ``/rest/stream`` 开头的请求，包括：

.. code-block:: text

   /rest/stream
   /rest/stream.view

典型日志行：

.. code-block:: text

   2026-05-17 09:43:16,216 [INFO] stream event=request headers="user-agent=TestPlayer/1.0;host=localhost;authorization=***;range=bytes=0-0;x-request-id=stream-req-1" type=REST request_id=stream-req-1 remote=127.0.0.1 method=GET path=/rest/stream query="u=root&t=***&s=***&id=track-1" status=200 bytes=6 duration=0.000075s

字段说明：

.. list-table::
   :header-rows: 1

   * - 字段
     - 含义
   * - ``event=request``
     - 固定表示一次 stream HTTP 请求。
   * - ``headers``
     - 请求头快照，header 名统一小写，多个 header 用 ``;`` 分隔。
   * - ``type``
     - 请求类型，stream 为 ``REST``。
   * - ``request_id``
     - 请求关联 ID；优先使用客户端 ``X-Request-ID``，否则服务端生成。
   * - ``remote``
     - 客户端 IP。
   * - ``method``
     - HTTP 方法，例如 ``GET``、``HEAD``。
   * - ``path``
     - 请求路径。
   * - ``query``
     - 脱敏后的 query string。
   * - ``status``
     - HTTP 响应状态码。
   * - ``bytes``
     - 响应大小；流式响应无法计算时可能为 ``-``。
   * - ``duration``
     - Flask 应用层处理耗时。

``stream.log`` 是应用层日志。gevent server 仍会在 stdout 里输出原始访问日志，
例如 ``[ACCESS:STREAM] ...``，它不写入 ``stream.log``，Docker 下通过
``docker logs`` 查看。

脱敏规则
--------

日志使用 ``key=value`` 文本格式。字段值包含空格、分号、换行或特殊字符时会
自动加引号并转义。

Query string 会脱敏以下参数：

.. code-block:: text

   p, password, s, salt, t, token

请求头会脱敏以下 header：

.. code-block:: text

   authorization
   cookie
   proxy-authorization
   set-cookie
   x-api-key
   x-auth-token
   x-csrf-token
   x-release-token

示例：

.. code-block:: text

   query="u=root&t=***&s=***&id=track-1"
   headers="authorization=***;cookie=***;range=bytes=0-0"

不要依赖 header 原始大小写。HTTP header 名大小写不敏感，日志里统一按小写输出。

接入建议
--------

客户端或运维系统接入时，建议优先按这些字段索引：

.. code-block:: text

   request_id
   path
   method
   status
   duration
   remote
   headers
   query

客户端联调时建议发送 ``X-Request-ID``，这样可以同时关联 ``access.log``、
``stream.log``、``api.log`` 和客户端本地日志。

示例请求：

.. code-block:: bash

   curl -I \
     -H 'X-Request-ID: client-stream-001' \
     -H 'Range: bytes=0-0' \
     'http://localhost:8000/rest/stream.view?id=<trackId>&u=<user>&t=<token>&s=<salt>&v=1.16.1&c=emosonic'

查看 stream 独立日志：

.. code-block:: bash

   tail -f /log/web/stream.log

Docker 未挂载文件日志时查看控制台日志：

.. code-block:: bash

   docker logs -f my_supysonic | grep '/rest/stream'

开发接入约定
------------

新增 Web 日志分类时，优先复用 ``supysonic.logging_manager.configure_web_logging()``
和 ``format_log_event()``，不要绕过现有日志系统直接写文件。

新增字段时遵守以下规则：

1. 不记录密码、token、cookie、authorization 或大段 payload。
2. 保持单行 ``key=value`` 格式，便于 grep、tail、日志采集器解析。
3. 为新增日志行为补充 ``unittest``，至少验证文件路由和敏感信息脱敏。
4. 不要把高频音频 chunk 写入日志；stream 日志只记录请求级摘要。
