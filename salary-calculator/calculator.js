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

function calculateSocialSecurity(monthlySalary, settings = DEFAULT_SETTINGS) {
  const salary = finiteNonNegative(monthlySalary);
  const config = normalizedSettings(settings);
  const contributionBase = clamp(salary, config.socialMinBase, config.socialMaxBase);
  const monthlyAmount = contributionBase * (PENSION_RATE + MEDICAL_RATE + UNEMPLOYMENT_RATE);
  return { contributionBase, monthlyAmount: roundMoney(monthlyAmount), annualAmount: roundMoney(monthlyAmount * 12) };
}

function calculateHousingFund(monthlySalary, settings = DEFAULT_SETTINGS) {
  const salary = finiteNonNegative(monthlySalary);
  const config = normalizedSettings(settings);
  const contributionBase = clamp(salary, config.housingMinBase, config.housingMaxBase);
  const monthlyAmount = contributionBase * config.housingFundRate;
  return { contributionBase, monthlyAmount: roundMoney(monthlyAmount), annualAmount: roundMoney(monthlyAmount * 12) };
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
  const settings = normalizedSettings(input.settings);
  const annualBaseSalary = roundMoney(monthlySalary * 12);
  const annualGrossIncome = roundMoney(annualBaseSalary + bonus);
  const social = calculateSocialSecurity(monthlySalary, settings);
  const housing = calculateHousingFund(monthlySalary, settings);
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

function compareOffers(offerA, offerB, shared = {}) {
  const buildInput = offer => ({
    monthlySalary: finiteNonNegative(offer.monthlySalary),
    bonus: roundMoney(finiteNonNegative(offer.monthlySalary) * finiteNonNegative(offer.bonusMonths)),
    monthlySpecialDeduction: finiteNonNegative(shared.monthlySpecialDeduction),
    settings: shared.settings
  });
  const a = calculateIncome(buildInput(offerA));
  const b = calculateIncome(buildInput(offerB));
  const difference = {};
  ["annualGrossIncome", "annualCashIncome", "annualHousingFund", "annualPersonalAssetIncrease", "totalTax", "averageMonthlyCashIncome"].forEach(key => {
    difference[key] = roundMoney(b[key] - a[key]);
  });
  difference.cashConversionRate = difference.annualGrossIncome
    ? difference.annualCashIncome / difference.annualGrossIncome
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

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    const byId = id => document.getElementById(id);
    const inputIds = ["monthlySalary", "bonusMonths", "bonusAmount", "monthlySpecialDeduction", "housingFundRate", "socialMinBase", "socialMaxBase", "housingMinBase", "housingMaxBase"];
    const offerInputIds = ["offerASalary", "offerABonusMonths", "offerBSalary", "offerBBonusMonths"];
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
      const comparison = compareOffers(
        { monthlySalary: byId("offerASalary").value, bonusMonths: byId("offerABonusMonths").value },
        { monthlySalary: byId("offerBSalary").value, bonusMonths: byId("offerBBonusMonths").value },
        { monthlySpecialDeduction: byId("monthlySpecialDeduction").value, settings: readSettings() }
      );
      const rows = [
        ["税前年包", "annualGrossIncome"],
        ["全年现金到手", "annualCashIncome"],
        ["全年个人公积金", "annualHousingFund"],
        ["全年个人资产增加", "annualPersonalAssetIncrease"],
        ["全年个人所得税", "totalTax"],
        ["平均月到手", "averageMonthlyCashIncome"]
      ];
      byId("offerTableBody").innerHTML = rows.map(([label, key]) =>
        `<tr><td>${label}</td><td>${formatMoney(comparison.a[key])}</td><td>${formatMoney(comparison.b[key])}</td><td>${formatDelta(comparison.difference[key])}</td></tr>`
      ).join("");
      const d = comparison.difference;
      const direction = d.annualGrossIncome >= 0 ? "增加" : "减少";
      const cashDirection = d.annualCashIncome >= 0 ? "增加" : "减少";
      const conversionText = d.annualGrossIncome === 0 ? "税前年包相同" : `实际现金转化率约 ${formatPercent(Math.abs(d.cashConversionRate))}`;
      setText("offerSummary", `Offer B 相比 Offer A，税前年包${direction} ${formatWan(Math.abs(d.annualGrossIncome))}，全年现金到手${cashDirection}约 ${formatWan(Math.abs(d.annualCashIncome))}，${conversionText}。`);
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

    function findTaxThresholdNodes(bonusMonths, monthlySpecialDeduction, settings) {
      const nodes = [];
      let previousBracket = -1;
      for (let salary = 5000; salary <= 100000; salary += 100) {
        const result = calculateIncome({ monthlySalary: salary, bonus: salary * bonusMonths, monthlySpecialDeduction, settings });
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
      const salaries = [];
      const gross = [], cash = [], housing = [], tax = [];
      const marginalCash = [], marginalHousing = [], marginalTax = [], marginalSocial = [];
      for (let salary = 5000; salary <= 100000; salary += 1000) {
        const input = { monthlySalary: salary, bonus: salary * bonusMonths, monthlySpecialDeduction: deduction, settings };
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

      const taxNodes = findTaxThresholdNodes(bonusMonths, deduction, settings);
      const markData = [
        { xAxis: settings.socialMaxBase, name: "社保封顶", label: { formatter: "社保封顶" } },
        { xAxis: settings.housingMaxBase, name: "公积金封顶", label: { formatter: "公积金封顶", position: "insideEndBottom" } },
        ...taxNodes.map((node, i) => ({ xAxis: node, name: `税档 ${i + 1}`, label: { formatter: "税档切换", show: i < 2 } }))
      ];
      marginalChart.setOption({
        ...commonChartOptions("每增加 ¥1,000 工资，我能留下多少？", theme),
        yAxis: { type: "value", axisLabel: { color: theme.muted, formatter: value => `¥${Math.round(value)}` }, splitLine: { lineStyle: { color: theme.line, type: "dashed" } } },
        color: [theme.accent, theme.blue, theme.orange, theme.red],
        series: [
          { name: "新增现金到手", type: "line", showSymbol: false, data: marginalCash, lineStyle: { width: 4 }, areaStyle: { opacity: .12 }, markLine: { silent: true, symbol: "none", lineStyle: { type: "dashed", color: theme.muted, opacity: .65 }, label: { color: theme.muted, fontSize: 10 }, data: markData } },
          { name: "新增个人公积金", type: "line", showSymbol: false, data: marginalHousing, lineStyle: { width: 2 } },
          { name: "新增个税", type: "line", showSymbol: false, data: marginalTax, lineStyle: { width: 2 } },
          { name: "新增社保", type: "line", showSymbol: false, data: marginalSocial, lineStyle: { width: 2 } }
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
    offerInputIds.forEach(id => byId(id).addEventListener("input", updateOfferComparison));
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
    DEFAULT_SETTINGS,
    COMPREHENSIVE_TAX_BRACKETS,
    ANNUAL_BONUS_TAX_BRACKETS
  };
}
