import { useEffect, useMemo, useState } from "react";
import { Activity, ArrowRight, Database, LoaderCircle, TriangleAlert } from "lucide-react";
import { api } from "./api";
import type { WorkView } from "./App";
import FashionOptionCompare from "./FashionOptionCompare";
import FashionPlanningPanel from "./FashionPlanningPanel";
import type { FashionAnalysis, FashionCase, FashionDecision, FashionPlanDecision } from "./types";
import "./fashion.css";

const groups = [
  { id: "2026SS", label: "여름 잔여", question: "남은 재고를 어떤 순서로 소진할까?" },
  { id: "2026FW", label: "가을 신상", question: "출시 전 초도 물량과 일정은 준비됐나?" },
  { id: "2025FW", label: "작년 겨울 행사", question: "재발주 없이 얼마 동안 판매할 수 있나?" },
] as const;
const number = (value: number) => new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 }).format(value);
const won = (value: number) => `₩${number(value)}`;

export default function FashionPage({ view, onNavigate }: { view: WorkView; onNavigate: (view: WorkView) => void }) {
  const [caseData, setCaseData] = useState<FashionCase | null>(null);
  const [ready, setReady] = useState(false);
  const [group, setGroup] = useState<string>("2026SS");
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [decisions, setDecisions] = useState<FashionDecision[]>([]);
  const [planDecisions, setPlanDecisions] = useState<FashionPlanDecision[]>([]);
  const [notice, setNotice] = useState("");

  async function refresh() {
    try {
      const status = await api.fashionStatus();
      setReady(status.imported);
      if (status.imported) {
        const [analysis, nextDecisions, nextPlanDecisions] = await Promise.all([
          api.fashionAnalysis(), api.fashionDecisions(), api.fashionPlanDecisions(),
        ]);
        setCaseData(analysis);
        setDecisions(nextDecisions);
        setPlanDecisions(nextPlanDecisions);
      } else {
        setCaseData(null);
        setDecisions([]);
        setPlanDecisions([]);
      }
    } catch (err) { setError(err instanceof Error ? err.message : "사례를 불러오지 못했습니다."); }
  }
  useEffect(() => { void refresh(); }, [view]);

  async function importSample() {
    setBusy(true); setError("");
    try { await api.fashionImportSample(); await refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : "샘플을 연결하지 못했습니다."); }
    finally { setBusy(false); }
  }

  async function importSales(file?: File) {
    if (!file) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api.fashionImportSales(file);
      await refresh();
      setNotice(`${result.updated}개의 일별 판매 기록을 반영하고 마진을 다시 계산했습니다.`);
    } catch (err) { setError(err instanceof Error ? err.message : "판매 자료를 반영하지 못했습니다."); }
    finally { setBusy(false); }
  }

  const items = useMemo(() => caseData?.products.filter((item) => item.season_group === group) ?? [], [caseData, group]);
  const maxUnits30d = Math.max(1, ...items.map((item) => item.units_30d));
  const focus = items.find((item) => item.sku === selected) ?? items[0];
  const groupInfo = groups.find((item) => item.id === group)!;
  const seasonSummary = caseData?.summary_by_season[group];
  const attention = caseData?.products.filter((item) => item.risk !== "healthy") ?? [];
  const ranked = [...attention].sort((a, b) => {
    const rank = (item: FashionAnalysis) => item.risk === "out_of_stock" ? 0 : item.risk === "stockout_risk" ? 1 : item.risk === "overstock_risk" ? 2 : item.risk === "slow_moving" ? 3 : 4;
    return rank(a) - rank(b) || b.revenue_30d - a.revenue_30d;
  });
  const totalRevenue = caseData?.products.reduce((sum, item) => sum + item.revenue_30d, 0) ?? 0;
  const totalProfit = caseData?.products.reduce((sum, item) => sum + item.gross_margin_30d, 0) ?? 0;
  const totalUnits = caseData?.products.reduce((sum, item) => sum + item.units_30d, 0) ?? 0;

  function openProduct(groupId: string, sku: string) {
    setGroup(groupId);
    setSelected(sku);
    onNavigate("products");
    requestAnimationFrame(() => requestAnimationFrame(() => document.getElementById("fashion-product-detail")?.scrollIntoView({ behavior: "smooth", block: "start" })));
  }

  return <div className="fashion-page">
    <header className="fashion-work-header"><div><span className="section-kicker">MD DECISION LAB</span><h1>{view === "overview" ? "오늘의 할 일" : view === "products" ? "전체 상품" : view === "actions" ? "내 결정 기록" : "다음 시즌 기획"}</h1></div><span className="fashion-source-badge">합성 사례 데이터 · 기준일 2026-08-31</span></header>
    {error && <div className="error-banner"><TriangleAlert size={17}/>{error}</div>}
    {notice && <div className="notice-banner">{notice}</div>}
    {!ready && <section className="panel fashion-intro"><h2>상품 데이터 연결</h2><p>내장된 합성 의류 자료를 연결해 화면을 확인할 수 있습니다.</p><button className="button button-primary" disabled={busy} onClick={() => void importSample()}>{busy ? <LoaderCircle className="spin" size={17}/> : <Database size={17}/>} {busy ? "연결 중…" : "예시 데이터 연결"}</button></section>}
    {caseData && <>
      {view === "overview" && <>
        <div className="fashion-kpis fashion-work-kpis"><div><span>30일 매출</span><strong>{won(totalRevenue)}</strong></div><div><span>30일 매출총이익</span><strong>{won(totalProfit)}</strong></div><div><span>30일 판매</span><strong>{number(totalUnits)}개</strong></div><div><span>확인 필요</span><strong>{attention.length}개</strong></div></div>
        <section className="panel fashion-section"><div className="fashion-heading"><div><h2>우선 확인할 상품</h2></div><button type="button" className="button button-secondary" onClick={() => onNavigate("products")}>전체 상품 보기 <ArrowRight size={15}/></button></div><div className="table-scroll"><table className="data-table fashion-table"><thead><tr><th>상품</th><th>상태</th><th>30일 판매</th><th>재고 / 소진 예상</th><th>다음 검토</th></tr></thead><tbody>{ranked.slice(0, 10).map((item) => <tr key={item.sku}><td><button type="button" className="fashion-product-link" onClick={() => openProduct(item.season_group || "2026SS", item.sku)}><b>{item.name.replace(/^\[[^\]]+\]\s*/, "")}</b><small>{item.sku}</small></button></td><td>{item.risk_label}</td><td>{number(item.units_30d)}개</td><td>{number(item.stock_on_hand)}개<small>{item.days_of_cover == null ? "추정 불가" : `약 ${item.days_of_cover}일`}</small></td><td>{item.recommendation}</td></tr>)}</tbody></table></div></section>
      </>}
      {view === "products" && <>
      <div className="fashion-upload"><div><b>판매 기록</b><small>CSV 업로드 · sku, sale_date, units_sold, revenue</small></div><label className="button button-secondary upload-button">{busy ? "반영 중…" : "판매 CSV 올리기"}<input type="file" accept=".csv,text/csv" disabled={busy} onChange={(event) => { void importSales(event.target.files?.[0]); event.currentTarget.value = ""; }}/></label></div>
      <div className="fashion-group-tabs" role="tablist" aria-label="시즌별 상품">
        {groups.map((item) => <button key={item.id} role="tab" aria-selected={group === item.id} className={group === item.id ? "active" : ""} onClick={() => { setGroup(item.id); setSelected(null); }}><span>{item.label}</span><b>{caseData.products.filter((product) => product.season_group === item.id).length}개</b></button>)}
      </div>
      <section className="panel fashion-section">
        <div className="fashion-heading"><div><span className="section-kicker">{groupInfo.id} · MD QUESTION</span><h2>{groupInfo.question}</h2></div><small>판매 기록은 기준일 직전 30일 · 재고는 8월 31일 스냅샷</small></div>
        <div className="fashion-kpis"><div><span>현재 보유 원가</span><strong>{won(seasonSummary?.stock_cost_value ?? 0)}</strong><small>현재고 × 상품 원가의 합계</small></div><div><span>최근 30일 매출</span><strong>{won(seasonSummary?.revenue_30d ?? 0)}</strong><small>해당 시즌 상품의 합계</small></div><div><span>30일 매출총이익</span><strong>{won(seasonSummary?.gross_margin_30d ?? 0)}</strong><small>매출총이익률 {seasonSummary?.gross_margin_rate_30d_pct == null ? "계산 불가" : seasonSummary.gross_margin_rate_30d_pct + "%"}{seasonSummary?.margin_is_estimated ? " · 원가 기준 추정 포함" : ""}</small></div><div><span>우선 확인</span><strong>{seasonSummary?.attention_count ?? 0}개</strong><small>규칙 기반 검토 대상</small></div></div>
        <div className="table-scroll"><table className="data-table fashion-table"><thead><tr><th>상품</th><th>7일 / 30일 판매</th><th>전기 30일</th><th>재고 / 소진 예상</th><th>30일 매출총이익 / 마진율</th><th>다음 검토</th></tr></thead><tbody>{items.map((item) => <tr key={item.sku} className={focus?.sku === item.sku ? "selected-row" : ""}><td><button type="button" className="fashion-product-link" onClick={() => openProduct(group, item.sku)} aria-label={`${item.name} 판단 근거 보기`}><b>{item.name.replace(/^\[[^\]]+\]\s*/, "")}</b><small>{item.sku} · {item.category}</small></button></td><td>{number(item.units_7d)}개 / {number(item.units_30d)}개<div className="fashion-sales-bar" role="img" aria-label={`${item.name} 최근 30일 ${number(item.units_30d)}개 판매, 현재 상품군 최대 ${number(maxUnits30d)}개 기준`}><span style={{ width: `${item.units_30d / maxUnits30d * 100}%` }}/></div></td><td>{item.prior_30d_units == null ? "비교 불가" : `${number(item.prior_30d_units)}개`}{item.units_change_pct != null && <small>{item.units_change_pct > 0 ? "+" : ""}{item.units_change_pct}%</small>}</td><td>{number(item.stock_on_hand)}개<small>{item.days_of_cover == null ? "판매 속도 추정 불가" : `약 ${item.days_of_cover}일 판매분`}</small></td><td>{won(item.gross_margin_30d)}{item.margin_is_estimated ? "*" : ""}<small>{item.gross_margin_rate_30d_pct == null ? "계산 불가" : item.gross_margin_rate_30d_pct + "%"}</small></td><td><b>{item.recommendation}</b><ArrowRight size={14}/></td></tr>)}</tbody></table></div>
      </section>
      {focus && <section id="fashion-product-detail" className="panel fashion-evidence" aria-live="polite"><div className="fashion-heading"><div><span className="section-kicker">DECISION EVIDENCE</span><h2>{focus.name}</h2></div><span className={`risk-badge risk-${focus.risk}`}>{focus.risk_label}</span></div><div className="fashion-evidence-grid"><div><h3>왜 이 판단인가요?</h3><p>{focus.recommendation_reason}</p><ul><li>30일 {number(focus.units_30d)}개 · 최근 7일 {number(focus.units_7d)}개</li><li>적용한 판매 속도: {focus.demand_basis === "none" ? "계산 불가" : `${focus.demand_basis} 평균 ${focus.decision_daily_units}개/일`}</li><li>재고 {number(focus.stock_on_hand)}개 · 입고 예정 {number(focus.inbound_units)}개 · 리드타임 {focus.lead_time_days}일</li><li>재발주 {focus.reorderable ? "가능" : "불가"} · {focus.trend_note}</li></ul></div><div><h3>MD가 확인할 것</h3><p>{focus.planning_note || "상품 상태와 운영 조건을 확인하세요."}</p><p className="fashion-action">{focus.recommendation}</p>{focus.suggested_replenishment_units != null && <p>계산상 검토 수량: <b>{number(focus.suggested_replenishment_units)}개</b></p>}{focus.data_warnings.map((warning) => <small key={warning}>주의: {warning}</small>)}</div></div><div className="fashion-margin-summary"><span>현재 판매가 <b>{won(focus.unit_price)}</b></span><span>상품 원가 <b>{won(focus.unit_cost)}</b></span><span>원가 대비 이익률 <b>{focus.unit_markup_pct == null ? "계산 불가" : focus.unit_markup_pct + "%"}</b></span><span>30일 매출총이익 <b>{won(focus.gross_margin_30d)}{focus.margin_is_estimated ? "*" : ""}</b></span><span>30일 매출총이익률 <b>{focus.gross_margin_rate_30d_pct == null ? "계산 불가" : focus.gross_margin_rate_30d_pct + "%"}</b></span></div>{focus.margin_is_estimated && <small className="fashion-margin-note">* 판매 CSV에 매출총이익이 없어 현재 상품 원가로 계산한 추정값입니다.</small>}<FashionOptionCompare key={`${focus.sku}:${focus.unit_price}:${focus.unit_cost}:${focus.stock_on_hand}:${focus.inbound_units}:${focus.units_30d}:${focus.reorderable}`} item={focus} decisions={decisions} onDecisionSaved={refresh}/><details className="fashion-data-edit"><summary>상품 원본 값 수정하기</summary><ProductInputEditor key={focus.sku} item={focus} onSaved={refresh}/></details><p className="fashion-footnote"><Activity size={15}/> 이 판단은 입력값과 규칙에 따른 검토 제안입니다. 할인·추가 매입의 실제 성과는 측정하지 않았습니다.</p></section>}
      </>}
      {view === "actions" && <section className="panel fashion-section"><div className="fashion-heading"><div><h2>저장한 판단 {decisions.length + planDecisions.length}건</h2></div></div>{decisions.length + planDecisions.length === 0 ? <p className="fashion-empty-message">기록이 없습니다. 상품을 선택해 판단을 저장하세요.</p> : <div className="fashion-record-list">{[...decisions.map((item) => ({ key: `action-${item.id}`, sku: item.sku, label: item.chosen_option === "hold" ? "조치 보류" : item.chosen_option === "A" ? "현재가 유지" : "변경안 검토", rationale: item.rationale, date: item.created_at, planning: false })), ...planDecisions.map((item) => ({ key: `plan-${item.id}`, sku: item.sku, label: "다음 시즌 물량 검토", rationale: item.rationale, date: item.created_at, planning: true }))].sort((a, b) => b.date.localeCompare(a.date)).map((item) => <article className="fashion-record" key={item.key}><div><b>{item.label}</b><small>{item.sku} · {item.date ? new Date(item.date).toLocaleDateString("ko-KR") : ""}</small></div><p>{item.rationale}</p><button type="button" className="button button-secondary" onClick={() => item.planning ? onNavigate("planning") : openProduct(caseData.products.find((product) => product.sku === item.sku)?.season_group || "2026SS", item.sku)}>관련 상품 보기 <ArrowRight size={14}/></button></article>)}</div>}</section>}
      {view === "planning" && <FashionPlanningPanel />}
    </>}
  </div>;
}

function ProductInputEditor({ item, onSaved }: { item: FashionAnalysis; onSaved: () => Promise<void> }) {
  const [stock, setStock] = useState(item.stock_on_hand);
  const [inbound, setInbound] = useState(item.inbound_units);
  const [price, setPrice] = useState(item.unit_price);
  const [cost, setCost] = useState(item.unit_cost);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function save() {
    setBusy(true); setMessage("");
    try {
      await api.fashionUpdateProduct(item.sku, { stock_on_hand: stock, inbound_units: inbound, unit_price: price, unit_cost: cost });
      await onSaved();
      setMessage("입력값을 저장하고 재고 판단·현재 상품 마진을 다시 계산했습니다.");
    } catch (err) { setMessage(err instanceof Error ? err.message : "입력값을 저장하지 못했습니다."); }
    finally { setBusy(false); }
  }
  return <div className="fashion-editor"><div><h3>현재 상품 값 수정</h3><p>저장하면 재고 판단과 현재 판매가 기준 마진이 다시 계산됩니다. 과거 매출총이익은 당시 판매 CSV를 정정할 때만 바뀝니다.</p></div><div className="fashion-editor-fields"><label>8/31 현재고<input type="number" min="0" step="1" value={stock} onChange={(event) => setStock(Number(event.target.value))}/></label><label>입고 예정<input type="number" min="0" step="1" value={inbound} onChange={(event) => setInbound(Number(event.target.value))}/></label><label>현재 판매가<input type="number" min="0" step="1" value={price} onChange={(event) => setPrice(Number(event.target.value))}/></label><label>상품 원가<input type="number" min="0" step="1" value={cost} onChange={(event) => setCost(Number(event.target.value))}/></label></div><button className="button button-secondary" disabled={busy || stock < 0 || inbound < 0 || price < 0 || cost < 0 || !Number.isInteger(stock) || !Number.isInteger(inbound)} onClick={() => void save()}>{busy ? "저장 중…" : "입력값 적용"}</button>{message && <small>{message}</small>}</div>;
}


