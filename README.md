# A股与美股定投 vs 等低点回测（可直接生成公众号文章）

## 1. 环境

- Python 由 `uv` 管理（`requires-python >= 3.11`）
- 依赖：`akshare`、`pandas`、`numpy`、`matplotlib`（已写入 `pyproject.toml`）

## 2. 运行

```bash
uv run python main.py
```

## 3. 输出文件

- 公众号 Markdown 成品：`output/wechat_article.md`
- 图表目录：`output/charts/`
- 结果数据：`output/data/`

## 4. 回测标的

- A股全收益指数：`H00300`（沪深300全收益）、`H00906`（中证800全收益）、`H00905`（中证500全收益）
- 美股分红再投资近似口径：`SPY`、`QQQ` 前复权收盘价

## 5. 策略定义

- 基准：每月定投（DCA）
- 择时：资金先入现金池，回撤阈值触发后一次性买入；超过最长等待期限强制买入
- 参数网格：回撤阈值 `5%~30%`，最长等待 `3/6/12/18` 个月
