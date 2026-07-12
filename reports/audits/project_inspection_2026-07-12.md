# A-Share Multi-Factor Project — 全面项目检查报告

> 生成日期: 2026-07-12  
> 状态：清理前的只读检查快照；当前权威状态以根 README、项目总报告和 completion audit 为准。  
> 说明：本报告仅做检查与记录，不修改任何项目内容。

---

## 目录

1. [项目概览](#1-项目概览)
2. [目录结构](#2-目录结构)
3. [代码统计](#3-代码统计)
4. [架构与模块分析](#4-架构与模块分析)
5. [测试覆盖率分析](#5-测试覆盖率分析)
6. [配置与依赖](#6-配置与依赖)
7. [检查发现的问题](#7-检查发现的问题)
8. [代码质量评价](#8-代码质量评价)
9. [数据文件审计](#9-数据文件审计)
10. [报告文件审计](#10-报告文件审计)
11. [改进建议](#11-改进建议)

---

## 1. 项目概览

| 项目 | 内容 |
|------|------|
| 项目名称 | A-Share Multi-Factor Selection Research (A股多因子选股研究) |
| 研究标的 | 沪深300 (HS300) |
| 时间范围 | 2016-01-01 至 2025-12-31 |
| 开发语言 | Python 3 |
| 数据源 | baostock（行情数据）、akshare（基本面/财务数据） |
| 核心依赖 | pandas, numpy, POT (Python Optimal Transport) |
| 运行环境 | 系统 Python3 或 `quant` conda 环境 |
| Git 追踪文件 | 56 个 |

**项目演进阶段：**

1. **阶段 1** — 数据获取 + 价量因子（baostock, akshare）
2. **阶段 2** — EOT 漂移原型 (`src/eot_drift.py`)
3. **阶段 3** — 因子生命周期距离版 (`src/factor_lifecycle/`)
4. **阶段 4** — 正式 EOT-map 两样本检验 (`src/factor_lifecycle_test/`) ← **当前活跃开发**

---

## 2. 目录结构

```
a_share_multi_factor_project/
├── README.md                           # 项目说明文档
├── config/
│   └── config.yaml                     # 集中配置
├── data/
│   ├── raw/                            # 原始数据（baostock, akshare 下载）
│   │   ├── .gitkeep
│   │   ├── hs300_constituents_...
│   │   ├── market/                     # ~240 只个股 parquet
│   │   ├── akshare/
│   │   ├── fundamentals_akshare/
│   │   ├── adjust_factor/
│   │   ├── universe/
│   │   └── trade_calendar_...
│   └── processed/                      # 处理后数据面板
│       ├── .gitkeep
│       ├── clean_daily_data.csv
│       ├── hs300_dynamic_panel_*.parquet
│       ├── fundamental_panel_*.parquet
│       ├── market_cap_panel.parquet
│       ├── weekly_factor_performance.parquet
│       ├── eot_factor_drift_scores.parquet
│       ├── eot_factor_lifecycle/       # 旧版生命周期输出
│       ├── eot_factor_lifecycle_test/  # 新版 EOT-map 检验输出
│       └── coverage_expansion/
├── src/                                # 可复用研究模块 (2921 行)
│   ├── __init__.py
│   ├── eot_drift.py                   # 旧版 EOT 漂移
│   ├── analysis/                      # 因子分析
│   │   ├── ic.py                      # Rank IC / Pearson IC
│   │   ├── grouping.py                # 分位数分组收益
│   │   ├── correlations.py            # 因子相关性矩阵
│   │   ├── decay.py                   # IC 衰减
│   │   ├── attribution.py             # 市场模型归因
│   │   └── fama_macbeth.py            # Fama-MacBeth 回归
│   ├── backtest/                      # 回测执行
│   │   ├── costs.py                   # 换手率、线性成本
│   │   └── execution.py               # 可交易标志、订单约束
│   ├── data/                          # 数据加载清洗
│   │   ├── loader.py                  # CSV/Parquet 读取
│   │   ├── akshare_financials.py      # (615 行) 财务报表获取
│   │   ├── coarse_industry.py         # 行业分类映射
│   │   ├── coverage_expansion.py      # 覆盖扩展面板
│   │   ├── float_cap_proxy.py         # 自由流通市值代理
│   │   └── market_cap_panel.py        # 市值面板构建
│   ├── evaluation/                    # 评估指标
│   │   └── metrics.py                 # 夏普率/最大回撤等
│   ├── factors/                       # 因子构建
│   │   ├── preprocess.py              # 截尾/Z-score/中性化
│   │   ├── price_volume.py            # 动量/反转/低波/低换手
│   │   ├── value.py                   # BP/EP/SP/CFP
│   │   └── quality_growth_risk.py     # ROE/质量/增长/风险
│   ├── factor_lifecycle/              # 旧版生命周期（距离版）
│   │   ├── factor_registry.py         # 因子注册表 (21 个因子)
│   │   ├── lifecycle.py               # 权重归一化/漂移惩罚
│   │   └── preprocessing.py           # MAD 截尾/中性化
│   └── factor_lifecycle_test/         # 新版 EOT-map 两样本检验
│       ├── eot_map_two_sample.py      # 核心检验 (243 行)
│       ├── metric_registry.py         # 指标注册表 (8 个)
│       └── monitoring.py              # FDR/持续性/生命周期分类
├── scripts/                           # 运行脚本 (8583 行, 33 文件)
│   ├── 核心研究:
│   │   ├── run_full_research_pipeline.py
│   │   ├── run_demo.py
│   │   ├── run_eot_map_lifecycle_test.py      # (343 行)
│   │   ├── run_eot_factor_drift_feasibility.py # (910 行)
│   │   ├── run_eot_factor_lifecycle.py         # (745 行)
│   │   ├── run_smoke_factor_report.py
│   │   └── run_outline_completion_audit.py
│   ├── 数据下载:
│   │   ├── baostock_hs300_downloader_fixed.py   # (772 行)
│   │   ├── download_stock_akshare.py
│   │   ├── download_stocks_efinance.py
│   │   ├── download _stocks_baostocks.py        # ⚠️ 文件名含空格
│   │   ├── download_fundamentals_akshare.py
│   │   ├── fetch_akshare_financial_statements.py
│   │   └── fetch_broad_fundamentals.py
│   ├── 构建:
│   │   ├── build_fundamental_panel_from_akshare.py
│   │   ├── build_market_cap_panel.py
│   │   ├── build_coverage_expansion_panel.py
│   │   └── rebuild_akshare_fundamentals_with_market_cap.py
│   └── 其他:
│       ├── factors.py
│       ├── test.py
│       ├── probe_data_sources.py
│       ├── probe_akshare_financials.py
│       └── audit_task_711.py
├── tests/                            # 单元测试 (514 行, 6 文件)
│   ├── test_demo.py
│   ├── test_akshare_financials.py
│   ├── test_market_cap_panel.py
│   ├── test_factor_lifecycle.py
│   ├── test_eot_map_lifecycle_test.py
│   └── test_research_modules.py
├── reports/                          # 生成的研究报告
│   ├── completion_audit/
│   ├── eot_factor_drift_feasibility/
│   ├── eot_factor_lifecycle/
│   ├── eot_factor_lifecycle_test/
│   ├── demo/
│   ├── coverage_expansion/
│   ├── final/
│   ├── project_overview_report.md
│   ├── akshare_financial_data_audit.md
│   ├── akshare_fundamental_smoke_test.md
│   ├── market_cap_data_audit.md
│   └── market_cap_factor_smoke_test.md
├── notebook/                         # Jupyter Notebook
│   ├── stockdatacheck.ipynb
│   └── test.ipynb
├── results/                          # 结果输出（空，仅 .gitkeep）
├── task_711.md                       # 主要开发任务文档 (1832 行)
├── project_inspection_report.md      # 本报告
└── .gitignore
```

---

## 3. 代码统计

| 目录 | Python 文件数 | 总代码行数 | 备注 |
|------|:-----------:|:---------:|------|
| `src/` | 20 | 2,921 | 核心可复用模块 |
| `scripts/` | 33 | 8,583 | 运行脚本（含大量业务逻辑） |
| `tests/` | 6 | 514 | 单元测试 |
| **总计** | **59** | **12,661** | 不含 notebook、报告、配置 |

**最长文件 Top 5：**

| 文件 | 行数 | 说明 |
|------|:---:|------|
| `scripts/run_weekly_eot_drift_robustness.py` | 1,014 | 周度 EOT 漂移稳健性 |
| `scripts/run_eot_factor_drift_feasibility.py` | 910 | EOT 漂移可行性研究 |
| `scripts/baostock_hs300_downloader_fixed.py` | 772 | 沪深300数据下载器 |
| `scripts/run_eot_factor_lifecycle.py` | 745 | 旧版生命周期运行 |
| `scripts/run_weekly_eot_factor_drift.py` | 725 | 周度 EOT 漂移 |

---

## 4. 架构与模块分析

### 4.1 包架构

```
src/ (package)
├── eot_drift.py                     # 顶级模块：旧版 EOT 漂移
├── analysis/                        # 因子分析
├── backtest/                        # 回测执行
├── data/                            # 数据加载
├── evaluation/                      # 评估指标
├── factors/                         # 因子构建
├── factor_lifecycle/                # 旧版生命周期
│   ├── __init__.py                  # 导出 FACTOR_REGISTRY, lifecycle_factor_names
│   ├── factor_registry.py           # FactorSpec 数据类
│   ├── lifecycle.py                 # 权重/漂移/回测
│   └── preprocessing.py             # 截面预处理
└── factor_lifecycle_test/           # 新版 EOT-map 检验
    ├── __init__.py                  # 导出 EOT_METRIC_NAMES, METRIC_REGISTRY
    ├── eot_map_two_sample.py        # 核心检验逻辑
    ├── metric_registry.py           # 指标规格
    └── monitoring.py                # 多重比较/持续性/分类
```

### 4.2 模块间依赖关系

- `src/factors/` ← 依赖 `src/data/loader.py`
- `src/analysis/` ← 依赖 `src/data/`, `src/analysis/`
- `src/factor_lifecycle/` ← 独立（不依赖其他 src 子包）
- `src/factor_lifecycle_test/` ← 依赖 `src/factor_lifecycle/`
- `scripts/` ← 依赖 `src/*`
- `tests/` ← 依赖 `src/*` 和 `scripts/*`

### 4.3 `__init__.py` 导出 API 分析

| 包 | 导出内容 |
|----|---------|
| `src` | 仅 docstring（无导出） |
| `src.analysis` | 仅 docstring（无导出） |
| `src.backtest` | 仅 docstring（无导出） |
| `src.data` | 仅 docstring（无导出） |
| `src.evaluation` | 仅 docstring（无导出） |
| `src.factors` | 仅 docstring（无导出） |
| `src.factor_lifecycle` | `FACTOR_REGISTRY`, `lifecycle_factor_names`, `preprocess_factor_cross_section`, `registry_frame` |
| `src.factor_lifecycle_test` | `EOT_METRIC_NAMES`, `METRIC_REGISTRY`, `metric_registry_frame` |

**发现**：只有 `factor_lifecycle` 和 `factor_lifecycle_test` 有显式导出，其他子包虽是正规包的 `__init__.py` 但仅包含 docstring。

---

## 5. 测试覆盖率分析

### 5.1 测试文件与覆盖模块

| 测试文件 | 行数 | 覆盖范围 |
|---------|:---:|---------|
| `test_demo.py` | 28 | 演示脚本核心函数 |
| `test_akshare_financials.py` | 82 | 财务报表转换、TTM、增长率 |
| `test_market_cap_panel.py` | 53 | 市值面板、万→元转换 |
| `test_factor_lifecycle.py` | 114 | 生命周期预处理/权重/漂移，EOT 旧版 |
| `test_eot_map_lifecycle_test.py` | 94 | EOT-map 两样本检验核心 |
| `test_research_modules.py` | 143 | 价量因子/IC/回测/执行/风险因子 |

### 5.2 覆盖不足的模块

| 模块 | 评估 |
|------|------|
| `src.data.akshare_financials.py` | 有测试但只覆盖核心函数，未覆盖批量获取/多进程 |
| `src.data.coarse_industry.py` | **无直接测试**（仅在 `test_factor_lifecycle.py` 间接使用） |
| `src.data.coverage_expansion.py` | **无测试** |
| `src.data.float_cap_proxy.py` | **无测试** |
| `src.data.market_cap_panel.py` | 有测试（万→元转换）|
| `src.analysis.attribution.py` | **无直接测试** |
| `src.evaluation.metrics.py` | **无直接测试** |
| `src.factors.value.py` | **无直接测试**（仅在 `test_market_cap_panel.py` 间接覆盖） |
| `src.factor_lifecycle_test.monitoring.py` | 有测试（FDR/持续性/惩罚）|

### 5.3 测试依赖问题

- `tests/test_factor_lifecycle.py` 导入了 `scripts.run_eot_factor_lifecycle` — 测试依赖脚本，违背常规测试原则
- `tests/test_demo.py` 导入了 `scripts.run_demo` — 同上

---

## 6. 配置与依赖

### 6.1 配置文件

| 文件 | 状态 |
|------|------|
| `config/config.yaml` | ✅ 53 行，涵盖项目参数、路径、回测设置、EOT-map 参数、因子参数 |
| `README.md` | ✅ 81 行，描述项目状态与用法 |
| `.gitignore` | ✅ 45 行，覆盖 macOS/Python/数据/结果 |

### 6.2 缺失的配置/构建文件

| 文件 | 状态 | 影响 |
|------|------|------|
| `pyproject.toml` / `setup.py` | ❌ 缺失 | 无法 `pip install -e .` 安装 |
| `requirements.txt` / `Pipfile` | ❌ 缺失 | 依赖不明确 |
| `pytest.ini` / `conftest.py` | ❌ 缺失 | 需从根目录运行 `python -m pytest tests/` |
| `Makefile` | ❌ 缺失 | 无标准化命令入口 |
| `.flake8` / `ruff.toml` | ❌ 缺失 | 无代码风格检查配置 |

### 6.3 依赖推断

根据代码导入分析，项目依赖：

```
pandas>=1.5
numpy>=1.23
pot>=0.9          (Python Optimal Transport)
matplotlib>=3.6
seaborn>=0.12
pyarrow / fastparquet  (parquet 读写)
akshare            (金融数据 API)
baostock           (行情数据 API)
```

---

## 7. 检查发现的问题

### 🔴 严重问题

#### P1: 文件名包含空格

**文件**: `scripts/download _stocks_baostocks.py`

文件名 `download _stocks_baostocks.py` 中包含空格，在 Unix/Linux/macOS 命令行中会导致各种问题：
- 无法通过 `python scripts/download _stocks_baostocks.py` 直接调用
- 可能被其他脚本或工具遗漏
- 建议重命名为 `download_stocks_baostocks.py`

#### P2: 引用不存在的文件

**文件**: `README.md`
```
"A股多因子选股项目大纲.md": target research scope and success criteria.
```
该文件（`A股多因子选股项目大纲.md`）**不存在于项目目录中**。

### 🟡 中等问题

#### P3: 无 Python 包构建配置

缺少 `pyproject.toml` 或 `setup.py`，导致：
- 无法通过 `pip install -e .` 安装
- 无法声明依赖版本
- `import src` 仅靠 PYTHONPATH 工作

#### P4: 测试依赖脚本模块

- `tests/test_factor_lifecycle.py` 导入 `scripts.run_eot_factor_lifecycle._dynamic_cluster_map, _dynamic_redundancy_map`
- `tests/test_demo.py` 导入 `scripts.run_demo.CORE_FACTORS, backward_signal_date`

这导致测试依赖于脚本模块正常导入，而脚本模块通常不应作为库被导入。

#### P5: 脚本中包含大量业务逻辑

脚本文件（如 `run_eot_map_lifecycle_test.py` 343 行、`run_eot_factor_lifecycle.py` 745 行）包含了大量本应放入 `src/` 模块的业务逻辑。这导致：
- 代码复用困难
- 无法单独测试脚本中的逻辑

#### P6: `src/eot_drift.py` 与 `src/factor_lifecycle_test/` 功能重叠

旧版 `eot_drift.py` 与新版的 `eot_map_two_sample.py` 都是做 EOT 相关计算，但前者是顶级模块、后者在子包中。存在一定程度的功能重叠和代码组织不一致。

### 🟢 小问题 / 建议

#### P7: `results/` 目录空（除 .gitkeep）

`results/` 有 `.gitkeep` 但为空。部分脚本似乎将结果输出到 `reports/` 而非 `results/`。

#### P8: 部分模块缺少测试

见 [5.2 覆盖不足的模块](#52-覆盖不足的模块)。

#### P9: `src/factor_lifecycle/preprocessing.py` 与 `src/factors/preprocess.py` 代码重复

两个模块都实现了 MAD 截尾和 Z-score 标准化功能，API 不同但逻辑重复：
- `src/factors/preprocess.py`: `winsorize_series()`, `zscore_series()`, `neutralize_cross_section()`
- `src/factor_lifecycle/preprocessing.py`: `_mad_winsorize()`, `_zscore()`, `preprocess_factor_cross_section()`

#### P10: 依赖没有明确声明

无 `requirements.txt` 或 `pyproject.toml`，新环境配置较麻烦。

#### P11: `scripts/` 目录没有 `__init__.py` 但有 `__pycache__/`

`scripts/__pycache__/` 目录存在但 `__init__.py` 不存在，表明之前运行时自动生成了缓存。

---

## 8. 代码质量评价

### 8.1 优点

| 方面 | 评价 |
|------|------|
| **代码风格** | 统一使用 `from __future__ import annotations`，类型提示良好（含 `|` union 语法） |
| **数据类** | 善用 `@dataclass` 定义结果类型（`EOTDriftResult`, `FactorSpec`, `MetricSpec`, `TableSummary`） |
| **错误处理** | POT 失败时有 fallback 逻辑，数值稳定性考虑（`np.where(std <= 1e-12, 1.0, std)`）|
| **无未来数据** | 明确强调 PIT-safe 设计，`rolling_past_stat()` 使用 `shift(1)` 排除当期 |
| **文档字符串** | 每个模块和函数都有清晰的 docstring |
| **测试质量** | 测试覆盖了核心逻辑边界情况（如常量列、nan、未来数据防范）|

### 8.2 不足

| 方面 | 评价 |
|------|------|
| **模块组织** | `src/eot_drift.py` 为顶级模块，缺乏一致性 |
| **脚本臃肿** | 部分脚本超 700 行，包含过多业务逻辑 |
| **无格式化配置** | 未发现 `ruff`/`black`/`isort` 配置 |
| **无 CI/CD** | 无 `.github/workflows/` 或类似配置 |

---

## 9. 数据文件审计

### 9.1 原始数据 (`data/raw/`)

| 文件/目录 | 大小估计 | 说明 |
|-----------|---------|------|
| `market/` | ~240 parquet 文件 | 个股日行情（baostock） |
| `akshare/` | - | akshare 数据缓存 |
| `fundamentals_akshare/` | - | 基本面原始数据 |
| `adjust_factor/` | - | 复权因子 |
| `universe/` | - | 股票池快照 |
| `trade_calendar_*.parquet` | 小 | 交易日历 |
| `hs300_constituents_*.csv` | 小 | 成分股列表 |

### 9.2 处理后数据 (`data/processed/`)

| 文件 | 说明 |
|------|------|
| `clean_daily_data.csv` | 清洗后日频数据 |
| `hs300_dynamic_panel_*.parquet` | 动态面板（行情+因子） |
| `hs300_member_sample_*.parquet` | 样本面板 |
| `fundamental_panel_akshare.parquet` | 基本面面板 |
| `fundamental_panel_akshare_with_market_cap.parquet` | 含市值的基本面面板 |
| `market_cap_panel.parquet` | 市值面板 |
| `weekly_factor_performance.parquet` | 周度因子表现 |
| `eot_factor_drift_scores.parquet` | EOT 漂移分数 |
| `weekly_eot_factor_drift_scores.parquet` | 周度 EOT 漂移分数 |

**注意**：根据 `.gitignore`，`data/raw/*` 和 `data/processed/*` 不纳入版本控制。以上文件存在于磁盘但不会被 commit。

---

## 10. 报告文件审计

`reports/` 目录包含丰富的已生成报告：

| 分类 | 内容 |
|------|------|
| **完成度审计** | `completion_audit/` — 项目完整度评估 |
| **EOT 漂移可行性** | `eot_factor_drift_feasibility/` — 含 5 个 .md 报告、6 个 .csv、9 个 PNG |
| **旧版生命周期** | `eot_factor_lifecycle/` — 含 7 个 .md、10 个 .csv、16 个 PNG |
| **新版生命周期检验** | `eot_factor_lifecycle_test/` — 含 5 个 .md、10 个 .csv、14 个 PNG |
| **最终报告** | `final/` — 价值因子、质量-增长-风险因子、综合因子报告 |
| **Demo** | `demo/` — 含演示报告、回测摘要、图表 |
| **数据审计** | akshare 基本面审计、市值审计、覆盖扩展审计 |

---

## 11. 改进建议

### 高优先级

1. **重命名 `download _stocks_baostocks.py`** — 去除文件名中的空格
2. **添加 `pyproject.toml`** — 声明依赖和项目元数据
3. **创建 `requirements.txt`** — 锁定依赖版本
4. **补充 `A股多因子选股项目大纲.md` 或修改 README 引用**

### 中优先级

5. **脚本逻辑迁移** — 将 `scripts/run_*.py` 中的业务逻辑抽到 `src/` 下相应模块
6. **消除测试对脚本的依赖** — 将被测试的函数移到 `src/` 中
7. **消除 `preprocess.py` 与 `preprocessing.py` 的代码重复**
8. **为缺失测试的模块补充测试**：`coarse_industry.py`, `coverage_expansion.py`, `float_cap_proxy.py`, `attribution.py`, `metrics.py`, `value.py`
9. **统一 `src/eot_drift.py` 的组织** — 放入适当的子包或与新 EOT-map 模块合并

### 低优先级

10. **添加代码风格配置**（`.github/workflows/`, `ruff.toml`）
11. **添加 CI 配置**（GitHub Actions 自动运行测试）
12. **清理 `scripts/__pycache__/`** 并添加 `__init__.py`（如需要作为包）
13. **整理 `results/` 与 `reports/` 的输出路径分工**
14. **删除 `data/.DS_Store` 并确认 `.gitignore` 生效**

---

## 总结

这是一个功能完整、代码质量较高的 A 股多因子量化研究平台。项目代码风格统一，类型提示规范，PIT-safe 和防未来数据意识强。当前处于 **阶段 4**（EOT-map 两样本检验升级）的活跃开发中。

核心优势在于：
- 完善的数据管道（baostock + akshare）
- 丰富的价量/基本面因子库
- 前沿的 EOT 因子漂移监控
- 清晰的项目演进记录

主要改进空间在于：
- 工程化配置缺失（pyproject.toml, requirements.txt）
- 脚本层过厚，复用性不足
- 测试覆盖率有待提升
- 文件名问题（含空格）
