import { readdir, readFile, mkdir, writeFile } from "node:fs/promises";
import { zipSync } from "fflate";
import { join } from "node:path";
const files = {};
async function collect(dir) {
  for (const item of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, item.name);
    if (
      item.isDirectory() &&
      !["__pycache__", ".pytest_cache", "output", "profiles"].includes(
        item.name,
      )
    )
      await collect(path);
    else if (
      item.isFile() &&
      /\.(py|json|md|txt)$/.test(item.name) &&
      item.name !== "profile.json"
    ) {
      files[path.replaceAll("\\", "/")] = [
        new Uint8Array(await readFile(path)),
        { mtime: new Date("2026-01-01T00:00:00Z") },
      ];
    }
  }
}
await collect("roomscope-core");
await mkdir("public/downloads", { recursive: true });
await writeFile("public/downloads/roomscope-core.zip", zipSync(files));
console.log(`Packaged ${Object.keys(files).length} DSP source files`);
