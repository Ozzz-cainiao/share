# 投资策略研究仓库（可长期维护）

这个仓库现在有两套入口：

- `main.py`：一键生成你当前文章型回测结果（含图表/文章）
- `investlab`：可复用框架入口，方便后续持续加策略、加回测

## 1. 环境准备

```bash
uv sync
```

Python 版本与依赖由 `pyproject.toml` + `uv.lock` 固定。

## 2. 旧入口（保持兼容）

```bash
uv run python main.py
```

用途：快速生成当前这套“定投 vs 等低点”完整产物。

## 3. 新框架入口（推荐后续都用这个）

### 3.1 运行方式

```bash
# 方式1：直接用框架入口
uv run python -m investlab.cli

# 方式2：沿用 main.py，但切到框架模式
uv run python main.py --framework
```

### 3.2 常用参数

```bash
uv run python -m investlab.cli \
  --start 2005-01-01 \
  --end 2026-03-09 \
  --assets H00300,H00906,H00905,SPY,QQQ \
  --drawdown-rules 10:6,20:12 \
  --monthly 1.0 \
  --cash-rate 0.02 \
  --fee-rate 0.0003 \
  --output-dir output/framework
```

### 3.3 框架输出

- `output/framework/summary_long.csv`：长表（每个标的 × 每个策略）
- `output/framework/summary_xirr_wide.csv`：XIRR 宽表
- `output/framework/summary_xirr_excess_wide.csv`：相对定投超额宽表
- `output/framework/price_series/*.csv`：回测中使用的价格序列

## 4. 目录说明（后续维护重点）

- `investlab/data.py`：数据源与标的选择
- `investlab/strategies.py`：策略定义（定投、回撤择时）
- `investlab/engine.py`：统一回测引擎
- `investlab/metrics.py`：指标计算
- `investlab/cli.py`：命令行入口与结果导出
- `investlab/strategy_template.py`：新增策略模板

## 5. 以后如何“加策略”

按这 4 步走：

1. 复制 `investlab/strategy_template.py` 到 `investlab/strategies.py` 或新文件中。  
2. 新策略实现统一接口：
   - `name`
   - `display_name`
   - `reset()`
   - `should_buy(ctx)`
3. 在 `investlab/cli.py` 里把策略加入运行列表。  
4. 跑命令验证：
   - `uv run python -m investlab.cli --drawdown-rules ...`

## 6. 以后如何“加回测场景”

推荐做法：

1. 在 `investlab/cli.py` 新增参数（例如不同手续费、现金收益、调仓频率）。
2. 通过 `--output-dir` 区分不同实验，避免结果互相覆盖。
3. 用 `summary_long.csv` 作为统一对比底表。

## 7. 维护提醒（请固定执行）

- 提交代码前先跑至少一遍：
  - `uv run python -m investlab.cli --start 2018-01-01 --end 2026-03-09`
- 不把 `output/` 生成物提交到 git（已在 `.gitignore`）。
- 每次策略改动都在 commit message 里写清楚：参数、假设、影响范围。

## 8. 建议分支流程

```bash
git checkout -b feat/<strategy-or-backtest-name>
# 开发 + 回测
git add .
git commit -m "feat(strategy): add xxx"
git push -u origin feat/<strategy-or-backtest-name>
```

这样你后面持续加“新策略/新回测”时，仓库会一直保持可维护。
