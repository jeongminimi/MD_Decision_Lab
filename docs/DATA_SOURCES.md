# 데이터 출처와 보관

## 원본

H&M Personalized Fashion Recommendations (Kaggle 대회) — <https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations>

데이터는 대회 규칙에 동의한 사람만 받을 수 있고, 규칙에 따라 이 저장소에 포함하지 않는다. 아래 값은 파일 내용이 아니라 같은 파일인지 확인하기 위한 크기와 SHA-256 해시다.

| 파일 | 크기 (바이트) | SHA-256 | 받은 날짜 |
|---|---:|---|---|
| `articles.csv.zip` | 107,081,191 | `8a6007409cc7bd15716ae218b17ecf5bcb7d890e7dce39c1bf0129dd3a8f6fed` | 2026-10-28 |
| `transactions_train.csv.zip` | 612,670,986 | `5fcc90e80355e35aa04c04aa5c47587f4c6817eb3ba4ed3dc685b89a591559e3` | 2026-10-28 |
| `images.zip` | 30,036,309,564 | `2f70a9886bb2ca21da5e8abd4522d13c4deb8d303dcfd4f065cef0581168484b` | 2026-10-28 |

`backend/scripts/import_hm.py`는 실행 전에 이 값과 비교한다. 다르면 경고를 출력하고 계속 진행한다. 다른 시점에 받은 파일은 표본과 문서의 수치가 달라질 수 있다. `images.zip`은 기본으로 크기만 비교하고, `--verify-images`를 붙이면 SHA-256까지 확인한다(수 분 소요).

직접 확인하려면 PowerShell에서 `Get-FileHash 파일경로 -Algorithm SHA256`을 실행한다.

## 저장소에 두지 않는 파일

| 파일 | 위치 | 다시 만드는 방법 |
|---|---|---|
| 로컬 DB | `backend/md_decision_lab.db` | `python scripts/import_hm.py ... --replace` |
| 상품 사진 (선정 상품만) | `frontend/public/hm_images/` | `import_hm.py ... --images images.zip` |
| 가상 운영 조건 CSV 4개 | `sample_data/hm_operating_case/*.csv` | `generate_hm_operating_case.py` → `verify_hm_operating_case.py` |

모두 `.gitignore`로 제외한다. 원본만 있으면 같은 결과를 다시 만들 수 있으므로 따로 백업하지 않아도 된다.

## 원본 보관 원칙

- 저장소 밖 전용 폴더에 둔다. 저장소 안에 복사하지 않는다.
- 백업은 본인만 접근하는 저장소(공유 링크 없는 개인 클라우드, 외장 디스크)에 둔다. 다른 사람이 볼 수 있는 곳, 협업자가 있는 비공개 저장소에도 올리지 않는다.
- 화면 캡처와 시연 자료에는 상품 사진을 가린 `사진 숨김` 보기를 쓴다.
