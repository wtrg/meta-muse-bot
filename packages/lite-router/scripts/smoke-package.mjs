import { createRequire } from "node:module";

const esm = await import("../dist/index.mjs");
const require = createRequire(import.meta.url);
const cjs = require("../dist/index.cjs");

for (const mod of [esm, cjs]) {
  if (typeof mod.createLiteRouter !== "function") {
    throw new Error("createLiteRouter export is missing");
  }
  if (typeof mod.handleLiteEmail !== "function") {
    throw new Error("handleLiteEmail export is missing");
  }
  if (typeof mod.verifyLiteWebhookRequest !== "function") {
    throw new Error("verifyLiteWebhookRequest export is missing");
  }
}
