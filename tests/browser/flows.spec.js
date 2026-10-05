import { test, expect } from "@playwright/test";
import { demoProfile } from "../../assets/profiles.js";
const upload = (page, slot, value) =>
  page.locator(`#file-${slot}`).setInputFiles({
    name: "profile.json",
    mimeType: "application/json",
    buffer: Buffer.from(
      typeof value === "string" ? value : JSON.stringify(value),
    ),
  });
test.beforeEach(async ({ page }) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("response", (r) => {
    if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`);
  });
  page.on("requestfailed", (r) =>
    errors.push(`${r.failure()?.errorText} ${r.url()}`),
  );
  await page.goto("/workspace.html");
  page.errors = errors;
});
test.afterEach(async ({ page }) => {
  expect(page.errors).toEqual([]);
});
test("demo chart, rename, reload, export, clear and import", async ({
  page,
}, info) => {
  await expect(page.locator("#empty")).toBeVisible();
  await page.getByRole("button", { name: "Загрузить демо A/B" }).click();
  await expect(page.locator("#chart")).toBeVisible();
  await expect(page.locator("#chart polyline")).toHaveCount(2);
  await expect(page.locator("#rms")).not.toHaveText("—");
  await page.locator("#label-a").fill("Диван · до");
  await page.locator("#label-a").press("Tab");
  await page.reload();
  await expect(page.locator("#label-a")).toHaveValue("Диван · до");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Скачать A", exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("roomscope-a.json");
  const path = await download.path();
  await page.getByRole("button", { name: "Очистить A/B" }).click();
  await expect(page.locator("#empty")).toBeVisible();
  await page.locator("#file-a").setInputFiles(path);
  await expect(page.locator("#label-a")).toHaveValue("Диван · до");
  await upload(page, "b", demoProfile("B"));
  await page.locator("#chart").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `test-results/${info.project.name}-comparison.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("malformed and incompatible files keep existing data and show actionable errors", async ({
  page,
}) => {
  await upload(page, "a", demoProfile("A"));
  await upload(page, "a", "{broken");
  await expect(page.getByRole("status")).toContainText(
    "Не удалось прочитать JSON",
  );
  await expect(page.locator("#label-a")).toHaveValue("Демо · позиция A");
  const old = demoProfile("B");
  old.roomscope_version = "0.2";
  delete old.response.reference;
  await upload(page, "b", old);
  await expect(page.getByRole("status")).toContainText("разные системы");
  await expect(page.locator("#rms")).toHaveText("—");
  await upload(page, "b", demoProfile("B"));
  await expect(page.locator("#rms")).not.toHaveText("—");
});
test("loads the profile produced by the Python pipeline", async ({ page }) => {
  await page
    .locator("#file-a")
    .setInputFiles("docs/examples/synthetic-profile.json");
  await page
    .locator("#file-b")
    .setInputFiles("docs/examples/synthetic-profile.json");
  await expect(page.locator("#rms")).toHaveText("0.00 дБ");
  await expect(page.locator('[data-slot="a"] .meta')).toContainText("29 полос");
  await expect(page.locator("#chart")).toBeVisible();
});

test("clear and demo supersede pending imports, including failed reads", async ({
  page,
}) => {
  await page.evaluate(() => {
    File.prototype.text = function () {
      return new Promise((resolve) => {
        window.finishImport = resolve;
      });
    };
  });
  for (const action of ["clear", "demo"]) {
    for (const content of [
      JSON.stringify({ ...demoProfile(), label: "stale" }),
      "{broken",
    ]) {
      await upload(page, "a", demoProfile());
      await page.waitForFunction(
        () => typeof window.finishImport === "function",
      );
      await page.locator(`#${action}`).click();
      const message = await page.getByRole("status").textContent();
      await page.evaluate(async (value) => {
        window.finishImport(value);
        delete window.finishImport;
        await new Promise((resolve) => setTimeout(resolve, 0));
      }, content);
      await expect(page.locator("#label-a")).toHaveValue(
        action === "clear" ? "" : "Демо · позиция A",
      );
      await expect(page.getByRole("status")).toHaveText(message);
      await page.reload();
      await expect(page.locator("#label-a")).toHaveValue(
        action === "clear" ? "" : "Демо · позиция A",
      );
      await page.evaluate(() => {
        File.prototype.text = function () {
          return new Promise((resolve) => {
            window.finishImport = resolve;
          });
        };
      });
    }
  }
});
test("corrupt storage recovers; blocked storage still supports comparison", async ({
  page,
}) => {
  await page.evaluate(() =>
    localStorage.setItem("roomscope.profiles.v1", "{bad"),
  );
  await page.reload();
  await expect(page.getByRole("status")).toContainText("повреждены");
  await page.evaluate(() => {
    Storage.prototype.setItem = () => {
      throw new Error("blocked");
    };
  });
  await page.getByRole("button", { name: "Загрузить демо A/B" }).click();
  await expect(page.getByRole("status")).toContainText(
    "не разрешил сохранение",
  );
  await expect(page.locator("#chart")).toBeVisible();
});
test("roadmap alias, all AR layers, reduced motion and presentation links", async ({
  page,
}, info) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/roadmap.html#final");
  await expect(page).toHaveURL(/index.html#final/);
  await expect(page.locator("#motion")).toHaveAttribute("aria-pressed", "true");
  for (const layer of ["fr", "gal", "modes", "arrow"]) {
    const button = page.locator(`button[data-layer="${layer}"]`);
    await button.click();
    await expect(button).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(`.layer[data-layer="${layer}"]`)).toHaveAttribute(
      "aria-hidden",
      "false",
    );
  }
  await page.locator("#ar").scrollIntoViewIfNeeded();
  await page.screenshot({ path: `test-results/${info.project.name}-ar.png` });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.goto("/presentation.html");
  await expect(page.locator("h1").first()).toContainText("XREAL");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("link", { name: "Лаборатория", exact: true }).click();
  await expect(page).toHaveURL(/workspace.html/);
  const archive = await page.request.get("/downloads/roomscope-core.zip");
  expect(archive.ok()).toBe(true);
  expect((await archive.body()).subarray(0, 2).toString()).toBe("PK");
});
