# Deploying this demo's worker on AWS Lambda — runbook

Step-by-step deployment of the Celery→Temporal demo's Standalone-Activity worker
as a **Temporal Serverless Worker** on AWS Lambda. 


## Prerequisites

- Temporal Cloud with an **AWS-hosted Namespace** and **API key auth** (the
  same Cloud setup from the earlier steps). Namespace cloud provider must be AWS.
- An AWS account with permission to create/invoke Lambda functions and create
  IAM roles; `aws` CLI installed and authenticated (SSO is fine — pass
  `--profile <p>`, or `export AWS_PROFILE=<p>`).
- Python 3.13 and `pip` locally.
- The Temporal CLI, logged in to your Cloud namespace.


---

## 1. The Lambda handler (already in this repo)

`lambda_function.py` is the handler. It registers only the Standalone Activity,
passes a `WorkerDeploymentVersion` (required for Serverless Workers), and
provides a `ThreadPoolExecutor` for the synchronous activity. No Strands plugin,
no workflows.

## 2. Versioning behavior

Serverless Workers require Worker Versioning, which means every Workflow needs a versioning behavior.
See more info on versioning options [here](https://docs.temporal.io/production-deployment/worker-deployments/worker-versioning)

## 3. Build the dependency package for Lambda's Linux runtime

The `temporalio` wheel bundles a compiled Rust core, so **deps installed on
macOS won't run on Lambda's Linux x86_64 runtime** (you'll hit `invalid ELF
header` at import). Install Linux wheels explicitly.

```bash
cd serverless-lambda
rm -rf package/ function.zip
mkdir package

pip install --target ./package \
  --platform manylinux2014_x86_64 \
  --implementation cp --python-version 3.13 \
  --only-binary=:all: \
  -r requirements-lambda.txt
```

Verify the compiled binary is Linux ELF, not macOS Mach-O:

```bash
file package/temporalio/bridge/*.so
# Expect: ELF 64-bit LSB shared object, x86-64
```

For arm64/Graviton, use `--platform manylinux2014_aarch64` and add
`--architectures arm64` to `create-function` in step 5.

> If you ever pin `temporalio` to a git commit (e.g. a `uv.lock`),
> `--only-binary=:all:` fails because there's no published wheel for a git ref
> and a source build tries to compile Rust. Use the **PyPI** `temporalio` for
> Lambda packaging.

## 4. Size check (usually nothing to trim here)

This demo's only dependency is `temporalio`, so the package is well under
Lambda's 250 MB unzipped limit. no trimming is normally needed.
Confirm and do light hygiene:

```bash
du -sh package/
find package/ -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find package/ -type d -name "tests" -exec rm -rf {} + 2>/dev/null
find package/ -name "*.pyc" -delete
```

## 5. Zip the package and source

Dependencies go at the **root** of the zip (not nested under `package/`), then
add the app files:

```bash
rm -f function.zip
cd package && zip -r ../function.zip . && cd ..
zip function.zip lambda_function.py my_activity.py shared.py
```

Sanity-check the layout — files at the root, no directory prefix:

```bash
unzip -l function.zip | grep -E "lambda_function.py|temporalio/client.py"
```

## 6. Create the Lambda execution role (one-time)

The role Lambda assumes to **run** your code. Trusted principal is
`lambda.amazonaws.com`. **No Bedrock policy needed** for this demo.

```bash
aws iam create-role \
  --role-name celery-demo-serverless-worker-exec \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' \
  --profile <your-profile>

aws iam attach-role-policy \
  --role-name celery-demo-serverless-worker-exec \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
  --profile <your-profile>
```

## 7. Deploy the function

This demo's zip is small (only `temporalio`), so **direct upload works** — no S3
staging required. The default 3-second Lambda timeout is too short for the worker
to start, connect, and register the queue; set a generous deadline.

```bash
aws lambda create-function \
  --function-name celery-migration-demo-worker \
  --runtime python3.13 \
  --handler lambda_function.lambda_handler \
  --role arn:aws:iam::<ACCOUNT_ID>:role/celery-demo-serverless-worker-exec \
  --zip-file fileb://function.zip \
  --timeout 600 \
  --memory-size 256 \
  --region us-west-2 \
  --profile <your-profile> \
  --environment '{"Variables":{
    "TEMPORAL_ADDRESS":"<namespace>.<account>.tmprl.cloud:7233",
    "TEMPORAL_NAMESPACE":"<namespace>.<account>",
    "TEMPORAL_API_KEY":"<api-key>"
  }}'
```

Publish an immutable version and note the qualified ARN (`...:function:...:1`)
for step 9:

```bash
aws lambda publish-version \
  --function-name celery-migration-demo-worker \
  --description "build-1" \
  --region <AWS_REGION> --profile <your-profile>
```

Encrypt `TEMPORAL_API_KEY` (KMS) for anything beyond a throwaway demo. Iterate
later with `aws lambda update-function-code --function-name
celery-migration-demo-worker --zip-file fileb://function.zip`.

**If your zip ever exceeds 70 MB** (the direct-upload limit), stage it in S3 as
the LENNY guide does:

```bash
aws s3 mb s3://celery-demo-lambda-deploy --region us-west-2 --profile <your-profile>
aws s3 cp function.zip s3://celery-demo-lambda-deploy/function.zip \
  --region us-west-2 --profile <your-profile>
# then create-function with: --code S3Bucket=celery-demo-lambda-deploy,S3Key=function.zip
```

## 8. IAM so Temporal Cloud can invoke the Lambda

A **second, separate role** — the one Temporal Cloud assumes to call
`lambda:InvokeFunction`. Its trust policy uses an External ID to prevent
confused-deputy attacks.

```bash
curl -o temporal-cloud-serverless-worker-role.yaml \
  https://docs.temporal.io/assets/files/temporal-cloud-serverless-worker-role-fac5401b050a296d845a9aee4cd1aa5f.yaml

aws cloudformation create-stack \
  --stack-name celery-demo-temporal-role \
  --template-body file://temporal-cloud-serverless-worker-role.yaml \
  --parameters \
    ParameterKey=AssumeRoleExternalId,ParameterValue=<EXTERNAL_ID> \
    ParameterKey=LambdaFunctionARNs,ParameterValue='"arn:aws:lambda:us-west-2:<ACCOUNT_ID>:function:celery-migration-demo-worker:*"' \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2 \
  --profile <your-profile>
```

Pick any `<EXTERNAL_ID>` string and save it — you reuse it in step 9. Get the
invocation role ARN from the stack outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name celery-demo-temporal-role \
  --query 'Stacks[0].Outputs[?OutputKey==`RoleARN`].OutputValue' \
  --output text --region us-west-2 --profile <your-profile>
```

The Temporal Cloud UI's **Create Worker Deployment → Launch Stack** button does
this same step with the template pre-filled, if you prefer the console.

## 9. Register the Worker Deployment Version

`deployment-name` and `build-id` **must match** `lambda_function.py`
(`celery-migration-demo` / `build-1`).

```bash
temporal worker deployment create-version \
  --namespace <namespace> \
  --deployment-name celery-migration-demo \
  --build-id build-1 \
  --aws-lambda-function-arn <QUALIFIED_LAMBDA_ARN_FROM_STEP_7> \
  --aws-lambda-assume-role-arn <INVOCATION_ROLE_ARN_FROM_STEP_8> \
  --aws-lambda-assume-role-external-id <EXTERNAL_ID>
```

The Temporal UI (**Workers → Create Worker Deployment**) does this too and sets
the version current automatically (skip step 10). It also offers **Actions →
Validate Connection** to confirm Temporal can assume the role and invoke the
function.

## 10. Set the version as current

Required if you used the CLI — without it, tasks won't route to the version.

```bash
temporal worker deployment set-current-version \
  --namespace <namespace> \
  --deployment-name celery-migration-demo \
  --build-id build-1
```

## 11. Test

**Import / startup check** — invoke the Lambda directly and read the inline logs:

```bash
aws lambda invoke \
  --function-name celery-migration-demo-worker \
  --region us-west-2 --profile <your-profile> \
  --log-type Tail --query 'LogResult' --output text \
  response.json | base64 --decode
```

**End-to-end check** — submit the Standalone Activity from your laptop. The
activity task lands on `email-tasks` with no active pollers, Temporal invokes
the Lambda, and the worker processes it:

```bash
export TEMPORAL_ADDRESS=<namespace>.<account>.tmprl.cloud:7233
export TEMPORAL_NAMESPACE=<namespace>.<account>
export TEMPORAL_API_KEY=<api-key>

python trigger.py            # execute_activity → expect: Result: sent to user42@example.com
```

Watch the invocation in the Temporal UI (the Standalone Activity execution;
Workers → Deployments → Connection status) and in CloudWatch:

```bash
aws logs tail /aws/lambda/celery-migration-demo-worker \
  --follow --region us-west-2 --profile <your-profile>
```


---

## Troubleshooting quick reference

| Symptom | Cause | Fix |
| --- | --- | --- |
| `invalid ELF header` on `temporal_sdk_bridge.abi3.so` | macOS wheel packaged for the Linux runtime | Reinstall with `--platform manylinux2014_x86_64 --only-binary=:all:` (step 3) |
| `No module named 'lambda_function'` | Files nested under a subdir in the zip, or wrong `--handler` | Ensure files are at the zip root; handler is `lambda_function.lambda_handler` |
| `unexpected keyword argument 'default_versioning_behavior'` | Invalid `worker_config` key | Already removed from `lambda_function.py`; don't re-add it (step 2) |
| `Request must be smaller than 70167211 bytes` | Zip > 70 MB for direct upload | Deploy via S3 (step 7) |
| `Unable to locate credentials` | CLI not authenticated to a profile | `aws sso login --profile <p>`, then `export AWS_PROFILE=<p>` or pass `--profile` |
| Lambda never invoked; task sits in backlog | First invocation timed out before the worker registered the queue | Raise `--timeout` (step 7); confirm the Worker Deployment Version is **current** (step 10) |

## Files involved

| File | Role |
| --- | --- |
| `lambda_function.py` | **The Lambda handler** (`run_worker`, activity-only) |
| `my_activity.py` | Unchanged — packaged into the zip |
| `shared.py` | Unchanged — the `TASK_QUEUE` constant, packaged into the zip |
| `requirements-lambda.txt` | Minimal deps for the Linux package |
| `trigger.py` | Run locally to submit the activity (end-to-end test) |
| `../worker.py`, `../*.py` | The local demo — unchanged, kept for local dev |
