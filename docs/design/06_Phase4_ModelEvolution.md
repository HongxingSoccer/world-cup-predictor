





⚽
World Cup 2026 Predictor
AI赛事预测平台
Phase 4 — 模型进化 + 内容生成 详细设计文档


版本: v1.0  |  日期: 2026年5月1日  |  详细设计阶段

1. 文档说明
1.1 文档定位
本文档是 Phase 4（模型进化 + 内容生成）的详细设计文档。Phase 4 涉及 M2 ML 引擎进阶、M4 内容生成完整实现和 M6 推送服务，目标是提升模型能力至 Dixon-Coles + XGBoost，上线 AI 中文分析报告，实现高价值机会推送和蒙特卡洛赛事模拟。
1.2 Phase 4 目标回顾
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
高 EV 机会自动推送
微信 + App 推送
蒙特卡洛模拟
整届赛事模拟
出线/夺冠概率页面

2. Dixon-Coles 模型详细设计
2.1 算法原理
Dixon-Coles（1997）是对独立泊松模型的两个关键改进：(1) 低比分修正因子 τ 纠正 0-0、1-0、0-1、1-1 这四个比分的独立性假设偏差；(2) 时间衰减权重让近期比赛对参数估计有更大影响。

2.1.1 低比分修正因子 τ
对于比分 (x, y)，联合概率修正为：P(x,y) = τ(λ_home, λ_away, ρ) × Poisson(λ_home, x) × Poisson(λ_away, y)
τ 函数仅对 (0,0), (1,0), (0,1), (1,1) 四种比分生效：
比分
τ 修正公式
(0, 0)
τ = 1 - λ_home × λ_away × ρ
(1, 0)
τ = 1 + λ_away × ρ
(0, 1)
τ = 1 + λ_home × ρ
(1, 1)
τ = 1 - ρ
其他
τ = 1（不修正）
其中 ρ（rho）是修正参数，通常为负值（约 -0.03 ~ -0.13），反映低比分比赛的概率被标准泊松模型低估。

2.1.2 时间衰减权重
每场历史比赛的权重随时间指数衰减：w(t) = exp(-ξ × t)，其中 t 是该比赛距当前的天数/半年数，ξ（xi）是衰减率参数。
参数
说明
ξ = 0
所有历史比赛等权（退化为标准模型）
ξ = 0.001
慢衰减，约 3 年前的比赛权重还有 ~33%
ξ = 0.005
快衰减，约 1 年前的比赛权重就只有 ~16%
推荐范围
通过网格搜索在 [0.0005, 0.01] 区间选择最优值

2.1.3 参数估计
使用加权最大似然估计（Weighted MLE）：最大化 L = ∏ w(t_i) × P(x_i, y_i | α, β, γ, ρ)，其中 α_j 是球队 j 的攻击参数，β_j 是防守参数，γ 是主场优势参数。使用 scipy.optimize.minimize (method=&apos;L-BFGS-B&apos;) 求解。
⚠ Dixon-Coles 需要对每支球队估计攻击+防守共2个参数，加上 ρ 和 γ 全局参数。对于 ~100 支球队约需优化 200+ 参数，计算量较大但仍可在分钟级完成。

2.2 Dixon-Coles 与 Poisson 对比
维度
Poisson Baseline (Phase 2)
Dixon-Coles (Phase 4)
低比分处理
假设独立，低估 0-0/1-1
τ 修正因子纠偏
时间因素
所有历史等权
指数衰减，近期权重更大
参数估计
简化公式计算
加权 MLE 严格优化
计算成本
毫秒级
分钟级（可缓存）
预期改进
基线
Brier Score 降低 3-5%，ROI 提升 1-3%

3. XGBoost 模型详细设计
3.1 模型定位
XGBoost 模型通过融合 50+ 维特征来捕获泊松模型无法表达的非线性关系（如伤病对比赛结果的复杂影响）。定位为集成模型的一部分，与 Dixon-Coles 互补。

3.2 特征工程 v2 完整特征列表
Phase 4 在 Phase 2 的 28 个基础特征上扩展至 56 个特征：
3.2.1 新增特征组：xG 深度特征
特征名
类型
计算逻辑
home_xg_overperform_5
float
主队近5场（实际进球 - xG）的均值，正值=超常发挥
away_xg_overperform_5
float
客队近5场超常发挥值
home_xga_save_pct_5
float
主队近5场实际失球/xGA 比率，反映门将表现
away_xga_save_pct_5
float
客队近5场门将表现
home_npxg_avg5
float
主队近5场非点球 xG 均值（更纯粹的进攻指标）
away_npxg_avg5
float
客队近5场非点球 xG 均值

3.2.2 新增特征组：伤病影响特征
特征名
类型
计算逻辑
home_injury_count
int
主队当前伤病球员数
away_injury_count
int
客队当前伤病球员数
home_injury_impact
float
主队伤病球员总身价占阵容总身价百分比（衡量缺阵影响）
away_injury_impact
float
客队伤病影响
home_key_player_out
bool
主队是否有身价前3的球员缺阵
away_key_player_out
bool
客队是否有关键球员缺阵

3.2.3 新增特征组：赛程密度特征
特征名
类型
计算逻辑
home_days_since_last
int
主队距上场比赛天数
away_days_since_last
int
客队距上场比赛天数
home_matches_last_30d
int
主队最近30天比赛场次（疲劳度）
away_matches_last_30d
int
客队最近30天比赛场次
rest_diff
int
两队休息天数差值

3.2.4 新增特征组：赔率市场特征
特征名
类型
计算逻辑
market_implied_home
float
市场（赔率）隐含主胜概率（去抽水后，取多家均值）
market_implied_draw
float
市场隐含平局概率
market_implied_away
float
市场隐含客胜概率
odds_movement_home
float
主胜赔率 24h 内变化幅度（正=赔率上升/看衰）
odds_spread
float
同一赔率类型各家博彩公司的标准差（市场分歧度）
ℹ 市场特征利用了&quot;赔率即智慧&quot;的原理。博彩公司赔率隐含了大量信息，作为特征输入能显著提升模型。但要严格使用赛前快照，不能用赛后赔率。

3.3 XGBoost 模型配置
3.3.1 任务设计
XGBoost 不直接预测比分概率矩阵，而是训练多个子任务模型：
子模型
目标变量
任务类型
输出
model_1x2
胜/平/负
多分类 (softmax)
三分类概率
model_goals_home
主队进球数
回归 (poisson)
λ_home 估计
model_goals_away
客队进球数
回归 (poisson)
λ_away 估计
model_ou25
总进球 &gt;2.5 / &lt;=2.5
二分类
大小球概率
model_btts
双方是否均进球
二分类
BTTS 概率

3.3.2 超参数搜索空间
参数
搜索范围
说明
n_estimators
[100, 300, 500, 800]
树的数量
max_depth
[3, 4, 5, 6, 7]
树的最大深度
learning_rate
[0.01, 0.03, 0.05, 0.1]
学习率
subsample
[0.7, 0.8, 0.9]
样本采样比例
colsample_bytree
[0.7, 0.8, 0.9]
特征采样比例
min_child_weight
[1, 3, 5]
叶节点最小权重
reg_alpha
[0, 0.01, 0.1]
L1 正则化
reg_lambda
[1, 1.5, 2]
L2 正则化
使用 Optuna 进行贝叶斯超参数优化，目标函数为时间序列交叉验证的 Brier Score 均值。每次搜索 100 轮 trial。

3.4 集成策略
Phase 4 的最终预测由 Dixon-Coles 和 XGBoost 加权集成：
输出项
DC 权重
XGB 权重
集成方式
胜平负概率
0.4
0.6
加权平均
λ_home / λ_away
0.5
0.5
加权平均后重新计算比分矩阵
大小球概率
从 λ 计算
直接输出
取 XGB 直接输出（专门训练的模型更准）
BTTS 概率
从 λ 计算
直接输出
取 XGB 直接输出
⚠ 集成权重为初始值，后续通过回测优化。权重存储在 MLflow 参数中，可快速调整。如果某个模型回测表现差，可动态降低其权重。

4. AI 中文分析报告设计 (M4)
4.1 报告定位
每场比赛赛前自动生成中文深度分析报告，是付费用户的核心价值之一。内容通俗易懂，非专业用户也能看明白。报告在赛前 6-12 小时自动生成。

4.2 报告内容结构
#
章节
内容详述
1
比赛概览
双方阵容信息、赛事背景、比赛重要性（如必须获胜才能出线）
2
近况对比
两队近 5 场战绩、进球趋势、状态走势，用具体数据支撑
3
伤病情况
关键球员缺阵情况、对阵容实力的影响评估
4
历史交锋
交锋记录摘要、心理优势分析
5
数据分析
xG 趋势、射门效率、防守数据、控球风格对比
6
模型判断
模型预测结果解读、置信度说明、关键依据
7
赔率洞察
市场赔率分析、EV 机会解读（如有价值信号则重点标注）
8
总结与建议
综合判断、风险提示（免责声明）

4.3 LLM 调用设计
4.3.1 Prompt 工程
采用结构化 Prompt，分为 System Prompt + Data Prompt + Instruction Prompt 三部分：
Prompt 部分
内容
System Prompt
角色设定：你是一位资深足球数据分析师，擅长用通俗的中文为竞猜用户提供赛前分析。风格要求：专业但不晦涩，用数据说话，避免主观臆断。
Data Prompt
注入结构化数据：比赛信息、两队近况、伤病列表、xG/射门数据、Elo评分、模型预测结果、赔率分析结果、交锋记录等，全部以 JSON 格式注入。
Instruction Prompt
输出要求：按指定8段结构输出，每段 100-200 字，总计 800-1500 字。使用中文标点，禁止&quot;稳赢&quot;&quot;必赢&quot;等诱导用语，结尾必须包含免责声明。

4.3.2 LLM 调用配置
配置项
说明
模型选择
Claude Sonnet 4 (claude-sonnet-4-20250514) — 性价比最优
备用模型
GPT-4o-mini — Claude API 不可用时 fallback
max_tokens
2000
temperature
0.3（偏低，确保数据分析的严谨性）
超时设置
30 秒，超时后使用模板化 fallback 报告
重试策略
最多 2 次重试，间隔 5s
成本预估
每场报告约 ~3000 input tokens + ~1500 output tokens，约 ¥0.05/场

4.4 报告生成 Pipeline
步骤
操作
详细
1
触发检查
Celery Beat 每小时检查未来 6-12h 内有比赛且尚未生成报告的
2
数据组装
从 DB 查询比赛、球队、预测、赔率分析、伤病等数据
3
Prompt 组装
将数据注入 Prompt 模板
4
LLM 调用
调用 Claude API 生成报告文本
5
内容校验
检查输出长度、结构完整性、是否包含违禁词
6
存储报告
写入 analysis_reports 表，状态标记为 published
7
触发推送
如报告包含高价值信号，触发推送通知

4.5 analysis_reports 表设计
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
match_id
BIGINT FK
NO
-
关联 matches.id
prediction_id
BIGINT FK
YES
-
关联 predictions.id
title
VARCHAR(200)
NO
-
报告标题
content_md
TEXT
NO
-
Markdown 格式正文
content_html
TEXT
YES
-
渲染后的 HTML
summary
VARCHAR(500)
NO
-
摘要（用于预览和 OG 描述）
model_used
VARCHAR(30)
NO
-
使用的 LLM 模型
prompt_tokens
INTEGER
YES
-
输入 token 数
completion_tokens
INTEGER
YES
-
输出 token 数
status
VARCHAR(20)
NO
draft
draft/published/failed
generated_at
TIMESTAMPTZ
NO
-
生成时间
published_at
TIMESTAMPTZ
YES
-
发布时间
created_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(match_id) WHERE status=&apos;published&apos;；idx_reports_published (published_at DESC)

5. 推送服务设计 (M6)
5.1 推送场景
#
推送场景
触发条件
目标用户
1
高价值信号推送
赔率分析发现 ⭐⭐⭐ 信号
基础订阅 + 高阶订阅
2
赛前报告推送
AI 报告生成完成
基础订阅 + 高阶订阅
3
比赛开始提醒
收藏比赛开赛前 30 分钟
所有登录用户
4
红单通知
预测命中（赛后结算）
所有登录用户
5
战绩里程碑
达到连红记录/ROI 新高等
所有用户（营销）

5.2 推送渠道
渠道
技术方案
覆盖用户
优先级
微信服务号
微信模板消息 API
关注公众号的用户
P0 核心
Web Push
Web Push API + Service Worker
浏览器用户
P0 核心
App Push
JPush / Firebase FCM
App 用户（如有）
P1
邮件
SendGrid / AWS SES
注册了邮箱的用户
P2
短信
阿里云短信
仅用于验证码，不做营销
P2

5.3 推送 API 与数据表
5.3.1 push_notifications 表
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
目标用户
channel
VARCHAR(20)
NO
-
wechat/web_push/email/app_push
notification_type
VARCHAR(30)
NO
-
high_ev/report/match_start/red_hit/milestone
title
VARCHAR(200)
NO
-
推送标题
body
TEXT
NO
-
推送内容
target_url
TEXT
YES
-
点击跳转 URL
status
VARCHAR(20)
NO
pending
pending/sent/failed/clicked
sent_at
TIMESTAMPTZ
YES
-
发送时间
clicked_at
TIMESTAMPTZ
YES
-
点击时间
meta
JSONB
YES
-
推送平台返回的元数据
created_at
TIMESTAMPTZ
NO
NOW()

索引: idx_push_user (user_id, created_at DESC)；idx_push_status

5.3.2 user_push_settings 表
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
关联 users.id，UNIQUE
wechat_openid
VARCHAR(100)
YES
-
微信服务号 openid
web_push_subscription
JSONB
YES
-
Web Push 订阅信息
enable_high_ev
BOOLEAN
NO
true
是否接收高价值信号
enable_reports
BOOLEAN
NO
true
是否接收报告通知
enable_match_start
BOOLEAN
NO
true
是否接收开赛提醒
enable_red_hit
BOOLEAN
NO
true
是否接收红单通知
quiet_hours_start
TIME
YES
-
免打扰开始时间
quiet_hours_end
TIME
YES
-
免打扰结束时间
updated_at
TIMESTAMPTZ
NO
NOW()


5.4 推送限流策略
规则
说明
每人每天最多 5 条
避免推送疲劳，超出后只发送最高优先级
高 EV 推送最多 3 条/天
只推送 ⭐⭐⭐ 信号，不推 ⭐ 级别
免打扰时间段
用户可设置免打扰时间，该时段内推送延迟到时段结束
重复推送去重
同一比赛同一类型不重复推送
退订即停
用户关闭某类型推送后立即生效

6. 蒙特卡洛赛事模拟设计
6.1 模拟原理
使用蒙特卡洛方法模拟整届世界杯赛事进程。对每场未进行的比赛，基于模型预测的 λ_home 和 λ_away 随机生成比分，模拟完整的小组赛 + 淘汰赛过程。重复 N 次（默认 10000 次），统计每队的出线概率、各阶段晋级概率和最终夺冠概率。

6.2 模拟流程
步骤
操作
详细
1
加载赛事结构
读取世界杯小组赛分组、淘汰赛对阵规则
2
加载已知结果
已完成的比赛使用真实比分，不再模拟
3
获取模型预测
对每场未进行的比赛获取 λ_home / λ_away
4
模拟单场比赛
基于 λ 值随机生成泊松分布比分
5
模拟小组赛排名
根据模拟比分计算积分榜，确定小组排名
6
模拟淘汰赛
按赛制规则进行淘汰赛模拟（含加时赛/点球大战逻辑）
7
记录结果
记录每次模拟中各队的最终排名
8
统计概率
N 次模拟后，统计各队在各阶段的概率

6.3 输出数据结构
字段
说明
group_advance_prob
各队小组出线概率（前2名）
group_winner_prob
各队小组第一概率
round_of_16_prob
各队进入16强概率
quarter_final_prob
各队进入8强概率
semi_final_prob
各队进入4强概率
final_prob
各队进入决赛概率
champion_prob
各队夺冠概率
most_likely_bracket
最可能的淘汰赛对阵路径

6.4 simulation_results 表
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
simulation_version
VARCHAR(30)
NO
-
模拟版本/时间标识
num_simulations
INTEGER
NO
10000
模拟次数
model_version
VARCHAR(30)
NO
-
使用的模型版本
results
JSONB
NO
-
完整模拟结果（各队各阶段概率）
computed_at
TIMESTAMPTZ
NO
NOW()
计算时间
created_at
TIMESTAMPTZ
NO
NOW()

索引: idx_simulation_latest (computed_at DESC)
ℹ 模拟在每个比赛日结束后自动重新运行（已知比赛结果更新后），赛事期间约每天更新一次。模拟结果通过 Redis 缓存（TTL 1小时），前端展示夺冠概率排行和可交互的概率 bracket。

7. Phase 4 新增 API 端点
7.1 ML 服务新增端点
方法
端点
说明
POST
/api/v1/predict (model_version 参数)
支持指定 dixon_coles / xgboost / ensemble
GET
/api/v1/models/compare?match_id=X
返回多模型预测对比（公开 P2 功能数据源）
POST
/api/v1/simulation/run
手动触发蒙特卡洛模拟
GET
/api/v1/simulation/latest
获取最新模拟结果

7.2 Java 业务服务新增端点
方法
端点
说明
GET
/api/v1/matches/{id}/report
获取 AI 分析报告（付费内容）
GET
/api/v1/worldcup/simulation
获取夺冠概率排行（公开）
GET
/api/v1/worldcup/team/{id}/path
获取某队的预测晋级路径
GET
/api/v1/push/settings
获取用户推送设置
PUT
/api/v1/push/settings
更新用户推送设置
POST
/api/v1/push/test
发送测试推送（管理员）

8. Phase 4 前端新增页面
8.1 新增路由
路由
页面
权限
SSR/SSG
/match/[id]/report
AI 分析报告页
付费用户
SSR
/worldcup/simulation
夺冠概率 + 模拟页
公开
SSR + ISR
/profile/push-settings
推送设置页
登录用户
CSR

8.2 AI 报告页组件设计
组件
说明
ReportHeader
报告标题、生成时间、模型版本标记
ReportSection
报告各章节渲染（Markdown → HTML），支持折叠展开
DataHighlight
关键数据高亮卡片（xG、伤病人数、EV 值等）
ModelBasis
模型判断依据可视化（特征重要性柱状图）
ReportShareButton
分享报告按钮（生成报告截图卡片）

8.3 蒙特卡洛模拟页组件设计
组件
说明
ChampionRanking
夺冠概率排行榜（柱状图，按概率降序）
SimulationBracket
可交互的淘汰赛概率 bracket，hover 显示各阶段晋级概率
GroupSimulation
各小组的出线概率热力表
TeamPathCard
单队的预测晋级路径（从小组赛到决赛的概率递减瀑布图）
SimulationMeta
模拟参数说明（模型版本、模拟次数、最后更新时间）

9. Phase 4 部署架构增量
服务名
镜像
端口
说明
report-worker
自建 (Python)
-
AI 报告生成 Worker
push-worker
自建 (Python/Java)
-
推送服务 Worker
simulation-worker
自建 (Python)
-
蒙特卡洛模拟 Worker
新增服务依赖：report-worker 依赖 postgres + LLM API（Claude/GPT）；push-worker 依赖 postgres + redis + 微信API/Web Push；simulation-worker 依赖 postgres + ml-api。

10. Phase 4 验收标准
#
验收条件
度量指标
优先级
1
Dixon-Coles 模型回测 ROI 优于 Poisson Baseline
回测报告对比
必须
2
XGBoost 模型回测 Brier Score 优于 Dixon-Coles
回测报告对比
必须
3
集成模型 +EV 回测 ROI &gt; 0 且优于单模型
回测报告对比
必须
4
特征工程 v2 包含 50+ 特征且无数据泄露
特征完整性检查
必须
5
AI 报告在赛前 6h 内自动生成并发布
定时任务正常执行
必须
6
AI 报告内容结构完整、无违禁词
内容校验通过
必须
7
LLM 调用失败时 fallback 模板报告可用
手动触发 fallback 测试
必须
8
高 EV 信号推送在发现后 5 分钟内送达
推送延迟监控
必须
9
微信服务号模板消息正常推送
测试推送成功
必须
10
Web Push 在 Chrome/Safari 正常工作
测试推送成功
必须
11
用户可自定义推送偏好和免打扰时间
设置保存后生效
必须
12
蒙特卡洛模拟产出各队夺冠概率
结果合理（概率和=100%）
必须
13
模拟结果在比赛日结束后自动更新
定时任务正常执行
必须
14
前端夺冠概率页面和 bracket 正确渲染
数据正确、交互流畅
必须
15
所有新模型已注册到 MLflow
MLflow UI 可查看
必须

11. 与 Phase 5 的交接点
交接项
Phase 5 如何使用
集成模型（DC + XGB）
Phase 5 的高级可视化使用多模型对比数据
AI 报告生成 Pipeline
Phase 5 扩展为营销素材自动生成（短视频脚本等）
推送服务基础设施
Phase 5 运营后台可手动触发推送
蒙特卡洛模拟
Phase 5 的交互式 bracket 使用模拟数据
analysis_reports 表
Phase 5 运营后台的内容表现分析
push_notifications 表
Phase 5 运营后台的推送效果分析
全部 ML 模型在 MLflow
Phase 5 CI/CD 自动化部署模型


— Phase 4 详细设计文档结束 —

