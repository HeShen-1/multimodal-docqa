import { expect, test } from "@playwright/test";

test("redirects to login when no token", async ({ page }) => {
  await page.goto("/workspace");
  await expect(page).toHaveURL(/\/login/);
});

