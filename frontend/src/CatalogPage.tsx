import { useEffect, useLayoutEffect, useState } from "react";
import { ArrowRight, Search } from "lucide-react";
import { workApi, type CatalogProduct, type CatalogResult, type CatalogSortBy, type CatalogSortDir, type WorkDataset } from "./workApi";
import PeerPanel from "./PeerPanel";

const n = (value: number) => new Intl.NumberFormat("ko-KR").format(value);

export default function CatalogPage({ dataset, asOf, simulation, onReview }: {
  dataset: WorkDataset; asOf: string; simulation: boolean; onReview: (sku: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<CatalogSortBy>("name");
  const [sortDir, setSortDir] = useState<CatalogSortDir>("asc");
  const [result, setResult] = useState<CatalogResult | null>(null);
  const [selected, setSelected] = useState<CatalogProduct | null>(null);
  const [error, setError] = useState("");

  useEffect(() => { setQuery(""); setPage(1); setSelected(null); setSortBy("name"); setSortDir("asc"); }, [dataset.id]);
  useEffect(() => { setSelected(null); }, [simulation, asOf]);
  useLayoutEffect(() => {
    if (selected) document.getElementById("catalog-product-detail")?.scrollIntoView({ behavior: "instant", block: "start" });
  }, [selected]);
  function selectProduct(item: CatalogProduct) {
    setSelected(item);
    if (selected?.sku === item.sku) document.getElementById("catalog-product-detail")?.scrollIntoView({ behavior: "instant", block: "start" });
  }
  function nextDirection(column: CatalogSortBy): CatalogSortDir {
    if (column === sortBy) return sortDir === "asc" ? "desc" : "asc";
    return column === "units_30d" || column === "stock" ? "desc" : "asc";
  }
  function changeSort(column: CatalogSortBy) {
    setSortDir(nextDirection(column));
    setSortBy(column);
    setPage(1);
    setSelected(null);
  }
  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void workApi.catalog(dataset.id, query, page, asOf, simulation, sortBy, sortDir)
        .then((data) => { if (active) { setResult(data); setError(""); } })
        .catch((err) => { if (active) setError(err instanceof Error ? err.message : "상품을 불러오지 못했습니다."); });
    }, query ? 250 : 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [dataset.id, query, page, asOf, simulation, sortBy, sortDir]);

  const columns: { key: CatalogSortBy; label: string }[] = [
    { key: "name", label: "상품" }, { key: "category", label: "종류" },
    { key: "section", label: "섹션" }, { key: "units_30d", label: "최근 30일 판매" },
    { key: "stock", label: "재고" },
  ];

  const stockLabel = selected?.stock_source === "simulation" ? "가상 재고" :
    selected?.stock_source === "company_upload" ? "업로드 재고" :
    selected?.stock_source === "md_input" ? "입력 재고" : "현재 재고";
  return <>
    <section className="panel work-panel">
      <div className="work-panel-heading"><div><h2>상품 찾기</h2><small>{dataset.kind === "hm" ? `H&M 원본 상품 파일의 모든 품목 · 판매 기준일 ${asOf}` : `${dataset.name}의 상품 파일 전체`}</small></div>
        <label className="catalog-search"><Search size={16}/><input aria-label="전체 상품 검색" placeholder="상품명·상품번호·종류·섹션 검색" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); setSelected(null); }}/></label></div>
      {error && <p className="work-error">{error}</p>}
      {result === null ? <p className="work-empty">상품을 불러오는 중…</p> : !result.catalog_ready && dataset.kind === "hm" ? <p className="work-empty">전체 상품 자료가 아직 연결되지 않았습니다. 원본 H&M 상품·거래 파일을 연결하면 모든 품목이 여기에 표시됩니다.</p> : <>
        <p className="catalog-count">검색 결과 <b>{n(result?.total ?? 0)}종</b></p>
        <div className="table-scroll"><table className="data-table work-table catalog-table"><thead><tr>{columns.map((column) => <th key={column.key} aria-sort={sortBy === column.key ? sortDir === "asc" ? "ascending" : "descending" : undefined}><button type="button" className={`catalog-sort ${sortBy === column.key ? "active" : ""}`} onClick={() => changeSort(column.key)} aria-label={`${column.label} ${nextDirection(column.key) === "asc" ? "오름차순" : "내림차순"} 정렬`}>{column.label}<span aria-hidden="true">{sortBy === column.key ? sortDir === "asc" ? "▲" : "▼" : "↕"}</span></button></th>)}</tr></thead><tbody>{result.items.map((item) => <tr key={item.sku} className={selected?.sku === item.sku ? "selected-row" : ""}><td><button type="button" className="work-table-product" onClick={() => selectProduct(item)}>{item.image_ref && <img className="work-product-image" src={item.image_ref} alt="" loading="lazy"/>}<span><b>{item.name}</b><small>{item.sku}</small></span></button></td><td>{item.category}</td><td>{item.section}</td><td>{item.units_30d == null ? "자료 없음" : `${n(item.units_30d)}개`}</td><td>{item.stock_on_hand == null ? "자료 없음" : `${n(item.stock_on_hand)}개`}<small>{item.stock_source === "simulation" ? "가상 재고" : item.stock_on_hand == null ? "" : "입력 재고"}</small></td></tr>)}</tbody></table></div>
        {result?.total === 0 && <p className="work-empty">일치하는 상품이 없습니다.</p>}
        {result.total > result.page_size && <div className="catalog-pages"><button type="button" className="button button-secondary" disabled={page === 1} onClick={() => { setSelected(null); setPage(page - 1); }}>이전</button><span>{page} / {Math.ceil(result.total / result.page_size)}</span><button type="button" className="button button-secondary" disabled={page * result.page_size >= result.total} onClick={() => { setSelected(null); setPage(page + 1); }}>다음</button></div>}
      </>}
    </section>
    {selected && <div className="work-detail-target" id="catalog-product-detail"><section className="panel work-panel catalog-selection"><div className="work-panel-heading"><div><span className="section-kicker">PRODUCT · {selected.sku}</span><h2>{selected.name}</h2><small>{selected.section} · {selected.category}</small></div>{selected.image_ref && <img className="work-product-image large" src={selected.image_ref} alt={`${selected.name} 상품 사진`}/>}</div>
      <div className="catalog-selection-metrics"><div><small>최근 14일 판매 · {selected.sales_as_of_date || asOf} 기준</small><strong>{selected.units_14d == null ? "자료 없음" : `${n(selected.units_14d)}개`}</strong></div><div><small>최근 30일 판매 · {selected.sales_as_of_date || asOf} 기준</small><strong>{selected.units_30d == null ? "자료 없음" : `${n(selected.units_30d)}개`}</strong></div><div><small>{stockLabel}{selected.stock_as_of_date ? ` · ${selected.stock_as_of_date} 기준` : ""}</small><strong>{selected.stock_on_hand == null ? "자료 없음" : `${n(selected.stock_on_hand)}개`}</strong></div></div>
      {selected.reviewable && <button type="button" className="button button-primary" onClick={() => onReview(selected.sku)}>오늘의 할 일에서 검토 <ArrowRight size={16}/></button>}
      {dataset.kind === "hm" && <small className="catalog-note">H&M에는 실제 재고가 없습니다. 가상 재고는 시뮬레이션 상품에만 표시됩니다.{!selected.reviewable ? " 이 상품은 MD 판단용 표본 밖입니다." : ""}</small>}
    </section>{dataset.kind === "hm" && <PeerPanel datasetId={dataset.id} sku={selected.sku}/>}</div>}
  </>;
}
