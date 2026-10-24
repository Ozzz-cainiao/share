"use strict";

// 上海参数集中配置。页面高级设置可以覆盖基数上下限。
const POLICY_PERIOD = "社保 2026.7 起 · 公积金采用最新已公布参数";
const SOCIAL_SECURITY_MIN_BASE = 7546;
const SOCIAL_SECURITY_MAX_BASE = 37731;
const HOUSING_FUND_MIN_BASE = 2690;
const HOUSING_FUND_MAX_BASE = 37302;
const PENSION_RATE = 0.08;
const MEDICAL_RATE = 0.02;
const UNEMPLOYMENT_RATE = 0.005;
const HOUSING_FUND_RATE = 0.12;
const ANNUAL_BASIC_DEDUCTION = 60000;
const DEFAULT_WORKING_WEEKS = 52;

const WORK_SCHEDULE_PRESETS = Object.freeze({
  "965": { startTime: "09:00", endTime: "18:00", workdaysPerWeek: 5, lunchBreakHours: 1, dinnerBreakHours: 0 },
  "995": { startTime: "09:00", endTime: "21:00", workdaysPerWeek: 5, lunchBreakHours: 1, dinnerBreakHours: 1 },
  "996": { startTime: "09:00", endTime: "21:00", workdaysPerWeek: 6, lunchBreakHours: 1, dinnerBreakHours: 1 },
  "11116": { startTime: "11:00", endTime: "23:00", workdaysPerWeek: 6, lunchBreakHours: 1, dinnerBreakHours: 1 }
});

const COMPREHENSIVE_TAX_BRACKETS = [
  { upper: 36000, rate: 0.03, quickDeduction: 0 },
  { upper: 144000, rate: 0.10, quickDeduction: 2520 },
  { upper: 300000, rate: 0.20, quickDeduction: 16920 },
  { upper: 420000, rate: 0.25, quickDeduction: 31920 },
  { upper: 660000, rate: 0.30, quickDeduction: 52920 },
  { upper: 960000, rate: 0.35, quickDeduction: 85920 },
  { upper: Infinity, rate: 0.45, quickDeduction: 181920 }
];

// 全年一次性奖金：奖金 ÷ 12 后匹配月度税率档。
const ANNUAL_BONUS_TAX_BRACKETS = [
  { upper: 3000, rate: 0.03, quickDeduction: 0 },
  { upper: 12000, rate: 0.10, quickDeduction: 210 },
  { upper: 25000, rate: 0.20, quickDeduction: 1410 },
  { upper: 35000, rate: 0.25, quickDeduction: 2660 },
  { upper: 55000, rate: 0.30, quickDeduction: 4410 },
  { upper: 80000, rate: 0.35, quickDeduction: 7160 },
  { upper: Infinity, rate: 0.45, quickDeduction: 15160 }
];

const DEFAULT_SETTINGS = Object.freeze({
  socialMinBase: SOCIAL_SECURITY_MIN_BASE,
  socialMaxBase: SOCIAL_SECURITY_MAX_BASE,
  housingMinBase: HOUSING_FUND_MIN_BASE,
  housingMaxBase: HOUSING_FUND_MAX_BASE,
  housingFundRate: HOUSING_FUND_RATE
});

function finiteNonNegative(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, number) : fallback;
}

function optionalNonNegative(value) {
  if (value === undefined || value === null || String(value).trim() === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, number) : null;
}

function clamp(value, min, max) {
  const safeMin = Math.min(min, max);
  const safeMax = Math.max(min, max);
  return Math.min(Math.max(value, safeMin), safeMax);
}

function roundMoney(value) {
  return Math.round((Number(value) + Number.EPSILON) * 100) / 100;
}

function normalizedSettings(settings = {}) {
  const socialMinBase = finiteNonNegative(settings.socialMinBase, DEFAULT_SETTINGS.socialMinBase);
  const socialMaxBase = Math.max(socialMinBase, finiteNonNegative(settings.socialMaxBase, DEFAULT_SETTINGS.socialMaxBase));
  const housingMinBase = finiteNonNegative(settings.housingMinBase, DEFAULT_SETTINGS.housingMinBase);
  const housingMaxBase = Math.max(housingMinBase, finiteNonNegative(settings.housingMaxBase, DEFAULT_SETTINGS.housingMaxBase));
  return {
    socialMinBase,
    socialMaxBase,
    housingMinBase,
    housingMaxBase,
    housingFundRate: Math.min(finiteNonNegative(settings.housingFundRate, DEFAULT_SETTINGS.housingFundRate), 1)
  };
}

function calculateSocialSecurity(monthlySalary, settings = DEFAULT_SETTINGS, declaredBase = null) {
  const salary = finiteNonNegative(monthlySalary);
  const config = normalizedSettings(settings);
  const customBase = optionalNonNegative(declaredBase);
  const contributionBase = clamp(customBase ?? salary, config.socialMinBase, config.socialMaxBase);
  const monthlyAmount = contributionBase * (PENSION_RATE + MEDICAL_RATE + UNEMPLOYMENT_RATE);
  return { contributionBase, declaredBase: customBase, usesCustomBase: customBase !== null, monthlyAmount: roundMoney(monthlyAmount), annualAmount: roundMoney(monthlyAmount * 12) };
}

function calculateHousingFund(monthlySalary, settings = DEFAULT_SETTINGS, declaredBase = null) {
  const salary = finiteNonNegative(monthlySalary);
  const config = normalizedSettings(settings);
  const customBase = optionalNonNegative(declaredBase);
  const contributionBase = clamp(customBase ?? salary, config.housingMinBase, config.housingMaxBase);
  const monthlyAmount = contributionBase * config.housingFundRate;
  return { contributionBase, declaredBase: customBase, usesCustomBase: customBase !== null, monthlyAmount: roundMoney(monthlyAmount), annualAmount: roundMoney(monthlyAmount * 12) };
}

function taxFromBrackets(taxableIncome, brackets) {
  const taxable = Math.max(0, finiteNonNegative(taxableIncome));
  if (taxable === 0) return 0;
  const bracket = brackets.find(item => taxable <= item.upper) || brackets[brackets.length - 1];
  return roundMoney(Math.max(0, taxable * bracket.rate - bracket.quickDeduction));
}

function calculateAnnualComprehensiveTax(annualIncome, annualSocialSecurity = 0, annualHousingFund = 0, annualSpecialDeduction = 0) {
  const taxableIncome = Math.max(0,
    finiteNonNegative(annualIncome) -
    finiteNonNegative(annualSocialSecurity) -
    finiteNonNegative(annualHousingFund) -
    finiteNonNegative(annualSpecialDeduction) -
    ANNUAL_BASIC_DEDUCTION
  );
  return { taxableIncome: roundMoney(taxableIncome), tax: taxFromBrackets(taxableIncome, COMPREHENSIVE_TAX_BRACKETS) };
}

function calculateAnnualBonusTax(bonus) {
  const safeBonus = finiteNonNegative(bonus);
  if (safeBonus === 0) return { monthlyEquivalent: 0, rate: 0, quickDeduction: 0, tax: 0 };
  const monthlyEquivalent = safeBonus / 12;
  const bracket = ANNUAL_BONUS_TAX_BRACKETS.find(item => monthlyEquivalent <= item.upper) || ANNUAL_BONUS_TAX_BRACKETS.at(-1);
  return {
    monthlyEquivalent: roundMoney(monthlyEquivalent),
    rate: bracket.rate,
    quickDeduction: bracket.quickDeduction,
    tax: roundMoney(Math.max(0, safeBonus * bracket.rate - bracket.quickDeduction))
  };
}

function calculateIncome(input = {}) {
  const monthlySalary = finiteNonNegative(input.monthlySalary);
  const bonus = finiteNonNegative(input.bonus);
  const monthlySpecialDeduction = finiteNonNegative(input.monthlySpecialDeduction);
  const socialSecurityBaseInput = optionalNonNegative(input.socialSecurityBase);
  const housingFundBaseInput = optionalNonNegative(input.housingFundBase);
  const settings = normalizedSettings(input.settings);
  const annualBaseSalary = roundMoney(monthlySalary * 12);
  const annualGrossIncome = roundMoney(annualBaseSalary + bonus);
  const social = calculateSocialSecurity(monthlySalary, settings, socialSecurityBaseInput);
  const housing = calculateHousingFund(monthlySalary, settings, housingFundBaseInput);
  const annualSpecialDeduction = roundMoney(monthlySpecialDeduction * 12);

  const separateComprehensive = calculateAnnualComprehensiveTax(
    annualBaseSalary, social.annualAmount, housing.annualAmount, annualSpecialDeduction
  );
  const separateBonus = calculateAnnualBonusTax(bonus);
  const separateTotalTax = roundMoney(separateComprehensive.tax + separateBonus.tax);

  const mergedComprehensive = calculateAnnualComprehensiveTax(
    annualGrossIncome, social.annualAmount, housing.annualAmount, annualSpecialDeduction
  );
  const mergedTotalTax = mergedComprehensive.tax;
  const useSeparateBonusTax = separateTotalTax <= mergedTotalTax;
  const comprehensiveTax = useSeparateBonusTax ? separateComprehensive.tax : mergedComprehensive.tax;
  const bonusTax = useSeparateBonusTax ? separateBonus.tax : 0;
  const totalTax = useSeparateBonusTax ? separateTotalTax : mergedTotalTax;
  // 不截断到手金额：极低工资但仍按最低基数缴费时可能为负，保留真实算术结果，
  // 以确保“现金 + 税 + 社保 + 公积金 = 税前收入”始终成立。
  const annualCashIncome = roundMoney(annualGrossIncome - social.annualAmount - housing.annualAmount - totalTax);

  return {
    monthlySalary,
    annualBaseSalary,
    bonus,
    annualGrossIncome,
    annualSocialSecurity: social.annualAmount,
    annualHousingFund: housing.annualAmount,
    comprehensiveTax,
    bonusTax,
    totalTax,
    annualCashIncome,
    averageMonthlyCashIncome: roundMoney(annualCashIncome / 12),
    annualPersonalAssetIncrease: roundMoney(annualCashIncome + housing.annualAmount),
    socialSecurityBase: social.contributionBase,
    housingFundBase: housing.contributionBase,
    socialSecurityBaseInput,
    housingFundBaseInput,
    usesCustomSocialSecurityBase: social.usesCustomBase,
    usesCustomHousingFundBase: housing.usesCustomBase,
    monthlySocialSecurity: social.monthlyAmount,
    monthlyHousingFund: housing.monthlyAmount,
    separateComprehensiveTax: separateComprehensive.tax,
    separateBonusTax: separateBonus.tax,
    separateTotalTax,
    mergedTotalTax,
    taxDifference: roundMoney(Math.abs(separateTotalTax - mergedTotalTax)),
    recommendedScheme: useSeparateBonusTax ? "separate" : "merged",
    taxableIncome: useSeparateBonusTax ? separateComprehensive.taxableIncome : mergedComprehensive.taxableIncome
  };
}

function calculateMarginalIncome(input = {}, increment = 1000) {
  const safeIncrement = finiteNonNegative(increment, 1000) || 1000;
  const current = calculateIncome(input);
  const increased = calculateIncome({ ...input, monthlySalary: finiteNonNegative(input.monthlySalary) + safeIncrement });
  const delta = (key) => roundMoney(increased[key] - current[key]);
  const annualSalaryIncrease = roundMoney(safeIncrement * 12);
  const annualCashIncrease = delta("annualCashIncome");
  const annualAssetIncrease = delta("annualPersonalAssetIncrease");
  return {
    increment: safeIncrement,
    annualGrossIncrease: delta("annualGrossIncome"),
    annualSalaryIncrease,
    taxIncrease: delta("totalTax"),
    socialSecurityIncrease: delta("annualSocialSecurity"),
    housingFundIncrease: delta("annualHousingFund"),
    annualCashIncrease,
    averageMonthlyCashIncrease: delta("averageMonthlyCashIncome"),
    annualAssetIncrease,
    // 转化率按“每月增加 1000 元”对应的全年 12000 元增量计算。
    cashConversionRate: annualSalaryIncrease ? annualCashIncrease / annualSalaryIncrease : 0,
    assetConversionRate: annualSalaryIncrease ? annualAssetIncrease / annualSalaryIncrease : 0,
    current,
    increased
  };
}

function timeToMinutes(value, fallback) {
  const match = String(value || "").match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return fallback;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  return hours >= 0 && hours <= 23 && minutes >= 0 && minutes <= 59 ? hours * 60 + minutes : fallback;
}

function calculateWorkingHours(schedule = {}, workingWeeks = DEFAULT_WORKING_WEEKS) {
  const defaultSchedule = WORK_SCHEDULE_PRESETS["965"];
  const startMinutes = timeToMinutes(schedule.startTime, timeToMinutes(defaultSchedule.startTime, 9 * 60));
  const endMinutes = timeToMinutes(schedule.endTime, timeToMinutes(defaultSchedule.endTime, 18 * 60));
  const elapsedMinutes = endMinutes === startMinutes ? 0 : endMinutes > startMinutes ? endMinutes - startMinutes : endMinutes + 24 * 60 - startMinutes;
  const grossDailyHours = elapsedMinutes / 60;
  const lunchBreakHours = Math.min(finiteNonNegative(schedule.lunchBreakHours, defaultSchedule.lunchBreakHours), 12);
  const dinnerBreakHours = Math.min(finiteNonNegative(schedule.dinnerBreakHours, defaultSchedule.dinnerBreakHours), 12);
  const breakHours = lunchBreakHours + dinnerBreakHours;
  const netDailyHours = Math.max(0, grossDailyHours - breakHours);
  const workdaysPerWeek = Math.min(Math.max(finiteNonNegative(schedule.workdaysPerWeek, 5), 1), 7);
  const safeWorkingWeeks = Math.min(Math.max(finiteNonNegative(workingWeeks, DEFAULT_WORKING_WEEKS), 1), 53);
  const weeklyHours = roundMoney(netDailyHours * workdaysPerWeek);
  return {
    startTime: schedule.startTime || "09:00",
    endTime: schedule.endTime || "18:00",
    grossDailyHours: roundMoney(grossDailyHours),
    breakHours: roundMoney(breakHours),
    netDailyHours: roundMoney(netDailyHours),
    workdaysPerWeek,
    workingWeeks: safeWorkingWeeks,
    weeklyHours,
    annualWorkingHours: roundMoney(weeklyHours * safeWorkingWeeks)
  };
}

function createMarginalMarkGroups(taxNodes, settings, usesCustomSocialBase, usesCustomHousingBase) {
  return {
    socialSecurityCap: usesCustomSocialBase ? [] : [{ xAxis: settings.socialMaxBase, name: "社保封顶" }],
    housingFundCap: usesCustomHousingBase ? [] : [{ xAxis: settings.housingMaxBase, name: "公积金封顶" }],
    taxBrackets: taxNodes.map((node, index) => ({
      xAxis: node,
      name: "税档切换",
      label: { show: index < 2 }
    }))
  };
}

function compareOffers(offerA, offerB, shared = {}) {
  const buildInput = offer => ({
    monthlySalary: finiteNonNegative(offer.monthlySalary),
    bonus: roundMoney(finiteNonNegative(offer.monthlySalary) * finiteNonNegative(offer.bonusMonths)),
    monthlySpecialDeduction: finiteNonNegative(shared.monthlySpecialDeduction),
    socialSecurityBase: optionalNonNegative(shared.socialSecurityBase),
    housingFundBase: optionalNonNegative(shared.housingFundBase),
    settings: shared.settings
  });
  const a = calculateIncome(buildInput(offerA));
  const b = calculateIncome(buildInput(offerB));
  const scheduleA = calculateWorkingHours(offerA.schedule, shared.workingWeeks);
  const scheduleB = calculateWorkingHours(offerB.schedule, shared.workingWeeks);
  a.workSchedule = scheduleA;
  b.workSchedule = scheduleB;
  a.grossHourlyIncome = scheduleA.annualWorkingHours ? roundMoney(a.annualGrossIncome / scheduleA.annualWorkingHours) : 0;
  b.grossHourlyIncome = scheduleB.annualWorkingHours ? roundMoney(b.annualGrossIncome / scheduleB.annualWorkingHours) : 0;
  a.cashHourlyIncome = scheduleA.annualWorkingHours ? roundMoney(a.annualCashIncome / scheduleA.annualWorkingHours) : 0;
  b.cashHourlyIncome = scheduleB.annualWorkingHours ? roundMoney(b.annualCashIncome / scheduleB.annualWorkingHours) : 0;
  a.assetHourlyIncome = scheduleA.annualWorkingHours ? roundMoney(a.annualPersonalAssetIncrease / scheduleA.annualWorkingHours) : 0;
  b.assetHourlyIncome = scheduleB.annualWorkingHours ? roundMoney(b.annualPersonalAssetIncrease / scheduleB.annualWorkingHours) : 0;
  const difference = {};
  ["annualGrossIncome", "annualCashIncome", "annualHousingFund", "annualPersonalAssetIncrease", "totalTax", "averageMonthlyCashIncome", "grossHourlyIncome", "cashHourlyIncome", "assetHourlyIncome"].forEach(key => {
    difference[key] = roundMoney(b[key] - a[key]);
  });
  difference.annualWorkingHours = roundMoney(scheduleB.annualWorkingHours - scheduleA.annualWorkingHours);
  difference.cashConversionRate = difference.annualGrossIncome
    ? difference.annualCashIncome / difference.annualGrossIncome
    : 0;
  difference.cashHourlyChangeRate = a.cashHourlyIncome
    ? difference.cashHourlyIncome / a.cashHourlyIncome
    : 0;
  return { a, b, difference };
}

function formatMoney(value, digits = 0) {
  const safe = Number.isFinite(Number(value)) ? Number(value) : 0;
  const sign = safe < 0 ? "−" : "";
  return `${sign}¥${Math.abs(safe).toLocaleString("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

function formatDelta(value) {
  const safe = Number.isFinite(Number(value)) ? Number(value) : 0;
  if (Math.abs(safe) < 0.005) return "¥0";
  return `${safe > 0 ? "+" : "−"}¥${Math.abs(safe).toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`;
}

function formatPercent(value) {
  const safe = Number.isFinite(Number(value)) ? Number(value) : 0;
  return `${(safe * 100).toFixed(1)}%`;
}

function formatWan(value) {
  const safe = Number(value) || 0;
  const sign = safe < 0 ? "−" : "";
  return `${sign}${(Math.abs(safe) / 10000).toFixed(1)} 万元`;
}

function formatHours(value) {
  const safe = Number.isFinite(Number(value)) ? Number(value) : 0;
  return `${safe.toLocaleString("zh-CN", { maximumFractionDigits: 1 })} 小时`;
}

function formatHourDelta(value) {
  const safe = Number.isFinite(Number(value)) ? Number(value) : 0;
  if (Math.abs(safe) < 0.005) return "0 小时";
  return `${safe > 0 ? "+" : "−"}${Math.abs(safe).toLocaleString("zh-CN", { maximumFractionDigits: 1 })} 小时`;
}

function formatHourlyMoney(value) {
  return `${formatMoney(value, 2)} / 小时`;
}

function formatHourlyDelta(value) {
  return `${formatDelta(value)} / 小时`;
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    const byId = id => document.getElementById(id);
    const inputIds = ["monthlySalary", "bonusMonths", "bonusAmount", "monthlySpecialDeduction", "socialSecurityBase", "housingFundBase", "housingFundRate", "socialMinBase", "socialMaxBase", "housingMinBase", "housingMaxBase"];
    const offerMoneyInputIds = ["offerASalary", "offerABonusMonths", "offerBSalary", "offerBBonusMonths", "workingWeeks"];
    const offerScheduleFieldNames = ["StartTime", "EndTime", "Workdays", "LunchBreak", "DinnerBreak"];
    let bonusUpdateSource = "months";
    let chartInstances = [];

    function setDefaultBaseInputs() {
      byId("socialMinBase").value = SOCIAL_SECURITY_MIN_BASE;
      byId("socialMaxBase").value = SOCIAL_SECURITY_MAX_BASE;
      byId("housingMinBase").value = HOUSING_FUND_MIN_BASE;
      byId("housingMaxBase").value = HOUSING_FUND_MAX_BASE;
    }

    function readSettings() {
      return normalizedSettings({
        socialMinBase: byId("socialMinBase").value,
        socialMaxBase: byId("socialMaxBase").value,
        housingMinBase: byId("housingMinBase").value,
        housingMaxBase: byId("housingMaxBase").value,
        housingFundRate: finiteNonNegative(byId("housingFundRate").value) / 100
      });
    }

    function readMainInput() {
      return {
        monthlySalary: finiteNonNegative(byId("monthlySalary").value),
        bonus: finiteNonNegative(byId("bonusAmount").value),
        monthlySpecialDeduction: finiteNonNegative(byId("monthlySpecialDeduction").value),
        socialSecurityBase: optionalNonNegative(byId("socialSecurityBase").value),
        housingFundBase: optionalNonNegative(byId("housingFundBase").value),
        settings: readSettings()
      };
    }

    function setText(id, text) { byId(id).textContent = text; }

    function syncBonusFromMonths() {
      bonusUpdateSource = "months";
      const value = roundMoney(finiteNonNegative(byId("monthlySalary").value) * finiteNonNegative(byId("bonusMonths").value));
      byId("bonusAmount").value = value;
    }

    function syncMonthsFromBonus() {
      bonusUpdateSource = "amount";
      const salary = finiteNonNegative(byId("monthlySalary").value);
      const months = salary > 0 ? finiteNonNegative(byId("bonusAmount").value) / salary : 0;
      byId("bonusMonths").value = Math.round(months * 100) / 100;
    }

    function updateResults(result, marginal) {
      const socialWasClamped = result.usesCustomSocialSecurityBase && result.socialSecurityBase !== result.socialSecurityBaseInput;
      const housingWasClamped = result.usesCustomHousingFundBase && result.housingFundBase !== result.housingFundBaseInput;
      setText("socialBaseHint", result.usesCustomSocialSecurityBase
        ? `实际按 ${formatMoney(result.socialSecurityBase)} 计算${socialWasClamped ? "（已按上下限校准）" : ""}`
        : `当前按月薪校准为 ${formatMoney(result.socialSecurityBase)}`);
      setText("housingBaseHint", result.usesCustomHousingFundBase
        ? `实际按 ${formatMoney(result.housingFundBase)} 计算${housingWasClamped ? "（已按上下限校准）" : ""}`
        : `当前按月薪校准为 ${formatMoney(result.housingFundBase)}`);
      setText("recommendation", `推荐方案：${result.recommendedScheme === "separate" ? "年终奖单独计税" : "并入综合所得"}`);
      setText("annualCashIncome", formatMoney(result.annualCashIncome));
      setText("annualAssetIncrease", formatMoney(result.annualPersonalAssetIncrease));
      setText("annualGrossIncome", formatMoney(result.annualGrossIncome));
      setText("averageMonthlyCashIncome", formatMoney(result.averageMonthlyCashIncome));
      setText("totalTax", formatMoney(result.totalTax));
      setText("annualSocialSecurity", formatMoney(result.annualSocialSecurity));
      setText("annualHousingFund", formatMoney(result.annualHousingFund));
      setText("separateTotalTax", formatMoney(result.separateTotalTax));
      setText("separateTaxDetail", `工资个税 ${formatMoney(result.separateComprehensiveTax)} + 奖金个税 ${formatMoney(result.separateBonusTax)}`);
      setText("mergedTotalTax", formatMoney(result.mergedTotalTax));
      setText("taxDifference", formatMoney(result.taxDifference));
      setText("taxSavingText", result.taxDifference < 0.01 ? "两种方案税负相同" : `${result.recommendedScheme === "separate" ? "单独计税" : "并入综合所得"}更省税`);

      setText("marginalCash", formatMoney(marginal.averageMonthlyCashIncrease));
      setText("cashConversionRate", formatPercent(marginal.cashConversionRate));
      setText("assetConversionRate", formatPercent(marginal.assetConversionRate));
      setText("deltaGross", formatDelta(marginal.annualGrossIncrease));
      setText("deltaTax", formatDelta(marginal.taxIncrease));
      setText("deltaSocial", formatDelta(marginal.socialSecurityIncrease));
      setText("deltaHousing", formatDelta(marginal.housingFundIncrease));
      setText("deltaMonthlyCash", formatDelta(marginal.averageMonthlyCashIncrease));
      setText("deltaAsset", formatDelta(marginal.annualAssetIncrease));
      setText("distributionCheck", formatMoney(result.annualCashIncome + result.totalTax + result.annualSocialSecurity + result.annualHousingFund));
    }

    function updateOfferComparison() {
      const readSchedule = prefix => ({
        startTime: byId(`offer${prefix}StartTime`).value,
        endTime: byId(`offer${prefix}EndTime`).value,
        workdaysPerWeek: byId(`offer${prefix}Workdays`).value,
        lunchBreakHours: byId(`offer${prefix}LunchBreak`).value,
        dinnerBreakHours: byId(`offer${prefix}DinnerBreak`).value
      });
      const comparison = compareOffers(
        { monthlySalary: byId("offerASalary").value, bonusMonths: byId("offerABonusMonths").value, schedule: readSchedule("A") },
        { monthlySalary: byId("offerBSalary").value, bonusMonths: byId("offerBBonusMonths").value, schedule: readSchedule("B") },
        {
          monthlySpecialDeduction: byId("monthlySpecialDeduction").value,
          socialSecurityBase: byId("socialSecurityBase").value,
          housingFundBase: byId("housingFundBase").value,
          workingWeeks: byId("workingWeeks").value,
          settings: readSettings()
        }
      );
      const rows = [
        { label: "税前年包", key: "annualGrossIncome", format: formatMoney, deltaFormat: formatDelta },
        { label: "全年现金到手", key: "annualCashIncome", format: formatMoney, deltaFormat: formatDelta },
        { label: "全年个人公积金", key: "annualHousingFund", format: formatMoney, deltaFormat: formatDelta },
        { label: "全年个人资产增加", key: "annualPersonalAssetIncrease", format: formatMoney, deltaFormat: formatDelta },
        { label: "全年个人所得税", key: "totalTax", format: formatMoney, deltaFormat: formatDelta },
        { label: "平均月到手", key: "averageMonthlyCashIncome", format: formatMoney, deltaFormat: formatDelta },
        { label: "预计年工作时长", key: "annualWorkingHours", format: formatHours, deltaFormat: formatHourDelta, scheduleValue: true },
        { label: "税前时薪", key: "grossHourlyIncome", format: formatHourlyMoney, deltaFormat: formatHourlyDelta },
        { label: "税后现金时薪", key: "cashHourlyIncome", format: formatHourlyMoney, deltaFormat: formatHourlyDelta },
        { label: "个人资产时薪", key: "assetHourlyIncome", format: formatHourlyMoney, deltaFormat: formatHourlyDelta }
      ];
      byId("offerTableBody").innerHTML = rows.map(row => {
        const aValue = row.scheduleValue ? comparison.a.workSchedule[row.key] : comparison.a[row.key];
        const bValue = row.scheduleValue ? comparison.b.workSchedule[row.key] : comparison.b[row.key];
        return `<tr${row.key === "cashHourlyIncome" ? ' class="highlight-row"' : ""}><td>${row.label}</td><td>${row.format(aValue)}</td><td>${row.format(bValue)}</td><td>${row.deltaFormat(comparison.difference[row.key])}</td></tr>`;
      }
      ).join("");
      const d = comparison.difference;
      const direction = d.annualGrossIncome >= 0 ? "增加" : "减少";
      const cashDirection = d.annualCashIncome >= 0 ? "增加" : "减少";
      const conversionText = d.annualGrossIncome === 0 ? "税前年包相同" : `实际现金转化率约 ${formatPercent(Math.abs(d.cashConversionRate))}`;
      const hourlyDirection = d.cashHourlyIncome >= 0 ? "上涨" : "下降";
      const hourlyRate = comparison.a.cashHourlyIncome ? formatPercent(Math.abs(d.cashHourlyChangeRate)) : "无法比较";
      setText("offerAScheduleSummary", `每天净工作 ${comparison.a.workSchedule.netDailyHours} 小时 · 每周 ${comparison.a.workSchedule.weeklyHours} 小时 · 年约 ${formatHours(comparison.a.workSchedule.annualWorkingHours)}`);
      setText("offerBScheduleSummary", `每天净工作 ${comparison.b.workSchedule.netDailyHours} 小时 · 每周 ${comparison.b.workSchedule.weeklyHours} 小时 · 年约 ${formatHours(comparison.b.workSchedule.annualWorkingHours)}`);
      setText("offerSummary", `Offer B 相比 Offer A，税前年包${direction} ${formatWan(Math.abs(d.annualGrossIncome))}，全年现金到手${cashDirection}约 ${formatWan(Math.abs(d.annualCashIncome))}，${conversionText}；税后现金时薪为 ${formatHourlyMoney(comparison.b.cashHourlyIncome)}，${hourlyDirection} ${hourlyRate}。`);
    }

    function applySchedulePreset(prefix) {
      const presetName = byId(`offer${prefix}SchedulePreset`).value;
      const preset = WORK_SCHEDULE_PRESETS[presetName];
      if (!preset) return;
      byId(`offer${prefix}StartTime`).value = preset.startTime;
      byId(`offer${prefix}EndTime`).value = preset.endTime;
      byId(`offer${prefix}Workdays`).value = preset.workdaysPerWeek;
      byId(`offer${prefix}LunchBreak`).value = preset.lunchBreakHours;
      byId(`offer${prefix}DinnerBreak`).value = preset.dinnerBreakHours;
      updateOfferComparison();
    }

    function chartTheme() {
      const style = getComputedStyle(document.documentElement);
      return {
        ink: style.getPropertyValue("--ink").trim(),
        muted: style.getPropertyValue("--muted").trim(),
        line: style.getPropertyValue("--line").trim(),
        surface: style.getPropertyValue("--surface").trim(),
        accent: style.getPropertyValue("--accent").trim(),
        blue: style.getPropertyValue("--blue").trim(),
        orange: style.getPropertyValue("--orange").trim(),
        red: style.getPropertyValue("--red").trim()
      };
    }

    function commonChartOptions(title, theme) {
      return {
        animationDuration: 350,
        backgroundColor: "transparent",
        title: { text: title, left: 10, top: 8, textStyle: { color: theme.ink, fontSize: 16, fontWeight: 650 } },
        legend: { top: 44, left: 6, textStyle: { color: theme.muted } },
        tooltip: { trigger: "axis", backgroundColor: theme.surface, borderColor: theme.line, textStyle: { color: theme.ink }, valueFormatter: value => formatMoney(value, 2) },
        grid: { left: 18, right: 22, top: 88, bottom: 18, containLabel: true },
        xAxis: { type: "value", min: 5000, max: 100000, interval: 10000, axisLabel: { color: theme.muted, formatter: value => `${value / 1000}k` }, axisLine: { lineStyle: { color: theme.line } }, splitLine: { show: false } },
        yAxis: { type: "value", axisLabel: { color: theme.muted, formatter: value => `${Math.round(value / 1000)}k` }, splitLine: { lineStyle: { color: theme.line, type: "dashed" } } }
      };
    }

    function findTaxThresholdNodes(bonusMonths, monthlySpecialDeduction, settings, socialSecurityBase, housingFundBase) {
      const nodes = [];
      let previousBracket = -1;
      for (let salary = 5000; salary <= 100000; salary += 100) {
        const result = calculateIncome({ monthlySalary: salary, bonus: salary * bonusMonths, monthlySpecialDeduction, socialSecurityBase, housingFundBase, settings });
        const bracket = COMPREHENSIVE_TAX_BRACKETS.findIndex(item => result.taxableIncome <= item.upper);
        if (previousBracket >= 0 && bracket > previousBracket) nodes.push(salary);
        previousBracket = bracket;
      }
      return nodes.slice(0, 4);
    }

    function updateCharts(result) {
      if (typeof echarts === "undefined") return;
      const theme = chartTheme();
      const settings = readSettings();
      const bonusMonths = finiteNonNegative(byId("bonusMonths").value);
      const deduction = finiteNonNegative(byId("monthlySpecialDeduction").value);
      const socialSecurityBase = optionalNonNegative(byId("socialSecurityBase").value);
      const housingFundBase = optionalNonNegative(byId("housingFundBase").value);
      const salaries = [];
      const gross = [], cash = [], housing = [], tax = [];
      const marginalCash = [], marginalHousing = [], marginalTax = [], marginalSocial = [];
      for (let salary = 5000; salary <= 100000; salary += 1000) {
        const input = { monthlySalary: salary, bonus: salary * bonusMonths, monthlySpecialDeduction: deduction, socialSecurityBase, housingFundBase, settings };
        const item = calculateIncome(input);
        const delta = calculateMarginalIncome(input);
        salaries.push(salary);
        gross.push([salary, salary]);
        cash.push([salary, item.averageMonthlyCashIncome]);
        housing.push([salary, item.monthlyHousingFund]);
        tax.push([salary, item.totalTax / 12]);
        marginalCash.push([salary, delta.annualCashIncrease / 12]);
        marginalHousing.push([salary, delta.housingFundIncrease / 12]);
        marginalTax.push([salary, delta.taxIncrease / 12]);
        marginalSocial.push([salary, delta.socialSecurityIncrease / 12]);
      }

      chartInstances.forEach(instance => instance.dispose());
      const incomeChart = echarts.init(byId("incomeChart"));
      const marginalChart = echarts.init(byId("marginalChart"));
      const distributionChart = echarts.init(byId("distributionChart"));
      chartInstances = [incomeChart, marginalChart, distributionChart];

      incomeChart.setOption({
        ...commonChartOptions("税前月薪 vs 月均现金到手", theme),
        color: [theme.ink, theme.accent, theme.blue, theme.orange],
        series: [
          { name: "税前月薪", type: "line", showSymbol: false, data: gross, lineStyle: { width: 2 } },
          { name: "月均现金到手", type: "line", showSymbol: false, data: cash, lineStyle: { width: 4 } },
          { name: "月均个人公积金", type: "line", showSymbol: false, data: housing, lineStyle: { width: 2 } },
          { name: "月均个人所得税", type: "line", showSymbol: false, data: tax, lineStyle: { width: 2 } }
        ]
      });

      const taxNodes = findTaxThresholdNodes(bonusMonths, deduction, settings, socialSecurityBase, housingFundBase);
      const markGroups = createMarginalMarkGroups(
        taxNodes,
        settings,
        socialSecurityBase !== null,
        housingFundBase !== null
      );
      marginalChart.setOption({
        ...commonChartOptions("每增加 ¥1,000 工资，我能留下多少？", theme),
        yAxis: { type: "value", axisLabel: { color: theme.muted, formatter: value => `¥${Math.round(value)}` }, splitLine: { lineStyle: { color: theme.line, type: "dashed" } } },
        color: [theme.accent, theme.blue, theme.orange, theme.red],
        series: [
          { name: "新增现金到手", type: "line", showSymbol: false, data: marginalCash, lineStyle: { width: 4 }, areaStyle: { opacity: .12 } },
          {
            name: "新增个人公积金", type: "line", showSymbol: false, data: marginalHousing, lineStyle: { width: 2 },
            markLine: {
              silent: true, symbol: "none",
              lineStyle: { color: "#0284C7", type: "dashed", width: 1.5, opacity: 0.9 },
              label: { formatter: "{b}", position: "insideEndBottom", color: "#0284C7", fontSize: 10, fontWeight: 600 },
              data: markGroups.housingFundCap
            }
          },
          {
            name: "新增个税", type: "line", showSymbol: false, data: marginalTax, lineStyle: { width: 2 },
            markLine: {
              silent: true, symbol: "none",
              lineStyle: { color: "#7C3AED", type: "dashed", width: 1.5, opacity: 0.9 },
              label: { formatter: "{b}", position: "insideMiddleTop", color: "#7C3AED", fontSize: 10, fontWeight: 600 },
              data: markGroups.taxBrackets
            }
          },
          {
            name: "新增社保", type: "line", showSymbol: false, data: marginalSocial, lineStyle: { width: 2 },
            markLine: {
              silent: true, symbol: "none",
              lineStyle: { color: "#DC2626", type: "dashed", width: 1.5, opacity: 0.9 },
              label: { formatter: "{b}", position: "insideEndTop", color: "#DC2626", fontSize: 10, fontWeight: 600 },
              data: markGroups.socialSecurityCap
            }
          }
        ]
      });

      distributionChart.setOption({
        backgroundColor: "transparent",
        color: [theme.accent, theme.orange, theme.red, theme.blue],
        title: { text: "税前年收入如何被分配", left: 10, top: 8, textStyle: { color: theme.ink, fontSize: 16, fontWeight: 650 } },
        tooltip: { trigger: "item", backgroundColor: theme.surface, borderColor: theme.line, textStyle: { color: theme.ink }, formatter: params => `${params.name}<br>${formatMoney(params.value, 2)} · ${params.percent.toFixed(1)}%` },
        legend: { orient: "vertical", right: 10, top: "center", textStyle: { color: theme.muted } },
        series: [{
          type: "pie", radius: ["46%", "68%"], center: ["38%", "56%"], avoidLabelOverlap: true,
          itemStyle: { borderColor: theme.surface, borderWidth: 3, borderRadius: 6 },
          label: { show: false },
          data: [
            { name: "到手现金", value: result.annualCashIncome },
            { name: "个人所得税", value: result.totalTax },
            { name: "个人社保", value: result.annualSocialSecurity },
            { name: "个人公积金", value: result.annualHousingFund }
          ]
        }]
      });
    }

    function updateAll() {
      const input = readMainInput();
      const result = calculateIncome(input);
      const marginal = calculateMarginalIncome(input);
      updateResults(result, marginal);
      updateOfferComparison();
      updateCharts(result);
    }

    setDefaultBaseInputs();
    setText("policyPeriod", POLICY_PERIOD);
    inputIds.forEach(id => byId(id).addEventListener("input", () => {
      if (id === "monthlySalary" && bonusUpdateSource === "months") syncBonusFromMonths();
      if (id === "bonusMonths") syncBonusFromMonths();
      if (id === "bonusAmount") syncMonthsFromBonus();
      updateAll();
    }));
    offerMoneyInputIds.forEach(id => byId(id).addEventListener("input", updateOfferComparison));
    ["A", "B"].forEach(prefix => {
      byId(`offer${prefix}SchedulePreset`).addEventListener("change", () => applySchedulePreset(prefix));
      offerScheduleFieldNames.forEach(fieldName => {
        byId(`offer${prefix}${fieldName}`).addEventListener("input", () => {
          byId(`offer${prefix}SchedulePreset`).value = "custom";
          updateOfferComparison();
        });
      });
    });
    byId("resetDefaults").addEventListener("click", () => {
      setDefaultBaseInputs();
      byId("housingFundRate").value = HOUSING_FUND_RATE * 100;
      updateAll();
    });

    const savedTheme = localStorage.getItem("salary-calculator-theme");
    const initialTheme = savedTheme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.dataset.theme = initialTheme;
    setText("themeToggle", initialTheme === "dark" ? "浅色" : "深色");
    byId("themeToggle").addEventListener("click", () => {
      const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      localStorage.setItem("salary-calculator-theme", next);
      setText("themeToggle", next === "dark" ? "浅色" : "深色");
      updateCharts(calculateIncome(readMainInput()));
    });

    let resizeTimer;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => chartInstances.forEach(instance => instance.resize()), 120);
    });
    updateAll();
  });
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    calculateSocialSecurity,
    calculateHousingFund,
    calculateAnnualComprehensiveTax,
    calculateAnnualBonusTax,
    calculateIncome,
    calculateMarginalIncome,
    compareOffers,
    calculateWorkingHours,
    createMarginalMarkGroups,
    WORK_SCHEDULE_PRESETS,
    DEFAULT_SETTINGS,
    COMPREHENSIVE_TAX_BRACKETS,
    ANNUAL_BONUS_TAX_BRACKETS
  };
}
