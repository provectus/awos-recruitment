# Infrastructure Cost Estimation

Analyze Terraform infrastructure and estimate AWS costs.

## Workflow

1. **Discovery:** `Glob: **/*.tf`
2. **Parse Resources:** Identify AWS resources (EC2, RDS, S3, NAT Gateways, ALB, Lambda, EBS, VPC endpoints)
3. **Calculate Costs:** Apply AWS us-east-1 2025 pricing (730 hours/month for compute)
4. **Generate Report:** Profile-appropriate cost analysis with optimization recommendations

## Pricing Reference (us-east-1)

- **EC2:** t3.micro=$7.59/mo, t3.small=$15.18/mo, t3.medium=$30.37/mo
- **EBS:** gp3=$0.08/GB/mo, gp2=$0.10/GB/mo
- **NAT Gateway:** $32.85/mo + $0.045/GB
- **ALB:** $16.43/mo + LCU charges
- **S3:** $0.023/GB/mo (Standard)
- **CloudWatch:** detailed monitoring $2.10/instance/mo

## Profile Output

### Enthusiast
- Simple summary: "Your infrastructure will cost about $XX/month"
- Top 3 costs with relatable comparisons
- 1-2 easy optimization tips
- Traffic light system: 🟢 <$25, 🟡 $25-$100, 🔴 >$100

### DevOps
- Full markdown report with tables and emojis
- Cost breakdown by category and file
- Monthly and annual projections with percentages
- Detailed optimization opportunities with savings calculations
- Actionable recommendations: Reserved Instances, right-sizing, monitoring adjustments

## Output Format (DevOps)

```markdown
# 💰 AWS Infrastructure Cost Analysis

**Region:** us-east-1 | **Date:** [current date]

## 📊 Cost Summary

| Category | Monthly | Annual | % of Total |
|----------|--------:|-------:|-----------:|
| Compute | $X.XX | $X.XX | XX% |
| Storage | $X.XX | $X.XX | XX% |
| **TOTAL** | **$X.XX** | **$X.XX** | **100%** |

---

## 📁 Breakdown by File

[Tables showing resources per file with costs]

---

## 💡 Optimization Opportunities

| Recommendation | Current | Optimized | Savings |
|----------------|--------:|----------:|--------:|
| Reserved Instance | $X.XX | $X.XX | XX% |

---

⚠️ Estimates based on standard on-demand pricing. Actual costs vary with usage.
```

## Notes

- Stop execution if no `.tf` files found
- Estimates assume standard on-demand pricing
- Include disclaimer that actual costs vary with usage patterns
