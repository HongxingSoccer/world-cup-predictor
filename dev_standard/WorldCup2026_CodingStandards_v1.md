# ⚽ World Cup 2026 Predictor — 代码规范文档

**版本:** v1.0 | **日期:** 2026年5月1日 | **适用范围:** Phase 1 - Phase 5 全阶段

---

## 目录

1. [总则](#1-总则)
2. [项目结构规范](#2-项目结构规范)
3. [Python 代码规范 (数据采集 + ML + FastAPI)](#3-python-代码规范)
4. [Java 代码规范 (Spring Boot 业务服务)](#4-java-代码规范)
5. [TypeScript/React 代码规范 (Next.js 前端)](#5-typescriptreact-代码规范)
6. [数据库规范 (PostgreSQL)](#6-数据库规范)
7. [API 设计规范](#7-api-设计规范)
8. [注释与文档规范](#8-注释与文档规范)
9. [Git 工作流与提交规范](#9-git-工作流与提交规范)
10. [测试规范](#10-测试规范)
11. [日志与错误处理规范](#11-日志与错误处理规范)
12. [安全规范](#12-安全规范)
13. [配置与环境管理](#13-配置与环境管理)
14. [代码审查检查清单](#14-代码审查检查清单)

---

## 1. 总则

### 1.1 规范目的

本规范为 World Cup 2026 Predictor 项目的编码依据。项目涉及 Python、Java、TypeScript 三种语言，本规范确保跨语言风格统一、代码可维护、交接无障碍。

### 1.2 核心原则

| 原则 | 说明 |
|------|------|
| **可读性优先** | 代码是写给人看的，其次才是给机器执行的 |
| **显式优于隐式** | 命名、类型、意图都要明确，不靠猜 |
| **单一职责** | 每个函数/类/模块只做一件事 |
| **不要重复自己 (DRY)** | 公共逻辑提取到工具类/基类 |
| **尽早失败 (Fail Fast)** | 参数校验、数据验证在入口处完成 |
| **约定大于配置** | 遵循框架惯例，不造轮子 |

### 1.3 语言版本锁定

| 技术 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 使用 type hints、match-case |
| Java | 17 LTS | Spring Boot 3.x 最低要求 |
| TypeScript | 5.x | 严格模式 (`strict: true`) |
| Node.js | 20 LTS | Next.js 14+ 要求 |
| PostgreSQL | 15+ | 支持 JSONB、MERGE 语法 |

### 1.4 强制工具链

| 语言 | 格式化 | Lint | 类型检查 |
|------|--------|------|----------|
| Python | `ruff format` | `ruff check` | `mypy --strict` |
| Java | IDE 内置 (Google Java Format) | `checkstyle` + `spotbugs` | 编译器 |
| TypeScript | `prettier` | `eslint` (strict config) | `tsc --noEmit` |

**所有代码提交前必须通过对应的 Lint + 类型检查，CI 流水线中强制拦截。**

---

## 2. 项目结构规范

### 2.1 仓库整体结构

```
worldcup-predictor/
├── src/                           # Python 后端源码 (数据采集 + ML + FastAPI)
│   ├── adapters/                  # 数据源适配器 (M1)
│   ├── models/                    # SQLAlchemy ORM 模型
│   ├── dto/                       # Data Transfer Objects
│   ├── pipelines/                 # 数据清洗 Pipeline
│   ├── scrapers/                  # Scrapy 爬虫
│   ├── tasks/                     # Celery 任务
│   ├── events/                    # Kafka 事件
│   ├── ml/                        # ML 引擎 (M2)
│   │   ├── features/              # 特征工程
│   │   ├── models/                # 预测模型
│   │   ├── odds/                  # 赔率分析器
│   │   ├── backtest/              # 回测框架
│   │   └── training/              # 训练入口
│   ├── api/                       # FastAPI 推理服务
│   ├── content/                   # 内容生成 (M4)
│   ├── push/                      # 推送服务 (M6)
│   ├── utils/                     # 公共工具
│   └── config/                    # 配置
├── java-api/                      # Java Spring Boot 业务服务 (M3)
│   └── src/main/java/com/wcp/
│       ├── controller/            # REST 控制器
│       ├── service/               # 业务逻辑
│       ├── repository/            # 数据访问
│       ├── model/                 # JPA 实体
│       ├── dto/                   # 请求/响应 DTO
│       ├── security/              # 认证/授权
│       ├── config/                # Spring 配置
│       └── exception/             # 异常处理
├── web/                           # Next.js 前端 (M7)
│   └── src/
│       ├── app/                   # App Router 路由
│       ├── components/            # React 组件
│       ├── lib/                   # 工具库
│       ├── hooks/                 # 自定义 Hooks
│       ├── stores/                # Zustand 状态
│       ├── types/                 # TypeScript 类型
│       └── i18n/                  # 国际化
├── migrations/                    # Alembic 数据库迁移
├── scripts/                       # 运维/工具脚本
├── notebooks/                     # Jupyter 分析笔记本
├── deploy/                        # 部署配置
│   ├── charts/                    # Helm Charts
│   ├── terraform/                 # IaC
│   └── docker-compose.yml         # 本地开发环境
├── tests/                         # 测试
│   ├── python/                    # Python 测试
│   ├── java/                      # Java 测试
│   └── e2e/                       # 端到端测试
├── docs/                          # 项目文档
├── .github/workflows/             # CI/CD
├── pyproject.toml                 # Python 项目配置
├── pom.xml                        # Java Maven 配置 (java-api/)
└── package.json                   # 前端 (web/)
```

### 2.2 文件命名规范

| 场景 | 规则 | 正确示例 | 错误示例 |
|------|------|----------|----------|
| Python 模块 | snake_case | `odds_analyzer.py` | `OddsAnalyzer.py` |
| Python 类 | PascalCase | `class OddsAnalyzer` | `class odds_analyzer` |
| Java 类文件 | PascalCase | `MatchController.java` | `match_controller.java` |
| TypeScript 组件 | PascalCase | `MatchCard.tsx` | `match-card.tsx` |
| TypeScript 工具 | camelCase | `useAuth.ts` | `use_auth.ts` |
| CSS/Tailwind | kebab-case | `match-card.module.css` | `matchCard.css` |
| 数据库迁移 | `{timestamp}_{desc}` | `20260501_add_users_table.py` | `v1_users.py` |
| 测试文件 | `test_` 前缀 / `.test.` | `test_poisson.py` / `MatchCard.test.tsx` | `poisson_tests.py` |
| 环境变量 | UPPER_SNAKE_CASE | `DATABASE_URL` | `databaseUrl` |

### 2.3 单文件长度限制

| 文件类型 | 最大行数 | 超出处理 |
|----------|----------|----------|
| Python 模块 | 400 行 | 拆分子模块 |
| Java 类 | 500 行 | 拆分 Service / Helper |
| React 组件 | 300 行 | 拆分子组件 |
| 测试文件 | 无限制 | — |

---

## 3. Python 代码规范

适用范围: `src/` 目录下所有 Python 代码（数据采集、ML 引擎、FastAPI 服务、内容生成、推送服务）。

### 3.1 格式化与 Lint 配置

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E", "W",    # pycodestyle
    "F",          # pyflakes
    "I",          # isort
    "N",          # pep8-naming
    "UP",         # pyupgrade
    "B",          # flake8-bugbear
    "SIM",        # flake8-simplify
    "RUF",        # ruff 专属规则
]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### 3.2 导入顺序

使用 `ruff` 自动排序，分三组，组间空行：

```python
# 1. 标准库
import logging
from datetime import datetime, timezone
from typing import Optional

# 2. 第三方库
import httpx
from celery import shared_task
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# 3. 项目内部
from src.adapters.base import BaseDataSourceAdapter
from src.models.match import Match
from src.utils.rate_limiter import RateLimiter
```

### 3.3 类型标注

**所有函数签名必须有完整的类型标注，包括返回值。** 不允许 `Any` 类型在公开接口中出现。

```python
# ✅ 正确
def calculate_elo(
    team_id: int,
    match_date: datetime,
    k_factor: float = 40.0,
) -> float:
    """计算球队截至指定日期的 Elo 评分。"""
    ...

# ✅ 正确：复杂类型使用 TypeAlias
ScoreMatrix = list[list[float]]       # 10x10 比分概率矩阵
FeatureDict = dict[str, float | int]  # 特征字典

def compute_score_matrix(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = 10,
) -> ScoreMatrix:
    ...

# ❌ 错误：缺少类型标注
def calculate_elo(team_id, match_date, k_factor=40.0):
    ...

# ❌ 错误：使用 Any
def process_data(data: Any) -> Any:
    ...
```

### 3.4 Pydantic 模型 (DTO)

所有跨模块数据传输使用 Pydantic BaseModel，字段必须有 docstring 或 Field(description=)：

```python
class MatchDTO(BaseModel):
    """从外部数据源采集的比赛数据。"""

    external_id: str = Field(description="数据源原始 ID")
    home_team_name: str = Field(description="主队名称，用于内部实体匹配")
    away_team_name: str = Field(description="客队名称")
    match_date: datetime = Field(description="比赛时间 (UTC)")
    status: str = Field(description="比赛状态: scheduled/live/finished")
    home_score: int | None = Field(default=None, description="主队进球数")
    away_score: int | None = Field(default=None, description="客队进球数")

    model_config = ConfigDict(frozen=True)  # DTO 不可变
```

### 3.5 类设计规范

```python
class OddsAnalyzer:
    """赔率分析器：对比模型概率与博彩赔率，发现正 EV 机会。

    核心流程: 赔率 → 隐含概率 → 去抽水 → 计算 EV → 标记信号等级。

    Attributes:
        ev_threshold: EV 阈值，高于此值才标记为有价值。默认 0.05 (5%)。
        edge_threshold: Edge 阈值。默认 0.03 (3%)。
    """

    # --- 类常量 ---
    SIGNAL_STRONG: int = 3      # ⭐⭐⭐ EV > 15%
    SIGNAL_MEDIUM: int = 2      # ⭐⭐   EV 8%-15%
    SIGNAL_WEAK: int = 1        # ⭐     EV 5%-8%
    SIGNAL_NONE: int = 0        # 无信号

    def __init__(
        self,
        ev_threshold: float = 0.05,
        edge_threshold: float = 0.03,
    ) -> None:
        self._ev_threshold = ev_threshold
        self._edge_threshold = edge_threshold

    # --- 公开方法 ---
    def analyze_match(self, match_id: int, prediction: PredictionDTO) -> OddsAnalysisResult:
        """分析单场比赛的赔率价值。"""
        ...

    # --- 私有方法 ---
    def _remove_vig(self, implied_probs: list[float]) -> list[float]:
        """去除博彩公司抽水，归一化隐含概率。"""
        ...
```

**类结构统一顺序：**
1. Docstring
2. 类常量（UPPER_SNAKE_CASE）
3. `__init__`
4. 公开方法（按业务逻辑排序）
5. 私有方法（`_` 前缀）
6. 静态方法 / 类方法

### 3.6 异步代码规范 (FastAPI)

```python
# ✅ 正确：I/O 操作使用 async
@router.post("/predict", response_model=PredictionResponse)
async def predict_match(
    request: PredictRequest,
    db: AsyncSession = Depends(get_db),
    model_service: ModelService = Depends(get_model_service),
) -> PredictionResponse:
    """为指定比赛生成预测结果。"""
    features = await model_service.compute_features(request.match_id, db)
    prediction = model_service.predict(features)  # CPU 密集型，同步即可
    return PredictionResponse.from_prediction(prediction)

# ❌ 错误：async 函数内使用阻塞调用
async def bad_example():
    time.sleep(5)        # 阻塞事件循环！
    requests.get(url)    # 阻塞！应使用 httpx.AsyncClient
```

### 3.7 函数长度与复杂度

| 指标 | 限制 | 处理方式 |
|------|------|----------|
| 函数体行数 | ≤ 30 行 | 提取子函数 |
| 函数参数 | ≤ 5 个 | 超出封装为 Pydantic 模型或 dataclass |
| 圈复杂度 | ≤ 10 | 减少嵌套、提取策略模式 |
| 嵌套层级 | ≤ 3 层 | 提前 return / 提取函数 |

---

## 4. Java 代码规范

适用范围: `java-api/` 目录下所有 Java 代码（Spring Boot 业务服务）。

### 4.1 格式化配置

使用 Google Java Format，行宽 120 字符。IDE 安装对应插件自动格式化。

### 4.2 包结构

```
com.wcp/
├── controller/          # REST 控制器 — 仅负责 HTTP 入参/出参、调用 Service
├── service/             # 业务逻辑 — 核心业务编排
│   └── impl/            # Service 实现（接口 + 实现分离）
├── repository/          # 数据访问 — Spring Data JPA
├── model/               # JPA 实体 — 数据库映射
│   └── enums/           # 枚举类型
├── dto/                 # 请求/响应 DTO
│   ├── request/         # 入参 DTO
│   └── response/        # 出参 DTO
├── security/            # JWT、认证、授权
├── config/              # Spring 配置类
├── exception/           # 自定义异常 + 全局异常处理
├── client/              # 外部服务调用（ML API 等）
└── util/                # 工具类
```

### 4.3 命名规范

| 元素 | 规则 | 示例 |
|------|------|------|
| 类名 | PascalCase，名词 | `MatchService`, `UserController` |
| 方法名 | camelCase，动词开头 | `findMatchById()`, `createSubscription()` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT = 3` |
| 接口 | 不加 `I` 前缀 | `MatchService`（非 `IMatchService`） |
| 实现类 | 加 `Impl` 后缀 | `MatchServiceImpl` |
| DTO | 用途 + `Request` / `Response` | `PredictRequest`, `MatchDetailResponse` |
| 异常 | 用途 + `Exception` | `SubscriptionExpiredException` |

### 4.4 Controller 规范

```java
/**
 * 比赛数据 REST 控制器。
 *
 * <p>负责赛程查询、预测分发和赔率分析接口。
 * 根据用户订阅层级控制返回数据粒度。
 */
@RestController
@RequestMapping("/api/v1/matches")
@RequiredArgsConstructor
@Validated
@Tag(name = "比赛", description = "比赛赛程与预测数据")
public class MatchController {

    private final MatchService matchService;

    /**
     * 获取今日比赛列表及预测摘要。
     *
     * @param date 查询日期，默认今天
     * @param auth 当前认证用户信息（可为空，匿名用户）
     * @return 比赛列表，每场含预测摘要和价值信号
     */
    @GetMapping("/today")
    @Operation(summary = "今日比赛列表")
    public ResponseEntity<List<MatchSummaryResponse>> getTodayMatches(
            @RequestParam(required = false) @DateTimeFormat(iso = ISO.DATE) LocalDate date,
            @AuthenticationPrincipal UserPrincipal auth) {

        LocalDate queryDate = (date != null) ? date : LocalDate.now(ZoneOffset.UTC);
        SubscriptionTier tier = (auth != null) ? auth.getSubscriptionTier() : SubscriptionTier.FREE;

        List<MatchSummaryResponse> matches = matchService.getTodayMatches(queryDate, tier);
        return ResponseEntity.ok(matches);
    }
}
```

**Controller 原则：**
- Controller 不写业务逻辑，只做参数解析和 Service 调用
- 每个方法加 `@Operation` 注解（OpenAPI 文档）
- 入参用 `@Valid` + DTO 校验
- 返回值统一用 `ResponseEntity<T>`

### 4.5 Service 规范

```java
/**
 * 比赛服务 — 赛程查询与预测数据分发。
 *
 * <p>核心职责：
 * <ul>
 *   <li>从数据库查询比赛信息</li>
 *   <li>调用 ML API 获取预测结果</li>
 *   <li>根据用户订阅层级过滤返回数据</li>
 * </ul>
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class MatchServiceImpl implements MatchService {

    private final MatchRepository matchRepository;
    private final MlApiClient mlApiClient;
    private final RedisTemplate<String, Object> redisTemplate;

    private static final Duration CACHE_TTL = Duration.ofMinutes(5);

    @Override
    @Transactional(readOnly = true)
    public List<MatchSummaryResponse> getTodayMatches(LocalDate date, SubscriptionTier tier) {
        // 1. 尝试读缓存
        String cacheKey = "matches:today:" + date;
        // ...

        // 2. 查询数据库
        List<Match> matches = matchRepository.findByMatchDateBetween(
                date.atStartOfDay(ZoneOffset.UTC).toInstant(),
                date.plusDays(1).atStartOfDay(ZoneOffset.UTC).toInstant());

        // 3. 获取预测数据
        // ...

        // 4. 按订阅层级过滤
        return matches.stream()
                .map(m -> MatchSummaryResponse.fromEntity(m, prediction, tier))
                .toList();
    }
}
```

### 4.6 JPA 实体规范

```java
/**
 * 比赛实体 — 系统最核心的表，存储比赛基本信息和结果。
 */
@Entity
@Table(name = "matches", indexes = {
    @Index(name = "idx_matches_date", columnList = "matchDate"),
    @Index(name = "idx_matches_status", columnList = "status")
})
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)  // JPA 需要无参构造
@ToString(exclude = {"matchStats", "odds"})          // 避免懒加载触发
public class Match extends BaseEntity {

    @Column(name = "api_football_id", unique = true)
    private Integer apiFootballId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "home_team_id", nullable = false)
    private Team homeTeam;

    @Column(name = "match_date", nullable = false)
    private Instant matchDate;

    @Column(nullable = false, length = 20)
    @Enumerated(EnumType.STRING)
    private MatchStatus status = MatchStatus.SCHEDULED;

    // --- 业务方法 ---

    /** 比赛是否已结束。 */
    public boolean isFinished() {
        return this.status == MatchStatus.FINISHED;
    }
}
```

**JPA 规范要点：**
- 使用 Lombok `@Getter`，不使用 `@Data`（避免生成 setter 破坏封装）
- `@ToString` 排除关联对象（防止懒加载 N+1）
- 关联关系默认 `FetchType.LAZY`
- 业务判断方法写在实体内（充血模型）

---

## 5. TypeScript/React 代码规范

适用范围: `web/` 目录下所有前端代码（Next.js 14+ App Router）。

### 5.1 格式化与 Lint

```json
// .prettierrc
{
  "semi": true,
  "singleQuote": true,
  "trailingComma": "all",
  "tabWidth": 2,
  "printWidth": 100
}
```

ESLint 使用 `@typescript-eslint/recommended` + `next/core-web-vitals` 预设。

### 5.2 组件文件结构

每个组件文件内部统一顺序：

```tsx
// 1. 导入 — 外部库在前，内部模块在后
import { useState, useCallback } from 'react';
import Image from 'next/image';

import { cn } from '@/lib/utils';
import { useSubscription } from '@/hooks/useSubscription';
import type { MatchSummary, SubscriptionTier } from '@/types';

// 2. 类型定义
interface MatchCardProps {
  /** 比赛摘要数据 */
  match: MatchSummary;
  /** 当前用户订阅层级，控制显示粒度 */
  tier: SubscriptionTier;
  /** 点击卡片回调 */
  onClick?: (matchId: number) => void;
}

// 3. 组件实现
/**
 * 比赛卡片 — 首页赛程列表的单场比赛展示。
 *
 * 展示双方队名、比赛时间、胜平负概率、价值信号标签。
 * 根据 tier 控制是否显示详细赔率信号。
 */
export function MatchCard({ match, tier, onClick }: MatchCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const handleClick = useCallback(() => {
    onClick?.(match.id);
  }, [match.id, onClick]);

  return (
    <div
      className={cn(
        'rounded-lg border border-gray-200 p-4 transition-shadow',
        'hover:shadow-md cursor-pointer',
      )}
      onClick={handleClick}
      role="button"
      tabIndex={0}
    >
      {/* 比赛头部：队名 + 时间 */}
      <div className="flex items-center justify-between">
        <TeamBadge team={match.homeTeam} />
        <MatchTime date={match.matchDate} />
        <TeamBadge team={match.awayTeam} />
      </div>

      {/* 胜平负概率条（免费可见） */}
      <ProbabilityBar prediction={match.prediction} />

      {/* 价值信号标签（付费内容） */}
      {tier !== 'free' ? (
        <ValueSignalBadge signal={match.valueSignal} />
      ) : (
        <PaywallHint feature="赔率价值信号" />
      )}
    </div>
  );
}
```

### 5.3 命名规范

| 元素 | 规则 | 示例 |
|------|------|------|
| 组件 | PascalCase，名词/名词短语 | `MatchCard`, `ValueSignalBadge` |
| Hook | camelCase，`use` 前缀 | `useAuth`, `useSubscription` |
| 工具函数 | camelCase，动词开头 | `formatMatchDate`, `calculateEV` |
| 常量 | UPPER_SNAKE_CASE | `API_BASE_URL` |
| 类型/接口 | PascalCase | `MatchSummary`, `PredictionResponse` |
| 事件处理 | `handle` + 事件名 | `handleClick`, `handleSubmit` |
| Props | 组件名 + `Props` | `MatchCardProps` |
| 状态 | 描述性名称 | `isLoading`, `matchList`, `selectedDate` |

### 5.4 类型定义规范

```typescript
// types/match.ts

/** 比赛状态枚举 */
export type MatchStatus = 'scheduled' | 'live' | 'finished' | 'postponed' | 'cancelled';

/** 价值信号等级: 0=无, 1=⭐, 2=⭐⭐, 3=⭐⭐⭐ */
export type SignalLevel = 0 | 1 | 2 | 3;

/** 用户订阅层级 */
export type SubscriptionTier = 'free' | 'basic' | 'premium';

/** 比赛摘要 — 首页列表使用 */
export interface MatchSummary {
  id: number;
  homeTeam: TeamBrief;
  awayTeam: TeamBrief;
  matchDate: string;          // ISO 8601
  status: MatchStatus;
  prediction?: PredictionBrief;
  valueSignal?: SignalLevel;
  competitionName: string;
  round?: string;
}

/** 比赛完整详情 — 详情页使用 */
export interface MatchDetail extends MatchSummary {
  venue?: string;
  referee?: string;
  prediction: PredictionFull;
  oddsAnalysis?: OddsAnalysis;  // 付费用户可见
  report?: AnalysisReport;      // 付费用户可见
  h2h: H2HRecord;
}
```

**类型规范要点：**
- 优先使用 `interface`（可扩展），联合类型用 `type`
- 所有字段加 JSDoc 注释
- 可选字段用 `?`，不用 `| undefined`
- API 响应类型与后端 DTO 一一对应
- 统一放在 `types/` 目录，按业务域拆文件

### 5.5 状态管理 (Zustand)

```typescript
// stores/auth-store.ts

import { create } from 'zustand';
import type { SubscriptionTier } from '@/types';

interface AuthState {
  /** 是否已登录 */
  isLoggedIn: boolean;
  /** 用户 UUID */
  userUuid: string | null;
  /** 当前订阅层级 */
  tier: SubscriptionTier;

  /** 登录 */
  login: (uuid: string, tier: SubscriptionTier) => void;
  /** 登出 */
  logout: () => void;
  /** 更新订阅层级（支付成功后调用） */
  updateTier: (tier: SubscriptionTier) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isLoggedIn: false,
  userUuid: null,
  tier: 'free',

  login: (uuid, tier) => set({ isLoggedIn: true, userUuid: uuid, tier }),
  logout: () => set({ isLoggedIn: false, userUuid: null, tier: 'free' }),
  updateTier: (tier) => set({ tier }),
}));
```

### 5.6 React 组件原则

| 原则 | 说明 |
|------|------|
| 函数式组件 | 禁止使用 class 组件 |
| Props 不超过 7 个 | 超出封装为子对象 |
| 单一职责 | 一个组件只做一件事，超 200 行必须拆分 |
| 受控组件 | 表单元素使用受控模式 |
| 避免 index 作 key | 列表渲染使用唯一业务 ID |
| 禁止内联对象/函数 | `useMemo` / `useCallback` 包裹或提到组件外 |

---

## 6. 数据库规范

适用范围: 全部 PostgreSQL 表设计与查询（Phase 1-5 共 20+ 张表）。

### 6.1 表命名

| 规则 | 示例 | 说明 |
|------|------|------|
| 复数 snake_case | `matches`, `odds_snapshots` | 表名用复数 |
| 关联表 | `user_favorites` | 两个实体名拼接 |
| 缓存/统计表 | `track_record_stats` | 后缀说明用途 |
| 日志表 | `data_source_logs` | `_logs` 后缀 |

### 6.2 字段命名

| 规则 | 示例 |
|------|------|
| 主键 | `id` (BIGSERIAL) |
| 外键 | `{table_singular}_id`，如 `match_id`, `team_id` |
| 布尔 | `is_` / `has_` 前缀，如 `is_active`, `has_xg_data` |
| 时间 | `_at` 后缀（TIMESTAMPTZ），如 `created_at`, `published_at` |
| 日期 | `_date` 后缀（DATE），如 `match_date`, `value_date` |
| 金额 | 后缀标明单位，如 `price_cny`（分）, `market_value_eur` |
| 外部 ID | `{source}_id`，如 `api_football_id`, `transfermarkt_id` |

### 6.3 通用字段

每张业务表必须包含以下字段（日志表除外）：

```sql
created_at  TIMESTAMPTZ  NOT NULL  DEFAULT NOW(),
updated_at  TIMESTAMPTZ  NOT NULL  DEFAULT NOW()
```

### 6.4 索引规范

| 原则 | 说明 |
|------|------|
| 外键必建索引 | 所有 FK 字段自动建索引 |
| 查询驱动 | 只为实际查询路径建索引，不预设 |
| 命名规范 | `idx_{table}_{col1}_{col2}` |
| UNIQUE 约束 | `UNIQUE({cols}) WHERE {condition}` 支持部分唯一 |
| 复合索引列顺序 | 高选择性列在前 |

### 6.5 迁移脚本规范

```python
# migrations/versions/20260501_001_create_matches_table.py

"""Create matches table.

Phase 1: 核心比赛表，下游几乎所有模块都依赖此表。
"""

from alembic import op
import sqlalchemy as sa

revision = "20260501_001"
down_revision = "20260430_003"


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("api_football_id", sa.Integer, unique=True, nullable=True),
        # ... 其他字段
    )
    # 索引单独创建，便于注释说明用途
    op.create_index(
        "idx_matches_date",
        "matches",
        [sa.text("match_date DESC")],
        comment="赛程查询：按日期倒序",
    )


def downgrade() -> None:
    op.drop_table("matches")
```

**迁移规范要点：**
- 每个迁移文件只做一件事
- `upgrade()` 和 `downgrade()` 必须成对
- 生产环境禁止 `DROP COLUMN`，只能 `ADD COLUMN` + 软删除
- 大表 DDL 变更在低峰期执行

---

## 7. API 设计规范

适用范围: FastAPI (ML 服务) + Spring Boot (业务服务) 的所有 REST API。

### 7.1 URL 设计

| 规则 | 正确 | 错误 |
|------|------|------|
| 统一前缀 | `/api/v1/` | `/api/`, `/v1/` |
| 资源名用复数名词 | `/matches`, `/predictions` | `/match`, `/getMatches` |
| 层级关系用嵌套 | `/matches/{id}/prediction` | `/match-prediction?id=1` |
| 行为用 HTTP 方法 | `POST /subscriptions` | `POST /createSubscription` |
| kebab-case | `/track-record`, `/odds-analysis` | `/trackRecord` |

### 7.2 HTTP 方法

| 操作 | 方法 | 幂等性 |
|------|------|--------|
| 查询单个 | GET | 是 |
| 查询列表 | GET | 是 |
| 创建 | POST | 否 |
| 全量更新 | PUT | 是 |
| 部分更新 | PATCH | 否 |
| 删除 | DELETE | 是 |

### 7.3 统一响应格式

**成功响应：**
```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

**错误响应：**
```json
{
  "code": 40001,
  "message": "订阅已过期，请续费后查看完整分析",
  "error": "SUBSCRIPTION_EXPIRED"
}
```

**分页响应：**
```json
{
  "code": 0,
  "data": {
    "items": [...],
    "total": 150,
    "page": 1,
    "pageSize": 20,
    "hasMore": true
  }
}
```

### 7.4 HTTP 状态码

| 状态码 | 使用场景 |
|--------|----------|
| 200 | 成功（查询、更新） |
| 201 | 成功创建（注册、新建订阅） |
| 400 | 参数校验失败 |
| 401 | 未认证（Token 缺失或过期） |
| 403 | 无权限（免费用户访问付费内容） |
| 404 | 资源不存在 |
| 429 | 请求频率超限 |
| 500 | 服务端内部错误 |

### 7.5 版本管理

URL 路径版本控制 `/api/v1/`。当需要 breaking change 时：
1. 新增 `/api/v2/` 端点
2. 旧版本至少维护 3 个月
3. 旧版本响应头添加 `Deprecation: true`

---

## 8. 注释与文档规范

### 8.1 核心原则

> **注释解释"为什么"，代码本身说明"做什么"。**
>
> 如果需要注释来解释代码在做什么，说明代码需要重构。

### 8.2 Python 注释标准

**模块级 Docstring（每个 .py 文件顶部）：**
```python
"""赔率分析器模块。

对比模型预测概率与博彩赔率隐含概率，发现正 EV (+Expected Value) 投注机会。
这是本产品的核心价值模块——用户付费的主要动力之一。

核心流程:
    赔率获取 → 隐含概率转换 → 去抽水 → EV 计算 → 信号分级 → 结果存储

依赖:
    - predictions 表: 模型预测概率
    - odds_snapshots 表: 博彩赔率快照

对应 HLD 模块: M2 ML 引擎 → 赔率分析器子模块
"""
```

**类 Docstring：**
```python
class PoissonModel:
    """泊松基线预测模型 (Phase 2 Stage 1)。

    基于泊松分布假设，估计每队的期望进球数 λ，
    然后通过概率矩阵计算胜平负、比分、大小球概率。

    算法原理:
        P(k goals) = (λ^k × e^(-λ)) / k!
        λ_home = league_avg × attack_strength × defense_weakness × home_factor

    参考文献:
        Dixon & Coles (1997). Modelling Association Football Scores
        and Inefficiencies in the Football Betting Market.

    Attributes:
        home_factor: 主场优势系数，默认 1.2。
        xg_weight: xG 在进攻强度计算中的权重，默认 0.6。
    """
```

**函数 Docstring：**
```python
def compute_ev(
    model_prob: float,
    decimal_odds: float,
) -> float:
    """计算期望值 (Expected Value)。

    EV = (model_prob × decimal_odds) - 1
    正 EV 表示模型认为赔率被高估，存在正期望投注机会。

    Args:
        model_prob: 模型预测概率，范围 [0, 1]。
        decimal_odds: 欧洲小数赔率，如 2.10。

    Returns:
        期望值。如 0.155 表示 +15.5% 的正期望。

    Raises:
        ValueError: 当 model_prob 不在 [0, 1] 范围内时。
        ValueError: 当 decimal_odds < 1.01 时。

    Example:
        >>> compute_ev(model_prob=0.55, decimal_odds=2.10)
        0.155
    """
```

### 8.3 Java 注释标准

**类 Javadoc：**
```java
/**
 * 订阅服务 — 管理用户订阅生命周期。
 *
 * <p>核心职责：
 * <ul>
 *   <li>创建订阅订单并调用支付 SDK</li>
 *   <li>处理支付回调，激活订阅</li>
 *   <li>订阅到期自动降级为免费用户</li>
 * </ul>
 *
 * <p>支付流程详见 Phase 3 详细设计文档 §3.2.2。
 *
 * <p>对应 HLD 模块: M3 业务服务 → 订阅服务子模块。
 *
 * @see PaymentService 支付处理
 * @see SubscriptionTier 订阅层级枚举
 */
```

**方法 Javadoc（公开方法必须有）：**
```java
/**
 * 创建订阅订单。
 *
 * <p>流程：验证用户 → 创建 Payment 记录 → 调用支付 SDK → 返回支付参数。
 * 订单状态初始为 PENDING，支付成功后由回调接口更新。
 *
 * @param userId 用户 ID
 * @param request 包含订阅计划和支付渠道
 * @return 支付参数（前端用于唤起支付宝/微信支付）
 * @throws UserNotFoundException 用户不存在
 * @throws SubscriptionConflictException 用户已有有效的同级或更高订阅
 */
public PaymentInitResponse createSubscription(Long userId, CreateSubscriptionRequest request) {
```

### 8.4 TypeScript/JSDoc 注释标准

```typescript
/**
 * 付费墙覆盖层 — 覆盖在锁定内容上方。
 *
 * 设计原则：让免费用户"看到但拿不到"，内容显示 blur(8px) 模糊效果，
 * 中央显示锁定图标和解锁按钮。
 *
 * @see Phase 3 详细设计 §6.4 付费墙 UI 设计
 */
```

### 8.5 行内注释规范

```python
# ✅ 好的行内注释：解释"为什么"
# 国家队比赛主客场效应较弱，衰减主场优势系数
# 参考: 2022 世界杯数据分析，中立场地主场优势仅约 5%
if is_international:
    home_factor *= 0.5

# ✅ 好的行内注释：标记业务规则
# PRD §2: 免费用户只能看到胜平负预测，比分/赔率锁定
if tier == SubscriptionTier.FREE:
    prediction.score_matrix = None
    prediction.odds_analysis = None

# ❌ 坏的行内注释：翻译代码
# 设置 x 为 5
x = 5
# 遍历列表
for item in items:
```

### 8.6 TODO / FIXME / HACK 标记

```python
# TODO(Phase 4): 引入 Dixon-Coles 时间衰减权重优化
# FIXME: FBref 爬虫在周末返回空数据，疑似反爬策略变更
# HACK: Transfermarkt 身价单位不统一，临时硬编码转换，待重构
# NOTE: odds_snapshots 是只追加表，不做 UPDATE
# PERF: 此查询在 >10000 场时变慢，Phase 5 需要添加分区表
```

**规范：** 所有 TODO 必须标注对应 Phase 或 Issue 编号，禁止无期限的裸 TODO。

---

## 9. Git 工作流与提交规范

### 9.1 分支策略 (GitHub Flow 简化版)

```
main              ← 生产分支，始终可部署
├── staging       ← 预发布分支，自动部署到 staging 环境
├── feature/*     ← 功能分支: feature/phase1-match-adapter
├── bugfix/*      ← 修复分支: bugfix/fbref-scraper-timeout
└── hotfix/*      ← 紧急修复: hotfix/payment-callback-idempotent
```

| 规则 | 说明 |
|------|------|
| 从 `main` 创建分支 | `git checkout -b feature/phase2-poisson-model main` |
| PR 合并到 `main` | 必须通过 CI + 至少 1 人 Review |
| 删除已合并分支 | 合并后自动删除 feature 分支 |
| 禁止直接 push main | 通过 Branch Protection 强制 |

### 9.2 提交信息规范 (Conventional Commits)

```
<type>(<scope>): <简短描述>

<详细说明（可选）>

<关联信息（可选）>
```

**Type 类型：**

| Type | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(ml): 实现 Poisson baseline 模型` |
| `fix` | Bug 修复 | `fix(scraper): FBref 爬虫超时处理` |
| `refactor` | 重构 | `refactor(adapter): 统一数据源抽象层接口` |
| `perf` | 性能优化 | `perf(api): 预测接口添加 Redis 缓存` |
| `test` | 测试 | `test(ml): 添加泊松模型回测单元测试` |
| `docs` | 文档 | `docs: 更新 Phase 2 API 接口文档` |
| `chore` | 构建/工具 | `chore: 升级 Python 依赖` |
| `ci` | CI/CD | `ci: 添加 staging 自动部署 workflow` |
| `schema` | 数据库变更 | `schema: 新增 predictions 表` |

**Scope 范围：**

| Scope | 对应模块 |
|-------|----------|
| `adapter` | M1 数据采集 |
| `ml` | M2 ML 引擎 |
| `api` | M3 Java 业务服务 |
| `content` | M4 内容生成 |
| `track` | M5 战绩追踪 |
| `social` | M6 社交推送 |
| `web` | M7 前端 |
| `ops` | M8 运维监控 |
| `schema` | 数据库 Schema |
| `deploy` | 部署/基础设施 |

**完整示例：**
```
feat(ml): 实现赔率分析器 EV 计算逻辑

- 赔率转换为隐含概率（去抽水归一化）
- 计算 EV = (model_prob × odds) - 1
- 三级价值信号分级: ⭐/⭐⭐/⭐⭐⭐
- 支持多家博彩公司赔率对比取最佳

对应 Phase 2 DDD §4 赔率分析器设计
Closes #42
```

---

## 10. 测试规范

### 10.1 测试金字塔

| 层级 | 占比 | 说明 | 工具 |
|------|------|------|------|
| 单元测试 | 70% | 函数/类级别，mock 外部依赖 | pytest / JUnit5 / Jest |
| 集成测试 | 20% | API 端到端、数据库交互 | pytest + testcontainers / Spring Test |
| E2E 测试 | 10% | 核心用户流程 | Playwright |

### 10.2 覆盖率要求

| 模块 | 最低覆盖率 | 说明 |
|------|------------|------|
| ML 模型/特征 | 90% | 核心算法必须高覆盖 |
| 赔率分析器 | 90% | 涉及金钱的计算必须严格 |
| 数据 Pipeline | 80% | 数据质量是一切的基础 |
| API 接口 | 80% | 请求/响应格式正确 |
| 前端组件 | 70% | 核心交互逻辑 |
| 工具类 | 80% | 通用逻辑 |

### 10.3 测试命名

```python
# Python: test_{被测方法}_{场景}_{期望结果}
def test_compute_ev_positive_ev_returns_positive_value():
    ...

def test_compute_ev_negative_ev_returns_negative_value():
    ...

def test_compute_ev_invalid_prob_raises_value_error():
    ...

def test_poisson_model_predict_balanced_teams_returns_draw_probability_around_25pct():
    ...
```

```java
// Java: should_{期望行为}_when_{条件}
@Test
void should_return_free_tier_data_when_user_not_subscribed() { ... }

@Test
void should_reject_payment_when_order_already_paid() { ... }
```

```typescript
// TypeScript: describe 嵌套 + it 描述
describe('MatchCard', () => {
  it('renders home and away team names', () => { ... });
  it('shows blurred overlay for free users on paid content', () => { ... });
  it('calls onClick with match id when clicked', () => { ... });
});
```

### 10.4 ML 模型测试特殊要求

```python
class TestPoissonModel:
    """泊松模型测试。

    核心验证点:
    1. 概率输出合法（总和为 1，非负）
    2. 数据泄露防护（不使用未来数据）
    3. 表现优于随机基准线
    """

    def test_probabilities_sum_to_one(self, model, sample_features):
        """胜平负概率之和必须为 1.0。"""
        result = model.predict(sample_features)
        total = result.prob_home + result.prob_draw + result.prob_away
        assert abs(total - 1.0) < 1e-6

    def test_no_data_leakage(self, model, future_match):
        """特征计算不得使用比赛日期之后的数据。"""
        features = model.compute_features(future_match.id)
        for feature_date in features.data_dates:
            assert feature_date < future_match.match_date

    def test_beats_random_baseline(self, model, test_dataset):
        """命中率必须显著高于随机基准线 (33%)。"""
        accuracy = model.evaluate(test_dataset)
        assert accuracy > 0.40  # Phase 2 验收标准
```

---

## 11. 日志与错误处理规范

### 11.1 日志级别

| 级别 | 使用场景 | 示例 |
|------|----------|------|
| `ERROR` | 需要人工介入的错误 | 支付回调验签失败、数据库连接断开 |
| `WARNING` | 异常但可自动恢复 | 爬虫被封换代理、API 限流重试 |
| `INFO` | 关键业务事件 | 预测发布、订阅激活、模型训练完成 |
| `DEBUG` | 开发调试详情 | SQL 查询、HTTP 请求详情、特征计算中间值 |

### 11.2 日志格式

```python
# Python 结构化日志
import structlog

logger = structlog.get_logger(__name__)

logger.info(
    "prediction_published",
    match_id=match_id,
    model_version="poisson_v1",
    confidence=72,
    home_win_prob=0.45,
)

logger.error(
    "payment_callback_failed",
    order_no=order_no,
    channel="alipay",
    error=str(e),
    raw_callback=callback_data,  # 注意脱敏
)
```

```java
// Java 结构化日志
@Slf4j
public class PaymentService {
    public void handleCallback(String orderNo) {
        log.info("Processing payment callback: orderNo={}, channel={}",
                orderNo, channel);
        // ...
        log.error("Payment verification failed: orderNo={}, reason={}",
                orderNo, e.getMessage(), e);
    }
}
```

### 11.3 日志脱敏

**以下信息禁止出现在日志中：**
- 用户密码、密码哈希
- JWT Token 完整内容（只记录前 8 位）
- 支付卡号、银行账号
- OAuth access_token / refresh_token
- 用户手机号（中间 4 位用 `****` 替代）

### 11.4 错误处理

**Python:**
```python
# ✅ 正确：捕获具体异常，记录上下文，向上抛有意义的异常
class DataFetchError(Exception):
    """数据采集失败。"""
    def __init__(self, source: str, message: str, retry_count: int = 0):
        self.source = source
        self.retry_count = retry_count
        super().__init__(f"[{source}] {message} (retries: {retry_count})")


async def fetch_odds(self, match_id: int) -> list[OddsDTO]:
    try:
        response = await self._client.get(url, params=params)
        response.raise_for_status()
    except httpx.TimeoutException:
        logger.warning("odds_api_timeout", match_id=match_id, url=url)
        raise DataFetchError("odds_api", "Request timeout", retry_count=self._retries)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning("odds_api_rate_limited", match_id=match_id)
            await self._backoff()
            return await self.fetch_odds(match_id)  # 重试
        raise DataFetchError("odds_api", f"HTTP {e.response.status_code}")

# ❌ 错误：裸 except 吞掉异常
try:
    do_something()
except:
    pass
```

**Java:**
```java
// ✅ 全局异常处理器
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(SubscriptionExpiredException.class)
    public ResponseEntity<ErrorResponse> handleSubscriptionExpired(SubscriptionExpiredException e) {
        return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .body(new ErrorResponse(40301, "订阅已过期，请续费", "SUBSCRIPTION_EXPIRED"));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleUnexpected(Exception e) {
        log.error("Unexpected error", e);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(new ErrorResponse(50000, "服务器内部错误", "INTERNAL_ERROR"));
    }
}
```

---

## 12. 安全规范

### 12.1 认证与授权

| 规则 | 说明 |
|------|------|
| 密码哈希 | BCrypt，cost factor ≥ 12 |
| JWT 算法 | RS256（非对称），禁止 HS256 在多服务环境 |
| Token 有效期 | Access: 2h, Refresh: 30d |
| 敏感接口限流 | 登录: 5次/min，支付: 3次/min |
| SQL 注入 | 全程 ORM 参数化，禁止字符串拼接 SQL |
| XSS | React 自动转义 + CSP Header |
| CORS | 仅允许主域名白名单 |

### 12.2 密钥管理

| 规则 | 说明 |
|------|------|
| 禁止硬编码 | API Key、密码、Token 禁止出现在代码中 |
| 环境变量 | 通过 `.env` 文件 或 K8s Secret 注入 |
| `.gitignore` | `.env*` 必须在 gitignore 中 |
| 密钥轮换 | JWT 签名密钥每 90 天轮换 |

### 12.3 预测数据不可篡改

```python
# predictions 表写入后禁止修改，由 PostgreSQL 触发器保护
# 详见 Phase 2 DDD §5.2

# content_hash 计算方式
import hashlib, json

def compute_content_hash(prediction: dict) -> str:
    """计算预测内容的 SHA-256 哈希，用于不可篡改校验。"""
    canonical = json.dumps(prediction, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

---

## 13. 配置与环境管理

### 13.1 环境分层

| 环境 | 用途 | 数据库 | 配置方式 |
|------|------|--------|----------|
| `local` | 本地开发 | docker-compose PostgreSQL | `.env.local` |
| `test` | CI 测试 | 内存/容器数据库 | `.env.test` |
| `staging` | 预发布 | 独立 RDS 实例 | K8s ConfigMap + Secret |
| `production` | 生产 | RDS 高可用主备 | K8s ConfigMap + Secret |

### 13.2 配置读取规范

```python
# Python: pydantic-settings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """应用配置，从环境变量读取。"""

    # 数据库
    database_url: str
    database_pool_size: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API 密钥
    api_football_key: str
    odds_api_key: str

    # ML
    model_version: str = "latest"
    prediction_cache_ttl: int = 300  # 秒

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
```

```java
// Java: application.yml + @ConfigurationProperties
@ConfigurationProperties(prefix = "wcp")
@Validated
public record WcpProperties(
    @NotBlank String mlApiUrl,
    @NotBlank String jwtPublicKey,
    @Min(1) int cacheTimeoutMinutes
) {}
```

### 13.3 Feature Flag 规范

```python
# 功能开关存储在 Redis，30 秒刷新一次
# 管理员通过后台 UI 修改

FEATURE_FLAGS = {
    "enable_predictions": True,     # 是否展示预测
    "enable_ai_reports": True,      # 是否生成 AI 报告
    "enable_push": True,            # 是否发送推送
    "enable_payment": True,         # 是否开放支付
    "maintenance_mode": False,      # 全站维护模式
}

def is_feature_enabled(flag: str) -> bool:
    """检查功能开关是否开启，默认查 Redis，降级查内存。"""
    ...
```

---

## 14. 代码审查检查清单

每次 PR 提交时，Reviewer 按以下清单逐项检查：

### 14.1 通用检查

- [ ] CI 全部通过（Lint + 类型检查 + 测试）
- [ ] 提交信息符合 Conventional Commits 规范
- [ ] 无硬编码的密钥、Token、密码
- [ ] 无 `console.log` / `print()` 调试代码残留
- [ ] 新增代码有对应的单元测试
- [ ] 函数长度 ≤ 30 行，文件长度在限制范围内

### 14.2 Python 专项

- [ ] 所有公开函数有完整类型标注
- [ ] 所有公开类/函数有 docstring
- [ ] 使用 Pydantic 做数据校验，不手动 `if-else`
- [ ] 异步函数中无阻塞调用
- [ ] 数据泄露防护：特征计算有 `cutoff_date` 参数

### 14.3 Java 专项

- [ ] Controller 不包含业务逻辑
- [ ] Service 方法有 `@Transactional` 标注
- [ ] JPA 关联使用 `FetchType.LAZY`
- [ ] 入参 DTO 使用 `@Valid` 校验
- [ ] 异常由全局处理器统一处理

### 14.4 TypeScript/React 专项

- [ ] 组件 Props 有 TypeScript 接口定义
- [ ] 无 `any` 类型（特殊情况需注释说明）
- [ ] 列表渲染使用业务 ID 作为 key
- [ ] 付费墙逻辑无法在前端绕过（Server Component 或 API 校验）

### 14.5 数据库专项

- [ ] 迁移脚本有 `downgrade()`
- [ ] 新增字段有默认值或允许 NULL
- [ ] 查询路径有对应索引
- [ ] 无 N+1 查询

---

## 附录 A: 快速参考卡

### Python 必记

```
文件名: snake_case.py          类名: PascalCase
函数名: snake_case              常量: UPPER_SNAKE_CASE
私有方法: _leading_underscore   类型标注: 必须
行宽: 100                      Docstring: Google 风格
```

### Java 必记

```
文件名: PascalCase.java        类名: PascalCase
方法名: camelCase               常量: UPPER_SNAKE_CASE
接口: 无 I 前缀                实现: Impl 后缀
DTO: XxxRequest/XxxResponse    行宽: 120
```

### TypeScript 必记

```
组件: PascalCase.tsx           Hook: useXxx.ts
工具: camelCase.ts             类型: PascalCase
Props: XxxProps                状态: isXxx / xxxList
行宽: 100                     分号: 是 / 单引号: 是
```

### SQL 必记

```
表名: 复数 snake_case           字段: snake_case
主键: id (BIGSERIAL)           外键: {table}_id
布尔: is_ / has_ 前缀          时间: _at 后缀 (TIMESTAMPTZ)
索引: idx_{table}_{cols}       迁移: {timestamp}_{desc}.py
```

---

*— 代码规范文档结束 —*

*本规范随项目迭代更新。任何规范变更需通过 PR Review 确认后合并。*
