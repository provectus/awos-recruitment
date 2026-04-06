# Metrics and Alarms

## Built-in Lambda Metrics

Lambda publishes these metrics to CloudWatch automatically (no instrumentation required):

| Metric | Unit | What it tells you |
|---|---|---|
| `Invocations` | Count | Number of times your function was invoked |
| `Duration` | Milliseconds | Execution time (use p50, p90, p99 percentiles) |
| `Errors` | Count | Invocations that resulted in a function error |
| `Throttles` | Count | Invocations rejected due to concurrency limits |
| `ConcurrentExecutions` | Count | Number of concurrent function instances |
| `UnreservedConcurrentExecutions` | Count | Concurrency used from the unreserved pool |
| `ProvisionedConcurrencyInvocations` | Count | Invocations served by provisioned environments |
| `ProvisionedConcurrencySpilloverInvocations` | Count | Invocations that exceeded provisioned concurrency |
| `ProvisionedConcurrencyUtilization` | Percentage | How much of provisioned concurrency is being used |
| `IteratorAge` | Milliseconds | Age of the last record processed (stream sources only) |
| `DeadLetterErrors` | Count | Failed attempts to send to DLQ |
| `AsyncEventsDropped` | Count | Async events dropped after all retries exhausted (no DLQ configured) |

## Recommended Alarms

### Critical alarms (set up for every production function)

| Metric | Statistic | Period | Threshold | Action |
|---|---|---|---|---|
| `Errors` | Sum | 1 min | > 0 for 3 consecutive periods | Page oncall; investigate function failures |
| `Throttles` | Sum | 1 min | > 0 for 3 consecutive periods | Request concurrency increase or review traffic |
| `Duration` | p99 | 5 min | > 80% of timeout | Investigate latency; risk of timeouts |

### Important alarms (set up for business-critical functions)

| Metric | Statistic | Period | Threshold | Action |
|---|---|---|---|---|
| `ConcurrentExecutions` | Maximum | 1 min | > 80% of reserved concurrency | Scale concurrency or investigate traffic |
| `IteratorAge` | Maximum | 1 min | > 30,000 ms | Falling behind on stream processing; add shards or optimize |
| `DeadLetterErrors` | Sum | 5 min | > 0 | DLQ delivery failures; check DLQ permissions and capacity |
| `AsyncEventsDropped` | Sum | 5 min | > 0 | Events being lost; configure a DLQ |

### Provisioned concurrency alarms

| Metric | Statistic | Period | Threshold | Action |
|---|---|---|---|---|
| `ProvisionedConcurrencyUtilization` | Average | 5 min | > 85% | Scale up provisioned concurrency |
| `ProvisionedConcurrencySpilloverInvocations` | Sum | 5 min | > 0 sustained | Cold starts occurring; increase provisioned concurrency |
| `ProvisionedConcurrencyUtilization` | Average | 5 min | < 20% sustained | Over-provisioned; reduce to save cost |

## Embedded Metric Format (EMF)

### Why EMF over PutMetricData

| Approach | Latency impact | Cost | Complexity |
|---|---|---|---|
| `PutMetricData` API call in handler | Adds network round-trip to each invocation | API call charges + higher function duration | Error handling for API failures |
| EMF (metrics in structured logs) | Zero -- metrics emitted as log lines | Standard CloudWatch Logs ingestion | Minimal -- structured log lines |

### How EMF works

1. Your function writes a specially formatted JSON log line
2. CloudWatch Logs automatically extracts metrics from the log
3. Metrics appear in CloudWatch Metrics with dimensions and namespaces

### EMF structure

```json
{
  "_aws": {
    "Timestamp": 1234567890,
    "CloudWatchMetrics": [{
      "Namespace": "MyService",
      "Dimensions": [["FunctionName", "Environment"]],
      "Metrics": [
        { "Name": "ProcessingTime", "Unit": "Milliseconds" },
        { "Name": "ItemsProcessed", "Unit": "Count" }
      ]
    }]
  },
  "FunctionName": "order-processor",
  "Environment": "production",
  "ProcessingTime": 145,
  "ItemsProcessed": 12
}
```

### Powertools for AWS Lambda

Instead of manually formatting EMF, use the Metrics utility from Powertools for AWS Lambda. Available for Python, TypeScript, Java, and .NET. It handles:

- EMF JSON formatting
- Namespace and dimension management
- Automatic flushing at the end of invocation
- Default dimensions (function name, service)

## Structured Logging

### Why structured JSON logging

| Plain text | Structured JSON |
|---|---|
| `Error processing order 123` | `{"level": "ERROR", "message": "Error processing order", "orderId": "123", "error": "timeout"}` |
| Hard to search and filter | CloudWatch Logs Insights queries: `fields @timestamp, orderId | filter level = "ERROR"` |
| No consistent format across functions | Consistent schema enables dashboards and automated analysis |

### What to include in every log entry

| Field | Purpose |
|---|---|
| `level` | Severity (DEBUG, INFO, WARN, ERROR) |
| `message` | Human-readable description |
| `timestamp` | ISO 8601 format |
| `requestId` | Lambda request ID (from context) |
| `correlationId` | End-to-end trace identifier |
| `service` | Service/function name |

### Correlation IDs

In distributed systems, trace a request across services:

1. Extract or generate a correlation ID at the entry point (API Gateway, first Lambda)
2. Pass it through all downstream calls (HTTP headers, SQS message attributes, event metadata)
3. Include it in every log entry
4. Use CloudWatch Logs Insights or X-Ray to search across functions by correlation ID

## AWS X-Ray

Enable active tracing to visualize request flow across Lambda and downstream services:

- **Traces** -- end-to-end view of a request across services
- **Segments** -- per-service timing (Lambda initialization, invocation, overhead)
- **Subsegments** -- individual operations (DynamoDB call, HTTP request)
- **Service map** -- visual topology of your application

### When to use X-Ray vs CloudWatch

| Need | Use |
|---|---|
| Per-function health and alerting | CloudWatch Metrics + Alarms |
| Cross-service latency analysis | X-Ray |
| Debugging a specific slow request | X-Ray traces |
| Aggregate performance trends | CloudWatch Metrics dashboards |
| Custom business metrics | EMF via CloudWatch Logs |

## Cost Anomaly Detection

AWS Cost Anomaly Detection uses ML to identify unusual spending patterns:

- Detects anomalies within 24 hours of usage
- Requires Cost Explorer to be enabled
- Configure alerts for Lambda-specific cost anomalies
- Catches runaway functions, recursive invocations, and unexpected traffic spikes that drive cost

### Setup

1. Enable Cost Explorer in your AWS account
2. Access Cost Anomaly Detection from the Cost Management console
3. Create a cost monitor for Lambda service specifically
4. Configure SNS notifications for detected anomalies
