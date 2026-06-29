const { test, expect } = require("@playwright/test");
const path = require("path");

const FILE = "http://localhost:9373/index.html";

test("一般合成送出會 POST /api/tts 並顯示結果", async ({ page }) => {
  await page.route("**/api/speakers", (r) => r.fulfill({ json: { speakers: ["hung_yi_lee"] } }));
  await page.route("**/api/tts", (r) =>
    r.fulfill({ contentType: "audio/mpeg", body: Buffer.from([0xff, 0xfb, 0x00, 0x00]) }));
  await page.goto(FILE);
  await page.fill("#text", "測試文字");
  await page.click("#synth");
  await expect(page.locator("#result")).toBeVisible();
  await expect(page.locator("#status")).toHaveText(/完成/);
});

test("克隆未勾同意會被擋", async ({ page }) => {
  await page.route("**/api/speakers", (r) => r.fulfill({ json: { speakers: [] } }));
  await page.goto(FILE);
  await page.click('.seg button[data-tab="clone"]');
  await page.click("#synth");
  await expect(page.locator("#status")).toHaveText(/同意/);
});

test("克隆模式顯示朗讀腳本，換一段會更換內容", async ({ page }) => {
  await page.route("**/api/speakers", (r) => r.fulfill({ json: { speakers: [] } }));
  await page.goto(FILE);
  await page.click('.seg button[data-tab="clone"]');
  const script = page.locator("#script-text");
  await expect(script).toBeVisible();
  const first = await script.textContent();
  await page.click("#script-next");
  await expect(script).not.toHaveText(first);
});

test("範例 chip 一鍵填入文字框", async ({ page }) => {
  await page.route("**/api/speakers", (r) => r.fulfill({ json: { speakers: [] } }));
  await page.goto(FILE);
  const chip = page.locator("#examples .chip").nth(1);
  const full = await chip.getAttribute("title");
  await chip.click();
  await expect(page.locator("#text")).toHaveValue(full);
});

test("產生兩次會出現歷史紀錄，最舊的進入可比較清單", async ({ page }) => {
  await page.route("**/api/speakers", (r) => r.fulfill({ json: { speakers: [] } }));
  await page.route("**/api/tts", (r) =>
    r.fulfill({ contentType: "audio/mpeg", body: Buffer.from([0xff, 0xfb, 0x00, 0x00]) }));
  await page.goto(FILE);
  await page.fill("#text", "第一句");
  await page.click("#synth");
  await expect(page.locator("#status")).toHaveText(/完成/);
  await expect(page.locator("#history")).toBeHidden();
  await page.fill("#text", "第二句");
  await page.click("#synth");
  await expect(page.locator("#history")).toBeVisible();
  await expect(page.locator("#history-list .clip-item")).toHaveCount(1);
  await page.click("#history-clear");
  await expect(page.locator("#result")).toBeHidden();
});

test("GPU 面板顯示即時使用率", async ({ page }) => {
  await page.route("**/api/speakers", (r) => r.fulfill({ json: { speakers: [] } }));
  await page.route("**/api/gpu", (r) =>
    r.fulfill({ json: { available: true, util: 73, mem_util: 40, power: 120, temp: 55, clock: 2400 } }));
  await page.goto(FILE);
  await expect(page.locator("#gpu-pct")).toHaveText("73%");
  await expect(page.locator("#gpu-readout")).toContainText("120 W");
});

test("內建語者試聽會帶 speaker 呼叫 /api/tts", async ({ page }) => {
  await page.route("**/api/speakers", (r) => r.fulfill({ json: { speakers: ["hung_yi_lee"] } }));
  let sentSpeaker = null;
  await page.route("**/api/tts", (r) => {
    sentSpeaker = (r.request().postDataJSON() || {}).speaker;
    return r.fulfill({ contentType: "audio/mpeg", body: Buffer.from([0xff, 0xfb, 0x00, 0x00]) });
  });
  await page.goto(FILE);
  await page.click('.seg button[data-tab="preset"]');
  await page.click("#speaker-preview");
  await expect.poll(() => sentSpeaker).toBe("hung_yi_lee");
});
