import csv
from datetime import date, timedelta
import random

# Fix random seed for reproducible synthetic dataset
random.seed(20260831)

OUTPUT_DIR = r"C:\Users\samsung\Documents\Codex\2026-10-24\x20\MD_Decision_Lab\sample_data\fashion_fw_case"

products_meta = [
    # --- 10 Summer Remaining Items (2026SS) ---
    {
        "sku": "FSH-SS-001",
        "name": "[여름 잔여] 린넨 블렌드 릴렉스 반팔 셔츠",
        "category": "상의",
        "stock_on_hand": 145,
        "inbound_units": 0,
        "lead_time_days": 14,
        "target_cover_days": 30,
        "list_price": 59000,
        "unit_price": 49000,
        "unit_cost": 18000,
        "season_group": "2026SS",
        "collection_year": 2026,
        "lifecycle_status": "clearance",
        "reorderable": False,
        "launch_date": "2026-05-01",
        "event_start_date": "2026-08-01",
        "planning_note": "여름 베스트셀러였으나 잔여 재고 145개가 남아 목표 보유일(30일) 대비 과잉재고 상태. 추가 할인 검토 필요",
        "type": "summer_overstock"
    },
    {
        "sku": "FSH-SS-002",
        "name": "[여름 잔여] 쿨맥스 베이직 크루넥 반팔 티",
        "category": "상의",
        "stock_on_hand": 180,
        "inbound_units": 0,
        "lead_time_days": 14,
        "target_cover_days": 30,
        "list_price": 35000,
        "unit_price": 29000,
        "unit_cost": 9500,
        "season_group": "2026SS",
        "collection_year": 2026,
        "lifecycle_status": "clearance",
        "reorderable": False,
        "launch_date": "2026-05-01",
        "event_start_date": "2026-08-01",
        "planning_note": "기본 티셔츠로 일 1개 수준 판매 유지되나 잔여 수량이 180개로 8월 말 기준 심각한 과잉재고",
        "type": "summer_overstock"
    },
    {
        "sku": "FSH-SS-003",
        "name": "[여름 잔여] 서머 시어서커 원턱 쇼츠",
        "category": "하의",
        "stock_on_hand": 110,
        "inbound_units": 0,
        "lead_time_days": 14,
        "target_cover_days": 30,
        "list_price": 49000,
        "unit_price": 39000,
        "unit_cost": 15000,
        "season_group": "2026SS",
        "collection_year": 2026,
        "lifecycle_status": "clearance",
        "reorderable": False,
        "launch_date": "2026-05-15",
        "event_start_date": "2026-08-01",
        "planning_note": "시어서커 소재 특성상 가을 착용 불가, 시즌 오프 할인율 확대 및 프로모션 노출 필요",
        "type": "summer_overstock"
    },
    {
        "sku": "FSH-SS-004",
        "name": "[여름 잔여] 라이트웨이트 린넨 스트레이트 팬츠",
        "category": "하의",
        "stock_on_hand": 35,
        "inbound_units": 0,
        "lead_time_days": 14,
        "target_cover_days": 30,
        "list_price": 69000,
        "unit_price": 59000,
        "unit_cost": 22000,
        "season_group": "2026SS",
        "collection_year": 2026,
        "lifecycle_status": "clearance",
        "reorderable": False,
        "launch_date": "2026-05-10",
        "event_start_date": "2026-08-01",
        "planning_note": "자연스러운 잔여 재고 소진 진행 중, 9월 초 자연 소진 예상",
        "type": "summer_moderate"
    },
    {
        "sku": "FSH-SS-005",
        "name": "[여름 잔여] 브이넥 티어드 플리츠 롱 원피스",
        "category": "원피스",
        "stock_on_hand": 95,
        "inbound_units": 0,
        "lead_time_days": 21,
        "target_cover_days": 30,
        "list_price": 89000,
        "unit_price": 69000,
        "unit_cost": 28000,
        "season_group": "2026SS",
        "collection_year": 2026,
        "lifecycle_status": "clearance",
        "reorderable": False,
        "launch_date": "2026-05-20",
        "event_start_date": "2026-08-01",
        "planning_note": "바캉스 시즌 종료로 수요 둔화되었으나 재고 95개 잔여로 과잉재고 주의군",
        "type": "summer_overstock"
    },
    {
        "sku": "FSH-SS-006",
        "name": "[여름 잔여] 스퀘어넥 퍼프 반팔 원피스",
        "category": "원피스",
        "stock_on_hand": 28,
        "inbound_units": 0,
        "lead_time_days": 14,
        "target_cover_days": 30,
        "list_price": 79000,
        "unit_price": 65000,
        "unit_cost": 25000,
        "season_group": "2026SS",
        "collection_year": 2026,
        "lifecycle_status": "clearance",
        "reorderable": False,
        "launch_date": "2026-05-20",
        "event_start_date": "2026-08-01",
        "planning_note": "재고 소량 잔여(28개)로 적정 보유 수준 내 정상 소진 중",
        "type": "summer_moderate"
    },
    {
        "sku": "FSH-SS-007",
        "name": "[여름 잔여] 서머 시스루 오픈카라 니트 가디건",
        "category": "니트",
        "stock_on_hand": 120,
        "inbound_units": 0,
        "lead_time_days": 14,
        "target_cover_days": 30,
        "list_price": 59000,
        "unit_price": 49000,
        "unit_cost": 17000,
        "season_group": "2026SS",
        "collection_year": 2026,
        "lifecycle_status": "clearance",
        "reorderable": False,
        "launch_date": "2026-06-01",
        "event_start_date": "2026-08-01",
        "planning_note": "간절기 걸침용으로 8월 말까지 유지 후 균일가 정리 권장",
        "type": "summer_overstock"
    },
    {
        "sku": "FSH-SS-008",
        "name": "[여름 잔여] 린넨 케이블 반팔 니트 풀오버",
        "category": "니트",
        "stock_on_hand": 30,
        "inbound_units": 0,
        "lead_time_days": 14,
        "target_cover_days": 30,
        "list_price": 65000,
        "unit_price": 52000,
        "unit_cost": 19000,
        "season_group": "2026SS",
        "collection_year": 2026,
        "lifecycle_status": "clearance",
        "reorderable": False,
        "launch_date": "2026-05-15",
        "event_start_date": "2026-08-01",
        "planning_note": "인기 품목으로 8월 대부분 소진 완료, 잔여 30장 안정적 마감",
        "type": "summer_moderate"
    },
    {
        "sku": "FSH-SS-009",
        "name": "[여름 잔여] 윈드브레이커 패커블 서머 아노락",
        "category": "아우터",
        "stock_on_hand": 130,
        "inbound_units": 0,
        "lead_time_days": 21,
        "target_cover_days": 30,
        "list_price": 79000,
        "unit_price": 59000,
        "unit_cost": 24000,
        "season_group": "2026SS",
        "collection_year": 2026,
        "lifecycle_status": "clearance",
        "reorderable": False,
        "launch_date": "2026-05-01",
        "event_start_date": "2026-08-01",
        "planning_note": "장마철 이후 판매 급감 및 높은 잔여 재고(130개)로 과잉재고 리스크 등록",
        "type": "summer_overstock"
    },
    {
        "sku": "FSH-SS-010",
        "name": "[여름 잔여] 초경량 린넨 싱글 서머 자켓",
        "category": "아우터",
        "stock_on_hand": 42,
        "inbound_units": 0,
        "lead_time_days": 21,
        "target_cover_days": 30,
        "list_price": 119000,
        "unit_price": 89000,
        "unit_cost": 36000,
        "season_group": "2026SS",
        "collection_year": 2026,
        "lifecycle_status": "clearance",
        "reorderable": False,
        "launch_date": "2026-05-01",
        "event_start_date": "2026-08-01",
        "planning_note": "초가을까지 오피스룩 소진 유도 후 시즌 종료 예정",
        "type": "summer_moderate"
    },

    # --- 12 Fall New Arrivals (2026FW) ---
    {
        "sku": "FSH-FW-001",
        "name": "[26FW 신상] 울 블렌드 클래식 오버핏 트렌치코트",
        "category": "아우터",
        "stock_on_hand": 120,
        "inbound_units": 60,
        "lead_time_days": 28,
        "target_cover_days": 45,
        "list_price": 189000,
        "unit_price": 189000,
        "unit_cost": 68000,
        "season_group": "2026FW",
        "collection_year": 2026,
        "lifecycle_status": "upcoming",
        "reorderable": True,
        "launch_date": "2026-09-01",
        "event_start_date": "",
        "planning_note": "가을 메인 시그니처 아우터, 9/1 정식 론칭 쇼케이스 오픈 준비 재고",
        "type": "fall"
    },
    {
        "sku": "FSH-FW-002",
        "name": "[26FW 신상] 헤비 비건레더 봄버 자켓",
        "category": "아우터",
        "stock_on_hand": 80,
        "inbound_units": 40,
        "lead_time_days": 21,
        "target_cover_days": 45,
        "list_price": 149000,
        "unit_price": 149000,
        "unit_cost": 52000,
        "season_group": "2026FW",
        "collection_year": 2026,
        "lifecycle_status": "upcoming",
        "reorderable": True,
        "launch_date": "2026-09-01",
        "event_start_date": "",
        "planning_note": "트렌드 아우터 라인업, 오픈 전 입고 완료 및 론칭 대기",
        "type": "fall"
    },
    {
        "sku": "FSH-FW-003",
        "name": "[26FW 신상] 클래식 더블브레스티드 테일러드 블레이저",
        "category": "아우터",
        "stock_on_hand": 100,
        "inbound_units": 50,
        "lead_time_days": 21,
        "target_cover_days": 45,
        "list_price": 159000,
        "unit_price": 159000,
        "unit_cost": 55000,
        "season_group": "2026FW",
        "collection_year": 2026,
        "lifecycle_status": "upcoming",
        "reorderable": True,
        "launch_date": "2026-09-01",
        "event_start_date": "",
        "planning_note": "오피스 셋업 중심 아이템, 초도 물량 입고 완료",
        "type": "fall"
    },
    {
        "sku": "FSH-FW-004",
        "name": "[26FW 신상] 엑스트라파인 메리노울 라운드 니트",
        "category": "니트",
        "stock_on_hand": 150,
        "inbound_units": 100,
        "lead_time_days": 18,
        "target_cover_days": 45,
        "list_price": 79000,
        "unit_price": 79000,
        "unit_cost": 26000,
        "season_group": "2026FW",
        "collection_year": 2026,
        "lifecycle_status": "upcoming",
        "reorderable": True,
        "launch_date": "2026-09-01",
        "event_start_date": "",
        "planning_note": "FW 기본 에센셜 니트, 9/1 전 색상 동시 론칭",
        "type": "fall"
    },
    {
        "sku": "FSH-FW-005",
        "name": "[26FW 신상] 캐시미어 블렌드 케이블 가디건",
        "category": "니트",
        "stock_on_hand": 90,
        "inbound_units": 45,
        "lead_time_days": 21,
        "target_cover_days": 45,
        "list_price": 99000,
        "unit_price": 99000,
        "unit_cost": 34000,
        "season_group": "2026FW",
        "collection_year": 2026,
        "lifecycle_status": "upcoming",
        "reorderable": True,
        "launch_date": "2026-09-01",
        "event_start_date": "",
        "planning_note": "간절기 아우터 겸용 니트웨어 주력 신상품",
        "type": "fall"
    },
    {
        "sku": "FSH-FW-006",
        "name": "[26FW 신상] 모헤어 소프트 터치 하프집업 니트",
        "category": "니트",
        "stock_on_hand": 70,
        "inbound_units": 35,
        "lead_time_days": 21,
        "target_cover_days": 45,
        "list_price": 89000,
        "unit_price": 89000,
        "unit_cost": 31000,
        "season_group": "2026FW",
        "collection_year": 2026,
        "lifecycle_status": "upcoming",
        "reorderable": True,
        "launch_date": "2026-09-01",
        "event_start_date": "",
        "planning_note": "2030 영타깃 트렌드 집업 스타일",
        "type": "fall"
    },
    {
        "sku": "FSH-FW-007",
        "name": "[26FW 신상] 클래식 릴렉스드 옥스포드 셔츠",
        "category": "상의",
        "stock_on_hand": 110,
        "inbound_units": 50,
        "lead_time_days": 14,
        "target_cover_days": 45,
        "list_price": 59000,
        "unit_price": 59000,
        "unit_cost": 19000,
        "season_group": "2026FW",
        "collection_year": 2026,
        "lifecycle_status": "upcoming",
        "reorderable": True,
        "launch_date": "2026-09-01",
        "event_start_date": "",
        "planning_note": "가을 레이어드 기본 필수 셔츠",
        "type": "fall"
    },
    {
        "sku": "FSH-FW-008",
        "name": "[26FW 신상] 헤비웨이트 프렌치테리 스웨트셔츠",
        "category": "상의",
        "stock_on_hand": 130,
        "inbound_units": 70,
        "lead_time_days": 14,
        "target_cover_days": 45,
        "list_price": 65000,
        "unit_price": 65000,
        "unit_cost": 21000,
        "season_group": "2026FW",
        "collection_year": 2026,
        "lifecycle_status": "upcoming",
        "reorderable": True,
        "launch_date": "2026-09-01",
        "event_start_date": "",
        "planning_note": "캐주얼 데일리 라인업 핵심 상품",
        "type": "fall"
    },
    {
        "sku": "FSH-FW-009",
        "name": "[26FW 신상] 투턱 와이드 포멀 슬랙스",
        "category": "하의",
        "stock_on_hand": 140,
        "inbound_units": 60,
        "lead_time_days": 18,
        "target_cover_days": 45,
        "list_price": 75000,
        "unit_price": 75000,
        "unit_cost": 24000,
        "season_group": "2026FW",
        "collection_year": 2026,
        "lifecycle_status": "upcoming",
        "reorderable": True,
        "launch_date": "2026-09-01",
        "event_start_date": "",
        "planning_note": "블레이저와 셋업 연출 가능한 베이직 팬츠",
        "type": "fall"
    },
    {
        "sku": "FSH-FW-010",
        "name": "[26FW 신상] 딥인디고 레귤러 스트레이트 데님",
        "category": "하의",
        "stock_on_hand": 125,
        "inbound_units": 50,
        "lead_time_days": 18,
        "target_cover_days": 45,
        "list_price": 69000,
        "unit_price": 69000,
        "unit_cost": 23000,
        "season_group": "2026FW",
        "collection_year": 2026,
        "lifecycle_status": "upcoming",
        "reorderable": True,
        "launch_date": "2026-09-01",
        "event_start_date": "",
        "planning_note": "사계절 범용 데님, FW 시즌용 딥 컬러 워싱 적용",
        "type": "fall"
    },
    {
        "sku": "FSH-FW-011",
        "name": "[26FW 신상] 벨티드 플리츠 셔츠 원피스",
        "category": "원피스",
        "stock_on_hand": 65,
        "inbound_units": 30,
        "lead_time_days": 21,
        "target_cover_days": 45,
        "list_price": 109000,
        "unit_price": 109000,
        "unit_cost": 37000,
        "season_group": "2026FW",
        "collection_year": 2026,
        "lifecycle_status": "upcoming",
        "reorderable": True,
        "launch_date": "2026-09-01",
        "event_start_date": "",
        "planning_note": "가을 출근룩/하객룩 타깃 단품 원피스",
        "type": "fall"
    },
    {
        "sku": "FSH-FW-012",
        "name": "[26FW 신상] 울 니트 플레어 롱 원피스",
        "category": "원피스",
        "stock_on_hand": 55,
        "inbound_units": 25,
        "lead_time_days": 21,
        "target_cover_days": 45,
        "list_price": 119000,
        "unit_price": 119000,
        "unit_cost": 41000,
        "season_group": "2026FW",
        "collection_year": 2026,
        "lifecycle_status": "upcoming",
        "reorderable": True,
        "launch_date": "2026-09-01",
        "event_start_date": "",
        "planning_note": "보온성과 실루엣을 강조한 FW 시즌 원피스",
        "type": "fall"
    },

    # --- 8 Winter Event Items (2025FW 재고 소진 이벤트) ---
    {
        "sku": "FSH-EV-001",
        "name": "[25FW 이벤트] 프리미엄 구스다운 후드 롱패딩",
        "category": "아우터",
        "stock_on_hand": 22,
        "inbound_units": 0,
        "lead_time_days": 28,
        "target_cover_days": 30,
        "list_price": 299000,
        "unit_price": 119000,
        "unit_cost": 75000,
        "season_group": "2025FW",
        "collection_year": 2025,
        "lifecycle_status": "event_clearance",
        "reorderable": False,
        "launch_date": "2025-10-15",
        "event_start_date": "2026-08-25",
        "planning_note": "작년 헤비 아우터 60% 역시즌 세일, 8/25 오픈 후 판매 폭증. 재발주 절대 불가",
        "type": "winter_event"
    },
    {
        "sku": "FSH-EV-002",
        "name": "[25FW 이벤트] 미니멀 덕다운 숏패딩 점퍼",
        "category": "아우터",
        "stock_on_hand": 18,
        "inbound_units": 0,
        "lead_time_days": 21,
        "target_cover_days": 30,
        "list_price": 199000,
        "unit_price": 79000,
        "unit_cost": 49000,
        "season_group": "2025FW",
        "collection_year": 2025,
        "lifecycle_status": "event_clearance",
        "reorderable": False,
        "launch_date": "2025-10-20",
        "event_start_date": "2026-08-25",
        "planning_note": "가성비 숏패딩 특가전, 잔여 18개 완판 예상. 재생산 불가",
        "type": "winter_event"
    },
    {
        "sku": "FSH-EV-003",
        "name": "[25FW 이벤트] 핸드메이드 울 더블 롱코트",
        "category": "아우터",
        "stock_on_hand": 15,
        "inbound_units": 0,
        "lead_time_days": 28,
        "target_cover_days": 30,
        "list_price": 279000,
        "unit_price": 109000,
        "unit_cost": 69000,
        "season_group": "2025FW",
        "collection_year": 2025,
        "lifecycle_status": "event_clearance",
        "reorderable": False,
        "launch_date": "2025-10-15",
        "event_start_date": "2026-08-25",
        "planning_note": "고가 울 핸드메이드 코트 61% 할인, 행사 직후 완판 임박. 추가 공급 불가",
        "type": "winter_event"
    },
    {
        "sku": "FSH-EV-004",
        "name": "[25FW 이벤트] 리버시블 시어링 무스탕 자켓",
        "category": "아우터",
        "stock_on_hand": 12,
        "inbound_units": 0,
        "lead_time_days": 25,
        "target_cover_days": 30,
        "list_price": 239000,
        "unit_price": 95000,
        "unit_cost": 59000,
        "season_group": "2025FW",
        "collection_year": 2025,
        "lifecycle_status": "event_clearance",
        "reorderable": False,
        "launch_date": "2025-11-01",
        "event_start_date": "2026-08-25",
        "planning_note": "소량 남은 무스탕 라인 재고 정리, 8/25 이후 판매 급증. 추가 매입 불가",
        "type": "winter_event"
    },
    {
        "sku": "FSH-EV-005",
        "name": "[25FW 이벤트] 헤비게이지 울 터틀넥 니트",
        "category": "니트",
        "stock_on_hand": 35,
        "inbound_units": 0,
        "lead_time_days": 18,
        "target_cover_days": 30,
        "list_price": 89000,
        "unit_price": 39000,
        "unit_cost": 21000,
        "season_group": "2025FW",
        "collection_year": 2025,
        "lifecycle_status": "event_clearance",
        "reorderable": False,
        "launch_date": "2025-10-25",
        "event_start_date": "2026-08-25",
        "planning_note": "겨울 보온 니트 역시즌 기획전 특가, 빠른 소진 추세",
        "type": "winter_event"
    },
    {
        "sku": "FSH-EV-006",
        "name": "[25FW 이벤트] 알파카 블렌드 라운드 풀오버",
        "category": "니트",
        "stock_on_hand": 20,
        "inbound_units": 0,
        "lead_time_days": 18,
        "target_cover_days": 30,
        "list_price": 99000,
        "unit_price": 45000,
        "unit_cost": 24000,
        "season_group": "2025FW",
        "collection_year": 2025,
        "lifecycle_status": "event_clearance",
        "reorderable": False,
        "launch_date": "2025-11-05",
        "event_start_date": "2026-08-25",
        "planning_note": "작년 잔여 알파카 니트 반값 세일, 8월 말 완판 예상",
        "type": "winter_event"
    },
    {
        "sku": "FSH-EV-007",
        "name": "[25FW 이벤트] 본딩 기모 웜 테이퍼드 슬랙스",
        "category": "하의",
        "stock_on_hand": 40,
        "inbound_units": 0,
        "lead_time_days": 18,
        "target_cover_days": 30,
        "list_price": 79000,
        "unit_price": 35000,
        "unit_cost": 17000,
        "season_group": "2025FW",
        "collection_year": 2025,
        "lifecycle_status": "event_clearance",
        "reorderable": False,
        "launch_date": "2025-11-10",
        "event_start_date": "2026-08-25",
        "planning_note": "한겨울용 기모 바지 역시즌 할인, 실구매자 중심 주문 유입",
        "type": "winter_event"
    },
    {
        "sku": "FSH-EV-008",
        "name": "[25FW 이벤트] 코듀로이 웜 와이드 팬츠",
        "category": "하의",
        "stock_on_hand": 25,
        "inbound_units": 0,
        "lead_time_days": 18,
        "target_cover_days": 30,
        "list_price": 75000,
        "unit_price": 35000,
        "unit_cost": 16000,
        "season_group": "2025FW",
        "collection_year": 2025,
        "lifecycle_status": "event_clearance",
        "reorderable": False,
        "launch_date": "2025-11-10",
        "event_start_date": "2026-08-25",
        "planning_note": "골덴 와이드 팬츠 53% 세일, 재입고 없이 현 재고 한정 판매",
        "type": "winter_event"
    }
]

# Calculate discount_pct
for p in products_meta:
    lp = p["list_price"]
    cp = p["unit_price"]
    disc = round((1.0 - (cp / lp)) * 100.0, 1)
    p["discount_pct"] = disc

# -------------------------------------------------------------
# 2. Generate 60 Days of Sales (2026-07-03 to 2026-08-31)
# -------------------------------------------------------------
start_date = date(2026, 7, 3)
end_date = date(2026, 8, 31)
days_count = (end_date - start_date).days + 1  # 60 days
dates = [start_date + timedelta(days=i) for i in range(days_count)]

sales_rows = []

for p in products_meta:
    sku = p["sku"]
    unit_price = p["unit_price"]
    unit_cost = p["unit_cost"]
    p_type = p["type"]

    for d in dates:
        d_str = d.isoformat()
        day_idx = (d - start_date).days # 0 to 59
        units = 0

        if p_type == "fall":
            # 2026FW New arrival: 0 sales before 2026-09-01 official launch
            units = 0

        elif p_type == "summer_overstock":
            # Summer overstock: Steady low sales across 30d (~1/day, ~30 units in 30d, 7d ~6 units)
            # This ensures units_7d >= 5 (no recent_drop_uncertain) and decision_daily ~ 1.0.
            # With stock >= 95, cover >= 95 days > target_cover (30) + 30 -> overstock_risk!
            if day_idx <= 28: # July
                units = random.choice([2, 3, 2, 4, 3, 2])
            elif day_idx <= 52: # Aug 1 to Aug 24
                units = random.choice([1, 1, 0, 1, 2, 1])
            else: # Aug 25 to Aug 31 (recent 7d)
                units = random.choice([1, 1, 1, 1, 0, 1, 1]) # total ~6 units in 7d

        elif p_type == "summer_moderate":
            # Moderate clearance: stock 28~42. Total 30d units ~25.
            # cover ~ 35 days (between 30 and 60 days -> slow_moving or healthy)
            if day_idx <= 28:
                units = random.choice([1, 2, 2, 1, 2])
            elif day_idx <= 52:
                units = random.choice([1, 1, 0, 1, 1])
            else:
                units = random.choice([1, 0, 1, 1, 1])

        elif p_type == "winter_event":
            # 8 Winter items: Event starts on 2026-08-25 (day 53 to 59)
            if d < date(2026, 8, 25):
                units = 0
            else:
                # 8/25 to 8/31: surge 3~6 units/day
                units = random.choice([4, 5, 4, 6, 5, 4, 5])

        revenue = units * unit_price
        gross_margin = revenue - (units * unit_cost)

        sales_rows.append({
            "sku": sku,
            "sale_date": d_str,
            "units_sold": units,
            "revenue": revenue,
            "gross_margin": gross_margin
        })

# Write Files
products_file = f"{OUTPUT_DIR}\\fashion_products_20260831.csv"
product_headers = [
    "sku", "name", "category", "stock_on_hand", "inbound_units",
    "lead_time_days", "target_cover_days", "unit_price", "unit_cost"
]
with open(products_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=product_headers)
    writer.writeheader()
    for p in products_meta:
        writer.writerow({k: p[k] for k in product_headers})

sales_file = f"{OUTPUT_DIR}\\fashion_daily_sales_20260831.csv"
sales_headers = ["sku", "sale_date", "units_sold", "revenue", "gross_margin"]
with open(sales_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=sales_headers)
    writer.writeheader()
    for row in sales_rows:
        writer.writerow(row)

context_file = f"{OUTPUT_DIR}\\fashion_merchandising_context.csv"
context_headers = [
    "sku", "season_group", "collection_year", "lifecycle_status",
    "reorderable", "launch_date", "event_start_date",
    "list_price", "current_price", "discount_pct", "planning_note"
]
with open(context_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=context_headers)
    writer.writeheader()
    for p in products_meta:
        writer.writerow({
            "sku": p["sku"],
            "season_group": p["season_group"],
            "collection_year": p["collection_year"],
            "lifecycle_status": p["lifecycle_status"],
            "reorderable": "true" if p["reorderable"] else "false",
            "launch_date": p["launch_date"],
            "event_start_date": p["event_start_date"],
            "list_price": p["list_price"],
            "current_price": p["unit_price"],
            "discount_pct": f"{p['discount_pct']:.1f}",
            "planning_note": p["planning_note"]
        })

print("Generated CSVs successfully.")

