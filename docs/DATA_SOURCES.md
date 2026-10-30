# 데이터 출처와 보관

## 원본

H&M Personalized Fashion Recommendations (Kaggle 대회) — <https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations>

데이터는 대회 규칙에 동의한 사람만 받을 수 있고, 규칙에 따라 이 저장소에 포함하지 않는다. 아래 값은 파일 내용이 아니라 같은 파일인지 확인하기 위한 크기와 SHA-256 해시다.

| 파일 | 크기 (바이트) | SHA-256 | 받은 날짜 |
|---|---:|---|---|
| `articles.csv.zip` | 107,081,191 | `8a6007409cc7bd15716ae218b17ecf5bcb7d890e7dce39c1bf0129dd3a8f6fed` | 2026-10-28 |
| `transactions_train.csv.zip` | 612,670,986 | `5fcc90e80355e35aa04c04aa5c47587f4c6817eb3ba4ed3dc685b89a591559e3` | 2026-10-28 |
| `images.zip` | 30,036,309,564 | `2f70a9886bb2ca21da5e8abd4522d13c4deb8d303dcfd4f065cef0581168484b` | 2026-10-28 |

현재 상품 목록·동종 판매·다음 시즌 비교를 다시 만들 때 필요한 원본은 `articles.csv.zip`과 `transactions_train.csv.zip`이다. `images.zip`은 상품 사진을 표시할 때만 필요하다. 내려받은 `customers.csv.zip`과 `sample_submission.csv.zip`은 이 도구의 MD 분석에 사용하지 않는다.

`backend/scripts/import_hm.py`는 실행 전에 이 값과 비교한다. 다르면 경고를 출력하고 계속 진행한다. 다른 시점에 받은 파일은 표본과 문서의 수치가 달라질 수 있다. `images.zip`은 기본으로 크기만 비교하고, `--verify-images`를 붙이면 SHA-256까지 확인한다(수 분 소요).

직접 확인하려면 PowerShell에서 `Get-FileHash 파일경로 -Algorithm SHA256`을 실행한다.

## 저장소에 두지 않는 파일

| 파일 | 위치 | 다시 만드는 방법 |
|---|---|---|
| 로컬 DB와 개인 백업본 | `backend/md_decision_lab.db`, `backend/*.db` | 원본 판매 집계는 다시 만들 수 있지만 사용자가 저장한 판단·입력·기획안은 DB 백업 없이는 복구할 수 없다 |
| 상품 사진 (선정 상품만) | `frontend/public/hm_images/` | `import_hm.py ... --images images.zip` |
| 가상 운영 조건 CSV 4개 | `sample_data/hm_operating_case/*.csv` | `generate_hm_operating_case.py` → `verify_hm_operating_case.py` |
| 대용량 변환 파일 | `*.parquet`, `*.arrow` | 원본 ZIP으로 다시 생성 |

모두 `.gitignore`로 제외한다. **원본 ZIP은 재현을 위해 보관하고, 로컬 DB는 저장한 MD 판단과 기획안을 지키기 위해 별도로 백업한다.** 상품 사진과 가상 운영 조건 CSV는 원본과 스크립트로 다시 만들 수 있다. `--replace`는 기존 H&M 작업공간의 판단을 삭제할 수 있으므로 백업 확인 전에 실행하지 않는다.

`sample_data/public_demo/`의 두 CSV는 별도의 **완전 합성 자료**라 공개 저장소에 포함한다. H&M 판매·사진·상품 정보를 변환하거나 추출한 파일이 아니다.

## 원본 보관 원칙

- 저장소 밖 전용 폴더에 둔다. 저장소 안에 복사하지 않는다.
- 현재 작업 폴더에 원본을 내려받았더라도 `H&M판매량 파일/`과 원본 파일명은 `.gitignore`로 제외한다. 이는 실수 방지용이며 장기 보관 위치로 권장하지 않는다.
- 백업은 본인만 접근하는 저장소(공유 링크 없는 개인 클라우드, 외장 디스크)에 둔다. 다른 사람이 볼 수 있는 곳, 협업자가 있는 비공개 저장소에도 올리지 않는다.
- 화면 캡처와 시연 자료에는 상품 사진을 가린 `사진 숨김` 보기를 쓴다.
