# DEV_LOG

用于记录项目后续开发过程中的关键事件、帮助信息、提示词等。按日期分段，建议以“小结 + 事件条目”的形式记录，条目包含：时间、动作、涉及模块、命令/接口、要点与注意事项。

## 记录模板
- 日期：YYYY-MM-DD
  - 时间：HH:MM，动作：...
  - 模块：...
  - 命令/接口：...
  - 要点：...

---

## 2025-12-04
- 09:30，动作：项目目录初始化
  - 模块：基础框架
  - 要点：创建 `app/`, `templates/`, `static/` 等目录；`README.md` 初始化

- 10:10，动作：虚拟环境与依赖安装
  - 模块：环境准备
  - 命令：
    - `python -m venv venv`
    - `./venv/Scripts/Activate.ps1`
    - `python -m pip install -r requirements/requirements.txt`

- 11:00，动作：数据库迁移初始化
  - 模块：Flask-Migrate
  - 命令：
    - `python -m flask --app app:create_app db init`
    - `python -m flask --app app:create_app db migrate -m "init"`
    - `python -m flask --app app:create_app db upgrade`

- 12:00，动作：登录与角色权限完成
  - 模块：`auth`, `models(User, Role)`, `Flask-Login`
  - 要点：登录拦截、默认管理员 `admin/admin123`

- 13:20，动作：UI 调整与左侧导航重构
  - 模块：`templates/base.html`
  - 要点：左侧菜单包含首页/后台管理/用户管理/系统设置；顶部 `layui-logo` 文本“政企智能舆情分析”

- 14:30，动作：百度采集模块开发
  - 模块：`collector/service.py`, `collector/routes.py`
  - 接口：`GET /api/collect`
  - 参数：`q/keyword`, `limit`, `pn`
  - 返回：`title`, `cover`, `url`, `source`
  - 要点：移除 `summary`；英文 key；分页聚合；可选 `BAIDU_COOKIE`

- 15:10，动作：后台“数据采集管理”页面搭建
  - 模块：`admin/collect.html`, `admin/routes.py`
  - 内容：输入关键字、进度条、橱窗列表（封面/标题/来源）、批量存储、深度采集按钮与状态

- 16:00，动作：深度采集实现
  - 模块：`admin/routes.py(collect_deep)`, `models(CollectionDetail)`
  - 行为：抓取原文 HTML，提取正文与 `final_url`，保存详情，返回 `preview`
  - 注意：清理脚本/样式标签，限制正文长度；返回弹窗预览与原文链接

- 17:00，动作：新增新华爬虫（四川要闻）
  - 模块：`collector/service.py(fetch_xinhua_sichuan)`, `collector/routes.py(/collect/xinhua)`
  - 数据源：`https://sc.news.cn/scyw.htm`
  - 返回与百度一致：`title`, `cover`, `url`, `source(新华网)`

- 17:40，动作：README 编写
  - 模块：`README.md`
  - 内容：环境、配置、启动、迁移、接口说明与开发指引

---

## 2025-12-05
- 09:10，动作：采集规则库表头与表单优化
  - 模块：`templates/admin/rules.html`
  - 要点：将“站点”改为“域名”，新增“站点名称”字段（与来源名匹配）

- 09:40，动作：规则复制功能
  - 模块：`admin/routes.py(/rules/copy)`, `models(CrawlRule)`
  - 行为：复制生成与原规则内容完全一致的新规则，取消 `site` 唯一约束以支持重复域名多规则
  - 迁移：`flask db migrate -m "remove unique on crawl_rule.site" && flask db upgrade`

- 10:20，动作：数据仓库与规则库联动
  - 模块：`admin/routes.py(warehouse_list, warehouse_deep_collect)`, `templates/admin/warehouse.html`
  - 行为：按来源名与 URL 域名匹配多个规则，仓库列表显示“匹配规则”徽章；深度采集依次尝试规则直至成功

- 11:30，动作：AI 引擎管理模块
  - 模型：`models(AIEngine)` 字段：`provider`, `api_url`, `api_key`, `model_name`, `enabled`
  - 接口：`/admin/ai_engines/*`（列表/新增/修改/删除）
  - 页面：`templates/admin/ai_engines.html` 橱窗卡片展示、就地编辑与批量删除
  - 导航：`templates/base.html` 增加菜单入口
  - 迁移：`flask db migrate -m "add AIEngine" && flask db upgrade`

- 12:00，动作：README 文档更新
  - 模块：`README.md`
  - 内容：补充规则库与仓库联动、AI 引擎管理、模型与迁移变更说明、安全提示

## 记录规范
- 每次重要改动在此文件追加新条目，保持简洁与可检索性
- 优先记录：接口变更、模型变更、迁移命令、运行与调试命令、常见问题与解决方法、提示词与抓取策略
- 如涉及敏感信息（Cookie、密钥等），仅记录说明，不写入实际值
