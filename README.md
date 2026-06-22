# 投资策略研究仓库（可长期维护）

这个仓库统一入口为 `investlab` 包，通过 `python -m investlab.cli` 运行所有回测与发布流程。旧的顶层脚本（`main.py`、`rolling_returns.py`、`dca_comparison.py`、`build_site.py`）已删除，所有逻辑已迁入 `investlab/` 包。

## 1. 环境准备

```bash
uv sync
```

Python 版本与依赖由 `pyproject.toml` + `uv.lock` 固定。

## 2. 统一命令入口

```bash
uv run python -m investlab.cli --help
uv run python -m investlab.cli scenarios list
```

所有回测、滚动收益、定投对比、站点构建都通过 `python -m investlab.cli` 子命令运行。旧顶层脚本直接运行会打印弃用提示并退出。

### 2.1 框架回测

```bash
uv run python -m investlab.cli run framework \
  --start 2005-01-01 \
  --end 2026-03-09 \
  --assets H00300,H00906,H00905,SPY,QQQ \
  --drawdown-rules 10:6,20:12 \
  --monthly 1.0 \
  --cash-rate 0.02 \
  --fee-rate 0.0003 \
  --output-dir output/framework
```

### 2.2 框架输出

- `output/framework/summary_long.csv`：长表（每个标的 × 每个策略）
- `output/framework/summary_xirr_wide.csv`：XIRR 宽表
- `output/framework/summary_xirr_excess_wide.csv`：相对定投超额宽表
- `output/framework/price_series/*.csv`：回测中使用的价格序列

## 4. 目录说明（后续维护重点）

- `investlab/core/`：资产注册表（`asset_registry.py`）与价格加载（`price_loading.py`）等共享计算基元
- `investlab/scenarios/`：场景注册表（`registry.py`）与各结果家族模块（`framework_scenario.py`、`rolling_returns_scenario.py`、`dca_comparison_scenario.py`）及共享矩阵工具（`annual_matrix.py`、`dca_matrix.py`）
- `investlab/publish/`：报告注册表（`report_registry.py`）、站点构建（`site_builder.py`）与长图导出契约（`export_contract.py`）
- `investlab/data.py`：数据源与标的选择
- `investlab/strategies.py`：策略定义（定投、回撤择时）
- `investlab/engine.py`：统一回测引擎
- `investlab/metrics.py`：指标计算
- `investlab/cli.py`：统一命令入口（scenarios / run / publish）
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

## 6. 以后如何“加回测场景（result family）”

新结果家族通过 `investlab/scenarios/` 的场景注册表接入，无需改 `investlab/cli.py` 的 dispatch：

1. 在 `investlab/scenarios/` 新建 `<name>_scenario.py`，定义 `add_arguments(parser)` 和 `run(args)`，复用 `investlab.scenarios.annual_matrix` / `dca_matrix` 等共享矩阵工具。
2. 用 `ScenarioEntry(name=..., description=..., add_arguments=..., run=...)` 构造条目，并调用 `SCENARIO_REGISTRY.register(entry)`。
3. 在 `investlab/scenarios/__init__.py` 导入该模块以触发注册。
4. 验证：`uv run python -m investlab.cli run <name> --help` 自动出现新子命令；`uv run python -m investlab.cli scenarios list` 仍正常。

CLI 的 `run <scenario>` 子命令由 `SCENARIO_REGISTRY.entries()` 动态生成，新家族是增量工作，不需要克隆顶层脚本。

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

## 9. 滚动年化收益率矩阵

`rolling-returns` 场景使用 AkShare 获取中证指数日线，或读取美股 ETF 分红再投资年度总收益，并生成滚动年化收益率矩阵。默认标的是中证全指全收益指数 `H00985`。

未传入 `--start-year` 时，各标的使用自己的默认历史起点：中国指数从 2005 年开始，SPY 从 1993 年开始，纳指100从 2000 年开始（FRED 全收益指数 `XNDX` 数据始于 1999-03-04，1999 年不完整，以 1999 年末为基期）。SPY 的起始年度是 ETF 上市后的不完整自然年；如需统一比较区间，可显式传入 `--start-year` 覆盖。

计算口径：起始年以前一年度最后一个可用收盘价为起点，持有 N 年以后第 N 个年度最后一个可用收盘价为终点，按复合年化收益率计算：

```text
CAGR = (终点指数 / 起点指数) ^ (1 / 持有年数) - 1
```

例如，“2005 / 持有 10 年”表示从 2004 年最后一个交易日收盘持有至 2014 年最后一个交易日收盘的年化收益率，并非十个单年度收益率的算术平均数。

运行：

```bash
uv run python -m investlab.cli run rolling-returns \
  --start-year 2005 \
  --end-year 2025 \
  --symbol H00985 \
  --name 中证全指全收益 \
  --output-dir output/rolling_returns
```

输出：

- `h00985_rolling_annualized_returns.csv`：便于继续分析的数值矩阵。
- `h00985_rolling_annualized_returns.html`：自包含中文热力表，可直接用浏览器打开；不依赖任何前端库，窄屏支持横向滚动。

如果某个日历年完全没有数据，相应单元格会留空，同时 HTML 和终端会给出数据提示。当前年份尚未结束时，其“年末值”实际是获取到的最新交易日收盘，正式比较时建议只使用已经结束的完整年份。

## 10. 一次投入与年度定投对比

`dca-comparison` 场景比较两种投入方式：

- 一次投入：起始年前一年度末投入，持有 N 年，指标为 CAGR。
- 年度定投：每年年初等额投入一份，共投入 N 次，第 N 年年末估值，指标为年度 IRR。
- 差值：`定投 IRR - 一次投入 CAGR`；正数代表定投占优，负数代表一次投入占优。

```bash
uv run python -m investlab.cli run dca-comparison \
  --start-year 2005 \
  --end-year 2025 \
  --symbol H00985 \
  --name 中证全指全收益 \
  --output-dir output/dca_comparison
```

场景分别生成一次投入、定投和差值 HTML。三个页面可互相切换；悬浮单元格可同时查看两种年化收益、差值、定投累计投入、期末资产与累计收益。

数据说明：当指数为 `H00300` 时，场景默认应用《中国大类资产投资 2025 年报》披露的2005年分红估算，将2005年及以后财富指数乘以 `1.026`，使2005年收益由 `-7.65%` 修正为约 `-5.25%`。如需查看数据源未经修正的原始结果，可增加参数 `--no-known-adjustments`。

### 选择或批量生成投资标的

```bash
# 查看全部内置标的
uv run python -m investlab.cli scenarios list

# 生成单个标的
uv run python -m investlab.cli run dca-comparison --assets large-cap

# 一次生成多个标的
uv run python -m investlab.cli run dca-comparison --assets all-a,large-cap,small-cap

# 生成全部内置标的
uv run python -m investlab.cli run dca-comparison --assets all
```

内置标的包括：中证全指全收益（`all-a/H00985`）、沪深300全收益（`large-cap/H00300`）、中证800全收益（`csi800/H00906`）、中证500全收益（`mid-cap/H00905`）、中证1000全收益（`small-cap/H00852`）、标普500 ETF 代理（`sp500/SPY`）和纳斯达克100全收益指数（`nasdaq100/NASDAQXNDX`）。也可继续使用 `--symbol CODE --name 名称` 运行自定义中证指数。

美股表格：标普500使用 Total Real Returns 公布的 SPY 分红再投资年度总收益（可投资 ETF 代理，含管理费、跟踪误差及数据商口径影响）；纳指100使用 FRED 公布的纳斯达克100全收益指数（XNDX / 系列 `NASDAQXNDX`，来源 Nasdaq, Inc.），含股息再投资，数据始于 1999-03-04，完整年度自 2000 年起。

展示思路参考：[有知有行《中国大类资产投资2025年报》滚动年化收益](https://youzhiyouxing.cn/sbbi2025/annual-rolling-returns/)。更多长期投资研究，欢迎关注公众号：**炼金魔女手记**。

批量运行会额外生成 `index.html`，作为不同投资标的和三种分析页面的统一入口。

## 11. 构建公开网站（GitHub Pages，CI 自动部署）

本地构建静态站点到 `dist/site`：

```bash
uv run python -m investlab.cli publish site --assets all --end-year 2025 --site-dir dist/site
```

`dist/site/` 是可直接由 GitHub Pages 发布的静态站点：

- `dist/site/index.html`：网站总入口；
- `dist/site/methodology.html`：计算公式、数据来源、修正和限制；
- `dist/site/assets/<asset-key>/index.html`：单个投资标的入口；
- 每个标的目录下包含一次投入、年度定投、差值 HTML 以及对应 CSV；
- `dist/site/.nojekyll`：要求 GitHub Pages 原样发布静态文件。

构建后可导出全部带水印长图。Node 脚本会自动启动本地服务、校验“炼金魔女手记”水印，并按页面完整尺寸截图：

```bash
node scripts/export_watermarked_tables.mjs \
  --site-dir dist/site \
  --assets all \
  --output-dir dist/site/downloads/wechat
```

也可以只导出部分内容，例如 `--assets sp500,nasdaq100 --pages lump-sum,dca`。运行 `node scripts/export_watermarked_tables.mjs --help` 查看完整参数。导出文件命名契约（`<asset-key>-<page-name>.jpg`）由 `investlab/publish/export_contract.py` 定义并校验。

### CI 自动部署

`.github/workflows/publish.yml` 在推送到 `main` 时自动：构建 rolling-returns 与 dca-comparison 场景输出 → 构建 `dist/site` → 导出带水印长图 → 通过 `actions/upload-pages-artifact` 与 `actions/deploy-pages` 部署到 GitHub Pages。仓库不再依赖手动提交的 `docs/` 作为发布源（`docs/index.html` 已标注 `GENERATED`，仅作历史快照保留）。

新增标的时编辑 `asset_catalog.py`；新增公开表格类型时在 `investlab/publish/report_registry.py` 的 `REPORT_REGISTRY` 中登记。
