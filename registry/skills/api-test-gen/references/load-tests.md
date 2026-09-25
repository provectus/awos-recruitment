# Load Testing Reference

## Default profile
- Virtual users: 10
- Duration: 30 seconds
- Ramp-up: 5 seconds
- Target: happy-path endpoints only

## Node.js — autocannon

```typescript
// load-tests/run-load.ts
import autocannon from 'autocannon';
import * as dotenv from 'dotenv';
dotenv.config();

const BASE_URL = process.env.BASE_URL!;
const AUTH = process.env.auth_bearer
  ? { Authorization: `Bearer ${process.env.auth_bearer}` }
  : {};

async function runLoad(path: string, method: string, body?: object) {
  const result = await autocannon({
    url: `${BASE_URL}${path}`,
    connections: 10,        // virtual users
    duration: 30,           // seconds
    method: method as any,
    headers: { 'Content-Type': 'application/json', ...AUTH },
    body: body ? JSON.stringify(body) : undefined,
  });
  return {
    path,
    method,
    requests: result.requests,
    latency: result.latency,
    throughput: result.throughput,
    errors: result.errors,
  };
}

// Generated load test calls — one per happy-path endpoint
async function main() {
  const results = [];
  // results.push(await runLoad('/users', 'GET'));
  // results.push(await runLoad('/users', 'POST', { name: 'load-user', email: 'load@example.com' }));
  console.table(results.map(r => ({
    endpoint: `${r.method} ${r.path}`,
    'req/sec': r.requests.mean,
    'p99 latency ms': r.latency.p99,
    errors: r.errors,
  })));
}

main();
```

## Python — locust

```python
# load-tests/locustfile.py
import os
from locust import HttpUser, task, between
from dotenv import load_dotenv
load_dotenv()

class APIUser(HttpUser):
    wait_time = between(0.1, 0.5)
    headers = {}

    def on_start(self):
        if os.getenv("auth_bearer"):
            self.headers = {"Authorization": f"Bearer {os.getenv('auth_bearer')}"}

    # Generated task per happy-path endpoint
    # @task
    # def get_users(self):
    #     self.client.get("/users", headers=self.headers)

    # @task
    # def create_user(self):
    #     self.client.post("/users",
    #       json={"name": "load-user", "email": "load@example.com"},
    #       headers=self.headers)
```

## Run commands

Node autocannon:
```bash
npm install autocannon
npx ts-node load-tests/run-load.ts
```

Python locust:
```bash
pip install locust --break-system-packages
locust -f load-tests/locustfile.py --headless \
  --host $BASE_URL -u 10 -r 2 --run-time 30s \
  --html reports/load-report.html
```
