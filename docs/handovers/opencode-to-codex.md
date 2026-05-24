# OpenCode 到 Codex 迁移交接文档

## 项目概况

### 事实
项目路径：`/workspace/supysonic`

项目类型：Python 项目，核心栈为 Flask + Peewee。

测试框架：`unittest`

Python 环境：

```bash
/root/enter/envs/supysonic/bin/python
```

当前仓库：Git 仓库，当前分支 `master`

## OpenCode 交接时 Git 状态

### 事实
交接时最新提交序列：

```text
810d9c1 refactor: split db models by domain
f207c97 refactor: extract low dependency db models
60a1c48 refactor: extract subsonic serializers
d55a389 refactor: extract db runtime helpers
ed46c2e refactor: extract db schema helpers
4b451da refactor: extract db core primitives
089b9a3 test: add db layer facade contract
a8b295f add album enrichment and client release support
```

交接时工作区只剩 `img/*.png` 未跟踪截图，不应提交。

### Codex 接手后先核验

```bash
git status --short --untracked-files=all
git branch --show-current
git log --oneline -8
```

## 近期重构结果

### 事实
近期完成的是 DB layer refactor：

目标是把 `supysonic/db.py` 拆成兼容 facade + `supysonic/db_layer/` 下的领域模块，同时保持旧导入兼容：

```python
from supysonic.db import Album, Track, init_database
from supysonic import db
```

交接时 `supysonic/db.py` 是 38 行兼容 facade。

当前 `supysonic/db_layer/` 模块：

```text
core.py
schema.py
runtime.py
serializers.py
emo.py
client_releases.py
library.py
users.py
annotations.py
review_tasks.py
playlists.py
misc.py
```

关键 contract test：

```text
tests/base/test_db_layer_contract.py
```

该测试验证 `supysonic.db` 与 `supysonic.db_layer.*` 暴露的是同一对象，不是复制对象。

计划文件：

```text
docs/plans/2026-05-09-db-layer-refactor.md
```

该计划已执行到 Task 8 完成。

## 验证状态

### 事实
最终完整验证通过：

```bash
/root/enter/envs/supysonic/bin/python -m unittest
```

结果：

```text
Ran 554 tests in 213.917s

OK
```

空白检查：

```bash
git diff --check
```

结果：无输出。

## Codex 接手后的第一步

1. 核验 Git 状态：

```bash
git status --short --untracked-files=all
git branch --show-current
git log --oneline -8
```

2. 阅读关键文件：

```text
supysonic/db.py
supysonic/db_layer/
tests/base/test_db_layer_contract.py
docs/plans/2026-05-09-db-layer-refactor.md
```

3. 如继续修改 DB layer，先运行窄测试：

```bash
/root/enter/envs/supysonic/bin/python -m unittest tests.base.test_db_layer_contract
```

4. 完成前运行：

```bash
/root/enter/envs/supysonic/bin/python -m unittest
git diff --check
```

## 开发规则

### 事实
- 始终使用简体中文回复。
- 修改前先阅读相关文件。
- 每次只做最小必要改动。
- 不确定时先查证或提问，不要猜测。
- 完成前运行验证。
- 不要提交 `img/` 下截图。
- 不要覆盖用户未提交改动。
- 不要泄露或提交本地配置、密钥、token。

## 测试命令

完整测试：

```bash
/root/enter/envs/supysonic/bin/python -m unittest
```

DB layer contract：

```bash
/root/enter/envs/supysonic/bin/python -m unittest tests.base.test_db_layer_contract
```

空白检查：

```bash
git diff --check
```

## 风险点/不要做

### 事实
`/workspace/supysonic/supysonic.conf` 包含本地配置和 `lastfm` `api_key` / `secret`，不要输出、泄露或提交。

`/emo/upload_log` 的 `413` 根因是 nginx client body limit，不是 Flask app。

`IniConfig` mutable defaults 污染问题已修复。

### 不要做
- 不要破坏 `from supysonic.db import ...` 兼容性。
- 不要把 facade 导出改成包装对象；contract test 要求共享同一对象。
- 不要提交 `img/*.png`。
- 不要提交或展示 `supysonic.conf` 中的密钥。
- 不要在未验证时声称完成。

## 建议 Codex 分析的问题

### 事实
DB layer refactor 已完成到 Task 8，并通过完整测试。

### 待核验
1. `supysonic/db_layer/` 各模块是否还有可降低耦合的导入关系。
2. `supysonic/db.py` facade 是否需要额外 contract 覆盖所有公开导出。
3. 是否还有业务代码直接依赖 DB layer 内部实现细节。
4. 是否需要补充文档说明新的 DB layer 模块边界。
5. 是否存在 legacy import 路径未被 contract test 覆盖。
