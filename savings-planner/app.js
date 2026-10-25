import {MAX_MONTHS, addMonths, monthIndex, balanceAt, project, validateState} from './model.js';
import {DEFAULT_GRID, gridAxes, TIME_BANDS, timeBand} from './exploration.js';
const $ = id => document.getElementById(id);
const now = new Date();
const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
const KEY = 'investlab.savings-planner.v1';
const expenseNames = ['话费', '水电煤费', '吃饭', '房租 / 房贷', '其他生活支出'];
const defaults = () => ({version: 1, plan: {initial: 300000, target: 3000000, monthly: 10000, extra: 2000, annual: 6, compareAnnual: 8, start: currentMonth, withdrawal: 3, salary: 20000, cashIncome: 0, expenses: [120, 280, 1800, 2500, 1300]}, records: []});
let state = defaults();
let editing = null;
let gridCacheKey = '';
let gridSelection = null;
let storageBlocked = false;
let corruptStorage = false;
const money = n => '¥' + Math.round(n).toLocaleString('zh-CN');
const wan = n => `${(n / 10000).toLocaleString('zh-CN', {maximumFractionDigits: 1})} 万`;
const duration = n => n === 0 ? '已达标' : `${Math.floor(n / 12) ? `${Math.floor(n / 12)} 年 ` : ''}${n % 12 ? `${n % 12} 个月` : ''}`.trim();
const percent = (n, d) => d > 0 ? `${(n / d * 100).toFixed(1)}%` : '未设置';
const dateText = m => m.replace('-', ' 年 ') + ' 月';
const endMonth = (p, n) => n === 0 ? '起点已达标' : dateText(addMonths(p.start, n - 1));
const resultText = r => r ? duration(r.months) : '100 年内未达标';
function announce(message) { $('message').textContent = message; }
try {
  const saved = localStorage.getItem(KEY);
  if (saved) state = checkedState(JSON.parse(saved));
} catch (error) {
  if (error.name === 'SecurityError') { storageBlocked = true; announce('浏览器禁止本地保存，本次可正常计算，请导出备份保留数据。'); }
  else { corruptStorage = true; announce('原有本地数据无法读取，已保留原数据；当前使用示例。请先导出原始数据或导入有效备份。'); }
}
function checkedState(data) {
  validateState(data);
  if (data.grid) gridAxes(data.grid);
  return data;
}
function persist() {
  if (corruptStorage) { announce('原有数据暂未覆盖。请先导出原始数据，再导入有效备份恢复保存。'); return; }
  try { localStorage.setItem(KEY, JSON.stringify(state)); storageBlocked = false; }
  catch { storageBlocked = true; announce('本地保存失败；当前修改仅在本次页面保留，请导出备份。'); }
}
function success(message) {
  if (!storageBlocked && !corruptStorage) announce(message);
}
function hydrate() {
  const p = state.plan;
  for (const [key, value] of Object.entries(p)) {
    const control = $('plan-form').elements.namedItem(key) || $('coverage-form').elements.namedItem(key);
    if (control) control.value = value;
  }
  p.expenses.forEach((value, i) => { $('coverage-form').elements.namedItem(`expense${i}`).value = value; });
  $('extra').max = Math.max(20000, p.extra);
  $('extra').value = p.extra;
  $('compare-annual').value = p.compareAnnual;
  $('base-annual').value = p.annual;
  for (const key of Object.keys(DEFAULT_GRID)) $('grid-form').elements.namedItem(key).value = (state.grid || DEFAULT_GRID)[key];
  const form = $('record-form');
  form.elements.month.value = currentMonth < p.start ? p.start : currentMonth;
  form.elements.month.min = p.start;
  form.elements.month.max = addMonths(p.start, MAX_MONTHS - 1);
  form.elements.contribution.value = p.monthly;
}
function scenarioResults(p) {
  return [
    {name: '当前计划', monthly: p.monthly, annual: p.annual},
    {name: '增加投入', monthly: p.monthly + p.extra, annual: p.annual},
    {name: '收益率情景', monthly: p.monthly, annual: p.compareAnnual}
  ].map(s => ({...s, result: project(p.initial, s.monthly, s.annual, p.target)}));
}
function metric(label, value, detail) { return `<div class="metric"><div class="label">${label}</div><strong>${value}</strong><small>${detail}</small></div>`; }
function latestRecord() { return [...state.records].sort((a, b) => b.month.localeCompare(a.month))[0]; }
function render() {
  const p = state.plan;
  const scenarios = scenarioResults(p);
  const base = scenarios[0].result, more = scenarios[1].result;
  $('extra-label').textContent = `每月从 ${money(p.monthly)} 增加到 ${money(p.monthly + p.extra)}`;
  $('extra-value').textContent = money(p.extra);
  $('time-saved').textContent = base && more ? (base.months === 0 ? '目标已在起点达成' : base.months === more.months ? '达标月份相同' : `提前 ${duration(base.months - more.months)}`) : more ? `增加投入后，${duration(more.months)}达标` : '100 年内暂未达标';
  $('compare-detail').textContent = base && more ? `同样假设年化 ${p.annual}%，从 ${resultText(base)}缩短到${resultText(more)}。${base.months === more.months && base.months > 0 ? '按整月计算，小幅差异可能未改变达标月份。' : ''}` : `当前计划：${resultText(base)}；增加投入：${resultText(more)}。试着调整投入或目标。`;
  const finish = base ? endMonth(p, base.months) : '100 年内未达标';
  $('summary').innerHTML = metric('当前计划 · 预计达标', resultText(base), finish) + metric('计划起点 · 目标进度', percent(p.initial, p.target), `${wan(p.initial)} / ${wan(p.target)}`) + metric('达标时 · 投入与收益', base ? wan(base.principal) : '—', base ? `原有资产 + 累计投入；投资收益 ${money(base.gain)}` : '当前假设下尚无达标结果');
  $('scenario-rows').innerHTML = scenarios.map((s, i) => `<tr class="${i === 1 ? 'highlight' : ''}"><th scope="row">${s.name}</th><td>${money(s.monthly)}</td><td>${s.annual}%</td><td>${resultText(s.result)}</td><td>${s.result ? endMonth(p, s.result.months) : '—'}</td><td>${money(balanceAt(p.initial, s.monthly, s.annual, 120))}</td></tr>`).join('');
  renderGrid(p);
  renderChart(p, scenarios);
  const milestones = [...new Set([500000, 1000000, 2000000, p.target].filter(v => v <= p.target))].sort((a, b) => a - b);
  $('milestones').innerHTML = milestones.map(target => {
    const r = project(p.initial, p.monthly, p.annual, target);
    return `<div class="milestone ${r?.months === 0 ? 'done' : ''}"><strong>${wan(target)}</strong><small>${resultText(r)}</small><small>${r ? endMonth(p, r.months) : '调整计划试试'}</small></div>`;
  }).join('');
  renderCoverage(p);
  renderRecords(p, base);
}
function renderGrid(p) {
  const config = state.grid || DEFAULT_GRID;
  const cacheKey = JSON.stringify([p.initial, p.target, p.monthly, p.annual, config]);
  if (cacheKey === gridCacheKey) return;
  gridCacheKey = cacheKey;
  const axes = gridAxes(config);
  $('grid-context').textContent = `起始资产 ${money(p.initial)} → 目标 ${money(p.target)}；${axes.monthly.length} 列 × ${axes.annual.length} 行。起始资产与目标可在上方「我的计划」设置。`;
  $('grid-head').innerHTML = '<tr><th scope="col">年化 ↓ / 月投 →</th>' + axes.monthly.map(value => `<th scope="col">${money(value)}</th>`).join('') + '</tr>';
  const rows = [...axes.annual].reverse().map(annual => ({annual, cells: axes.monthly.map(monthly => ({monthly, result: project(p.initial, monthly, annual, p.target)}))}));
  $('heat-key').innerHTML = TIME_BANDS.map(band => `<span><i class="heat-swatch heat-${band.key}"></i>${band.label}</span>`).join('') + '<span><i class="heat-swatch heat-unreachable"></i>— 100 年内未达标</span><span>◎ 当前基准</span>';
  $('grid-body').innerHTML = rows.map(row => `<tr><th scope="row">${row.annual}%</th>${row.cells.map(cell => {
    const {monthly, result} = cell;
    const band = timeBand(result);
    const isBase = Math.abs(p.monthly - monthly) < 1e-7 && Math.abs(p.annual - row.annual) < 1e-7;
    const label = result ? result.months === 0 ? '已达标' : (result.months / 12).toFixed(1) : '—';
    const description = `每月投入 ${money(monthly)}，年化 ${row.annual}%，${resultText(result)}`;
    const selected = gridSelection && gridSelection.monthly === monthly && gridSelection.annual === row.annual;
    return `<td><button type="button" data-monthly="${monthly}" data-annual="${row.annual}" class="heat-${band} ${isBase ? 'is-base' : ''}" aria-pressed="${Boolean(selected)}" aria-label="${description}" title="${description}">${isBase ? '◎ ' : ''}${label}</button></td>`;
  }).join('')}</tr>`).join('');
  if (!gridSelection) gridSelection = {monthly: p.monthly, annual: p.annual};
  renderSelection(p);
}
function renderSelection(p) {
  const {monthly, annual} = gridSelection;
  const result = project(p.initial, monthly, annual, p.target);
  const base = project(p.initial, p.monthly, p.annual, p.target);
  let comparison = '';
  if (base && result) {
    const diff = base.months - result.months;
    comparison = diff === 0 ? '与当前计划同月达标。' : `比当前计划${diff > 0 ? '提前' : '晚'} ${duration(Math.abs(diff))}。`;
  }
  $('grid-selection').textContent = `所选组合：每月 ${money(monthly)}，假设年化 ${annual}%。${result ? `预计 ${resultText(result)}，${endMonth(p, result.months)}。` : '100 年内未达标。'}${comparison}`;
}
$('grid-form').addEventListener('submit', event => {
  event.preventDefault();
  const config = Object.fromEntries(Object.keys(DEFAULT_GRID).map(key => [key, Number(event.target.elements.namedItem(key).value)]));
  try { gridAxes(config); } catch (error) { $('grid-error').textContent = error.message; return; }
  $('grid-error').textContent = '';
  state.grid = config; gridCacheKey = ''; persist(); renderGrid(state.plan); success('网格已更新。点击任意组合查看精确达标时间。');
});
$('grid-body').addEventListener('click', event => {
  const button = event.target.closest('button[data-monthly]');
  if (!button) return;
  gridSelection = {monthly: Number(button.dataset.monthly), annual: Number(button.dataset.annual)};
  $('grid-body').querySelectorAll('button[aria-pressed="true"]').forEach(cell => cell.setAttribute('aria-pressed', 'false'));
  button.setAttribute('aria-pressed', 'true');
  renderSelection(state.plan);
});
function renderChart(p, scenarios) {
  const symbols = ['━', '┄', '··'];
  const classes = ['', 'positive', 'muted'];
  $('chart-legend').innerHTML = scenarios.map((s, i) => `<span class="${classes[i]}">${symbols[i]} ${s.name}：每月 ${money(s.monthly)} · 年化 ${s.annual}%</span>`).join('') + '<span>● 实际记录</span>';
  const base = scenarios[0].result;
  // Bound the graph to 40 years for readability; the calculator still searches 100 years.
  const horizon = Math.max(12, Math.min(480, Math.ceil((base?.months || 240) / 12) * 12));
  const step = Math.max(1, Math.ceil(horizon / 240));
  const samples = [];
  for (let n = 0; n <= horizon; n += step) samples.push(n);
  if (samples.at(-1) !== horizon) samples.push(horizon);
  const observed = state.records.map(r => ({...r, n: monthIndex(r.month) - monthIndex(p.start) + 1})).filter(r => r.n <= horizon);
  // Clip projections above the goal so extreme assumptions do not flatten the useful range.
  const upper = Math.max(p.target * 1.15, p.initial * 1.15, ...observed.map(r => r.balance * 1.1));
  const x = n => 72 + n / horizon * 862;
  const y = v => 258 - Math.min(v, upper) / upper * 220;
  let svg = `<svg viewBox="0 0 960 310" role="img" aria-labelledby="chart-title chart-desc"><title id="chart-title">三个攒钱情景的资产增长曲线与实际记录</title><desc id="chart-desc">横轴为计划经过年数，纵轴为资产万元。实线为当前计划，短虚线为增加投入，点线为收益率情景。超过纵轴上限的预测截顶显示。逐年数据见下方表格。</desc>`;
  for (let i = 0; i <= 4; i++) {
    const v = upper * i / 4;
    svg += `<line x1="72" x2="934" y1="${y(v)}" y2="${y(v)}" stroke="#dce2ed"/><text x="60" y="${y(v) + 4}" text-anchor="end" fill="#68758b" font-size="13">${(v / 10000).toFixed(0)}万</text>`;
  }
  for (let i = 0; i <= 4; i++) {
    const n = horizon * i / 4;
    svg += `<text x="${x(n)}" y="285" text-anchor="middle" fill="#68758b" font-size="13">${(n / 12).toFixed(1).replace('.0', '')}年</text>`;
  }
  svg += `<line x1="72" x2="934" y1="${y(p.target)}" y2="${y(p.target)}" stroke="#68758b" stroke-dasharray="6 6"/><text x="80" y="${Math.max(18, y(p.target) - 9)}" fill="#68758b" font-size="13">目标 ${wan(p.target)}</text>`;
  const colors = ['#405477', '#1a7a3a', '#68758b'];
  scenarios.forEach((s, i) => {
    const points = samples.map(n => `${x(n)},${y(balanceAt(p.initial, s.monthly, s.annual, n))}`).join(' ');
    svg += `<polyline points="${points}" fill="none" stroke="${colors[i]}" stroke-width="3" stroke-dasharray="${['none', '9 5', '2 5'][i]}"/>`;
  });
  observed.forEach(r => { svg += `<circle cx="${x(r.n)}" cy="${y(r.balance)}" r="5" fill="#26304a" stroke="white" stroke-width="2"><title>${r.month} 实际资产 ${money(r.balance)}</title></circle>`; });
  $('chart').innerHTML = svg + '</svg>';
  $('chart-window').textContent = `展示前 ${horizon / 12} 年 · 预测超过纵轴上限截顶显示`;
  const rows = [];
  for (let n = 0; n <= horizon; n += 12) rows.push(`<tr><th scope="row">${n === 0 ? '起点' : `${n / 12} 年后`}</th>${scenarios.map(s => `<td>${money(balanceAt(p.initial, s.monthly, s.annual, n))}</td>`).join('')}</tr>`);
  $('year-rows').innerHTML = rows.join('');
}
function renderCoverage(p) {
  const latest = latestRecord();
  const assets = latest ? latest.balance : p.initial;
  const budget = p.expenses.reduce((a, b) => a + b, 0);
  const available = assets * p.withdrawal / 100 / 12;
  $('coverage-summary').innerHTML = metric('月均假设可支用金额', money(available), `参考资产 ${wan(assets)} × 年提取 ${p.withdrawal}% ÷ 12`) + metric('生活支出覆盖率', percent(available, budget), `月支出 ${money(budget)}；工资替代率 ${percent(available, p.salary)}`) + metric('实际现金收入覆盖率', percent(p.cashIncome, budget), `你填报的实际月均现金收入 ${money(p.cashIncome)}`);
  $('coverage-note').textContent = `参考资产：${latest ? `${latest.month} 月末记录` : '计划起点'}，${money(assets)}。当前生活费全部覆盖所需资产：${budget === 0 ? '未设置支出' : p.withdrawal > 0 ? money(budget * 12 / (p.withdrawal / 100)) : '提取比例为 0，无法推算'}。`;
  let cumulative = 0;
  $('expense-progress').innerHTML = p.expenses.map((expense, i) => {
    cumulative += expense;
    const target = p.withdrawal > 0 ? cumulative * 12 / (p.withdrawal / 100) : Infinity;
    const already = cumulative > 0 && available >= cumulative;
    const base = Number.isFinite(target) ? project(p.initial, p.monthly, p.annual, target) : null;
    const more = Number.isFinite(target) ? project(p.initial, p.monthly + p.extra, p.annual, target) : null;
    const saved = base && more && base.months > more.months ? `多存 ${money(p.extra)} / 月，可提前 ${duration(base.months - more.months)}` : '';
    const coverage = cumulative > 0 ? percent(available, cumulative) : '未设置';
    return `<div class="progress-row"><div class="progress-head"><strong>${i === 0 ? '' : '+ '}${expenseNames[i]} <span>本项 ${money(expense)} / 月</span></strong><span>累计 ${money(cumulative)} / 月 · 覆盖 ${coverage}</span></div><div class="track" role="meter" aria-label="累计覆盖至${expenseNames[i]}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${cumulative > 0 ? Math.min(100, available / cumulative * 100).toFixed(1) : 0}"><div class="fill" style="width:${cumulative > 0 ? Math.min(100, available / cumulative * 100) : 0}%"></div></div><div class="progress-info"><span>${cumulative === 0 ? '填写支出后计算' : already ? '按当前参考资产，已覆盖' : Number.isFinite(target) ? `所需资产 ${wan(target)} · 原计划 ${base ? endMonth(p, base.months) : '100 年内未达标'}` : '设置大于 0 的提取比例后计算'}</span><span>${saved}</span></div></div>`;
  }).join('');
}
function renderRecords(p, base) {
  const records = [...state.records].sort((a, b) => b.month.localeCompare(a.month));
  $('record-rows').innerHTML = records.length ? records.map(r => {
    const n = monthIndex(r.month) - monthIndex(p.start) + 1;
    const delta = r.balance - balanceAt(p.initial, p.monthly, p.annual, n);
    return `<tr><th scope="row">${r.month}</th><td>${money(r.contribution)}</td><td>${percent(r.contribution, p.monthly)}</td><td>${money(r.balance)}</td><td class="${delta >= 0 ? 'positive' : 'negative'}">${delta >= 0 ? '+' : '−'}${money(Math.abs(delta))}</td><td><button type="button" class="secondary" data-edit="${r.month}" aria-label="编辑 ${r.month} 记录">编辑</button><button type="button" class="secondary" data-delete="${r.month}" aria-label="删除 ${r.month} 记录">删除</button></td></tr>`;
  }).join('') : '<tr><td colspan="6" class="muted">还没有记录。从这个月开始，留下你的第一笔进度。</td></tr>';
  if (!records.length) { $('record-summary').textContent = ''; return; }
  const latest = records[0];
  const forecast = project(latest.balance, p.monthly, p.annual, p.target);
  let estimate = forecast ? forecast.months === 0 ? '最新记录已达标' : `${dateText(addMonths(latest.month, forecast.months))} 达标` : '未来 100 年内未达标';
  if (forecast && forecast.months > 0 && base && base.months > 0) {
    const diff = monthIndex(addMonths(latest.month, forecast.months)) - monthIndex(addMonths(p.start, base.months - 1));
    estimate += diff === 0 ? '，与原计划同月' : `，较原计划${diff > 0 ? '晚' : '提前'} ${duration(Math.abs(diff))}`;
  }
  $('record-summary').innerHTML = `已记录 <strong>${records.length} 个月</strong>，实际投入合计 <strong>${money(records.reduce((s, r) => s + r.contribution, 0))}</strong>。<br>从 ${latest.month} 月末余额继续，${estimate}。`;
}
function readNumber(form, name) { return Number(form.elements.namedItem(name).value); }
$('plan-form').addEventListener('submit', event => {
  event.preventDefault();
  const next = structuredClone(state);
  for (const key of ['initial', 'target', 'monthly', 'annual']) next.plan[key] = readNumber(event.target, key);
  next.plan.start = event.target.elements.start.value;
  try { validateState(next); } catch (error) { announce(error.message + '。请先处理不在新计划范围内的月度记录。'); return; }
  state = next; cancelEdit(); persist(); hydrate(); render(); success('计划已更新，情景对比和生活覆盖已重新计算。');
});
$('extra').addEventListener('input', event => { state.plan.extra = Number(event.target.value); render(); });
$('extra').addEventListener('change', persist);
$('base-annual').addEventListener('change', event => {
  if (!event.target.reportValidity()) return;
  setBaseAnnual(Number(event.target.value));
});
document.querySelectorAll('[data-base-rate]').forEach(button => button.addEventListener('click', () => setBaseAnnual(Number(button.dataset.baseRate))));
function setBaseAnnual(annual) {
  state.plan.annual = annual;
  $('plan-form').elements.annual.value = annual;
  $('base-annual').value = annual;
  persist(); render(); success(`基础年化已设为 ${annual}%，所有预测已同步更新。`);
}
$('compare-annual').addEventListener('change', event => {
  if (!event.target.reportValidity()) return;
  state.plan.compareAnnual = Number(event.target.value); persist(); render();
});
$('coverage-form').addEventListener('submit', event => {
  event.preventDefault();
  for (const key of ['withdrawal', 'salary', 'cashIncome']) state.plan[key] = readNumber(event.target, key);
  state.plan.expenses = expenseNames.map((_, i) => readNumber(event.target, `expense${i}`));
  persist(); render(); success('生活预算已更新。实际现金收入与假设可支用金额分别计算。');
});
function cancelEdit() { editing = null; $('record-submit').textContent = '保存本月记录'; $('cancel-edit').hidden = true; }
$('cancel-edit').addEventListener('click', () => { cancelEdit(); hydrate(); });
$('record-form').addEventListener('submit', event => {
  event.preventDefault();
  const form = event.target;
  const record = {month: form.elements.month.value, contribution: readNumber(form, 'contribution'), balance: readNumber(form, 'balance')};
  if (record.month > currentMonth) { announce('请记录本月或过去月份；未来月份请使用计划预测。'); return; }
  if (editing && editing !== record.month) { announce('编辑时请保留原月份。如需换月，请删除原记录后重新添加。'); return; }
  const exists = state.records.some(r => r.month === record.month);
  if (exists && !editing && !confirm(`${record.month} 已有记录，是否替换？`)) return;
  const next = {...state, records: [...state.records.filter(r => r.month !== record.month), record]};
  try { validateState(next); } catch (error) { announce(error.message); return; }
  state = next; cancelEdit(); persist(); render(); success(`${record.month} 的记录已保存。每一次投入都算数。`);
});
$('record-rows').addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.dataset.edit) {
    const record = state.records.find(r => r.month === button.dataset.edit);
    editing = record.month;
    for (const [key, value] of Object.entries(record)) $('record-form').elements.namedItem(key).value = value;
    $('record-submit').textContent = '保存修改'; $('cancel-edit').hidden = false;
    $('record-form').scrollIntoView({block: 'center'}); $('record-form').elements.contribution.focus();
  } else if (button.dataset.delete && confirm(`删除 ${button.dataset.delete} 的记录？`)) {
    state.records = state.records.filter(r => r.month !== button.dataset.delete);
    if (editing === button.dataset.delete) cancelEdit();
    persist(); render(); success('该月记录已删除。');
  }
});
function download(data, filename) {
  const url = URL.createObjectURL(new Blob([data], {type: 'application/json'}));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$('export').addEventListener('click', () => {
  if (corruptStorage) {
    download(localStorage.getItem(KEY) || '', `攒钱计划-原始数据-${currentMonth}.json`);
    announce('原始数据已导出。请导入有效备份恢复，或导入修复后的原始数据。');
  } else { download(JSON.stringify(state, null, 2), `攒钱计划-${currentMonth}.json`); success('备份已导出，包含计划、预算与全部月度记录。'); }
});
$('import').addEventListener('click', () => $('import-file').click());
$('import-file').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file) return;
  try {
    if (file.size > 1024 * 1024) throw new Error('备份文件不能超过 1 MB');
    const imported = checkedState(JSON.parse(await file.text()));
    if (imported.records.some(r => r.month > currentMonth)) throw new Error('备份含未来月份的实际记录');
    if (!confirm(`导入将替换当前计划和 ${state.records.length} 条记录，恢复备份中的 ${imported.records.length} 条记录。是否继续？`)) return;
    state = imported; corruptStorage = false; cancelEdit(); persist(); hydrate(); render(); success('备份已恢复。');
  } catch (error) { announce(`导入失败：${error.message}。原有计划与记录未改变。`); }
  finally { event.target.value = ''; }
});
hydrate(); render();
