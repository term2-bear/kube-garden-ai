# Kube-Garden AWS 환경 설정 가이드

Kube-Garden 배포 에이전트를 실제 AWS 환경에서 실행하기 위한 설정 가이드입니다.

## 1. 필수 인프라 구성

### 1.1 Amazon EKS 클러스터 생성
`eksctl`을 사용하여 클러스터를 생성합니다.

```bash
eksctl create cluster \
  --name kube-garden-cluster \
  --region ap-northeast-2 \
  --nodegroup-name standard-workers \
  --node-type t3.medium \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 3 \
  --managed
```

### 1.2 AWS CodeBuild 프로젝트 생성
CI 파이프라인(테스트, 빌드)을 위한 CodeBuild 프로젝트를 생성합니다.
- **Project Name**: `kube-garden-build`
- **Source**: GitHub Repository 연결
- **Environment**: Managed Image (Ubuntu, Standard, Python 3.x & Docker support)
- **Service Role**: 새 역할 생성 (S3, ECR 접근 권한 필요)

### 1.3 Amazon ECR 리포지토리 생성
컨테이너 이미지를 저장할 리포지토리를 생성합니다.
```bash
aws ecr create-repository --repository-name demo-api
```

## 2. IAM 권한 설정

Lambda 함수(`AgentFunction`)가 다른 AWS 서비스를 호출할 수 있도록 IAM 역할을 수정해야 합니다.

1. **IAM 콘솔** 접속 -> **Roles** 이동.
2. `agent-v1-stack-AgentFunction-xxxx` 역할 검색.
3. 다음 정책(Policy)을 연결(Attach)하거나 인라인 정책으로 추가합니다.

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "codebuild:StartBuild",
                "codebuild:BatchGetBuilds"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "eks:DescribeCluster",
                "eks:ListClusters"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "cloudwatch:GetMetricData",
                "cloudwatch:GetMetricStatistics",
                "cloudwatch:ListMetrics"
            ],
            "Resource": "*"
        }
    ]
}
```

## 3. EKS 접근 권한 설정 (aws-auth)

Lambda 함수가 EKS 클러스터에 접근하려면 `aws-auth` ConfigMap에 Lambda의 IAM Role을 추가해야 합니다.

1. Lambda Role ARN 확인 (예: `arn:aws:iam::123456789012:role/agent-v1-stack-AgentFunction-xxxx`)
2. `aws-auth` 수정:
```bash
kubectl edit -n kube-system configmap/aws-auth
```
3. `mapRoles` 섹션에 추가:
```yaml
- rolearn: <LAMBDA_ROLE_ARN>
  username: lambda-agent
  groups:
    - system:masters
```

## 4. 환경 변수 설정 (Lambda)

AWS Lambda 콘솔에서 다음 환경 변수를 설정하여 Mock 모드를 해제하고 실제 AWS를 사용하도록 전환할 수 있습니다. (코드 수정 필요: `utils/deployment_tools.py`에서 환경 변수 체크 로직 추가 필요)

- `USE_REAL_AWS`: `true`
- `EKS_CLUSTER_NAME`: `kube-garden-cluster`
- `CODEBUILD_PROJECT_NAME`: `kube-garden-build`
- `OPENAI_API_KEY`: `sk-...`
- `STATIC_SITE_DEPLOY_API_URL`: `https://api.example.com/deploy` (Lambda URL)

## 5. 배포 (SAM)

이전 단계에서 생성한 `template.yaml`을 사용하여 배포합니다.

```bash
sam build
sam deploy --guided
```
