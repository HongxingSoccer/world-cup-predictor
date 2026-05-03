# 设计文档（权威）

本目录包含 World Cup 2026 Predictor 项目的完整设计文档原文，是所有实现的**权威依据**。
代码与本目录冲突时，以本目录为准（除非另有书面变更说明）。

| 文件 | 内容 |
|------|------|
| [01_PRD.md](01_PRD.md) | 产品需求文档：定位、用户分层、P0/P1/P2 功能、ML 演进路线、合规、5 阶段路线图 |
| [02_HLD.md](02_HLD.md) | 概要设计：8 个模块 M1-M8、双语言后端、技术选型、数据架构、阶段覆盖矩阵 |
| [03_Phase1_DataFoundation.md](03_Phase1_DataFoundation.md) | Phase 1 数据基座：完整 PostgreSQL Schema、6 个 Adapter、Celery+Kafka 流水线 |
| [04_Phase2_MLBaseline.md](04_Phase2_MLBaseline.md) | Phase 2 ML Baseline：28 个 v1 特征、Poisson、FastAPI 接口、EV 分析、MLflow、回测 |
| [05_Phase3_FrontendMVP.md](05_Phase3_FrontendMVP.md) | Phase 3 前端 MVP + 核心业务：用户/订阅/支付/战绩/分享卡片/付费墙/React 页面 |
| [06_Phase4_ModelEvolution.md](06_Phase4_ModelEvolution.md) | Phase 4 模型进化：Dixon-Coles MLE、XGBoost 5 子模型、特征 v2、AI 中文报告、推送、蒙特卡洛 |
| [07_Phase5_Productization.md](07_Phase5_Productization.md) | Phase 5 产品化：K8s 部署、CI/CD、运营后台、性能优化、高级可视化、i18n |

## 重要约定

- 模块编号 **M1-M8**（数据采集 / ML 引擎 / 业务服务 / 内容生成 / 战绩追踪 / 社交推送 / 前端 / 运营监控）
- 后端：**Java Spring Boot**（用户/订阅/内容分发）+ **Python FastAPI**（数据/ML/推理）
- 数据库：PostgreSQL 15+；表名复数 snake_case，PK `BIGSERIAL`，时间 `TIMESTAMPTZ`
- API 前缀：`/api/v1/`
- 模型评估目标：**ROI 为正**，而不是单纯的命中率最大化
- 合规：定位"赛事数据分析平台"，不提供下注链接，含免责声明

## Phase 4 关键 Schema/接口（本次对齐目标）

| 实体 | 表名 | 关键字段 |
|------|------|----------|
| AI 报告 | `analysis_reports` | match_id, prediction_id, content_md, content_html, summary, model_used, prompt/completion_tokens, status, generated_at, published_at |
| 推送记录 | `push_notifications` | user_id, channel, notification_type, title, body, target_url, status, sent_at, clicked_at, meta |
| 用户推送设置 | `user_push_settings` | user_id (UNIQUE), wechat_openid, web_push_subscription, enable_high_ev/reports/match_start/red_hit, quiet_hours_start/end |
| 蒙特卡洛 | `simulation_results` | simulation_version, num_simulations, model_version, results (JSONB), computed_at |

| API | 说明 |
|-----|------|
| `GET /api/v1/matches/{id}/report` | AI 报告（付费） |
| `GET /api/v1/worldcup/simulation` | 夺冠概率排行（公开） |
| `GET /api/v1/worldcup/team/{id}/path` | 某队晋级路径 |
| `GET/PUT /api/v1/push/settings` | 推送设置 |
| `POST /api/v1/push/test` | 测试推送（管理员） |
| `POST /api/v1/predict?model_version=` | 支持 dixon_coles/xgboost/ensemble |
| `GET /api/v1/models/compare?match_id=X` | 多模型对比 |
| `POST /api/v1/simulation/run` | 触发模拟 |
| `GET /api/v1/simulation/latest` | 最新模拟结果 |

## 文档生成方式

由 `.docx` 提取（保留 git 友好的纯文本格式）：

```bash
unzip -p file.docx word/document.xml | python3 -c "import sys,re;t=sys.stdin.read();t=re.sub(r'</w:p>','\n',t);t=re.sub(r'<[^>]+>','',t);print(t)"
```

原始 docx 在仓库外：`/Users/dbaa/Documents/HongxingSoccer/{Requirment,Design,Detial_Design}/`
