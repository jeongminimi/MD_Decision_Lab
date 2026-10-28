import { useCallback, useEffect, useState } from "react";
import { ArrowDownToLine, ArrowUpRight, Database, FileUp, LoaderCircle, RefreshCw, TriangleAlert } from "lucide-react";
import { api } from "./api";
import type { OlistComparison, OlistScenarioDetail, OlistScenarioSummary, OlistStatus, OlistTopProduct, ProductAnalysis, Risk } from "./types";

const brl = (value: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(value);
const number = (value: number) => new Intl.NumberFormat("ko-KR").format(value);
const riskName: Record<Risk, string> = { out_of_stock: "재고 소진", data_insufficient: "판매 데이터 부족", stockout_risk: "품절 위험", overstock_risk: "과잉재고 위험", slow_moving: "판매 둔화", healthy: "안정" };
const categoryNames: Record<string, string> = { telephony: "휴대폰·통신", food: "식품", health_beauty: "뷰티·건강", bed_bath_table: "침구·생활", computers_accessories: "컴퓨터·주변기기", watches_gifts: "시계·선물", sports_leisure: "스포츠·레저", housewares: "생활용품", fashion_bags_accessories: "패션 잡화", consoles_games: "게임기·게임", perfumery: "향수" };
const categoryLabel = (category: string) => categoryNames[category] ?? category.replace(/_/g, " ");
const displayProduct = (item: Pick<ProductAnalysis, "category" | "sku">) => `${categoryLabel(item.category)} 상품 · ${item.sku.slice(6, 12)}`;
const displayComparedProduct = (name: string, sku: string) => `${categoryLabel(name.split(" · ")[0])} 상품 · ${sku.slice(6, 12)}`;
function plainRiskReason(item: ProductAnalysis) {
  if (item.risk === "out_of_stock") return "입력한 재고가 0개예요. 실제 재고가 있는지 먼저 확인하세요.";
  if (item.risk === "stockout_risk") return `지금 판매 속도라면 약 ${item.days_of_cover ?? "?"}일 뒤 재고가 부족할 수 있어요.`;
  if (item.risk === "overstock_risk") return "판매 속도에 비해 재고가 오래 남을 가능성이 있어요.";
  if (item.risk === "data_insufficient") return item.units_30d > 0 && item.units_7d === 0
    ? `최근 30일에는 ${number(item.units_30d)}개 팔렸지만 최근 7일은 0개예요. 이유를 확인하세요.`
    : "최근 판매 흐름을 확인하기 전에는 매입 수량을 추천하지 않아요.";
  return "판매 속도가 느려 상품 노출 방법을 다시 볼 만해요.";
}

export default function OlistPage() {
  const [status, setStatus] = useState<OlistStatus | null>(null);
  const [top, setTop] = useState<OlistTopProduct[]>([]);
  const [scenarios, setScenarios] = useState<OlistScenarioSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [compareId, setCompareId] = useState<number | null>(null);
  const [detail, setDetail] = useState<OlistScenarioDetail | null>(null);
  const [comparison, setComparison] = useState<OlistComparison | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    const nextStatus = await api.olistStatus();
    setStatus(nextStatus);
    if (nextStatus.imported) {
      const [nextTop, nextScenarios] = await Promise.all([api.olistTopProducts(), api.olistScenarios()]);
      setTop(nextTop.products);
      setScenarios(nextScenarios);
      setSelectedId((previous) => previous ?? nextScenarios[0]?.id ?? null);
      setCompareId((previous) => previous ?? nextScenarios[1]?.id ?? null);
    }
  }, []);

  useEffect(() => { void refresh().catch((err) => setError(err instanceof Error ? err.message : "데이터를 불러오지 못했습니다.")); }, [refresh]);
  useEffect(() => {
    let active = true;
    setDetail(null);
    if (selectedId === null) return;
    void api.olistScenario(selectedId)
      .then((result) => { if (active) setDetail(result); })
      .catch((err) => { if (active) setError(err instanceof Error ? err.message : "시나리오를 불러오지 못했습니다."); });
    return () => { active = false; };
  }, [selectedId]);
  useEffect(() => {
    if (selectedId === null || compareId === null || selectedId === compareId) { setComparison(null); return; }
    let active = true;
    setComparison(null);
    void api.olistCompare(compareId, selectedId)
      .then((result) => { if (active) setComparison(result); })
      .catch((err) => { if (active) setError(err instanceof Error ? err.message : "시나리오를 비교하지 못했습니다."); });
    return () => { active = false; };
  }, [selectedId, compareId]);

  async function importDemand() {
    setBusy(true); setError("");
    try { const result = await api.olistImport(); setNotice(`Olist 주문 ${number(result.order_count ?? 0)}건의 상품 판매 자료를 연결했습니다.`); await refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : "원본 데이터를 가져오지 못했습니다."); }
    finally { setBusy(false); }
  }

  async function downloadTemplate() {
    setError("");
    try {
      const blob = await api.olistTemplate();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = "olist_scenario_template.csv"; link.click();
      URL.revokeObjectURL(url);
    } catch (err) { setError(err instanceof Error ? err.message : "양식을 받지 못했습니다."); }
  }

  async function downloadAnalysis() {
    if (selectedId === null) return;
    setError("");
    try {
      const blob = await api.olistExport(selectedId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = `olist_scenario_${selectedId}.csv`; link.click();
      URL.revokeObjectURL(url);
    } catch (err) { setError(err instanceof Error ? err.message : "분석 CSV를 받지 못했습니다."); }
  }

  async function uploadScenario(file?: File) {
    if (!file) return;
    setBusy(true); setError("");
    try {
      const created = await api.olistImportScenario(file);
      setNotice(`${created.name}: 상품 ${created.product_count}개의 재고 가정을 저장했습니다.`);
      await refresh();
      setSelectedId(created.scenario_id);
    } catch (err) { setError(err instanceof Error ? err.message : "시나리오를 저장하지 못했습니다."); }
    finally { setBusy(false); }
  }

  const attention = detail?.products.filter((item) => item.risk !== "healthy") ?? [];
  const urgentCount = detail?.products.filter((item) => ["out_of_stock", "stockout_risk"].includes(item.risk)).length ?? 0;

  return <div className="olist-page">
    <div className="page-heading editorial-hero olist-hero"><div className="hero-copy"><div className="eyebrow"><span className="eyebrow-line"/> SALES & STOCK <span className="demo-tag">과거 판매로 연습하기</span></div><h1>판매 흐름을 읽고,<br/>다음 재고 결정을 준비해요.</h1><p>브라질 온라인 상점의 실제 과거 판매 기록에 직접 입력한 가상 재고를 적용해봅니다.</p></div><div className="hero-orb" aria-hidden="true"><span className="hero-orb-core"/></div></div>
    {error && <div className="error-banner"><TriangleAlert size={16}/><span>{error}</span><button onClick={() => setError("")}>닫기</button></div>}
    {notice && <div className="notice-banner"><span>{notice}</span><button onClick={() => setNotice("")}>닫기</button></div>}

    {detail && <section className="olist-spotlight" aria-labelledby="olist-spotlight-title"><div className="editorial-section-heading"><div><span className="section-kicker">SCENARIO REVIEW</span><h2 id="olist-spotlight-title">이 재고 가정에서 먼저 볼 상품</h2><p>{detail.as_of_date} 기준 · {detail.name} · 품절 또는 품절 위험 {urgentCount}개</p></div><span className="priority-count">{attention.length}개 확인</span></div><div className="olist-spotlight-grid">{attention.length ? attention.slice(0, 3).map((item) => <article className={`olist-action-card priority-${item.risk}`} key={item.product_id}><span className="olist-card-eyebrow">{displayProduct(item)}</span><span className={`risk-badge risk-${item.risk}`}>{item.risk_label}</span><h3>{plainRiskReason(item)}</h3><p><b>다음 검토</b> {item.recommendation}</p><small>최근 30일 실제 판매 {number(item.units_30d)}개 · 직접 입력한 재고 {number(item.stock_on_hand)}개</small><a href="#olist-evidence">숫자 근거 보기 <ArrowUpRight size={14}/></a></article>) : <div className="priority-empty"><Database size={25}/><strong>현재 가정에서 긴급한 경고는 없어요.</strong><p>아래 상세 수치에서 모든 상품을 검토할 수 있습니다.</p></div>}</div><div className="evidence-legend"><span><i className="legend-observed"/>판매 수량·매출은 실제 과거 기록</span><span><i className="legend-assumed"/>재고·원가는 직접 입력한 가정</span><span><i className="legend-estimated"/>이익은 가정 원가로 계산한 추정</span></div></section>}

    <section className="panel olist-source">
      <div className="olist-section-title"><div><Database size={19}/><div><h2>1. 실제 판매 기록</h2><p>배송이 완료된 과거 주문을 상품별·날짜별로 모았습니다.</p></div></div>{status?.imported && <span className="olist-ready">연결됨</span>}</div>
      {!status?.imported ? <div className="olist-empty"><p>동일한 작업 폴더에 있는 Olist 원본 저장소의 압축 CSV를 읽습니다. 첫 연결에는 시간이 조금 걸릴 수 있습니다.</p><button className="button button-primary" disabled={busy} onClick={() => void importDemand()}>{busy ? <LoaderCircle className="spin" size={15}/> : <Database size={15}/>} Olist 데이터 연결</button></div> : <>
        <div className="olist-facts"><span>기간 <b>{status.period_start} ~ {status.period_end}</b></span><span>배송 완료 주문 <b>{number(status.order_count ?? 0)}건</b></span><span>상품 항목 <b>{number(status.item_count ?? 0)}건</b></span><span>상품 <b>{number(status.product_count ?? 0)}개</b></span></div>
        <p className="olist-source-note">매출은 배송비를 제외한 상품 가격 합계이며 통화는 브라질 헤알(BRL)입니다. 원본 식별값: {status.source_revision}</p>
      </>}
    </section>

    {status?.imported && <>
      <section className="panel olist-simulation"><div className="olist-section-title"><div><FileUp size={19}/><div><h2>2. 재고를 가정해보기</h2><p>양식에 현재 재고, 입고 예정, 발주 후 입고까지 걸리는 날, 목표 재고 기간과 원가를 입력하세요.</p></div></div></div>
        <div className="olist-buttons"><button className="button button-secondary" onClick={() => void downloadTemplate()}><ArrowDownToLine size={15}/> 입력 양식 받기</button><label className="button button-primary upload-button">{busy ? "처리 중…" : "작성한 파일 올리기"}<input type="file" accept=".csv,text/csv" onChange={(event) => { void uploadScenario(event.target.files?.[0]); event.currentTarget.value = ""; }}/></label></div>
        <p className="olist-source-note">빈 칸을 채워 올리면 새 시나리오로 저장됩니다. 기존 Olist 판매 기록과 데모 상품 자료는 바뀌지 않습니다.</p>
      </section>

      {scenarios.length > 0 && <section id="olist-evidence" className="panel olist-results"><div className="olist-section-title"><div><RefreshCw size={19}/><div><h2>3. 상품별 판단 근거</h2><p>적용한 재고 가정을 고르고, 숫자와 추천 이유를 확인하세요.</p></div></div><select aria-label="재고 가정 선택" value={selectedId ?? ""} onChange={(event) => { const id = Number(event.target.value); setSelectedId(id); if (compareId === id) setCompareId(scenarios.find((item) => item.id !== id)?.id ?? null); }}>{scenarios.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.as_of_date} · {item.product_count}개</option>)}</select></div>
        <div className="olist-buttons"><button className="button button-secondary" disabled={selectedId === null} onClick={() => void downloadAnalysis()}><ArrowDownToLine size={15}/> 분석 결과 저장하기</button></div>
        {detail && <><div className="olist-provenance"><span><b>판매·매출</b> Olist 주문 실측</span><span><b>재고·원가</b> 사용자가 입력한 가정</span><span><b>매출총이익</b> 가정 원가로 계산한 추정</span></div><div className="table-scroll"><table className="data-table olist-table"><thead><tr><th>상품</th><th>30일 판매</th><th>30일 매출 (BRL)</th><th>가정 재고</th><th>재고 커버</th><th>판단</th></tr></thead><tbody>{detail.products.map((item: ProductAnalysis) => <tr key={item.product_id}><td><div className="olist-product"><b>{displayProduct(item)}</b><small>{item.sku}</small></div></td><td>{number(item.units_30d)}개</td><td>{brl(item.revenue_30d)}</td><td>{number(item.stock_on_hand)}개</td><td>{item.days_of_cover == null ? "계산 불가" : `${item.days_of_cover}일`}</td><td><span className={`risk-badge risk-${item.risk}`}>{item.risk_label}</span><details className="olist-reason"><summary>근거 보기 <ArrowUpRight size={12}/></summary><p>7일 {number(item.units_7d)}개 ({item.avg_daily_7d.toFixed(2)}개/일) · 30일 {number(item.units_30d)}개 ({item.avg_daily_units.toFixed(2)}개/일)</p><p>판단에 사용한 속도: {item.demand_basis === "none" ? "계산 불가" : `${item.demand_basis === "7d" ? "최근 7일" : "최근 30일"} · ${item.decision_daily_units.toFixed(2)}개/일`}</p><p>{item.demand_explanation}</p>{item.data_warnings.map((warning) => <p key={warning}>주의: {warning}</p>)}<p>{item.recommendation_reason}</p><p>추천: {item.recommendation}{item.suggested_replenishment_units != null ? ` · 추가 매입 검토 ${number(item.suggested_replenishment_units)}개` : ""}</p><p>가정 원가 기준 매출총이익: {brl(item.gross_margin_30d)}</p></details></td></tr>)}</tbody></table></div></>}
      </section>}

      {scenarios.length > 1 && <section className="panel olist-compare"><div className="olist-section-title"><div><RefreshCw size={19}/><div><h2>4. 두 재고 가정 비교</h2><p>과거 판매는 그대로 두고 입력한 재고만 바꿨을 때 판단이 어떻게 달라지는지 봅니다.</p></div></div><select aria-label="비교 기준 재고 가정" value={compareId ?? ""} onChange={(event) => setCompareId(Number(event.target.value))}>{scenarios.filter((item) => item.id !== selectedId).map((item) => <option key={item.id} value={item.id}>기준: {item.name}</option>)}</select></div>
        {comparison && <><p className="olist-source-note">{comparison.interpretation}</p><div className="olist-compare-grid"><div><span>품절·품절 위험 상품</span><strong>{comparison.baseline.stockout_count} → {comparison.candidate.stockout_count}개</strong></div><div><span>과잉재고 위험 상품</span><strong>{comparison.baseline.overstock_count} → {comparison.candidate.overstock_count}개</strong></div><div><span>가정 재고 가치</span><strong>{brl(comparison.baseline.stock_value)} → {brl(comparison.candidate.stock_value)}</strong></div><div><span>추가 매입 검토 수량</span><strong>{number(comparison.baseline.suggested_replenishment_units)} → {number(comparison.candidate.suggested_replenishment_units)}개</strong></div></div><div className="table-scroll"><table className="data-table"><thead><tr><th>상품</th><th>기준 재고</th><th>선택 재고</th><th>기준 커버</th><th>선택 커버</th><th>판단 변화</th></tr></thead><tbody>{comparison.products.map((item) => <tr key={item.sku}><td>{displayComparedProduct(item.name, item.sku)}</td><td>{item.baseline_stock}개</td><td>{item.candidate_stock}개</td><td>{item.baseline_cover == null ? "계산 불가" : `${item.baseline_cover}일`}</td><td>{item.candidate_cover == null ? "계산 불가" : `${item.candidate_cover}일`}</td><td>{riskName[item.baseline_risk]} → {riskName[item.candidate_risk]}</td></tr>)}</tbody></table></div></>}
      </section>}

      <section className="panel olist-top"><div className="olist-section-title"><div><Database size={19}/><div><h2>참고: 최근 30일 판매 상위 상품</h2><p>{status.period_end} 기준 Olist 실측 수요입니다. 재고 위험은 시나리오를 입력한 뒤 계산합니다.</p></div></div></div><div className="table-scroll"><table className="data-table"><thead><tr><th>상품</th><th>상품 코드</th><th>판매 수량</th><th>상품 매출</th></tr></thead><tbody>{top.slice(0, 10).map((item) => <tr key={item.id}><td>{displayProduct(item)}</td><td>{item.sku}</td><td>{number(item.units_30d)}개</td><td>{brl(item.revenue_30d)}</td></tr>)}</tbody></table></div></section>
    </>}
  </div>;
}
