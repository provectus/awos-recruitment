#!/usr/bin/env python3
"""Tests for block-writes.sh: run with `python3 scripts/block-writes_test.py`.

Each command goes to the hook as a PreToolUse JSON input, once with jq and
python3 on PATH and once without them (the sed fallback). Commands under
ALLOW must exit 0; commands under BLOCK must exit 2.
"""

import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "block-writes.sh")

# Files the commands refer to, created in a temporary project folder.
FILES = {
    "scripts/read.sh": "#!/bin/sh\naws dynamodb describe-table --table-name x\n",
    "scripts/bad.sh": "#!/bin/sh\necho hi\naws dynamodb delete-table --table-name x\n",
    "scripts/nested.sh": "#!/bin/sh\nsh scripts/bad.sh\n",
    "scripts/ok.py": "import json\nprint(json.dumps({}))\n",
    "scripts/bad.py": 'import boto3\nboto3.client("s3").delete_bucket(Bucket="b")\n',
    "cmds.txt": "aws dynamodb delete-table --table-name x\n",
}

ALLOW = [
    "git log --format='%h %ad' --date=short --diff-filter=A -- k8s/argo-cd/argo-cd-server-secret.yaml",
    "git log --oneline -- infra/prod.tfvars",
    "grep -n '^```' docs/a.md",
    "sed -i '' 's/| no — `terraform plan\\/apply` impossible/| no plan or apply/' doc.md",
    "awk -F: '$1>=474 && $1<=800' doc.md",
    "cmp <(sed -n '514,$p' /tmp/a.md) <(sed -n '801,$p' doc.md) && echo same",
    'grep -n -i -E "deploy|terraform apply|ci " context/product/architecture.md | head -40',
    "python3 -I - <<'EOF'\nstep = '''## 0. Select access\n\n```bash\naws configure list-profiles\naws sts get-caller-identity --profile <AWS_PROFILE>\n```\n'''\nprint(step)\nEOF",
    "echo 'run terraform plan in CI; never kubectl delete here'",
    'aws dynamodb list-tables --query \'TableNames\' --output text | tr \'\\t\' \'\\n\' | while read -r t; do aws dynamodb describe-table --table-name "$t" --query \'Table.TableSizeBytes\'; done',
    'aws sts get-caller-identity',
    'aws dynamodb describe-table --table-name x --region eu-central-1',
    'aws s3 ls s3://b',
    "aws secretsmanager list-secrets --query 'SecretList[].Name'",
    "aws lambda get-function-configuration --function-name f --query 'Environment.Variables | keys(@)'",
    'for t in a b; do aws dynamodb describe-continuous-backups --table-name "$t"; done',
    'export AWS_PROFILE=p AWS_REGION=eu-central-1 AWS_PAGER=""',
    'AWS_PROFILE=p aws s3api get-bucket-replication --bucket b',
    "timeout 30 aws ec2 describe-regions --query 'Regions[].RegionName'",
    'aws eks update-kubeconfig --name c --region r',
    'az aks get-credentials -g rg -n c',
    'gcloud container clusters get-credentials c --region r',
    'az account set --subscription s',
    'gcloud config set project p',
    "az functionapp config appsettings list -g rg -n f --query '[].name'",
    "gcloud run services describe s --region r --format='value(spec.template.spec.containers[0].env[].name)'",
    'gsutil -m du -s gs://b',
    'kubectl get pods -A',
    'kubectl get secrets -n x',
    'kubectl --kubeconfig ~/.kube/config get deploy -A',
    'helm list -A',
    'kustomize build deploy/overlays/production | yq \'.kind + "/" + .metadata.name\'',
    'terraform version',
    'git log --oneline -5 && git status --short',
    'git show HEAD --stat',
    'git branch -a',
    'git config --get remote.origin.url',
    'grep -rn region infra/',
    'grep -rln password infra/',
    "grep -rn -E 'aws_secretsmanager_secret|aws_ssm_parameter' infra/",
    'cat infra/main.tf',
    'cat .env.example',
    'ls -la .env infra/',
    'F=$(mktemp) && echo x > "$F" && rm -f /tmp/x',
    'python3 -c \'import json,sys; print(json.load(sys.stdin)["a"])\' < /tmp/x.json',
    'aws dynamodb list-tables | python3 -c \'import json,sys; print(len(json.load(sys.stdin)["TableNames"]))\'',
    'sh scripts/read.sh',
    'python3 scripts/ok.py',
    'curl -s https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json -o /tmp/p.json',
    "jq '.items | length' /tmp/x.json",
    "find infra -name '*.tf'",
    'git tag -l',
    'git tag',
    "git tag --list 'v*'",
    'git branch --show-current',
    "grep -rln -i 'BEGIN RSA PRIVATE' .",
    'bash scripts/read.sh',
    # From the ClusterQuest debug run (2026-11-06) and the allow-list.
    "cat >> /tmp/facts.md <<'EOF'\n- Route 53 health check: free; $0.50/month per check | first 50 free\nEOF",
    "cat > /tmp/x.sh <<'EOF'\naws s3 rb s3://b --force\nEOF",
    'dig +short example.com CNAME; dig +short NS example.com | head -3',
    'gh secret list --repo o/r',
    'aws pricing get-products --region us-east-1 --service-code AmazonDynamoDB --filters Type=TERM_MATCH,Field=regionCode,Value=eu-west-1',
    'for b in a b; do aws s3api head-bucket --bucket $b >/dev/null 2>&1; echo "$b exit=$?"; done',
    "for t in a b; do n=x-$t; echo \"== $n\"; aws dynamodb describe-table --table-name $n --query 'Table.TableStatus'; done",
    "python3 - \"$F\" <<'EOF'\nimport sys, re\ns = open(sys.argv[1]).read()\nopen(sys.argv[1], 'w').write(s.replace('a', 'b'))\nEOF",
    'sleep 1; echo waiting',
    "git grep -nE 'eu-central-1' -- ':!context' ':!*.md' | cut -d: -f1 | sort -u",
    'git -C infra log --oneline -3',
    'kubectl -n prod get deploy',
    'kubectl config get-contexts',
    'helm -n prod status app',
    'terraform -chdir=infra validate',
    'terraform fmt -check -recursive infra',
    'az sql db show -g rg -n db',
    'gcloud sql instances describe db --format=json',
    'gcloud alpha run services list',
    'echo "lines: $(wc -l < doc.md)"',
    'F=$(mktemp -d) && cp doc.md "$F"/',
    'case $x in prod) echo p ;; esac',
    'mkdir -p context/disaster-recovery/production',
    'aws configure list-profiles',
    'aws --version',
    # From the Kubeflow (Azure, AKS) debug run, 2026-11-06.
    "az acr show-usage -n r --query \"value[?name=='Size'].currentValue\" -o tsv",
    'curl -s -G "https://prices.azure.com/api/retail/prices" --data-urlencode "\\$filter=armRegionName eq \'northcentralus\'" | jq -r \'.Items[].unitPrice\'',
    "python3 - <<'EOF'\np='dr-recovery-today.md'\ns=open(p).read()\ns=s.replace('a', 'Other team requests: the kubernetes socket and subprocess limits')\nopen(p,'w').write(s)\nEOF",
    "grep -l -i -E 'password|secret|token|key' input-variables.auto.tfvars",
    "grep -rl ClusterSecretStore k8s/kubeflow/secrets",
    'ls k8s/kubeflow/secrets/team-a',
    'ls k8s/secrets',
    'grep -rl region k8s/secrets',
    "kubectl get cm -n argo-cd argocd-cm -o jsonpath='{.data.application\\.resourceTrackingMethod}'",
    "kubectl get deploy,sts -n kubeflow -o custom-columns=KIND:.kind,NAME:.metadata.name --no-headers",
    'kubectl get applications -n argo-cd --no-headers',
    'kubectl get pvc -A -o wide',
    'F=doc.md && head -n 5 "$F" > "$F.tmp" && mv "$F.tmp" "$F"',
    'mv /tmp/x.md context/x.md',
    'aws configure get region --profile p',
    "aws cognito-idp describe-user-pool-client --user-pool-id p --client-id c --query 'UserPoolClient.{Callbacks:CallbackURLs,Logout:LogoutURLs}'",
    "aws ecs describe-task-definition --task-definition t --query 'taskDefinition.containerDefinitions[].secrets[].name'",
    "aws lambda get-function --function-name f --query 'Configuration.{name:FunctionName,runtime:Runtime}'",
    'aws secretsmanager describe-secret --secret-id x --query ReplicationStatus',
    'aws cognito-idp list-user-pool-clients --user-pool-id p',
    'P=$(aws cognito-idp list-user-pools --max-results 20 --query "UserPools[?Name==\'x\'].Id" --output text); echo "pool=$P"',
    'P="--profile p --region eu-central-1"; aws dynamodb describe-table --table-name x $P',
    'q(){ aws pricing get-products --region us-east-1 --service-code "$1" --output json; }; q AmazonDynamoDB',
    'cp doc.md /tmp/doc.md && sed -i "" s/a/b/ /tmp/doc.md && mv /tmp/doc.md doc.md',
    'echo "- ID **E1** verified with \\`aws cloudfront list-distributions\\`" >> /tmp/facts.md',
    'aws s3api head-bucket --bucket b 2>&1 | tail -1',
    # Field filters that select names, settings or one named ConfigMap key.
    "kubectl get cm -n kubeflow pipeline-install-config -o jsonpath='{.data.bucketName}'",
    "kubectl get cm -n kubeflow pipeline-install-config -o jsonpath='{.data}' | jq -r 'keys[]'",
    "kubectl get deploy -n kubeflow ml-pipeline -o jsonpath='{.spec.template.spec.containers[*].env[*].name}'",
    "kubectl get pv -o custom-columns=CLAIM:.spec.claimRef.name,HANDLE:.spec.csi.volumeHandle --no-headers",
    "gh api repos/o/r/hooks --jq '.[] | {id, events, active, host: (.config.url | split(\"/\")[2])}'",
    "gh api repos/o/r/hooks/1/deliveries --jq '.[0] | {status, status_code, delivered_at}'",
    "az keyvault secret list --vault-name kv --query \"[?name=='github-token' || name=='datadog-api-token'].name\" -o tsv",
    "aws secretsmanager list-secrets --query 'SecretList[].Name' --output text",
    "aws iam list-access-keys --user-name ci --query 'AccessKeyMetadata[].{id:AccessKeyId,status:Status}'",
    "az vm show -g rg -n vm1 --query osProfile.linuxConfiguration.disablePasswordAuthentication",
    "az storage account show -n sa --query '{sharedKey:allowSharedKeyAccess,tls:minimumTlsVersion}'",
    "aws lambda get-function-configuration --function-name f --query '{env:Environment.Variables | keys(@), role:Role}'",
    "az aks get-credentials -g rg -n aks1 --overwrite-existing",
    "gcloud run services describe api --format='value(spec.template.spec.containers[0].env[].name)'",
    'find . | xargs grep -l bucket',
    'git ls-files | xargs -n1 shasum',
    "find . -name '*.tf' -exec grep -l bucket {} +",
    'find . -name "*.tf" | xargs wc -l',
    # Flags before the resource type, awk, sed, sort and git reads that stay allowed.
    'kubectl get -n prod secrets',
    'kubectl get -A pods -o wide',
    'kubectl -n p get pvc -o yaml',
    "kubectl get -n p deploy -o custom-columns=N:.metadata.name",
    "awk -F: '{print $1 || $2}' f",
    "awk '$3 > 100 {print $1}' f",
    "awk -F: 'NR>1{print prev\" -> \"($1-p)} {p=$1}' f",
    "awk '{print \"a>b|c\", $1}' f",
    "awk '{if ($2 > 5) print $1}' f",
    'awk "{print \\$1 \\" -> \\" \\$2}" f',
    "awk -F'|' '{print $1 \"a|b\"}' f",
    "grep -n x f | awk '/plan$/ {print}'",
    "sed -n 's/^name: //p' f",
    "sed 's/one/e/' f",
    'sort -u f',
    'git -C repo log --oneline -5',
    'git grep -c bucket',
    'git ls-remote origin',
]

BLOCK = [
    "git log -p -- infra/prod.tfvars",
    "git show HEAD:k8s/secrets/db.yaml",
    "git log -L 1,5:infra/prod.tfvars",
    'grep -n "^```" docs/a.md',
    'cat secrets/db.yaml',
    'grep -rn name k8s/secrets',
    "bash -c '$A dynamodb delete-table --table-name x'",
    'echo "`aws dynamodb delete-table --table-name x`"',
    'bash -c "ls; $A dynamodb delete-table --table-name x"',
    "cat > /tmp/x.sh <<'EOF'\naws s3 rb s3://b --force\nEOF\nsh /tmp/x.sh",
    "sh <<'EOF'\naws dynamodb delete-table --table-name x\nEOF",
    'echo $(aws dynamodb delete-table --table-name x)',
    'find . -name x -exec aws s3 rm s3://b/{} \\;',
    "python3 - <<'EOF'\nimport subprocess\nsubprocess.run(['ls'])\nEOF",
    "grep -rn 'aws dynamodb' . | sh",
    'aws dynamodb \\\n  delete-table --table-name x',
    "aws dynamodb 'delete-table' --table-name x",
    'aws dynamodb de\\lete-table --table-name x',
    'A=aws; $A dynamodb delete-table --table-name x',
    'C="aws dynamodb delete-table --table-name x"; eval "$C"',
    'bash -c "$C"',
    'bash -c "aws dynamodb delete-table --table-name x"',
    'echo YXdz | base64 -d | bash',
    '$(echo aws) dynamodb list-tables',
    'xargs -n1 sh < cmds.txt',
    'python3 -c "import boto3; boto3.client(\'dynamodb\').delete_table(TableName=\'x\')"',
    'python3 - <<\'PY\'\nimport subprocess\nsubprocess.run(["aws","s3","rb","s3://b"])\nPY',
    'python3 -m awscli dynamodb delete-table --table-name x',
    'node -e "require(\'child_process\').execSync(\'ls\')"',
    'sh scripts/bad.sh',
    './scripts/bad.sh',
    'sh scripts/nested.sh',
    'python3 scripts/bad.py',
    'curl -X DELETE -H "Authorization: Bearer $T" https://management.azure.com/subscriptions/s',
    "curl -s -d '{}' https://example.com/hook",
    'http POST https://example.com/x',
    'az rest --method delete --url https://management.azure.com/x',
    'curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/role',
    'make deploy',
    'npm run deploy',
    'npx cdk deploy',
    'git push origin main',
    'git commit -am "dr plan"',
    'git reset --hard HEAD~1',
    'git branch -D old',
    'git config user.email x@y',
    'git show HEAD:.env',
    'gh workflow run deploy.yml',
    'gh api -X POST repos/o/r/dispatches',
    'cat .env',
    'head -n 5 .env.production',
    'cat infra/terraform.tfstate',
    'jq . terraform.tfstate.backup',
    'cat ~/.aws/credentials',
    'grep -rn password infra/',
    "rg -i 'api_key' .",
    'sops -d secrets.enc.yaml',
    'vault kv get secret/db',
    'op read op://vault/item/password',
    'argocd app sync prod',
    'flux reconcile kustomization apps',
    'serverless deploy --stage prod',
    'ansible-playbook site.yml',
    'docker push repo/img:1',
    'rm -rf context/',
    'rm -f "$F"',
    'find . -name "*.tf" -delete',
    'aws dynamodb delete-table --table-name x',
    'aws secretsmanager get-secret-value --secret-id x',
    'aws lambda get-function-configuration --function-name f',
    'terraform plan',
    'kubectl get secret x -o yaml',
    'kubectl get --raw /api/v1/namespaces/x/secrets',
    'kustomize build deploy/overlays/production',
    'az keyvault secret show --name x --vault-name v',
    'gcloud secrets versions access latest --secret x',
    'gsutil -m cp x gs://b',
    'git tag v1.0',
    'git tag -d v1.0',
    'git branch -m old new',
    'grep -rn client_secret infra/',
    "grep -rn -i 'BEGIN RSA PRIVATE' .",
    'bash scripts/bad.sh',
    # Not on the read-only list: an allow-list blocks these by default.
    'pulumi up',
    'cdk deploy',
    'terraform apply -auto-approve',
    'tofu state list',
    'terragrunt run-all plan',
    'aws $S delete-table --table-name x',
    'aws dynamodb scan --table-name x',
    'aws s3api get-object --bucket b --key k /tmp/o',
    'aws sts assume-role --role-arn r --role-session-name s',
    'aws lambda invoke --function-name f /tmp/o',
    'aws configure export-credentials',
    'az vm delete -g rg -n vm',
    'az webapp restart -g rg -n app',
    'gcloud run deploy s --image i',
    'gcloud auth print-access-token',
    'gcloud storage cat gs://b/o',
    'gcloud redis instances get-auth-string r',
    'kubectl rollout restart deploy/x',
    'kubectl -n prod exec -it p -- sh',
    'helm upgrade app chart',
    'helm get values app',
    'git fetch',
    'git stash',
    'gh pr create --fill',
    'gh run rerun 1',
    '/usr/local/bin/mytool --apply',
    'docker run img',
    'ssh host uptime',
    'kill 123',
    'printenv',
    'env',
    'chmod +x x.sh',
    'mv doc.md /tmp/x',
    "awk 'BEGIN { system(\"aws s3 rb s3://b\") }'",
    "python3 - <<'EOF'\nimport urllib.request\nurllib.request.urlopen('https://x', data=b'1')\nEOF",
    'echo "$(terraform output)"',
    'cat <(aws s3 rm s3://b/k)',
    'make --list',
    'cat k8s/kubeflow/secrets/team-a/awscreds.yaml',
    "grep -h -E 'kind|name|key' k8s/kubeflow/secrets/team-a/awscreds.yaml",
    'head -20 deploy/db-credentials.yaml',
    'yq . charts/app/values-secret.yaml',
    'kubectl get cm -n auth dex -o yaml',
    'kubectl get deploy -n kubeflow ml-pipeline -o json',
    'kubectl get pods -A -o yaml',
    'kubectl get applications -n argo-cd -o yaml',
    'kubectl describe cm dex -n auth',
    "python3 - <<'EOF'\nimport requests\nrequests.post('https://x', data='1')\nEOF",
    'node -e "require(\'https\').request(\'https://x\')"',
    'mv context/x.md /Users/someone/x.md',
    'mv ../other/x.md x.md && mv x.md ../x.md',
    'aws configure get aws_secret_access_key --profile p',
    "aws cognito-idp describe-user-pool-client --user-pool-id p --client-id c --query 'UserPoolClient.ClientSecret'",
    # Reads that print secrets, found by a probe outside the listed cases.
    'aws cognito-idp describe-user-pool-client --user-pool-id p --client-id c',
    'aws apigateway get-api-keys --include-values',
    'aws apigateway get-api-key --api-key k --include-value',
    'aws appsync list-api-keys --api-id a',
    'aws eks get-token --cluster-name c',
    'aws redshift get-cluster-credentials --cluster-identifier c --db-user u',
    'aws lightsail get-instance-access-details --instance-name i',
    'aws codebuild batch-get-projects --names p',
    "aws lambda get-function-configuration --function-name f --query 'Environment'",
    'az webapp deployment list-publishing-profiles -g rg -n w',
    "az functionapp config appsettings list -g rg -n f --query '[].value'",
    'gcloud functions describe f --format=json',
    "gcloud run services describe s --region r --format='value(spec.template.spec.containers[0].env)'",
    'P=$(aws dynamodb delete-table --table-name x)',
    'q(){ aws s3 rb s3://b; }; q',
    'X="a b" aws dynamodb delete-table --table-name x',
    'echo "`aws dynamodb delete-table --table-name x`" >> /tmp/f',
    # Field filters that select secret values, data or environment values.
    "kubectl get cm -n kubeflow pipeline-install-config -o jsonpath='{.data}'",
    "kubectl get cm x -o go-template='{{.data}}'",
    "kubectl get deploy -n kubeflow ml-pipeline -o jsonpath='{.spec.template.spec.containers[*].env}'",
    "kubectl get pods -o jsonpath='{.items[*].spec.containers[*].env[*].value}'",
    "kubectl config view -o jsonpath='{.users[*].user.token}'",
    "aws rds describe-db-instances --query 'DBInstances[].MasterUserPassword'",
    "az storage account show -n sa --query primaryConnectionString",
    "az cosmosdb show -g rg -n db --query '{k:primaryMasterKey}'",
    "gcloud run services describe api --format='value(spec.template.spec.containers[0].env[].value)'",
    # Log reads.
    "kubectl logs -n kubeflow deploy/ml-pipeline --tail 50",
    "aws logs filter-log-events --log-group-name /aws/lambda/f --limit 5",
    "aws logs get-log-events --log-group-name g --log-stream-name s",
    "gcloud logging read 'resource.type=cloud_run_revision' --limit 5",
    "az containerapp logs show -g rg -n app",
    "az monitor log-analytics query -w ws --analytics-query 'AzureDiagnostics | take 5'",
    # Webhooks and cluster-admin credentials.
    "gh api repos/o/r/hooks",
    "gh api repos/o/r/hooks --jq '.[] | [.id, .config.url] | @tsv'",
    "gh api repos/o/r/hooks/1/deliveries/2 --jq '.request.headers'",
    "az aks get-credentials -g rg -n aks1 --admin",
    "az aks get-credentials -g rg -n aks1 --file -",
    'echo a | xargs rm',
    'ls | xargs rm -rf',
    'find . -name x | xargs cat',
    "find . -name '*.env' -exec cat {} \\;",
    'git ls-files | parallel cat',
    'grep -rl ExternalSecret k8s | xargs grep -h key',
    # A flag before the resource type (review: Blocker 1).
    'kubectl get -n prod secret db -o yaml',
    'kubectl get --namespace prod secret db -o json',
    'kubectl get -A secrets -o yaml',
    'kubectl get -n prod configmap app -o yaml',
    'kubectl get -n prod pod p -o yaml',
    'kubectl get -n prod secret/db -o yaml',
    'kubectl describe -n prod cm app',
    # Tools that run a command (review: Blocker 2).
    "awk 'BEGIN{print \"aws s3 rb s3://x --force\" | \"sh\"}'",
    "awk 'BEGIN{printf \"aws s3 rb s3://x\\n\" | \"sh\"}'",
    "awk 'BEGIN{print \"x\" |& \"sh\"}'",
    'awk -f prog.awk f',
    "awk 'BEGIN{print \"x\" > \"/tmp/drp-awk-write\"}'",
    "awk 'BEGIN{print \"x\" >> \"/tmp/drp-awk-write\"}'",
    # An awk program in double quotes, mixed quotes or $'...', and a pipe to a field.
    'awk "BEGIN{print \\"aws s3 rb s3://x\\" | \\"sh\\"}"',
    'awk "BEGIN{printf \\"x\\" |& \\"sh\\"}"',
    'awk "BEGIN{print 1 > \\"/tmp/x\\"}"',
    "awk 'BEGIN{print 1 |'\"\\\"sh\\\"}\"",
    "awk $'BEGIN{print 1 | \\x22sh\\x22}'",
    "echo sh | awk '{print \"id\" | $1}'",
    # gawk code from files or extensions, and the environment.
    'gawk -E prog.awk f',
    "gawk -i inplace '{print}' f",
    "gawk --include lib.awk 'BEGIN{}'",
    "gawk -l filefuncs 'BEGIN{}'",
    "gawk '@load \"filefuncs\"; BEGIN{}'",
    "awk 'BEGIN{for (k in ENVIRON) print k, ENVIRON[k]}'",
    "sed 's/a/b/e' f",
    "sed '1e id' f",
    'sort --compress-program=sh f',
    "git -c core.fsmonitor='aws s3 rb s3://x' status",
    "git -c diff.external='aws s3 rb s3://x' diff",
    "GIT_EXTERNAL_DIFF='aws s3 rb s3://x' git diff",
    "env GIT_EXTERNAL_DIFF='aws s3 rb s3://x' git diff",
    'git --config-env=core.pager=X log',
    'GIT_PAGER=sh git log',
    'export GIT_PAGER=sh',
    "git grep -O'sh' bucket",
    "git ls-remote --upload-pack='touch x' .",
    "LESSOPEN='|id %s' less f",
    # The self-test of Step 2.4 (review: Blocker 3).
    'drp-hook-selftest',
]


# Read and Grep calls: (exit code, tool, tool_input). They are checked as the
# cat or grep command they stand for.
TOOL_CASES = [
    (2, "Read", {"file_path": "/r/k8s/kubeflow/secrets/team-a/awscreds.yaml"}),
    (2, "Read", {"file_path": "secrets/db.yaml"}),
    (2, "Read", {"file_path": "/r/infra/prod.tfvars"}),
    (2, "Read", {"file_path": "/r/.env"}),
    (2, "Read", {"file_path": "/r/infra/terraform.tfstate"}),
    (2, "Read", {"file_path": "/home/u/.kube/config"}),
    (2, "Read", {"file_path": "/r/deploy/db-credentials.json"}),
    (0, "Read", {"file_path": "/r/.env.example"}),
    (0, "Read", {"file_path": "/r/infra/main.tf"}),
    (0, "Read", {"file_path": "/r/my dir/it's (x).md"}),
    (0, "Read", {"file_path": "/r/docs/secrets-handling.md"}),
    (0, "Grep", {"pattern": "password", "path": "/r"}),
    (0, "Grep", {"pattern": "password", "path": "/r", "output_mode": "count"}),
    (2, "Grep", {"pattern": "password|token", "path": "/r", "output_mode": "content"}),
    (2, "Grep", {"pattern": "kind|name|key", "path": "/r/k8s/secrets/a.yaml", "output_mode": "content"}),
    (2, "Grep", {"pattern": "x", "path": "/r/k8s/secrets", "output_mode": "content"}),
    (2, "Grep", {"pattern": "region", "path": "/r", "glob": "*.tfvars", "output_mode": "content"}),
    (0, "Grep", {"pattern": "region", "path": "/r", "glob": "*.tfvars"}),
    (0, "Grep", {"pattern": "$(rm -rf /)`x`", "path": "/r", "output_mode": "content"}),
    (0, "Grep", {"pattern": 'backend "s3"', "path": "/r/infra", "output_mode": "content"}),
    (0, "Grep", {"pattern": "region", "output_mode": "content"}),
    (0, "Glob", {"pattern": "**/*.tfvars"}),
]


def run(command, cwd, env):
    data = json.dumps({"tool_input": {"command": command}, "cwd": cwd})
    return subprocess.run(["sh", HOOK], input=data, capture_output=True, text=True, env=env)


def gate_tests(env):
    """The two modes: the skill hook marks the session, the gate checks subagents."""
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(env, TMPDIR=tmp)
        bad = "aws dynamodb delete-table --table-name x"

        def hook(mode, tool, command, agent=None, sid="s-1"):
            tool_input = command if isinstance(command, dict) else {"command": command}
            data = {"session_id": sid, "tool_name": tool, "tool_input": tool_input, "cwd": tmp}
            if agent:
                data["agent_id"] = agent
            e = dict(env, DRP_MODE=mode)
            return subprocess.run(["sh", HOOK], input=json.dumps(data), capture_output=True, text=True, env=e).returncode

        cases = [
            ("gate, session not marked", hook("gate", "Bash", bad, agent="a1"), 0),
            ("skill, Agent call marks the session", hook("skill", "Agent", ""), 0),
            ("gate, marked, subagent write", hook("gate", "Bash", bad, agent="a1"), 2),
            ("gate, marked, subagent read", hook("gate", "Bash", "aws dynamodb list-tables", agent="a1"), 0),
            ("gate, marked, main session", hook("gate", "Bash", bad), 0),
            ("gate, other session", hook("gate", "Bash", bad, agent="a1", sid="s-2"), 0),
            ("skill, main session write", hook("skill", "Bash", bad), 2),
            ("gate, marked, subagent reads a secret file", hook("gate", "Read", {"file_path": "/r/secrets/a.yaml"}, agent="a1"), 2),
            ("gate, marked, subagent reads code", hook("gate", "Read", {"file_path": "/r/main.tf"}, agent="a1"), 0),
            ("gate, marked, subagent greps secret words", hook("gate", "Grep", {"pattern": "password", "path": "/r", "output_mode": "content"}, agent="a1"), 2),
            ("gate, marked, main session Read", hook("gate", "Read", {"file_path": "/r/secrets/a.yaml"}), 0),
            ("skill, main session reads a secret file", hook("skill", "Read", {"file_path": "/r/.env"}), 2),
            ("subagent removes the mark", hook("gate", "Bash", f"rm -f {tmp}/drp-active/s-1", agent="a1"), 2),
            ("session id with a path", hook("skill", "Agent", "", sid="../../x"), 0),
        ]
        if not os.path.isfile(os.path.join(tmp, "drp-active", "s-1")):
            cases.append(("mark file created", 1, 0))
        if os.path.exists(os.path.join(tmp, "..", "x")):
            cases.append(("session id path ignored", 1, 0))
        for name, got, want in cases:
            if got != want:
                failures += 1
                print(f"FAIL (gate): {name}: want {want}, got {got}")
    return failures, len(cases)


def main():
    failures = 0
    with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as stubs:
        for path, text in FILES.items():
            os.makedirs(os.path.dirname(os.path.join(proj, path)) or proj, exist_ok=True)
            with open(os.path.join(proj, path), "w") as f:
                f.write(text)
        for tool in ("jq", "python3"):
            stub = os.path.join(stubs, tool)
            with open(stub, "w") as f:
                f.write("#!/bin/sh\nexit 127\n")
            os.chmod(stub, 0o755)
        envs = {
            "with jq": dict(os.environ),
            "without jq or python3": {"PATH": stubs + ":/usr/bin:/bin", "HOME": "/nonexistent"},
        }
        for label, env in envs.items():
            for want, commands in ((0, ALLOW), (2, BLOCK)):
                for command in commands:
                    result = run(command, proj, env)
                    if result.returncode != want:
                        failures += 1
                        print(f"FAIL ({label}): want {want}, got {result.returncode}: {command!r}")
                        if result.stderr:
                            print("   ", result.stderr.strip()[:200])
        for label, env in envs.items():
            for want, tool, tool_input in TOOL_CASES:
                data = json.dumps({"tool_name": tool, "tool_input": tool_input, "cwd": proj})
                result = subprocess.run(["sh", HOOK], input=data, capture_output=True, text=True, env=env)
                if result.returncode != want:
                    failures += 1
                    print(f"FAIL ({label}): want {want}, got {result.returncode}: {tool} {tool_input!r}")
        for label, env in envs.items():
            f, n = gate_tests(env)
            failures += f
            gate_total = getattr(main, "gate_total", 0) + n
            main.gate_total = gate_total
    total = 2 * (len(ALLOW) + len(BLOCK) + len(TOOL_CASES)) + main.gate_total
    print(f"{total - failures} of {total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
