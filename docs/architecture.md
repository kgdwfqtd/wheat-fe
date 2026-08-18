# 项目架构说明

## 目标

把当前项目从“单一 Streamlit + 兼容 API”的混合结构，逐步调整为一个清晰的三层架构：

- UI 层：负责展示与表单交互
- Service 层：负责核心业务逻辑
- Repository 层：负责数据库访问与外部数据操作

## 当前状态

- Streamlit 仍然承担桌面端 / 管理端页面
- FastAPI 负责移动端数据采集 API
- 两个前端都需要访问共享的业务逻辑
- 重构目标是让它们共享同一套 Service / Repository，而不是让页面直接写数据库

## 建议方向

### 1. 继续保留 Streamlit

不建议在当前阶段彻底移除 Streamlit，因为：

- 现有管理端功能已经完整依赖它
- 移除成本高、风险也高
- 这不是“架构缺陷”，而是“拓展需求导致的混合架构”

### 2. 保留 FastAPI

移动端 API 是一个合理的独立接口层，适合用于现场数据采集、鉴权和小程序/手机端访问。

### 3. 逐步抽象业务逻辑

新的目录结构中，推荐保持：

- `wheat_app/config.py`：配置中心
- `wheat_app/repositories/`：数据库访问层
- `wheat_app/services/`：业务逻辑层
- `pages/`：Streamlit 页面
- `mobile_api/`：移动端 FastAPI 接口

## 未来重构路线

1. 把页面所有数据库查询收敛到 service 层
2. 让 API 和 Streamlit 共享同一套 repository/service
3. 在必要时再评估是否迁移到更现代的前端框架
4. 仅在业务规模明显扩大时再考虑完全抛弃 Streamlit
