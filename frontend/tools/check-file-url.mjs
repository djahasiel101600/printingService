/**
 * Regression guard for the file preview / download URL.
 *
 * The preview endpoint authenticates with the `Authorization` header, so the UI
 * fetches it through the shared axios instance (`api.get(...)`). That instance
 * already carries `baseURL` (VITE_API_URL, "/api" in Docker), which means the
 * URL handed to it must be *relative* to that base. Concatenating
 * `api.defaults.baseURL` into the URL as well made axios join the prefix twice,
 * producing `/api/api/orders/<id>/files/<id>/preview/` and a 404 from nginx.
 *
 * Run with:  npm run check:file-url
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import axios from "axios";

const failures = [];
const check = (label, actual, expected) => {
  const ok = actual === expected;
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}\n      ${actual}`);
  if (!ok) failures.push(`${label}\n      expected: ${expected}\n      actual:   ${actual}`);
};

// The path the fixed helper produces: relative to the axios baseURL.
const relativePath = "/orders/3/files/3/preview/?variant=original";

// Same-origin deployment (docker-compose default: VITE_API_URL=/api).
const prod = axios.create({ baseURL: "/api" });
check("prod baseURL joins to exactly one /api",
  prod.getUri({ url: relativePath }),
  "/api/orders/3/files/3/preview/?variant=original");

// Absolute baseURL (the local dev default).
const dev = axios.create({ baseURL: "http://127.0.0.1:8000/api" });
check("dev baseURL joins to exactly one /api",
  dev.getUri({ url: relativePath }),
  "http://127.0.0.1:8000/api/orders/3/files/3/preview/?variant=original");

// Guard the premise: if axios ever stopped doubling the prefix, the test above
// would keep passing for the wrong reason, so pin the broken form explicitly.
check("the old baseURL-prefixed form is what caused the doubled path",
  prod.getUri({ url: `${prod.defaults.baseURL}${relativePath}` }),
  "/api/api/orders/3/files/3/preview/?variant=original");

// Static guard: the source must not re-introduce the double-prefix.
const sourcePath = fileURLToPath(new URL("../src/components/FilePreviewDialog.tsx", import.meta.url));
const source = readFileSync(sourcePath, "utf8");
check("FilePreviewDialog does not concatenate api.defaults.baseURL",
  String(/api\.defaults\.baseURL/.test(source)),
  "false");
check("buildFilePath returns a baseURL-relative path",
  String(/return `\/orders\/\$\{orderId\}\/files\/\$\{fileId\}\/preview\//.test(source)),
  "true");
check("axios calls use the relative path builder",
  String(/buildFilePath\(orderId, fileId/.test(source)),
  "true");

if (failures.length) {
  console.error(`\n${failures.length} check(s) failed:\n- ${failures.join("\n- ")}`);
  process.exit(1);
}
console.log("\nAll file URL checks passed.");