"""
H&M 거래 파일 -> 상품x주 단위 판매 집계 (가벼운 파일로 줄이기)

사용법 (명령 프롬프트 또는 VS Code 터미널):
    pip install pandas
    python hm_weekly_sales.py --input "C:/경로/transactions_train.csv" --articles "C:/경로/articles.csv" --top 3000

결과 파일 (입력 파일과 같은 폴더에 생성):
    weekly_sales_top.csv   : 상품(article_id) x 주(week_start) x 채널별 판매 수량
    article_totals.csv     : 상품별 전체 판매 수량과 순위 (선택된 상품 목록)

옵션:
    --articles 경로  articles.csv를 지정하면 '의류'만 남깁니다 (아래 --scope 참고). 권장.
    --scope apparel|all  apparel(기본): Ladieswear/Divided/Menswear/Sport 중
                         상의·하의·원피스류(Garment Upper/Lower/Full body)만. 약 5만 개 상품.
                         all: 액세서리·신발·속옷 등 전부.
    --top N       전체 판매량 상위 N개 상품만 남깁니다 (기본 3000). 0이면 전부 남깁니다.
    --since DATE  이 날짜 이후 거래만 사용합니다 (기본: 전체 기간).
    --until DATE  이 날짜까지만 사용합니다.

참고:
 - H&M 거래 한 행은 상품 1개 구매 1건입니다. 그래서 '판매 수량 = 행 수'입니다.
 - price 값은 정규화된 값이라 원화 매출이 아닙니다. 평균 가격 지수(price_index)로만 남깁니다.
 - sales_channel_id: 1 = 오프라인 매장, 2 = 온라인 (H&M 대회 설명 기준)
 - 파일 크기에 따라 몇 분 걸릴 수 있습니다. 진행 상황이 화면에 표시됩니다.
"""
import argparse
import os
import sys

import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="transactions_train.csv 경로")
    ap.add_argument("--articles", default=None, help="articles.csv 경로 (의류만 남길 때)")
    ap.add_argument("--scope", choices=["apparel", "all"], default="apparel")
    ap.add_argument("--top", type=int, default=3000)
    ap.add_argument("--since", default=None)
    ap.add_argument("--until", default=None)
    ap.add_argument("--chunk", type=int, default=2_000_000)
    args = ap.parse_args()

    if not os.path.exists(args.input):
        sys.exit(f"파일을 찾을 수 없습니다: {args.input}")

    out_dir = os.path.dirname(os.path.abspath(args.input))

    keep_articles = None
    if args.articles and args.scope == "apparel":
        if not os.path.exists(args.articles):
            sys.exit(f"articles.csv를 찾을 수 없습니다: {args.articles}")
        art = pd.read_csv(args.articles, usecols=["article_id", "index_group_name", "product_group_name"])
        art = art[
            art["index_group_name"].isin(["Ladieswear", "Divided", "Menswear", "Sport"])
            & art["product_group_name"].isin(["Garment Upper body", "Garment Lower body", "Garment Full body"])
        ]
        keep_articles = set(art["article_id"].astype("int32"))
        print(f"의류 범위 상품 수: {len(keep_articles):,}")
    elif args.scope == "apparel":
        print("* --articles 를 지정하지 않아 전체 상품(액세서리 포함)으로 집계합니다.")
    since = pd.Timestamp(args.since) if args.since else None
    until = pd.Timestamp(args.until) if args.until else None

    # customer_id(긴 문자열)는 읽지 않아 메모리를 아낍니다.
    usecols = ["t_dat", "article_id", "price", "sales_channel_id"]
    dtypes = {"article_id": "int32", "price": "float32", "sales_channel_id": "int8"}

    acc = None  # (week_start, article_id) 단위 누적 결과
    total_rows = 0
    kept_rows = 0

    reader = pd.read_csv(
        args.input, usecols=usecols, dtype=dtypes, parse_dates=["t_dat"], chunksize=args.chunk
    )
    for i, chunk in enumerate(reader, start=1):
        total_rows += len(chunk)
        if keep_articles is not None:
            chunk = chunk[chunk["article_id"].isin(keep_articles)]
        if since is not None:
            chunk = chunk[chunk["t_dat"] >= since]
        if until is not None:
            chunk = chunk[chunk["t_dat"] <= until]
        if chunk.empty:
            continue
        kept_rows += len(chunk)

        # 월요일 시작 주
        week_start = chunk["t_dat"].dt.normalize() - pd.to_timedelta(chunk["t_dat"].dt.dayofweek, unit="D")
        part = (
            pd.DataFrame(
                {
                    "week_start": week_start,
                    "article_id": chunk["article_id"],
                    "units_store": (chunk["sales_channel_id"] == 1).astype("int32"),
                    "units_online": (chunk["sales_channel_id"] == 2).astype("int32"),
                    "price_sum": chunk["price"].astype("float64"),
                }
            )
            .groupby(["week_start", "article_id"], as_index=False)
            .sum()
        )
        acc = part if acc is None else pd.concat([acc, part]).groupby(["week_start", "article_id"], as_index=False).sum()
        print(f"[{i}] 읽은 행 {total_rows:,} / 사용한 행 {kept_rows:,} / 누적 집계 행 {len(acc):,}", flush=True)

    if acc is None or acc.empty:
        sys.exit("조건에 맞는 거래가 없습니다. --since / --until 값을 확인하세요.")

    acc["units"] = acc["units_store"] + acc["units_online"]
    acc["price_index"] = (acc["price_sum"] / acc["units"]).round(6)  # 정규화 가격의 평균 (원화 아님)
    acc = acc.drop(columns=["price_sum"])

    totals = (
        acc.groupby("article_id", as_index=False)["units"].sum()
        .sort_values("units", ascending=False)
        .reset_index(drop=True)
    )
    totals["rank"] = totals.index + 1

    if args.top and args.top > 0:
        keep = set(totals.head(args.top)["article_id"])
        acc = acc[acc["article_id"].isin(keep)]
        totals = totals[totals["article_id"].isin(keep)]

    acc = acc.sort_values(["article_id", "week_start"])
    acc["week_start"] = acc["week_start"].dt.strftime("%Y-%m-%d")

    w_path = os.path.join(out_dir, "weekly_sales_top.csv")
    t_path = os.path.join(out_dir, "article_totals.csv")
    acc.to_csv(w_path, index=False)
    totals.to_csv(t_path, index=False)

    print("\n완료")
    print(f"  전체 거래 행: {total_rows:,}")
    print(f"  사용한 거래 행: {kept_rows:,}")
    print(f"  남긴 상품 수: {totals['article_id'].nunique():,}")
    print(f"  주간 집계 행 수: {len(acc):,}")
    print(f"  기간: {acc['week_start'].min()} ~ {acc['week_start'].max()}")
    print(f"  저장: {w_path}")
    print(f"  저장: {t_path}")
    size_mb = os.path.getsize(w_path) / 1024 / 1024
    print(f"  weekly_sales_top.csv 크기: {size_mb:.1f} MB")
    if size_mb > 50:
        print("  * 파일이 큽니다. --top 값을 줄이거나 --since 로 기간을 줄여 다시 실행하세요.")


if __name__ == "__main__":
    main()
