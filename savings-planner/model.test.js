import test from 'node:test';
import assert from 'node:assert/strict';
import {balanceAt, project, addMonths, validateState} from './model.js';
test('monthly end contributions, effective annual compounding and minimum whole month', () => {
  assert.equal(project(300000, 10000, 6, 3000000).months, 158);
  assert.equal(project(300000, 12000, 6, 3000000).months, 141);
  assert.equal(project(300000, 10000, 8, 3000000).months, 141);
  assert.ok(balanceAt(300000, 10000, 6, 157) < 3000000);
  assert.ok(balanceAt(300000, 10000, 6, 158) >= 3000000);
  assert.ok(Math.abs(balanceAt(100, 0, 6, 12) - 106) < 1e-8);
});
test('zero, negative, already achieved, no contribution and unreachable cases', () => {
  assert.equal(project(300000, 10000, 0, 3000000).months, 270);
  assert.equal(project(300000, 12000, 0, 3000000).months, 225);
  assert.equal(project(3000000, 0, -10, 3000000).months, 0);
  assert.equal(project(300000, 0, 0, 3000000), null);
  assert.equal(project(300000, 100, -20, 3000000), null);
  assert.ok(balanceAt(300000, 0, -10, 12) < 300000);
});
test('calendar is independent of day length and daylight savings', () => {
  assert.equal(addMonths('2026-12', 1), '2027-01');
  assert.equal(addMonths('2026-10', 157), '2039-11');
});
const state = () => ({version: 1, plan: {initial: 300000, target: 3000000, monthly: 10000, extra: 2000, annual: 6, compareAnnual: 8, withdrawal: 3, salary: 20000, cashIncome: 0, start: '2026-10', expenses: [120, 280, 1800, 2500, 1300]}, records: [{month: '2026-10', contribution: 10000, balance: 310000}]});
test('backups are validated completely before being accepted', () => {
  assert.doesNotThrow(() => validateState(state()));
  const duplicate = state(); duplicate.records.push(duplicate.records[0]);
  assert.throws(() => validateState(duplicate));
  for (const bad of [NaN, Infinity, -1, '10000', null]) {
    const data = state(); data.plan.monthly = bad;
    assert.throws(() => validateState(data));
  }
  const earlier = state(); earlier.records[0].month = '2026-09';
  assert.throws(() => validateState(earlier));
  const invalidMonth = state(); invalidMonth.records[0].month = '2026-13';
  assert.throws(() => validateState(invalidMonth));
  const injection = state(); injection.records[0].month = '<img src=x onerror=alert(1)>';
  assert.throws(() => validateState(injection));
});
