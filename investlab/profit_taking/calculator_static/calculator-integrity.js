"use strict";

(function exposeCalculatorIntegrity(root) {
  class DataIntegrityError extends Error {
    constructor(message) {
      super(message);
      this.name = "DataIntegrityError";
    }
  }

  function formatClose(value) {
    if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
      throw new DataIntegrityError("价格数据必须为正有限数");
    }
    const [coefficient, rawExponent] = value.toPrecision(17).split("e");
    const normalized = coefficient
      .replace(/(\.\d*?[1-9])0+$/, "$1")
      .replace(/\.0+$/, "");
    if (rawExponent === undefined) return normalized;
    const exponent = Number(rawExponent);
    return `${normalized}e${exponent >= 0 ? "+" : "-"}${String(Math.abs(exponent)).padStart(2, "0")}`;
  }

  function canonicalPriceBytes(prices) {
    if (!Array.isArray(prices) || prices.length < 2) {
      throw new DataIntegrityError("价格数据至少需要两个交易日");
    }
    let previousDate = "";
    const rows = prices.map((row) => {
      if (!Array.isArray(row) || row.length !== 2) {
        throw new DataIntegrityError("价格数据行格式无效");
      }
      const [date, close] = row;
      if (
        typeof date !== "string"
        || !/^\d{4}-\d{2}-\d{2}$/.test(date)
        || date <= previousDate
      ) {
        throw new DataIntegrityError("价格日期必须严格递增且使用 YYYY-MM-DD");
      }
      previousDate = date;
      return `${date},${formatClose(close)}\n`;
    });
    return new TextEncoder().encode(rows.join(""));
  }

  function validatePayloadMetadata(payload) {
    const firstDate = payload.prices[0][0];
    const lastDate = payload.prices[payload.prices.length - 1][0];
    const provenance = payload.provenance;
    const requested = provenance.requested_coverage;
    const actual = provenance.actual_coverage;
    if (
      payload.schema_version !== 1
      || payload.asset?.kind !== "total_return_index"
      || payload.asset?.symbol !== "H00300"
      || typeof payload.asset?.name !== "string"
      || !Array.isArray(requested)
      || requested.length !== 2
      || !Array.isArray(actual)
      || actual.length !== 2
      || actual[0] !== firstDate
      || actual[1] !== lastDate
      || requested[0] > firstDate
      || requested[1] < lastDate
      || provenance.normalized_row_count !== payload.prices.length
      || typeof provenance.provider !== "string"
      || provenance.provider.length === 0
    ) {
      throw new DataIntegrityError("指数数据元信息与价格快照不一致");
    }
  }

  async function verifyPricePayload(
    payload,
    expectedChecksum,
    cryptoProvider = globalThis.crypto,
  ) {
    if (!cryptoProvider || !cryptoProvider.subtle) {
      throw new DataIntegrityError("浏览器不支持 WebCrypto，无法验证指数数据");
    }
    if (!/^[0-9a-f]{64}$/.test(expectedChecksum)) {
      throw new DataIntegrityError("页面缺少可信的数据校验码");
    }
    if (
      !payload
      || !payload.provenance
      || payload.provenance.checksum_sha256 !== expectedChecksum
    ) {
      throw new DataIntegrityError("指数数据声明的校验码与可信快照不一致");
    }
    const digest = await cryptoProvider.subtle.digest(
      "SHA-256",
      canonicalPriceBytes(payload.prices),
    );
    const actual = Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
    if (actual !== expectedChecksum) {
      throw new DataIntegrityError("指数数据完整性校验失败，已拒绝载入");
    }
    validatePayloadMetadata(payload);
    return payload;
  }

  async function verifyPayloadText(
    payloadText,
    expectedPayloadChecksum,
    expectedPriceChecksum,
    cryptoProvider = globalThis.crypto,
  ) {
    if (!cryptoProvider || !cryptoProvider.subtle) {
      throw new DataIntegrityError("浏览器不支持 WebCrypto，无法验证指数数据");
    }
    if (!/^[0-9a-f]{64}$/.test(expectedPayloadChecksum)) {
      throw new DataIntegrityError("页面缺少可信的完整载荷校验码");
    }
    const digest = await cryptoProvider.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(payloadText),
    );
    const actual = Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
    if (actual !== expectedPayloadChecksum) {
      throw new DataIntegrityError("指数数据载荷完整性校验失败，已拒绝载入");
    }
    let payload;
    try {
      payload = JSON.parse(payloadText);
    } catch {
      throw new DataIntegrityError("指数数据载荷不是有效 JSON");
    }
    return verifyPricePayload(payload, expectedPriceChecksum, cryptoProvider);
  }

  const api = Object.freeze({
    DataIntegrityError,
    canonicalPriceBytes,
    verifyPayloadText,
    verifyPricePayload,
  });
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CalculatorIntegrity = api;
})(typeof window === "undefined" ? null : window);
