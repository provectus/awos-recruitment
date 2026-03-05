# Question Framework

All questions MUST use the `AskUserQuestion` tool to get answers from the user.

## Profile Question (Ask Once — Skip if Already Set)
If the profile has already been selected in this conversation, do NOT ask again. Otherwise, use `AskUserQuestion` to ask:
```
Before we start, are you:
1. Enthusiast - Keep it simple, I just want things running
2. DevOps - Show me the full picture (state, modules, pipelines)
```

## Profile Approaches

| Aspect    | Enthusiast                                        | DevOps                                      |
|-----------|---------------------------------------------------|---------------------------------------------|
| Language  | "S3 = cloud storage", "EC2 = virtual server"      | Technical terms: state, modules, workspaces |
| Questions | Minimal, use smart defaults (us-east-1, t3.micro) | CI/CD, monitoring, tagging, blast radius    |
| Costs     | "~$10/month, like a coffee"                       | Detailed breakdown + optimization tips      |

## Question Types

Use `AskUserQuestion` for each type:

| Type           | When                   | How                                                |
|----------------|------------------------|----------------------------------------------------|
| Confirmation   | Before deploy/destroy  | Show impact, require yes/no                        |
| Choice         | Multiple options exist | 2-4 options with costs                             |
| Info Gathering | Missing params         | AWS region, VPC, subnet, tags, instance type       |
| Destructive    | Destroy operations     | List AWS resources, data loss risks, require "yes" |

## Best Practices

1. Explain before asking
2. Offer defaults (us-east-1, t3.micro, gp3)
3. Be specific about consequences
4. Show costs upfront
5. Confirm understanding
