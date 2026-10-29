# 테스트 따라 하기 (Windows, 개발 경험 없이)

준비에 30~40분, 테스트에 20분 정도 걸립니다. 처음 한 번만 준비하면 다음부터는 **3단계(실행)**부터 하면 됩니다.

## 1단계. 프로그램 설치 (처음 한 번)

1. **Python**: <https://www.python.org/downloads/> 에서 받아 설치합니다. 설치 첫 화면 아래쪽의 **"Add python.exe to PATH"를 꼭 체크**하세요.
2. **Node.js**: <https://nodejs.org/> 에서 **LTS** 버전을 받아 기본 설정으로 설치합니다.
3. 설치가 끝나면 PC를 한 번 재시작합니다.
4. **프로젝트 받기**: <https://github.com/jeongminimi/MD_Decision_Lab> → 초록색 **Code** 버튼 → **Download ZIP** → 받은 파일을 `C:\`에 압축 해제합니다. `C:\MD_Decision_Lab-main` 폴더가 생깁니다.

## 2단계. H&M 데이터 준비 (처음 한 번)

H&M 데이터는 Kaggle 대회 규칙상 이 저장소에 들어 있지 않아 직접 받아야 합니다.

1. <https://www.kaggle.com> 에 가입하고 로그인합니다.
2. <https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data> 에서 대회 규칙에 동의합니다.
3. `articles.csv`, `transactions_train.csv`, `images` 세 가지를 받아 `C:\hm-data` 폴더에 둡니다. 파일 이름은 `articles.csv.zip`, `transactions_train.csv.zip`, `images.zip`이어야 합니다.
   - `images`는 약 30GB라 오래 걸립니다. 상품 사진 없이 테스트하려면 받지 않아도 되고, 아래 명령에서 `--images "C:\hm-data\images.zip"` 부분만 지우면 됩니다.
4. **시작 메뉴 → "PowerShell"**을 열고, 아래 명령을 **한 줄씩** 복사해 붙여넣고 Enter를 누릅니다.

```powershell
cd C:\MD_Decision_Lab-main\backend
python -m pip install -r requirements.txt
python scripts/import_hm.py --articles "C:\hm-data\articles.csv.zip" --transactions "C:\hm-data\transactions_train.csv.zip" --images "C:\hm-data\images.zip"
cd ..
python sample_data/hm_operating_case/generate_hm_operating_case.py
python sample_data/hm_operating_case/verify_hm_operating_case.py
cd frontend
npm.cmd install
```

- `import_hm.py`는 거래 3천만 줄을 읽어 **5~10분** 걸립니다. 멈춘 것처럼 보여도 기다려 주세요. 끝나면 `완료: ... 상품 286종`이 나옵니다.
- 검증 결과에 **`실패 0건`**이 나오면 데이터 준비가 끝난 것입니다.
- `npm.cmd install`에서 노란색 `npm warn` 문구가 나와도 괜찮습니다.

## 3단계. 실행 (테스트할 때마다)

PowerShell 창을 **두 개** 열고, 테스트하는 동안 둘 다 닫지 않습니다.

**창 1 — 백엔드**
```powershell
cd C:\MD_Decision_Lab-main\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
`Application startup complete`가 보이면 정상입니다.

**창 2 — 화면**
```powershell
cd C:\MD_Decision_Lab-main\frontend
npm.cmd run dev
```
`Local: http://localhost:5173/`이 보이면 브라우저(크롬 권장)에서 **<http://localhost:5173>** 을 엽니다.

처음 열면 **"운영 시뮬레이션 자료 연결"** 버튼을 한 번 누릅니다. 이후에는 누르지 않아도 됩니다.

## 4단계. 테스트 과제 (약 20분)

각 과제를 하면서 **멈칫했던 숫자·단어·버튼을 메모**해 주세요. 그 메모가 가장 중요한 결과입니다.

**과제 1. 오늘 먼저 볼 상품 고르기**
- `오늘의 할 일`의 "기준일에 확인할 상품"에서 위쪽 3개를 보고, 각각 왜 먼저 봐야 하는지 이유 문장을 읽습니다.
- 확인할 점: 이유를 읽고 바로 이해됐나요? "재고 없음", "소진 위험"의 뜻이 분명했나요?

**과제 2. 할인·추가 매입 비교하기**
- 왼쪽 메뉴 `전체 상품`에서 "재고 과다" 상품 하나를 엽니다.
- 아래 **두 조치안 비교**에서 할인율과 "B안 예상 30일 판매"를 바꾸고 **숫자로 비교**를 누릅니다.
- 예상 판매를 아주 크게(예: 99999) 넣어 빨간 **"재고 공백"** 안내가 나오는지도 봅니다.
- 확인할 점: 재고 공백이 왜 생기는지, 매출총이익 숫자가 어떻게 나왔는지 이해됐나요?

**과제 3. 판단 기록하고 돌아보기**
- 과제 2의 상품에서 "가능"으로 나오는 수량으로 비교한 뒤, 판단 이유를 쓰고 **판단 기록 저장**을 누릅니다. 재고 공백이 있는 안은 저장 버튼이 꺼져 있습니다.
- 왼쪽 메뉴 `내 결정 기록`에서 저장한 기록과 그 아래 **"회고"** 줄(9월 실제 판매)을 봅니다.
- `다음 시즌 기획`에서 **9월 판매 추정과 실제**, **8/31 판단 회고** 표를 봅니다.
- 확인할 점: 판단을 돌아보는 데 도움이 됐나요? 어려운 표는 무엇이었나요?

**알아둘 점**
- 판매 수량만 H&M 실제 기록입니다. 재고·발주·가격·원가는 회사 내부 자료를 대신한 **가상 값**입니다.
- 화면을 캡처해 다른 사람과 나눌 때는 오른쪽 위 **사진 표시/사진 숨김** 버튼으로 사진을 숨기세요. 상품 사진은 Kaggle 자료입니다.

## 5단계. 끝내기

PowerShell 창 두 개에서 각각 `Ctrl + C`를 누르거나 창을 닫습니다.

## 막힐 때

| 증상 | 해결 |
|---|---|
| `python`을 찾을 수 없다고 나옴 | Python을 다시 설치하면서 "Add python.exe to PATH"를 체크하고 PC를 재시작합니다 |
| `npm` 실행 시 "스크립트를 실행할 수 없으므로…" 오류 | 안내대로 `npm` 대신 `npm.cmd`를 씁니다 |
| `WinError 10013` 또는 포트가 사용 중이라는 오류 | 이미 켜진 서버가 있습니다. 열린 PowerShell 창을 모두 닫고 3단계부터 다시 합니다 |
| `No module named app` | `cd C:\MD_Decision_Lab-main\backend`를 먼저 실행했는지 확인합니다 |
| 화면은 열리는데 내용이 비어 있거나 오류 문구가 나옴 | 창 1(백엔드)이 켜져 있는지 확인하고 브라우저를 새로고침합니다 |
| "운영 시뮬레이션 자료 연결"이 실패함 | 2단계의 마지막 검증 명령을 다시 실행해 `실패 0건`인지 확인합니다 |
| `import_hm.py`에서 "크기가 기록과 다릅니다" 경고 | 다른 시점에 받은 파일입니다. 실행은 되지만 숫자가 문서와 조금 다를 수 있습니다 |

## H&M 데이터 없이 잠깐 보기

`오늘의 할 일` → **자사 상품·판매 파일 연결**에서 `sample_data/company_products_template.csv`와 `sample_data/company_sales_template.csv`를 올리고 재고 기준일을 `2026-10-28`로 넣으면 업로드 기능을 볼 수 있습니다. 다만 예시 판매가 이틀치뿐이라 판정은 "판매 자료 확인"으로만 나옵니다.
