
# WorldCup 2026 Predictor — M9 对冲建议模块

**版本**: v1.0  |  **日期**: 2026年5月12日  |  **详细设计阶段**

> Source: M9 Hedging Advisory Module design v1.0, 2026-05-12.
> Imported into the repo as the canonical reference for the M9 implementation.

---

# 1. 文档说明

## 1.1 文档定位

本文档是 World Cup 2026 Predictor 项目的 M9 对冲建议模块（Hedging Advisory Module）详细设计文档。该模块是在现有 M2 ML 引擎的赔率分析器（Odds Analyzer）基础上的增量模块,专门为用户提供智能对冲策略建议,包括完全对冲、部分对冲（冒险对冲）和多场串关对冲等场景。

本模块定位为"数据分析参考工具",不提供任何下注功能或链接到博彩平台,严格遵守 PRD 中的合规要求。

## 1.2 模块定位与价值

对冲建议是本产品的高级功能之一,目标用户是已有一定足彩经验的付费用户。对冲功能的核心价值在于:帮助用户在已有持仓的基础上,通过数学计算给出最优对冲方案,降低风险或锁定利润。特别是"冒险对冲"模式,允许用户保留部分风险敲口以追求更高回报。

## 1.3 与现有模块的关系

| 上游模块 | 依赖内容 | 说明 |
| --- | --- | --- |
| M2 ML 引擎 | 模型概率 + 赔率分析 | 对冲计算的核心数据源 |
| M2 赔率分析器 | EV、edge、多家赔率对比 | 对冲时机判断的依据 |
| M3 业务服务 | 用户订阅层级 | 对冲功能仅对高阶订阅开放 |
| M1 数据采集 | 实时赔率数据 | 赛中对冲需要实时赔率更新 |

| 下游模块 | 输出内容 | 说明 |
| --- | --- | --- |
| M7 前端 | 对冲计算器 UI | 用户交互界面 |
| M4 内容生成 | 对冲方案分享卡片 | 营销素材 |
| M6 推送服务 | 对冲窗口提醒 | 赛中赔率变动时推送 |
| M5 战绩追踪 | 对冲策略效果追踪 | 对冲 ROI 统计 |

---

# 2. 对冲概念与场景定义

## 2.1 什么是足彩对冲

对冲（Hedging）是指在已有持仓的基础上,通过下反向注来降低或转移风险的操作。在足球博彩/竞彩中,对冲通常发生在以下场景:赛前下注后赔率发生显著变化,串关前 N 场已赢而最后一场尚未开赛,以及比赛进行中场上形势发生变化等。

## 2.2 三种对冲模式

| 对冲模式 | 定义 | 风险特征 | 适用场景 |
| --- | --- | --- | --- |
| 完全对冲 (Full Hedge) | 下反向注完全覆盖原始持仓,无论结果如何都保证固定利润或将亏损降到最低 | 零风险,锁定利润 | 串关最后一场、已有较大浮盈 |
| 部分对冲 (Partial Hedge) | 只对冲部分金额,保留一定风险敲口以追求更高回报 | 中等风险,潜在回报更高 | 有信心但想缩小风险敲口 |
| 冒险对冲 (Risk Hedge) | 只对冲少量金额,保留大部分风险敲口,但确保最坏情况不至于全亏 | 较高风险,最大回报潜力 | 对原始判断非常自信,只想"保底" |

## 2.3 对冲数学原理

对冲的核心计算基于以下公式:

**单场对冲公式:**

```
hedge_stake = original_stake × original_odds / hedge_odds
保证利润 = original_stake × original_odds - original_stake - hedge_stake
```

**部分对冲公式:**

```
hedge_stake = hedge_ratio × (original_stake × original_odds / hedge_odds)
```

其中 hedge_ratio ∈ (0, 1],代表对冲比例。ratio = 1.0 为完全对冲,ratio = 0.3 为冒险对冲。

**串关对冲公式（Parlay Hedge）:**

```
parlay_potential   = original_stake × ∏(leg_odds)            # 串关潜在总回报
hedge_stake        = parlay_potential / hedge_odds           # 对冲最后一场的反向注
guaranteed_profit  = parlay_potential - original_stake - hedge_stake
```

---

# 3. 数据库 Schema 设计

## 3.1 新增表清单

| # | 表名 | 说明 | 预估行数 | 所属模块 |
| --- | --- | --- | --- | --- |
| 1 | hedge_scenarios | 用户对冲场景配置 | ~50000 | M9 |
| 2 | hedge_calculations | 对冲计算结果快照 | ~200000 | M9 |
| 3 | hedge_results | 对冲策略实际结果追踪 | ~50000 | M9 |
| 4 | parlay_legs | 串关各场次详情 | ~150000 | M9 |

## 3.2 hedge_scenarios 表

| 字段 | 类型 | NULL | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| id | BIGSERIAL PK | NO | auto | 主键 |
| user_id | BIGINT FK | NO | - | 关联 users.id |
| scenario_type | VARCHAR(20) | NO | - | single / parlay / live |
| match_id | BIGINT FK | YES | - | 单场对冲关联的比赛 |
| original_stake | NUMERIC(12,2) | NO | - | 原始下注金额 |
| original_odds | NUMERIC(8,3) | NO | - | 原始赔率（欧洲小数） |
| original_outcome | VARCHAR(30) | NO | - | 原始下注结果: home/draw/away/over/under |
| original_market | VARCHAR(30) | NO | - | 1x2/over_under/asian_handicap/btts |
| hedge_mode | VARCHAR(20) | NO | - | full / partial / risk |
| hedge_ratio | NUMERIC(4,3) | NO | 1.000 | 对冲比例 0.0-1.0 |
| status | VARCHAR(20) | NO | active | active/settled/cancelled |
| created_at | TIMESTAMPTZ | NO | NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NO | NOW() | 更新时间 |

*索引: idx_hedge_scenarios_user (user_id, status); idx_hedge_scenarios_match (match_id)*

## 3.3 hedge_calculations 表

| 字段 | 类型 | NULL | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| id | BIGSERIAL PK | NO | auto | 主键 |
| scenario_id | BIGINT FK | NO | - | 关联 hedge_scenarios.id |
| hedge_outcome | VARCHAR(30) | NO | - | 对冲方向: home/draw/away/over/under |
| hedge_odds | NUMERIC(8,3) | NO | - | 对冲时的赔率 |
| hedge_bookmaker | VARCHAR(50) | NO | - | 提供最佳对冲赔率的博彩公司 |
| hedge_stake | NUMERIC(12,2) | NO | - | 建议对冲金额 |
| profit_if_original_wins | NUMERIC(12,2) | NO | - | 原始注赢时的净利润 |
| profit_if_hedge_wins | NUMERIC(12,2) | NO | - | 对冲注赢时的净利润 |
| max_loss | NUMERIC(12,2) | NO | - | 最坏情况亏损 |
| guaranteed_profit | NUMERIC(12,2) | YES | - | 仅完全对冲时有值 |
| ev_of_hedge | NUMERIC(8,4) | YES | - | 对冲操作本身的 EV |
| model_prob_hedge | NUMERIC(5,4) | YES | - | 模型对对冲方向的概率估计 |
| model_assessment | VARCHAR(50) | YES | - | **GAP 1**: 持久化 advisor 评估字符串 |
| calculated_at | TIMESTAMPTZ | NO | NOW() | 计算时间 |

*索引: UNIQUE(scenario_id, hedge_outcome); idx_hedge_calc_ev (ev_of_hedge DESC NULLS LAST)*

## 3.4 hedge_results 表

| 字段 | 类型 | NULL | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| id | BIGSERIAL PK | NO | auto | 主键 |
| scenario_id | BIGINT FK | NO | - | 关联 hedge_scenarios.id, UNIQUE |
| actual_outcome | VARCHAR(30) | NO | - | 比赛实际结果 |
| original_pnl | NUMERIC(12,2) | NO | - | 原始注盈亏 |
| hedge_pnl | NUMERIC(12,2) | NO | - | 对冲注盈亏 |
| total_pnl | NUMERIC(12,2) | NO | - | 总盈亏 = original_pnl + hedge_pnl |
| would_have_pnl | NUMERIC(12,2) | NO | - | 如果不对冲的盈亏（用于对比分析） |
| hedge_value_added | NUMERIC(12,2) | NO | - | total_pnl - would_have_pnl |
| settled_at | TIMESTAMPTZ | NO | NOW() | 结算时间 |

## 3.5 parlay_legs 表

| 字段 | 类型 | NULL | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| id | BIGSERIAL PK | NO | auto | 主键 |
| scenario_id | BIGINT FK | NO | - | 关联 hedge_scenarios.id |
| leg_order | SMALLINT | NO | - | 串关场次序号 (1, 2, 3...) |
| match_id | BIGINT FK | NO | - | 关联 matches.id |
| outcome | VARCHAR(30) | NO | - | 该场下注结果 |
| odds | NUMERIC(8,3) | NO | - | 该场赔率 |
| is_settled | BOOLEAN | NO | false | 是否已结算 |
| is_won | BOOLEAN | YES | - | 是否命中 |

*索引: idx_parlay_legs_scenario (scenario_id, leg_order); idx_parlay_legs_match (match_id); UNIQUE(scenario_id, leg_order)*

---

# 4. API 接口设计

## 4.1 对冲计算 API (FastAPI — ML 服务侧)

### POST /api/v1/hedge/calculate

核心对冲计算接口,接收用户的持仓信息和对冲偏好,返回对冲方案。

**Request Body:**

```json
{
  "match_id": 12345,
  "original_stake": 100,
  "original_odds": 2.10,
  "original_outcome": "home",
  "original_market": "1x2",
  "hedge_mode": "partial",
  "hedge_ratio": 0.6
}
```

**Response:**

```json
{
  "code": 0,
  "data": {
    "scenario_id": 678,
    "recommendations": [
      {
        "hedge_outcome": "draw",
        "hedge_odds": 3.40,
        "hedge_bookmaker": "Bet365",
        "hedge_stake": 37.06,
        "profit_if_original_wins": 72.94,
        "profit_if_hedge_wins": 25.94,
        "max_loss": -37.06,
        "ev_of_hedge": 0.034,
        "model_assessment": "对冲有价值"
      },
      {
        "hedge_outcome": "away",
        "hedge_odds": 4.20,
        "hedge_bookmaker": "Pinnacle",
        "hedge_stake": 30.00,
        "profit_if_original_wins": 80.00,
        "profit_if_hedge_wins": 26.00,
        "max_loss": -30.00,
        "ev_of_hedge": -0.021,
        "model_assessment": "谨慎对冲"
      }
    ],
    "disclaimer": "本平台仅提供数据分析参考,不构成任何投注建议。对冲计算器为数学工具,计算结果仅供参考,请用户自行判断。"
  }
}
```

### POST /api/v1/hedge/parlay

串关对冲计算接口。

**Request Body:**

```json
{
  "original_stake": 50,
  "legs": [
    { "match_id": 101, "outcome": "home",     "odds": 1.85, "is_settled": true,  "is_won": true },
    { "match_id": 102, "outcome": "over_2.5", "odds": 1.90, "is_settled": true,  "is_won": true },
    { "match_id": 103, "outcome": "away",     "odds": 2.20, "is_settled": false }
  ],
  "hedge_mode": "risk",
  "hedge_ratio": 0.3
}
```

Response 结构同 `calculate`, scenario_type='parlay'。

### GET /api/v1/hedge/live-odds/{match_id}

获取指定比赛的实时对冲赔率,返回多家博彩公司的实时赔率对比,用于赛中对冲场景。

**行为约定**:
- 查 `odds_snapshots`, 限制最近 10 分钟内
- 按 market 分组返回 (1x2 / over_under / btts)
- 每个 outcome 标出最佳赔率 bookmaker
- 12 小时内无任何快照 → 404
- 公开端点, 走 `APIKeyMiddleware`

## 4.2 业务服务 API (Spring Boot)

| 接口 | 方法 | 说明 | 权限 |
| --- | --- | --- | --- |
| /api/v1/hedge/scenarios | POST | 创建对冲场景 | premium |
| /api/v1/hedge/scenarios | GET | 获取用户的对冲场景列表 | premium |
| /api/v1/hedge/scenarios/{id} | GET | 获取单个场景详情（含计算结果） | premium |
| /api/v1/hedge/scenarios/{id}/recalc | POST | 重新计算（赔率变动后） | premium |
| /api/v1/hedge/results | GET | 获取对冲策略历史结果 | premium |
| /api/v1/hedge/stats | GET | 对冲策略综合统计（ROI、成功率） | basic+ |

---

# 5. 核心算法设计

## 5.1 HedgeCalculator 类设计

对冲计算器是 M9 的核心类,位于 `src/ml/hedge/` 目录下。

**核心方法:**

| 方法 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `calculate_single()` | original_stake, original_odds, hedge_odds, hedge_ratio | HedgeResult | 单场对冲计算 |
| `calculate_parlay()` | original_stake, legs[], hedge_odds, hedge_ratio | ParlayHedgeResult | 串关对冲计算 |
| `find_optimal_ratio()` | original_stake, original_odds, hedge_odds, risk_tolerance | float | 根据风险偏好计算最优对冲比例 |
| `evaluate_hedge_ev()` | model_prob, hedge_odds | float | 评估对冲操作本身的 EV |
| `compare_scenarios()` | original, full_hedge, partial_hedge, risk_hedge | ComparisonTable | 三种模式对比表 |

## 5.2 完整计算示例

### 场景 1: 单场对冲

用户以 ¥100 下注主胜,赔率 2.10。比赛进行中主队 1:0 领先,客胜实时赔率变为 6.50。

| 对冲模式 | 对冲金额 | 主队赢利润 | 客队赢/平利润 | 最坏亏损 |
| --- | --- | --- | --- | --- |
| 不对冲 | ¥0 | +¥110 | -¥100 | -¥100 |
| 完全对冲 (ratio=1.0) | ¥32.31 | +¥77.69 | +¥77.69 | ¥0 (无风险) |
| 部分对冲 (ratio=0.6) | ¥19.38 | +¥90.62 | +¥25.97 | -¥19.38 |
| 冒险对冲 (ratio=0.3) | ¥9.69 | +¥100.31 | -¥36.96 | -¥9.69 |

### 场景 2: 串关对冲

用户以 ¥50 下了 3 场串关（赔率 1.85 × 1.90 × 2.20 = 7.733）,前 2 场已赢,第 3 场尚未开赛。

```
串关潜在总回报: ¥50 × 7.733 = ¥386.65
第 3 场反向赔率（非客胜）: 1.65
```

| 对冲模式 | 对冲金额 | 全串赢利润 | 最后一场输利润 | 保底利润 |
| --- | --- | --- | --- | --- |
| 不对冲 | ¥0 | +¥336.65 | -¥50 | N/A |
| 完全对冲 | ¥234.33 | +¥102.32 | +¥302.82 | +¥102.32 |
| 冒险对冲 (ratio=0.3) | ¥70.30 | +¥266.35 | +¥65.69 | +¥65.69 |

## 5.3 智能对冲建议算法

系统不仅提供纯数学对冲计算,还结合 M2 ML 引擎的模型概率给出智能建议:

| 建议类型 | 触发条件 | 建议内容 |
| --- | --- | --- |
| "建议对冲" | 模型概率显示原始下注方向 EV 已转负 | 建议对冲锁定利润,原始判断的价值已被市场消化 |
| "对冲有价值" | 对冲方向本身是 +EV（模型认为反向赔率也有价值） | 对冲操作本身也是一笔有价值的交易,双重正期望 |
| "谨慎对冲" | 对冲方向 EV 为负,但原始方向仍为 +EV | 对冲会牺牲正期望,仅在风险控制需要时才建议 |
| "不建议对冲" | 原始方向仍为强 +EV,对冲方向 EV 显著为负 | 保持原始持仓是最优策略 |

---

# 6. 前端组件设计

(本 PR 不实现, 仅作为后续 PR 的设计参考)

## 6.1 对冲计算器页面

新增页面: `/hedge`,作为独立工具页,仅对 premium 订阅用户开放。

| 组件名 | 职责 | 所在位置 |
| --- | --- | --- |
| HedgeCalculator | 对冲计算器主容器,管理输入表单和结果展示 | `/hedge` |
| SingleHedgeForm | 单场对冲输入表单 | `/hedge?type=single` |
| ParlayHedgeForm | 串关对冲输入表单（动态添加场次） | `/hedge?type=parlay` |
| HedgeResultPanel | 对冲结果展示面板,包含三种模式对比 | 子组件 |
| HedgeModeSlider | 对冲比例滑块（保守 ↔ 激进） | 子组件 |
| ProfitLossChart | 不同结果下的盈亏柱状图（Recharts） | 子组件 |
| ModelInsightBadge | ML 模型对对冲操作的评估标签 | 子组件 |
| HedgeHistoryList | 历史对冲记录列表 | `/hedge/history` |

## 6.2 对冲比例滑块 (HedgeModeSlider)

这是本模块最核心的交互组件。用户通过滑块选择对冲比例（0% - 100%）,界面实时更新各种结果下的盈亏显示。滑块分三个区间色块:绿色区 (0-30%) "冒险对冲",蓝色区 (30-70%) "部分对冲",灰色区 (70-100%) "完全对冲"。随着滑块移动,下方的 ProfitLossChart 实时重绘。

## 6.3 比赛详情页集成

在现有比赛详情页（`/matches/{id}`）中新增"对冲计算器"快捷入口。当赔率发生显著变动时（与用户持仓时相比变动 > 15%）,显示"对冲窗口"提示标签。这个提示也会通过 M6 推送服务发送给用户。

## 6.4 访问权限

| 功能 | 免费用户 | 基础订阅 | 高阶订阅 |
| --- | --- | --- | --- |
| 查看对冲概念说明 | ✓ | ✓ | ✓ |
| 对冲计算器（单场） | ✗ | ✗ | ✓ |
| 对冲计算器（串关） | ✗ | ✗ | ✓ |
| ML 模型对冲建议 | ✗ | ✗ | ✓ |
| 对冲窗口推送提醒 | ✗ | ✗ | ✓ |
| 对冲历史记录 & ROI | ✗ | ✓ (只看) | ✓ |

---

# 7. 项目结构增量

在现有项目结构基础上新增以下目录:

```
src/ml/hedge/                    # M9 对冲核心算法
    calculator.py                # HedgeCalculator 类
    parlay.py                    # ParlayHedgeCalculator
    advisor.py                   # HedgeAdvisor — 结合 ML 模型给建议
    optimizer.py                 # 最优对冲比例计算
    schemas.py                   # Pydantic 数据模型

src/api/routes/hedge.py          # FastAPI 对冲接口
src/models/hedge_scenario.py     # SQLAlchemy ORM 模型

frontend/src/pages/HedgePage.tsx         # 对冲工具页（本 PR 不实现）
frontend/src/components/hedge/           # 对冲相关组件目录（本 PR 不实现）

tests/test_hedge_calculator.py   # 对冲计算单元测试
tests/test_hedge_api.py          # API 集成测试
```

---

# 8. 测试策略

| 测试类型 | 测试内容 | 覆盖率要求 |
| --- | --- | --- |
| 单元测试 | HedgeCalculator 各方法的数学正确性:对冲金额计算、盈亏计算、边界值（赔率=1.0、ratio=0/1） | > 95% |
| API 测试 | 各接口的请求/响应、参数校验、权限控制 | > 90% |
| 回测测试 | 用历史赔率数据模拟对冲场景,验证对冲建议的准确性 | 含在回测报告中 |
| 前端测试 | HedgeModeSlider 交互、实时更新、响应式布局 | E2E 覆盖 |

---

# 9. 合规与免责声明

本模块严格遵守 PRD 中的合规要求,必须在所有对冲相关页面和功能中显著展示以下免责声明:

> *"本平台仅提供数据分析参考,不构成任何投注建议。对冲计算器为数学工具,计算结果仅供参考,请用户自行判断。"*

具体合规措施:
- 不提供任何下注链接或博彩平台跳转
- 不使用"稳赚""必赢""保证盈利"等诱导性用语
- 对冲计算结果始终标注"仅供参考"
- 产品定位为"数据分析参考工具"而非"博彩辅助工具"

---

# 10. 实施计划与排期

对冲模块建议在 Phase 4（模型进化 + 内容生成）期间开发,因为它依赖 M2 ML 引擎的成熟模型概率和多家赔率对比数据。

| 周次 | 任务 | 交付物 |
| --- | --- | --- |
| Week 1 | 数据库 Schema + HedgeCalculator 核心算法 + 单元测试 | 对冲计算引擎 + 数据库迁移 |
| Week 2 | FastAPI 接口 + HedgeAdvisor (ML集成) + 串关对冲 | API 服务 + 智能建议 |
| Week 3 | 前端对冲计算器页面 + 滑块交互 + 图表 | 前端功能完成 |
| Week 4 | Spring Boot 业务 API + 权限控制 + 推送集成 + 测试 | 全模块交付 |

---

# 11. 验收标准

| # | 验收条件 | 度量指标 | 优先级 |
| --- | --- | --- | --- |
| 1 | 单场对冲计算数学正确 | 对冲金额 + 原始回报 = 总资金 × 反向赔率覆盖 | 必须 |
| 2 | 串关对冲计算正确 | 完全对冲时两个结果的利润相等 | 必须 |
| 3 | API 响应时间 < 200ms | 压测确认 | 必须 |
| 4 | 前端滑块实时更新 < 50ms | 无感知延迟 | 必须 |
| 5 | ML 智能建议与模型概率一致 | 建议方向与 EV 计算结果匹配 | 必须 |
| 6 | 合规免责声明全覆盖 | 所有对冲页面均显示免责文案 | 必须 |
| 7 | 对冲历史记录完整 | 所有场景赛后自动结算并归档 | 必须 |
| 8 | 对冲 ROI 统计正确 | 统计数据与历史记录一致 | 建议 |

---

# 12. 与其他 Phase 的交接点

| 交接项 | 下游如何使用 |
| --- | --- |
| hedge_calculations 表 | M5 战绩追踪系统统计对冲策略的历史 ROI |
| FastAPI /hedge/calculate 接口 | 前端对冲计算器的数据源 |
| 对冲窗口事件 | M6 推送服务监听赔率变动事件,触发对冲提醒推送 |
| 对冲方案分享卡片 | M4 内容生成模块自动生成对冲方案的可分享图片 |
| 对冲 ROI 数据 | Phase 5 运营后台的对冲功能使用数据看板 |

*— M9 对冲建议模块详细设计文档结束 —*

