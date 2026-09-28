# GraphQL Reference

## Supported input formats
- SDL schema file (`.graphql` / `.gql`)
- Introspection JSON (from `__schema` query)

## Parse model
For each query/mutation/subscription in the schema extract:
```
{
  operation: query|mutation|subscription,
  name, arguments: [{ name, type, required }],
  returnType
}
```

## Test framework: Playwright TS (default for GraphQL)

```typescript
// tests/graphql/<operation>.spec.ts
import { test, expect } from '../fixtures';

const GQL_ENDPOINT = '/graphql';

test.describe('Query: getUser', () => {

  test('test_query_getUser_happy_valid_id', async ({ api }) => {
    const res = await api.post(GQL_ENDPOINT, {
      data: {
        query: `query GetUser($id: ID!) { getUser(id: $id) { id name email } }`,
        variables: { id: '00000000-0000-0000-0000-000000000001' }
      }
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body).not.toHaveProperty('errors');
    expect(body.data.getUser).toHaveProperty('id');
  });

  test('test_query_getUser_neg_missing_id', async ({ api }) => {
    const res = await api.post(GQL_ENDPOINT, {
      data: {
        query: `query GetUser($id: ID!) { getUser(id: $id) { id } }`,
        variables: {}
      }
    });
    const body = await res.json();
    expect(body).toHaveProperty('errors');
  });

});

test.describe('Mutation: createUser', () => {

  test('test_mutation_createUser_happy_valid_input', async ({ api }) => {
    const res = await api.post(GQL_ENDPOINT, {
      data: {
        query: `mutation CreateUser($input: CreateUserInput!) {
          createUser(input: $input) { id name email }
        }`,
        variables: { input: { name: 'test-string-name', email: 'test@example.com' } }
      }
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body).not.toHaveProperty('errors');
    expect(body.data.createUser).toHaveProperty('id');
  });

});
```

## Notes
- GraphQL always returns 200; check `body.errors` for failures
- Auth is handled identically to REST (Bearer/API Key in headers)
- Load tests: same endpoint `/graphql` for all operations
