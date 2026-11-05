# infra: 도원결의 AWS 인프라 (Terraform)

ARCHITECTURE 2절 `infra/`·`.github/workflows/` 행과 5절 진입 경로·과부하 방지·운영 기준안·접속 로그, PRIVACY 제3조·제5조·제7조·제10조·제11조를 구현한다. 계정 ID는 `infra/terraform.tfvars`(gitignore)에, 프로필 `itbm`, 리전 ap-northeast-2. CloudFront용 인증서와 WAF만 us-east-1에 만든다.

> 상태(2026-11-05): 코드 작성과 `terraform fmt`·`init -backend=false`·`validate`, state 없는 `plan`까지 했다. `apply`는 실행하지 않았다. 실제 AWS에서 동작하는지는 확인하지 않았다(아래 "확인하지 못한 것").

## 구성

```
브라우저 ─HTTPS─> CloudFront (dowonpact.com, www → 301 apex, WAF, PriceClass_200)
                   ├─ 기본 동작 → S3 (비공개, OAC) SPA. CloudFront Function이 확장자 없는 경로를 /index.html로 바꾼다
                   └─ /api/* → origin.dowonpact.com (ALB, HTTPS, 캐시 없음, Host 외 헤더·쿠키·쿼리 전달, X-Origin-Verify 헤더 추가)
ALB (보안 그룹: CloudFront origin-facing 접두사 목록 443만, 리스너: 헤더 일치 시에만 전달, 나머지 403)
 └─ ECS Fargate ARM64 0.5 vCPU/1 GB × 2, 공개 서브넷·공인 IP(NAT 없음), 보안 그룹: ALB에서 8000만
     └─ RDS PostgreSQL 16 db.t4g.micro, 단일 AZ, gp3 20 GB, 암호화, 백업 7일, 비공개 서브넷, ECS 보안 그룹에서만
```

| 파일 | 내용 |
|---|---|
| `versions.tf` | Terraform ≥ 1.9, AWS provider `~> 5.80`(5.x 고정), random. 로컬 backend, S3 backend는 주석 |
| `providers.tf` | 서울 기본 provider, `aws.us_east_1` 별칭. 공통 태그 `Project=dowonpact`, `Owner=ItBM`, `allowed_account_ids` |
| `variables.tf`, `locals.tf` | 환경별 값과 기본값. 컨테이너 환경 변수 이름은 `locals.tf`의 `app_env_plain`·`app_env_secrets` 한 곳에 있다 |
| `network.tf` | 전용 VPC, 공개·비공개 서브넷 각 2개, IGW, 보안 그룹 3개 |
| `dns.tf` | 기존 호스팅 영역 `data` 조회, ACM 인증서 2개(us-east-1: apex+www, 서울: origin)와 DNS 검증, apex·www·origin 레코드 |
| `alb.tf` | ALB, 대상 그룹(`/api/health`), HTTPS 리스너(기본 403), 비밀 헤더 규칙 |
| `ecs.tf` | 클러스터, 로그 그룹(30일), 실행·태스크 역할, 태스크 정의, 서비스(롤링, 회로 차단기 롤백) |
| `ecr.tf` | ECR(태그 불변, 푸시 시 기본 스캔, 최근 10개 유지) |
| `rds.tf` | RDS와 서브넷 그룹 |
| `secrets.tf` | 비밀 4개(이름만), DB 비밀번호 `random_password`, `dowonpact/db` 값(접속 URL) |
| `cloudfront.tf` | SPA 버킷, OAC, 라우터 함수, 배포 |
| `waf.tf` | CLOUDFRONT 범위 web ACL, IP별 rate rule 4개, 선택적 공통 규칙 세트(Count) |
| `github_oidc.tf` | GitHub OIDC 공급자, main 전용 배포 역할과 최소 권한 정책 |
| `budget.tf` | 주석만. 기존 예산을 Terraform으로 관리하지 않는 이유 |
| `outputs.tf` | GitHub 저장소 변수에 넣을 값 |

### 설계 선택과 이유

- **SPA 대체 경로**: 브리프의 "403/404 → /index.html, 200"은 CloudFront `custom_error_response`가 아닌 viewer-request 함수로 구현했다. `custom_error_response`는 배포 전체에 적용되어 `/api/*`의 실제 404·403 JSON까지 index.html 200으로 바꾸기 때문이다. 함수는 마지막 경로 조각에 `.`이 없으면 `/index.html`로 바꾼다. 존재하지 않는 정적 파일(`/x.js`)은 S3의 403이 그대로 간다.
- **ALB 원본 도메인**: CloudFront는 원본 인증서가 원본 도메인과 맞아야 하므로 ALB에 `origin.dowonpact.com` 별칭과 서울 ACM 인증서를 둔다. 그래서 Host 헤더는 전달하지 않는다(관리형 `AllViewerExceptHostHeader`). 그 밖의 헤더·쿠키·쿼리는 모두 전달한다. 서버가 원래 Host가 필요하면 `CloudFront-Forwarded-Proto`나 `PUBLIC_BASE_URL`을 쓴다.
- **DB 비밀번호**: RDS 관리형 비밀번호 대신 `random_password`를 골랐다. 앱은 `DATABASE_URL` 하나를 받는데, RDS 관리형 비밀은 `{username,password}` JSON이고 기본 7일마다 교체되어 URL 비밀이 낡는다. 대가로 비밀번호가 Terraform state에 평문으로 들어간다. state를 커밋하지 않고(`.gitignore`), S3 backend로 옮길 때는 암호화 버킷을 쓴다. `dowonpact/db` 값은 `postgresql://...?sslmode=require`이다(PostgreSQL 16 기본 파라미터 그룹은 SSL을 강제한다).
- **비밀 헤더 순환 의존**: CloudFront 원본 헤더와 ALB 규칙이 `data "aws_secretsmanager_secret_version"`으로 `dowonpact/origin-verify` 값을 plan 시점에 읽는다. 비밀에 값이 없으면 plan이 실패하므로 처음에는 비밀만 `-target`으로 만들고 값을 넣은 뒤 전체 apply한다(부트스트랩 2~3단계). 값을 바꾸면 apply 한 번에 CloudFront와 ALB가 함께 바뀌지만, CloudFront 전파(수 분) 동안 `/api/*`가 403일 수 있다. 값은 state에도 남는다.
- **태스크 정의 소유**: Terraform이 기본 리비전(크기·환경 변수·비밀)을 만들고, CI는 최신 리비전을 복사해 이미지만 바꾼 새 리비전을 등록한다. 서비스는 `ignore_changes = [task_definition]`이다. Terraform에서 환경 변수를 바꾸면 다음 배포 때 반영된다.
- **접속 기록**: CloudFront 표준 로그, WAF 로그, WAF 샘플 요청은 끈다. 모두 User-Agent를 담는데 PRIVACY 제11조는 User-Agent를 저장하지 않는다고 밝힌다. 접속 기록(IP·시각·경로·상태)은 앱이 표준 출력으로 남기고 로그 그룹 `/ecs/dowonpact-app`이 30일 보관한다. WAF는 CloudWatch 지표만 남긴다.
- **WAF**: 차단하면 429와 `{"error":"rate_limited",...}` JSON을 돌려준다(화면이 "잠시 뒤 다시 시도" 안내에 쓴다). 생성 경로는 정규식 `^/api/rooms/[^/]+/(generate|retry|regenerate)$`로 잡는다(SPEC 6절 경로 기준). "나머지 POST 5분 300회" 규칙은 방 생성·생성 요청도 함께 센다. 더 엄격한 규칙이 먼저 걸리므로 결과는 같다. `/api/*` 전체 규칙은 `waf_api_limit_block=false`(Count)로 시작한다.
- **비밀 삭제 대기**: `recovery_window_in_days = 7`. 2027-01-05에 destroy하면 2027-01-12까지 삭제가 끝난다.
- **예산**: 이미 계정에 `dowon-total-20261109-20270112`(COST, USD 300, CUSTOM 기간 2026-11-09 00:00 ~ 2027-01-12 23:59:59 KST, 실제 80%·100% 초과 시 teamitbm@gmail.com 메일)이 있다(2026-11-05 읽기 전용 조회). 고정한 AWS provider 5.x(최신 5.100.0)는 `time_unit = "CUSTOM"`을 받지 않아(`terraform validate`가 거부) Terraform으로 같은 모양을 표현할 수 없다. 그래서 기존 예산을 그대로 두고 Terraform으로 만들지 않는다.

## 사전 준비

- Terraform 1.9 이상(`brew install hashicorp/tap/terraform`), AWS CLI, 프로필 `itbm`(`aws --profile itbm sts get-caller-identity`가 팀 계정 ID를 반환).
- 프로필 `itbm`은 `aws login` 세션(`login_session`)이라 AWS provider 5.x가 직접 읽지 못한다(2026-11-05 plan에서 "No valid credential sources found"). `~/.aws/config`에 아래 프로필을 추가하고 `-var aws_profile=itbm-tf`로 실행한다. 비밀 값은 파일에 남지 않는다.
  ```
  [profile itbm-tf]
  region = ap-northeast-2
  credential_process = aws configure export-credentials --profile itbm --format process
  ```
- `infra/.terraform.lock.hcl`은 darwin_arm64·linux_amd64·linux_arm64 해시를 담고 있으므로 커밋한다.
- 계정 ID와 호스팅 영역 ID는 저장소에 두지 않는다. `infra/terraform.tfvars.example`을 `infra/terraform.tfvars`로 복사해 값을 채운다(gitignore. 2026-11-05 팀 결정).

## 부트스트랩 순서 (사람이 한다)

1. `cd infra && terraform init`
2. 비밀 두 개만 먼저 만든다. `origin-verify`와 `db`는 Terraform이 값까지 쓴다(2026-11-05 팀 결정).
   ```
   terraform apply \
     -target=aws_secretsmanager_secret.openai \
     -target=aws_secretsmanager_secret.vapid
   ```
3. 값을 넣는다(콘솔 또는 CLI. 값을 셸 기록·저장소에 남기지 않는다).
   - `dowonpact/openai-api-key`: OpenAI API 키 문자열.
   - `dowonpact/vapid`: `{"public_key": "...", "private_key": "...", "subject": "mailto:teamitbm@gmail.com"}`. 키 형식(base64url 원시 키인지 PEM인지)은 서버 구현(`pywebpush`)에 맞춘다.
   - `dowonpact/db`와 `dowonpact/origin-verify`는 넣지 않는다. 4단계에서 Terraform이 쓴다.
4. 첫 전체 apply. ECR에 이미지가 아직 없으므로 태스크 수 0으로 한다.
   ```
   terraform plan -var app_desired_count=0 -out tfplan
   terraform apply tfplan
   ```
   ACM DNS 검증과 CloudFront 배포 생성에 수십 분 걸릴 수 있다. 도메인은 이미 Route 53 등록·호스팅 영역이 있으므로 별도 NS 작업은 없다.
5. GitHub 저장소 `Team-ItBM/deliverables` → Settings → Secrets and variables → Actions → **Variables**에 `terraform output` 값을 넣는다. AWS 키는 넣지 않는다.

   | 변수 | output |
   |---|---|
   | `AWS_DEPLOY_ROLE_ARN` | `github_deploy_role_arn` |
   | `ECR_REPOSITORY` | `ecr_repository` |
   | `ECS_CLUSTER` | `ecs_cluster` |
   | `ECS_SERVICE` | `ecs_service` |
   | `ECS_TASK_FAMILY` | `ecs_task_family` |
   | `ECS_CONTAINER_NAME` | `ecs_container_name` |
   | `SPA_BUCKET` | `spa_bucket` |
   | `CLOUDFRONT_DISTRIBUTION_ID` | `cloudfront_distribution_id` |
6. main에 푸시하거나 Actions에서 `deploy`를 수동 실행한다. 이미지 푸시 → 새 리비전 등록 → 스키마 초기화 태스크(`python -m travel.server.db --init`) → 서비스 갱신 → SPA 동기화 → 무효화 순이다. 태스크 수가 0이어도 스키마 초기화는 돈다.
7. `terraform apply`(기본 `app_desired_count=2`). 서비스는 6단계에서 CI가 등록한 리비전을 계속 쓴다.
8. 확인: `https://dowonpact.com/api/health`가 200이어야 한다. `https://origin.dowonpact.com/api/health`를 직접 호출하면 보안 그룹이 CloudFront 외 주소를 막으므로 연결 시간 초과가 정상이다(헤더 없이 CloudFront 주소에서 오면 403). ALB 헤더 조건 값은 128자 이하여야 하므로 `openssl rand -hex 32`(64자)를 권한다.

### State backend (선택)

로컬 state는 한 사람의 노트북에만 있다. 팀이 apply를 나눠 하려면 S3로 옮긴다.

1. state 버킷을 콘솔이나 CLI로 따로 만든다(이 구성 밖. 버전 관리·SSE·퍼블릭 차단). 이 구성이 자기 state 버킷을 만들면 destroy 때 함께 지워진다.
2. `versions.tf`의 `backend "s3"` 주석을 풀고 `terraform init -migrate-state`.
3. 정리 단계에서 state 버킷을 마지막에 수동으로 지운다.

## 비용 메모

ARCHITECTURE 5절 운영 기준안의 추정(월 약 $99, 2026-11-09~2027-01-12 약 $208, 도메인 제외)과 같은 구성 요소(Fargate ARM 0.5 vCPU/1 GB × 2, ALB, RDS db.t4g.micro 단일 AZ gp3 20 GB, CloudFront PriceClass_200, WAF, Secrets Manager, CloudWatch Logs 30일)를 쓴다. 추정의 항목별 내역을 저장소에서 찾지 못해 이 구성으로 다시 계산하지 않았다. 추정에 들어갔는지 확인할 항목:

- 공인 IPv4: ALB(AZ당 1개)와 태스크마다 1개. NAT 게이트웨이를 두지 않는 대가다.
- WAF: web ACL 1개와 규칙 4개(공통 규칙 세트를 켜면 1개 더)의 월 요금, 요청 수 요금.
- Secrets Manager 비밀 4개, ACM 공인 인증서(무료), Route 53 호스팅 영역.
- 배포 중 태스크가 잠시 4개(최대 200%)가 된다.
- 꺼 둔 것: Container Insights, Performance Insights, Multi-AZ, NAT, CloudFront·WAF 로그.

## 정리 (서비스 종료 2027-01-05, 기한 2027-01-12)

1. `terraform apply -var db_deletion_protection=false`
2. 접속기록 버킷을 Terraform 관리에서 뗀다(버킷은 남긴다. 아래 "관리자 접속기록" 참조). `terraform state rm aws_s3_bucket.audit aws_s3_bucket_public_access_block.audit aws_s3_bucket_ownership_controls.audit aws_s3_bucket_server_side_encryption_configuration.audit aws_s3_bucket_versioning.audit aws_s3_bucket_lifecycle_configuration.audit aws_s3_bucket_policy.audit`. `prevent_destroy`가 있어 state에 두고 destroy하면 실패한다.
3. `terraform destroy`. trail(`aws_cloudtrail.audit`), RDS(최종 스냅샷 없음, `db_skip_final_snapshot=true`가 기본), ECS, CloudFront 등이 지워진다. PRIVACY 제7조 3항대로 종료 후 7일 안에 백업까지 모두 사라진다(자동 백업은 인스턴스와 함께 지워진다).
4. ECR은 `force_delete=false`라 이미지가 있으면 destroy가 실패한다. 콘솔에서 이미지를 먼저 지우거나 `aws ecr batch-delete-image`로 지운다.
5. 비밀은 7일 뒤 삭제된다. 로그 그룹은 destroy와 함께 지워진다.
6. 수동으로 만든 예산, (만들었다면) state 버킷을 지운다.
7. **관리자 접속기록 버킷은 지우지 않는다.** ARCHITECTURE 8절·PRIVACY 제10조 3항의 1년 보관 대상이다. 2단계에서 state에서 뗐으므로 destroy에 영향이 없다. 버킷 정책(HTTPS만 허용, CloudTrail 쓰기)과 수명 주기는 그대로 둔다. 버킷 유지 비용은 월 $1 미만이다.

## 관리자 접속기록 (`infra/audit.tf`, 2026-11-05 결정)

- 기록 범위: CloudTrail 관리 이벤트(모든 리전, 읽기·쓰기, 로그 파일 검증 켬)와 앱의 `delete-room` 기록(`admin-audit/` 접두사, 이름·메모 없음). 관리자는 DB에 직접 접속하지 않는다는 전제다. 필요해지면 별도 기록 방안을 정한다.
- 저장: 버킷 `<project>-audit-<계정 ID>`(이름은 `audit_bucket_name`으로 바꿀 수 있다). 공개 차단, SSE-S3, 버전 관리, HTTPS 요청만 허용. 수명 주기는 현재·이전 버전 모두 `audit_retention_days`(기본 400일) 뒤 삭제, 만료된 삭제 마커와 미완성 업로드 정리. `prevent_destroy`로 보호한다.
- 비용: 관리 이벤트 첫 사본은 무료다. S3 저장 수 MB와 전송 요청으로 월 $1 미만으로 본다(사용량은 가정).
- 앱 기록 실패: `delete-room`은 S3 저장이 실패해도 삭제를 되돌리지 않는다. 결과 JSON에 `audit_stored: false`와 이유를 넣고 종료 코드 3을 내며 표준 출력에 남긴다. 그 기록은 수동으로 보관한다.
- 정리 뒤 버킷 삭제: 마지막 기록은 늦어도 2027-01-12(정리 완료일)에 쓰이므로, 수명 주기가 모든 객체와 이전 버전을 지운 2028-02-16 이후에 담당자(전민규, ARCHITECTURE 5절 정리 담당)가 버킷이 비었는지 확인하고 콘솔에서 지운다. 비어 있지 않으면 400일이 지나지 않은 기록이 있다는 뜻이므로 지우지 않는다.

## 확인하지 못한 것

- 2026-11-05에 첫 apply를 했다(70개 생성, 서비스 위임 기록 §2-6). 그 전 읽기 전용 plan은 "68 to add, 0 to change, 0 to destroy"였다. 읽기 데이터 소스(호스팅 영역, CloudFront 접두사 목록, 관리형 캐시·원본 요청·응답 헤더 정책)는 이때 조회됐다. 비밀 값 조회는 apply 시점으로 미뤄졌으므로 부트스트랩 2~3단계 없이 전체 apply하면 실패한다. IAM 정책, WAF 규칙 본문, CloudFront Function 코드가 AWS API에서 받아들여지는지는 apply 전까지 모른다.
- SCP: 기억 기록상 SCP는 서울만 허용한다. 2026-11-05에 us-east-1에서 `acm list-certificates`, `wafv2 list-web-acls --scope CLOUDFRONT` 읽기는 성공했지만, 생성 작업이 허용되는지는 확인하지 않았다. 막히면 SCP 예외(ACM·WAFv2의 us-east-1)가 필요하다. 우회하지 않는다.
- 서버 쪽 계약: `/api/health`, `python -m travel.server.db --init`, 환경 변수 이름은 아직 서버 코드에 없다. `requirements.txt`에 `uvicorn`이 아직 없어 현재 이미지의 CMD는 실행되지 않는다.
- ARM64 이미지를 GitHub의 x86 러너에서 QEMU로 빌드하는 시간, 배포 워크플로 전체, OIDC 신뢰 조건은 실행해 보지 않았다.
- CloudFront가 국외 엣지를 거치는 문제는 PRIVACY 제6조에 이미 안내되어 있다. 이 구성이 바꾸지 않는다.
