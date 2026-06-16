import { expect, test } from "@playwright/test"

test("starts the dashboard shell", async ({ page }) => {
  await page.goto("/")

  await expect(page).toHaveTitle(/EQ Command Center/)
  await expect(page.locator("main")).toContainText("EQ Command Center")
  await expect(page.getByRole("button", { name: "Check API" })).toBeVisible()
})
