





⚽
World Cup 2026 Predictor
AI赛事预测平台
Phase 2 — ML Baseline 详细设计文档 (DDD)


版本: v1.0  |  日期: 2026年5月1日  |  详细设计阶段

1. 文档说明
1.1 文档定位
本文档是 Phase 2（ML Baseline）的详细设计文档，基于 HLD v1.0 和 Phase 1 详细设计编写。本文档定义 ML 引擎模块的完整设计，包括特征工程、模型算法、推理服务 API、赔率分析器、MLflow 实验管理和回测框架。
1.2 Phase 2 目标回顾
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
/predict、/odds-analysis 接口
MLflow 设置
模型版本管理
MLflow 实验追踪环境
1.3 与 Phase 1 的依赖
Phase 2 依赖 Phase 1 的以下输出：matches + match_stats 表提供比赛和统计数据；elo_ratings 表提供 Elo 特征；odds_snapshots 表提供赔率数据；injuries + player_valuations 提供伤病和身价数据；Kafka 事件流触发实时推理。

2. 特征工程详细设计
2.1 特征总览
Phase 2 v1 特征共计 28 个基础特征，分为 6 个特征组。每个特征都以比赛为单位计算，分别为主队和客队生成。
#
特征组
包含特征数
数据来源
计算复杂度
1
Elo 评分特征
4 个
elo_ratings 表
低
2
近期战绩特征
8 个
matches 表
中
3
进攻/防守特征
6 个
match_stats 表
中
4
主客场特征
4 个
matches 表
低
5
历史交锋特征
3 个
h2h_records 表
低
6
球队实力特征
3 个
teams + player_valuations
低

2.2 特征详细定义
2.2.1 Elo 评分特征组
特征名
类型
计算逻辑
home_elo
float
主队当前 Elo 评分，取 elo_ratings 表中最新一条记录
away_elo
float
客队当前 Elo 评分
elo_diff
float
home_elo - away_elo，正值表示主队更强
elo_win_prob
float
基于 Elo 差计算的预期胜率: 1 / (1 + 10^(-elo_diff/400))
ℹ Elo 评分初始值为 1500，K 值国家队用 60，俱乐部用 40。世界杯赛事 K 值可调高到 80。Phase 1 的 elo_ratings 表已预计算完成。

2.2.2 近期战绩特征组
特征名
类型
计算逻辑
home_win_rate_last5
float
主队近 5 场比赛胜率（不区分主客场）
away_win_rate_last5
float
客队近 5 场比赛胜率
home_goals_scored_avg5
float
主队近 5 场均进球数
away_goals_scored_avg5
float
客队近 5 场均进球数
home_goals_conceded_avg5
float
主队近 5 场均失球数
away_goals_conceded_avg5
float
客队近 5 场均失球数
home_unbeaten_streak
int
主队当前连续不败场次（上限 20）
away_unbeaten_streak
int
客队当前连续不败场次
⚠ 近 N 场计算时，仅统计比赛日期在当前比赛之前的已结束比赛，严格避免数据泄露。国家队比赛和俱乐部比赛分开统计（两套独立的近期战绩）。

2.2.3 进攻/防守特征组
特征名
类型
计算逻辑
home_xg_avg5
float
主队近 5 场均 xG（若无 xG 数据则 fallback 为实际进球数）
away_xg_avg5
float
客队近 5 场均 xG
home_xg_against_avg5
float
主队近 5 场均被射 xG
away_xg_against_avg5
float
客队近 5 场均被射 xG
home_shot_accuracy_avg5
float
主队近 5 场均射正率 (shots_on_target/shots)
away_shot_accuracy_avg5
float
客队近 5 场均射正率

2.2.4 主客场特征组
特征名
类型
计算逻辑
home_home_win_rate
float
主队本赛季主场胜率
away_away_win_rate
float
客队本赛季客场胜率
home_home_goals_avg
float
主队本赛季主场均进球
away_away_goals_avg
float
客队本赛季客场均进球
ℹ 国家队比赛主客场效应较弱，可尝试对国家队比赛的主场优势系数做衰减处理。

2.2.5 历史交锋特征组
特征名
类型
计算逻辑
h2h_home_win_rate
float
历史交锋中主队胜率（从 h2h_records 表计算）
h2h_total_matches
int
历史交锋总场次（上限 cap 在 50）
h2h_avg_goals
float
历史交锋均总进球数

2.2.6 球队实力特征组
特征名
类型
计算逻辑
home_squad_value_log
float
主队球员总身价 log10（欧元），来自 player_valuations 最新记录
away_squad_value_log
float
客队球员总身价 log10
value_ratio
float
home_squad_value / away_squad_value，取对数比值避免极端值

2.3 特征计算 Pipeline 设计
2.3.1 Pipeline 架构
特征计算采用两阶段架构：离线批量计算（训练用）+ 在线实时计算（推理用）。
模式
说明
触发时机
离线批量
为所有历史比赛计算特征矩阵，存储为 Parquet 文件
模型训练前 / 每日更新
在线实时
为单场比赛计算特征向量，直接查 DB
API 请求时实时计算

2.3.2 特征存储 Schema
离线计算的特征矩阵存储在 PostgreSQL 的 match_features 表中，同时导出为 Parquet 文件供训练使用。
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
关联 matches.id，UNIQUE
feature_version
VARCHAR(10)
NO
-
特征版本号，如 &apos;v1&apos;
features
JSONB
NO
-
全部特征的 JSON 字典
label_home_score
SMALLINT
YES
-
实际主队进球（标签）
label_away_score
SMALLINT
YES
-
实际客队进球（标签）
label_result
VARCHAR(5)
YES
-
H/D/A 胜平负结果标签
computed_at
TIMESTAMPTZ
NO
NOW()
计算时间
created_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(match_id, feature_version)
⚠ 使用 JSONB 存储特征而非每个特征一列，原因是特征集会频繁变化（新增/删除特征），JSONB 避免频繁的 Schema 迁移。feature_version 字段确保不同版本特征可共存。

2.4 数据泄露防护设计
数据泄露是赛事预测模型最常见的错误。以下是必须严格执行的防护措施：
#
防护规则
实现方式
1
时间截断严格执行
所有特征计算仅使用 match_date 之前的数据，通过 SQL WHERE match_date &lt; :current_match_date 强制
2
训练/测试集按时间划分
绝对禁止随机划分，必须用时间截断点分割，如 2025-01-01 之前训练、之后测试
3
比赛结果不进入特征
比分、胜负只作为 label，绝不作为同场比赛的特征
4
赔率特征用赛前快照
仅使用 snapshot_at &lt; match_date 的赔率数据，不使用赛后最终赔率
5
特征计算函数参数化
每个计算函数必须接受 cutoff_date 参数，禁止硬编码时间

3. 模型详细设计
3.1 Poisson Baseline 模型
3.1.1 算法原理
泊松模型假设足球比赛中每队的进球数服从泊松分布，即 P(k goals) = (λ^k * e^(-λ)) / k!，其中 λ 是该队的期望进球数。核心任务是为每场比赛估计主队和客队的 λ 值。

3.1.2 参数估计
采用对数线性回归估计 λ：
log(λ_home) = intercept + attack_home + defense_away + home_advantage
log(λ_away) = intercept + attack_away + defense_home

其中 attack_i 和 defense_i 是每支球队的进攻和防守强度参数，home_advantage 是主场优势参数。使用最大似然估计 (MLE) 或贝叶斯 MCMC 估计参数。
Phase 2 采用简化版本：直接用历史平均进球/失球率结合特征加权计算 λ。Phase 4 的 Dixon-Coles 会用更严格的统计估计。

3.1.3 λ 计算公式（简化版）
对于一场比赛（主队 A vs 客队 B）：
λ_A = league_avg_goals * (A_attack_strength / league_avg_attack) * (B_defense_weakness / league_avg_defense) * home_factor
λ_B = league_avg_goals * (B_attack_strength / league_avg_attack) * (A_defense_weakness / league_avg_defense)

其中：
参数
计算方式
league_avg_goals
整个训练集场均进球数（通常约 1.3-1.5）
A_attack_strength
球队 A 场均进球数（加权: xG 占 60%，实际进球占 40%）
B_defense_weakness
球队 B 场均失球数（同样加权）
home_factor
主场优势系数，默认 1.2，可通过训练集实际统计调整
Elo 修正
若 Elo 差 &gt; 200，额外对 λ 做 ±5% 修正

3.1.4 概率输出计算
基于 λ_home 和 λ_away，计算以下概率矩阵：
比分概率矩阵（Score Matrix）
遍历 0-9 进球数组合，计算每个比分 (i, j) 的概率：P(i, j) = P_poisson(λ_home, i) * P_poisson(λ_away, j)。输出 10×10 的概率矩阵。

胜平负概率（1X2）
P(Home Win) = ∑ P(i,j) where i &gt; j；P(Draw) = ∑ P(i,j) where i == j；P(Away Win) = ∑ P(i,j) where i &lt; j。三个概率之和必须 = 1.0。

大小球概率（Over/Under）
对于每个盘口 N（如 2.5）：P(Over N) = ∑ P(i,j) where i+j &gt; N；P(Under N) = 1 - P(Over N)。

BTTS（双方进球）
P(BTTS Yes) = ∑ P(i,j) where i &gt;= 1 AND j &gt;= 1。

Top 10 比分预测
从比分概率矩阵中取概率最高的 10 个比分，作为推荐比分输出。

3.2 模型置信度设计
置信度让用户知道模型对这场预测的确定程度。Phase 2 采用简单的复合置信度计算：
置信度因子
权重
逻辑
概率集中度
40%
胜平负最大概率 vs 第二大概率的差值，差值越大越自信
数据完整度
30%
match_features 中非空特征占比，越完整越可靠
历史样本量
20%
两队历史比赛数量，越多越可靠
Elo 差异确定性
10%
Elo 差绝对值越大，实力差距越明确
最终置信度输出为 0-100 的整数，并映射到三个等级：低置信度（0-40）、中置信度（41-70）、高置信度（71-100）。付费用户可按置信度筛选预测。

4. 赔率分析器详细设计
赔率分析器是本产品的核心价值模块——将模型概率与博彩公司赔率对比，发现正期望值 (+EV) 投注机会。
4.1 核心计算流程
步骤
名称
详细
1
赔率转换为隐含概率
implied_prob = 1 / decimal_odds，多结果合计 &gt; 1.0（这是博彩公司的利润率）
2
去除抽水（Vig Removal）
将隐含概率归一化到和为 1.0，方法: fair_prob = implied_prob / sum(implied_probs)
3
计算 EV（期望值）
EV = (model_prob * decimal_odds) - 1，EV &gt; 0 表示模型认为赔率有价值
4
计算 Edge（边缘）
edge = model_prob - fair_prob，正值表示模型概率高于博彩公司评估
5
标记价值信号
EV &gt; 0.05 且 edge &gt; 0.03 表示有价值信号
6
价值强度排序
按 EV 降序排列，让用户快速找到最佳机会

4.2 EV 计算示例
假设某场比赛，模型预测主胜概率 55%，博彩公司主胜赔率 2.10：
implied_prob = 1 / 2.10 = 0.476 (47.6%)
model_prob   = 0.55  (55.0%)
EV = (0.55 * 2.10) - 1 = 0.155 (+15.5%)
edge = 0.55 - 0.476 = 0.074 (+7.4%)

结论：这是一个强价值信号（EV=15.5% &gt; 5% 阈值，edge=7.4% &gt; 3% 阈值）。

4.3 价值信号分级
信号等级
EV 范围
edge 范围
前端展示
⭐⭐⭐ 强烈推荐
EV &gt; 15%
edge &gt; 8%
金色标签 + 推送通知
⭐⭐ 推荐
EV 8%-15%
edge 5%-8%
蓝色标签
⭐ 可关注
EV 5%-8%
edge 3%-5%
灰色标签
无信号
EV &lt; 5%
edge &lt; 3%
不显示价值标签

4.4 多家赔率对比
系统会同时分析多家博彩公司的赔率，找出每个市场的最佳赔率。输出结构包括：每个博彩公司的赔率对比、每个结果的最佳赔率及对应博彩公司、基于最佳赔率计算的 EV。

4.5 赔率分析结果存储
新增 odds_analysis 表存储每场比赛的 EV 分析结果：
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
NO
-
关联 predictions.id
market_type
VARCHAR(30)
NO
-
1x2/over_under/btts/asian_handicap
market_value
VARCHAR(20)
YES
-
盘口值，如 &apos;2.5&apos;
outcome
VARCHAR(20)
NO
-
结果类型: home/draw/away/over/under
model_prob
NUMERIC(5,4)
NO
-
模型概率
best_odds
NUMERIC(6,3)
NO
-
最佳赔率
best_bookmaker
VARCHAR(50)
NO
-
提供最佳赔率的博彩公司
implied_prob
NUMERIC(5,4)
NO
-
赔率隐含概率（去抽水后）
ev
NUMERIC(6,4)
NO
-
期望值
edge
NUMERIC(5,4)
NO
-
边缘值
signal_level
SMALLINT
NO
0
信号等级 0-3
analyzed_at
TIMESTAMPTZ
NO
NOW()
分析时间
created_at
TIMESTAMPTZ
NO
NOW()

索引: idx_odds_analysis_match (match_id)；idx_odds_analysis_signal (signal_level DESC, analyzed_at DESC)；idx_odds_analysis_market (market_type)

5. 预测结果存储设计
根据 PRD 要求，所有预测发布后不可篆改。这是建立用户信任的核心机制。
5.1 predictions 表（只追加表）
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
model_version
VARCHAR(30)
NO
-
模型版本，如 &apos;poisson_v1&apos;
feature_version
VARCHAR(10)
NO
-
特征版本
prob_home_win
NUMERIC(5,4)
NO
-
主胜概率
prob_draw
NUMERIC(5,4)
NO
-
平局概率
prob_away_win
NUMERIC(5,4)
NO
-
客胜概率
lambda_home
NUMERIC(5,3)
NO
-
主队期望进球数
lambda_away
NUMERIC(5,3)
NO
-
客队期望进球数
score_matrix
JSONB
NO
-
10x10 比分概率矩阵
top_scores
JSONB
NO
-
Top 10 比分预测 [{score, prob}]
over_under_probs
JSONB
NO
-
各盘口大小球概率
btts_prob
NUMERIC(5,4)
YES
-
双方进球概率
confidence_score
SMALLINT
NO
-
置信度 0-100
confidence_level
VARCHAR(10)
NO
-
low/medium/high
features_snapshot
JSONB
NO
-
生成预测时的特征快照
content_hash
VARCHAR(64)
NO
-
SHA-256（用于完整性校验）
published_at
TIMESTAMPTZ
NO
-
发布时间（发布后不可修改）
created_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(match_id, model_version)；idx_predictions_published (published_at DESC)；idx_predictions_confidence (confidence_score DESC)

5.2 不可篆改机制
机制
实现方式
content_hash
对预测结果的全部字段计算 SHA-256 哈希，存储在 content_hash 字段
DB 规则约束
predictions 表不允许 UPDATE/DELETE，通过 PostgreSQL 触发器禁止修改已发布记录
审计日志
所有对 predictions 表的操作都记录在审计日志中
features_snapshot
发布时快照保存当时的特征向量，可复现预测过程
后期增强
考虑引入哈希链或第三方存证服务

6. FastAPI 推理服务 API 设计
6.1 服务总览
FastAPI 推理服务是 ML 引擎对外的唯一接口，负责接收比赛 ID、计算特征、调用模型、返回预测结果和赔率分析。服务运行在独立的 Python 容器中。

6.2 API 端点设计
6.2.1 POST /api/v1/predict
为指定比赛生成预测结果。
Request Body:
字段
类型
必填
说明
match_id
integer
是
比赛 ID
model_version
string
否
模型版本，默认 &apos;latest&apos;
include_score_matrix
boolean
否
是否返回完整比分矩阵，默认 false
publish
boolean
否
是否立即发布（写入 predictions 表），默认 false

Response Body (200 OK):
字段
类型
说明
match_id
integer
比赛 ID
model_version
string
使用的模型版本
home_team
string
主队名称
away_team
string
客队名称
match_date
string (ISO)
比赛时间
predictions.result_1x2
object
{home: 0.45, draw: 0.28, away: 0.27}
predictions.lambda_home
float
主队期望进球数
predictions.lambda_away
float
客队期望进球数
predictions.top_scores
array
[{score: &apos;1-0&apos;, prob: 0.12}, ...]
predictions.over_under
object
{2.5: {over: 0.55, under: 0.45}, ...}
predictions.btts
object
{yes: 0.52, no: 0.48}
predictions.score_matrix
array[][]
10x10 矩阵（仅 include_score_matrix=true）
confidence
object
{score: 72, level: &apos;high&apos;}
features_used
object
使用的特征值摘要
prediction_id
integer|null
如 publish=true，返回已存储的预测 ID

6.2.2 POST /api/v1/odds-analysis
对指定比赛进行赔率价值分析。
Request Body:
字段
类型
必填
说明
match_id
integer
是
比赛 ID
markets
string[]
否
分析的市场类型，默认 [&apos;1x2&apos;, &apos;over_under_2.5&apos;]
bookmakers
string[]
否
指定博彩公司，默认全部

Response Body (200 OK):
字段
类型
说明
match_id
integer
比赛 ID
analysis_time
string (ISO)
分析时间
markets[].market_type
string
市场类型
markets[].outcomes[]
array
每个结果的分析
.outcome
string
home/draw/away/over/under
.model_prob
float
模型概率
.bookmakers[]
array
各博彩公司赔率
.best_odds
float
最佳赔率
.best_bookmaker
string
提供最佳赔率的博彩公司
.ev
float
期望值
.edge
float
边缘值
.signal_level
integer
信号等级 0-3
value_signals[]
array
全部有价值的机会，按 EV 降序

6.2.3 GET /api/v1/predictions/today
获取今日所有比赛的预测结果和价值信号。此接口会被 Phase 3 前端高频调用。
参数
类型
必填
说明
date
string (YYYY-MM-DD)
否
查询日期，默认今天
min_confidence
integer
否
最低置信度筛选，默认 0
min_signal
integer
否
最低价值信号筛选，默认 0
competition_id
integer
否
赛事筛选
Response: 返回比赛列表，每场包含预测摘要和价值信号。结果缓存在 Redis，TTL 5 分钟。

6.2.4 GET /api/v1/predictions/{prediction_id}
获取单场预测的完整详情，包括完整比分矩阵、所有市场的赔率分析、特征值等。

6.2.5 GET /api/v1/model/health
模型服务健康检查接口，返回当前加载的模型版本、最后训练时间、服务状态。

6.3 认证与限流
配置项
说明
服务间认证
Java 业务服务通过 API Key 调用 ML 服务，不直接暴露给前端
速率限制
默认 100 req/min，用于保护 ML 推理服务不被压垂
缓存策略
同一比赛同一模型版本的预测结果缓存 5 分钟
超时设置
推理请求超时 10s，特征计算超时 5s

7. 历史回测框架设计
7.1 回测目的
回测是验证模型有效性的唯一方法。核心目标：对模型标记为正 EV 的比赛，假设每场等额下注，长期 ROI 是否为正。这直接对应 PRD 的核心模型评估指标。

7.2 回测方法论
7.2.1 时间序列交叉验证
采用滚动窗口（Rolling Window）方法，模拟真实场景：
参数
设定
训练窗口
最近 12 个月比赛数据（滚动更新）
测试窗口
接下来 1 个月的比赛
滚动步长
1 个月
最早起始点
2023年1月（确保至少 12 个月训练数据）
测试期总范围
2023年1月 - 2026年4月（约 40 个滚动窗口）

7.2.2 核心评估指标
指标
类型
说明
ROI (投资回报率)
商业核心
对模型标记正 EV 的比赛，假设等额下注，计算累计回报
Accuracy (命中率)
基础
胜平负预测的正确率
Brier Score
概率校准
衡量概率预测质量的标准指标，越小越好
校准曲线
概率校准
模型预测概率 vs 实际频率的对比图
+EV 命中率
价值发现
标记为正 EV 的比赛中实际命中的比例
+EV 累计 ROI
价值发现
仅对正 EV 比赛的累计投资回报率
按信号等级 ROI
分层分析
各信号等级（⭐/⭐⭐/⭐⭐⭐）的独立 ROI
按盘口类型 ROI
分层分析
胜平负/比分/大小球/让球各自的 ROI

7.3 回测报告输出
回测结束后自动生成 HTML 报告，包含以下内容：
#
报告章节
内容
1
执行摘要
模型版本、回测时间范围、总比赛数、核心指标概览
2
ROI 累计曲线图
按时间的累计 ROI 变化图（最重要的可视化）
3
概率校准图
模型概率 vs 实际频率的散点图 + 对角线
4
分层分析表
按信号等级、盘口类型、赛事的分别统计
5
每月详细数据
每个滚动窗口的独立指标
6
失败分析
最大亏损的比赛、连败记录、特征分布异常
7
结论与建议
是否达到上线标准、优化方向

7.4 回测基准线
为了评估模型的价值，需要与以下基准线对比：
基准线
说明
Random Baseline
随机预测胜平负，命中率应约 33%，ROI 应为负值（抽水影响）
Odds-Implied Baseline
直接用博彩公司赔率隐含概率作为预测，是很强的基准线
Home Win Baseline
永远预测主胜，测试主场优势的强度
Elo-Only Baseline
仅用 Elo 评分差预测，测试其他特征的增量价值

8. MLflow 实验管理设计
8.1 MLflow 配置
配置项
设定
部署方式
Docker 容器，Phase 1 的 docker-compose.yml 中新增 mlflow-server 服务
Tracking URI
http://mlflow:5000
Backend Store
postgresql://mlflow:pass@postgres:5432/mlflow
Artifact Store
s3://wcp-mlflow-artifacts/ 或本地 /data/mlflow-artifacts
UI 访问
http://localhost:5000 (开发环境)

8.2 实验组织结构
Experiment
说明
包含的 Run
wcp-poisson-baseline
泊松基线模型实验
不同超参数组合的训练 run
wcp-feature-engineering
特征工程实验
不同特征组合的对比 run
wcp-backtest
回测实验
每次回测作为一个 run
wcp-dixon-coles
Phase 4 Dixon-Coles 模型
预留
wcp-xgboost
Phase 4 XGBoost 模型
预留

8.3 Run 记录规范
每次训练/回测运行必须记录以下信息：
类别
记录内容
示例
Parameters
训练集时间范围、特征版本、模型超参数、home_factor、xg_weight
train_start=2022-11，xg_weight=0.6
Metrics
accuracy、brier_score、roi_all、roi_positive_ev、calibration_error
roi_positive_ev=0.034
Tags
模型类型、环境、开发者
model_type=poisson_v1
Artifacts
模型文件、回测报告 HTML、特征重要性图
backtest_report.html

8.4 模型注册与部署
使用 MLflow Model Registry 管理模型的生命周期：
阶段
操作
说明
Staging
回测通过后注册
模型在 Staging 环境接受进一步验证
Production
确认无误后提升
FastAPI 服务自动加载 Production 版本
Archived
旧版本归档
保留历史记录但不再使用

9. Phase 2 项目结构
以下为 Phase 2 新增的目录结构（在 Phase 1 基础上扩展）：
worldcup-predictor/
├── src/
│   ├── adapters/              # Phase 1 已有
│   ├── models/                # Phase 1 已有 + 新增 match_features 模型
│   ├── ml/                    # ⭐ Phase 2 新增
│   │   ├── features/
│   │   │   ├── base.py           # BaseFeatureCalculator 基类
│   │   │   ├── elo.py            # Elo 特征计算
│   │   │   ├── recent_form.py    # 近期战绩特征
│   │   │   ├── attack_defense.py # 进攻/防守特征
│   │   │   ├── home_away.py      # 主客场特征
│   │   │   ├── h2h.py            # 历史交锋特征
│   │   │   ├── team_strength.py  # 球队实力特征
│   │   │   └── pipeline.py       # 特征组装 Pipeline
│   │   ├── models/
│   │   │   ├── base.py           # BasePredictionModel 抽象基类
│   │   │   ├── poisson.py        # PoissonBaselineModel
│   │   │   └── confidence.py     # ConfidenceCalculator
│   │   ├── odds/
│   │   │   ├── analyzer.py       # OddsAnalyzer
│   │   │   ├── vig_removal.py    # 抽水去除
│   │   │   └── ev_calculator.py  # EV 计算
│   │   ├── backtest/
│   │   │   ├── runner.py         # BacktestRunner
│   │   │   ├── evaluator.py      # 指标计算
│   │   │   ├── report.py         # HTML 报告生成
│   │   │   └── baselines.py      # 基准线模型
│   │   └── training/
│   │       ├── trainer.py        # 模型训练入口
│   │       └── mlflow_utils.py   # MLflow 工具函数
│   ├── api/                   # ⭐ Phase 2 新增
│   │   ├── main.py           # FastAPI app 入口
│   │   ├── routes/
│   │   │   ├── predict.py    # /api/v1/predict
│   │   │   ├── odds.py       # /api/v1/odds-analysis
│   │   │   ├── predictions.py# /api/v1/predictions/*
│   │   │   └── health.py     # /api/v1/model/health
│   │   ├── schemas/
│   │   │   ├── predict.py    # Request/Response Pydantic 模型
│   │   │   └── odds.py
│   │   ├── dependencies.py   # 依赖注入
│   │   └── middleware.py     # 认证、限流中间件
│   └── ...                    # Phase 1 其他目录
├── scripts/
│   ├── compute_features.py    # 离线特征计算脚本
│   ├── train_model.py         # 模型训练脚本
│   └── run_backtest.py        # 回测执行脚本
├── notebooks/
│   ├── 01_eda.ipynb           # 探索性数据分析
│   ├── 02_feature_analysis.ipynb
│   └── 03_model_experiments.ipynb
└── ...

10. Phase 2 部署架构增量
在 Phase 1 的 docker-compose.yml 基础上新增以下服务：
服务名
镜像
端口
说明
ml-api
自建 (FastAPI)
8000
ML 推理服务
mlflow-server
ghcr.io/mlflow/mlflow
5000
MLflow Tracking Server
ml-worker
自建
-
离线训练/回测 Worker

服务依赖关系：ml-api 依赖 postgres + redis + mlflow-server；ml-worker 依赖 postgres + mlflow-server；所有 Phase 1 服务保持不变。

11. Phase 2 验收标准
#
验收条件
度量指标
优先级
1
特征 Pipeline 能为所有历史比赛计算特征
match_features 表覆盖率 &gt; 95%
必须
2
Poisson 模型胜平负命中率 &gt; 随机基准线
命中率 &gt; 40%（随机约 33%）
必须
3
模型标记的正 EV 比赛累计 ROI &gt; 0
回测报告确认
必须
4
FastAPI /predict 接口响应时间 &lt; 500ms
压测结果
必须
5
FastAPI /odds-analysis 接口正常工作
返回正确的 EV 和信号等级
必须
6
/predictions/today 接口返回今日比赛预测
数据正确且响应 &lt; 2s
必须
7
预测结果发布后不可修改
尝试 UPDATE 被触发器拦截
必须
8
MLflow 实验追踪正常运行
能看到训练 run 和指标
必须
9
回测报告自动生成
HTML 报告包含所有核心指标和图表
必须
10
数据泄露检查通过
所有特征计算仅用历史数据
必须
11
content_hash 校验机制正常
能检测到篆改
必须
12
单元测试覆盖特征/模型/API 核心逻辑
覆盖率 &gt; 80%
建议

12. 与 Phase 3 的交接点
交接项
Phase 3 如何使用
FastAPI /predict 接口
Java 业务服务调用获取预测结果，分发给前端
FastAPI /odds-analysis 接口
业务服务获取赔率分析，根据用户订阅层级决定展示粒度
FastAPI /predictions/today 接口
前端赛程页的预测数据源
predictions 表
战绩系统 (M5) 对比预测结果与实际结果
odds_analysis 表
前端价值信号标签的数据源
置信度数据
付费用户的置信度筛选功能
content_hash 机制
分享卡片和战绩页的信任背书


— Phase 2 详细设计文档结束 —

