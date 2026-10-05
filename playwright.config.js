import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './tests/browser',
  fullyParallel: true,
  use: { baseURL: process.env.BASE_URL || 'http://127.0.0.1:5173', trace: 'retain-on-failure' },
  projects: [
    { name:'desktop', use:{ ...devices['Desktop Chrome'], viewport:{width:1440,height:960} } },
    { name:'mobile', use:{ ...devices['iPhone 13'], defaultBrowserType:'chromium' } },
  ],
  webServer: process.env.BASE_URL ? undefined : { command:'npm run dev -- --port 5173 --strictPort', url:'http://127.0.0.1:5173', reuseExistingServer:!process.env.CI },
});
