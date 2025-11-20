# AWS Serverless 배포 가이드 (AWS SAM)

이 가이드는 FastAPI 에이전트 서버를 AWS Lambda에 배포하는 방법을 설명합니다. AWS SAM(Serverless Application Model)을 사용합니다.

## 1. 사전 준비 사항 (Prerequisites)

배포를 위해 다음 도구들이 설치되어 있어야 합니다.

1.  **AWS CLI**: [설치 가이드](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
    *   설치 후 `aws configure`를 실행하여 자격 증명(Access Key, Secret Key)을 설정하세요.
2.  **AWS SAM CLI**: [설치 가이드](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
3.  **Docker** (선택 사항): 로컬에서 Lambda 함수를 테스트하려면 필요합니다.

## 2. 프로젝트 설정 확인

이미 프로젝트 루트에 `template.yaml` 파일을 생성해 두었습니다. 이 파일은 AWS 리소스(Lambda, API Gateway)를 정의합니다.

*   **Handler**: `server.handler` (Mangum 핸들러)
*   **Runtime**: Python 3.11
*   **Timeout**: 60초 (에이전트 응답 시간을 고려하여 넉넉하게 설정)

## 3. 배포하기 (Deployment)

터미널에서 프로젝트 루트 경로로 이동한 후 다음 명령어를 순서대로 실행하세요.

### 1단계: 빌드
필요한 패키지를 설치하고 배포 아티팩트를 준비합니다.
```bash
sam build
```

### 2단계: 배포
AWS에 리소스를 생성하고 코드를 업로드합니다. `--guided` 옵션을 사용하면 대화형으로 설정을 진행할 수 있습니다.
```bash
sam deploy --guided
```

**설정 가이드:**
*   **Stack Name**: `agent-v1-stack` (원하는 이름 입력)
*   **AWS Region**: `ap-northeast-2` (서울) 또는 원하는 리전
*   **Confirm changes before deploy**: `y`
*   **Allow SAM CLI IAM role creation**: `y`
*   **Disable rollback**: `n`
*   **AgentFunction has no authentication...**: `y` (API Gateway 인증 없이 오픈할 경우. 보안이 필요하면 추후 설정)
*   **Save arguments to configuration file**: `y`
*   **SAM configuration file**: `samconfig.toml` (기본값)
*   **SAM configuration environment**: `default` (기본값)

배포가 완료되면 터미널 출력의 `Outputs` 섹션에서 **API Gateway Endpoint URL**을 확인할 수 있습니다.
예: `https://xxxxxxxxxx.execute-api.ap-northeast-2.amazonaws.com/Prod/`

## 4. 환경 변수 설정

에이전트 실행을 위해 API Key들이 필요합니다. `template.yaml`에는 빈 값으로 설정되어 있으므로, AWS 콘솔에서 설정하는 것이 안전합니다.

1.  [AWS Lambda 콘솔](https://console.aws.amazon.com/lambda/) 접속
2.  생성된 함수(`agent-v1-stack-AgentFunction-xxxx`) 클릭
3.  **Configuration** (구성) -> **Environment variables** (환경 변수) 탭 클릭
4.  **Edit** (편집)을 눌러 다음 변수들을 추가/수정합니다.
    *   `OPENAI_API_KEY`

## 5. 테스트

배포된 URL을 사용하여 테스트합니다.

```bash
# 예시
curl -X POST "https://<YOUR-API-ID>.execute-api.<REGION>.amazonaws.com/Prod/chat" \
     -H "Content-Type: application/json" \
     -d '{"message": "안녕", "thread_id": "prod_test_1"}'
```

## 참고 사항

*   **State Management**: 현재 `InMemorySaver`를 사용하고 있어, Lambda 컨테이너가 재사용되지 않으면 대화 기억이 사라질 수 있습니다. 프로덕션 환경에서는 **LangGraph Checkpointer**를 Redis나 DynamoDB로 교체하는 것을 권장합니다.
*   **비용**: AWS Lambda와 API Gateway는 사용량 기반 과금입니다. 프리 티어 범위를 확인하세요.
