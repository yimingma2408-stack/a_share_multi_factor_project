# A 股多因子研究与 EOT 因子生命周期监控项目报告

> ## 当前状态说明（2026-07-12，优先于以下历史叙述）
>
> 本项目的权威生命周期结论已升级为 `reports/eot_factor_lifecycle_test/` 下的正式 EOT-map 两样本检验：10 个价量因子、3,165 个周度检验、共同单位球 reference、base-only scaling、缩放统计量、300 次 IID/block centered multiplier bootstrap、FDR、持续告警及坐标恶化诊断。
>
> 本文以下涉及 `epsilon scale=0.1`、EWMA distance drift、旧生命周期比例或旧 drift penalty 的段落，均是**保留的 distance-based baseline**，不是正式 p-value 结论。正式方法与结果以 `reports/eot_factor_lifecycle_test/eot_map_factor_lifecycle_final_report.md` 为准。
>
> 基本面扩展面板没有未来可用日期违规，但缺少 dated PIT-safe industry history；因此它们是 conditional research inputs，不进入 headline formal multifactor allocation。详见 `reports/data_quality/point_in_time_coverage_audit.md`。

## 1. 项目概述

本项目构建了一个面向 A 股的多因子研究原型，主线是：

> 在动态沪深 300 股票池上构建价量因子，评价因子有效性，使用熵正则最优传输（EOT）监控因子表现分布漂移，并将漂移信息用于因子生命周期诊断和保守调权实验。

项目的核心定位不是直接寻找一个可以宣称实盘有效的交易策略，而是建立一套可复现、可审计、能够识别因子失效风险的研究流程。

当前项目已经覆盖：

- 动态沪深 300 日频数据整理；
- 价量因子注册和计算；
- 单因子 Rank IC、ICIR、多空收益和换手率评价；
- 周度 EOT 漂移监控；
- 因子生命周期状态识别；
- 因子相关性聚类和冗余控制；
- 月度 walk-forward 组合回测；
- 交易成本和市场状态敏感性分析；
- 财务、行业和自由流通市值覆盖扩展实验；
- 面向简历展示的五因子 Demo。

## 2. 研究股票池和数据

### 2.1 动态沪深 300 股票池

项目使用的是动态沪深 300 成分股面板，而不是把当前成分股静态回填到整个历史区间。

- 研究区间：2016-01-04 至 2025-12-31；
- 历史出现过的不同股票：627 只；
- 单期有效股票数量随成分调整、停牌、ST 和交易状态变化；
- 平均有效股票池约 296 只；
- 月度组合通常选择有效股票池前 20%，约 50–60 只股票。

### 2.2 日频字段

日频面板主要包含：

- 开高低收价格和复权价格；
- 日收益率；
- 成交额；
- 换手率；
- 交易状态；
- ST 标记；
- 动态沪深 300 成员标记；
- 总市值和部分自由流通市值字段。

项目默认使用后复权或前复权价格构造研究信号，并将未来收益严格放在信号构造之后计算。

## 3. 因子库

### 3.1 正式 EOT 生命周期分析使用的 10 个因子

正式生命周期分析启用了 10 个市场价量因子：

1. `reversal_1m`：过去 1 个月收益率的反向指标；
2. `momentum_1m`：1 个月动量；
3. `momentum_3m`：3 个月动量；
4. `momentum_6m`：6 个月动量；
5. `momentum_12m`：12 个月动量；
6. `volatility_1m`：1 个月低波动；
7. `volatility_3m`：3 个月低波动；
8. `turnover_1m`：1 个月低换手；
9. `turnover_3m`：3 个月低换手；
10. `liquidity_1m`：1 个月成交额流动性。

### 3.2 已实现但未全部进入正式生命周期的因子

因子注册表共包含 31 个定义，除正式 10 因子外，还包括：

- 跳过最近一个月的动量因子；
- 120 日和 250 日低波动；
- 低换手的对数变换；
- Size；
- Rolling beta；
- 特异波动率；
- Downside beta；
- Book-to-price、Earnings yield、Sales yield、Cash-flow yield；
- Value composite；
- ROE、Gross profitability、OCF to assets；
- Revenue growth、Earnings growth。

财务因子已经有计算框架，但在原有正式生命周期结果中因覆盖率不足被排除或标记为 watch-only。

## 4. 单因子研究流程

每个因子的基本研究流程为：

1. 从价格、收益、成交额或换手率构造原始因子；
2. 根据交易状态、ST 和历史观测长度过滤不可用股票；
3. 横截面 MAD winsorization；
4. 横截面标准化；
5. 在有足够数据时进行 Size 或行业中性化；
6. 计算未来一周或未来一个月收益；
7. 计算 Rank IC、ICIR、多空收益、胜率、因子换手和覆盖率；
8. 记录因子表现随时间的变化。

主要评价指标包括：

- Rank IC：因子排序与未来收益排序的相关性；
- ICIR：平均 Rank IC 除以 Rank IC 波动；
- 多空收益：高因子组减低因子组；
- 正收益周期比例；
- 因子换手率；
- 有效股票覆盖率；
- 因子相关性和冗余度。

研究中明确区分因子构造信息和未来收益信息，未来收益不会反向进入因子计算。

## 5. EOT 漂移监控

### 5.1 EOT 解决的问题

传统因子评价通常只看因子平均 IC 或平均收益，但因子可能在平均表现没有明显变化时，已经发生了表现结构变化。

本项目使用 EOT 比较因子历史表现分布和近期表现分布，识别：

- 因子 IC 分布是否变化；
- 因子多空收益分布是否变化；
- 因子 downside 表现是否变化；
- 因子表现的联合分布是否发生漂移。

因此，EOT 在本项目中的主要作用是“因子失效风险监控”，不是单独的收益预测器。

### 5.2 EOT 输入和参数

EOT 输入保持三维：

```text
(RankIC, long_short_return, downside_return)
```

主要参数：

- Base window：156 周；
- Recent window：26 周；
- Reference points：100；
- Epsilon scale：0.1；
- Random seed：42；
- EWMA half-life：8 周。

同时保留以下对照诊断：

- Energy distance；
- MMD；
- Mean shift；
- Covariance shift；
- Sinkhorn 收敛状态。

### 5.3 漂移和生命周期

EOT 漂移经过 EWMA 平滑后，与以下信息共同决定生命周期状态：

- 历史 ICIR；
- 近期 ICIR；
- ICIR 趋势；
- 漂移信号的历史扩展分位数；
- 因子资格状态。

最终状态包括：

- `Healthy`：历史和近期表现稳定；
- `Watch`：出现质量或漂移风险；
- `Decaying`：近期表现恶化并伴随较高漂移；
- `Dormant`：历史长度不足或表现缺乏有效性；
- `Recovering`：近期表现改善。

生命周期分析的总体状态比例约为：

- Dormant：42.91%；
- Healthy：41.04%；
- Watch：10.79%；
- Decaying：3.67%；
- Recovering：1.58%。

早期样本因为历史窗口不足，会被保守地标记为 Dormant，而不是强行判断为有效或失效。

## 6. 因子聚类、去冗余和调权

项目将横截面相关性和因子多空收益相关性结合起来进行聚类：

- 相关性距离：`1 - |correlation|`；
- 使用 average linkage；
- 聚类距离阈值：0.40；
- 聚类和冗余关系在 walk-forward 中只使用当时已经可获得的历史数据。

正式研究中观察到的高冗余关系包括：

- `reversal_1m` 与 `momentum_1m`；
- `turnover_1m` 与 `turnover_3m`；
- `volatility_1m` 与 `volatility_3m`；
- `turnover_1m` 与 `liquidity_1m`。

组合调权方法包括：

- Equal eligible factors；
- Cluster representative equal；
- ICIR weighted；
- ICIR + EOT drift penalty；
- Redundancy-aware weighting；
- Turnover/cost-aware weighting；
- Lifecycle-filtered drift weighting。

EOT 惩罚采用保守裁剪，例如将漂移惩罚限制在合理区间内，避免短期噪声导致权重完全归零。

## 7. 回测设计

组合回测采用月度 walk-forward 方式：

- 使用调仓日前最近的周度信号；
- 选择有效股票池前 20%；
- 股票等权；
- 过滤 ST、停牌和部分不可交易股票；
- 使用约 120 个交易日的历史观测长度约束；
- 计算组合收益、Sharpe、最大回撤、Calmar、胜率和换手率；
- 测试 0、5、10、20 bps 交易成本。

生命周期正式回测中，10 bps 下的代表性结果包括：

- Cluster representative equal：Sharpe 约 0.436；
- Equal eligible：Sharpe 约 0.426；
- ICIR + EOT：Sharpe 约 0.308；
- Lifecycle-filtered drift：Sharpe 约 0.310。

这说明在完整生命周期研究中，EOT 惩罚并没有稳定优于简单等权方法，因此结论应当是：

> EOT 当前更适合作为监控信号，而不是已经验证的收益优化器。

早期 MVP 可行性实验中，ICIR + EOT 在无成本条件下相对于简单等权有过较好的结果，但这属于单次历史实验，不能与正式生命周期结果混淆，也不能作为 EOT 稳定增益的证据。

## 8. 简历 Demo

项目另外提供了一个轻量 Demo，避免把尚不完整的财务和行业数据混入主结果。

Demo 使用 5 个核心价量因子：

- reversal；
- 3 个月 momentum；
- 1 个月 low volatility；
- 1 个月 low turnover；
- liquidity。

Demo 输出：

- 周度因子表现；
- 周度 EOT drift；
- 生命周期状态；
- 因子权重；
- 月度组合净值；
- 交易成本敏感性；
- 漂移时间线；
- 生命周期热力图。

Demo 报告中的最新状态分布约为：

- Healthy：44.48%；
- Dormant：36.44%；
- Watch：11.25%；
- Decaying：6.06%；
- Recovering：1.78%。

Demo 在 10 bps 下观察到 Equal strategy Sharpe 约 0.444。该结果仅用于展示完整研究流程，不代表实盘策略或可交易 alpha。

## 9. 财务、行业与自由流通市值扩展

这部分作为独立的 coverage expansion 分支完成，未覆盖原有 EOT、Demo 或历史回测结果。

### 9.1 财务数据

使用 AKShare 抓取并标准化：

- 资产负债表；
- 利润表；
- 现金流量表。

扩展后：

- 目标股票数：627 只；
- 月度财务面板：69,016 条记录；
- 财务有效日期 PIT 违规：0；
- 主要价值、质量和成长字段覆盖率大多在 95% 以上。

面板保留：

- `report_date`；
- `announcement_date`；
- `available_date`；
- `data_vintage`；
- `available_date_method`；
- `financial_data_quality`；
- `financial_imputation_flag`；
- `source_revision_available`。

### 9.2 粗粒度行业

使用 BaoStock 批量行业接口获得最新行业快照，并映射到 11 个粗粒度行业桶：

- financials；
- industrials；
- information technology；
- healthcare；
- consumer discretionary；
- consumer staples；
- materials energy；
- utilities；
- real estate；
- telecom；
- other。

行业标签覆盖率为 100%，但当前是最新快照：

- `industry_pit_safe = false`；
- 历史行业 PIT 安全比例为 0%；
- 不能直接作为严格历史回测中的无条件行业标签。

### 9.3 自由流通市值代理

使用三层市值结构：

- Level A：真实自由流通市值；
- Level B：行业和规模分层的自由流通比例代理；
- Level C：总市值兜底。

当前结果：

- 市值或代理覆盖率：99.99%；
- Level A：约 80.6%；
- Level B：约 1.8%；
- Level C：约 17.6%。

### 9.4 三种研究模式

扩展审计固定区分：

- Strict：真实可用日期、PIT 安全行业、Level A/B 市值；
- Expanded：允许保守财务滞后、最新行业快照和 Level C 市值；
- Proxy Sensitivity：只观察 Level C 代理的敏感性结果。

当前审计结果：

- Strict：0 条可用绩效记录，原因是缺少历史 PIT 行业；
- Expanded：1,186 条因子-日期绩效记录；
- Proxy Sensitivity：236 条诊断记录；
- PIT 违规数：0；
- 股票目标数和市值代理覆盖率均通过第一阶段验收。

因此，扩展分支可以用于扩大覆盖率、数据质量监控和敏感性分析，但不能被描述成商业级 point-in-time 财务数据库。

## 10. 代码和结果组织

### 10.1 主要代码模块

- `src/factors/`：因子计算和预处理；
- `src/analysis/`：IC、衰减和相关性分析；
- `src/eot_drift.py`：EOT 漂移计算；
- `src/factor_lifecycle/`：资格筛选、生命周期和权重逻辑；
- `src/data/akshare_financials.py`：财务抓取和标准化；
- `src/data/coarse_industry.py`：粗粒度行业映射；
- `src/data/float_cap_proxy.py`：自由流通市值代理；
- `src/data/coverage_expansion.py`：扩展面板构建。

### 10.2 主要运行入口

- `scripts/run_eot_factor_drift_feasibility.py`：早期 EOT 可行性研究；
- `scripts/run_eot_factor_lifecycle.py`：正式 10 因子生命周期研究；
- `scripts/run_demo.py`：简历 Demo；
- `scripts/fetch_broad_fundamentals.py`：广覆盖财务和行业数据抓取；
- `scripts/build_coverage_expansion_panel.py`：扩展面板生成；
- `scripts/run_coverage_expansion_audit.py`：覆盖率和模式审计。

### 10.3 重要输出目录

- `reports/eot_factor_drift_feasibility/`：早期 EOT 可行性结果；
- `reports/eot_factor_lifecycle/`：正式生命周期、聚类、回测和稳健性结果；
- `reports/demo/`：简历 Demo 报告和图表；
- `reports/coverage_expansion/`：财务、行业、市值覆盖扩展审计；
- `data/processed/coverage_expansion/`：独立扩展面板。

## 11. 测试和可复现性

项目在 `quant` Conda 环境中完成核心运行和验证。

当前测试结果：

```text
49 passed, 0 failed
```

测试覆盖：

- 价量因子字段生成；
- 标准化和中性化；
- Rank IC；
- IC decay；
- 换手率和交易成本；
- 可交易性过滤；
- 财务因子字段；
- Rolling risk 因子；
- Demo 防未来函数逻辑；
- 生命周期聚类和状态逻辑；
- 市值面板和覆盖扩展相关逻辑。
- PIT 数据可用日期、行业和市值覆盖审计；
- 收益归因和绩效评估模块；
- 正式 EOT-map 两样本检验、bootstrap、FDR 与持续性规则；
- 月末信号和权重映射的防未来函数边界。

项目还修复了两个数值兼容问题：

1. 新版 NumPy 下 EOT 生命周期聚类相关矩阵可能为只读数组；
2. 常数序列计算相关系数时产生除零和 constant-input 警告。

修复后不改变正常数据下的算法逻辑，测试已无警告通过。

## 12. 项目最终结论

本项目已经完成了一个较完整的 A 股多因子研究原型，主要贡献不是提出一个未经验证的高收益策略，而是把以下研究环节串联起来：

```text
动态股票池
    ↓
价量因子构建
    ↓
单因子有效性评价
    ↓
EOT 联合表现分布漂移
    ↓
因子生命周期状态
    ↓
聚类去冗余与保守调权
    ↓
月度 walk-forward 回测
    ↓
交易成本、换手和市场状态分析
```

最稳妥的项目结论是：

> EOT 能够为因子状态变化和潜在失效提供结构化监控信号，但目前还不足以证明其本身具有稳定的收益预测或组合配置增量价值。

财务、行业和自由流通市值扩展已经显著提高了数据覆盖率，但由于历史行业 PIT 重构和财务修订版本仍不完整，扩展结果应当继续区分 Strict、Expanded 和 Proxy Sensitivity 三种研究模式。

## 13. 当前局限和下一步

主要局限：

- 财务修订历史不完整；
- 历史行业 PIT 面板尚未建立；
- 部分自由流通市值使用代理；
- 成交成本、冲击成本和买卖限制仍是简化模型；
- 研究股票池主要是沪深 300，外部泛化能力有限；
- EOT 近期窗口较短时可能对噪声敏感；
- 历史回测不能代表实时可交易性。

下一步优先级：

1. 获取带公告时间和修订版本的历史财务数据；
2. 构建年度或季度历史行业快照；
3. 验证动态成分股的公告和生效时间；
4. 增加严格涨跌停买卖约束、冲击成本和成交容量模型；
5. 扩展到其他股票池进行外部验证；
6. 先进行 out-of-sample 纸面监控，再评估是否允许 EOT 进入正式配置。

## 14. 简历表述

### 中文简历版本

基于动态沪深 300 构建 A 股多因子研究与生命周期监控框架，注册并评价 10 个价量因子，使用熵正则最优传输比较因子 Rank IC、多空收益和 downside 表现的历史与近期联合分布，结合 past-only 资格筛选、相关性聚类和保守漂移惩罚完成月度 walk-forward 回测，并系统评估交易成本、换手率、回撤和市场状态稳健性；同时扩展 AKShare 财务、粗粒度行业和自由流通市值代理覆盖，明确区分 Strict、Expanded 与 Proxy Sensitivity 研究模式。

### English resume version

Built an A-share multifactor research and lifecycle-monitoring framework on a dynamic CSI 300 universe. Registered and evaluated ten price-volume factors, used entropic optimal transport to compare historical and recent joint distributions of Rank IC, long-short returns and downside performance, and combined past-only eligibility, redundancy clustering and conservative drift penalties in monthly walk-forward backtests with transaction-cost and regime analysis. Extended financial, coarse-industry and free-float-cap coverage while separating Strict, Expanded and Proxy Sensitivity research modes.
