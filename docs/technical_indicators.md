# 技术指标择时说明

本文档解释 `technical-timing` 场景使用的 32 个技术指标。它们来自《精选 32 个技术指标在指数上的择时能力分析》的默认参数框架，分为趋势、动量、波动、成交量四类。

## 如何读结果

- `*_summary.csv`：每个指标一行，展示收益、风险和换仓统计。
- `*_equity_curves.csv`：每个指标一列，数值为从 1.0 开始的策略净值。
- `*_equity_all.png`：32 个指标和基准的总览净值图。
- `*_equity_trend.png`、`*_equity_momentum.png`、`*_equity_volatility.png`、`*_equity_volume.png`：按类别拆分后的净值图。
- `*_signals.csv`：每天每个指标是否产生买入或卖出信号。

图里的 `benchmark` 是买入并持有指数本身。某条指标曲线高于 `benchmark`，表示在该数据和当前实现口径下，这个择时规则跑赢了持有指数。

## 统计字段

- `sharpe`：年化夏普比率，越高表示单位波动获得的收益越高。
- `annual_return`：策略年化收益。
- `annual_excess`：策略年化收益减去基准年化收益。
- `annual_volatility`：策略年化波动。
- `holding_win_rate`：每次完整持仓交易中，盈利交易占比。
- `payoff_ratio`：盈利交易平均收益 / 亏损交易平均亏损绝对值。
- `max_drawdown`：最大回撤。
- `annual_turnover`：年均换仓次数，数值越高交易越频繁。

## 趋势类指标

趋势类指标尝试回答：现在是否已经形成上涨或下跌趋势？这类指标通常是顺势交易，优点是能抓趋势，缺点是震荡市容易频繁反复。

### SMA

简单移动平均线。计算过去 N 天收盘价的算术平均：

```text
SMA(N) = MA(CLOSE, N)
```

默认参数：短期 5 日，长期 20 日。短期均线上穿长期均线买入，下穿卖出。

### EMA

指数移动平均线。相比 SMA，EMA 对近期价格变化更敏感：

```text
EMA_t = alpha * CLOSE_t + (1 - alpha) * EMA_{t-1}
alpha = 2 / (N + 1)
```

默认参数：短期 10 日，长期 20 日。短期 EMA 上穿长期 EMA 买入，下穿卖出。

### KAMA

卡夫曼自适应移动平均线。它会根据价格运动效率调节平滑速度。趋势清晰时更贴近价格，噪声大时更平滑：

```text
ER = ABS(CLOSE - REF(CLOSE, N)) / SUM(ABS(CLOSE - REF(CLOSE, 1)), N)
SC = [ER * (fast - slow) + slow]^2
KAMA_t = KAMA_{t-1} + SC * (CLOSE_t - KAMA_{t-1})
```

默认参数：短期 10 日，长期 20 日。短期 KAMA 上穿长期 KAMA 买入，下穿卖出。

### MACD

指数平滑异同移动平均线。先计算快慢 EMA 差值，再计算信号线：

```text
DIFF = EMA(CLOSE, 12) - EMA(CLOSE, 26)
DEA = EMA(DIFF, 9)
MACD = 2 * (DIFF - DEA)
```

默认规则：MACD 柱在 0 线上方买入，0 线下方卖出。

### AROON

阿隆指标衡量最近 N 天高点和低点距离当前有多近：

```text
AROON_UP = (N - 最高价距今天数) / N * 100
AROON_DOWN = (N - 最低价距今天数) / N * 100
AROON = AROON_UP - AROON_DOWN
```

默认参数：20 日，阈值 70。`AROON_UP` 上穿 70 且 `AROON > 0` 买入；`AROON_DOWN` 下穿 70 且 `AROON < 0` 卖出。

### ADX

平均趋向指标。先计算上行方向强度 `+DI` 和下行方向强度 `-DI`：

```text
+DM = 当日向上突破幅度
-DM = 当日向下突破幅度
TR = 真实波幅
+DI = SUM(+DM, N) / SUM(TR, N) * 100
-DI = SUM(-DM, N) / SUM(TR, N) * 100
```

默认参数：14 日。`+DI` 上穿 `-DI` 买入，下穿卖出。

### DPO

区间震荡线，试图剥离长期趋势，只看短周期偏离：

```text
DPO = CLOSE - REF(MA(CLOSE, N), N / 2 + 1)
```

默认参数：20 日。DPO 上穿 0 买入，下穿 0 卖出。

### SAR

抛物线转向指标。它使用加速因子和极值点跟踪趋势止损线：

```text
SAR_t = SAR_{t-1} + AF * (EP - SAR_{t-1})
```

默认参数：步长 0.02，最大加速因子 0.2。收盘价在 SAR 上方买入，在 SAR 下方卖出。

## 动量类指标

动量类指标尝试回答：价格变化速度是否足够强？有些动量指标追随强势，有些在极端区域寻找反转。

### MOM

动量指标，计算当前收盘价和 N 天前收盘价差值：

```text
MOM = CLOSE - REF(CLOSE, N)
```

默认参数：10 日。MOM 大于 0 买入，小于 0 卖出。

### BIAS

乖离率，衡量价格偏离均线的幅度：

```text
BIAS = (CLOSE - MA(CLOSE, N)) / MA(CLOSE, N) * 100
```

默认参数：26 日，阈值 5。BIAS 大于 5 买入，小于 -5 卖出。

### RSI

相对强弱指数，比较上涨和下跌幅度：

```text
RSI = 100 * EMA(上涨幅度, N) / [EMA(上涨幅度, N) + EMA(下跌幅度, N)]
```

默认参数：14 日。RSI 上穿 30 买入，下穿 70 卖出。

### ROC

变动率指标，计算 N 日收益率：

```text
ROC = (CLOSE - REF(CLOSE, N)) / REF(CLOSE, N) * 100
```

默认参数：20 日。ROC 大于 0 买入，小于 0 卖出。

### KDJ

随机指标，衡量收盘价在近期高低价区间中的位置：

```text
RSV = (CLOSE - MIN(LOW, N)) / [MAX(HIGH, N) - MIN(LOW, N)] * 100
K = EMA(RSV, 3)
D = MA(K, 3)
J = 3K - 2D
```

默认参数：9、3、80、20。D 小于 20 且 K 上穿 D 买入；D 大于 80 且 K 下穿 D 卖出。

### WR

威廉指标，衡量收盘价接近近期高点还是低点：

```text
WR = -100 * [MAX(HIGH, N) - CLOSE] / [MAX(HIGH, N) - MIN(LOW, N)]
```

默认参数：6 日。WR 下穿 -80 买入，上穿 -20 卖出。

### CCI

顺势指标，衡量典型价格相对均值的偏离：

```text
TYP = (HIGH + LOW + CLOSE) / 3
CCI = (TYP - MA(TYP, N)) / [0.015 * MA(ABS(TYP - MA(TYP, N)), N)]
```

默认参数：14 日。CCI 大于 100 买入，小于 -100 卖出。

### CMO

钱德动量摆动指标，比较上涨总幅度和下跌总幅度：

```text
CMO = [SUM(上涨幅度, N) - SUM(下跌幅度, N)] / [SUM(上涨幅度, N) + SUM(下跌幅度, N)] * 100
```

默认参数：25 日。CMO 大于 0 买入，小于 0 卖出。

### UO

终极振荡器，综合 7、14、28 日三个周期的买入压力：

```text
UO = 100 * (4 * AVG7 + 2 * AVG14 + AVG28) / 7
```

默认规则：UO 上穿 70 买入，下穿 50 卖出。

### TRIX

三重指数平滑移动平均指标：

```text
TRIPLE_EMA = EMA(EMA(EMA(CLOSE, 12), 12), 12)
TRIX = PCT_CHANGE(TRIPLE_EMA)
TRIXMA = MA(TRIX, 20)
```

TRIX 上穿 TRIXMA 买入，下穿卖出。

### POS

位置指标，衡量 N 日收益率在过去 N 日收益率区间中的位置：

```text
PC = (CLOSE - REF(CLOSE, N)) / REF(CLOSE, N)
POS = (PC - MIN(PC, N)) / [MAX(PC, N) - MIN(PC, N)] * 100
```

默认参数：20 日。POS 上穿 80 买入，下穿 20 卖出。

## 波动类指标

波动类指标尝试回答：价格是否突破了由波动率或价格区间构造出的通道？

### ATR/KC

ATR 是真实波幅均值，KC 是肯特纳通道：

```text
TR = MAX(HIGH - LOW, ABS(HIGH - REF(CLOSE, 1)), ABS(LOW - REF(CLOSE, 1)))
ATR = EMA(TR, N)
UPPER = MA(CLOSE, N) + M * ATR
LOWER = MA(CLOSE, N) - M * ATR
```

默认参数：14 日，倍数 2。收盘价上穿上轨买入，下穿下轨卖出。

### BBANDS

布林带，用均线加减标准差构造通道：

```text
MID = MA(CLOSE, N)
UPPER = MID + M * STD(CLOSE, N)
LOWER = MID - M * STD(CLOSE, N)
```

默认参数：20 日，倍数 2。收盘价上穿上轨买入，下穿下轨卖出。

### DC

唐奇安通道，用近期最高价和最低价构造通道：

```text
UPPER = MAX(HIGH, N)
LOWER = MIN(LOW, N)
```

默认参数：20 日。收盘价突破上轨买入，跌破下轨卖出。

### ACCBANDS

加速带，根据高低价振幅动态调整通道宽度：

```text
HL_RATIO = (HIGH - LOW) / (HIGH + LOW)
UPPER = MA(HIGH * (1 + M * HL_RATIO), N)
LOWER = MA(LOW * (1 - M * HL_RATIO), N)
```

默认参数：20 日，倍数 4。收盘价上穿上轨买入，下穿下轨卖出。

### MASSI

梅斯线，寻找高低价波幅急剧扩张后的反转：

```text
MASSI = SUM(EMA(HIGH - LOW, 9) / EMA(EMA(HIGH - LOW, 9), 9), 25)
```

MASSI 上穿 27 后再下穿 26.5，并结合 9 日价格斜率判断买卖。

### RVI

相对离散指数，用价格波动标准差替代涨跌幅来构造类似 RSI 的指标：

```text
STD = STD(CLOSE, N)
USTD = EMA(上涨日 STD, N)
DSTD = EMA(下跌日 STD, N)
RVI = 100 * USTD / (USTD + DSTD)
```

默认参数：14 日。RVI 下穿 30 买入，上穿 70 卖出。

### UDVD

单向波动差，比较向上波动和向下波动：

```text
VOLUP = (HIGH - OPEN) / OPEN
VOLDOWN = (OPEN - LOW) / OPEN
UDVD = MA(VOLUP - VOLDOWN, N)
```

默认参数：20 日。UDVD 大于 0 买入，小于 0 卖出。

## 成交量类指标

成交量类指标尝试回答：价格变化是否获得了成交量确认？

### AD

累计派发指标，根据收盘价在高低价区间中的位置分配成交量：

```text
AD = CUMSUM(((CLOSE - LOW) - (HIGH - CLOSE)) * VOLUME / (HIGH - LOW))
ADOSC = EMA(AD, 3) - EMA(AD, 10)
```

ADOSC 大于 0 且收盘价在 90 日均线上方买入；ADOSC 小于 0 且收盘价在 90 日均线下方卖出。

### OBV

能量潮，把上涨日成交量记为正、下跌日成交量记为负：

```text
OBV = CUMSUM(上涨日 VOLUME - 下跌日 VOLUME)
OBV_HISTOGRAM = MA(OBV, 10) - MA(OBV, 20)
```

OBV_HISTOGRAM 大于 0 买入，小于 0 卖出。

### MFI

资金流量指标，类似 RSI，但引入成交量：

```text
TP = (HIGH + LOW + CLOSE) / 3
MF = TP * VOLUME
MFI = 100 - 100 / (1 + 正向资金流 / 负向资金流)
```

MFI 上穿 20 买入，下穿 80 卖出。

### EOM

简易波动指标，衡量价格移动和成交量之间的关系：

```text
MID_MOVE = (HIGH + LOW) / 2 - REF((HIGH + LOW) / 2, 1)
BOX_RATIO = VOLUME / 10000000 / (HIGH - LOW)
EOM = MA(MID_MOVE / BOX_RATIO, N)
```

默认参数：20 日。EOM 大于 0 买入，小于 0 卖出。

### MAAMT

成交量均线：

```text
MAAMT = MA(VOLUME, N)
```

默认参数：30 日。成交量上穿其均线买入，下穿卖出。

### FI

强力指数，结合价格涨跌幅和成交量：

```text
FI = EMA((CLOSE - REF(CLOSE, 1)) * VOLUME, N)
```

默认参数：13 日。FI 大于 0 买入，小于 0 卖出。
