





⚽
World Cup 2026 Predictor
AI赛事预测平台
Phase 3 — 前端 MVP + 核心业务 详细设计文档


版本: v1.0  |  日期: 2026年5月1日  |  详细设计阶段

1. 文档说明
1.1 文档定位
本文档是 Phase 3（前端 MVP + 核心业务）的详细设计文档。Phase 3 是模块覆盖面最广的阶段，涉及 M3 业务服务、M4 内容生成（基础）、M5 战绩追踪、M6 社交传播（基础）和 M7 前端 MVP 共五个模块。本文档定义 Java 业务服务的 API 接口、用户/订阅/支付流程、前端页面结构与组件设计、战绩系统、分享卡片生成和权限控制体系。
1.2 Phase 3 目标回顾
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
1.3 与上游 Phase 的依赖
依赖项
说明
Phase 1 数据库
matches、teams、competitions 等基础数据表
Phase 2 ML API
FastAPI /predict、/odds-analysis、/predictions/today 接口
Phase 2 predictions 表
预测结果，战绩系统的核心数据源
Phase 2 odds_analysis 表
赔率分析结果，前端价值信号标签的数据源

2. Phase 3 新增数据库 Schema
Phase 3 在 Phase 1/2 的基础上新增以下表，覆盖用户、订阅、支付、战绩和分享链接等业务实体。
2.1 新增表清单
#
表名
说明
预估行数
所属模块
1
users
用户基本信息
~50000
M3
2
user_oauth
第三方 OAuth 绑定
~80000
M3
3
subscriptions
订阅记录
~20000
M3
4
payments
支付流水
~30000
M3
5
prediction_results
赛后预测结果比对
~5000
M5
6
track_record_stats
累计战绩统计（缓存表）
~20
M5
7
share_links
分享链接 + UTM 追踪
~100000
M6
8
share_cards
生成的分享卡片记录
~30000
M4
9
user_favorites
用户收藏的比赛
~50000
M7

2.2 各表详细定义
2.2.1 users — 用户表
字段
类型
NULL
默认
说明
id
BIGSERIAL PK
NO
auto
主键
uuid
UUID
NO
gen_random_uuid()
外部暴露 ID，不暴露自增主键
phone
VARCHAR(20)
YES
-
手机号（国内用户主要登录方式）
email
VARCHAR(200)
YES
-
邮箱
password_hash
VARCHAR(255)
YES
-
密码哈希（BCrypt），OAuth 用户可为空
nickname
VARCHAR(50)
YES
-
昵称
avatar_url
TEXT
YES
-
头像 URL
subscription_tier
VARCHAR(20)
NO
free
当前订阅层级: free/basic/premium
subscription_expires
TIMESTAMPTZ
YES
-
订阅到期时间
locale
VARCHAR(10)
NO
zh-CN
语言偏好
timezone
VARCHAR(50)
NO
Asia/Shanghai
时区
last_login_at
TIMESTAMPTZ
YES
-
最后登录时间
is_active
BOOLEAN
NO
true
是否激活
role
VARCHAR(20)
NO
user
角色: user/admin
created_at
TIMESTAMPTZ
NO
NOW()

updated_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(uuid)；UNIQUE(phone) WHERE phone IS NOT NULL；UNIQUE(email) WHERE email IS NOT NULL；idx_users_subscription

2.2.2 user_oauth — 第三方 OAuth 绑定表
字段
类型
NULL
默认
说明
id
BIGSERIAL PK
NO
auto
主键
user_id
BIGINT FK
NO
-
关联 users.id
provider
VARCHAR(20)
NO
-
wechat/weibo/google/apple
provider_user_id
VARCHAR(200)
NO
-
第三方平台用户 ID
access_token
TEXT
YES
-
访问令牌（加密存储）
refresh_token
TEXT
YES
-
刷新令牌（加密存储）
token_expires_at
TIMESTAMPTZ
YES
-
令牌过期时间
created_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(provider, provider_user_id)；idx_oauth_user

2.2.3 subscriptions — 订阅记录表
字段
类型
NULL
默认
说明
id
BIGSERIAL PK
NO
auto
主键
user_id
BIGINT FK
NO
-
关联 users.id
tier
VARCHAR(20)
NO
-
basic/premium
plan_type
VARCHAR(20)
NO
-
monthly/worldcup_pass
status
VARCHAR(20)
NO
active
active/expired/cancelled/refunded
price_cny
INTEGER
NO
-
价格（分）
started_at
TIMESTAMPTZ
NO
-
开始时间
expires_at
TIMESTAMPTZ
NO
-
到期时间
auto_renew
BOOLEAN
NO
false
是否自动续费
payment_id
BIGINT FK
YES
-
关联 payments.id
created_at
TIMESTAMPTZ
NO
NOW()

updated_at
TIMESTAMPTZ
NO
NOW()

索引: idx_subscriptions_user (user_id, status)；idx_subscriptions_expires

2.2.4 payments — 支付流水表
字段
类型
NULL
默认
说明
id
BIGSERIAL PK
NO
auto
主键
user_id
BIGINT FK
NO
-
关联 users.id
order_no
VARCHAR(64)
NO
-
内部订单号（唯一）
payment_channel
VARCHAR(20)
NO
-
alipay/wechat_pay
amount_cny
INTEGER
NO
-
金额（分）
status
VARCHAR(20)
NO
pending
pending/paid/failed/refunded
channel_trade_no
VARCHAR(100)
YES
-
第三方支付流水号
paid_at
TIMESTAMPTZ
YES
-
支付时间
refunded_at
TIMESTAMPTZ
YES
-
退款时间
callback_raw
JSONB
YES
-
支付回调原始数据
meta
JSONB
YES
-
额外元数据（订阅计划等）
created_at
TIMESTAMPTZ
NO
NOW()

updated_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(order_no)；idx_payments_user；idx_payments_status

2.2.5 prediction_results — 赛后预测结果比对表
字段
类型
NULL
默认
说明
id
BIGSERIAL PK
NO
auto
主键
prediction_id
BIGINT FK
NO
-
关联 predictions.id
match_id
BIGINT FK
NO
-
关联 matches.id
actual_home_score
SMALLINT
NO
-
实际主队进球
actual_away_score
SMALLINT
NO
-
实际客队进球
result_1x2_hit
BOOLEAN
NO
-
胜平负是否命中
result_score_hit
BOOLEAN
NO
-
比分是否命中（Top10 中）
result_ou25_hit
BOOLEAN
YES
-
大小球 2.5 是否命中
result_btts_hit
BOOLEAN
YES
-
BTTS 是否命中
best_ev_outcome
VARCHAR(30)
YES
-
最高 EV 的投注结果
best_ev_odds
NUMERIC(6,3)
YES
-
最高 EV 对应赔率
best_ev_hit
BOOLEAN
YES
-
最高 EV 是否命中
pnl_unit
NUMERIC(8,4)
YES
-
假设1单位等额投注的盈亏
settled_at
TIMESTAMPTZ
NO
NOW()
结算时间
created_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(prediction_id)；idx_results_match；idx_results_settled (settled_at DESC)

2.2.6 track_record_stats — 累计战绩统计缓存表
此表为预计算缓存表，避免每次请求实时聚合。由赛后结算任务自动更新。
字段
类型
NULL
默认
说明
id
BIGSERIAL PK
NO
auto
主键
stat_type
VARCHAR(30)
NO
-
统计类型: overall/1x2/score/ou25/btts/positive_ev
period
VARCHAR(20)
NO
-
统计周期: all_time/last_30d/last_7d/worldcup
total_predictions
INTEGER
NO
0
总预测场次
hits
INTEGER
NO
0
命中场次
hit_rate
NUMERIC(5,4)
NO
0
命中率
total_pnl_units
NUMERIC(10,4)
NO
0
累计盈亏（单位）
roi
NUMERIC(6,4)
NO
0
ROI
current_streak
INTEGER
NO
0
当前连红/连黑（正=连红，负=连黑）
best_streak
INTEGER
NO
0
历史最长连红
updated_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(stat_type, period)

2.2.7 share_links — 分享链接追踪表
字段
类型
NULL
默认
说明
id
BIGSERIAL PK
NO
auto
主键
short_code
VARCHAR(10)
NO
-
短链接码
user_id
BIGINT FK
YES
-
分享人
target_type
VARCHAR(20)
NO
-
prediction/match/track_record
target_id
BIGINT
YES
-
目标实体 ID
target_url
TEXT
NO
-
目标完整 URL
utm_source
VARCHAR(50)
YES
-
来源渠道
utm_medium
VARCHAR(50)
YES
-
媒体类型
utm_campaign
VARCHAR(100)
YES
-
营销活动
click_count
INTEGER
NO
0
点击次数
register_count
INTEGER
NO
0
带来的注册数
subscribe_count
INTEGER
NO
0
带来的付费数
created_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(short_code)；idx_share_user；idx_share_target

2.2.8 share_cards — 分享卡片记录表
字段
类型
NULL
默认
说明
id
BIGSERIAL PK
NO
auto
主键
card_type
VARCHAR(20)
NO
-
prediction/red_hit/track_record
target_id
BIGINT
NO
-
关联的预测/比赛 ID
platform
VARCHAR(20)
NO
-
wechat/weibo/douyin/x/generic
image_url
TEXT
NO
-
S3/MinIO 图片 URL
width
SMALLINT
NO
-
图片宽度 px
height
SMALLINT
NO
-
图片高度 px
created_at
TIMESTAMPTZ
NO
NOW()

索引: idx_cards_target (card_type, target_id)；idx_cards_platform

3. Java 业务服务 API 设计 (M3)
Java Spring Boot 业务服务是前端与后端之间的中间层，负责用户管理、订阅、权限控制和内容分发。所有 API 前缀为 /api/v1/。认证使用 JWT Bearer Token。
3.1 用户服务 API
方法
端点
说明
POST
/api/v1/auth/register
手机号/邮箱注册（发送验证码）
POST
/api/v1/auth/login
登录（手机号+验证码 或 邮箱+密码）
POST
/api/v1/auth/oauth/{provider}
第三方 OAuth 登录（wechat/weibo/google）
POST
/api/v1/auth/refresh
刷新 JWT Token
GET
/api/v1/users/me
获取当前用户信息
PUT
/api/v1/users/me
更新用户资料（昵称、头像）
POST
/api/v1/auth/logout
登出（废弃当前 Token）

3.1.1 JWT Token 设计
配置项
说明
算法
RS256（非对称加密，公钥可给前端验证）
Access Token 有效期
2 小时
Refresh Token 有效期
30 天
Payload 字段
sub(user_uuid), role, subscription_tier, exp, iat
Token 刷新策略
Access Token 过期后用 Refresh Token 换新，双 Token 机制
黑名单
用户登出或修改密码时将 Token 加入 Redis 黑名单

3.2 订阅服务 API
方法
端点
说明
GET
/api/v1/subscriptions/plans
获取可用订阅计划及价格
POST
/api/v1/subscriptions/create
创建订阅订单（返回支付参数）
GET
/api/v1/subscriptions/current
获取当前订阅状态
POST
/api/v1/subscriptions/cancel
取消自动续费
POST
/api/v1/payments/callback/alipay
支付宝异步回调（服务端签名验证）
POST
/api/v1/payments/callback/wechat
微信支付异步回调

3.2.1 订阅计划定义
计划
包含内容
月价（元）
世界杯通票
plan_type
基础订阅 Basic
比分/大小球/让球 + 赔率信号 + AI报告 + 推送
29.9
68
basic
高阶订阅 Premium
全部基础 + xG面板 + 置信度筛选 + 回测数据
59.9
128
premium
ℹ 世界杯通票（worldcup_pass）覆盖 2026.6.11 - 2026.7.19 整个赛事周期，一次性付费。是主推产品。

3.2.2 支付流程设计
步骤
操作
详细
1
用户选择计划
前端展示订阅计划，用户点击订阅
2
创建订单
后端生成 order_no，写入 payments 表（status=pending）
3
调用支付SDK
后端调用支付宝/微信支付 SDK 创建预支付订单，返回支付参数
4
前端唤起支付
前端用支付参数唤起支付宝/微信支付
5
异步回调
支付平台回调 /payments/callback/*，验签后更新 payments.status=paid
6
激活订阅
回调成功后创建 subscriptions 记录，更新 users.subscription_tier
7
同步查询
前端轮询订单状态（最多 30s），确认支付成功后刷新页面
⚠ 支付回调必须做签名验证、幂等处理（同一 order_no 不重复处理）、金额校验。所有支付敏感操作记录完整日志。

3.3 比赛与预测分发 API
方法
端点
说明
GET
/api/v1/matches/today
今日比赛列表 + 预测摘要（调用 ML API）
GET
/api/v1/matches/{id}
比赛详情（根据订阅层级返回不同粒度）
GET
/api/v1/matches/{id}/prediction
比赛预测详情（付费内容分层）
GET
/api/v1/matches/{id}/odds-analysis
赔率分析（付费内容）
GET
/api/v1/competitions/{id}/standings
赛事积分榜
GET
/api/v1/competitions/worldcup/bracket
世界杯淘汰赛对阵图
GET
/api/v1/matches/upcoming
未来 7 天比赛列表
POST
/api/v1/matches/{id}/favorite
收藏/取消收藏比赛

3.3.1 内容分层策略（付费墙逻辑）
Java 服务根据 JWT 中的 subscription_tier 字段控制返回的数据粒度：
数据项
免费用户
基础订阅
高阶订阅
胜平负概率
✅ 完整
✅ 完整
✅ 完整
比分 Top10
❌ 锁定
✅ 完整
✅ 完整
大小球/让球
❌ 锁定
✅ 完整
✅ 完整
赔率 EV 分析
❌ 锁定
✅ 完整
✅ 完整
AI 分析报告
❌ 锁定
✅ 完整
✅ 完整
价值信号标签
❌ 仅显示&quot;有信号&quot;
✅ 完整信号等级
✅ 完整信号等级
xG/伤病面板
❌ 锁定
❌ 锁定
✅ 完整
置信度筛选
❌ 锁定
❌ 锁定
✅ 完整
回测历史数据
❌ 锁定
❌ 锁定
✅ 完整
ℹ 免费用户看到锁定内容时显示模糊预览+解锁按钮，而非完全隐藏。这是关键的付费转化设计。

4. 战绩系统设计 (M5)
4.1 赛后自动结算流程
步骤
操作
详细
1
监听比赛结束事件
消费 Kafka match.finished 事件，获取比赛 ID 和最终比分
2
查询对应预测
从 predictions 表查询该比赛的预测记录
3
结果比对
对比预测概率与实际结果，计算各盘口的命中情况
4
写入结果表
将比对结果写入 prediction_results 表
5
更新统计缓存
重新计算 track_record_stats 表中的累计指标
6
触发卡片生成
如果命中（红单），触发红单卡片生成任务
7
缓存更新
清除 Redis 中战绩页面的缓存

4.2 战绩 API
方法
端点
说明
GET
/api/v1/track-record/overview
战绩总览（命中率、ROI、连红等）- 公开
GET
/api/v1/track-record/roi-chart
ROI 累计曲线数据 - 公开
GET
/api/v1/track-record/history
历史预测记录列表（分页）- 公开
GET
/api/v1/track-record/by-market/{type}
按盘口类型的战绩统计 - 公开
GET
/api/v1/track-record/by-confidence
按置信度的战绩统计 - 公开
⚠ 战绩页面是全部公开的（无需登录），这是最强的营销素材。数据通过 Redis 缓存（TTL 10分钟），避免实时聚合。

5. 分享卡片 &amp; 社交传播设计 (M4 + M6)
5.1 分享卡片生成
5.1.1 卡片类型
卡片类型
触发时机
内容
平台适配
预测卡片
预测发布时
比赛双方、胜平负概率、价值信号、时间戳
4种尺寸
红单卡片
赛后命中时
比赛结果、预测结果、命中标记、连红标签
4种尺寸
战绩卡片
手动触发
累计战绩、ROI、命中率、最佳记录
4种尺寸

5.1.2 平台尺寸适配
平台
尺寸
比例
说明
微信
1080 x 1080 px
1:1
朋友圈分享最佳
微博
1200 x 675 px
16:9
微博卡片展示
抖音
1080 x 1920 px
9:16
短视频封面
X (Twitter)
1200 x 675 px
16:9
推文预览卡片

5.1.3 生成技术方案
采用 HTML → Image 方案：用 Jinja2 模板渲染 HTML，然后用 Playwright 截图为 PNG。优势是设计灵活、支持中文字体、可快速迭代。
组件
说明
HTML 模板
Jinja2 模板，使用 TailwindCSS 样式，预置4种卡片模板 × 4种尺寸
数据注入
从 predictions + odds_analysis 表获取数据，注入模板
截图服务
Playwright headless Chrome，设置对应尺寸视口，截图为 PNG
字体
内嵌思源黑体（Noto Sans SC），确保中文渲染
存储
上传到 S3/MinIO，写入 share_cards 表
异步执行
通过 Celery 异步任务执行，避免阻塞主流程

5.2 分享链接服务
5.2.1 短链接生成
每次分享生成带 UTM 参数的短链接，格式: https://wcp.ai/s/{short_code}。short_code 为 6-8 位 Base62 编码，由 share_links.id 转换而来。

5.2.2 分享 API
方法
端点
说明
POST
/api/v1/share/create
创建分享链接（指定目标 + 平台）
GET
/s/{short_code}
短链接重定向（记录点击并 302 跳转）
GET
/api/v1/share/{id}/stats
分享链接统计（点击数、注册数、付费数）

6. 前端页面设计 (M7)
6.1 技术栈确认
技术
说明
框架
Next.js 14+ (App Router) — SSR/SSG 支持 SEO 和社交分享 OG 标签
语言
TypeScript — 类型安全
样式
TailwindCSS — 快速开发、响应式优先
图表
Recharts — 图表组件（ROI曲线、概率柱状图等）
状态管理
Zustand — 轻量级状态管理（用户状态、订阅状态）
HTTP
Axios + SWR — API 请求 + 缓存 + 自动重验证
i18n
next-intl — 国际化框架（先做中文，预留英文）
部署
Vercel 或自建 Node.js 容器

6.2 页面路由设计
路由
页面
访问权限
SSR/SSG
/
首页（今日赛程 + 预测列表）
公开
SSR
/match/[id]
比赛详情页
公开（部分付费）
SSR
/track-record
战绩/ROI 页面
公开
SSG + ISR
/worldcup/groups
世界杯小组赛积分榜
公开
SSR
/worldcup/bracket
世界杯淘汰赛对阵图
公开
SSR
/login
登录/注册页
公开
CSR
/profile
个人中心
登录
CSR
/subscribe
订阅页面
公开
SSG
/admin/*
后台管理（Phase 5）
管理员
CSR
ℹ 关键营销页面（首页、战绩页）使用 SSR/SSG 确保 SEO 和社交分享时 OG 标签正确渲染。

6.3 核心页面组件设计
6.3.1 首页 / 赛程页 (/)
组件
说明
MatchDayHeader
日期选择器，可切换查看不同日期的比赛
MatchCard
单场比赛卡片：双方队名/队徽、比赛时间、胜平负概率、价值信号标签
ValueSignalBadge
价值信号标签组件（⭐/⭐⭐/⭐⭐⭐），付费用户显示详细，免费用户显示模糊
CompetitionFilter
赛事筛选器（世界杯/英超/西甲等）
ConfidenceFilter
置信度筛选器（仅高阶用户可用，免费用户显示锁定）
PromotionBanner
订阅推广横幅（非订阅用户显示）

6.3.2 比赛详情页 (/match/[id])
组件
说明
MatchHeader
比赛基本信息：双方队名/队徽、比赛时间/比分、赛事/轮次
PredictionPanel
预测结果面板：胜平负概率柱状图（免费可见）
ScoreMatrix
比分概率热力图（付费内容，免费用户看模糊版+解锁按钮）
OddsCompareTable
多家博彩赔率对比表 + EV 分析（付费内容）
ValueSignalCard
价值信号详情卡片：最佳赔率、EV、edge、信号等级
TeamStatsPanel
两队基础数据对比（近5场战绩、控球率等）
XGPanel
xG 详细面板（高阶订阅内容）
InjuryPanel
伤病情况面板（高阶订阅内容）
H2HPanel
历史交锋记录
ShareButton
分享按钮（生成分享卡片+短链接）
PaywallOverlay
付费墙覆盖层（模糊预览+解锁提示）

6.3.3 战绩页 (/track-record)
组件
说明
StatsOverview
核心指标卡片组：总命中率、ROI、连红记录、总预测场次
ROIChart
ROI 累计曲线图（Recharts 折线图）
MarketBreakdown
按盘口类型的分层统计表
ConfidenceBreakdown
按置信度的分层统计表
PredictionHistory
历史预测记录列表（分页，带红单/黑单标记）
ShareTrackRecord
一键分享战绩卡片按钮

6.3.4 世界杯淘汰赛对阵图 (/worldcup/bracket)
组件
说明
BracketView
淘汰赛对阵图（16强→决赛），响应式横向/纵向切换
BracketMatch
单场淘汰赛卡片，显示预测概率 + 已知比分
GroupStandings
小组赛积分榜，可切换各小组

6.3.5 个人中心 (/profile)
组件
说明
UserInfo
用户基本信息编辑
SubscriptionStatus
当前订阅状态、到期时间、续费/升级按钮
PaymentHistory
支付历史记录
FavoriteMatches
收藏的比赛列表
PushSettings
推送通知设置（Phase 4 实现）

6.4 付费墙 UI 设计
付费墙设计原则：锁定内容显示模糊预览 + 解锁提示，而不是完全隐藏。让免费用户「看到但拿不到」，制造付费冲动。
设计元素
实现方式
模糊预览
CSS filter: blur(8px) 叠加在内容上方，用户能看到内容轮廓但无法阅读
锁定图标
内容区域中央显示锁定图标 + &quot;解锁查看完整分析&quot; 按钮
价格锚点
在解锁按钮旁显示 &quot;基础订阅 ¥29.9/月&quot; 或 &quot;世界杯通票 ¥68&quot;
试用钩子
首次注册用户可免费查看 3 场完整预测（之后锁定）
渐进式解锁
胜平负免费→点击查看详情→比分/赔率付费→AI报告付费，逐步暴露价值

7. 前端项目结构
worldcup-predictor-web/
├── src/
│   ├── app/                       # Next.js App Router
│   │   ├── (public)/              # 公开路由组
│   │   │   ├── page.tsx           # 首页
│   │   │   ├── match/[id]/page.tsx# 比赛详情
│   │   │   ├── track-record/page.tsx
│   │   │   ├── worldcup/
│   │   │   │   ├── groups/page.tsx
│   │   │   │   └── bracket/page.tsx
│   │   │   └── subscribe/page.tsx
│   │   ├── (auth)/                # 认证路由组
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── (protected)/           # 需登录路由组
│   │   │   └── profile/page.tsx
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── match/                 # 比赛相关组件
│   │   ├── prediction/            # 预测相关组件
│   │   ├── track-record/          # 战绩相关组件
│   │   ├── worldcup/              # 世界杯专属组件
│   │   ├── subscription/          # 订阅/付费墙组件
│   │   ├── share/                 # 分享相关组件
│   │   ├── ui/                    # 通用 UI 组件
│   │   └── layout/                # 布局组件
│   ├── lib/
│   │   ├── api.ts                 # API 客户端封装
│   │   ├── auth.ts                # 认证工具
│   │   └── utils.ts               # 通用工具函数
│   ├── hooks/                     # 自定义 Hooks
│   ├── stores/                    # Zustand stores
│   │   ├── auth-store.ts
│   │   └── subscription-store.ts
│   ├── types/                     # TypeScript 类型定义
│   └── i18n/                      # 国际化资源
├── public/                        # 静态资源
├── tailwind.config.ts
├── next.config.js
└── package.json

8. SEO &amp; 社交分享 OG 标签
社交平台分享时展示正确的标题、描述和图片对传播至关重要。以下为各页面的 OG 标签配置：
页面
og:title 示例
og:image
首页
World Cup 2026 AI 预测 - 今日3场高价值推荐
默认品牌图
比赛详情
巴西 vs 德国 预测 | AI模型: 巴西52%胜率
自动生成的预测卡片
战绩页
AI预测累计ROI +12.3% | 命中率67.8%
战绩卡片截图
淘汰赛对阵
2026世界杯淘汰赛对阵 + AI出线概率
对阵图截图
⚠ 比赛详情页的 OG 标签必须通过 SSR 动态生成，确保微信/微博等平台爬虫能获取到正确的数据。这是 Next.js SSR 的核心价值之一。

9. Phase 3 部署架构增量
服务名
镜像
端口
说明
java-api
自建 (Spring Boot)
8080
Java 业务服务
frontend
自建 (Next.js)
3000
前端 SSR 服务
card-worker
自建 (Python)
-
分享卡片生成 Worker
settlement-worker
自建 (Python/Java)
-
赛后结算 Worker
nginx
nginx:alpine
80/443
反向代理 + SSL 终结
新增服务依赖：java-api 依赖 postgres + redis + ml-api；frontend 依赖 java-api；card-worker 依赖 postgres + S3；所有 Phase 1/2 服务保持不变。

9.1 API Gateway 路由设计
路由规则
目标服务
说明
/api/v1/auth/**
java-api:8080
认证相关
/api/v1/users/**
java-api:8080
用户相关
/api/v1/subscriptions/**
java-api:8080
订阅相关
/api/v1/payments/**
java-api:8080
支付相关
/api/v1/matches/**
java-api:8080
比赛数据（Java 内部调用 ML API）
/api/v1/track-record/**
java-api:8080
战绩相关
/api/v1/share/**
java-api:8080
分享相关
/s/**
java-api:8080
短链接重定向
/**
frontend:3000
所有其他请求路由到前端

10. Phase 3 验收标准
#
验收条件
度量指标
优先级
1
用户可通过手机号/邮箱注册并登录
注册→登录→获取用户信息流程完整
必须
2
微信 OAuth 登录可用
跳转授权→回调→创建用户→获取 Token
必须
3
三层订阅付费流程完整（支付宝+微信支付）
从选择计划到支付成功到订阅激活
必须
4
首页正确展示今日比赛 + 预测摘要
数据正确、价值信号标签显示
必须
5
比赛详情页按订阅层级展示不同内容
免费/基础/高阶用户看到不同粒度
必须
6
付费墙正确显示（模糊预览+解锁按钮）
锁定内容不可在前端绕过
必须
7
战绩页公开展示命中率、ROI、历史记录
数据正确、ROI 曲线图可渲染
必须
8
赛后自动结算预测结果并更新战绩
match.finished 事件触发后自动完成
必须
9
分享卡片自动生成并适配4个平台尺寸
预测卡片+红单卡片正确生成
必须
10
分享链接带 UTM 追踪且点击计数准确
短链接正确跳转、计数更新
必须
11
世界杯积分榜和淘汰赛对阵图正确
数据正确、响应式布局
必须
12
OG 标签在微信/微博分享时正确展示
分享预览包含标题+描述+图片
必须
13
移动端响应式布局正常
主要页面在 375px 以上正确显示
必须
14
页面加载时间 &lt; 2s（首屏）
Lighthouse Performance &gt; 80
建议
15
前端单元测试覆盖核心组件
测试覆盖率 &gt; 70%
建议

11. 与 Phase 4 的交接点
交接项
Phase 4 如何使用
用户订阅体系
Phase 4 推送服务根据订阅状态决定推送目标
predictions + prediction_results 表
Phase 4 AI 报告基于预测数据生成内容
share_cards 生成流程
Phase 4 扩展为营销素材自动生成
Java 业务 API 架构
Phase 4 新增 AI 报告 API、推送 API 等端点
前端组件体系
Phase 4 新增 AI 报告页面、蒙特卡洛模拟页面
Kafka match.finished 事件
Phase 4 扩展为触发 AI 报告和推送
战绩系统
Phase 4 的推送内容引用战绩数据作为信任背书


— Phase 3 详细设计文档结束 —

