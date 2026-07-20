"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  parseRequest,
  runCalculator,
} = require("../../../investlab/profit_taking/calculator_static/calculator-core.js");

function noStopRequest() {
  return parseRequest({
    startDate: "2024-01-02",
    endDate: "2024-01-03",
    rows: [{
      id: "xirr",
      name: "不止盈",
      contributionAmount: "100",
      cadence: "monthly",
      stopFamily: "none",
      targetReturn: "",
      trailingDrawdown: "",
      saleFraction: "",
      recycleProceeds: false,
    }],
  }, ["2024-01-02", "2024-01-03"]);
}

test("adjacent trading-day 1% gain has a finite high XIRR", () => {
  // Given: one contribution gains 1% on the next trading observation.
  const request = noStopRequest();

  // When: the dependency-free browser calculator annualizes the cash flows.
  const [result] = runCalculator(
    [["2024-01-02", 100], ["2024-01-03", 101]],
    request,
  );

  // Then: the root above the former limit of ten is recovered.
  assert.ok(Math.abs(result.summary.xirr - (1.01 ** 365.25 - 1)) <= 1e-8);
});

test("adjacent trading-day root above the finite cap stays null", () => {
  // Given: a 10% one-day gain whose annualized root exceeds the safety cap.
  const request = noStopRequest();

  // When: the browser calculator cannot safely bracket the root.
  const [result] = runCalculator(
    [["2024-01-02", 100], ["2024-01-03", 110]],
    request,
  );

  // Then: convergence failure is explicit rather than a capped rate.
  assert.equal(result.summary.xirr, null);
});

test("near-total loss returns a finite negative XIRR", () => {
  const request = parseRequest({
    startDate: "2020-01-01",
    endDate: "2020-01-31",
    rows: [{
      id: "loss",
      name: "loss",
      contributionAmount: "100",
      cadence: "monthly",
      stopFamily: "none",
      targetReturn: "",
      trailingDrawdown: "",
      saleFraction: "",
      recycleProceeds: false,
    }],
  }, ["2020-01-01", "2020-01-31"]);

  const [result] = runCalculator(
    [["2020-01-01", 100], ["2020-01-31", 40]],
    request,
  );

  assert.ok(Number.isFinite(result.summary.xirr));
  assert.ok(result.summary.xirr < -0.9999);
});
