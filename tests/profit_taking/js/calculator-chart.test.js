"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {
  buildChartModel,
  chartIndexAt,
  downsample,
  formatPercent,
  renderResultsMarkup,
} = require("../../../investlab/profit_taking/calculator_static/calculator-chart.js");

function result(id, name, values, xirr = 0.081) {
  const dailyStates = values.map((value, index) => ({
    date: `2024-01-${String(index + 1).padStart(2, "0")}`,
    totalAssets: value,
    nav: 1 + value / 1000,
  }));
  return {
    config: { id, name },
    dailyStates,
    summary: {
      scheduledInvested: 300,
      externalInvested: 250,
      endingHoldings: values.at(-1),
      reusablePool: 20,
      reserve: 30,
      totalAssets: values.at(-1) + 50,
      totalProfit: values.at(-1) - 200,
      cumulativeReturn: 0.2,
      xirr,
      maximumDrawdown: -0.1,
      timeInMarket: 2 / 3,
      stopCount: 2,
    },
  };
}

test("downsample preserves exact endpoints and bounded finite points", () => {
  const points = Array.from({ length: 1000 }, (_, index) => ({
    date: `d${index}`,
    value: Math.sin(index),
  }));
  const sampled = downsample(points, 80);
  assert.equal(sampled.length, 80);
  assert.deepEqual(sampled[0], points[0]);
  assert.deepEqual(sampled.at(-1), points.at(-1));
  assert.ok(sampled.every((point) => Number.isFinite(point.value)));
});

test("chart model supports five stable series without invalid paths", () => {
  const results = Array.from({ length: 5 }, (_, index) =>
    result(`strategy-${index + 1}`, `策略 ${index + 1}`, [100 + index, 120 + index, 115 + index]));
  const model = buildChartModel(results, "totalAssets");
  assert.equal(model.series.length, 5);
  assert.equal(new Set(model.series.map((series) => series.styleIndex)).size, 5);
  assert.ok(model.series.every((series) => !/NaN|Infinity/.test(series.path)));
  assert.equal(model.series[0].points[0].value, 100);
  assert.equal(model.series[0].points.at(-1).value, 115);
});

test("chart model follows stable UI keys after delete and replacement", () => {
  const results = [
    result("strategy-1", "保留 A", [100, 101]),
    result("strategy-3", "保留 C", [100, 102]),
    result("strategy-4", "新方案复用 B", [100, 103]),
  ];
  const rowStyles = [
    { id: "strategy-1", key: "A", styleIndex: 0 },
    { id: "strategy-3", key: "C", styleIndex: 2 },
    { id: "strategy-4", key: "B", styleIndex: 1 },
  ];

  const model = buildChartModel(results, "totalAssets", rowStyles);

  assert.deepEqual(model.series.map((series) => series.key), ["A", "C", "B"]);
  assert.deepEqual(model.series.map((series) => series.styleIndex), [0, 2, 1]);
});

test("pointer index clamps to the padded plotting bounds", () => {
  assert.equal(chartIndexAt(68, 11), 0);
  assert.equal(chartIndexAt(780, 11), 10);
  assert.equal(chartIndexAt(-100, 11), 0);
  assert.equal(chartIndexAt(900, 11), 10);
  assert.equal(chartIndexAt(424, 11), 5);
  assert.equal(chartIndexAt(134, 11, { left: 100, width: 400 }), 0);
  assert.equal(chartIndexAt(490, 11, { left: 100, width: 400 }), 10);
});

test("asset and return axes expose Chinese units and endpoint dates", () => {
  const results = [result("strategy-1", "基准", [10000, 15000, 20000])];
  const markup = renderResultsMarkup(results, {
    requestedStart: "2024-01-01",
    requestedEnd: "2024-01-03",
    actualStart: "2024-01-01",
    actualEnd: "2024-01-03",
  });

  assert.match(markup, /总资产（万元）/);
  assert.match(markup, /收益率（%）/);
  assert.match(markup, />2024-01-01</);
  assert.match(markup, />2024-01-03</);
  assert.match(markup, /class="grid-line"/);
  assert.doesNotMatch(markup, /NaN|Infinity/);
});

test("one-day axes remain finite and render one stable date tick", () => {
  const markup = renderResultsMarkup([result("strategy-1", "单日", [100])], {
    requestedStart: "2024-01-01",
    requestedEnd: "2024-01-01",
    actualStart: "2024-01-01",
    actualEnd: "2024-01-01",
  });

  assert.equal((markup.match(/>2024-01-01</g) || []).length, 2);
  assert.doesNotMatch(markup, /NaN|Infinity/);
});

test("result markup exposes every metric, two SVGs and textual summaries", () => {
  const results = [
    result("strategy-1", "<基准>", [100], null),
    result("strategy-2", "止盈", [100], 0.1),
  ];
  const markup = renderResultsMarkup(results, {
    requestedStart: "2024-01-01",
    requestedEnd: "2024-01-01",
    actualStart: "2024-01-01",
    actualEnd: "2024-01-01",
  });
  for (const label of [
    "计划定投额", "外部投入", "期末持仓", "复投资金池", "止盈资金池", "总资产",
    "总盈利", "累计收益率", "年化收益率（XIRR", "贡献中性最大回撤", "在场率", "止盈次数",
  ]) assert.match(markup, new RegExp(label));
  assert.equal((markup.match(/<svg/g) || []).length, 2);
  assert.equal((markup.match(/<title/g) || []).length, 2);
  assert.equal((markup.match(/<desc/g) || []).length, 2);
  assert.match(markup, /aria-label="图例"/);
  assert.match(markup, /当前值/);
  assert.match(markup, />—</);
  assert.doesNotMatch(markup, /<基准>/);
  assert.match(markup, /<thead><tr><th scope="col">指标<\/th><th scope="col">&lt;基准&gt;<\/th><th scope="col">止盈<\/th>/);
  const tableBody = markup.match(/<table class="results-table">[\s\S]*?<tbody>([\s\S]*?)<\/tbody>/)[1];
  assert.equal((tableBody.match(/<tr>/g) || []).length, 12);
  assert.equal((tableBody.match(/<th scope="row">/g) || []).length, 12);
});

test("responsive CSS preserves readable charts and desktop date action row", () => {
  const css = fs.readFileSync(path.join(
    __dirname,
    "../../../investlab/profit_taking/calculator_static/calculator.css",
  ), "utf8");
  assert.match(css, /\.chart-scroll\s*\{[^}]*overflow-x:\s*auto/s);
  assert.match(css, /\.chart-scroll svg\s*\{[^}]*min-width:\s*640px/s);
  assert.match(css, /#calculator-form\s*\{[^}]*display:\s*grid/s);
  assert.match(css, /\.form-actions\s*\{[^}]*grid-column:\s*2/s);
  assert.match(css, /@media \(max-width: 768px\)[\s\S]*#calculator-form\s*\{[^}]*display:\s*block/s);
});

test("formatPercent uses signed text and handles undefined XIRR", () => {
  assert.equal(formatPercent(null), "—");
  assert.equal(formatPercent(0.1234), "+12.34%");
  assert.equal(formatPercent(-0.1), "−10.00%");
});
