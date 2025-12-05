# 政企智能舆情分析报告生成应用系统

本项目是一个基于 B/S 架构的 Web 应用：前端使用 `layui`，后端为 `Python 3 + Flask + SQLite`。系统提供数据采集、数据规则库、数据仓库、AI 引擎与 AI 清洗分析模块，支持动态爬虫管理、数据分页、以及面向报告生成的分析能力。

**快速入口**
- 首页：`http://127.0.0.1:5000/`
- 登录：`http://127.0.0.1:5000/auth/login`（默认账号 `admin/admin123`）
- 后台：`http://127.0.0.1:5000/admin/`

## 安装与启动
- 创建并激活虚拟环境（Windows PowerShell）
  - `python -m venv venv`
  - `./venv/Scripts/Activate.ps1`
- 安装依赖
  - `python -m pip install --upgrade pip`
  - `python -m pip install -r requirements/requirements.txt`
- 初始化数据库
  - `python -m flask --app app:create_app db init`
  - `python -m flask --app app:create_app db migrate -m "init"`
  - `python -m flask --app app:create_app db upgrade`
- 启动开发服务
  - `python -m flask --app app:create_app run --port 5000 --debug`

## 配置
- 在 `.env/.env` 中设置：
  - `FLASK_ENV=development`
  - `SECRET_KEY=dev`
  - `DATABASE_URL=sqlite:///绝对或相对路径`（可选，默认根目录 `govinfo.db`）
  - `BAIDU_COOKIE=...`（可选，用于提升百度新闻采集的成功率与字段完整度）

## 模块概览
- 采集管理：关键字采集、橱窗展示、批量入库、深度采集（正文提取与预览）
- 数据仓库：分页列表（每页 10 条）、来源与关键字编辑、批量删除、详情采集与预览
- 采集规则库：站点名称/域名，标题/内容 XPath，Headers；支持启用与一键复制
- 爬虫管理：
  - 横向表展示：名称、key、Class、Base URL、启用
  - 智能分析生成：输入“源始地址 + 原始请求头”自动生成爬虫配置
  - 动态参数管理：支持 `dynamic_keys` 标记（如 `keyword/q/word`、`pn/page`、`limit`）
  - Headers 刷新：粘贴原始请求头文本，快速更新失效的 Header
- AI 引擎管理：OpenAI API 范式配置第三方大模型（服务商、API URL、API Key、模型名称、启用），卡片式展示；提供对话测试弹窗
- AI 清洗分析：选择大模型对数据库文章进行分析或清洗建议输出（Demo），为后续工具化操作打基础

## 关键页面与路径
- 采集规则库：`/admin/rules`
- 数据仓库管理：`/admin/warehouse`
- 爬虫管理：`/admin/crawlers`
- AI 引擎管理：`/admin/ai_engines`
- AI 清洗分析：`/admin/ai_clean`

## 通用采集与动态爬虫
- 智能分析生成（爬虫管理）
  - 提交：`POST /admin/crawlers/analyze`，Body：`source_url`, `headers_raw`
  - 行为：解析 `base_url`、`headers_json`、查询参数为默认 `params_json`，并自动识别 `dynamic_keys`
- 刷新请求头（爬虫管理）
  - `POST /admin/crawlers/headers_refresh`，Body：`id`, `headers_raw`
  - 行为：将原始请求头文本解析为 JSON 更新至爬虫配置
- 动态变量查询（按来源）
  - `GET /admin/crawlers/vars_by_source`，Query：`source`
  - 返回：`crawler_id`, `dynamic_keys`
- 运行爬虫（后端自动适配）
  - 若配置了 `class_path`，使用通用爬虫类 `GenericListCrawler`；否则调用入口函数
  - 合并顺序：`params_json` 作为默认值，传入的运行时 `params` 覆盖

## AI 清洗与分析（Demo）
- 页面：`/admin/ai_clean`
- 选择引擎与任务类型（分析/清洗），从 SQLite 表 `article_details` 读取近期数据（最多 50 条，默认 10），将数据摘要传给大模型输出建议或统计
- 测试用表结构（示例）：
  ```sql
  CREATE TABLE article_details (
      id INTEGER NOT NULL,
      crawl_item_id INTEGER NOT NULL,
      title VARCHAR(256),
      content TEXT,
      created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
      PRIMARY KEY (id),
      FOREIGN KEY (crawl_item_id) REFERENCES crawl_items (id),
      UNIQUE (crawl_item_id)
  );
  ```

## 采集 API
- 百度新闻：`GET /api/collect`
  - 参数：`q|keyword`、`limit`（默认 20）、`pn`（分页偏移）
- 新华网（四川要闻）：`GET /api/collect/xinhua`
  - 参数：`limit`、`q|keyword`（按标题包含过滤）

## 开发指南
- 代码结构：
  - 应用工厂与蓝图：`app/__init__.py`
  - 扩展实例：`app/extensions.py`
  - 数据模型：`app/models.py`
  - 管理路由：`app/admin/routes.py`
  - 采集服务：`app/collector/service.py`
- 数据库迁移：
  - `python -m flask --app app:create_app db migrate -m "message"`
  - `python -m flask --app app:create_app db upgrade`

## 常见问题
- `layui is not defined`：确保页面脚本写在 `{% block page_scripts %}` 中，并在 `layui.js` 引入后初始化
- Headers 失效：使用“刷新Headers”功能粘贴原始请求头，立即更新并生效
- 数据库路径：默认根目录 `govinfo.db`，可通过 `DATABASE_URL` 定制

## 安全
- 不要提交真实账号、密码或 Cookie
- `.env/.env` 仅用于本地开发，生产环境请使用安全的配置注入机制
- 不要在仓库提交任何真实的 AI `API Key`

## 参考与状态
- 代码托管：`https://github.com/Suisaaa/GovInfoCheckSystemv2.git`
- 技术栈：Flask、Layui、SQLite；OpenAI 风格模型接口（兼容 Azure）
