# 项目修改任务：用正式 EOT-map 两样本检验升级因子生命周期诊断

## 0. 项目目标

请基于当前量化项目已有的：

- 因子库；
- 周度因子表现面板；
- monthly / weekly EOT drift 原型；
- 因子生命周期诊断；
- ICIR 动态调权；
- 回测与交易成本分析；

将现有基于简单 EOT distance、barycentric-map distance 或 Sinkhorn distance 的漂移监控模块，升级为正式的：

# EOT-Map Two-Sample Testing for Factor Lifecycle Diagnostics

中文定位：

# 基于 EOT-map 两样本检验的因子生命周期诊断与实验性漂移感知调权

核心要求：

1. 不再把 Sinkhorn distance 或未校准的 EOT map distance 当作正式漂移结论；
2. 对每个因子构造历史表现样本和近期表现样本；
3. 使用共同参考分布上的经验 EOT maps；
4. 使用论文中的缩放统计量；
5. 使用中心化 weighted multiplier bootstrap 计算临界值和 \(p\)-value；
6. 对检验统计量进行坐标贡献分解；
7. 识别 Rank IC、多空收益、下行收益等哪个评价指标发生了主要变化；
8. 进一步区分变化是改善还是恶化；
9. 用正式检验结果替换原来仅依赖 `eot_drift_zscore` 的生命周期分类；
10. 将正式检验主要用于监控，调权仅作为保守的实验性扩展。

不要删除已有 distance-based 结果。旧结果保留为 baseline 和 robustness benchmark。

---

# 1. 先审计当前实现

请先搜索并理解当前项目中与以下内容有关的所有代码和结果：

- weekly factor performance；
- monthly factor performance；
- EOT drift；
- Sinkhorn distance；
- barycentric map；
- EOT reference points；
- factor lifecycle states；
- factor health score；
- factor weights；
- backtest；
- transaction cost；
- monitoring diagnostics。

重点寻找但不限于：

```text
src/eot_drift.py
src/factor_lifecycle/
data/processed/weekly_factor_performance.parquet
data/processed/weekly_eot_factor_drift_scores.parquet
data/processed/eot_factor_lifecycle/
reports/eot_factor_drift_feasibility/
reports/eot_factor_lifecycle/
```

如果实际路径不同，请通过项目搜索定位。

先输出：

```text
reports/eot_factor_lifecycle_test/current_eot_implementation_audit.md
```

报告必须回答：

1. 当前计算的是 Sinkhorn distance、EOT transport cost，还是 EOT map distance；
2. 当前是否使用共同 reference sample；
3. 当前统计量是否包含 \(nm/(n+m)\) 缩放；
4. 当前是否执行 bootstrap；
5. bootstrap 是否使用 centered map increments；
6. 当前是否输出正式 \(p\)-value；
7. 当前是否保留 map difference；
8. 当前是否支持 coordinate contribution；
9. 当前生命周期状态如何依赖 drift score；
10. 哪些模块可以复用；
11. 哪些模块必须修改；
12. 当前实现与正式 EOT-map test 的主要差异。

在完成审计前，不要大规模修改代码。

---

# 2. 建立因子表现指标注册表

不同因子使用相同的评价指标，但每个指标的“越大越好”或“越小越好”方向不同。

请新增：

```text
src/factor_lifecycle_test/metric_registry.py
```

每个表现指标至少记录：

```text
metric_name
description
better_direction
primary_or_auxiliary
included_in_eot
scaling_method
diagnostic_weight
notes
```

初始主指标建议为：

| metric_name         | 含义                        | better_direction | included_in_eot |
| ------------------- | --------------------------- | ---------------: | --------------: |
| `rank_ic`           | 周度 Rank IC                |               +1 |            True |
| `long_short_return` | 周度多空收益                |               +1 |            True |
| `downside_return`   | `min(long_short_return, 0)` |               +1 |            True |

可选扩展指标：

| metric_name             | 含义                             | better_direction | included_in_eot |
| ----------------------- | -------------------------------- | ---------------: | --------------: |
| `factor_turnover`       | 因子组合换手                     |               -1 |           False |
| `long_short_volatility` | 因子收益波动                     |               -1 |           False |
| `drawdown`              | 因子净值回撤，若用负值则越高越好 |               +1 |           False |
| `coverage_ratio`        | 因子覆盖率                       |               +1 |           False |
| `ic_breadth`            | 横截面预测广度                   |               +1 |           False |

第一版正式 EOT 检验默认只使用：

\[
Z_{j,t}
=
\left(
RankIC_{j,t},
LSReturn_{j,t},
DownsideReturn_{j,t}
\right).
\]

不要未经验证就将所有辅助指标放进高维 EOT 检验。

输出：

```text
reports/eot_factor_lifecycle_test/metric_registry.csv
```

---

# 3. 构造正式两样本问题

对每个因子 \(j\) 和每个周度监控时点 \(t\)，定义：

## Base sample

过去约 3 年的周度因子表现：

\[
X_{j,t}
=
\left\{
Z_{j,t-182},
\ldots,
Z_{j,t-27}
\right\}.
\]

默认：

```text
base_window = 156 weeks
```

## Recent sample

最近约 6 个月的周度因子表现：

\[
Y_{j,t}
=
\left\{
Z_{j,t-26},
\ldots,
Z_{j,t-1}
\right\}.
\]

默认：

```text
recent_window = 26 weeks
```

检验：

\[
H_0:
P_{j,t}=Q_{j,t}
\qquad
\text{vs}
\qquad
H_1:
P_{j,t}\neq Q_{j,t},
\]

其中：

- \(P_{j,t}\) 是 base window 中因子表现向量的分布；
- \(Q_{j,t}\) 是 recent window 中因子表现向量的分布。

约定：

```text
P = base distribution
Q = recent distribution
map_difference = T_recent - T_base
```

全项目必须保持这个符号方向一致。

---

# 4. Base-window robust scaling

不同评价指标尺度不同，必须在 EOT 检验前标准化。

但不得分别标准化 base 和 recent，否则会消除要检测的均值和尺度变化。

对每个因子、每个监控时点、每个指标 \(k\)，仅使用 base sample 计算：

\[
m_{j,t,k}
=
\operatorname{median}
\left(
X_{j,t,k}
\right),
\]

\[
s_{j,t,k}
=
1.4826
\operatorname{MAD}
\left(
X_{j,t,k}
\right).
\]

然后对 base 和 recent 使用同一个变换：

\[
\widetilde X_{i,k}
=
\frac{X_{i,k}-m_k}{s_k+\delta},
\]

\[
\widetilde Y_{i,k}
=
\frac{Y_{i,k}-m_k}{s_k+\delta}.
\]

要求：

1. scaling statistics 只能来自 base window；
2. 不得使用全样本统计；
3. 不得分别对 recent 重新居中；
4. 若 MAD 接近 0，使用标准差或最小尺度 fallback；
5. 记录每个指标的 center、scale 和 fallback 状态。

输出诊断字段：

```text
metric_center
metric_scale
scaling_fallback
near_zero_scale_warning
```

---

# 5. 实现共同参考 EOT maps

请新增主模块：

```text
src/factor_lifecycle_test/eot_map_two_sample.py
```

核心函数建议包括：

```python
def sample_uniform_unit_ball(
    n_reference: int,
    dimension: int,
    random_state: int,
):
    """Sample common reference points from the uniform law on the unit ball."""
    pass


def compute_eot_barycentric_map(
    reference_points,
    target_sample,
    epsilon,
    target_weights=None,
    method="sinkhorn_log",
    num_iter_max=2000,
    stop_thr=1e-9,
):
    """Compute the EOT barycentric map from the common reference sample."""
    pass


def compute_eot_map_test_statistic(
    map_base,
    map_recent,
    n_base,
    n_recent,
):
    """Compute the scaled squared L2 map discrepancy."""
    pass


def run_eot_map_two_sample_test(
    X_base,
    X_recent,
    n_reference=100,
    epsilon_scale=0.2,
    n_bootstrap=300,
    alpha=0.05,
    random_state=42,
    bootstrap_method="iid_multiplier",
):
    """Run the complete common-reference EOT-map two-sample test."""
    pass
```

## Common reference points

若表现向量维度为 \(d\)，生成：

\[
U_1,\ldots,U_N
\overset{i.i.d.}{\sim}
U_d,
\]

其中 \(U_d\) 是 \(d\) 维单位球上的均匀分布。

要求：

- base 和 recent 必须使用完全相同的 reference points；
- bootstrap repetitions 也保持相同 reference points；
- reference points 与目标样本独立；
- 固定 random seed；
- 保存 reference seed 和 reference sample size。

默认：

```text
n_reference = 100
```

稳健性版本：

```text
n_reference in [50, 100, 200]
```

主结果不要通过全样本挑选最优 `n_reference`。

---

# 6. Epsilon 规则

正式检验使用 pooled standardized samples：

\[
\widetilde Z
=
\widetilde X
\cup
\widetilde Y.
\]

计算非零 pairwise squared distances 的中位数：

\[
M
=
\operatorname{median}
\left\{
\|z_a-z_b\|^2:
a\neq b
\right\}.
\]

设置：

\[
\varepsilon
=
c_\varepsilon M.
\]

默认：

```text
epsilon_scale = 0.2
```

稳健性检查：

```text
epsilon_scale in [0.1, 0.2, 0.5]
```

要求：

1. 主结果固定使用 `0.2`；
2. 不得根据最终回测收益选择 epsilon；
3. 若 epsilon 过小导致 Sinkhorn 不收敛，记录 warning；
4. 必要时可 fallback 到更稳定的 `sinkhorn_log`；
5. 保存 epsilon、iterations、residual 和 convergence status。

---

# 7. 正式 EOT-map 两样本统计量

设：

- \(n\) 为 base sample 数量；
- \(m\) 为 recent sample 数量；
- \(N\) 为 reference points 数量；
- \(\widehat T_{\varepsilon,P}\) 为 base EOT map；
- \(\widehat T_{\varepsilon,Q}\) 为 recent EOT map。

定义 map difference：

\[
\widehat D_\varepsilon(U_\ell)
=
\widehat T_{\varepsilon,Q}(U_\ell)
-
\widehat T_{\varepsilon,P}(U_\ell).
\]

正式统计量：

\[
\mathcal T_{n,m}
=
\frac{nm}{n+m}
\frac{1}{N}
\sum_{\ell=1}^{N}
\left\|
\widehat D_\varepsilon(U_\ell)
\right\|^2.
\]

必须输出：

```text
test_statistic
unscaled_map_distance
effective_sample_size
n_base
n_recent
n_reference
epsilon
map_base
map_recent
map_difference
```

其中：

\[
\text{unscaled map distance}
=
\frac1N
\sum_{\ell=1}^{N}
\|\widehat D_\varepsilon(U_\ell)\|^2.
\]

正式检验结论必须基于 `test_statistic` 和 bootstrap calibration，而不是仅基于未缩放距离。

---

# 8. 实现论文中的 centered weighted multiplier bootstrap

主函数建议：

```python
def weighted_eot_map_bootstrap(
    reference_points,
    X_base,
    X_recent,
    map_base,
    map_recent,
    epsilon,
    n_bootstrap,
    random_state,
    bootstrap_method="iid_multiplier",
    block_length=None,
):
    pass
```

## IID multiplier 版本

对每个 bootstrap repetition \(b\)：

\[
\xi_1^{(b)},\ldots,\xi_n^{(b)}
\overset{i.i.d.}{\sim}
Exp(1),
\]

\[
\zeta_1^{(b)},\ldots,\zeta_m^{(b)}
\overset{i.i.d.}{\sim}
Exp(1).
\]

归一化：

\[
W_i^{P,*}
=
\frac{\xi_i}{\sum_r \xi_r},
\qquad
W_j^{Q,*}
=
\frac{\zeta_j}{\sum_s \zeta_s}.
\]

构造 weighted empirical targets，并计算：

\[
\widehat T_{\varepsilon,P}^{*},
\qquad
\widehat T_{\varepsilon,Q}^{*}.
\]

必须使用 centered bootstrap map process：

\[
\mathbb Z_{n,m}^{*}
=
\sqrt{\frac{nm}{n+m}}
\left[
\left(
\widehat T_{\varepsilon,P}^{*}
-
\widehat T_{\varepsilon,P}
\right)
-
\left(
\widehat T_{\varepsilon,Q}^{*}
-
\widehat T_{\varepsilon,Q}
\right)
\right].
\]

bootstrap statistic：

\[
\mathcal T_{n,m}^{*}
=
\frac1N
\sum_{\ell=1}^{N}
\left\|
\mathbb Z_{n,m}^{*}(U_\ell)
\right\|^2.
\]

不得错误地直接计算：

\[
\|\widehat T_P^*-\widehat T_Q^*\|^2
\]

作为 null bootstrap statistic。

计算：

\[
p
=
\frac{
1+
\sum_{b=1}^{B}
\mathbf 1
\left\{
\mathcal T_{n,m}^{*,b}
\geq
\mathcal T_{n,m}
\right\}
}{
B+1
}.
\]

并输出：

```text
bootstrap_critical_value
p_value
reject_raw
bootstrap_statistics
bootstrap_method
n_bootstrap
```

默认：

```text
n_bootstrap = 300
alpha = 0.05
```

最终正式结果建议：

```text
n_bootstrap = 500
```

---

# 9. 时间序列依赖：实现 block / dependent multiplier 扩展

周度 Rank IC 和多空收益不是严格 iid，可能存在：

- 序列相关；
- 波动聚集；
- 重叠收益；
- 市场状态持续性。

因此需要明确区分：

## Paper-faithful benchmark

```text
bootstrap_method = iid_multiplier
```

该版本严格复现论文算法，但在周度时间序列应用中仅作为 benchmark。

## Main time-series diagnostic

请实现至少一种依赖稳健 bootstrap：

```text
bootstrap_method = block_multiplier
```

可以选择以下一种合理方案：

### 方案 A：moving block multiplier

将连续周组成 block，对同一 block 使用共同 multiplier。

### 方案 B：stationary block multiplier

使用随机长度 block，平均 block length 预先设定。

### 方案 C：dependent Gaussian multiplier

构造具有 kernel correlation 的 multiplier sequence，再平移并转换为合适权重。

实现时优先选择工程上稳定、可解释的方案。

预设 block length：

```text
block_length in [4, 8, 13]
```

主结果默认：

```text
block_length = 8 weeks
```

要求：

1. 不得声称论文中的 iid bootstrap 理论自动覆盖时间序列；
2. block bootstrap 必须明确标记为应用扩展；
3. 同时报告 iid 和 block 版本；
4. 主 dashboard 优先使用 block bootstrap；
5. 若 block 版本尚未得到理论证明，报告中使用“dependence-robust exploratory calibration”措辞；
6. 对 block length 做有限稳健性分析；
7. 不通过回测收益选择 block length。

输出：

```text
p_value_iid
p_value_block
reject_iid
reject_block
block_length
bootstrap_dependence_warning
```

---

# 10. 坐标贡献分解

若 EOT 输入维度为 \(d\)，对每个坐标 \(k\) 定义：

\[
\mathcal T_{n,m}^{(k)}
=
\frac{nm}{n+m}
\frac1N
\sum_{\ell=1}^{N}
\widehat D_{\varepsilon,k}(U_\ell)^2.
\]

总统计量满足：

\[
\mathcal T_{n,m}
=
\sum_{k=1}^{d}
\mathcal T_{n,m}^{(k)}.
\]

坐标贡献率：

\[
r_k
=
\frac{
\mathcal T_{n,m}^{(k)}
}{
\mathcal T_{n,m}
}.
\]

必须检查数值上：

```text
sum(coordinate_statistics) ≈ total_test_statistic
sum(coordinate_contribution_ratios) ≈ 1
```

输出长表：

```text
date
factor_name
metric_name
coordinate_statistic
coordinate_contribution_ratio
coordinate_rank
```

请新增：

```python
def decompose_map_statistic_by_coordinate(
    map_difference,
    n_base,
    n_recent,
    metric_names,
):
    pass
```

重要解释：

- contribution ratio 说明哪个指标对整体分布变化贡献最大；
- contribution ratio 本身不说明变化方向；
- 不得将“贡献最大”直接表述为“恶化最严重”。

---

# 11. Signed improvement / deterioration diagnostics

因为平方差会丢失方向，请增加有符号诊断。

约定：

\[
\widehat D_\varepsilon
=
\widehat T_{\varepsilon,Q}
-
\widehat T_{\varepsilon,P}
=
T_{\text{recent}}
-
T_{\text{base}}.
\]

对坐标 \(k\)：

\[
\overline D_k
=
\frac1N
\sum_{\ell=1}^{N}
\widehat D_{\varepsilon,k}(U_\ell).
\]

从 `metric_registry` 读取：

\[
s_k=
\begin{cases}
+1,& \text{指标越高越好},\\
-1,& \text{指标越低越好}.
\end{cases}
\]

定义 signed improvement：

\[
I_k
=
s_k \overline D_k.
\]

解释：

```text
I_k > 0  => recent relative to base shows improvement
I_k < 0  => recent relative to base shows deterioration
```

定义 map-level deterioration score：

\[
Bad_k
=
\frac1N
\sum_{\ell=1}^{N}
\left[
-s_k
\widehat D_{\varepsilon,k}(U_\ell)
\right]_+^2.
\]

定义 deterioration share：

\[
BadShare_k
=
\frac{
Bad_k
}{
\sum_{r=1}^{d}Bad_r+\delta
}.
\]

输出：

```text
signed_map_displacement
signed_improvement_score
deterioration_score
deterioration_share
improvement_or_deterioration
dominant_change_metric
dominant_deterioration_metric
```

解释时必须同时结合：

1. global EOT test 是否拒绝；
2. coordinate contribution；
3. signed improvement；
4. deterioration share。

示例：

```text
Global EOT-map test rejects homogeneity.
The largest coordinate contribution comes from downside_return.
The signed displacement is negative after direction adjustment,
indicating that the change is primarily a deterioration in downside behavior.
```

---

# 12. 可选的坐标级显著性分析

在 global test 拒绝后，可对单个指标做坐标级 follow-up。

可以选择：

1. 一维 EOT-map test；
2. 一维两样本 permutation test；
3. block bootstrap mean / distribution test；
4. coordinate bootstrap contribution interval。

坐标级检验属于 post-hoc analysis，必须做多重比较修正。

至少实现：

```text
Holm correction
BH-FDR correction
```

输出：

```text
coordinate_raw_p_value
coordinate_holm_p_value
coordinate_bh_q_value
coordinate_reject
```

原则：

- global multivariate EOT test 是主检验；
- coordinate test 是解释性 follow-up；
- 不应因单个坐标不显著就否定联合分布变化；
- 不得在 global test 不拒绝时大规模寻找局部显著坐标。

---

# 13. 多因子、多日期检验的 FDR 控制

每个监控日期会同时测试多个因子，因此需要控制横截面多重检验。

在每个日期 \(t\)，对所有可检验因子的 global \(p\)-value 做：

```text
Benjamini-Hochberg FDR
```

输出：

```text
p_value_raw
q_value_cross_factor
reject_raw
reject_fdr
```

默认：

```text
alpha = 0.05
fdr_level = 0.10
```

生命周期 warning 优先使用：

```text
reject_fdr
```

但同时保留 raw \(p\)-value。

由于滚动窗口高度重叠，连续日期的检验也存在依赖。请增加 persistence rule：

```text
persistent_warning = reject_fdr in at least 2 of the last 3 monitoring weeks
```

同时输出：

```text
single_week_warning
persistent_warning
warning_start_date
warning_duration
```

---

# 14. 输出正式 EOT-map test panel

请生成：

```text
data/processed/eot_factor_lifecycle_test/eot_map_test_panel.parquet
```

至少包含：

```text
date
factor_name
factor_family
n_base
n_recent
n_reference
epsilon
epsilon_scale
test_statistic
unscaled_map_distance
bootstrap_critical_value_iid
bootstrap_critical_value_block
p_value_iid
p_value_block
q_value_cross_factor
reject_iid
reject_block
reject_fdr
persistent_warning
sinkhorn_status
bootstrap_status
block_length
dominant_change_metric
dominant_deterioration_metric
total_deterioration_score
notes
```

坐标级结果另存：

```text
data/processed/eot_factor_lifecycle_test/eot_map_coordinate_diagnostics.parquet
```

字段包括：

```text
date
factor_name
metric_name
coordinate_statistic
coordinate_contribution_ratio
signed_map_displacement
signed_improvement_score
deterioration_score
deterioration_share
coordinate_raw_p_value
coordinate_holm_p_value
coordinate_bh_q_value
coordinate_reject
```

---

# 15. 修改因子生命周期状态

不要再仅根据 `eot_drift_zscore` 划分状态。

生命周期状态必须综合：

```text
historical_quality
recent_quality
quality_trend
global EOT-map test
FDR-adjusted rejection
persistent warning
coordinate deterioration
dominant deterioration metric
```

建议状态规则如下。

## Healthy

满足：

- global EOT-map test 不拒绝；
- historical quality 为正或可接受；
- recent quality 没有明显恶化；
- 没有 persistent warning。

## Watch

满足之一：

- global test 拒绝，但方向混合；
- 存在显著分布变化，但主要指标没有明确恶化；
- 单周拒绝但尚未形成 persistent warning；
- 某个次要指标恶化。

## Decaying

满足：

- global test 拒绝或 FDR 后拒绝；
- persistent warning 为 True；
- Rank IC、long-short return 或 downside 的 signed diagnostic 显示恶化；
- recent quality 低于 historical quality。

## Recovering

满足：

- global test 拒绝；
- 主要变化方向是改善；
- recent quality 高于 historical quality；
- drift warning 从高位回落或 deterioration score 下降。

## Dormant

满足：

- historical 和 recent quality 均较弱；
- global test 可能不拒绝；
- 没有恢复证据；
- 当前不建议高权重配置。

请将原生命周期面板升级为：

```text
data/processed/eot_factor_lifecycle_test/factor_lifecycle_states_test_based.parquet
```

字段包括：

```text
date
factor_name
historical_icir
recent_icir
quality_trend
test_statistic
p_value
q_value
reject_fdr
persistent_warning
dominant_change_metric
dominant_deterioration_metric
total_deterioration_score
lifecycle_state
lifecycle_reason
```

保留旧 `drift_zscore` 状态作为 baseline，不要覆盖。

---

# 16. 构造正式监控 dashboard

请生成：

```text
data/processed/eot_factor_lifecycle_test/factor_test_dashboard.parquet
```

每个因子、每个日期至少包括：

```text
date
factor_name
factor_family
eligibility_status
lifecycle_state
historical_icir
recent_icir
test_statistic
p_value_iid
p_value_block
q_value_cross_factor
reject_fdr
persistent_warning
dominant_change_metric
dominant_change_contribution
dominant_deterioration_metric
dominant_deterioration_share
signed_improvement_summary
warning_level
warning_reason
current_portfolio_weight
```

建议 warning level：

```text
green
yellow
orange
red
```

规则示例：

- Green：不拒绝，质量稳定；
- Yellow：单次拒绝或轻度恶化；
- Orange：persistent warning，主要指标恶化；
- Red：persistent warning + 多个核心指标恶化 + recent ICIR 为负。

---

# 17. 实验性 drift-aware weighting 修改

EOT-map test 主要用于监控，调权只能作为实验性扩展。

不要直接使用未校准的 `eot_drift_zscore`。

构造 significance score：

\[
S_{j,t}
=
\left[
1-
\frac{q_{j,t}}{\alpha_q}
\right]_+,
\]

其中：

```text
alpha_q = 0.10
```

若：

```text
q_value >= alpha_q
```

则：

```text
S = 0
```

构造 deterioration severity：

\[
B_{j,t}
=
\sum_{k\in\mathcal K}
\omega_k
BadShare_{j,t,k},
\]

其中核心指标集合默认：

```text
rank_ic
long_short_return
downside_return
```

主惩罚：

\[
Penalty_{j,t}
=
\operatorname{clip}
\left(
1-\gamma S_{j,t}B_{j,t},
0.5,
1.0
\right).
\]

默认：

```text
gamma = 0.5
```

保守版本：

```text
gamma in [0.25, 0.5, 0.75]
```

不得通过全样本收益选择 gamma。

最终权重：

\[
RawWeight_{j,t}
=
\max(ICIR_{j,t},0)
\times
Penalty_{j,t}.
\]

可选 lifecycle filter：

```text
Healthy    => full eligibility
Watch      => penalty only
Recovering => conservative re-entry
Decaying   => capped weight or excluded
Dormant    => excluded
```

主方案不建议因一次检验拒绝就完全剔除因子。

输出：

```text
data/processed/eot_factor_lifecycle_test/factor_weights_test_based.parquet
```

---

# 18. 回测对比

必须比较以下策略：

```text
1. Equal eligible factors
2. ICIR weighting
3. Old distance-based EOT drift weighting
4. Formal EOT-map test significance penalty
5. Formal EOT-map test + signed deterioration penalty
6. Test-based lifecycle filtering
7. Test-based lifecycle filtering + conservative weighting
```

必须区分：

- 改善来自 EOT distance；
- 改善来自统计显著性；
- 改善来自坐标方向诊断；
- 改善来自生命周期过滤。

正式回测要求：

1. walk-forward；
2. 只能使用调仓日前已知的 \(p\)-value 和 lifecycle state；
3. weekly monitoring 映射到 monthly rebalance；
4. 禁止未来信息；
5. 加入 0、5、10、20 bps 交易成本；
6. 报告 stock turnover 和 factor weight turnover；
7. 不使用全样本选择最优参数。

输出：

```text
data/processed/eot_factor_lifecycle_test/backtest_nav_test_based.parquet
reports/eot_factor_lifecycle_test/backtest_summary_test_based.csv
reports/eot_factor_lifecycle_test/transaction_cost_sensitivity_test_based.csv
```

---

# 19. 验证正式检验实现

必须增加 synthetic validation。

## 19.1 IID null size test

模拟：

```text
P = Q
```

至少使用：

- Gaussian；
- Student-t；
- Gaussian mixture。

检查 iid multiplier bootstrap 在有限样本下的拒绝率是否接近 nominal level。

## 19.2 Alternative power test

至少包括：

- mean shift；
- scale change；
- correlation change；
- one-coordinate deterioration；
- downside coordinate deterioration。

## 19.3 Coordinate diagnostic validation

构造只改变某一个指标坐标的 synthetic alternative，检查：

```text
dominant coordinate contribution
dominant deterioration metric
signed direction
```

是否正确识别。

## 19.4 Time-series dependence test

生成 AR(1) 或 block-dependent 表现序列，比较：

```text
iid multiplier
block multiplier
```

在 dependent null 下的 size。

输出：

```text
reports/eot_factor_lifecycle_test/synthetic_validation_summary.csv
reports/eot_factor_lifecycle_test/bootstrap_calibration_report.md
```

如果 block bootstrap 表现仍不稳定，必须诚实说明。

---

# 20. 单元测试

请增加测试，至少覆盖：

```text
reference points lie in unit ball
base and recent share identical reference points
target weights sum to one
barycentric map output shape
test statistic scaling
bootstrap centering
coordinate statistics sum to total
coordinate contribution ratios sum to one
base-only scaling
metric direction handling
signed deterioration direction
FDR correction
persistence rule
block multiplier structure
no look-ahead
weekly-to-monthly mapping
weight normalization
```

特别测试：

```text
map_difference = recent - base
```

不能在不同模块中反向。

输出：

```text
reports/eot_factor_lifecycle_test/test_report.md
```

---

# 21. 计算性能优化

正式 bootstrap 计算量较大，请进行合理优化：

1. 固定并复用 reference points；
2. 缓存 base / recent standardized samples；
3. 缓存 cost matrices；
4. 使用 `sinkhorn_log`；
5. 对因子或日期并行，而不是在单次 Sinkhorn 内盲目并行；
6. pilot 使用 `B=100`；
7. final 使用 `B=300` 或 `B=500`；
8. 失败的单次 bootstrap 不得导致整个项目崩溃；
9. 保存 convergence diagnostics；
10. 不得因速度原因退回只算 Sinkhorn distance。

输出：

```text
reports/eot_factor_lifecycle_test/computational_diagnostics.csv
```

字段包括：

```text
date
factor_name
n_reference
n_bootstrap
bootstrap_method
runtime_seconds
sinkhorn_failures
bootstrap_failures
mean_iterations
max_iterations
notes
```

---

# 22. 图表

生成：

```text
reports/eot_factor_lifecycle_test/figures/
```

至少包括：

1. 各因子的 EOT-map test statistic 时间序列；
2. raw \(p\)-value 和 FDR \(q\)-value 时间序列；
3. lifecycle state timeline；
4. coordinate contribution heatmap；
5. deterioration share heatmap；
6. 每个因子的 dominant deterioration metric 时间线；
7. iid vs block bootstrap \(p\)-value 比较；
8. old distance-based drift vs formal test result；
9. 因子 warning dashboard；
10. 回测净值；
11. 回撤；
12. 交易成本敏感性；
13. 某些典型因子的 EOT map difference 可视化；
14. synthetic one-coordinate deterioration diagnostic。

对于 \(d=3\) 或更高维，不强求完整向量场可视化，可以使用：

- coordinate contribution bar plot；
- reference-point magnitude distribution；
- pairwise projected vector fields；
- PCA projection，仅作为辅助可视化。

---

# 23. 最终研究报告

输出：

```text
reports/eot_factor_lifecycle_test/eot_map_factor_lifecycle_final_report.md
```

报告结构如下。

## 1. Executive Summary

明确说明：

- 是否成功从 distance-based drift 升级为 formal EOT-map test；
- 是否成功生成 bootstrap \(p\)-value；
- 是否成功生成 coordinate diagnostics；
- 哪些评价指标最常导致因子状态变化；
- EOT-map test 主要价值是 monitoring 还是 allocation；
- block bootstrap 是否稳定；
- 项目是否适合用于求职展示。

## 2. Difference from the Previous Version

对比：

```text
Sinkhorn distance
unscaled EOT map distance
formal scaled EOT-map statistic
bootstrap-calibrated EOT-map test
```

说明为什么正式检验更适合 lifecycle diagnostics。

## 3. Method

完整写出：

\[
Z_{j,t}
\]

base / recent windows、base-only scaling、common reference maps、test statistic、bootstrap 和 coordinate decomposition。

## 4. Bootstrap Calibration

分别说明：

- iid multiplier；
- block multiplier；
- 时间序列依赖限制；
- synthetic size results。

不得声称 block bootstrap 具有论文中尚未证明的理论有效性。

## 5. Global Test Results

说明：

- 哪些因子经常拒绝；
- 哪些因子状态较稳定；
- 是否存在明显风格周期。

## 6. Coordinate Diagnostics

说明：

- Rank IC；
- long-short return；
- downside return；

各自对拒绝的贡献。

明确区分：

```text
largest change contribution
largest deterioration contribution
```

## 7. Lifecycle States

展示 Healthy、Watch、Decaying、Dormant、Recovering 的规则和实例。

## 8. Monitoring Value

判断 EOT-map test 是否能有效识别：

- 分布结构变化；
- 指标恶化；
- 因子生命周期切换。

## 9. Allocation Value

比较正式 test-based weighting 与旧 distance-based weighting。

重点分析：

- Sharpe；
- max drawdown；
- Calmar；
- turnover；
- transaction costs；
- 参数稳定性。

## 10. Limitations

必须包括：

1. 周度因子表现存在时间依赖；
2. 论文 iid bootstrap 理论不能直接覆盖时间序列；
3. block multiplier 属于应用扩展；
4. rolling windows 高度重叠；
5. 多因子、多日期存在多重检验问题；
6. coordinate contribution 不等于因果归因；
7. 因子表现指标本身存在估计噪声；
8. 当前结果不能表述为实盘策略保证；
9. epsilon 和 reference sample 仍需有限稳健性检查；
10. 财务因子仍需 point-in-time 安全。

## 11. Final Project Positioning

优先考虑：

```text
EOT-Map Tests for A-Share Factor Lifecycle Diagnostics
```

中文：

```text
基于 EOT-map 两样本检验的 A 股因子生命周期诊断
```

实验性扩展：

```text
Experimental Drift-Aware Multifactor Weighting
```

不要把调权放在项目标题最核心的位置，除非结果非常稳健。

## 12. Resume Wording

输出：

- 中文简历三条；
- 英文简历三条；
- 30 秒介绍；
- 2 分钟介绍。

必须强调：

- formal EOT-map two-sample test；
- common reference maps；
- bootstrap calibration；
- coordinate-wise diagnostics；
- factor lifecycle monitoring；
- experimental weighting extension。

不得将结果描述为已验证可实盘交易策略。

---

# 24. README

新增：

```text
reports/eot_factor_lifecycle_test/README.md
```

包含：

```text
project motivation
why not only Sinkhorn distance
factor performance vectors
base/recent windows
base-only scaling
common-reference EOT maps
test statistic
bootstrap
time-series extension
coordinate diagnostics
lifecycle states
experimental weighting
main findings
limitations
reproduction commands
```

---

# 25. 最终交付文件

至少检查以下文件是否存在：

```text
reports/eot_factor_lifecycle_test/current_eot_implementation_audit.md
reports/eot_factor_lifecycle_test/metric_registry.csv

src/factor_lifecycle_test/metric_registry.py
src/factor_lifecycle_test/eot_map_two_sample.py

data/processed/eot_factor_lifecycle_test/eot_map_test_panel.parquet
data/processed/eot_factor_lifecycle_test/eot_map_coordinate_diagnostics.parquet
data/processed/eot_factor_lifecycle_test/factor_lifecycle_states_test_based.parquet
data/processed/eot_factor_lifecycle_test/factor_test_dashboard.parquet
data/processed/eot_factor_lifecycle_test/factor_weights_test_based.parquet
data/processed/eot_factor_lifecycle_test/backtest_nav_test_based.parquet

reports/eot_factor_lifecycle_test/backtest_summary_test_based.csv
reports/eot_factor_lifecycle_test/transaction_cost_sensitivity_test_based.csv
reports/eot_factor_lifecycle_test/synthetic_validation_summary.csv
reports/eot_factor_lifecycle_test/bootstrap_calibration_report.md
reports/eot_factor_lifecycle_test/computational_diagnostics.csv
reports/eot_factor_lifecycle_test/test_report.md
reports/eot_factor_lifecycle_test/figures/
reports/eot_factor_lifecycle_test/eot_map_factor_lifecycle_final_report.md
reports/eot_factor_lifecycle_test/README.md
```

如果部分文件无法生成，必须在最终报告中说明，不得伪造。

---

# 26. 实施顺序

请按以下阶段执行。

## Phase 1：审计与设计

- 检查旧实现；
- 输出差异审计；
- 建立 metric registry；
- 确定符号和数据方向。

## Phase 2：正式 EOT-map test

- common reference；
- barycentric maps；
- scaled statistic；
- iid centered bootstrap；
- \(p\)-value。

## Phase 3：坐标诊断

- coordinate contribution；
- signed improvement；
- deterioration share；
- coordinate follow-up。

## Phase 4：时间依赖扩展

- block multiplier；
- iid vs block calibration；
- synthetic validation。

## Phase 5：生命周期状态

- FDR；
- persistence；
- test-based lifecycle states；
- dashboard。

## Phase 6：实验性调权

- significance penalty；
- deterioration penalty；
- walk-forward backtest；
- transaction cost。

## Phase 7：最终报告与测试

- 单元测试；
- 图表；
- README；
- final report。

不要在 Phase 1 未完成时直接覆盖现有生命周期代码。

---

# 27. 最终回复要求

完成后请简洁汇报：

1. 原项目实际使用的是什么距离或统计量；
2. 哪些模块已被升级为正式 EOT-map test；
3. 是否成功实现 centered multiplier bootstrap；
4. 是否实现 block multiplier；
5. 正式检验生成了多少个因子-日期结果；
6. 哪些因子最常拒绝同质性；
7. 哪些评价指标最常成为主要变化来源；
8. 哪些评价指标最常表现恶化；
9. 生命周期状态是否比旧 drift-score 版本更可解释；
10. test-based weighting 是否优于旧 distance-based weighting；
11. 交易成本后是否仍有增量价值；
12. 当前最重要的理论和数据限制；
13. 最终推荐的项目标题；
14. 最重要的输出文件路径。

不要只回复 `done`。