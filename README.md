# 纳米铁肥小麦试验记录程序

基于《纳米铁肥在小麦上的应用效果对比试验方案》开发的配套数据记录管理系统。

## 架构目标

当前项目已从“单体 UI 混合数据库逻辑”的模式，逐步转向真正的前后端分离架构：

- 后端：FastAPI，负责数据接口、认证、查询、写入
- 前端：轻量级 HTML/JS 页面或独立前端应用，负责展示和交互
- 业务层：保持 [wheat_app](wheat_app) 的 service/repository 组织方式
- 兼容层：旧版 Streamlit/根目录模块保留，便于平滑迁移

## 快速开始

### 1) 后端启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 FastAPI 后端
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8001
```

后端地址：
- Swagger 文档：http://localhost:8001/docs
- 健康检查：http://localhost:8001/api/v1/health

### 2) 前端访问

```bash
# 可直接用浏览器打开
frontend/index.html
```

也可以使用静态文件服务器：

```bash
python -m http.server 8080
```

然后访问：
- http://localhost:8080/frontend/index.html

### 3) 保留旧版 Streamlit

如果需要继续使用原始桌面版：

```bash
streamlit run app.py
```

## 目录结构

```text
wheat-fe/
├── app.py                         # 旧版 Streamlit 入口（兼容保留）
├── backend/
│   ├── __init__.py
│   └── app.py                    # 新版 FastAPI 后端入口
├── frontend/
│   └── index.html                # 轻量前端示例
├── wheat_app/
│   ├── __init__.py
│   ├── config.py                 # 统一配置中心
│   ├── repositories/
│   ├── services/
│   └── public_api.py             # 统一公开入口
├── pages/                        # 旧版 Streamlit 页面
├── mobile_api/                   # 历史兼容接口（逐步替换）
├── database.py                   # 旧数据库兼容层
├── config.py                     # 兼容层
├── .env.example                  # 环境变量示例
├── requirements.txt
├── README.md
└── experiment.db
```

> 说明：新架构中，后端不再依赖 Streamlit 页面，前端通过 HTTP 接口获取数据，数据逻辑仍由 [database.py](database.py) 和 [wheat_app](wheat_app) 的 repository/service 层提供。

## 模块职责

| 层次 | 责任 |
|------|------|
| Frontend | 页面渲染、交互、表单提交 |
| Backend API | 数据查询、写入、认证、权限 |
| Service | 业务聚合、字段校验、业务规则 |
| Repository | 数据库访问、CRUD、导出 |
| Legacy UI | 旧版 Streamlit 保留，过渡期兼容 |

## 功能模块

| 模块 | 功能 |
|------|------|
| 首页仪表盘 | 数据概览、录入进度、最近操作 |
| 小区管理 | 18 个小区初始化、田间布局展示 |
| 土壤数据 | 播前/收获后土壤理化性质 |
| 物候期 & 出苗 | 生育期记录、出苗率调查 |
| 农艺性状 | 分蘖、株高、叶面积、干重 |
| 生理指标 | SPAD、光合、活性铁、酶活性 |
| 产量数据 | 产量构成、实产、收获指数 |
| 品质数据 | 蛋白质、面筋、铁含量 |
| 操作日志 | 拌种/喷施/日常管理记录 |
| 数据导出 | Excel 导出、空白模板、图表 |

## 技术栈

- **后端**: FastAPI + Pydantic
- **前端**: HTML + JavaScript（可后续切换到 React/Vue）
- **数据库**: PostgreSQL / 兼容现有 SQLite/PG 逻辑
- **导出**: Excel (openpyxl)
- **图表**: Plotly / 前端绘图

## 试验处理

| 代号 | 名称 | 铁肥用量 |
|------|------|----------|
| CK | 空白对照 | 0 |
| FS | 硫酸亚铁 | 2.0 kg/亩 |
| NF-0.5 | 纳米铁半量 | 0.5 g/亩 |
| NF-1.0 | 纳米铁标准量 | 1.0 g/亩 |
| NF-1.5 | 纳米铁1.5倍量 | 1.5 g/亩 |
| NF-2.0 | 纳米铁2倍量 | 2.0 g/亩 |

× 3 个区组（Ⅰ、Ⅱ、Ⅲ）= 18 个小区

## 数据文件

- `experiment.db` — 当前本地数据库
- 导出文件为 `.xlsx` 格式
