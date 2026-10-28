import { useEffect, useState } from "react";
import { ArrowRight, Database, Info, TriangleAlert } from "lucide-react";
import type { WorkView } from "./App";
import { simApi, type SimAnalysis, type SimComparison, type SimDecision, type SimForecast, type SimProduct, type SimProductDetail, type SimScenario } from "./workApi";
import "./hm-sim.css";

const n = (value: number) => new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 }).format(value);
const won = (value: number) => `₩${n(value)}`;
const riskLabels: Record<string, string> = {
  stockout: "재고 없음", stock_risk: "소진 위험", overstock: "재고 과다", declining: "판매 감소",
  rising: "판매 증가", not_observed: "판매 미관측", stable: "정상",
};

function Source({ kind }: { kind: "sales" | "conditions" | "results" }) {
  const label = { sales: "H&M 관측", conditions: "가상 운영 조건", results: "시뮬레이션" }[kind];
  return <span className={`sim-source ${kind}`}>{label}</span>;
}

export default function HmSimulation({ datasetId, view, onNavigate }: { datasetId: number; view: WorkView; onNavigate: (view: WorkView) => void }) {
  const [scenario, setScenario] = useState<SimScenario | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [analysis, setAnalysis] = useState<SimAnalysis | null>(null);
  const [decisions, setDecisions] = useState<SimDecision[]>([]);
  const [selectedSku, setSelectedSku] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const items = await simApi.scenarios(datasetId);
    const current = items[0] || null;
    setScenario(current);
    if (current) {
      const [result, saved] = await Promise.all([simApi.analysis(current.id), simApi.decisions(current.id)]);
      setAnalysis(result); setDecisions(saved);
    }
    setLoaded(true);
  }
  useEffect(() => { setLoaded(false); void load().catch((err) => setError(err instanceof Error ? err.message : "시뮬레이션을 불러오지 못했습니다.")); }, [datasetId]);

  async function connect() {
    setBusy(true); setError("");
    try { await simApi.importSample(datasetId); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "시뮬레이션 자료를 연결하지 못했습니다."); }
    finally { setBusy(false); }
  }
  function openProduct(sku: string) { setSelectedSku(sku); onNavigate("products"); requestAnimationFrame(() => requestAnimationFrame(() => document.getElementById("sim-product-detail")?.scrollIntoView({ behavior: "smooth" }))); }

  if (error) return <div className="error-banner"><TriangleAlert size={17}/>{error}</div>;
  if (!loaded) return <p className="work-empty">시뮬레이션을 불러오는 중…</p>;
  if (!scenario || !analysis) return <section className="panel work-panel"><h2>운영 시뮬레이션 연결</h2><p>H&M 관측 판매 상품 일부에 가상 재고·발주·원화 가격·원가를 결합한 사례를 별도 테이블로 연결합니다. 자사 업로드와 H&M 판매 기록은 바뀌지 않습니다. 모든 행을 검증한 뒤 한 번에 저장합니다.</p><button type="button" className="button button-primary" disabled={busy} onClick={() => void connect()}><Database size={16}/>{busy ? "검증 중…" : "운영 시뮬레이션 자료 연결"}</button></section>;

  const focus = analysis.products.find((item) => item.sku === selectedSku) || analysis.products[0];
  const attention = analysis.products.filter((item) => !["stable", "not_observed"].includes(item.signal.risk));
  const unobserved = analysis.products.filter((item) => item.signal.risk === "not_observed");

  return <div className="sim-page">
    <section className="sim-legend" aria-label="출처 구분"><span><Source kind="sales"/> 판매 수량</span><span><Source kind="conditions"/> 재고·발주·원화 가격·원가·상품 상태</span><span><Source kind="results"/> 재고 위험·공급 부족분·매출총이익</span><b>판단 기준일 {analysis.as_of_date}</b></section>
    <p className="work-source-note"><Info size={15}/>{scenario.source_note}</p>
    <p className="sim-bias"><TriangleAlert size={15}/>{scenario.bias_note}</p>

    {view === "overview" && <>
      <section className="work-summary" aria-label="기준일 핵심 지표"><div><small>기준일 30일 판매 <Source kind="sales"/></small><strong>{n(analysis.summary.units_30d)}개</strong></div><div><small>우선 확인 <Source kind="results"/></small><strong>{analysis.summary.attention_count}개</strong></div><div><small>판매 미관측</small><strong>{unobserved.length}개</strong></div><div><small>시뮬레이션 상품</small><strong>{analysis.summary.total_products}종</strong></div></section>
      <section className="panel work-panel"><div className="work-panel-heading"><div><span className="section-kicker">AS OF {analysis.as_of_date}</span><h2>기준일에 확인할 상품</h2><small>8월 31일까지의 관측 판매와 가상 재고로 계산했습니다. 9월 판매는 사용하지 않았습니다.</small></div><button type="button" className="button button-secondary" onClick={() => onNavigate("products")}>전체 50종 <ArrowRight size={16}/></button></div>
        <div className="work-priority-list">{[...attention, ...unobserved].slice(0, 12).map((item) => <button type="button" key={item.sku} onClick={() => openProduct(item.sku)}>{item.image_ref && <img className="work-product-image" src={item.image_ref} alt="" loading="lazy"/>}<span className={`work-risk ${item.signal.risk}`}>{riskLabels[item.signal.risk]}</span><span className="work-priority-main"><b>{item.name}</b><small>{item.signal.reason}</small></span><span className="work-action">{item.signal.action}<ArrowRight size={15}/></span></button>)}</div>
      </section>
      <PostSummary analysis={analysis} onOpen={openProduct} limit={8}/>
    </>}

    {view === "products" && <>
      <section className="panel work-panel"><div className="work-panel-heading"><div><h2>시뮬레이션 {analysis.products.length}종 · {analysis.as_of_date} 기준</h2><small>판매는 H&M 관측, 재고는 가상 운영 조건, 판단은 시뮬레이션입니다.</small></div></div>
        <div className="table-scroll"><table className="data-table work-table"><thead><tr><th>상품</th><th>최근 14일 / 직전 <Source kind="sales"/></th><th>기준일 재고 <Source kind="conditions"/></th><th>판매율 7/1~8/31 <Source kind="results"/></th><th>판단 <Source kind="results"/></th><th>이후 관측 · 공급 부족분</th></tr></thead><tbody>{analysis.products.map((item) => <tr key={item.sku} className={focus?.sku === item.sku ? "selected-row" : ""}><td><button type="button" onClick={() => setSelectedSku(item.sku)}><b>{item.name}</b><small>{item.sku} · {item.conditions.lifecycle_label}</small></button></td><td>{n(item.observed.units_14d)}개 / {n(item.observed.prior_14d)}개</td><td>{n(item.conditions.stock_on_hand)}개<small>{item.signal.days_of_cover == null ? "소진일 계산 안 함" : `약 ${n(item.signal.days_of_cover)}일분`}</small></td><td>{item.sell_through.pct == null ? "—" : `${n(item.sell_through.pct)}%`}</td><td><span className={`work-risk ${item.signal.risk}`}>{riskLabels[item.signal.risk]}</span><small>{item.signal.action}</small></td><td>{n(item.post_as_of.observed_units)}개<small>{item.post_as_of.policy_shortfall_units ? `부족분 ${n(item.post_as_of.policy_shortfall_units)}개` : "부족분 없음"}</small></td></tr>)}</tbody></table></div>
      </section>
      {focus && <SimProductPanel key={`${scenario.id}-${focus.sku}`} scenario={scenario} sku={focus.sku} onSaved={async () => setDecisions(await simApi.decisions(scenario.id))}/>}
    </>}

    {view === "actions" && <section className="panel work-panel"><div className="work-panel-heading"><div><h2>시뮬레이션 판단 기록</h2><small>저장 당시의 관측 판매·가상 조건·계산 결과를 그대로 보관합니다. 이후 자료가 바뀌어도 기록은 바뀌지 않습니다.</small></div></div>
      {decisions.length ? <div className="work-decision-list">{decisions.map((item) => <article className="work-decision-row" key={item.id}><div><b>{item.name} · {item.action}</b><span>{item.snapshot.scenario.name}</span></div><p>{item.rationale}</p>
        <small><Source kind="sales"/> 기준일 {item.as_of_date} · 최근 14일 {n(item.snapshot.observed.units_14d)}개 · 30일 {n(item.snapshot.observed.units_30d)}개</small>
        <small><Source kind="conditions"/> 재고 {n(item.snapshot.conditions.stock_on_hand)}개 · 30일 내 계획 입고 {n(item.snapshot.conditions.planned_inbound_30d)}개 · 판매가 {won(item.snapshot.conditions.selling_price_krw)} · 원가 {won(item.snapshot.conditions.unit_cost_krw)}</small>
        <small><Source kind="results"/> {riskLabels[item.snapshot.signal.risk]} · 할인 {item.snapshot.comparison.discount_pct}% · 가정 판매 {n(item.snapshot.comparison.expected_units_30d)}개 · 추가 매입 {n(item.snapshot.comparison.purchase_units)}개 · 매출총이익 {item.snapshot.comparison.estimated_gross_profit_krw == null ? "계산 불가" : won(item.snapshot.comparison.estimated_gross_profit_krw)}</small>
        {(() => { const after = analysis.products.find((product) => product.sku === item.sku)?.post_as_of; return after && <small className="sim-after"><b>회고</b> 이후 관측 {after.start}~{after.end} <Source kind="sales"/> 판매 {n(after.observed_units)}개 · <Source kind="results"/> 가상 정책상 공급 부족 {n(after.policy_shortfall_units)}개{after.first_shortfall_date ? ` (첫 부족 ${after.first_shortfall_date})` : ""} · 저장 당시에는 알 수 없던 값이며 판단의 성과가 아닙니다</small>; })()}
      </article>)}</div> : <p className="work-empty">저장한 판단이 없습니다. 상품을 열어 두 안을 비교한 뒤 이유를 남겨 보세요.</p>}
    </section>}

    {view === "planning" && <><ForecastCheck scenarioId={scenario.id} onOpen={openProduct}/><Retrospective analysis={analysis}/><PostSummary analysis={analysis} onOpen={openProduct}/></>}
  </div>;
}

function ForecastCheck({ scenarioId, onOpen }: { scenarioId: number; onOpen: (sku: string) => void }) {
  const [data, setData] = useState<SimForecast | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { void simApi.forecast(scenarioId).then(setData).catch((err) => setError(err instanceof Error ? err.message : "추정을 불러오지 못했습니다.")); }, [scenarioId]);
  if (error) return <p className="work-error">{error}</p>;
  if (!data) return null;
  const pct = (value: number | null | undefined) => value == null ? "—" : `${value > 0 ? "+" : ""}${n(value)}%`;
  const range = (pair: [string, string]) => `${pair[0].slice(5)}~${pair[1].slice(5)}`;
  const methods = (["velocity", "seasonal"] as const).filter((key) => data.validation[key]);
  return <section className="panel work-panel sim-forecast"><div className="work-panel-heading"><div><span className="section-kicker">ESTIMATE · {data.as_of_date} → {data.windows.after[1]}</span><h2>9월 판매 추정과 실제</h2><small>8월 31일까지 알 수 있던 판매로 이후 {data.horizon_days}일을 추정하고, 실제 판매와 나란히 봅니다.</small></div><Source kind="results"/></div>
    <div className="sim-forecast-method"><p><b>{data.methods.velocity}</b> 최근 14일({range(data.windows.recent)}) 일평균 × {data.horizon_days}일</p><p><b>{data.methods.seasonal}</b> 위 값 × {data.seasonal_factor ?? "—"} <small>작년 같은 기간 표본 전체: {range(data.windows.after_last_year)} 일평균 ÷ {range(data.windows.base_last_year)} 일평균 ({n(data.seasonal_reference.after_units)}개/{data.horizon_days}일 ÷ {n(data.seasonal_reference.base_units)}개/14일) <Source kind="sales"/></small></p></div>
    <div className="table-scroll"><table className="data-table work-table"><thead><tr><th>방식</th><th>추정 합계</th><th>실제 합계 <Source kind="sales"/></th><th>합계 차이</th><th>상품별 오차율<small>Σ|추정−실제| ÷ Σ실제</small></th></tr></thead><tbody>{methods.map((key) => { const v = data.validation[key]!; return <tr key={key}><td><b>{data.methods[key]}</b></td><td>{n(v.estimated_units)}개</td><td>{n(v.actual_units)}개</td><td>{pct(v.bias_pct)}</td><td>{v.wape_pct == null ? "—" : `${n(v.wape_pct)}%`}</td></tr>; })}</tbody></table></div>
    <p className="work-caveat">8/31까지 28일 안에 판매가 있었던 H&M 상품 {data.validation.products}종 전체로 비교했습니다. {data.note}</p>
    <h3>시뮬레이션 상품 물량 검토 <small>작년 계절 보정 추정 기준</small></h3>
    <div className="table-scroll"><table className="data-table work-table"><thead><tr><th>상품</th><th>8/31 판정</th><th>추정 ({data.horizon_days}일)</th><th>{data.windows.after[1].slice(5)}까지 공급 가능 <Source kind="conditions"/><small>재고 + 기간 내 입고</small></th><th>예상 재고 공백<small>입고일 기준 날짜별 확인</small></th><th>실제 판매 <Source kind="sales"/></th><th>가상 정책상 부족</th></tr></thead><tbody>{data.products.map((row) => <tr key={row.sku}><td><button type="button" onClick={() => onOpen(row.sku)}><b>{row.name}</b><small>{row.sku}</small></button></td><td><span className={`work-risk ${row.risk}`}>{riskLabels[row.risk]}</span></td><td>{row.estimate.seasonal == null ? "—" : `${n(Math.round(row.estimate.seasonal))}개`}<small>속도 유지 {n(Math.round(row.estimate.velocity))}개</small></td><td>{row.supply_until_end == null ? "—" : `${n(row.supply_until_end)}개`}</td><td>{row.expected_gap_units ? <b className="sim-gap">최대 {n(row.expected_gap_units)}개</b> : "없음"}{row.first_gap_date ? <small>{row.first_gap_date.slice(5)}부터 · {row.purchase_arrives_in_window ? "추가 매입이 기간 안에 도착 가능" : "기간 안에 추가 매입 도착 불가"}</small> : null}</td><td>{n(row.actual_units)}개</td><td>{n(row.policy_shortfall_units)}개</td></tr>)}</tbody></table></div>
  </section>;
}

function Retrospective({ analysis }: { analysis: SimAnalysis }) {
  const retro = analysis.retrospective;
  const post = analysis.post_as_of_summary;
  const pct = (value: number | null) => value == null ? "—" : `${value > 0 ? "+" : ""}${n(value)}%`;
  return <section className="panel work-panel sim-retro"><div className="work-panel-heading"><div><span className="section-kicker">LOOK BACK · {analysis.as_of_date} → {post.end}</span><h2>8/31 판단 회고</h2><small>판정 유형별로 기준일 직전 14일과 이후 {retro.post_days}일의 관측 판매, 가상 재고 흐름을 나란히 봅니다.</small></div></div>
    <div className="table-scroll"><table className="data-table work-table"><thead><tr><th>8/31 판정</th><th>상품</th><th>일평균 판매 <Source kind="sales"/><small>직전 14일 → 이후 {retro.post_days}일</small></th><th>이후 판매 관측</th><th>가상 정책상 공급 부족 <Source kind="results"/></th><th>가상 재고 <Source kind="conditions"/><small>8/31 → {post.end}</small></th></tr></thead><tbody>{retro.groups.map((group) => <tr key={group.risk}><td><span className={`work-risk ${group.risk}`}>{riskLabels[group.risk]}</span></td><td>{group.products}종</td><td>{n(group.before_daily_units)} → {n(group.after_daily_units)}개<small>{pct(group.daily_change_pct)}</small></td><td>{group.products_sold_after}/{group.products}종</td><td>{group.products_with_shortfall}종 · {n(group.policy_shortfall_units)}개</td><td>{n(group.as_of_stock)} → {n(group.end_stock)}개</td></tr>)}</tbody></table></div>
    <p className="work-caveat">{retro.note}</p>
  </section>;
}

function PostSummary({ analysis, onOpen, limit }: { analysis: SimAnalysis; onOpen: (sku: string) => void; limit?: number }) {
  const post = analysis.post_as_of_summary;
  const rows = [...analysis.products].sort((a, b) => b.post_as_of.policy_shortfall_units - a.post_as_of.policy_shortfall_units || b.post_as_of.observed_units - a.post_as_of.observed_units);
  return <section className="panel work-panel sim-post"><div className="work-panel-heading"><div><span className="section-kicker">AFTER {analysis.as_of_date} · {post.start} ~ {post.end}</span><h2>이후 관측 판매</h2><small>기준일 판단에는 쓰지 않은 기간입니다. 8월 31일의 가상 재고와 계획 입고로 이 판매를 공급할 수 있었는지만 확인합니다.</small></div></div>
    <div className="work-summary"><div><small>이후 관측 판매 <Source kind="sales"/></small><strong>{n(post.observed_units)}개</strong></div><div><small>가상 재고로 공급 가능 <Source kind="results"/></small><strong>{n(post.supplied_units)}개</strong></div><div><small>가상 정책상 공급 부족분 <Source kind="results"/></small><strong>{n(post.policy_shortfall_units)}개</strong></div><div><small>부족분이 생긴 상품</small><strong>{post.products_with_shortfall}종</strong></div></div>
    <p className="work-caveat">{post.note}</p>
    <div className="table-scroll"><table className="data-table work-table"><thead><tr><th>상품</th><th>8/31 판단</th><th>이후 관측 판매</th><th>공급 가능</th><th>가상 정책상 공급 부족분</th><th>첫 부족일</th></tr></thead><tbody>{rows.slice(0, limit ?? rows.length).map((item) => <tr key={item.sku}><td><button type="button" onClick={() => onOpen(item.sku)}><b>{item.name}</b><small>{item.sku}</small></button></td><td><span className={`work-risk ${item.signal.risk}`}>{riskLabels[item.signal.risk]}</span></td><td>{n(item.post_as_of.observed_units)}개</td><td>{n(item.post_as_of.supplied_units)}개</td><td>{n(item.post_as_of.policy_shortfall_units)}개</td><td>{item.post_as_of.first_shortfall_date || "—"}</td></tr>)}</tbody></table></div>
  </section>;
}

function LedgerChart({ detail }: { detail: SimProductDetail }) {
  const rows = detail.ledger;
  const max = Math.max(1, ...rows.map((row) => Math.max(row.closing_stock, row.observed_units)));
  const width = 840, height = 220, pad = 28;
  const x = (i: number) => pad + (i / Math.max(1, rows.length - 1)) * (width - pad * 2);
  const y = (v: number) => height - pad - (v / max) * (height - pad * 2);
  const split = rows.findIndex((row) => row.period === "post_as_of_observed");
  const bar = (width - pad * 2) / rows.length * 0.7;
  const stockPath = rows.map((row, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(row.closing_stock).toFixed(1)}`).join(" ");
  return <div className="sim-chart"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${detail.name} 일별 관측 판매와 가상 기말재고. ${detail.scenario.as_of_date} 이후는 이후 관측 기간`}>
    {split > 0 && <rect x={x(split) - bar / 2} y={pad / 2} width={width - pad - x(split) + bar / 2} height={height - pad * 1.5} className="sim-chart-post"/>}
    {rows.map((row, i) => <g key={row.date}>
      <rect x={x(i) - bar / 2} y={y(row.supplied_units)} width={bar} height={height - pad - y(row.supplied_units)} className="sim-chart-supplied"/>
      {row.policy_shortfall_units > 0 && <rect x={x(i) - bar / 2} y={y(row.observed_units)} width={bar} height={y(row.supplied_units) - y(row.observed_units)} className="sim-chart-shortfall"/>}
    </g>)}
    <path d={stockPath} className="sim-chart-stock"/>
    {split > 0 && <><line x1={x(split) - bar} x2={x(split) - bar} y1={pad / 2} y2={height - pad} className="sim-chart-asof"/><text x={x(split) - bar - 4} y={pad} textAnchor="end">기준일 {detail.scenario.as_of_date}</text><text x={x(split) + 4} y={pad}>이후 관측</text></>}
    <text x={pad} y={height - 8}>{rows[0]?.date}</text><text x={width - pad} y={height - 8} textAnchor="end">{rows[rows.length - 1]?.date}</text>
  </svg><div className="sim-chart-legend"><span><i className="supplied"/>관측 판매 중 공급 가능 (H&M 관측 × 가상 재고)</span><span><i className="shortfall"/>가상 정책상 공급 부족분</span><span><i className="stock"/>가상 기말재고</span></div></div>;
}

function SimProductPanel({ scenario, sku, onSaved }: { scenario: SimScenario; sku: string; onSaved: () => Promise<void> }) {
  const [detail, setDetail] = useState<SimProductDetail | null>(null);
  const [discount, setDiscount] = useState(15);
  const [expected, setExpected] = useState(0);
  const [purchase, setPurchase] = useState(0);
  const [comparison, setComparison] = useState<[SimComparison, SimComparison] | null>(null);
  const [action, setAction] = useState("할인 검토");
  const [rationale, setRationale] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { void simApi.product(scenario.id, sku).then((value) => { setDetail(value); setExpected(value.observed.units_30d); }).catch((err) => setMessage(err instanceof Error ? err.message : "상품을 불러오지 못했습니다.")); }, [scenario.id, sku]);
  if (!detail) return <p className="work-empty">{message || "상품을 불러오는 중…"}</p>;
  const item: SimProduct = detail;

  async function compare() {
    setBusy(true); setMessage("");
    try {
      const common = { scenario_id: scenario.id, sku };
      const results = await Promise.all([
        simApi.compare({ ...common, discount_pct: 0, expected_units_30d: item.observed.units_30d, purchase_units: 0 }),
        simApi.compare({ ...common, discount_pct: discount, expected_units_30d: expected, purchase_units: purchase }),
      ]);
      setComparison(results as [SimComparison, SimComparison]);
    } catch (err) { setMessage(err instanceof Error ? err.message : "비교를 계산하지 못했습니다."); }
    finally { setBusy(false); }
  }
  async function save() {
    setBusy(true); setMessage("");
    try {
      await simApi.saveDecision({ scenario_id: scenario.id, sku, discount_pct: discount, expected_units_30d: expected, purchase_units: purchase, action, rationale });
      await onSaved(); setRationale(""); setMessage("판단과 당시의 관측 판매·가상 조건·계산 결과를 기록했습니다. 실제 실행이나 성과가 아닙니다.");
    } catch (err) { setMessage(err instanceof Error ? err.message : "판단을 저장하지 못했습니다."); }
    finally { setBusy(false); }
  }
  const maxProfit = Math.max(1, ...(comparison || []).map((value) => Math.max(0, value.estimated_gross_profit_krw || 0)));
  const c = item.conditions;

  return <section className="panel work-panel work-detail" id="sim-product-detail">
    <div className="work-panel-heading"><div><span className="section-kicker">SIMULATION · {item.sku} · 기준일 {scenario.as_of_date}</span><h2>{item.name}</h2><small>{item.section} · {item.category} · {c.lifecycle_label}{c.scenario_lifecycle !== "unassigned" ? " — 실제 출시·행사 사실이 아닌 가상 상태" : ""}</small></div><span className="work-detail-identity">{item.image_ref && <img className="work-product-image large" src={item.image_ref} alt={`${item.name} 상품 사진`} loading="lazy"/>}<span className={`work-risk ${item.signal.risk}`}>{riskLabels[item.signal.risk]}</span></span></div>
    <div className="sim-columns">
      <div><h3>판매 <Source kind="sales"/></h3><dl><dt>최근 7일</dt><dd>{n(item.observed.units_7d)}개</dd><dt>최근 14일 / 직전 14일</dt><dd>{n(item.observed.units_14d)} / {n(item.observed.prior_14d)}개</dd><dt>최근 30일 / 직전 30일</dt><dd>{n(item.observed.units_30d)} / {n(item.observed.prior_30d)}개</dd><dt>처음 관측된 판매일</dt><dd>{item.observed.first_sale_date || "기준일까지 없음"}</dd></dl><small>처음 관측된 날이며 실제 출시일이 아닙니다.</small></div>
      <div><h3>기준일 조건 <Source kind="conditions"/></h3><dl><dt>기준일 재고</dt><dd>{n(c.stock_on_hand)}개</dd><dt>기준일 이후 계획 입고</dt><dd>{n(c.planned_inbound_after_as_of)}개 (30일 내 {n(c.planned_inbound_30d)}개)</dd><dt>리드타임</dt><dd>{c.lead_time_days}일</dd><dt>재발주</dt><dd>{c.reorderable ? "가능" : `불가 (설정일 ${c.reorder_stop_date})`}</dd><dt>정가 / 판매가 / 원가</dt><dd>{won(c.list_price_krw)} / {won(c.selling_price_krw)} / {won(c.unit_cost_krw)}</dd></dl></div>
      <div><h3>판단 <Source kind="results"/></h3><dl><dt>소진 예상일</dt><dd>{item.signal.days_of_cover == null ? "판매 속도 없음 · 계산 안 함" : `약 ${n(item.signal.days_of_cover)}일`}</dd><dt>근거</dt><dd>{item.signal.reason}</dd><dt>다음 검토</dt><dd>{item.signal.action}</dd><dt>{item.sell_through.label}</dt><dd>{item.sell_through.pct == null ? item.sell_through.reason : `${n(item.sell_through.pct)}%`}<small>{item.sell_through.start} ~ {item.sell_through.end} · 공급 {n(item.sell_through.sold_units ?? 0)} ÷ (기초 {n(item.sell_through.opening_stock ?? 0)} + 입고 {n(item.sell_through.received_units ?? 0)})</small></dd><dt>기준일 30일 시뮬레이션 매출총이익</dt><dd>{won(item.signal.simulated_gross_profit_30d_krw)}</dd></dl><small>판매율은 가상 재고 기준이라 H&M 실제 판매율이 아닙니다. 매출총이익은 가상 가격·원가로 계산한 값이며 H&M 실적이 아닙니다.</small></div>
    </div>
    <details className="sim-reasons"><summary>선정 이유와 가정</summary><p>{detail.policy.selection_reason}</p><p>{detail.policy.assumption_reason}</p>{detail.prices.map((price) => <p key={price.valid_from}>{price.valid_from}~{price.valid_to}: 판매가 {won(price.selling_price_krw)} · {price.price_tier_rule} · 원가 {price.cost_rule}</p>)}</details>

    <h3>일별 수불 <Source kind="conditions"/></h3>
    <LedgerChart detail={detail}/>

    <div className="sim-two">
      <div><h3>계획 발주·입고 <Source kind="conditions"/></h3><p className="work-caveat">모두 {scenario.as_of_date} 이전에 낸 가상 발주입니다. 9월 부족분을 메우는 사후 입고는 넣지 않았습니다.</p>
        {detail.planned_orders.length ? <div className="table-scroll"><table className="data-table work-table"><thead><tr><th>발주일</th><th>입고(예정)일</th><th>수량</th><th>구분</th></tr></thead><tbody>{detail.planned_orders.map((po) => <tr key={po.po_code}><td>{po.order_date}</td><td>{po.actual_receipt_date || po.expected_receipt_date}</td><td>{n(po.ordered_units)}개</td><td>{po.timing}{po.status === "open" ? " · 기간 후 입고" : ""}</td></tr>)}</tbody></table></div> : <p className="work-empty">발주 없음 · 7월 1일 기초재고로만 운영</p>}</div>
      <div className="sim-post-box"><h3>이후 관측 ({item.post_as_of.start} ~ {item.post_as_of.end})</h3><dl><dt>이후 관측 판매 <Source kind="sales"/></dt><dd>{n(item.post_as_of.observed_units)}개</dd><dt>가상 재고로 공급 가능 <Source kind="results"/></dt><dd>{n(item.post_as_of.supplied_units)}개</dd><dt>가상 정책상 공급 부족분 <Source kind="results"/></dt><dd>{n(item.post_as_of.policy_shortfall_units)}개{item.post_as_of.first_shortfall_date ? ` · 첫 부족 ${item.post_as_of.first_shortfall_date}` : ""}</dd><dt>{item.post_as_of.end} 가상 기말재고</dt><dd>{n(item.post_as_of.closing_stock)}개</dd></dl><small>{scenario.shortfall_note}</small></div>
    </div>

    <div className="work-compare"><div className="work-panel-heading"><div><h3>두 조치안 비교 ({scenario.as_of_date} 기준)</h3><small>A: 현재 판매가·최근 30일 판매량 유지 · B: 내가 입력한 가정</small></div><Source kind="results"/></div>
      <div className="work-form-grid work-compare-fields"><label>B안 할인율 (%)<input type="number" min="0" max="70" value={discount} onChange={(event) => { setDiscount(Number(event.target.value)); setComparison(null); }}/></label><label>B안 예상 30일 판매 (개)<input type="number" min="0" value={expected} onChange={(event) => { setExpected(Number(event.target.value)); setComparison(null); }}/></label><label>추가 매입 (개)<input type="number" min="0" value={purchase} disabled={!c.reorderable} onChange={(event) => { setPurchase(Number(event.target.value)); setComparison(null); }}/>{!c.reorderable && <small>재발주 불가 상품</small>}</label></div>
      <button type="button" className="button button-primary" disabled={busy || discount < 0 || discount > 70 || expected < 0 || purchase < 0} onClick={() => void compare()}>숫자로 비교</button>
      {comparison && <><div className="work-comparison-result">{comparison.map((result, index) => <div key={index}><b>{index === 0 ? "A · 현재 유지" : "B · 변경안"}</b><strong>{result.feasible && result.estimated_gross_profit_krw != null ? won(result.estimated_gross_profit_krw) : "가용 수량 부족"}</strong><div className="work-profit-bar"><span style={{ width: `${result.feasible ? Math.max(0, (result.estimated_gross_profit_krw || 0) / maxProfit * 100) : 0}%` }}/></div><small>30일 가용 {n(result.available_units_30d)}개 · 예상 잔여 {result.estimated_remaining_units == null ? "계산 불가" : `${n(result.estimated_remaining_units)}개`}{result.purchase_counted_in_30d === false ? ` · 추가 매입은 ${result.purchase_arrival_date} 도착이라 30일 가용에서 제외` : ""}</small>{result.first_gap_date && <small className="work-gap">{result.first_gap_date}부터 재고 공백 · 최대 {n(result.max_gap_units)}개 부족</small>}</div>)}</div>
        <p className="work-caveat">{comparison[1].note}</p>
        <div className="work-decision-form"><label>검토할 조치<select value={action} onChange={(event) => setAction(event.target.value)}>{["할인 검토", "추가 매입 검토", "프로모션 검토", "라이브 노출 검토", "현재 유지"].map((value) => <option key={value}>{value}</option>)}</select></label><label>판단 이유<textarea rows={2} value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="예: 기준일 재고가 리드타임보다 짧아 추가 매입 가능 수량을 먼저 확인한다."/></label><button type="button" className="button button-secondary" disabled={busy || !comparison[1].feasible || rationale.trim().length < 5} onClick={() => void save()}>판단 기록 저장</button></div></>}
    </div>
    {message && <p className="work-inline-message">{message}</p>}
  </section>;
}
