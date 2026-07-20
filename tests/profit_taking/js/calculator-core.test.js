"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {
  contributionDates,
  parseRequest,
  runCalculator,
} = require("../../../investlab/profit_taking/calculator_static/calculator-core.js");

const PRICES = [
  ["2024-01-02", 100],
  ["2024-01-08", 110],
  ["2024-01-15", 120],
  ["2024-02-01", 120],
];
const COVERAGE_2024 = ["2024-01-01", "2024-12-31"];
const GOLDEN = JSON.parse(fs.readFileSync(
  path.join(__dirname, "../golden/calculator_parity.json"),
  "utf8",
));
const APP_SOURCE = fs.readFileSync(
  path.join(__dirname, "../../../investlab/profit_taking/calculator_static/calculator-app.js"),
  "utf8",
);

function assertClose(actual, expected, label) {
  if (expected === null) {
    assert.equal(actual, null, label);
    return;
  }
  assert.ok(
    Math.abs(actual - expected) <= 1e-8,
    `${label}: expected ${expected}, received ${actual}`,
  );
}

function targetRow(overrides = {}) {
  return {
    id: "series-1",
    name: "目标止盈",
    contributionAmount: "100",
    cadence: "monthly",
    stopFamily: "target_return",
    targetReturn: "20",
    trailingDrawdown: "",
    saleFraction: "100",
    recycleProceeds: false,
    ...overrides,
  };
}

function parse2024(input) {
  return parseRequest(input, COVERAGE_2024);
}

test("contributionDates emits the first close in every supported period", () => {
  // Given: four observations spanning ISO weeks, 14-day buckets, months, and quarters.
  const dates = PRICES.map(([date]) => date);

  // When: every cadence is scheduled.
  const result = {
    daily: contributionDates(dates, "daily"),
    weekly: contributionDates(dates, "weekly"),
    biweekly: contributionDates(dates, "biweekly"),
    monthly: contributionDates(dates, "monthly"),
    quarterly: contributionDates(dates, "quarterly"),
  };

  // Then: exact contribution dates follow the locked Python definitions.
  assert.deepEqual(result, {
    daily: dates,
    weekly: dates,
    biweekly: ["2024-01-02", "2024-02-01"],
    monthly: ["2024-01-02", "2024-02-01"],
    quarterly: ["2024-01-02"],
  });
});

test("runCalculator sells before a same-close contribution", () => {
  // Given: a monthly strategy reaches its exact target on February's contribution date.
  const request = parse2024({
    startDate: "2024-01-02",
    endDate: "2024-02-01",
    rows: [targetRow()],
  });

  // When: the same-close strategy is calculated.
  const [result] = runCalculator(
    [["2024-01-02", 100], ["2024-02-01", 120]],
    request,
  );

  // Then: the sale precedes the contribution and the new cycle basis is 100 yuan.
  assert.deepEqual(
    result.events.filter((event) => event.date === "2024-02-01").map((event) => event.type),
    ["sale", "contribution"],
  );
  assert.equal(result.dailyStates.at(-1).cycleBasis, 100);
  assert.equal(result.summary.stopCount, 1);
});

test("runCalculator uses recycled proceeds before external cash", () => {
  // Given: a full target sale recycles its proceeds.
  const request = parse2024({
    startDate: "2024-01-02",
    endDate: "2024-02-01",
    rows: [targetRow({ recycleProceeds: true })],
  });

  // When: the February contribution follows the sale.
  const [result] = runCalculator(PRICES, request);

  // Then: the pool pays the contribution and retains the remaining 20 yuan.
  assert.equal(result.dailyStates.at(-1).externalContribution, 0);
  assert.equal(result.dailyStates.at(-1).poolContribution, 100);
  assert.equal(result.dailyStates.at(-1).reusablePool, 20);
});

test("runCalculator waits for the exact trailing drawdown threshold", () => {
  // Given: a trailing strategy is armed at 120 and remains just above a 10% drawdown.
  const request = parse2024({
    startDate: "2024-01-02",
    endDate: "2024-01-05",
    rows: [targetRow({ stopFamily: "trailing_drawdown", trailingDrawdown: "10" })],
  });

  // When: the close falls from 130 to 118 before reaching the exact 117 threshold.
  const [result] = runCalculator([
    ["2024-01-02", 100],
    ["2024-01-03", 120],
    ["2024-01-04", 130],
    ["2024-01-05", 118],
  ], request);

  // Then: no premature trailing sale occurs.
  assert.equal(result.summary.stopCount, 0);
});

test("runCalculator sells at the inclusive trailing drawdown threshold", () => {
  // Given: a trailing strategy is armed and peaks at 130.
  const request = parse2024({
    startDate: "2024-01-02",
    endDate: "2024-01-05",
    rows: [targetRow({ stopFamily: "trailing_drawdown", trailingDrawdown: "10" })],
  });

  // When: the close reaches the exact 10% drawdown price of 117.
  const [result] = runCalculator([
    ["2024-01-02", 100],
    ["2024-01-03", 120],
    ["2024-01-04", 130],
    ["2024-01-05", 117],
  ], request);

  // Then: the trailing stop sells inclusively.
  assert.equal(result.summary.stopCount, 1);
});

test("parseRequest rejects malformed and sixth-row input", () => {
  // Given: an invalid amount and a request exceeding the five-row maximum.
  const malformed = {
    startDate: "2024-01-02",
    endDate: "2024-02-01",
    rows: [targetRow({ contributionAmount: "NaN" })],
  };
  const tooMany = {
    ...malformed,
    rows: Array.from({ length: 6 }, (_, index) =>
      targetRow({ id: `series-${index + 1}`, contributionAmount: "100" }),
    ),
  };

  // When/Then: both boundaries fail with field-addressable validation errors.
  assert.throws(() => parse2024(malformed), { name: "CalculatorValidationError" });
  assert.throws(() => parse2024(tooMany), /一至五/);
});

test("parseRequest clears stop-only values for a no-stop strategy", () => {
  // Given: stale values remain in disabled stop controls.
  const input = {
    startDate: "2024-01-02",
    endDate: "2024-02-01",
    rows: [
      targetRow({
        stopFamily: "none",
        targetReturn: "20",
        trailingDrawdown: "10",
        saleFraction: "50",
        recycleProceeds: true,
      }),
    ],
  };

  // When: the browser boundary parses the request.
  const request = parse2024(input);

  // Then: inactive values cannot leak into the calculation.
  assert.deepEqual(
    {
      targetReturn: request.rows[0].targetReturn,
      trailingDrawdown: request.rows[0].trailingDrawdown,
      saleFraction: request.rows[0].saleFraction,
      recycleProceeds: request.rows[0].recycleProceeds,
    },
    {
      targetReturn: null,
      trailingDrawdown: null,
      saleFraction: null,
      recycleProceeds: false,
    },
  );
});

test("parseRequest rejects both requested coverage boundaries and inverted dates", () => {
  // Given: the manifest allows requested dates from 2006-01-01 through 2026-07-17.
  const coverage = ["2006-01-01", "2026-07-17"];
  const input = {
    startDate: "2006-01-01",
    endDate: "2026-07-17",
    rows: [targetRow()],
  };

  // When/Then: pre-coverage, post-coverage, and inverted requests identify the date field.
  assert.throws(
    () => parseRequest({ ...input, startDate: "2005-12-31" }, coverage),
    { field: "startDate" },
  );
  assert.throws(
    () => parseRequest({ ...input, endDate: "2027-01-01" }, coverage),
    { field: "endDate" },
  );
  assert.throws(
    () => parseRequest({ ...input, startDate: "2026-01-02", endDate: "2025-01-02" }, coverage),
    { field: "endDate" },
  );
});

test("runCalculator accepts an in-coverage weekend and reports the inward trading date", () => {
  // Given: requested coverage starts on Sunday 2006-01-01, before the first close.
  const request = parseRequest({
    startDate: "2006-01-01",
    endDate: "2006-01-06",
    rows: [targetRow()],
  }, ["2006-01-01", "2026-07-17"]);

  // When: the valid request runs against prices beginning on 2006-01-04.
  const [result] = runCalculator([
    ["2006-01-04", 100],
    ["2006-01-05", 101],
    ["2006-01-06", 102],
  ], request);

  // Then: the requested weekend is retained while actual coverage rounds inward.
  assert.equal(request.startDate, "2006-01-01");
  assert.equal(result.dailyStates[0].date, "2006-01-04");
});

test("browser form binds manifest requested coverage and preserves date error focus", () => {
  // Given: the static browser controller is the date-input boundary.
  // When/Then: it binds requested coverage, passes it to parsing, and focuses invalid controls.
  assert.match(APP_SOURCE, /payload\.provenance\.requested_coverage/);
  assert.match(APP_SOURCE, /startInput\.min = requestedCoverage\[0\]/);
  assert.match(APP_SOURCE, /endInput\.max = requestedCoverage\[1\]/);
  assert.match(APP_SOURCE, /parseRequest\([\s\S]*payload\.provenance\.requested_coverage\)/);
  assert.match(APP_SOURCE, /control\.focus\(\)/);
  assert.match(APP_SOURCE, /dataset\.stale = "true"/);
});

test("runCalculator matches every Python golden parity case", () => {
  // Given: all 19 deterministic Python cases with prices, states, events, and summaries.
  assert.equal(GOLDEN.cases.length, 19);

  // When: each case is replayed through the dependency-free browser core.
  for (const fixture of GOLDEN.cases) {
    const config = fixture.config;
    const percent = (value) => value === null ? "" : String(value * 100);
    const request = parseRequest({
      startDate: fixture.requested_start,
      endDate: fixture.requested_end,
      rows: [{
        id: fixture.id,
        name: config.name,
        contributionAmount: String(config.contribution_amount),
        cadence: config.cadence,
        stopFamily: config.stop_family,
        targetReturn: percent(config.target_return),
        trailingDrawdown: percent(config.trailing_drawdown),
        saleFraction: percent(config.sale_fraction),
        recycleProceeds: config.recycle_proceeds,
      }],
    }, [fixture.requested_start, fixture.requested_end]);
    const [actual] = runCalculator(
      fixture.prices.map((point) => [point.date, point.close]),
      request,
    );

    // Then: dates/counts/discrete fields match exactly and every float is within 1e-8.
    assert.equal(actual.dailyStates[0].date, fixture.actual_start, fixture.id);
    assert.equal(actual.dailyStates.at(-1).date, fixture.actual_end, fixture.id);
    assert.equal(actual.dailyStates.length, fixture.daily_states.length, fixture.id);
    assert.equal(actual.events.length, fixture.events.length, fixture.id);
    const stateFields = {
      price: "price",
      scheduledContribution: "scheduled_contribution",
      externalContribution: "external_contribution",
      poolContribution: "pool_contribution",
      shares: "shares",
      cycleBasis: "cycle_basis",
      reusablePool: "reusable_pool",
      reserve: "reserve",
      holdingValue: "holding_value",
      totalAssets: "total_assets",
      nav: "nav",
    };
    actual.dailyStates.forEach((state, index) => {
      const expected = fixture.daily_states[index];
      assert.equal(state.date, expected.date, `${fixture.id}.states.${index}.date`);
      for (const [actualField, expectedField] of Object.entries(stateFields)) {
        assertClose(
          state[actualField],
          expected[expectedField],
          `${fixture.id}.states.${index}.${expectedField}`,
        );
      }
    });
    actual.events.forEach((event, index) => {
      const expected = fixture.events[index];
      assert.equal(event.date, expected.date, `${fixture.id}.events.${index}.date`);
      assert.equal(event.type, expected.event_type, `${fixture.id}.events.${index}.type`);
      for (const field of ["amount", "shares", "price"]) {
        assertClose(event[field], expected[field], `${fixture.id}.events.${index}.${field}`);
      }
    });
    const summaryFields = {
      scheduledInvested: "scheduled_invested",
      externalInvested: "external_invested",
      endingHoldings: "ending_holdings",
      reusablePool: "reusable_pool",
      reserve: "reserve",
      totalAssets: "total_assets",
      totalProfit: "total_profit",
      cumulativeReturn: "cumulative_return",
      xirr: "xirr",
      maximumDrawdown: "maximum_drawdown",
      timeInMarket: "time_in_market",
    };
    for (const [actualField, expectedField] of Object.entries(summaryFields)) {
      assertClose(
        actual.summary[actualField],
        fixture.summary[expectedField],
        `${fixture.id}.summary.${expectedField}`,
      );
    }
    assert.equal(actual.summary.stopCount, fixture.summary.stop_count, fixture.id);
  }
});
