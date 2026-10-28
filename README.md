# MD Decision Lab

**주니어 MD가 상품별 판매·재고를 보고 무엇을 먼저 확인할지 정하고, 그 판단을 나중에 돌아볼 수 있게 돕는 로컬 업무 도구**

의류 MD 실무 경험(시즌 물량 확보, 주간 판매율 기반 재고 조율, 프로모션 운영)에서 출발한 포트폴리오 프로젝트입니다. 자세한 문제 정의와 결과는 [사례 연구](docs/PORTFOLIO_CASE_STUDY.md)에 있습니다.

## 핵심 기능

- **오늘의 할 일**: 판단 기준일의 재고 위험(재고 0, 소진 위험, 재고 과다, 판매 감소·증가, 판매 미관측)을 우선순위대로 보여주고, 판정 이유와 다음 검토 행동을 함께 표시합니다.
- **상품 판단**: 판매 흐름, 재고 소진 예상일, 계획 입고, 판매율, 판매가·원가를 한 화면에서 봅니다.
- **조치안 비교**: 할인·추가 매입안의 매출총이익을 비교합니다. 예상 판매를 날짜별로 나눠, 입고 전에 재고가 비는 날이 있으면 30일 합계가 충분해도 "불가"로 판정합니다.
- **판단 기록**: 선택한 조치와 이유를 당시의 숫자·출처와 함께 저장합니다.
- **회고와 추정 검증**: 8/31 판정 이후 실제로 어떻게 팔렸는지 판정 유형별로 보고, 8/31까지의 정보로 만든 9월 판매 추정을 실제 판매와 비교합니다.
- **자사 파일 업로드**: 상품·판매 CSV/XLSX를 올려 같은 판단을 자기 데이터로 할 수 있습니다.

## 데이터 구조: 실제 판매 + 생성한 내부 자료

MD 판단에는 판매·재고·발주·원가가 모두 필요하지만, 공개 자료(H&M Kaggle)에는 판매만 있습니다. 그래서 데이터를 네 층으로 나누고, 화면의 모든 숫자에 출처를 표시합니다.

| 층 | 내용 | 출처 표시 |
|---|---|---|
| 수요 | 일별 판매, 작년 같은 기간 판매 | `H&M 관측` (실제 거래 기록) |
| 내부 운영 조건 | 재고 수불, 발주·리드타임, 판매가·원가, 시즌 상태 | `가상 운영 조건` (회사 내부 자료 대신 생성) |
| 판단 | 재고 위험, 조치안 비교, 매출총이익, 판매 추정 | `시뮬레이션` |
| 검증 | 판단 기준일 이후 판매 | `H&M 관측` |

판단 기준일은 **2020-08-31**로 고정합니다. 표본 선정, 재고 설정, 발주, 추정 모두 그 이후 판매를 쓰지 않으며, 9월 판매를 바꿔도 8/31까지의 결과가 같은지 테스트로 확인합니다.

## 주요 결과 (요약)

| 확인 내용 | 결과 |
|---|---|
| 9월 판매 추정 (H&M 220종) | 최근 14일 속도 유지: 합계 +35.5%, 상품별 오차율 53.1% → **작년 계절 보정: 합계 −0.4%, 오차율 43.0%** |
| 8/31 재고 과다 판정 20종 | 9/22에도 가상 재고의 93%가 남음 |
| 9월 공급 부족 | 8/31에 재고 공백을 예상한 11종과 실제 공급 부족이 난 11종이 같음 (부족 수량은 상품마다 크게 다름) |

재고·발주·원가가 가상이므로 **실제 H&M의 품절, 매출, 예측 정확도를 뜻하지 않습니다.** 한계와 시험 후 버린 방식은 [WORKSPACE_DATA.md](docs/WORKSPACE_DATA.md)에 공개했습니다.

## 실행 방법

필요한 것: Python 3.11 이상, Node.js 20 이상.

### 1. 백엔드

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API 문서: <http://127.0.0.1:8000/docs>

### 2. 프런트엔드

```powershell
cd frontend
npm install
npm run dev
```

기본 API 주소는 `http://127.0.0.1:8000`이며 `VITE_API_BASE_URL`로 바꿀 수 있습니다.

### 3. H&M 데이터 준비 (선택)

H&M 데이터는 Kaggle 대회 규칙에 따라 이 저장소에 포함하지 않습니다. [Kaggle 대회 페이지](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations)에서 규칙에 동의하고 파일을 받은 뒤, 저장소 밖에 두고 실행하세요.

```powershell
# backend/ 에서: 여성복 3개 섹션의 7/1~8/31 판매 상위 상품만 적재 (고객 ID는 저장하지 않음)
python scripts/import_hm.py --articles "C:\경로\articles.csv.zip" --transactions "C:\경로\transactions_train.csv.zip" --images "C:\경로\images.zip"

# 저장소 최상위에서: 가상 운영 조건 CSV 생성과 검증
python sample_data/hm_operating_case/generate_hm_operating_case.py
python sample_data/hm_operating_case/verify_hm_operating_case.py
```

스크립트는 실행 전에 원본 파일의 크기와 SHA-256을 [기록된 값](docs/DATA_SOURCES.md)과 비교합니다. 앱의 H&M 작업공간에서 **운영 시뮬레이션 자료 연결**을 한 번 누르면 검증 후 저장됩니다. 데이터를 이미 만든 상태에서 다시 만들려면 `import_hm.py`에 `--replace`를 붙입니다.

### 4. 자사 파일로 쓰기

`오늘의 할 일`의 **자사 상품·판매 파일 연결**에서 두 파일을 올립니다. 열 형식은 `sample_data/company_products_template.csv`, `sample_data/company_sales_template.csv`를 참고하세요. 입고 예정일·기초재고 등 선택 열은 [WORKSPACE_DATA.md](docs/WORKSPACE_DATA.md)에 있습니다. 고객명·연락처 같은 개인정보 열은 지우고 올리세요.

### 테스트

```powershell
cd backend
python -m unittest discover -s tests
```

H&M CSV가 없으면 H&M 시뮬레이션 테스트는 건너뜁니다.

## 폴더 안내

| 경로 | 내용 |
|---|---|
| `backend/app/api/work_routes.py` | 작업공간, 자사 업로드, 조치안 비교, 판단 기록 |
| `backend/app/api/hm_sim_routes.py` | H&M 운영 시뮬레이션, 회고, 9월 추정 검증 |
| `backend/app/services/` | 재고 위험 규칙, 날짜별 재고 확인, 판매율, 판매 추정 |
| `backend/scripts/import_hm.py` | H&M 원본에서 표본 적재 |
| `frontend/src/WorkPage.tsx`, `HmSimulation.tsx` | 화면 |
| `sample_data/hm_operating_case/` | 가상 운영 조건 생성·검증 스크립트와 [데이터 QA](sample_data/hm_operating_case/DATA_QA.md) |
| `sample_data/fashion_fw_case/` | 종료한 F/W 합성 사례. 회사 내부 자료(재고 수불, 시즌 상태, 작년 비교) 설계 참고용 |

## 문서

- [사례 연구](docs/PORTFOLIO_CASE_STUDY.md) — 문제, 데이터 설계, 8/31 판단, 9월 회고, 한계, 보완점, 역할 구분
- [작업공간 데이터와 판단 기준](docs/WORKSPACE_DATA.md) — 계산식, 출처 구분, 추정 방법과 결과, 한계
- [데이터 출처와 보관](docs/DATA_SOURCES.md) — 원본 파일 해시, 저장소에 두지 않는 파일, 보관 원칙
- [H&M 운영 사례 데이터 QA](sample_data/hm_operating_case/DATA_QA.md) — 가상 운영 조건 생성 규칙과 전수 검증
- [내부 자료 설계 참고](docs/FASHION_DATA_DESIGN.md) — 종료한 F/W 합성 사례의 재고 수불·시즌 기획 설계
- `docs/BUILD_LOG.md`, `ARCHITECTURE.md`, `PRODUCT_SPEC.md`, `DECISION_RULES.md`, `CSV_IMPORT.md` — 초기 버전의 기록

## 한계

- 재고·발주·원가·시즌 상태는 가상입니다. 실제 회사 자료로 바꾸는 방법은 사례 연구의 "보완점"에 정리했습니다.
- H&M 표본은 여름 판매 상위 상품이라 전체를 대표하지 않고, 9월에 처음 팔린 신상은 다루지 못합니다.
- 조치 전후 비교는 대조군이 없어 인과 효과를 증명하지 않습니다.
- 사이즈·컬러별 재고, 구매 예산(OTB), 반품, 여러 사용자 동시 사용은 지원하지 않습니다.

## 역할과 도구

기획자는 MD 실무 경험을 바탕으로 문제, 판단 기준, 데이터 구분, 검수 기준을 정하고 결과를 검토했습니다. 구현·테스트·검증 스크립트 작성에는 AI 코딩 도구(Codex, Claude Code)를 사용했습니다. 이 도구가 실제 매출을 높였다고 주장하지 않습니다.
