# TypeScript + Playwright Reference

## Project layout
```
api-tests/
├── playwright.config.ts
├── package.json
├── .env.example
├── tests/
│   ├── fixtures.ts          # shared APIRequestContext + auth
│   ├── <tag>.spec.ts        # one file per OpenAPI tag
│   └── workflows/
│       └── <tag>-workflow.spec.ts
├── helpers/
│   ├── factories.ts         # data synthesizers per schema
│   └── schema-validator.ts  # response schema assertions
└── reports/                 # HTML output goes here
```

## playwright.config.ts
```typescript
import { defineConfig } from '@playwright/test';
import * as dotenv from 'dotenv';
dotenv.config();

export default defineConfig({
  testDir: './tests',
  reporter: [
    ['html', { outputFolder: 'reports', open: 'never' }],
    ['json', { outputFile: 'reports/results.json' }],
    ['list']
  ],
  use: {
    baseURL: process.env.BASE_URL,
    extraHTTPHeaders: buildAuthHeaders(),
  },
});

function buildAuthHeaders(): Record<string, string> {
  if (process.env.auth_bearer) return { Authorization: `Bearer ${process.env.auth_bearer}` };
  if (process.env.auth_apikey) return { [process.env.auth_apikey_header || 'X-API-Key']: process.env.auth_apikey };
  if (process.env.auth_basic)  return { Authorization: `Basic ${process.env.auth_basic}` };
  return {};
}
```

## fixtures.ts
```typescript
import { test as base, APIRequestContext } from '@playwright/test';

type Fixtures = { api: APIRequestContext; anonApi: APIRequestContext };

export const test = base.extend<Fixtures>({
  api: async ({ playwright }, use) => {
    const ctx = await playwright.request.newContext({
      baseURL: process.env.BASE_URL,
      extraHTTPHeaders: buildAuthHeaders(),
    });
    await use(ctx);
    await ctx.dispose();
  },
  anonApi: async ({ playwright }, use) => {
    const ctx = await playwright.request.newContext({ baseURL: process.env.BASE_URL });
    await use(ctx);
    await ctx.dispose();
  },
});

export { expect } from '@playwright/test';

function buildAuthHeaders(): Record<string, string> {
  if (process.env.auth_bearer) return { Authorization: `Bearer ${process.env.auth_bearer}` };
  if (process.env.auth_apikey) return { [process.env.auth_apikey_header || 'X-API-Key']: process.env.auth_apikey };
  if (process.env.auth_basic)  return { Authorization: `Basic ${process.env.auth_basic}` };
  return {};
}
```

## Test file template
```typescript
import { test, expect } from './fixtures';

test.describe('POST /users', () => {

  test('test_post_users_happy_valid_body', async ({ api }) => {
    const res = await api.post('/users', {
      data: { name: 'test-string-name', email: 'test@example.com' }
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body).toHaveProperty('id');
    expect(body.email).toBe('test@example.com');
  });

  test('test_post_users_neg_missing_email', async ({ api }) => {
    const res = await api.post('/users', { data: { name: 'test-string-name' } });
    expect([400, 422]).toContain(res.status());
  });

  test('test_post_users_neg_no_auth', async ({ anonApi }) => {
    const res = await anonApi.post('/users', {
      data: { name: 'test-string-name', email: 'test@example.com' }
    });
    expect([401, 403]).toContain(res.status());
  });

  test('test_post_users_edge_name_max_length', async ({ api }) => {
    const res = await api.post('/users', {
      data: { name: 'a'.repeat(255), email: 'test@example.com' }  // maxLength value
    });
    expect(res.status()).toBe(201);
  });

  test('test_post_users_edge_name_over_max_length', async ({ api }) => {
    const res = await api.post('/users', {
      data: { name: 'a'.repeat(256), email: 'test@example.com' }  // maxLength + 1
    });
    expect([400, 422]).toContain(res.status());
  });

});

test.describe('GET /users/{id}', () => {

  test('test_get_users_id_happy_existing', async ({ api }) => {
    // Setup: create resource first
    const created = await api.post('/users', {
      data: { name: 'test-string-name', email: 'test@example.com' }
    });
    const { id } = await created.json();

    const res = await api.get(`/users/${id}`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.id).toBe(id);

    // Cleanup
    await api.delete(`/users/${id}`);
  });

  test('test_get_users_id_neg_not_found', async ({ api }) => {
    const res = await api.get('/users/00000000-0000-0000-0000-000000000000');
    expect(res.status()).toBe(404);
  });

});
```

## Workflow test template
```typescript
import { test, expect } from '../fixtures';

test.describe('Users CRUD workflow', () => {
  let resourceId: string;

  test('step1_create_user', async ({ api }) => {
    const res = await api.post('/users', {
      data: { name: 'workflow-user', email: 'workflow@example.com' }
    });
    expect(res.status()).toBe(201);
    resourceId = (await res.json()).id;
    expect(resourceId).toBeTruthy();
  });

  test('step2_read_user', async ({ api }) => {
    const res = await api.get(`/users/${resourceId}`);
    expect(res.status()).toBe(200);
    expect((await res.json()).name).toBe('workflow-user');
  });

  test('step3_update_user', async ({ api }) => {
    const res = await api.put(`/users/${resourceId}`, {
      data: { name: 'workflow-user-updated' }
    });
    expect(res.status()).toBe(200);
    expect((await res.json()).name).toBe('workflow-user-updated');
  });

  test('step4_delete_user', async ({ api }) => {
    const res = await api.delete(`/users/${resourceId}`);
    expect([200, 204]).toContain(res.status());
  });

  test('step5_confirm_deleted', async ({ api }) => {
    const res = await api.get(`/users/${resourceId}`);
    expect(res.status()).toBe(404);
  });
});
```

## package.json
```json
{
  "name": "api-tests",
  "version": "1.0.0",
  "scripts": {
    "test": "playwright test",
    "test:headed": "playwright test --headed",
    "report": "playwright show-report reports"
  },
  "devDependencies": {
    "@playwright/test": "^1.43.0",
    "dotenv": "^16.0.0",
    "typescript": "^5.0.0"
  }
}
```

## tsconfig.json
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "strict": true,
    "esModuleInterop": true,
    "outDir": "dist"
  },
  "include": ["tests/**/*.ts", "helpers/**/*.ts"]
}
```

## Run command
```bash
npm install
npx playwright install --with-deps chromium
cp .env.example .env  # then fill in values
BASE_URL=https://api.example.com auth_bearer=token npm test
```
