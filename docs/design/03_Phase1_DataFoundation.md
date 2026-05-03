





⚽
World Cup 2026 Predictor
AI赛事预测平台
Phase 1 — 数据基座 详细设计文档 (DDD)


版本: v1.0  |  日期: 2026年5月1日  |  详细设计阶段

1. 文档说明
1.1 文档定位
本文档是 World Cup 2026 Predictor 项目 Phase 1（数据基座）的详细设计文档，基于 HLD v1.0 编写。本文档定义数据库完整 Schema、数据采集模块的接口设计、类图、配置规范和部署方案，作为开发团队的编码依据。
1.2 Phase 1 目标回顾
根据 HLD 定义，Phase 1 的目标是：搭建数据采集和存储基础设施，采集全部历史数据。2-3周周期，涉及 M1 数据采集模块。
任务
说明
交付物
数据库 Schema 设计
定义核心实体表结构
PostgreSQL 迁移脚本
数据源 Adapter 开发
实现各数据源的采集适配器
6 个 Adapter 实现
历史数据采集
2022世界杯至今的比赛数据
4000-5000 场比赛数据入库
赔率数据采集
接入赔率 API / 爬虫
历史赔率数据入库
数据清洗 Pipeline
Celery 定时任务 + Kafka 事件流
自动化采集流水线
1.3 术语约定
术语
说明
DDD
Detailed Design Document，详细设计文档
Adapter
数据源适配器，统一接口封装不同数据源的采集逻辑
Pipeline
数据处理流水线，从采集到清洗到入库的完整链路
Celery Beat
Celery 定时任务调度器
Schema Validation
数据入库前的结构校验（字段类型、范围、非空约束）

2. 数据库 Schema 详细设计
本章定义 Phase 1 所有核心表的完整字段、类型、索引和约束。所有表使用 PostgreSQL，版本 &gt;= 15。命名规范：表名使用复数形式 snake_case，字段名使用 snake_case，主键统一使用 BIGSERIAL，时间字段统一使用 TIMESTAMPTZ。
2.1 Schema 概览——表清单
#
表名
说明
预估行数
所属域
1
competitions
赛事信息（世界杯、英超等）
~20
基座数据
2
seasons
赛季信息
~60
基座数据
3
teams
球队基本信息
~500
基座数据
4
players
球员基本信息
~8000
基座数据
5
matches
比赛基本信息、比分
~5000
比赛数据
6
match_stats
比赛统计数据（xG、射门等）
~10000
统计数据
7
match_lineups
比赛阵容（首发+替补）
~120000
比赛数据
8
player_stats
球员单场统计
~120000
统计数据
9
player_valuations
球员身价历史
~30000
身价数据
10
injuries
伤病记录
~15000
伤病数据
11
odds_snapshots
赔率快照（时间序列）
~500000
赔率数据
12
h2h_records
历史交锋记录
~3000
基座数据
13
data_source_logs
数据采集审计日志
无上限
运维
14
elo_ratings
球队 Elo 评分历史
~50000
特征数据

2.2 各表详细定义
2.2.1 competitions — 赛事表
存储赛事基本信息，包括世界杯、五大联赛、洲际赛事等。
字段
类型
NULL
默认值
说明
id
BIGSERIAL PK
NO
auto
主键
api_football_id
INTEGER
YES
-
外部数据源 ID，用于去重
name
VARCHAR(200)
NO
-
赛事名称，如 &apos;FIFA World Cup 2026&apos;
name_zh
VARCHAR(200)
YES
-
中文名称
competition_type
VARCHAR(20)
NO
-
league / cup / international
country
VARCHAR(100)
YES
-
所属国家（联赛）
logo_url
TEXT
YES
-
赛事 logo URL
is_active
BOOLEAN
NO
true
是否活跃采集
created_at
TIMESTAMPTZ
NO
NOW()
创建时间
updated_at
TIMESTAMPTZ
NO
NOW()
更新时间
索引: UNIQUE(api_football_id)；赛事类型 + 国家组合查询使用 idx_competitions_type_country

2.2.2 seasons — 赛季表
赛季信息，一个赛事可能有多个赛季。
字段
类型
NULL
默认值
说明
id
BIGSERIAL PK
NO
auto
主键
competition_id
BIGINT FK
NO
-
关联 competitions.id
year
SMALLINT
NO
-
赛季年份，如 2025
start_date
DATE
YES
-
开赛日期
end_date
DATE
YES
-
结束日期
is_current
BOOLEAN
NO
false
是否当前赛季
created_at
TIMESTAMPTZ
NO
NOW()

updated_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(competition_id, year)

2.2.3 teams — 球队表
球队基本信息，同时覆盖俱乐部和国家队。
字段
类型
NULL
默认值
说明
id
BIGSERIAL PK
NO
auto
主键
api_football_id
INTEGER
YES
-
外部数据源 ID
transfermarkt_id
VARCHAR(50)
YES
-
Transfermarkt slug/id
fbref_id
VARCHAR(50)
YES
-
FBref 球队 ID
name
VARCHAR(200)
NO
-
英文名称
name_zh
VARCHAR(200)
YES
-
中文名称
short_name
VARCHAR(50)
YES
-
缩写
country
VARCHAR(100)
YES
-
所属国家
team_type
VARCHAR(20)
NO
-
club / national
logo_url
TEXT
YES
-
队徽 URL
fifa_ranking
SMALLINT
YES
-
最新 FIFA 排名
fifa_ranking_updated
DATE
YES
-
排名更新日期
confederation
VARCHAR(20)
YES
-
AFC/CAF/CONCACAF/CONMEBOL/OFC/UEFA
created_at
TIMESTAMPTZ
NO
NOW()

updated_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(api_football_id) WHERE api_football_id IS NOT NULL；idx_teams_name；idx_teams_country_type

2.2.4 players — 球员表
字段
类型
NULL
默认值
说明
id
BIGSERIAL PK
NO
auto
主键
api_football_id
INTEGER
YES
-
外部 ID
transfermarkt_id
VARCHAR(50)
YES
-
Transfermarkt ID
fbref_id
VARCHAR(50)
YES
-
FBref ID
name
VARCHAR(200)
NO
-
英文名称
name_zh
VARCHAR(200)
YES
-
中文名称
nationality
VARCHAR(100)
YES
-
国籍
date_of_birth
DATE
YES
-
出生日期
position
VARCHAR(30)
YES
-
GK/DEF/MID/FWD
current_team_id
BIGINT FK
YES
-
当前俱乐部
national_team_id
BIGINT FK
YES
-
国家队
market_value_eur
BIGINT
YES
-
最新身价（欧元）
market_value_updated
DATE
YES
-
身价更新日期
photo_url
TEXT
YES
-
头像
created_at
TIMESTAMPTZ
NO
NOW()

updated_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(api_football_id) WHERE NOT NULL；idx_players_team；idx_players_nationality

2.2.5 matches — 比赛表（核心表）
系统最核心的表，存储比赛基本信息和结果。下游几乎所有模块都依赖此表。
字段
类型
NULL
默认值
说明
id
BIGSERIAL PK
NO
auto
主键
api_football_id
INTEGER
YES
-
外部数据源 ID
season_id
BIGINT FK
NO
-
关联 seasons.id
home_team_id
BIGINT FK
NO
-
主队
away_team_id
BIGINT FK
NO
-
客队
match_date
TIMESTAMPTZ
NO
-
比赛开球时间 (UTC)
venue
VARCHAR(200)
YES
-
比赛场馆
round
VARCHAR(50)
YES
-
轮次，如 &apos;Group A - 1&apos; / &apos;Round of 16&apos;
status
VARCHAR(20)
NO
scheduled
scheduled/live/finished/postponed/cancelled
home_score
SMALLINT
YES
-
主队进球数
away_score
SMALLINT
YES
-
客队进球数
home_score_ht
SMALLINT
YES
-
半场主队进球
away_score_ht
SMALLINT
YES
-
半场客队进球
referee
VARCHAR(100)
YES
-
主裁判
attendance
INTEGER
YES
-
观众人数
data_completeness
SMALLINT
NO
0
数据完整度 0-100
created_at
TIMESTAMPTZ
NO
NOW()

updated_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(api_football_id) WHERE NOT NULL；idx_matches_date (match_date DESC)；idx_matches_season；idx_matches_teams (home_team_id, away_team_id)；idx_matches_status
⚠ status 字段使用 CHECK 约束限制枚举值，不使用独立的枚举表。data_completeness 用于标记数据采集进度，0=仅赛程，50=有比分，100=统计数据完整。

2.2.6 match_stats — 比赛统计表
每场比赛每支球队一行（一场比赛产生 2 行），存储各类统计指标。
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
team_id
BIGINT FK
NO
-
关联 teams.id
is_home
BOOLEAN
NO
-
是否主场
possession
NUMERIC(4,1)
YES
-
控球率 %
shots
SMALLINT
YES
-
射门数
shots_on_target
SMALLINT
YES
-
射正数
xg
NUMERIC(5,2)
YES
-
预期进球数
xg_against
NUMERIC(5,2)
YES
-
被射 xG
passes
SMALLINT
YES
-
传球数
pass_accuracy
NUMERIC(4,1)
YES
-
传球成功率 %
corners
SMALLINT
YES
-
角球数
fouls
SMALLINT
YES
-
犯规数
yellow_cards
SMALLINT
YES
-
黄牌
red_cards
SMALLINT
YES
-
红牌
offsides
SMALLINT
YES
-
越位数
tackles
SMALLINT
YES
-
铲球数
interceptions
SMALLINT
YES
-
拦截数
saves
SMALLINT
YES
-
扑救数
data_source
VARCHAR(30)
NO
-
数据来源：api_football/fbref
created_at
TIMESTAMPTZ
NO
NOW()

updated_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(match_id, team_id)；idx_match_stats_team (team_id, match_id)
⚠ xG 数据主要来源于 FBref，基础统计来源于 API-Football。data_source 字段记录各行数据的实际来源。

2.2.7 match_lineups — 比赛阵容表
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
team_id
BIGINT FK
NO
-
关联 teams.id
player_id
BIGINT FK
NO
-
关联 players.id
is_starter
BOOLEAN
NO
-
是否首发
position
VARCHAR(30)
YES
-
本场位置
jersey_number
SMALLINT
YES
-
球衣号码
minutes_played
SMALLINT
YES
-
上场时间（分钟）
sub_in_minute
SMALLINT
YES
-
替补上场时间
sub_out_minute
SMALLINT
YES
-
被替换下场时间
rating
NUMERIC(3,1)
YES
-
评分（如有）
索引: UNIQUE(match_id, team_id, player_id)；idx_lineups_player

2.2.8 player_stats — 球员单场统计表
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
player_id
BIGINT FK
NO
-
关联 players.id
team_id
BIGINT FK
NO
-
关联 teams.id
goals
SMALLINT
YES
0
进球数
assists
SMALLINT
YES
0
助攻数
xg
NUMERIC(4,2)
YES
-
个人 xG
xa
NUMERIC(4,2)
YES
-
个人 xA
shots
SMALLINT
YES
-
射门数
key_passes
SMALLINT
YES
-
关键传球
tackles
SMALLINT
YES
-
铲球
interceptions
SMALLINT
YES
-
拦截
saves
SMALLINT
YES
-
扑救（守门员）
yellow_cards
SMALLINT
YES
0
黄牌
red_cards
SMALLINT
YES
0
红牌
data_source
VARCHAR(30)
NO
-
数据来源
索引: UNIQUE(match_id, player_id)；idx_player_stats_player；idx_player_stats_team_match

2.2.9 player_valuations — 球员身价历史表
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
player_id
BIGINT FK
NO
-
关联 players.id
team_id
BIGINT FK
YES
-
当时所在球队
value_date
DATE
NO
-
身价日期
market_value_eur
BIGINT
NO
-
身价（欧元）
data_source
VARCHAR(30)
NO
transfermarkt
数据来源
created_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(player_id, value_date)；idx_valuations_date DESC

2.2.10 injuries — 伤病记录表
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
player_id
BIGINT FK
NO
-
关联 players.id
team_id
BIGINT FK
YES
-
当时所在球队
injury_type
VARCHAR(100)
YES
-
伤病类型，如 &apos;Knee Injury&apos;
severity
VARCHAR(20)
YES
-
minor/moderate/major/unknown
start_date
DATE
NO
-
受伤日期
expected_return
DATE
YES
-
预计复出日期
actual_return
DATE
YES
-
实际复出日期
is_active
BOOLEAN
NO
true
是否当前伤病
data_source
VARCHAR(30)
NO
transfermarkt

created_at
TIMESTAMPTZ
NO
NOW()

updated_at
TIMESTAMPTZ
NO
NOW()

索引: idx_injuries_player_active (player_id, is_active)；idx_injuries_team_active

2.2.11 odds_snapshots — 赔率快照表（时间序列）
赔率数据是本产品的核心数据源之一，需要记录时间序列快照以追踪赔率变动。每次采集生成一行，不做更新。
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
bookmaker
VARCHAR(50)
NO
-
博彩公司名称
market_type
VARCHAR(30)
NO
-
1x2/asian_handicap/over_under/btts
market_value
VARCHAR(20)
YES
-
盘口值，如 &apos;2.5&apos; (over_under)
outcome_home
NUMERIC(6,3)
YES
-
主胜赔率
outcome_draw
NUMERIC(6,3)
YES
-
平局赔率
outcome_away
NUMERIC(6,3)
YES
-
客胜赔率
outcome_over
NUMERIC(6,3)
YES
-
大球赔率
outcome_under
NUMERIC(6,3)
YES
-
小球赔率
outcome_yes
NUMERIC(6,3)
YES
-
BTTS是
outcome_no
NUMERIC(6,3)
YES
-
BTTS否
snapshot_at
TIMESTAMPTZ
NO
-
采集时间
data_source
VARCHAR(30)
NO
-
odds_api/oddsportal
created_at
TIMESTAMPTZ
NO
NOW()

索引: idx_odds_match_market (match_id, market_type, snapshot_at DESC)；idx_odds_snapshot_time (snapshot_at DESC)
⚠ 赔率表是只追加表（append-only），不做 UPDATE。预估单场比赛会产生 50-100 行快照，整体数据量较大，后期可考虑按时间分区。

2.2.12 h2h_records — 历史交锋记录表
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
team_a_id
BIGINT FK
NO
-
球队 A（id 较小的一方）
team_b_id
BIGINT FK
NO
-
球队 B
total_matches
SMALLINT
NO
0
总交锋场次
team_a_wins
SMALLINT
NO
0
A 胜场次
team_b_wins
SMALLINT
NO
0
B 胜场次
draws
SMALLINT
NO
0
平局场次
team_a_goals
SMALLINT
NO
0
A 总进球
team_b_goals
SMALLINT
NO
0
B 总进球
last_match_date
DATE
YES
-
最近交锋日期
updated_at
TIMESTAMPTZ
NO
NOW()

索引: UNIQUE(team_a_id, team_b_id)，约定 team_a_id &lt; team_b_id

2.2.13 elo_ratings — Elo 评分历史表
记录每场比赛后球队的 Elo 评分变化，为 Phase 2 ML 特征工程提供基础。
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
team_id
BIGINT FK
NO
-
关联 teams.id
match_id
BIGINT FK
YES
-
触发评分变化的比赛
rating
NUMERIC(7,2)
NO
1500.00
当前 Elo 评分
rating_change
NUMERIC(6,2)
YES
-
本场变化量
rated_at
DATE
NO
-
评分日期
created_at
TIMESTAMPTZ
NO
NOW()

索引: idx_elo_team_date (team_id, rated_at DESC)；idx_elo_match

2.2.14 data_source_logs — 数据采集审计日志表
记录每次数据采集任务的执行情况，用于监控和排查。
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
source_name
VARCHAR(50)
NO
-
数据源名称
task_type
VARCHAR(50)
NO
-
fetch_matches/fetch_stats/fetch_odds 等
status
VARCHAR(20)
NO
-
started/success/failed/partial
records_fetched
INTEGER
YES
-
采集记录数
records_inserted
INTEGER
YES
-
新增入库数
records_updated
INTEGER
YES
-
更新记录数
error_message
TEXT
YES
-
错误信息
started_at
TIMESTAMPTZ
NO
-
开始时间
finished_at
TIMESTAMPTZ
YES
-
结束时间
meta
JSONB
YES
-
额外元数据（请求参数等）
created_at
TIMESTAMPTZ
NO
NOW()

索引: idx_logs_source_time (source_name, started_at DESC)；idx_logs_status
⚠ 建议对此表设置自动清理策略，保留最近 90 天的日志。

2.3 实体关系总览
以下是核心表之间的关系概览：
关系
主表
关联表
类型
1
competitions
seasons
1:N
2
seasons
matches
1:N
3
teams
matches (home)
1:N
4
teams
matches (away)
1:N
5
matches
match_stats
1:2 (主客)
6
matches
match_lineups
1:N
7
matches
odds_snapshots
1:N
8
players
match_lineups
1:N
9
players
player_stats
1:N
10
players
player_valuations
1:N
11
players
injuries
1:N
12
teams
elo_ratings
1:N
13
teams (pair)
h2h_records
N:N (team_a &lt; team_b)

2.4 数据库迁移策略
使用 Alembic（Python SQLAlchemy 生态）管理数据库迁移，原因：Phase 1 的主要代码是 Python 采集服务，与 Alembic 自然集成。每次 Schema 变更生成一个迁移文件，命名规范：{timestamp}_{description}.py。所有迁移必须包含 upgrade() 和 downgrade() 方法。

3. 数据采集模块详细设计 (M1)
3.1 模块架构总览
数据采集模块采用 Adapter Pattern + Strategy Pattern 设计，所有数据源通过统一的抽象接口接入，写入同一套数据模型。换源时只需替换 Adapter，不影响下游。
3.2 核心类设计
3.2.1 BaseDataSourceAdapter 抽象基类
所有数据源 Adapter 继承此基类，必须实现以下抽象方法：
抽象方法
返回类型
说明
fetch_matches(season_id)
List[MatchDTO]
获取指定赛季的比赛列表
fetch_match_detail(match_id)
MatchDetailDTO
获取单场比赛详细信息
fetch_team_stats(team_id, season_id)
TeamStatsDTO
获取球队赛季统计
fetch_player_stats(match_id)
List[PlayerStatDTO]
获取单场球员统计
get_rate_limit()
RateLimitConfig
返回该数据源的速率限制配置
health_check()
bool
检查数据源可用性
基类提供的通用能力（子类继承）：
方法
说明
_request_with_retry(url, params, max_retries=3)
带重试和指数退避的 HTTP 请求
_respect_rate_limit()
基于令牌桶算法的速率控制
_log_operation(task_type, status, ...)
自动写入 data_source_logs 表
_validate_response(data, schema)
响应数据的 Schema Validation

3.2.2 各 Adapter 实现说明
Adapter 类名
数据源
采集方式
提供的数据
ApiFootballAdapter
API-Football
REST API
赛程、比分、阵容、基础统计
FBrefAdapter
FBref
Scrapy 爬虫
xG、xA、高级统计数据
TransfermarktAdapter
Transfermarkt
Scrapy 爬虫
球员身价、伤病、转会
OddsApiAdapter
the-odds-api
REST API
实时赔率数据
OddsPortalAdapter
OddsPortal
Scrapy 爬虫
历史赔率数据
StaticDataAdapter
GitHub 数据集
静态导入
国家队历史交锋

3.2.3 核心 DTO 定义
所有 Adapter 返回统一的 DTO（Data Transfer Object），与数据库 Model 解耦。以下为核心 DTO 字段定义：
MatchDTO
字段
类型
说明
external_id
str
数据源原始 ID
home_team_name
str
主队名称（用于匹配）
away_team_name
str
客队名称
match_date
datetime
比赛时间 (UTC)
status
str
比赛状态
home_score
Optional[int]
主队进球数
away_score
Optional[int]
客队进球数
venue
Optional[str]
场馆
round
Optional[str]
轮次
competition_name
str
赛事名称
season_year
int
赛季年份

OddsDTO
字段
类型
说明
match_external_id
str
关联比赛的外部 ID
bookmaker
str
博彩公司名称
market_type
str
1x2/asian_handicap/over_under/btts
market_value
Optional[str]
盘口值
outcomes
Dict[str, float]
赔率字典，如 {&apos;home&apos;: 2.1, &apos;draw&apos;: 3.2, &apos;away&apos;: 3.5}
snapshot_at
datetime
采集时间

PlayerStatDTO / InjuryDTO / ValuationDTO 等类似结构，字段与对应数据库表字段对齐，略去内部 id 和时间戳。

3.3 数据采集调度设计
3.3.1 Celery Beat 定时任务配置
任务名称
调度频率
对应 Adapter
说明
sync_matches_daily
每日 06:00 UTC
ApiFootballAdapter
同步赛程和比分
sync_matches_live
比赛日每 5 分钟
ApiFootballAdapter
实时比分更新
sync_stats_post_match
比赛结束后 2h
ApiFootball + FBref
采集比赛统计
sync_fbref_xg
比赛结束后 6-12h
FBrefAdapter
xG 等高级数据
sync_injuries
每周二、周五 08:00
TransfermarktAdapter
伤病数据更新
sync_valuations
每周一 08:00
TransfermarktAdapter
身价数据更新
sync_odds_hourly
赛前 24h 每小时
OddsApiAdapter
赔率快照采集
sync_odds_frequent
赛前 2h 每 10 分钟
OddsApiAdapter
高频赔率采集
cleanup_old_logs
每周日 03:00
-
清理 90 天前日志

3.3.2 Kafka 事件流设计
事件驱动架构用于解耦数据采集与下游消费。Phase 1 定义以下 Topic：
Topic 名称
产生方
消费方（当前/未来）
match.created
数据采集服务
赔率采集触发器
match.finished
数据采集服务
Phase 2: 战绩更新 / 统计采集触发
match.updated
数据采集服务
Phase 2: 实时数据推送
odds.updated
赔率采集服务
Phase 2: EV 重新计算
data.quality.alert
数据质量检查
监控告警服务

3.3.3 事件消息格式
所有 Kafka 消息使用统一的 JSON Envelope 格式：
字段
类型
说明
event_type
string
事件类型，如 &apos;match.finished&apos;
event_id
string (UUID)
事件唯一标识，用于幂等去重
timestamp
string (ISO8601)
事件发生时间
source
string
产生方服务名称
payload
object
事件详细数据，包含相关实体 ID

3.4 数据清洗 Pipeline 设计
3.4.1 清洗流程
数据从采集到入库经过以下标准流程：
步骤
名称
详细说明
1
原始数据获取
Adapter 从外部数据源拉取原始数据
2
Schema Validation
使用 Pydantic Model 校验字段类型、范围、必填项
3
实体匹配
通过外部 ID 或名称模糊匹配，关联到内部实体（球队、球员）
4
数据标准化
统一日期格式 (UTC)、球队名称映射、货币单位等
5
去重判断
基于 UNIQUE 约束，使用 ON CONFLICT DO UPDATE
6
写入数据库
批量写入，单次最多 500 条
7
发布事件
写入成功后发布 Kafka 事件
8
记录日志
写入 data_source_logs 表

3.4.2 球队名称映射表
不同数据源对同一球队的命名可能不同（如 &apos;Man United&apos; vs &apos;Manchester United&apos; vs &apos;Manchester Utd&apos;）。系统维护一张内部映射表 team_name_aliases：
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
team_id
BIGINT FK
NO
-
关联 teams.id
alias
VARCHAR(200)
NO
-
别名
source
VARCHAR(30)
NO
-
来源数据源
索引: UNIQUE(alias, source)

3.5 反爬策略与容错设计
3.5.1 爬虫反封策略
策略
实现方式
请求速率控制
每个 Adapter 配置独立的 RateLimitConfig (requests_per_second, burst_size)，使用令牌桶算法
User-Agent 轮换
维护 10+ 个真实浏览器 UA，每次请求随机选择
IP 代理池
通过环境变量配置代理池，爬虫请求自动轮换
请求间隔随机化
在基础间隔上加入 0.5-2s 随机报动
Cookie / Session 管理
爬虫模拟真实浏览器 Session，Scrapy 自动管理 Cookie
Headless 浏览器备用
对于 JS 渲染页面，使用 Playwright 作为 fallback

3.5.2 容错与重试机制
场景
策略
详细
HTTP 429 (Rate Limit)
指数退避重试
初始 5s，最多重试 3 次，重试间隔 5s/15s/45s
HTTP 5xx
自动重试
最多 3 次，间隔 10s
HTTP 403 (Blocked)
切换代理 + 告警
记录日志，发送告警通知
网络超时
重试 + 备用数据源
切换到备用 Adapter（如有）
数据格式变更
告警 + 降级
记录解析失败的字段，保存已解析的部分
部分数据缺失
标记 + 继续
更新 data_completeness 字段，不阻塞整体流程

4. 项目结构与配置
4.1 目录结构
以下为 Phase 1 Python 采集服务的推荐目录结构：
worldcup-predictor/
├── src/
│   ├── adapters/                  # 数据源适配器
│   │   ├── base.py               # BaseDataSourceAdapter
│   │   ├── api_football.py       # ApiFootballAdapter
│   │   ├── fbref.py              # FBrefAdapter
│   │   ├── transfermarkt.py      # TransfermarktAdapter
│   │   ├── odds_api.py           # OddsApiAdapter
│   │   ├── odds_portal.py        # OddsPortalAdapter
│   │   └── static_data.py        # StaticDataAdapter
│   ├── models/                    # SQLAlchemy ORM 模型
│   │   ├── base.py               # Base, 通用 Mixin
│   │   ├── competition.py
│   │   ├── team.py
│   │   ├── player.py
│   │   ├── match.py
│   │   ├── stats.py
│   │   ├── odds.py
│   │   └── logs.py
│   ├── dto/                       # Data Transfer Objects
│   │   ├── match.py
│   │   ├── odds.py
│   │   ├── player.py
│   │   └── stats.py
│   ├── pipelines/                 # 数据清洗 Pipeline
│   │   ├── base.py
│   │   ├── match_pipeline.py
│   │   ├── stats_pipeline.py
│   │   ├── odds_pipeline.py
│   │   └── player_pipeline.py
│   ├── scrapers/                  # Scrapy 爬虫
│   │   ├── spiders/
│   │   ├── middlewares.py
│   │   └── settings.py
│   ├── tasks/                     # Celery 任务定义
│   │   ├── match_tasks.py
│   │   ├── stats_tasks.py
│   │   ├── odds_tasks.py
│   │   └── maintenance_tasks.py
│   ├── events/                    # Kafka 事件
│   │   ├── producer.py
│   │   └── schemas.py
│   ├── utils/                     # 工具类
│   │   ├── name_mapping.py       # 球队名称映射
│   │   ├── rate_limiter.py
│   │   └── validators.py
│   └── config/                    # 配置
│       ├── settings.py
│       ├── celery_config.py
│       └── kafka_config.py
├── migrations/                    # Alembic 迁移
├── tests/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md

4.2 环境变量配置
环境变量
示例值
说明
DATABASE_URL
postgresql://user:pass@db:5432/wcp
PostgreSQL 连接串
REDIS_URL
redis://redis:6379/0
Redis 连接串
KAFKA_BROKERS
kafka:9092
Kafka broker 地址
API_FOOTBALL_KEY
xxx-xxx-xxx
API-Football 密钥
ODDS_API_KEY
xxx-xxx-xxx
the-odds-api 密钥
PROXY_POOL_URL
http://proxy:5555/random
代理池地址
LOG_LEVEL
INFO
日志级别
SCRAPER_CONCURRENT
2
爬虫并发数

5. Phase 1 部署架构
5.1 Docker Compose 服务编排
Phase 1 使用 Docker Compose 进行本地开发和初期部署，Phase 5 再迁移到 K8s。
服务名
镜像
端口
说明
postgres
postgres:15-alpine
5432
主数据库
redis
redis:7-alpine
6379
缓存 + Celery Broker
kafka
confluentinc/cp-kafka
9092
消息队列
zookeeper
confluentinc/cp-zookeeper
2181
Kafka 依赖
ingestion-worker
自建
-
Celery Worker
ingestion-beat
自建
-
Celery Beat 调度器
scrapy-worker
自建
-
爬虫服务
flower
mher/flower
5555
Celery 监控 UI

5.2 初始化流程
项目首次启动时的执行顺序：
序
操作
命令/说明
1
启动基础设施
docker-compose up -d postgres redis kafka zookeeper
2
执行数据库迁移
alembic upgrade head
3
导入静态数据
python scripts/import_static_data.py (国家队历史、球队映射)
4
启动采集服务
docker-compose up -d ingestion-worker ingestion-beat
5
执行历史数据回填
python scripts/backfill_historical.py --from 2022-11
6
验证数据完整性
python scripts/validate_data.py

6. 历史数据回填计划
根据 PRD 要求，需要采集 2022 世界杯至今的所有相关比赛数据，作为 ML 模型的训练基础。
6.1 回填范围
赛事
时间范围
预估场次
优先级
数据源
FIFA World Cup 2022
2022.11-12
~64
P0
API-Football
英超 (EPL)
2022/23 - 2025/26
~1520
P0
API-Football + FBref
西甲 (La Liga)
2022/23 - 2025/26
~1520
P0
API-Football + FBref
德甲 (Bundesliga)
2022/23 - 2025/26
~1224
P0
API-Football + FBref
意甲 (Serie A)
2022/23 - 2025/26
~1520
P0
API-Football + FBref
法甲 (Ligue 1)
2022/23 - 2025/26
~1520
P0
API-Football + FBref
国家队友谊赛
2023-2026
~300
P1
API-Football
欧洲杯 / 美洲杯
2024
~100
P1
API-Football
WC 预选赛
2023-2026
~400
P0
API-Football

6.2 回填执行顺序
步骤
操作
依赖
预估耗时
1
导入球队基础数据
无
1-2 小时
2
导入球员基础数据
球队数据就绪
2-3 小时
3
回填比赛数据 (赛程 + 比分)
球队数据就绪
4-6 小时（受限于 API 速率限制）
4
回填比赛统计数据
比赛数据就绪
6-8 小时
5
回填 FBref xG 数据
比赛数据就绪
4-6 小时（爬虫降速）
6
回填球员身价 + 伤病
球员数据就绪
3-4 小时
7
回填历史赔率数据
比赛数据就绪
6-10 小时
8
计算历史 Elo 评分
全部比赛数据就绪
1 小时
9
数据完整性检查
全部数据就绪
30 分钟
⚠ 总计预估回填时间：2-3 天（受限于 API 速率限制和爬虫降速要求）。建议在 Phase 1 第 1 周末开始回填，与代码开发并行。

7. 数据质量保障
7.1 校验规则
实体
校验规则
处理方式
Match
match_date 不能在未来 &gt; 1 年
拒绝入库 + 告警
Match
home_score / away_score 范围 0-30
拒绝异常值
Odds
赔率值范围 1.01 - 100.0
过滤异常赔率
Odds
同一 bookmaker 同一 market 1 小时内不重复采集
去重
Player
身价 &gt; 0 且 &lt; 3亿欧元
拒绝异常值
Stats
xG 范围 0.0 - 10.0
过滤异常值
Stats
控球率双方加和应接近 100%
警告日志（允许 ±5% 误差）

7.2 数据完整性监控
每日运行数据完整性检查脚本，检查以下指标：
检查项
期望
异常处理
已结束比赛缺少统计数据
结束 &gt; 24h 的比赛应有统计
触发补采任务
赔率数据覆盖率
未来 7 天比赛应有赔率
触发赔率采集
球员伤病更新时效
最新更新 &lt; 7 天
告警 + 触发采集
FBref xG 数据覆盖率
已结束比赛 &gt; 80% 应有 xG
触发补采
数据源日志失败率
&lt; 5%
告警通知

8. Phase 1 验收标准
Phase 1 完成时，必须满足以下验收标准才能进入 Phase 2：
#
验收条件
度量指标
优先级
1
数据库全部表已创建并通过迁移脚本验证
14 张表全部就绪
必须
2
历史比赛数据入库数 &gt;= 4000 场
通过计数查询验证
必须
3
五大联赛历史数据完整性 &gt; 95%
比赛数/统计数覆盖率
必须
4
赔率历史数据至少覆盖 2 家博彩公司
bookmaker 去重计数 &gt;= 2
必须
5
自动化采集流水线正常运行 48h 无失败
data_source_logs 连续成功
必须
6
Kafka 事件正常发布和消费
手动触发并验证事件流
必须
7
数据清洗规则全部生效（异常值被过滤）
注入异常数据验证过滤
必须
8
采集审计日志可查询
data_source_logs 有记录
必须
9
单元测试覆盖 Adapter + Pipeline 核心逻辑
测试覆盖率 &gt; 80%
建议
10
数据完整性监控脚本可运行
手动运行产出报告
建议

9. 与 Phase 2 的交接点
Phase 1 的输出直接作为 Phase 2（ML Baseline）的输入。以下是关键交接点：
交接项
Phase 2 如何使用
matches + match_stats 表
ML 特征工程的主要数据源，计算近 N 场战绩、xG 趋势等特征
elo_ratings 表
直接作为 Elo 特征输入，无需重新计算
odds_snapshots 表
赔率分析器的数据源，计算隐含概率并与模型对比
injuries + player_valuations
伤病影响和身价特征的数据源
h2h_records 表
历史交锋特征的数据源
Kafka match.finished 事件
触发 Phase 2 的战绩自动更新和模型重新推理
Kafka odds.updated 事件
触发 Phase 2 的 EV 重新计算


— Phase 1 详细设计文档结束 —

