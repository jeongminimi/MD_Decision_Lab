import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import Papa from "papaparse";
import {
  Activity, ArrowDownRight, ArrowUpRight, ArrowUpRightFromSquare, Boxes, Check, ChevronDown,
  CircleAlert, Clock3, Database, FileUp, LayoutDashboard, LoaderCircle, Menu, MoreHorizontal,
  PackageCheck, Plus, Search, Sparkles, TrendingDown, TrendingUp, X,
} from "lucide-react";
import { api } from "./api";
import OlistPage from "./OlistPage";
import FashionPage from "./FashionPage";
import "./outcomes.css";
import type { ActionOutcome, ActionRecord, ActionType, DashboardSummary, ProductAnalysis, Risk } from "./types";

type Page = "overview" | "products" | "actions" | "olist" | "fashion";

const riskNames: Record<Risk, string> = {
  out_of_stock: "재고 소진", data_insufficient: "데이터 확인", stockout_risk: "품절 위험",
  overstock_risk: "과잉재고 위험", slow_moving: "판매 둔화", healthy: "안정",
};
const actionNames: Record<ActionType, string> = {
  replenish: "추가 매입 검토", promotion: "프로모션 검토", live_exposure: "라이브 노출 검토",
  content_test: "콘텐츠 테스트", monitor: "모니터링",
};
const actionForRisk: Record<Risk, ActionType> = {
  out_of_stock: "replenish", data_insufficient: "monitor", stockout_risk: "replenish",
  overstock_risk: "promotion", slow_moving: "live_exposure", healthy: "monitor",
};

const money = (value: number) => new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 }).format(value);
const shortMoney = (value: number) => value >= 100_000_000 ? `${(value / 100_000_000).toFixed(1)}억` : value >= 10_000 ? `${(value / 10_000).toFixed(0)}만` : money(value);
const coverText = (value: number | null) => value == null ? "계산 불가" : `${value.toFixed(1)}일`;
const priorityOrder: Record<Risk, number> = { out_of_stock: 0, stockout_risk: 1, overstock_risk: 2, data_insufficient: 3, slow_moving: 4, healthy: 5 };

function priorityReason(item: ProductAnalysis) {
  if (item.risk === "out_of_stock") return "지금 판매할 수 있는 재고가 없어요.";
  if (item.risk === "stockout_risk") return `현재 판매 속도라면 재고가 약 ${coverText(item.days_of_cover)} 뒤 부족해질 수 있어요.`;
  if (item.risk === "overstock_risk") return `입고 예정까지 포함한 재고가 약 ${coverText(item.cover_including_inbound)} 판매분이에요.`;
  if (item.risk === "data_insufficient") return "최근 판매 기록을 먼저 확인해야 해요.";
  return "판매 속도에 비해 재고가 오래 남을 수 있어요.";
}

function App() {
  const [page, setPage] = useState<Page>("fashion");
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [products, setProducts] = useState<ProductAnalysis[]>([]);
  const [actions, setActions] = useState<ActionRecord[]>([]);
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("all");
  const [selected, setSelected] = useState<ProductAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [actionNote, setActionNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextSummary, nextProducts, nextActions] = await Promise.all([
        api.dashboard(), api.products(search, riskFilter), api.actions(),
      ]);
      setSummary(nextSummary);
      setProducts(nextProducts);
      setActions(nextActions);
      setSelected((previous) => previous ? nextProducts.find((item) => item.product_id === previous.product_id) || null : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [search, riskFilter]);

  useEffect(() => { void refresh(); }, [refresh]);

  const attentionProducts = useMemo(() => products.filter((item) => ["out_of_stock", "stockout_risk", "overstock_risk"].includes(item.risk)), [products]);
  const priorityProducts = useMemo(() => products.filter((item) => item.risk !== "healthy").sort((a, b) => priorityOrder[a.risk] - priorityOrder[b.risk]).slice(0, 3), [products]);

  async function saveAction(product: ProductAnalysis, actionType = actionForRisk[product.risk]) {
    setBusy(true);
    try {
      await api.createAction(product.product_id, actionType, actionNote.trim());
      setActionNote("");
      setNotice(`${product.name} · ${actionNames[actionType]} 기록을 저장했습니다.`);
      await refresh();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "조치를 저장하지 못했습니다.");
    } finally { setBusy(false); }
  }

  async function completeAction(action: ActionRecord) {
    try {
      await api.completeAction(action.id);
      setNotice("조치 상태를 완료로 변경했습니다. 재고·매출 데이터는 자동으로 바뀌지 않습니다.");
      await refresh();
    } catch (err) { setNotice(err instanceof Error ? err.message : "상태를 변경하지 못했습니다."); }
  }

  async function importFile(file?: File) {
    if (!file) return;
    setBusy(true);
    setNotice("");
    try {
      const result = await api.importSales(file);
      setNotice(`${result.imported}행 반영 · ${result.rejected}행 제외${result.messages.length ? ` — ${result.messages[0]}` : ""}`);
      await refresh();
    } catch (err) { setNotice(err instanceof Error ? err.message : "CSV를 가져오지 못했습니다."); }
    finally { setBusy(false); }
  }

  async function importCatalogFile(file?: File) {
    if (!file) return;
    setBusy(true);
    setNotice("");
    try {
      const result = await api.importProducts(file);
      setNotice(`상품 ${result.imported}행 반영 · ${result.rejected}행 제외${result.messages.length ? ` — ${result.messages[0]}` : ""}`);
      await refresh();
    } catch (err) { setNotice(err instanceof Error ? err.message : "상품 CSV를 가져오지 못했습니다."); }
    finally { setBusy(false); }
  }

  function parseLocalCsv(file?: File) {
    if (!file) return;
    Papa.parse(file, { complete: () => void importFile(file), error: () => setNotice("CSV 파일을 읽지 못했습니다.") });
  }

  return (
    <div className="app-shell">
      {mobileNavOpen && <button className="mobile-nav-backdrop" aria-label="메뉴 닫기" onClick={() => setMobileNavOpen(false)}/>}
      <aside className={`sidebar ${mobileNavOpen ? "mobile-open" : ""}`}>
        <div className="brand-lockup"><div className="brand-mark">MD</div><div><strong>Decision Lab</strong><span>COMMERCE INTELLIGENCE</span></div></div>
        <div className="workspace-label">WORKSPACE <ChevronDown size={14} /></div>
        <div className="workspace-card"><span className="workspace-dot"/><div><b>의류 MD 의사결정</b><small>포트폴리오 사례 · 가상 데이터</small></div><MoreHorizontal size={17}/></div>
        <nav className="side-nav">
          <p>MAIN CASE</p>
          <button className={page === "fashion" ? "active" : ""} onClick={() => { setPage("fashion"); setMobileNavOpen(false); }}><Boxes size={17}/> 의류 MD 사례 <span className="new-pill">MAIN</span></button>
          <p className="nav-spaced">연습 · 확장</p>
          <button className={page === "olist" ? "active" : ""} onClick={() => { setPage("olist"); setMobileNavOpen(false); }}><Database size={17}/> Olist 데이터 연습</button>
          <p className="nav-spaced">기존 데모</p>
          <button className={page === "overview" ? "active" : ""} onClick={() => { setPage("overview"); setSearch(""); setRiskFilter("all"); setMobileNavOpen(false); }}><LayoutDashboard size={17}/> 오늘의 할 일</button>
          <button className={page === "products" ? "active" : ""} onClick={() => { setPage("products"); setMobileNavOpen(false); }}><Boxes size={17}/> 전체 상품 <span className="nav-count">{summary?.product_count ?? "—"}</span></button>
          <button className={page === "actions" ? "active" : ""} onClick={() => { setPage("actions"); setMobileNavOpen(false); }}><Activity size={17}/> 내 결정 기록 <span className="nav-count">{actions.length || "—"}</span></button>
        </nav>
        <div className="sidebar-bottom"><div className="help-card"><div className="help-icon"><Sparkles size={15}/></div><b>MD의 판단을 돕습니다</b><span>추천 근거를 확인하고<br/>실행은 직접 결정하세요.</span></div><div className="user-row"><div className="avatar">JM</div><div><b>MD 매니저</b><small>로컬 포트폴리오 사례</small></div><MoreHorizontal size={18}/></div></div>
      </aside>

      <main className="main-area">
        <header className="topbar"><button className="mobile-menu" aria-label="메뉴 열기" aria-expanded={mobileNavOpen} onClick={() => setMobileNavOpen((open) => !open)}><Menu size={20}/></button><div className="breadcrumbs"><span>MD Decision Lab</span><b>/</b><strong>{page === "overview" ? "오늘의 할 일" : page === "products" ? "전체 상품" : page === "actions" ? "내 결정 기록" : page === "fashion" ? "의류 MD 사례" : "Olist 데이터 연습"}</strong></div><div className="top-actions"><span className="live-status"><i/> DB 연결됨</span><button className="icon-button" aria-label="알림"><CircleAlert size={18}/><i className="notification-dot"/></button><div className="top-avatar">J</div></div></header>

        <div className="content-wrap">
          {error && <div className="error-banner"><CircleAlert size={17}/>{error}<button onClick={() => void refresh()}>다시 시도</button></div>}
          {notice && <div className="notice-banner"><Check size={16}/><span>{notice}</span><button onClick={() => setNotice("")}><X size={15}/></button></div>}

          {page !== "olist" && page !== "fashion" && <section className={`page-heading ${page === "overview" ? "editorial-hero" : "editorial-subheading"}`}><div className="hero-copy"><div className="eyebrow"><span className="eyebrow-line"/> MD DECISION LAB <span className="demo-tag">가상 매장 예시</span></div><h1>{page === "overview" ? <>오늘은 어떤 상품부터<br/>살펴볼까요?</> : page === "products" ? "상품을 하나씩 살펴봐요" : "검토한 결정을 모아봤어요"}</h1><p>{page === "overview" ? "판매와 재고를 함께 보고, 지금 확인할 일부터 차근차근 정리해요." : page === "products" ? "상품별 상태와 추천 이유를 확인하고 필요한 조치를 직접 결정하세요." : "기록한 조치와 이후 자료를 함께 확인하세요. 변화가 조치의 효과를 증명하지는 않습니다."}</p></div>{page === "overview" && <div className="hero-orb" aria-hidden="true"><span className="hero-orb-core"/></div>}<div className="heading-actions"><label className="button button-secondary upload-button"><FileUp size={16}/>{busy ? "처리 중…" : "상품 자료 올리기"}<input type="file" accept=".csv,text/csv" onChange={(e) => { void importCatalogFile(e.target.files?.[0]); e.currentTarget.value = ""; }} /></label><label className="button button-secondary upload-button"><FileUp size={16}/>{busy ? "처리 중…" : "판매 자료 올리기"}<input type="file" accept=".csv,text/csv" onChange={(e) => { parseLocalCsv(e.target.files?.[0]); e.currentTarget.value = ""; }} /></label><button className="button button-primary" onClick={() => void refresh()}><Activity size={16}/> 새로고침</button></div></section>}

          {(page === "overview" || page === "products") && <>
            {page === "overview" && <section className="priority-section" aria-labelledby="priority-title"><div className="editorial-section-heading"><div><span className="section-kicker">YOUR NEXT MOVE</span><h2 id="priority-title">먼저 확인할 상품</h2><p>숫자보다 먼저, 왜 살펴봐야 하는지와 다음 행동을 보여드려요.</p></div><span className="priority-count">{priorityProducts.length}개 표시</span></div><div className="priority-grid">{priorityProducts.length ? priorityProducts.map((item, index) => <button className={`priority-card priority-${item.risk}`} key={item.product_id} onClick={() => setSelected(item)}><span className="priority-card-top"><span>0{index + 1} · {item.category}</span><RiskBadge risk={item.risk}/></span><strong>{item.name}</strong><span className="priority-reason">{priorityReason(item)}</span><span className="priority-action"><span>다음 검토</span><b>{item.recommendation}</b><ArrowUpRight size={18}/></span></button>) : <div className="priority-empty"><PackageCheck size={26}/><strong>지금 급히 확인할 상품은 없어요.</strong><p>전체 상품의 판매 흐름은 아래 표에서 살펴볼 수 있습니다.</p></div>}</div></section>}
            <section className="metric-grid">
              <MetricCard label="30일 매출" value={summary ? `₩${shortMoney(summary.revenue_30d)}` : "—"} change="최근 30일 수집 데이터" icon={<TrendingUp size={17}/>} tone="green" loading={loading}/>
              <MetricCard label="30일 매출총이익" value={summary ? `₩${shortMoney(summary.gross_margin_30d)}` : "—"} change={summary?.gross_margin_rate_30d_pct == null ? "매출 없음" : "매출총이익률 " + summary.gross_margin_rate_30d_pct + "% · 추정 포함"} icon={<ArrowUpRight size={17}/>} tone="purple" loading={loading}/>
              <MetricCard label="판매 수량" value={summary ? `${money(summary.units_30d)}개` : "—"} change="등록된 상품 합계" icon={<PackageCheck size={17}/>} tone="blue" loading={loading}/>
              <MetricCard label="확인 필요" value={summary ? `${summary.attention_count}개` : "—"} change="품절 · 품절 위험 · 과잉재고" icon={<CircleAlert size={17}/>} tone="orange" loading={loading}/>
            </section>

            {page === "overview" && <div className="data-context"><Sparkles size={17}/><span>이 화면은 <b>연습용 가상 매장</b>입니다. 추천을 확인한 뒤 실제 발주나 할인은 직접 결정하세요.</span><button onClick={() => { setPage("products"); setSearch(""); setRiskFilter("all"); }}>모든 상품 보기 <ArrowUpRightFromSquare size={15}/></button></div>}

            <section className="panel product-panel">
              <div className="panel-heading"><div><h2>{page === "overview" ? "우선 확인할 상품" : "전체 상품"}</h2><p>{page === "overview" ? "재고 판단 기준과 다음 조치를 검토하세요." : "상품을 선택해 분석 근거와 기록을 확인하세요."}</p></div><div className="table-tools"><div className="search-box"><Search size={15}/><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="상품명, SKU 검색"/></div><select value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)} aria-label="위험 필터"><option value="all">모든 상태</option><option value="out_of_stock">재고 소진</option><option value="stockout_risk">품절 위험</option><option value="overstock_risk">과잉재고 위험</option><option value="slow_moving">판매 둔화</option><option value="data_insufficient">데이터 확인</option><option value="healthy">안정</option></select></div></div>
              <ProductTable items={page === "overview" ? attentionProducts : products} loading={loading} selectedId={selected?.product_id} onSelect={setSelected}/>
              <div className="table-footer"><span>합성 데모 데이터 · 매출 효과를 검증한 실적이 아닙니다.</span><button onClick={() => { setPage("products"); setSearch(""); setRiskFilter("all"); }}>상품 목록 전체 보기 <ArrowUpRight size={14}/></button></div>
            </section>
          </>}

          {page === "actions" && <section className="panel action-panel"><div className="panel-heading"><div><h2>최근 조치</h2><p>시스템 추천과 사람이 선택한 실행을 구분해 기록합니다.</p></div></div><ActionTable actions={actions} onComplete={(item) => void completeAction(item)}/></section>}
          {page === "olist" && <OlistPage/>}
          {page === "fashion" && <FashionPage/>}

          <footer className="page-footer"><span>MD Decision Lab <b>·</b> Local portfolio prototype</span><span><i/> SQLite 저장 중 <b>·</b> 규칙 기반 분석 v0.1</span></footer>
        </div>
      </main>

      {selected && <div className="drawer-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setSelected(null); }}><aside className="detail-drawer"><div className="drawer-top"><div><span className="eyebrow">PRODUCT REVIEW</span><h2>{selected.name}</h2><span className="drawer-sku">{selected.sku} · {selected.category}</span></div><button className="icon-button" onClick={() => setSelected(null)}><X size={18}/></button></div><RiskBadge risk={selected.risk}/><div className="recommendation-card"><span className="rec-label"><Sparkles size={14}/> 추천 조치</span><strong>{selected.recommendation}</strong><p>{selected.recommendation_reason}</p>{selected.suggested_replenishment_units != null && <div className="suggested-qty">참고 수량 <b>{money(selected.suggested_replenishment_units)}개</b><small>목표 보유일 기준의 계산값이며 매입 권고 확정값이 아닙니다.</small></div>}</div><div className="drawer-metrics"><MiniMetric label="현재고" value={`${money(selected.stock_on_hand)}개`}/><MiniMetric label="입고 예정" value={`${money(selected.inbound_units)}개`}/><MiniMetric label="30일 판매" value={`${money(selected.units_30d)}개`}/><MiniMetric label="재고 커버리지" value={coverText(selected.days_of_cover)}/></div><div className="drawer-section"><h3>판단 기준</h3><div className="rule-line"><span>최근 7일 평균 판매</span><b>{selected.avg_daily_7d.toFixed(2)}개 / 일</b></div><div className="rule-line"><span>최근 30일 평균 판매</span><b>{selected.avg_daily_units.toFixed(2)}개 / 일</b></div><div className="rule-line"><span>재고 판단 속도</span><b>{selected.demand_basis === "none" ? "계산 불가" : `${selected.demand_basis} · ${selected.decision_daily_units.toFixed(2)}개 / 일`}</b></div><small className="muted-note">{selected.demand_explanation}</small>{selected.data_warnings.map((warning) => <small className="muted-note" key={warning}>주의: {warning}</small>)}<div className="rule-line"><span>공급 리드타임</span><b>{selected.lead_time_days}일</b></div><div className="rule-line"><span>목표 보유일</span><b>{selected.target_cover_days}일</b></div><div className="rule-line"><span>30일 매출총이익</span><b>₩{money(selected.gross_margin_30d)}{selected.margin_is_estimated ? "*" : ""}</b></div>{selected.margin_is_estimated && <small className="muted-note">* 매출과 단가로 계산한 추정치입니다.</small>}</div><div className="drawer-section"><label className="field-label" htmlFor="action-note">내 검토 메모 <span>선택</span></label><textarea id="action-note" value={actionNote} onChange={(e) => setActionNote(e.target.value)} placeholder="예: 본사 재고 확인 후 추가 발주 수량 협의" rows={3}/><button className="button button-primary full-button" disabled={busy} onClick={() => void saveAction(selected)}>{busy ? <LoaderCircle className="spin" size={16}/> : <Plus size={16}/>} 조치 검토 기록</button></div><div className="drawer-footnote"><CircleAlert size={15}/> 추천은 검토용입니다. 발주·가격·게시를 자동 실행하지 않습니다.</div></aside></div>}
    </div>
  );
}

function MetricCard({ label, value, change, icon, tone, loading }: { label: string; value: string; change: string; icon: ReactNode; tone: string; loading: boolean }) {
  return <article className="metric-card"><div className="metric-top"><span>{label}</span><span className={`metric-icon ${tone}`}>{icon}</span></div><strong>{loading && value === "—" ? <LoaderCircle className="spin" size={20}/> : value}</strong><div className="metric-change"><span className={`trend-dot ${tone}`}/>{change}</div></article>;
}

function RiskBadge({ risk }: { risk: Risk }) { return <span className={`risk-badge risk-${risk}`}><i/>{riskNames[risk]}</span>; }

function ProductTable({ items, loading, selectedId, onSelect }: { items: ProductAnalysis[]; loading: boolean; selectedId?: number; onSelect: (item: ProductAnalysis) => void }) {
  if (loading && !items.length) return <div className="empty-state"><LoaderCircle className="spin"/> 상품 데이터를 불러오는 중</div>;
  if (!items.length) return <div className="empty-state"><PackageCheck size={23}/><b>표시할 상품이 없습니다.</b><span>검색어 또는 위험 필터를 바꾸어 보세요.</span></div>;
  return <div className="table-scroll"><table className="data-table"><thead><tr><th>상품</th><th>상태</th><th>현재고</th><th>30일 판매</th><th>커버리지</th><th>30일 매출</th><th>추천 조치</th><th/></tr></thead><tbody>{items.map((item) => <tr key={item.product_id} className={selectedId === item.product_id ? "selected-row" : ""} onClick={() => onSelect(item)}><td><div className="product-cell"><div className={`product-thumb thumb-${item.product_id % 5}`}><span>{item.category.slice(0, 1)}</span></div><div><b>{item.name}</b><small>{item.sku} <i>·</i> {item.category}</small></div></div></td><td><RiskBadge risk={item.risk}/></td><td><span className={item.stock_on_hand <= 12 ? "stock-low" : ""}>{money(item.stock_on_hand)}<small>개</small></span></td><td>{money(item.units_30d)}<small className="cell-unit">개</small></td><td><Coverage value={item.days_of_cover} target={item.target_cover_days}/></td><td>₩{shortMoney(item.revenue_30d)}</td><td><span className="recommendation-text">{item.recommendation}</span></td><td><button className="row-open" aria-label={`${item.name} 상세`}><ArrowUpRight size={15}/></button></td></tr>)}</tbody></table></div>;
}

function Coverage({ value, target }: { value: number | null; target: number }) {
  const ratio = value == null ? 0 : Math.min(100, Math.round((value / Math.max(target * 1.8, 1)) * 100));
  return <div className="coverage-cell"><span>{coverText(value)}</span><div className="coverage-track"><i style={{ width: `${ratio}%` }} className={value != null && value > target + 30 ? "bar-warn" : ""}/></div></div>;
}

function MiniMetric({ label, value }: { label: string; value: string }) { return <div className="mini-metric"><span>{label}</span><b>{value}</b></div>; }

function ActionTable({ actions, onComplete }: { actions: ActionRecord[]; onComplete: (item: ActionRecord) => void }) {
  const [openId, setOpenId] = useState<number | null>(null);
  const [outcome, setOutcome] = useState<ActionOutcome | null>(null);
  const [outcomeError, setOutcomeError] = useState("");
  async function openOutcome(id: number) {
    if (openId === id) { setOpenId(null); return; }
    setOpenId(id); setOutcome(null); setOutcomeError("");
    try { setOutcome(await api.actionOutcome(id)); }
    catch (error) { setOutcomeError(error instanceof Error ? error.message : "결과를 불러오지 못했습니다."); }
  }
  if (!actions.length) return <div className="empty-state"><Clock3 size={23}/><b>아직 기록된 조치가 없어요.</b><span>상품 분석에서 조치 검토 기록을 남겨보세요.</span></div>;
  return <div className="action-list">{actions.map((action) => <article className="action-item" key={action.id}><div className={`action-type-icon ${action.status}`}><Activity size={17}/></div><div className="action-main"><div><b>{actionNames[action.action_type]}</b><span className="action-product">{action.product_name} · {action.sku}</span></div><p>{action.note || "추가 메모 없음"}</p><small>{new Date(action.created_at).toLocaleString("ko-KR", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })} · 기록 당시 재고 {action.stock_before}개 / 30일 판매 {action.units_30d_before}개</small><button className="action-outcome-toggle" onClick={() => void openOutcome(action.id)}>{openId === action.id ? "결과 닫기" : "전후 변화 확인"}</button>{openId === action.id && <div className="action-outcome"><b>{outcome?.status === "comparable" ? "전후 7일 비교" : "비교 준비 상태"}</b>{outcomeError && <p>{outcomeError}</p>}{!outcome && !outcomeError && <p>자료를 확인하는 중…</p>}{outcome && <><p>{outcome.interpretation}</p>{outcome.status === "waiting_for_data" && <p>누락된 일별 기록: 이전 {outcome.missing_before_days}일 · 이후 {outcome.missing_after_days}일</p>}{outcome.before && outcome.after && <div className="action-outcome-grid"><span>판매 수량 <strong>{money(outcome.before.units)} → {money(outcome.after.units)}개</strong></span><span>매출 <strong>₩{money(outcome.before.revenue)} → ₩{money(outcome.after.revenue)}</strong></span><span>매출총이익 <strong>{outcome.before.gross_margin == null || outcome.after.gross_margin == null ? "실측 원가 정보 부족" : `₩${money(outcome.before.gross_margin)} → ₩${money(outcome.after.gross_margin)}`}</strong></span></div>}<p>기록 당시 재고 {money(outcome.stock_at_log)}개 · 현재고 {money(outcome.stock_now)}개</p><small>{outcome.stock_note}</small></>}</div>}</div><div className="action-end">{action.status === "completed" ? <span className="complete-pill"><Check size={13}/> 완료 표시</span> : <button className="button button-secondary small-button" onClick={() => onComplete(action)}>완료 표시</button>}</div></article>)}</div>;
}

export default App;



