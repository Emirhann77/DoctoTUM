import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const publicDir = path.join(root, "public");

fs.mkdirSync(publicDir, { recursive: true });

for (const name of fs.readdirSync(root)) {
  if (!name.endsWith(".html")) continue;
  fs.copyFileSync(path.join(root, name), path.join(publicDir, name));
}

const jsSrc = path.join(root, "js");
const jsDest = path.join(publicDir, "js");
if (!fs.existsSync(jsSrc)) {
  console.warn("sync-public: missing js/ — static app scripts will not deploy");
} else {
  fs.rmSync(jsDest, { recursive: true, force: true });
  fs.cpSync(jsSrc, jsDest, { recursive: true });
}
