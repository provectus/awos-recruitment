# HTML Report Template

Generate `reports/index.html` using this structure. Fill in values from test results.
If tests weren't run yet, show status as "NOT EXECUTED" for all rows.

## Template
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>API Test Report — {{spec_title}}</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #f5f5f5; color: #222; }
  header { background: #1a1a2e; color: white; padding: 24px 32px; }
  header h1 { margin: 0 0 6px; font-size: 1.4rem; }
  header p  { margin: 0; opacity: 0.7; font-size: 0.85rem; }
  .summary  { display: flex; gap: 16px; padding: 20px 32px; background: white;
               border-bottom: 1px solid #e0e0e0; flex-wrap: wrap; }
  .stat { padding: 12px 20px; border-radius: 8px; text-align: center; min-width: 90px; }
  .stat .num { font-size: 2rem; font-weight: 700; }
  .stat .lbl { font-size: 0.75rem; text-transform: uppercase; opacity: 0.7; }
  .total  { background: #e8eaf6; }
  .passed { background: #e8f5e9; color: #2e7d32; }
  .failed { background: #ffebee; color: #c62828; }
  .skipped{ background: #fff8e1; color: #f57f17; }
  .rate   { background: #e3f2fd; color: #1565c0; }
  .container { padding: 24px 32px; }
  .tag-section { background: white; border-radius: 8px; margin-bottom: 16px;
                  box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
  .tag-header { padding: 14px 20px; background: #f8f9fa; border-bottom: 1px solid #e0e0e0;
                 font-weight: 600; cursor: pointer; display: flex; justify-content: space-between; }
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 10px 16px; text-align: left; border-bottom: 1px solid #f0f0f0;
            font-size: 0.9rem; }
  th { background: #fafafa; font-weight: 600; font-size: 0.8rem; text-transform: uppercase;
       color: #666; }
  .badge { padding: 3px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
  .badge.pass { background: #e8f5e9; color: #2e7d32; }
  .badge.fail { background: #ffebee; color: #c62828; }
  .badge.skip { background: #fff8e1; color: #f57f17; }
  .badge.none { background: #eeeeee; color: #616161; }
  .error-detail { font-family: monospace; font-size: 0.8rem; background: #ffebee;
                   padding: 8px 12px; border-left: 3px solid #c62828; margin-top: 4px; }
  .coverage { width: 100%; border-collapse: collapse; margin-top: 24px; }
  .coverage th, .coverage td { padding: 8px 12px; border: 1px solid #e0e0e0; font-size: 0.85rem; }
  .coverage th { background: #f5f5f5; }
  .cov-yes { color: #2e7d32; font-weight: 600; }
  .cov-no  { color: #bdbdbd; }
</style>
</head>
<body>
<header>
  <h1>API Test Report — {{spec_title}} v{{spec_version}}</h1>
  <p>Generated: {{timestamp}} &nbsp;|&nbsp; Framework: {{framework}} &nbsp;|&nbsp; Base URL: {{base_url}}</p>
</header>

<div class="summary">
  <div class="stat total" ><div class="num">{{total}}</div><div class="lbl">Total</div></div>
  <div class="stat passed"><div class="num">{{passed}}</div><div class="lbl">Passed</div></div>
  <div class="stat failed"><div class="num">{{failed}}</div><div class="lbl">Failed</div></div>
  <div class="stat skipped"><div class="num">{{skipped}}</div><div class="lbl">Skipped</div></div>
  <div class="stat rate"  ><div class="num">{{pass_rate}}%</div><div class="lbl">Pass Rate</div></div>
</div>

<div class="container">

  <!-- Repeat this block per tag -->
  {{#each tags}}
  <div class="tag-section">
    <div class="tag-header">
      <span>{{tag_name}}</span>
      <span>{{tag_passed}}/{{tag_total}} passed</span>
    </div>
    <table>
      <thead><tr>
        <th>Test Name</th><th>Type</th><th>Method</th><th>Path</th>
        <th>Status</th><th>Duration</th>
      </tr></thead>
      <tbody>
        {{#each tests}}
        <tr>
          <td>{{name}}</td>
          <td>{{scenario_type}}</td>
          <td><code>{{method}}</code></td>
          <td><code>{{path}}</code></td>
          <td><span class="badge {{status_class}}">{{status}}</span></td>
          <td>{{duration_ms}}ms</td>
        </tr>
        {{#if error}}
        <tr><td colspan="6"><div class="error-detail">{{error}}</div></td></tr>
        {{/if}}
        {{/each}}
      </tbody>
    </table>
  </div>
  {{/each}}

  <!-- Coverage matrix -->
  <h3>Coverage Matrix</h3>
  <table class="coverage">
    <thead><tr>
      <th>Endpoint</th><th>Happy</th><th>Negative</th><th>Edge</th><th>Workflow</th>
    </tr></thead>
    <tbody>
      {{#each endpoints}}
      <tr>
        <td><code>{{method}} {{path}}</code></td>
        <td class="{{#if happy}}cov-yes{{else}}cov-no{{/if}}">{{#if happy}}✓{{else}}—{{/if}}</td>
        <td class="{{#if negative}}cov-yes{{else}}cov-no{{/if}}">{{#if negative}}✓{{else}}—{{/if}}</td>
        <td class="{{#if edge}}cov-yes{{else}}cov-no{{/if}}">{{#if edge}}✓{{else}}—{{/if}}</td>
        <td class="{{#if workflow}}cov-yes{{else}}cov-no{{/if}}">{{#if workflow}}✓{{else}}—{{/if}}</td>
      </tr>
      {{/each}}
    </tbody>
  </table>

</div>
</body>
</html>
```

## How to fill in values

When tests haven't been run, use:
- `total` = number of generated test cases
- `passed` = 0, `failed` = 0, `skipped` = total
- `pass_rate` = "N/A"
- all test status = "NOT EXECUTED" with class `none`

When tests have been run, parse the JSON results file:
- Playwright: `reports/results.json` → `stats` + `suites[].specs[].tests[]`
- pytest: `reports/results.json` → `summary` + `tests[]`
