
⚽

World Cup 2026 Predictor
AI赛事预测平台

概要设计文档 (HLD)

版本: v1.0  |  日期: 2026年5月1日  |  概要设计阶段


目录
TOC \h \o &quot;1-3&quot;



1. 文档说明
1.1 文档定位
本文档是 World Cup 2026 Predictor 项目的概要设计文档（High-Level Design），基于 PRD v1.0 编写。本文档定义系统架构、模块划分、数据流、技术选型和分阶段实现计划，不深入到接口级别的详细设计。
1.2 读者对象
详细设计负责人：基于本文档拆解各模块的 API、Schema、类图
开发团队：理解整体架构和模块边界
项目负责人：确认分阶段计划和资源分配
1.3 术语约定
术语
说明
EV (Expected Value)
期望值，模型概率 vs 赔率隐含概率的差值
+EV / 正EV
模型认为被低估的机会，即赔率有价值
ROI
投资回报率，模型累计表现的核心指标
红单 / 黑单
预测命中 / 预测未命中
xG (Expected Goals)
预期进球数，衡量射门质量的高级统计
Dixon-Coles
修正低比分偏差的泊松模型变体

2. 系统全景架构
2.1 架构总览
系统采用前后端分离、双语言后端架构。Java (Spring Boot) 负责业务服务（用户、订阅、内容分发），Python (FastAPI) 负责数据采集、ML 训练与推理。两者通过 Kafka 消息队列和共享数据库协作。
系统分为以下六层：
层次
职责
核心技术
① 数据采集层
外部数据源接入、爬取、清洗、入库
Python, Scrapy, Celery, Kafka
② ML 引擎层
特征工程、模型训练、推理、赔率分析
Python, FastAPI, scikit-learn, XGBoost, MLflow
③ 业务服务层
用户、订阅、内容分发、权限控制
Java, Spring Boot, Spring Security
④ 内容生成层
AI分析报告、分享卡片、推送内容
Python, LLM API, Pillow/Canvas
⑤ 前端层
用户界面、数据可视化、交互
React, TypeScript, TailwindCSS, Recharts
⑥ 运维监控层
系统监控、业务指标、运营后台
Prometheus, Grafana, PostHog, GA
2.2 数据流全景
系统的核心数据流可以概括为以下主链路：

外部数据源 → 数据采集 &amp; 清洗 → PostgreSQL 数据库 → ML 特征工程 &amp; 推理 → 预测结果 + 赔率分析 → API 分发 → 前端展示

并行链路：预测结果 → 内容生成（AI报告 + 分享卡片）→ 推送服务 → 用户触达。赛后链路：比赛结果回收 → 战绩自动更新 → 红单卡片生成 → 营销素材分发。

3. 模块划分
系统共划分为 8 个一级模块，每个模块内部可进一步拆解子模块。下面逐一说明各模块的职责边界、子模块拆解和核心技术选型。
3.1 M1 — 数据采集模块 (Data Ingestion)
职责：从外部数据源获取比赛、统计、赔率、伤病等数据，统一清洗后写入数据库。
技术栈：Python, Scrapy, BeautifulSoup, Celery, Redis (broker), Kafka
3.1.1 子模块拆解
子模块
数据源
采集方式
采集频率
赛程基座
API-Football
REST API
每日 1次 + 比赛日实时
高级统计
FBref
爬虫
比赛结束后采集
身价 &amp; 伤病
Transfermarkt
爬虫
每周 2次
赔率数据
the-odds-api / OddsPortal
API + 爬虫
赛前 24h 每小时
国家队历史
GitHub 开源数据集
静态导入
一次性
StatsBomb Open Data
StatsBomb
免费 API
补充采集
3.1.2 数据抽象层设计原则
所有数据源通过统一的 DataSource Adapter 抽象接入，写入同一套数据模型。换源时只需替换 Adapter，不影响下游。Adapter 接口包括：fetch_matches()、fetch_stats()、fetch_odds()、fetch_injuries() 等标准方法。每个 Adapter 内部处理反爬策略、速率限制、重试逻辑。
3.1.3 数据质量保障
数据入库前进行 schema validation（字段类型、范围、非空约束）
爬虫失败时自动重试 + 告警通知（发送到监控系统）
数据变更日志（audit trail），方便排查数据问题
3.2 M2 — ML 引擎模块 (ML Engine)
职责：特征工程、模型训练、推理服务、赔率价值分析。
技术栈：Python, FastAPI, scikit-learn, XGBoost, PyTorch, MLflow, ONNX
3.2.1 子模块拆解
子模块
职责
说明
特征工程
原始数据 → 模型特征
Elo评分、近N场战绩、xG指标、伤病影响等50+维特征
模型训练
离线训练 &amp; 回测
支持多模型并行训练，MLflow 版本管理
推理服务
FastAPI 提供预测 API
输入比赛 ID，输出胜平负/比分/大小球概率
赔率分析器
模型概率 vs 赔率对比
计算 EV、标记正EV机会、按价值排序
蒙特卡洛模拟
赛事整体模拟
每队出线概率、夺冠概率，赛事期间实时更新
3.2.2 模型演进路线
阶段
模型
输出
难度
Stage 1
Poisson Baseline
每队期望进球 → 胜平负/比分
⭐⭐
Stage 2
Dixon-Coles
修正低比分偏差 + 时间衰减
⭐⭐⭐
Stage 3
XGBoost/LightGBM
50+特征融合，结合身价/xG/伤病
⭐⭐⭐⭐
Stage 4
Ensemble + Deep Learning
多模型融合，含置信度区间
⭐⭐⭐⭐⭐
3.2.3 核心评估指标
模型的核心目标不是“预测准确率最大化”，而是“发现赔率定价偏差”。具体评估指标：对模型标记为正 EV 的比赛，假设每场等额下注，长期 ROI 是否为正。同时追踪命中率、Brier Score、校准曲线。
3.3 M3 — 业务服务模块 (Business Service)
职责：用户管理、订阅体系、内容分发、权限控制。
技术栈：Java, Spring Boot, Spring Security, JWT, PostgreSQL
3.3.1 子模块拆解
子模块
职责
用户服务
注册、登录、第三方OAuth、用户画像
订阅服务
三层订阅管理（免费/基础/高阶）、支付集成（支付宝/微信支付）、订阅生命周期
内容分发
根据用户订阅层级返回不同粒度的数据（免费用户只看胜平负，付费看详细分析）
权限控制
RBAC 角色权限，前端付费墙渲染控制
比赛服务
赛程、积分榜、淘汰赛对阵图数据提供
3.3.2 用户分层体系设计原则
免费层让用户感受到足够价值并产生信任，付费墙卡在竞猜用户最需要的决策点上。免费用户可见胜平负预测结果、赛程积分榜、战绩记录和分享卡片。基础订阅解锁比分/大小球/让球、赔率价值信号、AI分析报告、高价值推送。高阶订阅进一步解锁 xG/伤病详细面板、模型置信度筛选、历史回测数据。
3.4 M4 — 内容生成模块 (Content Generation)
职责：AI 分析报告生成、社交分享卡片生成、营销素材自动化。
技术栈：Python, LLM API (Claude/GPT), Pillow, HTML→Image, Celery
3.4.1 子模块拆解
子模块
职责
触发时机
AI 赛前报告
调用 LLM 生成中文深度分析
赛前 6-12 小时自动触发
预测分享卡片
生成精美图片，适配微信/微博/抖音/X
预测发布时自动生成
红单战绩卡片
赛后自动标记结果，生成战绩截图
比赛结束后自动触发
营销素材生成
自动生成推文/短视频脚本素材
赛前/红单后自动生成
3.4.2 不可篡改时间戳
所有预测发布时生成带时间戳的快照，写入只追加的审计表，发布后不可修改。这是建立用户信任的核心机制——红单时的公信力完全依赖于这一点。建议后期引入哈希链或第三方存证增强可信度。
3.5 M5 — 战绩 &amp; ROI 追踪模块 (Track Record)
职责：赛后自动更新预测结果，统计累计战绩，提供公开 ROI 仪表盘。
技术栈：Java/Python, PostgreSQL, Redis (缓存)
3.5.1 核心功能
赛后自动拉取比赛结果，与预测进行比对，标记红单/黑单
统计维度：按盘口类型（胜平负/比分/大小球/让球）、按置信度、按时间范围
累计 ROI 曲线：假设每场等额下注，实时计算累计收益
连红记录、最佳命中场次等营销性指标
3.5.2 设计要点
战绩页面是公开可访问的（无需登录），作为最强的营销素材。ROI 数据通过 Redis 缓存，避免每次请求重新计算。
3.6 M6 — 社交传播 &amp; 推送模块 (Social &amp; Push)
职责：分享链接管理、UTM追踪、推送通知。
技术栈：Java/Python, 微信服务号 API, Firebase/JPush, Redis
3.6.1 子模块拆解
子模块
职责
分享链接服务
生成带 UTM 参数的短链接，追踪每次分享的来源渠道、注册转化、付费转化
推送服务
发现高 EV 机会时主动推送给订阅用户（微信服务号 + App + 邮件）
平台适配
根据平台规则适配分享卡片尺寸（微信 1:1、微博 16:9、抖音 9:16、X 16:9）
3.7 M7 — 前端应用模块 (Frontend)
职责：用户界面、数据可视化、交互体验。
技术栈：React, TypeScript, TailwindCSS, Recharts, D3.js, Next.js (SSR/SSG)
3.7.1 页面规划
页面
内容
访问权限
首页 / 赛程页
比赛列表、今日预测、价值信号标签
全部公开
比赛详情页
预测概率、赔率对比、EV分析、数据面板
免费看胜平负，付费解锁详细
AI 分析报告页
中文深度分析、模型判断依据
付费用户
战绩 / ROI 页
累计战绩、ROI曲线、历史预测记录
全部公开（营销页）
群组 &amp; 淘汰赛页
积分榜、淘汰赛对阵图、出线概率
全部公开
个人中心
订阅管理、推送设置、收藏的比赛
登录用户
后台管理页
运营数据看板（详见 M8）
管理员
3.7.2 设计原则
移动优先：主要用户通过手机访问，响应式设计优先考虑移动端
中文排版优化：字体、行距、标点符号等适配中文阅读习惯
付费墙体验：锁定内容显示模糊预览 + 解锁提示，而不是完全隐藏
SSR/SSG：关键页面服务端渲染，保证 SEO 和社交分享 OG 标签正确
i18n：架构预留国际化支持，先做中文，后期扩展英文
3.8 M8 — 运营监控模块 (Ops &amp; Analytics)
职责：系统监控、业务指标、运营数据看板。
技术栈：Prometheus, Grafana, Google Analytics, PostHog/Mixpanel
3.8.1 两类监控
类别
监控内容
工具
系统监控
API 响应时间、爬虫状态、模型推理延迟、错误率、服务健康
Prometheus + Grafana
业务监控
流量渠道、用户漏斗、订阅收入、内容表现、分享追踪
GA + PostHog
3.8.2 运营后台看板
运营后台是独立的管理员页面，集成以下看板：流量来源 &amp; 实时 UV/PV、用户漏斗转化率、MRR/ARPU/订阅趋势、单场比赛热度 &amp; 分享数据、系统健康状态。前期建议用 GA + PostHog 等现成工具搞定，不需要从零开发。

4. 数据架构概要
4.1 核心数据实体
以下是系统的核心数据实体列表，具体字段级别的 Schema 由详细设计阶段定义。
实体
说明
存储
Team
球队基本信息（俱乐部 + 国家队）
PostgreSQL
Player
球员信息、身价、伤病状态
PostgreSQL
Match
比赛基本信息、比分、赛事、轮次
PostgreSQL
MatchStats
比赛统计数据（射门、传球、xG等）
PostgreSQL
Odds
多家博彩公司赔率快照（时间序列）
PostgreSQL
Prediction
模型预测结果（不可变更）
PostgreSQL
PredictionResult
赛后结果比对（红单/黑单）
PostgreSQL
User
用户信息、订阅状态
PostgreSQL
Subscription
订阅记录、支付历史
PostgreSQL
ShareLink
分享链接 &amp; UTM 追踪数据
PostgreSQL
AnalysisReport
AI 生成的中文分析报告
PostgreSQL + S3
ShareCard
生成的分享卡片图片
S3/MinIO
4.2 存储策略
存储
用途
PostgreSQL
核心业务数据（比赛、球队、预测、用户、订阅）
Redis
缓存（预测结果、ROI统计、热门数据）+ Celery broker
S3 / MinIO
分享卡片图片、AI报告富文本、模型制品
Kafka
数据采集事件流、比赛结果事件、推送触发事件

5. 技术选型汇总
层次
技术
选型理由
Frontend
React + TypeScript + TailwindCSS + Next.js
SSR/SSG 支持 SEO 和社交分享，生态成熟
可视化
Recharts + D3.js
图表类用 Recharts 快速实现，复杂可视化用 D3
API Gateway
Spring Cloud Gateway / Kong
统一入口、限流、路由、认证
Backend - 业务
Java + Spring Boot
用户、订阅、内容分发，企业级框架稳定成熟
Backend - ML
Python + FastAPI
ML 生态完善，FastAPI 高性能异步
数据采集
Python + Scrapy + Celery
定时任务 + 爬虫框架成熟
消息队列
Kafka
数据采集事件驱动，解耦模块间通信
ML 框架
scikit-learn + XGBoost + PyTorch + MLflow
从简单到复杂逐步演进
数据库
PostgreSQL + Redis
关系型主库 + 缓存
对象存储
S3 / MinIO
图片、报告、模型制品
容器 &amp; 编排
Docker + Kubernetes
模块化部署、弹性伸缩
CI/CD
GitHub Actions
自动化测试、构建、部署
IaC
Terraform
基础设施代码化
监控
Prometheus + Grafana + GA + PostHog
系统 + 业务双维度

6. 分阶段实现计划
2026 世界杯 6 月 11 日开赛，倒推约 11-15 周完整开发时间。以下将系统分为 5 个阶段逐步实现，每个阶段有明确的交付物和模块范围。
6.1 Phase 1 — 数据基座（2-3周）
目标：搭建数据采集和存储基础设施，采集全部历史数据。
涉及模块：M1 (数据采集)
任务
说明
交付物
数据库 Schema 设计
定义核心实体表结构
PostgreSQL 迁移脚本
数据源 Adapter 开发
实现各数据源的采集适配器
API-Football、FBref、Transfermarkt Adapter
历史数据采集
2022世界杯至今的比赛 &amp; 统计数据
4000-5000 场比赛数据入库
赔率数据采集
接入赔率 API / 爬虫
历史赔率数据入库
数据清洗 Pipeline
Celery 定时任务 + Kafka 事件流
自动化采集流水线
6.2 Phase 2 — ML Baseline（2-3周）
目标：建立基线模型，实现预测和赔率分析能力。
涉及模块：M2 (ML 引擎)
任务
说明
交付物
Poisson Baseline
实现基础泊松回归模型
胜平负、比分概率输出
特征工程 v1
Elo、近N场战绩、主客场等基础特征
特征计算 Pipeline
历史回测
用历史数据验证模型效果
回测报告（命中率、ROI）
赔率分析器
模型概率 vs 赔率对比、EV 计算
EV 分析服务
FastAPI 推理服务
封装模型为 REST API
/predict 、/odds-analysis 接口
MLflow 设置
模型版本管理
MLflow 实验追踪环境
6.3 Phase 3 — 前端 MVP + 核心业务（2-3周）
目标：可用的前端产品，包含预测展示、战绩系统、分享卡片、用户订阅。
涉及模块：M3 (业务服务) + M4 (内容生成) + M5 (战绩) + M6 (社交) + M7 (前端)
任务
说明
交付物
前端页面开发
赛程页、详情页、战绩页、个人中心
React 前端应用
用户服务
注册、登录、JWT 认证
用户 API
订阅服务
三层订阅 + 支付宝/微信支付
订阅管理 + 支付集成
战绩系统
赛后自动更新 + ROI 统计
公开战绩页
分享卡片生成
预测卡片 + 红单卡片
自动生成 + 一键分享
付费墙实现
免费/付费内容分层展示
权限控制体系
6.4 Phase 4 — 模型进化 + 内容生成（2-3周）
目标：提升模型能力，上线 AI 分析报告和推送功能。
涉及模块：M2 (ML 进阶) + M4 (内容生成) + M6 (推送)
任务
说明
交付物
Dixon-Coles 模型
低比分修正 + 时间衰减
模型 v2
XGBoost 模型
50+ 特征融合
模型 v3
特征工程 v2
加入 xG、伤病、身价、赛程密度
完整特征 Pipeline
AI 中文报告
LLM 生成赛前深度分析
自动化报告生成
推送服务
高EV机会自动推送
微信 + App 推送
蒙特卡洛模拟
整届赛事模拟
出线/夺冠概率页面
6.5 Phase 5 — 产品化 &amp; 上线（2-3周）
目标：生产环境部署、监控、性能优化、高级功能。
涉及模块：M7 (前端增强) + M8 (运营监控) + 全局优化
任务
说明
交付物
K8s 部署
全套服务容器化部署
Helm Charts + Terraform
CI/CD 流水线
自动化测试、构建、部署
GitHub Actions Pipeline
运营后台
流量、漏斗、收入看板
管理员看板页面
性能优化
Redis 缓存、CDN、数据库索引
性能测试报告
高级可视化
比分热力图、交互式 bracket
P2 功能页面
多语言支持
英文版本基础框架
i18n 基础设施
6.6 分阶段模块覆盖总览
模块
Phase 1
Phase 2
Phase 3
Phase 4
Phase 5
M1 数据采集
⭐ 核心
—
—
—
—
M2 ML 引擎
—
⭐ 核心
—
⭐ 进阶
—
M3 业务服务
—
—
⭐ 核心
—
—
M4 内容生成
—
—
⭐ 基础
⭐ 完整
—
M5 战绩追踪
—
—
⭐ 核心
—
—
M6 社交推送
—
—
⭐ 基础
⭐ 推送
—
M7 前端
—
—
⭐ MVP
—
⭐ 增强
M8 运营监控
—
—
—
—
⭐ 核心

7. 非功能需求概要
维度
要求
实现策略
性能
预测页加载 &lt; 2s，ML 推理 &lt; 500ms
Redis 缓存、CDN、数据库索引优化
可用性
比赛日 99.5% SLA
K8s 多副本、健康检查、自动恢复
扩展性
支持比赛日流量峰值
K8s HPA 自动扩缩容
安全性
HTTPS、JWT 认证、数据加密
Spring Security + Let&apos;s Encrypt
数据一致性
预测发布后不可篡改
只追加审计表 + 哈希验证
合规性
定位为赛事数据分析平台
不提供下注功能、加入免责声明

8. 模块间依赖关系
以下是模块间的核心依赖关系，确定了分阶段实现的先后顺序：
上游模块
下游模块
依赖内容
M1 数据采集
M2 ML 引擎
ML 依赖数据采集的比赛/统计/赔率数据
M2 ML 引擎
M3 业务服务
业务层调用 ML 推理 API 获取预测结果
M2 ML 引擎
M4 内容生成
报告和卡片基于模型预测结果生成
M2 ML 引擎
M5 战绩追踪
战绩系统对比预测结果与实际结果
M3 业务服务
M7 前端
前端通过业务 API 获取数据
M4 内容生成
M6 社交推送
推送内容来自内容生成模块
M1-M7 所有模块
M8 运营监控
监控采集所有模块的指标

9. 风险与对策
风险
影响
对策
数据源不稳定（爬虫被封、API变更）
数据断供影响预测
多数据源备份 + Adapter 抽象层快速换源
模型预测表现不佳
影响用户信任和付费转化
多模型集成 + 透明展示置信度
开发周期紧张（6月11日开赛）
功能不全上线
MVP 优先 + P0/P1 严格排序
比赛日流量峰值
服务性能压力
CDN + Redis 缓存 + K8s 自动扩缩
合规风险（博彩相关政策）
产品运营受限
定位为数据分析平台 + 免责声明 + 不提供下注链接

10. 下一步：详细设计输入
本概要设计文档将作为详细设计阶段的输入。详细设计需要在每个阶段开始前完成对应模块的详细设计，包括但不限于：
详细设计内容
对应模块
交付时机
数据库 Schema（表结构、索引、约束）
M1
Phase 1 开始前
API 接口设计（RESTful 端点、请求/响应格式）
M2, M3
Phase 2 开始前
特征工程详细设计（各特征计算逻辑）
M2
Phase 2 开始前
前端组件设计（页面结构、状态管理）
M7
Phase 3 开始前
支付集成设计（支付宝/微信支付流程）
M3
Phase 3 开始前
AI 报告 Prompt 设计 &amp; 模板
M4
Phase 4 开始前
K8s 部署架构（Helm、服务拓扑）
全局
Phase 5 开始前

— 文档结束 —

