"use strict";

(function startCalculatorApp() {
  const MAX_ROWS = 5;
  const SERIES_KEYS = ["A", "B", "C", "D", "E"];
  const DEFAULT_ROW = Object.freeze({
    name: "每月定投，不止盈",
    contributionAmount: "1000",
    cadence: "monthly",
    stopFamily: "none",
    targetReturn: "20",
    trailingDrawdown: "10",
    saleFraction: "100",
    recycleProceeds: false,
  });
  const form = document.querySelector("#calculator-form");
  const list = document.querySelector("#strategy-list");
  const addButton = document.querySelector("#add-strategy");
  const status = document.querySelector("#calculator-status");
  const dataState = document.querySelector("#data-state");
  const startInput = document.querySelector("#start-date");
  const endInput = document.querySelector("#end-date");
  let rows = [{ ...DEFAULT_ROW, id: "strategy-1", key: SERIES_KEYS[0] }];
  let nextId = 2;
  let payload = null;
  let lastValidResults = null;

  function fieldMarkup(id, label, type, attributes = "") {
    return `<div class="field"><label for="${id}">${label}</label><input id="${id}" ${type} ${attributes} aria-describedby="${id}-error"><p class="field-error" id="${id}-error"></p></div>`;
  }

  function createRow(row, index) {
    const fieldset = document.createElement("fieldset");
    fieldset.className = "strategy-row";
    fieldset.dataset.rowId = row.id;
    fieldset.innerHTML = `
      <legend id="${row.id}-legend" tabindex="-1"><span class="series-key" aria-hidden="true"></span>方案 ${index + 1} · 系列 ${row.key}</legend>
      ${fieldMarkup(`${row.id}-name`, "方案名称", 'name="name" type="text"', 'required maxlength="40"')}
      ${fieldMarkup(`${row.id}-amount`, "每次定投金额（元）", 'name="contributionAmount" type="number"', 'required min="1" max="10000000" step="0.01" inputmode="decimal"')}
      <div class="field"><label for="${row.id}-cadence">定投频率</label><select id="${row.id}-cadence" name="cadence"><option value="daily">每交易日</option><option value="weekly">每周</option><option value="biweekly">每两周</option><option value="monthly">每月</option><option value="quarterly">每季度</option></select><p class="field-error" id="${row.id}-cadence-error"></p></div>
      <div class="field"><label for="${row.id}-stop">止盈策略</label><select id="${row.id}-stop" name="stopFamily"><option value="none">不止盈</option><option value="target_return">目标收益率止盈</option><option value="trailing_drawdown">目标激活后回撤止盈</option></select><p class="field-error" id="${row.id}-stop-error"></p></div>
      ${fieldMarkup(`${row.id}-target`, "目标收益率（%）", 'name="targetReturn" type="number"', 'required min="0.1" max="500" step="0.1" inputmode="decimal"')}
      ${fieldMarkup(`${row.id}-drawdown`, "峰值回撤（%）", 'name="trailingDrawdown" type="number"', 'required min="0.1" max="99" step="0.1" inputmode="decimal"')}
      ${fieldMarkup(`${row.id}-fraction`, "每次卖出比例（%）", 'name="saleFraction" type="number"', 'required min="0.1" max="100" step="0.1" inputmode="decimal"')}
      <div class="checkbox-field"><input id="${row.id}-recycle" name="recycleProceeds" type="checkbox"><label for="${row.id}-recycle">止盈资金用于后续定投</label></div>
      <div class="row-actions"><button class="button secondary delete-row" type="button" aria-describedby="row-limit-help">删除此策略</button></div>`;
    for (const [name, value] of Object.entries(row)) {
      const control = fieldset.elements.namedItem(name);
      if (!control) continue;
      if (control.type === "checkbox") control.checked = value;
      else control.value = value;
    }
    updateConditionalFields(fieldset);
    return fieldset;
  }

  function renderRows(focusId = null) {
    const fragment = document.createDocumentFragment();
    rows.forEach((row, index) => fragment.append(createRow(row, index)));
    list.replaceChildren(fragment);
    addButton.disabled = rows.length >= MAX_ROWS;
    addButton.setAttribute("aria-disabled", String(addButton.disabled));
    list.querySelectorAll(".delete-row").forEach((button) => {
      button.disabled = rows.length === 1;
    });
    if (focusId) document.querySelector(`#${focusId}-name`)?.focus();
  }

  function updateConditionalFields(fieldset) {
    const family = fieldset.elements.namedItem("stopFamily").value;
    const noStop = family === "none";
    const trailing = family === "trailing_drawdown";
    for (const name of ["targetReturn", "saleFraction", "recycleProceeds"]) {
      fieldset.elements.namedItem(name).disabled = noStop;
    }
    fieldset.elements.namedItem("trailingDrawdown").disabled = !trailing;
  }

  function syncRowsFromDom() {
    rows = rows.map((row) => {
      const fieldset = list.querySelector(`[data-row-id="${row.id}"]`);
      return {
        ...row,
        name: fieldset.elements.namedItem("name").value,
        contributionAmount: fieldset.elements.namedItem("contributionAmount").value,
        cadence: fieldset.elements.namedItem("cadence").value,
        stopFamily: fieldset.elements.namedItem("stopFamily").value,
        targetReturn: fieldset.elements.namedItem("targetReturn").value,
        trailingDrawdown: fieldset.elements.namedItem("trailingDrawdown").value,
        saleFraction: fieldset.elements.namedItem("saleFraction").value,
        recycleProceeds: fieldset.elements.namedItem("recycleProceeds").checked,
      };
    });
  }

  function clearErrors() {
    form.querySelectorAll("[aria-invalid]").forEach((control) => control.removeAttribute("aria-invalid"));
    form.querySelectorAll(".field-error").forEach((element) => { element.textContent = ""; });
    status.classList.remove("error");
  }

  function showError(error) {
    status.classList.add("error");
    status.textContent = `参数未通过校验，已保留上一次有效结果。${error.reason || error.message}`;
    const parts = String(error.field || "").split(".");
    let control = null;
    if (parts[0] === "rows") {
      const row = rows[Number(parts[1])];
      const name = parts[2];
      control = list.querySelector(`[data-row-id="${row?.id}"] [name="${name}"]`);
    } else {
      control = form.elements.namedItem(error.field);
    }
    if (control) {
      control.setAttribute("aria-invalid", "true");
      const message = document.querySelector(`#${control.id}-error`);
      if (message) message.textContent = error.reason;
      control.focus();
    }
  }

  async function loadPrices() {
    try {
      const response = await fetch("./assets/h00300-prices.json");
      if (!response.ok) throw new Error(`数据文件响应 ${response.status}`);
      const payloadText = await response.text();
      const expectedChecksum = document.querySelector(
        'meta[name="calculator-data-sha256"]',
      )?.content;
      const expectedPayloadChecksum = document.querySelector(
        'meta[name="calculator-payload-sha256"]',
      )?.content;
      payload = await CalculatorIntegrity.verifyPayloadText(
        payloadText,
        expectedPayloadChecksum || "",
        expectedChecksum || "",
      );
      const requestedCoverage = payload.provenance.requested_coverage;
      const actualCoverage = payload.provenance.actual_coverage;
      startInput.value = requestedCoverage[0];
      endInput.value = requestedCoverage[1];
      startInput.min = requestedCoverage[0];
      startInput.max = requestedCoverage[1];
      endInput.min = requestedCoverage[0];
      endInput.max = requestedCoverage[1];
      dataState.textContent = `数据快照截至 ${actualCoverage[1]}；可选 ${requestedCoverage[0]} 至 ${requestedCoverage[1]}；实际交易数据 ${actualCoverage[0]} 至 ${actualCoverage[1]} · ${payload.provenance.provider} · SHA-256 ${payload.provenance.checksum_sha256}`;
      status.textContent = "数据已载入。请设置参数并点击“开始计算”。";
    } catch (error) {
      status.classList.add("error");
      status.textContent = `指数数据载入失败：${error.message}`;
      dataState.textContent = "载入失败";
    }
  }

  addButton.addEventListener("click", () => {
    if (rows.length >= MAX_ROWS) {
      status.textContent = "最多只能配置五个策略。";
      return;
    }
    syncRowsFromDom();
    const id = `strategy-${nextId++}`;
    const used = new Set(rows.map((row) => row.key));
    const key = SERIES_KEYS.find((candidate) => !used.has(candidate));
    rows.push({ ...DEFAULT_ROW, id, key, name: `方案 ${rows.length + 1}` });
    renderRows(id);
    status.textContent = rows.length === MAX_ROWS
      ? "已新增第五个策略，当前已达到五个策略上限。"
      : `已新增策略，当前共 ${rows.length} 个。`;
  });

  list.addEventListener("change", (event) => {
    if (event.target.name === "stopFamily") {
      updateConditionalFields(event.target.closest(".strategy-row"));
    }
  });

  list.addEventListener("click", (event) => {
    const button = event.target.closest(".delete-row");
    if (!button || rows.length === 1) return;
    syncRowsFromDom();
    const fieldset = button.closest(".strategy-row");
    const index = rows.findIndex((row) => row.id === fieldset.dataset.rowId);
    rows.splice(index, 1);
    const focusRow = rows[Math.min(index, rows.length - 1)];
    renderRows();
    document.querySelector(`[data-row-id="${focusRow.id}"] legend`)?.focus?.();
    status.textContent = `已删除策略，当前共 ${rows.length} 个。`;
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    clearErrors();
    try {
      if (!payload) throw new CalculatorCore.CalculatorValidationError("dateRange", "指数数据尚未载入");
      syncRowsFromDom();
      const request = CalculatorCore.parseRequest({
        startDate: startInput.value,
        endDate: endInput.value,
        rows,
      }, payload.provenance.requested_coverage);
      const results = CalculatorCore.runCalculator(payload.prices, request);
      lastValidResults = results;
      const resultsSummary = document.querySelector("#results-summary");
      delete resultsSummary.dataset.stale;
      CalculatorCharts.renderResults(resultsSummary, results, {
        requestedStart: request.startDate,
        requestedEnd: request.endDate,
        actualStart: results[0].dailyStates[0].date,
        actualEnd: results[0].dailyStates.at(-1).date,
        rowStyles: rows.map((row) => ({
          id: row.id,
          key: row.key,
          styleIndex: SERIES_KEYS.indexOf(row.key),
        })),
      });
      document.querySelector("#results-empty").hidden = true;
      status.textContent = `计算完成：${results.length} 个策略，实际区间 ${results[0].dailyStates[0].date} 至 ${results[0].dailyStates.at(-1).date}。`;
      document.dispatchEvent(new CustomEvent("calculator:results", {
        detail: { request, results, provenance: payload.provenance },
      }));
    } catch (error) {
      showError(error);
      if (lastValidResults) document.querySelector("#results-summary").dataset.stale = "true";
    }
  });

  renderRows();
  loadPrices();
})();
