"use strict";

(function exposeCalculatorCore(root) {
  class CalculatorValidationError extends Error {
    constructor(field, reason) {
      super(`${field}: ${reason}`);
      this.name = "CalculatorValidationError";
      this.field = field;
      this.reason = reason;
    }
  }

  const CADENCES = new Set(["daily", "weekly", "biweekly", "monthly", "quarterly"]);
  const STOP_FAMILIES = new Set(["none", "target_return", "trailing_drawdown"]);
  const XIRR_MAX_RATE = 1000000000000;

  function parseIsoDate(value, field) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value))
      throw new CalculatorValidationError(field, "请输入有效的 YYYY-MM-DD 日期");
    const parsed = new Date(`${value}T00:00:00Z`);
    if (!Number.isFinite(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== value)
      throw new CalculatorValidationError(field, "请输入有效日期");
    return value;
  }

  function parseDecimal(value, field, minimum, maximum, decimals) {
    const text = String(value).trim();
    if (!new RegExp(`^\\d+(?:\\.\\d{1,${decimals}})?$`).test(text))
      throw new CalculatorValidationError(field, `最多保留 ${decimals} 位小数`);
    const number = Number(text);
    if (!Number.isFinite(number) || number < minimum || number > maximum)
      throw new CalculatorValidationError(field, `必须在 ${minimum} 至 ${maximum} 之间`);
    return number;
  }

  function parseRow(input, index) {
    const prefix = `rows.${index}`;
    const name = String(input.name || "").trim();
    if (!name) throw new CalculatorValidationError(`${prefix}.name`, "请输入方案名称");
    const contributionAmount = parseDecimal(
      input.contributionAmount, `${prefix}.contributionAmount`, 1, 10000000, 2,
    );
    if (!CADENCES.has(input.cadence))
      throw new CalculatorValidationError(`${prefix}.cadence`, "未知定投频率");
    if (!STOP_FAMILIES.has(input.stopFamily))
      throw new CalculatorValidationError(`${prefix}.stopFamily`, "未知止盈策略");
    const row = {
      id: String(input.id || `series-${index + 1}`),
      name,
      contributionAmount,
      cadence: input.cadence,
      stopFamily: input.stopFamily,
      targetReturn: null,
      trailingDrawdown: null,
      saleFraction: null,
      recycleProceeds: false,
    };
    if (input.stopFamily === "none") return Object.freeze(row);
    row.targetReturn = parseDecimal(
      input.targetReturn, `${prefix}.targetReturn`, 0.1, 500, 1,
    ) / 100;
    row.saleFraction = parseDecimal(
      input.saleFraction, `${prefix}.saleFraction`, 0.1, 100, 1,
    ) / 100;
    row.recycleProceeds = input.recycleProceeds === true;
    if (input.stopFamily === "trailing_drawdown") {
      row.trailingDrawdown = parseDecimal(
        input.trailingDrawdown, `${prefix}.trailingDrawdown`, 0.1, 99, 1,
      ) / 100;
    }
    return Object.freeze(row);
  }

  function parseRequest(input, requestedCoverage) {
    if (!Array.isArray(requestedCoverage) || requestedCoverage.length !== 2)
      throw new CalculatorValidationError("dateRange", "缺少数据可选日期范围");
    const coverageStart = parseIsoDate(String(requestedCoverage[0]), "dateRange");
    const coverageEnd = parseIsoDate(String(requestedCoverage[1]), "dateRange");
    const startDate = parseIsoDate(String(input.startDate || ""), "startDate");
    const endDate = parseIsoDate(String(input.endDate || ""), "endDate");
    if (startDate > endDate)
      throw new CalculatorValidationError("endDate", "结束日期不能早于开始日期");
    if (startDate < coverageStart)
      throw new CalculatorValidationError("startDate", `不能早于 ${coverageStart}`);
    if (endDate > coverageEnd)
      throw new CalculatorValidationError("endDate", `不能晚于 ${coverageEnd}`);
    if (!Array.isArray(input.rows) || input.rows.length < 1 || input.rows.length > 5)
      throw new CalculatorValidationError("rows", "策略数量必须为一至五个");
    return Object.freeze({
      startDate,
      endDate,
      rows: Object.freeze(input.rows.map(parseRow)),
    });
  }

  function isoWeekKey(isoDate) {
    const date = new Date(`${isoDate}T00:00:00Z`);
    const day = date.getUTCDay() || 7;
    date.setUTCDate(date.getUTCDate() + 4 - day);
    const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
    const week = Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
    return `${date.getUTCFullYear()}-${week}`;
  }

  function contributionDates(dates, cadence) {
    if (!CADENCES.has(cadence))
      throw new CalculatorValidationError("cadence", "未知定投频率");
    if (dates.length === 0) return [];
    const anchor = new Date(`${dates[0]}T00:00:00Z`);
    const keys = dates.map((value, index) => {
      if (cadence === "daily") return index;
      if (cadence === "weekly") return isoWeekKey(value);
      if (cadence === "biweekly") {
        return Math.floor((new Date(`${value}T00:00:00Z`) - anchor) / 1209600000);
      }
      if (cadence === "monthly") return value.slice(0, 7);
      const month = Number(value.slice(5, 7));
      return `${value.slice(0, 4)}-${Math.floor((month - 1) / 3)}`;
    });
    return dates.filter((_, index) => index === 0 || keys[index] !== keys[index - 1]);
  }

  function normalizePrices(prices, request) {
    if (!Array.isArray(prices)) throw new CalculatorValidationError("prices", "价格数据无效");
    let previous = "";
    const selected = prices.filter((item) => {
      if (!Array.isArray(item) || item.length !== 2)
        throw new CalculatorValidationError("prices", "价格记录无效");
      const date = parseIsoDate(String(item[0]), "prices.date");
      const price = Number(item[1]);
      if (date <= previous || !Number.isFinite(price) || price <= 0)
        throw new CalculatorValidationError("prices", "日期须递增且收盘价须为正数");
      previous = date;
      return date >= request.startDate && date <= request.endDate;
    });
    if (selected.length === 0)
      throw new CalculatorValidationError("dateRange", "所选区间没有交易数据");
    return selected;
  }

  const atLeast = (value, threshold) => value >= threshold ||
    Math.abs(value - threshold) <= 1e-12;
  const atMost = (value, threshold) => value <= threshold ||
    Math.abs(value - threshold) <= 1e-12;

  function datedExternalXirr(states, terminalAssets) {
    if (states[0].date === states.at(-1).date) return null;
    const flows = states.filter((state) => state.externalContribution > 0)
      .map((state) => [state.date, -state.externalContribution]);
    flows.push([states.at(-1).date, terminalAssets]);
    if (!flows.some(([, amount]) => amount < 0) ||
        !flows.some(([, amount]) => amount > 0)) return null;
    const origin = new Date(`${flows[0][0]}T00:00:00Z`);
    const xnpv = (rate) => flows.reduce((total, [date, amount]) => {
      const days = (new Date(`${date}T00:00:00Z`) - origin) / 86400000;
      return total + amount / ((1 + rate) ** (days / 365.25));
    }, 0);
    let low = -0.9999, high = 10, npvLow = xnpv(low), npvHigh = xnpv(high);
    if (!Number.isFinite(npvLow) || !Number.isFinite(npvHigh)) return null;
    for (let exponent = 5; exponent <= 12 && npvLow * npvHigh > 0; exponent += 1) {
      const candidate = -(1 - 10 ** -exponent), candidateNpv = xnpv(candidate);
      if (!Number.isFinite(candidateNpv)) break;
      low = candidate;
      npvLow = candidateNpv;
    }
    while (npvLow * npvHigh > 0 && high < XIRR_MAX_RATE) {
      high = Math.min(high * 2, XIRR_MAX_RATE);
      npvHigh = xnpv(high);
      if (!Number.isFinite(npvHigh)) return null;
    }
    if (npvLow * npvHigh > 0) return null;
    for (let iteration = 0; iteration < 256; iteration += 1) {
      const middle = (low + high) / 2, npvMiddle = xnpv(middle);
      if (!Number.isFinite(npvMiddle)) return null;
      if (Math.abs(npvMiddle) < 1e-12 ||
          high - low <= 1e-12 * Math.max(1, Math.abs(middle))) return middle;
      if (npvLow * npvMiddle < 0) high = middle;
      else { low = middle; npvLow = npvMiddle; }
    }
    return null;
  }

  function simulate(prices, config) {
    const scheduledDates = new Set(contributionDates(prices.map(([date]) => date), config.cadence));
    let shares = 0, cycleBasis = 0, reusablePool = 0, reserve = 0;
    let scheduledInvested = 0, externalInvested = 0, trailingPeak = 0;
    let trailingArmed = false, stopCount = 0, nav = 1, navPeak = 1;
    let maximumDrawdown = 0, priorAssets = 0, marketDays = 0;
    const dailyStates = [], events = [];
    for (const [date, rawPrice] of prices) {
      const price = Number(rawPrice);
      const holdingBeforeFlow = shares * price;
      const targetReached = shares > 0 && atLeast(
        holdingBeforeFlow / cycleBasis - 1,
        config.targetReturn || 0,
      );
      let sell = config.stopFamily === "target_return" && targetReached;
      if (config.stopFamily === "trailing_drawdown") {
        if (trailingArmed) {
          trailingPeak = Math.max(trailingPeak, price);
          sell = atMost(price / trailingPeak - 1, -config.trailingDrawdown);
        } else if (targetReached) {
          trailingArmed = true;
          trailingPeak = price;
          events.push({ date, type: "stop_activation", amount: 0, shares: 0, price });
        }
      }
      if (sell) {
        const soldShares = shares * config.saleFraction;
        const proceeds = soldShares * price;
        shares -= soldShares;
        cycleBasis = shares * price;
        if (config.recycleProceeds) reusablePool += proceeds;
        else reserve += proceeds;
        trailingArmed = false;
        trailingPeak = 0;
        stopCount += 1;
        events.push({ date, type: "sale", amount: proceeds, shares: soldShares, price });
      }
      const scheduledContribution = scheduledDates.has(date) ? config.contributionAmount : 0;
      const poolContribution = Math.min(reusablePool, scheduledContribution);
      const externalContribution = scheduledContribution - poolContribution;
      if (scheduledContribution > 0) {
        reusablePool -= poolContribution;
        const sharesBought = scheduledContribution / price;
        shares += sharesBought;
        cycleBasis += scheduledContribution;
        scheduledInvested += scheduledContribution;
        externalInvested += externalContribution;
        events.push({ date, type: "contribution", amount: scheduledContribution, shares: sharesBought, price });
      }
      const holdingValue = shares * price;
      const totalAssets = holdingValue + reusablePool + reserve;
      if (priorAssets > 0) nav *= (totalAssets - externalContribution) / priorAssets;
      navPeak = Math.max(navPeak, nav);
      maximumDrawdown = Math.min(maximumDrawdown, nav / navPeak - 1);
      marketDays += Number(shares > 0);
      dailyStates.push({
        date, price, scheduledContribution, externalContribution, poolContribution,
        shares, cycleBasis, reusablePool, reserve, holdingValue, totalAssets, nav,
      });
      priorAssets = totalAssets;
    }
    const final = dailyStates.at(-1);
    const totalProfit = final.totalAssets - externalInvested;
    return {
      config, dailyStates, events,
      summary: {
        scheduledInvested, externalInvested, endingHoldings: final.holdingValue,
        reusablePool: final.reusablePool, reserve: final.reserve,
        totalAssets: final.totalAssets, totalProfit,
        cumulativeReturn: totalProfit / externalInvested,
        xirr: datedExternalXirr(dailyStates, final.totalAssets),
        maximumDrawdown, timeInMarket: marketDays / dailyStates.length, stopCount,
      },
    };
  }

  function runCalculator(prices, request) {
    const selected = normalizePrices(prices, request);
    return request.rows.map((row) => simulate(selected, row));
  }

  const api = Object.freeze(
    { CalculatorValidationError, contributionDates, parseRequest, runCalculator },
  );
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.CalculatorCore = api;
})(typeof globalThis === "undefined" ? this : globalThis);
