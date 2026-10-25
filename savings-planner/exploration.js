export const DEFAULT_GRID = {monthlyMin: 0, monthlyMax: 20000, monthlyStep: 1000, annualMin: 0, annualMax: 12, annualStep: 1};
export function gridAxes(config) {
  const limits = {monthlyMin: [0, 1e8], monthlyMax: [0, 1e8], monthlyStep: [1, 1e8], annualMin: [-99, 100], annualMax: [-99, 100], annualStep: [0.01, 199]};
  for (const [key, [min, max]] of Object.entries(limits)) {
    if (typeof config?.[key] !== 'number' || !Number.isFinite(config[key]) || config[key] < min || config[key] > max) throw new Error('请输入有效的网格范围与步长');
  }
  function axis(min, max, step) {
    if (max < min) throw new Error('最大值不能小于最小值');
    const count = Math.floor((max - min) / step + 1e-8) + 1;
    if (count > 100) throw new Error('单个方向最多 100 格，请增大步长或缩小范围');
    return Array.from({length: count}, (_, i) => Number((min + step * i).toFixed(8)));
  }
  const monthly = axis(config.monthlyMin, config.monthlyMax, config.monthlyStep);
  const annual = axis(config.annualMin, config.annualMax, config.annualStep);
  if (monthly.length * annual.length > 2500) throw new Error('网格最多 2,500 格，请增大步长或缩小范围');
  return {monthly, annual};
}
// Fixed bands make a given completion time retain its color across grid settings.
export const TIME_BANDS = [
  {key: 'fastest', maxMonths: 60, label: '≤ 5 年'},
  {key: 'fast', maxMonths: 120, label: '5–10 年'},
  {key: 'medium', maxMonths: 180, label: '10–15 年'},
  {key: 'long', maxMonths: 240, label: '15–20 年'},
  {key: 'longer', maxMonths: 360, label: '20–30 年'},
  {key: 'longest', maxMonths: Infinity, label: '> 30 年'}
];
export function timeBand(result) {
  return result ? TIME_BANDS.find(band => result.months <= band.maxMonths).key : 'unreachable';
}
