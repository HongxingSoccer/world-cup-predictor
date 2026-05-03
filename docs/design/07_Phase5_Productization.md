





⚽
World Cup 2026 Predictor
AI赛事预测平台
Phase 5 — 产品化 &amp; 上线 详细设计文档


版本: v1.0  |  日期: 2026年5月1日  |  详细设计阶段

1. 文档说明
1.1 文档定位
本文档是 Phase 5（产品化 &amp; 上线）的详细设计文档，是整个项目的收官阶段。Phase 5 涉及 M7 前端增强、M8 运营监控和全局优化，目标是完成 Kubernetes 生产部署、CI/CD 流水线、运营后台、性能优化、高级可视化和多语言支持基础设施。世界杯 2026年6月11日开赛，本阶段必须在此之前全部完成。
1.2 Phase 5 目标回顾
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

2. Kubernetes 生产部署架构
2.1 集群规划
配置项
说明
云服务商
阿里云 ACK / AWS EKS（根据目标市场选择，国内用户为主推荐阿里云）
节点规格
2-3 个 4C8G Worker 节点（日常），比赛日可弹性扩展到 5-6 个
K8s 版本
1.28+
容器运行时
containerd
网络插件
Calico / Flannel
Ingress Controller
NGINX Ingress Controller
证书管理
cert-manager + Let&apos;s Encrypt 自动签发
存储类
阿里云 SSD 云盘 / AWS gp3

2.2 Namespace 划分
Namespace
包含服务
说明
wcp-production
所有生产服务
线上环境
wcp-staging
所有服务的 staging 副本
预发布验证环境
wcp-infra
PostgreSQL, Redis, Kafka, MLflow
基础设施服务
wcp-monitoring
Prometheus, Grafana, Loki
监控栈
cert-manager
cert-manager
证书管理

2.3 服务部署清单
以下是所有 Phase 1-5 服务的完整 K8s 部署配置：
服务
副本数
CPU req
CPU lim
MEM req
MEM lim
HPA
frontend (Next.js)
2
100m
500m
256Mi
512Mi
2-5
java-api (Spring Boot)
2
200m
1000m
512Mi
1Gi
2-6
ml-api (FastAPI)
2
200m
1000m
512Mi
1Gi
2-4
ingestion-worker
1
100m
500m
256Mi
512Mi
-
ingestion-beat
1
50m
200m
128Mi
256Mi
-
card-worker
1
100m
500m
256Mi
512Mi
-
report-worker
1
100m
500m
256Mi
512Mi
-
push-worker
1
100m
500m
256Mi
512Mi
-
settlement-worker
1
100m
500m
256Mi
512Mi
-
simulation-worker
1
200m
1000m
512Mi
1Gi
-
nginx (Ingress)
2
50m
200m
64Mi
128Mi
-
⚠ HPA (Horizontal Pod Autoscaler) 仅对面向用户的服务开启。触发条件：CPU &gt; 70% 或自定义指标（请求延迟 &gt; 500ms）。比赛日高峰期可手动预扩容。

2.4 基础设施服务部署
服务
部署方式
说明
PostgreSQL
阿里云 RDS / AWS RDS
托管数据库，高可用主备，自动备份
Redis
阿里云 Redis / ElastiCache
托管 Redis，2GB 内存，持久化开启
Kafka
阿里云消息队列 Kafka / MSK
托管 Kafka，3 broker，按需扩展
S3/MinIO
阿里云 OSS / AWS S3
对象存储，分享卡片、报告、模型制品
MLflow
K8s Deployment
自建，连接 RDS + S3
ℹ 生产环境强烈推荐使用云服务商托管的数据库和消息队列，避免自行运维。开发环境使用 docker-compose 本地部署。

2.5 Helm Chart 结构
每个服务对应一个 Helm Chart，统一放在 deploy/charts/ 目录下：
deploy/
├── charts/
│   ├── wcp-frontend/          # Next.js 前端
│   ├── wcp-java-api/          # Java 业务服务
│   ├── wcp-ml-api/            # ML 推理服务
│   ├── wcp-workers/           # 所有 Worker 服务
│   ├── wcp-infra/             # 基础设施（开发环境用）
│   └── wcp-monitoring/        # 监控栈
├── terraform/
│   ├── modules/
│   │   ├── k8s-cluster/       # K8s 集群
│   │   ├── rds/               # 数据库
│   │   ├── redis/             # Redis
│   │   ├── oss/               # 对象存储
│   │   └── cdn/               # CDN
│   ├── environments/
│   │   ├── staging/
│   │   └── production/
│   └── main.tf
└── scripts/
    ├── deploy.sh
    └── rollback.sh

3. CI/CD 流水线设计
3.1 GitHub Actions Workflow 总览
Workflow
触发条件
执行内容
ci-test
PR 创建/更新
代码检查、单元测试、集成测试
ci-build
合并到 main 分支
构建 Docker 镜像、推送到容器仓库
cd-staging
ci-build 完成
自动部署到 staging 环境
cd-production
手动批准 / tag 发布
部署到 production 环境
db-migrate
ci-build 含 migration 变更
自动执行数据库迁移
ml-train
手动触发 / 定时
模型训练 + 回测 + MLflow 注册
scheduled-backtest
每周日 00:00
定时模型回测，结果推送到 Slack

3.2 CI 测试流水线详细
步骤
操作
详细
1
代码检查
Python: ruff + mypy；Java: checkstyle + spotbugs；TS: eslint + tsc
2
单元测试
Python: pytest (--cov &gt; 80%)；Java: JUnit5；TS: Jest
3
集成测试
启动 docker-compose 测试环境，运行 API 端到端测试
4
安全扫描
Trivy 容器镜像安全扫描、依赖漏洞检查
5
构建验证
确认所有服务的 Docker 镜像可以成功构建
6
覆盖率报告
生成覆盖率报告并评论到 PR

3.3 CD 部署流程
步骤
操作
详细
1
镜像构建
多阶段 Dockerfile，构建产物推送到 ACR/ECR
2
镜像标签
使用 git SHA 作为镜像 tag，生产同时打版本号 tag
3
Staging 部署
helm upgrade --install 到 staging namespace
4
Staging 烟雾测试
自动运行健康检查 + 核心 API 验证
5
人工审批
Staging 验证通过后，需要人工批准才能进入生产
6
Production 部署
helm upgrade --install 到 production namespace
7
渐进式发布
使用 Rolling Update，maxUnavailable=0, maxSurge=1
8
部署验证
自动健康检查，失败自动回滚到上一版本
9
通知
部署结果推送到 Slack/企业微信
⚠ 生产部署必须在非比赛日进行（避免比赛期间部署导致的服务中断）。紧急修复除外，但需要至少两人确认。

4. 运营监控系统设计 (M8)
4.1 监控架构总览
层次
工具
监控内容
告警方式
系统监控
Prometheus + Grafana
CPU/内存/磁盘/网络、容器状态、Pod 重启
企业微信/Slack
应用监控
Prometheus + Grafana
API 延迟/错误率/QPS、Worker 队列深度
企业微信/Slack
日志监控
Loki + Grafana
应用日志聚合、错误日志告警
Grafana 告警规则
业务监控
PostHog + GA
用户行为、漏斗转化、内容表现
PostHog 自带
爬虫监控
Prometheus + 自定义
爬虫成功率、数据采集延迟、数据源可用性
企业微信/Slack
模型监控
MLflow + 自定义
模型推理延迟、预测准确度漂移
Grafana 告警

4.2 核心告警规则
告警规则
阈值
严重性
通知方式
API 错误率 &gt; 5% (5min window)
5%
Critical
电话 + 企微
API P99 延迟 &gt; 2s
2000ms
Warning
企微
Pod 重启次数 &gt; 3 (30min)
3次
Critical
企微
磁盘使用率 &gt; 85%
85%
Warning
企微
数据库连接池使用率 &gt; 80%
80%
Warning
企微
Celery 队列积压 &gt; 100 任务
100
Warning
企微
爬虫连续失败 &gt; 3 次
3次
Critical
企微
ML 推理延迟 &gt; 1s
1000ms
Warning
企微
Kafka consumer lag &gt; 1000
1000
Warning
企微
SSL 证书到期 &lt; 14 天
14天
Warning
邮件

4.3 Grafana Dashboard 设计
4.3.1 系统总览 Dashboard
面板
内容
服务状态总览
所有服务的 Up/Down 状态、版本号、最后部署时间
请求量 &amp; 延迟
QPS 曲线 + P50/P90/P99 延迟分布
错误率趋势
HTTP 5xx/4xx 比例趋势图
资源使用
各服务 CPU/内存使用率热力图
数据库指标
连接数、慢查询数、TPS、缓存命中率
Kafka 指标
消息生产/消费速率、consumer lag

4.3.2 业务监控 Dashboard
面板
内容
今日预测概览
今日比赛数、已生成预测数、价值信号数
战绩实时统计
最新命中率、ROI、连红记录
用户漏斗
访问→注册→免费活跃→试用付费→正式订阅→续费
订阅趋势
各层订阅人数、MRR、ARPU 趋势图
内容表现
各比赛页面浏览量、分享次数、报告阅读量
推送效果
推送送达率、点击率、各类型推送的转化率
爬虫状态
各数据源最后采集时间、成功率、数据覆盖率

4.4 运营后台管理页面
运营后台是独立的管理员页面，集成在前端 /admin/* 路由下，需要 admin 角色的 JWT Token。
4.4.1 后台页面清单
路由
页面
功能
/admin
总览 Dashboard
核心业务指标卡片 + 今日预测状态
/admin/users
用户管理
用户列表、搜索、订阅状态查看/修改
/admin/subscriptions
订阅管理
订阅列表、收入统计、退款处理
/admin/predictions
预测管理
预测列表、结算状态、手动结算
/admin/reports
AI 报告管理
报告列表、重新生成、预览
/admin/data-sources
数据源状态
各爬虫状态、最后采集时间、手动触发
/admin/push
推送管理
推送记录、手动发送推送、推送统计
/admin/content
内容管理
分享卡片库、营销素材、热门内容排行
/admin/system
系统设置
环境变量、功能开关、缓存清理

4.4.2 功能开关系统 (Feature Flags)
通过功能开关可以在不部署代码的情况下开启/关闭特定功能，用于灰度发布和紧急降级：
开关名
默认值
说明
enable_predictions
true
是否展示预测结果（紧急降级用）
enable_odds_analysis
true
是否展示赔率分析
enable_ai_reports
true
是否生成/展示 AI 报告
enable_push_notifications
true
是否发送推送通知
enable_payment
true
是否开放支付（维护时关闭）
enable_simulation
true
是否展示蒙特卡洛模拟
enable_english
false
是否开放英文版本
maintenance_mode
false
全站维护模式
ℹ 功能开关存储在 Redis 中，Java/Python 服务启动时加载并定时刷新（每 30s）。管理员可在后台实时修改。

5. 性能优化设计
5.1 缓存策略
缓存对象
TTL
缓存位置
失效策略
今日预测列表
5 min
Redis
新预测发布时主动失效
比赛详情页数据
3 min
Redis
比赛状态变更时主动失效
战绩统计数据
10 min
Redis
赛后结算时主动失效
蒙特卡洛模拟结果
1 hour
Redis
新模拟完成时主动失效
AI 分析报告
24 hour
Redis + CDN
报告不可变，长期缓存
分享卡片图片
永久
CDN (S3)
图片不可变，永久缓存
用户订阅状态
5 min
Redis
订阅变更时主动失效
赛事积分榜
10 min
Redis
比赛结束后主动失效
功能开关
30 sec
内存
后台修改后 Redis 发布更新事件
静态资源
365 天
CDN
文件名含 hash，长期缓存

5.2 数据库性能优化
优化措施
说明
索引优化
基于实际查询模式添加复合索引，使用 EXPLAIN ANALYZE 验证
连接池
Java: HikariCP (max=20)；Python: SQLAlchemy pool_size=10, max_overflow=20
读写分离
如果单库压力大，启用 RDS 只读副本，战绩/预测查询走只读
慢查询监控
pg_stat_statements 启用，慢查询 &gt; 100ms 记录日志
分区表
odds_snapshots 表按月分区（数据量最大的表）
定期 VACUUM
配置 autovacuum 参数，避免表膨胀
查询优化
避免 N+1 查询，使用 JOIN FETCH；批量查询使用 IN 代替循环

5.3 CDN 配置
配置项
说明
CDN 服务商
阿里云 CDN / CloudFront（根据目标市场选择）
源站
Next.js SSR 服务 + S3 静态资源
缓存规则
静态资源 (js/css/img): 365天；HTML 页面: 不缓存（SSR 动态生成）；API: 不缓存
压缩
开启 Gzip + Brotli 压缩
HTTPS
全站强制 HTTPS，HTTP 301 重定向
域名
主域名: wcp.ai（国内）+ worldcuppredictor.com（国际）

6. 高级可视化功能设计 (P2)
6.1 比分概率热力图
设计要素
说明
展示形式
10×10 的比分矩阵网格，颜色深浅表示概率大小
交互
hover 显示具体概率值和排名
技术
D3.js 自定义热力图 + TailwindCSS 布局
数据源
ML API 返回的 score_matrix
访问权限
付费用户可见（免费用户看模糊版）

6.2 交互式淘汰赛 Bracket
设计要素
说明
展示形式
完整的淘汰赛树状图（16强→8强→4强→决赛）
交互
点击任一比赛显示预测概率、hover 显示球队晋级路径
动态数据
已完成比赛显示实际比分，未完成显示预测概率
蒙特卡洛集成
每个节点显示该队到达该阶段的模拟概率
技术
React + D3.js / Canvas 混合渲染，响应式支持横屏/竖屏
访问权限
公开页面

6.3 多模型对比面板
设计要素
说明
展示形式
并列显示 Poisson、Dixon-Coles、XGBoost、Ensemble 各模型的预测结果
内容
胜平负概率、λ 值、Top3 比分、大小球概率
可视化
雷达图对比各模型在不同维度的差异
技术
Recharts 雷达图 + 表格
访问权限
高阶订阅用户

7. 多语言支持 (i18n) 设计
7.1 i18n 架构
配置项
说明
框架
next-intl（Next.js 生态最佳 i18n 方案）
支持语言
Phase 5: zh-CN（简体中文）+ en（英文）
默认语言
zh-CN
路由策略
基于子路径: /zh/..., /en/...（有利于 SEO）
翻译文件
JSON 格式，存放在 src/i18n/messages/ 目录
动态内容
AI 报告、球队名称等动态内容通过数据库 name_zh/name 字段切换

7.2 翻译范围
内容类型
翻译方式
说明
UI 文案
静态翻译文件
按钮、标签、提示等固定文案
球队名称
数据库 name/name_zh
teams 表已有双语字段
球员名称
数据库 name/name_zh
players 表已有双语字段
赛事名称
数据库 name/name_zh
competitions 表已有双语字段
AI 报告
生成时指定语言
Prompt 中指定输出语言为英文
SEO 元数据
按语言版本生成
OG 标签、title、description 等
⚠ Phase 5 仅搭建 i18n 基础设施和完成前端 UI 的英文翻译。AI 报告英文版、营销素材英文版等留待后续迭代。

8. 安全加固设计
安全措施
实现方式
HTTPS 全站强制
cert-manager + Let&apos;s Encrypt，HSTS 头
API 认证
JWT RS256，短期 Access Token + 长期 Refresh Token
CORS 限制
仅允许主域名和 CDN 域名
SQL 注入防护
全程使用 ORM 参数化查询，禁止拼接 SQL
XSS 防护
Next.js 自动转义 + CSP 头
CSRF 防护
SameSite Cookie + CSRF Token
速率限制
API Gateway 全局限流 + 敏感接口独立限流（登录: 5次/min，支付: 3次/min）
敏感数据加密
支付信息 AES 加密存储，OAuth Token 加密存储，密码 BCrypt
日志脱敏
日志中不记录密码、Token、支付卡号等敏感信息
依赖安全
Dependabot 自动检测依赖漏洞，Trivy 扫描容器镜像
数据库安全
RDS 私有子网、安全组限制、定期备份（每日 + 事务日志）
免责声明
产品内所有预测页面底部显示免责声明

9. 灾备与恢复策略
场景
预防措施
恢复方案
数据库故障
RDS 高可用主备 + 每日备份
自动故障转移 + 时间点恢复（PITR）
服务崩溃
K8s 多副本 + 健康检查 + 自动重启
Pod 自动重启，HPA 自动扩容
数据源故障
多数据源备份 + Adapter 抽象层
自动切换备用 Adapter
CDN 故障
多 CDN 供应商备选
DNS 切换到备用 CDN
全站故障
K8s 滚动更新 + 版本回滚
helm rollback 快速回到上一版本
流量激增
HPA + 预扩容脚本
比赛日提前手动扩容
安全事件
WAF + 速率限制 + 日志审计
封禁恶意 IP + 紧急修复

9.1 比赛日保障预案
#
预案
详细
1
赛前 2 小时预扩容
frontend 和 java-api 扩到 4-6 副本
2
缓存预热
赛前 1 小时预加载所有今日比赛数据到 Redis
3
非核心服务降级
如有压力，可关闭 AI 报告生成、蒙特卡洛模拟等后台任务
4
值班制度
比赛日安排开发人员值班，手机保持畅通
5
快速回滚
备好上一版本的 Helm release 名，一键回滚
6
赛后缩容
比赛结束后 2 小时手动缩容回日常配置

10. Phase 5 验收标准
#
验收条件
度量指标
优先级
1
K8s 集群搭建完成，所有服务正常运行
kubectl get pods 全部 Running
必须
2
CI/CD 流水线完整工作
PR→测试→构建→staging→production 全链路
必须
3
生产环境 HTTPS 全站可访问
SSL 证书有效，HTTP 自动重定向
必须
4
Prometheus + Grafana 监控 Dashboard 可用
系统 + 业务两个 Dashboard 正常
必须
5
核心告警规则配置并测试通过
手动触发告警验证
必须
6
运营后台 9 个页面全部可用
管理员可正常操作
必须
7
功能开关系统正常工作
修改开关后 30s 内生效
必须
8
首页首屏加载 &lt; 2s
Lighthouse Performance &gt; 80
必须
9
ML API P99 延迟 &lt; 500ms
压测报告
必须
10
Redis 缓存策略全部生效
缓存命中率 &gt; 80%
必须
11
CDN 配置正确，静态资源加速
CDN 命中率 &gt; 90%
必须
12
比分热力图和交互 bracket 正常渲染
功能测试
必须
13
i18n 基础设施就绪，英文版基础可用
切换到 /en 能正常显示
必须
14
安全措施全部实施
安全检查清单全通过
必须
15
数据库自动备份正常
验证备份恢复
必须
16
比赛日预扩容脚本测试通过
模拟扩缩容
必须
17
全链路压力测试（模拟比赛日流量）
支撑 1000 QPS 无报错
建议

11. 上线前最终检查清单
以下是 2026年6月11日世界杯开赛前必须完成的最终检查清单：
#
检查项
状态
负责人/说明
1
所有 Phase 1-5 验收标准通过
待检
逐项确认
2
生产数据库数据完整性验证
待检
4000+ 场历史数据
3
所有数据源采集正常运行 &gt; 72h
待检
data_source_logs 无失败
4
ML 模型回测报告审核通过
待检
+EV ROI &gt; 0
5
模型已发布到 MLflow Production
待检
ensemble 模型
6
世界杯赛程数据已导入
待检
全部 64 场比赛
7
蒙特卡洛模拟首次运行完成
待检
夺冠概率合理
8
支付流程端到端测试（真实支付宝/微信沙箱）
待检
从支付到订阅激活
9
微信服务号模板消息审核通过
待检
推送功能依赖
10
CDN 预热完成
待检
静态资源已缓存
11
SSL 证书有效期 &gt; 90 天
待检
避免赛事期间过期
12
比赛日预扩容脚本就绪
待检
一键扩容
13
回滚方案测试通过
待检
helm rollback 可用
14
值班排班表确认
待检
比赛日值班人员
15
免责声明文案法务确认
待检
合规要求
16
域名备案完成（国内域名）
待检
合规要求
17
Google Analytics / PostHog 埋点验证
待检
核心事件正常上报
18
首场比赛预测手动验证
待检
开赛前一天生成并人工检查


— Phase 5 详细设计文档结束 —

— World Cup 2026 Predictor 全部详细设计文档（Phase 1-5）完成 —

