# 政企智能舆情分析报告生成应用系统

本项目是基于 B/S 架构的 Web 应用，前端采用 `layui` 组件，后端使用 `Python 3 + Flask + SQLite`。系统包含四大功能模块：数据采集、数据仓库、采集规则库、AI 引擎管理，支持用户登录与角色权限，后台管理与深度采集，并提供与第三方大模型服务的联动能力。

## 目录结构
- `app/` 应用源代码
  - `__init__.py` 应用工厂与蓝图注册
  - `config.py` 配置加载（支持 `.env/.env`）
  - `extensions.py` 扩展实例（SQLAlchemy/Migrate/LoginManager）
  - `models.py` 数据模型（用户、角色、设置、采集项、采集详情、采集规则、AI 引擎）
  - `main/` 基础页面
  - `auth/` 登录与退出
  - `admin/` 后台管理（用户、角色、设置、采集管理、数据仓库、采集规则库、AI 引擎管理）
  - `collector/` 采集服务与接口（百度新闻、新华网）
- `templates/` 页面模板（含 `base.html` 布局与各模块页面）
- `static/` 前端静态资源（请将 `layui-v2.13.2` 放置于 `static/layui`）
- `requirements/requirements.txt` Python 依赖
- `migrations/` 数据库迁移脚本
- `.env/.env` 环境变量文件

## 技术栈
- 后端：Flask、Flask-SQLAlchemy、Flask-Migrate、Flask-Login
- 前端：layui v2.13.2
- 数据库：SQLite（默认 `govinfo.db`）

## 环境准备（Windows PowerShell）
1. 创建虚拟环境
   - `python -m venv venv`
2. 激活虚拟环境
   - `./venv/Scripts/Activate.ps1`
3. 安装依赖
   - `python -m pip install --upgrade pip`
   - `python -m pip install -r requirements/requirements.txt`

## 配置
- `.env/.env` 支持以下变量：
  - `FLASK_ENV=development`
  - `SECRET_KEY=dev`
  - `DATABASE_URL=sqlite:///绝对或相对路径`（可选，不设置时使用项目根目录 `govinfo.db`）
  - `BAIDU_COOKIE=...`（可选，用于提升百度新闻采集的成功率与字段完整度）

## 初始化数据库
- 首次初始化与迁移：
  - `python -m flask --app app:create_app db init`
  - `python -m flask --app app:create_app db migrate -m "init"`
  - `python -m flask --app app:create_app db upgrade`

## 启动
- 开发模式启动：
  - `python -m flask --app app:create_app run --port 5000 --debug`
- 访问：
  - 首页：`http://127.0.0.1:5000/`
  - 登录：`http://127.0.0.1:5000/auth/login`
  - 后台：`http://127.0.0.1:5000/admin/`

## 默认账号与权限
- 首次运行会自动初始化角色与管理员：
  - 管理员账号：`admin`
  - 管理员密码：`admin123`
- 角色：`admin`（全部权限）、`user`（登录后可见基础数据视图）

## 模块概览
- 登录与退出：`app/auth/routes.py`
- 首页与基础页面：`app/main/routes.py`
- 后台管理：`app/admin/routes.py`
  - 用户管理：新增用户与角色分配
  - 角色管理：新增角色与列表视图
  - 系统设置：应用名称与 LOGO 路径设置
  - 数据采集模块：采集关键字、进度提示、橱窗展示、批量存储、深度采集
  - 数据仓库模块：分页列表、编辑来源/关键字、批量删除、详细内容采集与预览
  - 采集规则模块：站点名称/域名、标题/内容 XPath、Headers、启用与复制（复制保持内容一致）
  - AI 引擎模块：以 OpenAI API 范式配置第三方模型（服务商、API URL、API Key、模型名称、启用），支持新增/修改/删除、卡片橱窗和对话测试

## 模块详解
### 数据采集模块
- 路径：`/admin/collect`
- 能力：按关键词采集百度新闻与新华网四川频道，卡片式展示，批量保存到仓库；支持单条“深度采集”。
- 接口：
  - `GET /api/collect`（百度新闻）
  - `GET /api/collect/xinhua`（新华网四川要闻）

### 数据仓库模块
- 路径：`/admin/warehouse`
- 能力：分页显示已存储数据，支持编辑来源与关键字、批量删除、详细内容采集与预览。
- 规则联动：基于“来源”与“URL 域名”自动匹配多个采集规则，依次尝试采集直至成功；列表显示“匹配规则”数量徽章，悬停可查看名称。

### 采集规则模块
- 路径：`/admin/rules`
- 字段：站点名称（与来源名匹配）、域名、标题 XPath、内容 XPath、请求 Headers（JSON/文本支持）、启用。
- 操作：新增、修改、删除、复制（生成与原规则完全一致的新规则）；支持行内编辑。
- 模型与约束：取消 `site` 唯一约束以支持重复域名多规则。

### AI 引擎模块
- 路径：`/admin/ai_engines`
- 字段：服务商、API URL、API Key（掩码显示）、模型名称、启用状态。
- 能力：新增、修改、删除、卡片橱窗展示；“对话测试”支持打开独立聊天页与模型交互。
- 对话测试页：`/admin/ai_engines/chat/<id>`，基于 OpenAI Chat Completions 结构（`model` + `messages`）。

## 采集模块（API）
- 百度新闻采集：`GET /api/collect`
  - 参数：
    - `q` 或 `keyword`：关键词（必填建议）
    - `limit`：返回条目数（默认 20）
    - `pn`：起始页偏移（`0` 第 1 页，`10` 第 2 页……）
  - 返回字段：`title`, `cover`, `url`, `source`
- 新华网（四川要闻）采集：`GET /api/collect/xinhua`
  - 参数：
    - `limit`：返回条目数（默认 20）
    - `q` 或 `keyword`：可选，按标题包含过滤
  - 返回字段：`title`, `cover`, `url`, `source`（固定 `新华网`）

### 返回示例
```json
{
  "keyword": "宜宾",
  "count": 10,
  "items": [
    {
      "title": "示例标题",
      "cover": "https://.../img.jpg",
      "url": "https://...",
      "source": "新华网"
    }
  ]
}
```

## 深度采集
- 后端：`POST /admin/collect/deep`
  - Body（JSON）：`url`, `title`, `cover`, `source`, `keyword`
  - 行为：抓取原文，清理噪声，提取正文与 `final_url`，入库 `CollectionDetail`
  - 返回：`status`, `item_id`, `detail_id`, `preview`, `final_url`
- 前端：在“数据采集管理”页面每条卡片提供“深度采集”按钮，并弹窗预览

## 规则库与仓库联动
- 规则库（`/admin/rules`）维护站点名称（来源名）、域名与 XPath/Headers
- 数据仓库（`/admin/warehouse`）支持基于“来源”与“URL 域名”自动匹配多个规则，并依次尝试采集直至成功
- 仓库列表显示“匹配规则”数量徽章，悬停可查看具体规则名称
- 规则复制功能：支持一键复制为一条与原规则内容完全相同的新规则

## AI 引擎管理
- 页面路径：`/admin/ai_engines`
- 支持以卡片橱窗展示多个大模型配置，字段：服务商、API URL、API Key（掩码显示）、模型名称、启用状态
- 提供新增、修改、删除接口（`/admin/ai_engines/*`）以便后续与大模型交互功能调用
- 对话测试：打开独立聊天页，输入消息后调用配置好的模型进行响应展示。

## 数据模型
- `CollectionItem`：采集基础信息
  - `title`, `cover`, `url`(唯一), `source`, `keyword`, `deep_status`, `created_at`
- `CollectionDetail`：深度采集详情
  - `item_id`, `content_text`, `content_html`, `final_url`, `created_at`
- `CrawlRule`：采集规则
  - `name`(站点名称), `site`(域名), `title_xpath`, `content_xpath`, `request_headers`, `enabled`, `created_at`
- `AIEngine`：AI 引擎配置
  - `provider`, `api_url`, `api_key`, `model_name`, `enabled`, `created_at`

## 开发指引
- 新增模型：
  - 在 `app/models.py` 中定义模型
  - 执行迁移与升级：`flask db migrate`、`flask db upgrade`

### 模型与迁移变更说明（近期）
- 新增 `AIEngine` 模型：执行 `flask db migrate -m "add AIEngine" && flask db upgrade`
- `CrawlRule.site` 取消唯一约束以支持规则复制与重复域名多规则：执行 `flask db migrate -m "remove unique on crawl_rule.site" && flask db upgrade`
- 新增蓝图与路由：
  - 在 `app/xxx/__init__.py` 定义蓝图并在 `app/__init__.py` 注册
  - 在 `app/xxx/routes.py` 编写路由逻辑
- 新增页面模板：
  - 在 `templates/` 创建页面文件，并在蓝图路由中渲染
- 引入静态资源：
  - 将前端文件放入 `static` 并通过 `{{ url_for('static', filename='...') }}` 引用

## 常见问题
- 页面脚本报 `layui is not defined`：
  - 请确保子页面脚本写入 `base.html` 提供的 `{% block page_scripts %}` 中（位于 `layui.js` 引入之后），并在 `window.load` 后初始化。
- 采集结果字段缺失：
  - 源站结构或权限导致，设置 `BAIDU_COOKIE` 可提升完整度。
- 数据库文件位置：
  - 默认根目录 `govinfo.db`，可通过 `DATABASE_URL` 重定向。

## 安全与合规
- 请勿在仓库提交任何真实账号、密码或 Cookie
- `.env/.env` 中的敏感信息仅用于本地开发，生产环境建议通过安全的配置注入机制
- AI 引擎的 `API Key` 仅用于本地开发与测试，请勿在公共仓库明文提交实际密钥

## 后续规划
- 后台新增“采集数据列表”页面：分页筛选、删除与导出
- 面向报告生成的分析与模板化输出
- 针对常见媒体源（新华网、四川发布等）增加特定解析策略以提升正文准确性
