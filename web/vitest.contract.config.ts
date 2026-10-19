import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: { environment: 'node', include: ['checks/view.check.ts'] },
})
