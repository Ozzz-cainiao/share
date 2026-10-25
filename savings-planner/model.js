// All amounts are yuan. Annual return is an effective annual rate.
export const MAX_MONTHS = 1200;
export function monthIndex(month) {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) throw new Error('月份格式应为 YYYY-MM');
  return Number(month.slice(0, 4)) * 12 + Number(month.slice(5)) - 1;
}
export function addMonths(month, count) {
  const index = monthIndex(month) + count;
  return `${String(Math.floor(index / 12)).padStart(4, '0')}-${String(index % 12 + 1).padStart(2, '0')}`;
}
export function balanceAt(initial, monthly, annual, months) {
  const rate = Math.expm1(Math.log1p(annual / 100) / 12);
  return Math.abs(rate) < 1e-12 ? initial + monthly * months
    : initial * (1 + rate) ** months + monthly * Math.expm1(months * Math.log1p(rate)) / rate;
}
export function project(initial, monthly, annual, target, horizon = MAX_MONTHS) {
  if (initial >= target) return {months: 0, balance: initial, principal: initial, gain: 0};
  for (let n = 1; n <= horizon; n++) {
    const balance = balanceAt(initial, monthly, annual, n);
    if (balance >= target) return {months: n, balance, principal: initial + monthly * n, gain: balance - initial - monthly * n};
  }
  return null;
}
export function validateState(data) {
  if (!data || data.version !== 1 || !data.plan || !Array.isArray(data.records)) throw new Error('不是有效的攒钱计划备份');
  const p = data.plan;
  const bounds = {initial: [0, 1e12], target: [1, 1e12], monthly: [0, 1e8], extra: [0, 1e8], annual: [-99, 100], compareAnnual: [-99, 100], withdrawal: [0, 20], salary: [0, 1e8], cashIncome: [0, 1e8]};
  for (const [key, [min, max]] of Object.entries(bounds)) {
    if (typeof p[key] !== 'number' || !Number.isFinite(p[key]) || p[key] < min || p[key] > max) throw new Error(`参数 ${key} 超出允许范围`);
  }
  monthIndex(p.start);
  if (p.start < '1900-01' || p.start > '2200-12') throw new Error('计划月份需在 1900 至 2200 年之间');
  if (!Array.isArray(p.expenses) || p.expenses.length !== 5 || p.expenses.some(x => !Number.isFinite(x) || x < 0 || x > 1e8)) throw new Error('支出数据无效');
  const months = new Set();
  if (data.records.length > MAX_MONTHS) throw new Error('记录数量过多');
  for (const record of data.records) {
    const index = monthIndex(record.month);
    if (index < monthIndex(p.start) || index >= monthIndex(p.start) + MAX_MONTHS || months.has(record.month)) throw new Error('记录月份重复或不在计划的 100 年范围内');
    months.add(record.month);
    if (![record.contribution, record.balance].every(n => typeof n === 'number' && Number.isFinite(n) && n >= 0 && n <= 1e12)) throw new Error('记录金额无效');
  }
  return data;
}
