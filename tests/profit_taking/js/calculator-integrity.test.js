"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { createHash } = require("node:crypto");

const {
  DataIntegrityError,
  canonicalPriceBytes,
  verifyPayloadText,
  verifyPricePayload,
} = require("../../../investlab/profit_taking/calculator_static/calculator-integrity.js");

const PAYLOAD = {
  prices: [
    ["2006-01-04", 1121.73],
    ["2026-07-17", 6770.28],
  ],
  provenance: {
    checksum_sha256: "6ffbde968c9ada64418b0c89a373c414cf10ea24c8a5ebfd8e74e5ba8d370fee",
    actual_coverage: ["2006-01-04", "2026-07-17"],
    requested_coverage: ["2006-01-01", "2026-07-17"],
    normalized_row_count: 2,
    provider: "official snapshot",
  },
  asset: {
    kind: "total_return_index",
    name: "沪深300全收益指数",
    symbol: "H00300",
  },
  schema_version: 1,
};

test("canonicalPriceBytes matches the Python canonical representation", () => {
  // Given: normalized dates and floating-point closes.
  const expected = "2006-01-04,1121.73\n2026-07-17,6770.2799999999997\n";

  // When: the browser canonicalizer serializes them.
  const actual = new TextDecoder().decode(canonicalPriceBytes(PAYLOAD.prices));

  // Then: bytes match the Python .17g contract.
  assert.equal(actual, expected);
});

test("verifyPricePayload rejects a tampered close before rendering", async () => {
  // Given: a payload whose close no longer matches its trusted checksum.
  const tampered = structuredClone(PAYLOAD);
  tampered.prices[1][1] = 6770.29;

  // When/Then: WebCrypto rejects it with a typed integrity error.
  await assert.rejects(
    verifyPricePayload(tampered, PAYLOAD.provenance.checksum_sha256),
    DataIntegrityError,
  );
});

test("verifyPricePayload rejects unavailable WebCrypto clearly", async () => {
  // Given: a browser without the required SubtleCrypto capability.
  const missingCrypto = {};

  // When/Then: verification fails closed with an explicit message.
  await assert.rejects(
    verifyPricePayload(
      PAYLOAD,
      PAYLOAD.provenance.checksum_sha256,
      missingCrypto,
    ),
    /浏览器不支持 WebCrypto/,
  );
});

test("verifyPricePayload rejects provenance inconsistent with prices", async () => {
  const tampered = structuredClone(PAYLOAD);
  tampered.provenance.actual_coverage[0] = "2006-01-05";

  await assert.rejects(
    verifyPricePayload(tampered, PAYLOAD.provenance.checksum_sha256),
    /元信息与价格快照不一致/,
  );
});

test("verifyPayloadText binds provenance to the trusted snapshot", async () => {
  const payloadText = JSON.stringify(PAYLOAD);
  const payloadChecksum = createHash("sha256").update(payloadText).digest("hex");
  const tampered = JSON.stringify({
    ...PAYLOAD,
    provenance: { ...PAYLOAD.provenance, provider: "tampered provider" },
  });

  await assert.rejects(
    verifyPayloadText(
      tampered,
      payloadChecksum,
      PAYLOAD.provenance.checksum_sha256,
    ),
    /载荷完整性校验失败/,
  );
});
