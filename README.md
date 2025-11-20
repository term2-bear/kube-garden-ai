# Kube-Garden Deployment Agent (AI 기반 배포 자동화)

이 프로젝트는 **Kube-Garden** 플랫폼을 위한 AI 배포 에이전트입니다. LangGraph를 기반으로 구축되었으며, 사용자의 자연어 요청을 해석하여 배포 계획을 수립하고, CI/CD 파이프라인을 트리거하며, Kubernetes 및 정적 사이트 배포를 자동화합니다.

## 📂 프로젝트 구조

```bash
agent_v1/
├── agent.py                 # [Core] LangGraph 에이전트 로직 (Planner -> Executor -> Verifier)
├── server.py                # [API] FastAPI 서버 및 AWS Lambda 핸들러 (/deploy 엔드포인트)
├── template.yaml            # [AWS] AWS SAM 배포 템플릿 (Lambda + API Gateway)
├── requirements.txt         # 의존성 패키지 목록
└── utils/
    ├── deployment_tools.py  # [Tools] 배포 관련 도구 (CI/CD, K8s, Static Site 등)
    ├── prompts.py           # [Prompts] LLM 프롬프트 (Planning, Verification)
    └── ...
```

## 🏗️ 아키텍처 및 워크플로우

에이전트는 **Plan(계획) -> Execute(실행) -> Verify(검증)**의 3단계 루프를 통해 작업을 수행합니다.

1.  **Planner**: 사용자의 요청(`message`)과 서비스 메타데이터(`service_id`)를 분석하여 배포 계획(JSON)을 생성합니다.
2.  **Executor**: 계획된 단계들을 순차적으로 실행합니다.
    *   **Backend**: Unit Test -> Build -> Canary Deploy (K8s)
    *   **Frontend**: Unit Test -> Static Site Deploy (Lambda)
3.  **Verifier**: 배포 후 메트릭을 분석하여 배포 성공 여부를 판단하고, 필요 시 Rollback 또는 Promotion을 수행합니다.

## 🔌 인프라 연동 가이드

이 에이전트는 AWS Serverless (Lambda) 환경에서 실행되도록 설계되었으며, 다음과 같은 외부 인프라와 연동됩니다.

### 1. AWS Lambda (Agent Runtime)
*   **배포 방식**: AWS SAM (Serverless Application Model)
*   **핸들러**: `server.handler` (Mangum 어댑터 사용)
*   **설정**: `template.yaml` 참조

### 2. Kubernetes (EKS)
*   **연동 방식**: `boto3` 및 `kubernetes` Python 클라이언트를 사용하여 EKS 클러스터 제어.
*   **권한 설정**: Lambda의 IAM Role이 EKS의 `aws-auth` ConfigMap에 등록되어야 함. (상세: `aws_setup_guide.md` 참조)

### 3. CI/CD (AWS CodeBuild)
*   **연동 방식**: `boto3`를 통해 CodeBuild 프로젝트 트리거.
*   **환경 변수**: `CODEBUILD_PROJECT_NAME` 설정 필요.

### 4. 정적 사이트 배포 (External Lambda)
*   **연동 방식**: 외부 팀이 구축한 별도의 Lambda API 호출.
*   **환경 변수**: `STATIC_SITE_DEPLOY_API_URL` (예: `https://api.example.com/deploy`)
*   **파라미터**: `github_token`, `repo_url`, `app_name` 등을 요청 시 전달.

## 🚀 실행 방법

### 1. 로컬 실행 (테스트)

```bash
# 의존성 설치
pip install -r requirements.txt

# 서버 실행
uvicorn server:app --reload --port 8000
```

**API 테스트 (cURL):**

```bash
# 백엔드 배포 (Canary)
curl -X POST "http://127.0.0.1:8000/deploy" \
     -H "Content-Type: application/json" \
     -d '{
           "service_id": "demo-api", 
           "thread_id": "local_test_1", 
           "message": "Deploy v1.2.1"
         }'

# 프론트엔드 배포 (Static Site)
curl -X POST "http://127.0.0.1:8000/deploy" \
     -H "Content-Type: application/json" \
     -d '{
           "service_id": "demo-frontend", 
           "thread_id": "local_test_2", 
           "message": "Update landing page",
           "github_token": "ghp_xxxx",
           "repo_url": "https://github.com/user/demo-frontend"
         }'
```

### 2. AWS 배포 (Production)

```bash
# 빌드
sam build

# 배포 (가이드 모드)
sam deploy --guided
```

배포 시 입력해야 할 환경 변수:
*   `OPENAI_API_KEY`: OpenAI API 키
*   `STATIC_SITE_DEPLOY_API_URL`: 정적 사이트 배포용 Lambda API 주소
*   `USE_REAL_AWS`: `true` (실제 AWS 리소스 사용 시)

## 📝 참고 문서
*   `aws_setup_guide.md`: EKS 및 IAM 권한 설정 상세 가이드
*   `aws_deployment_guide.md`: SAM 배포 상세 가이드
