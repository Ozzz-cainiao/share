"use strict";

(function exposeCalculatorCharts(root) {
  const STYLE_COUNT = 5;
  const WIDTH = 800;
  const HEIGHT = 300;
  const PAD = Object.freeze({ left: 68, right: 20, top: 24, bottom: 40 });

  const escapeHtml = (value) => String(value)
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#39;");

  function downsample(points, limit = 180) {
    if (points.length <= limit) return points.slice();
    return Array.from({ length: limit }, (_, index) => {
      const sourceIndex = Math.round(index * (points.length - 1) / (limit - 1));
      return points[sourceIndex];
    });
  }

  function formatMoney(value) {
    return new Intl.NumberFormat("zh-CN", {
      style: "currency", currency: "CNY", maximumFractionDigits: 2,
    }).format(value);
  }

  function formatPercent(value) {
    if (value === null || value === undefined || !Number.isFinite(value)) return "—";
    const sign = value > 0 ? "+" : value < 0 ? "−" : "";
    return `${sign}${Math.abs(value * 100).toFixed(2)}%`;
  }

  function fallbackStyleIndex(id, fallback) {
    const match = String(id).match(/(\d+)$/);
    return match ? (Number(match[1]) - 1) % STYLE_COUNT : fallback % STYLE_COUNT;
  }

  function buildChartModel(results, metric, rowStyles = []) {
    const allValues = results.flatMap((result) => result.dailyStates.map((state) =>
      metric === "navReturn" ? state.nav - 1 : state.totalAssets));
    const finite = allValues.filter(Number.isFinite);
    let minimum = Math.min(...finite);
    let maximum = Math.max(...finite);
    if (minimum === maximum) { minimum -= 1; maximum += 1; }
    const plotWidth = WIDTH - PAD.left - PAD.right;
    const plotHeight = HEIGHT - PAD.top - PAD.bottom;
    const series = results.map((result, index) => {
      const uiStyle = rowStyles.find((candidate) => candidate.id === result.config.id);
      const assignedStyle = Number.isInteger(uiStyle?.styleIndex)
        ? uiStyle.styleIndex : fallbackStyleIndex(result.config.id, index);
      const allPoints = result.dailyStates.map((state) => ({
        date: state.date,
        value: metric === "navReturn" ? state.nav - 1 : state.totalAssets,
      }));
      const points = downsample(allPoints);
      const path = points.map((point, pointIndex) => {
        const x = PAD.left + (points.length === 1 ? plotWidth / 2 : pointIndex * plotWidth / (points.length - 1));
        const y = PAD.top + (maximum - point.value) * plotHeight / (maximum - minimum);
        return `${pointIndex ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
      }).join(" ");
      return {
        name: result.config.name,
        key: uiStyle?.key || String.fromCharCode(65 + assignedStyle),
        styleIndex: assignedStyle,
        points, allPoints, path,
      };
    });
    return { metric, minimum, maximum, series };
  }

  function axisMarkup(model) {
    const plotHeight = HEIGHT - PAD.top - PAD.bottom;
    const magnitude = Math.max(Math.abs(model.minimum), Math.abs(model.maximum));
    const divisor = model.metric === "totalAssets" && magnitude >= 10000 ? 10000 : 1;
    const unit = model.metric === "navReturn"
      ? "收益率（%）" : `总资产（${divisor === 10000 ? "万元" : "元"}）`;
    const tickText = (value) => model.metric === "navReturn"
      ? `${(value * 100).toFixed(1)}%`
      : (value / divisor).toFixed(divisor === 10000 ? 2 : 0);
    const yTicks = Array.from({ length: 5 }, (_, index) => {
      const ratio = index / 4;
      const value = model.maximum - ratio * (model.maximum - model.minimum);
      const y = PAD.top + ratio * plotHeight;
      return `<line class="grid-line" x1="${PAD.left}" y1="${y}" x2="${WIDTH - PAD.right}" y2="${y}"></line><text class="axis-label" x="${PAD.left - 8}" y="${y + 4}" text-anchor="end">${tickText(value)}</text>`;
    }).join("");
    const points = model.series[0].allPoints;
    const plotWidth = WIDTH - PAD.left - PAD.right;
    const xTicks = points.length === 1
      ? `<text class="axis-label" x="${PAD.left + plotWidth / 2}" y="${HEIGHT - 16}" text-anchor="middle">${points[0].date}</text>`
      : `<text class="axis-label" x="${PAD.left}" y="${HEIGHT - 16}" text-anchor="start">${points[0].date}</text><text class="axis-label tick-mid" x="${PAD.left + plotWidth / 2}" y="${HEIGHT - 16}" text-anchor="middle">${points[Math.floor((points.length - 1) / 2)].date}</text><text class="axis-label" x="${WIDTH - PAD.right}" y="${HEIGHT - 16}" text-anchor="end">${points.at(-1).date}</text>`;
    return { markup: `<g aria-hidden="true"><text class="axis-unit" x="${PAD.left}" y="14">${unit}</text>${yTicks}${xTicks}</g>`, unit };
  }

  function chartMarkup(model, title, valueFormatter, chartId) {
    const first = model.series[0].allPoints;
    const start = first[0].date;
    const end = first.at(-1).date;
    const axes = axisMarkup(model);
    const legend = model.series.map((series) =>
      `<li><span class="legend-line series-${series.styleIndex}" aria-hidden="true"></span>系列 ${escapeHtml(series.key)} · ${escapeHtml(series.name)}</li>`).join("");
    const paths = model.series.map((series) =>
      `<path class="chart-line series-${series.styleIndex}" d="${series.path}" vector-effect="non-scaling-stroke"></path>`).join("");
    const summaries = model.series.map((series) => {
      const values = series.allPoints.map((point) => point.value);
      return `<tr><th scope="row">${escapeHtml(series.name)}</th><td>${series.allPoints.length}</td><td>${valueFormatter(values.at(-1))}</td><td>${valueFormatter(Math.min(...values))}</td><td>${valueFormatter(Math.max(...values))}</td></tr>`;
    }).join("");
    return `<figure class="research-figure" data-chart-id="${chartId}"><h3>${title}</h3>
      <ul class="chart-legend" aria-label="图例">${legend}</ul>
      <div class="chart-frame"><svg viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img" tabindex="0" aria-labelledby="${chartId}-title ${chartId}-desc">
        <title id="${chartId}-title">${title}</title><desc id="${chartId}-desc">${start} 至 ${end}，纵轴 ${axes.unit}，横轴为交易日期，${model.series.length} 个策略；方向键可逐日读取数值。</desc>
        ${axes.markup}
        <line class="axis" x1="${PAD.left}" y1="${PAD.top}" x2="${PAD.left}" y2="${HEIGHT - PAD.bottom}"></line>
        <line class="axis" x1="${PAD.left}" y1="${HEIGHT - PAD.bottom}" x2="${WIDTH - PAD.right}" y2="${HEIGHT - PAD.bottom}"></line>
        ${paths}<line class="chart-cursor" x1="0" x2="0" y1="${PAD.top}" y2="${HEIGHT - PAD.bottom}" hidden></line>
      </svg></div><p class="chart-readout" aria-live="polite">当前值：聚焦图表后使用左右方向键逐日查看，初始为最新交易日。</p>
      <details class="chart-alternative"><summary>查看文字摘要</summary><div class="table-scroll" tabindex="0" aria-label="图表文字摘要，可横向滚动"><table><thead><tr><th>策略</th><th>完整观测数</th><th>当前值</th><th>最低值</th><th>最高值</th></tr></thead><tbody>${summaries}</tbody></table></div></details></figure>`;
  }

  function resultTable(results, coverage) {
    const cells = [
      ["计划定投额（累计计划金额）", "scheduledInvested", formatMoney],
      ["外部投入（收益率分母）", "externalInvested", formatMoney],
      ["期末持仓", "endingHoldings", formatMoney], ["复投资金池", "reusablePool", formatMoney],
      ["止盈资金池", "reserve", formatMoney], ["总资产", "totalAssets", formatMoney],
      ["总盈利（总资产−外部投入）", "totalProfit", formatMoney],
      ["累计收益率（总盈利÷外部投入）", "cumulativeReturn", formatPercent],
      ["年化收益率（XIRR，外部现金流口径）", "xirr", formatPercent],
      ["贡献中性最大回撤", "maximumDrawdown", formatPercent],
      ["在场率（持仓交易日÷区间交易日）", "timeInMarket", formatPercent],
      ["止盈次数", "stopCount", (value) => String(value)],
    ];
    const head = cells.map(([label]) => `<th scope="col">${label}</th>`).join("");
    const body = results.map((result) => `<tr><th scope="row">${escapeHtml(result.config.name)}</th>${cells.map(([, key, formatter]) => `<td>${formatter(result.summary[key])}</td>`).join("")}</tr>`).join("");
    return `<div class="table-scroll" tabindex="0" aria-label="策略结果表，可横向滚动"><p class="scroll-instruction">窄屏可横向滚动查看全部指标。</p><table class="results-table"><caption>请求区间 ${coverage.requestedStart} 至 ${coverage.requestedEnd}；实际交易日 ${coverage.actualStart} 至 ${coverage.actualEnd}</caption><thead><tr><th scope="col">策略</th>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
  }

  function renderResultsMarkup(results, coverage, rowStyles = coverage.rowStyles || []) {
    const assets = buildChartModel(results, "totalAssets", rowStyles);
    const nav = buildChartModel(results, "navReturn", rowStyles);
    return `${resultTable(results, coverage)}${chartMarkup(assets, "总资产", formatMoney, "assets-figure")}${chartMarkup(nav, "贡献中性累计收益", formatPercent, "nav-figure")}`;
  }

  function chartIndexAt(clientX, count, rect = { left: 0, width: WIDTH }) {
    const svgX = rect.width > 0 ? (clientX - rect.left) * WIDTH / rect.width : PAD.left;
    const ratio = Math.max(0, Math.min(1, (svgX - PAD.left) / (WIDTH - PAD.left - PAD.right)));
    return Math.round(ratio * (count - 1));
  }

  function attachChart(figure, model, formatter) {
    const svg = figure.querySelector("svg");
    const cursor = figure.querySelector(".chart-cursor");
    const readout = figure.querySelector(".chart-readout");
    let activeIndex = model.series[0].allPoints.length - 1;
    const show = () => {
      const count = model.series[0].allPoints.length;
      const x = PAD.left + (count === 1 ? (WIDTH - PAD.left - PAD.right) / 2 : activeIndex * (WIDTH - PAD.left - PAD.right) / (count - 1));
      cursor.hidden = false; cursor.setAttribute("x1", x); cursor.setAttribute("x2", x);
      const date = model.series[0].allPoints[activeIndex].date;
      const values = model.series.map((series) => `${series.name} ${formatter(series.allPoints[activeIndex].value)}`);
      readout.textContent = `当前值：${date}；${values.join("；")}`;
    };
    svg.addEventListener("focus", show);
    svg.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { cursor.hidden = true; readout.textContent = "当前值已隐藏；按方向键可继续查看。"; return; }
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      if (event.key === "Home") activeIndex = 0;
      else if (event.key === "End") activeIndex = model.series[0].allPoints.length - 1;
      else activeIndex = Math.max(0, Math.min(model.series[0].allPoints.length - 1, activeIndex + (event.key === "ArrowRight" ? 1 : -1)));
      show();
    });
    const pointAtPointer = (event) => {
      const rect = svg.getBoundingClientRect();
      activeIndex = chartIndexAt(event.clientX, model.series[0].allPoints.length, rect);
      show();
    };
    svg.addEventListener("pointermove", pointAtPointer);
    svg.addEventListener("pointerdown", pointAtPointer);
  }

  function renderResults(container, results, coverage) {
    container.innerHTML = renderResultsMarkup(results, coverage);
    const models = [
      buildChartModel(results, "totalAssets", coverage.rowStyles),
      buildChartModel(results, "navReturn", coverage.rowStyles),
    ];
    const formatters = [formatMoney, formatPercent];
    container.querySelectorAll(".research-figure").forEach((figure, index) => attachChart(figure, models[index], formatters[index]));
    container.hidden = false;
  }

  const api = Object.freeze({
    buildChartModel, chartIndexAt, downsample, formatPercent, renderResults, renderResultsMarkup,
  });
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.CalculatorCharts = api;
})(typeof globalThis === "undefined" ? this : globalThis);
