import { useEffect, useState } from "react";
import { ArrowRight, Database, TriangleAlert } from "lucide-react";
import { api } from "./api";
import type { FashionPlanDecision, FashionPlanning } from "./types";
import "./fashion-planning.css";

const qty = (value: number) => new Intl.NumberFormat("ko-KR").format(value);
const won = (value: number) => `₩${qty(value)}`;
const barWidth = (value: number, maximum: number) => `${Math.min(100, Math.max(0, maximum ? value / maximum * 100 : 0))}%`;

function SellThroughBar({ value, valid = true }: { value: number | null; valid?: boolean }) {
  if (!valid || value == null) return <span className="fashion-chart-unavailable">재검증 필요</span>;
  return <div className="fashion-sell-through" role="img" aria-label={`판매율 ${value}%`}>
    <span className="fashion-sell-through-track"><span style={{ width: barWidth(value, 100) }} /></span>
    <b>{value}%</b>
  </div>;
}

export default function FashionPlanningPanel() {
  const [ready, setReady] = useState(false);
  const [data, setData] = useState<FashionPlanning | null>(null);
  const [growth, setGrowth] = useState(0);
  const [target, setTarget] = useState(85);
  const [selected, setSelected] = useState("FSH-FW-012");
  const [salesGroup, setSalesGroup] = useState("SS");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [rationale, setRationale] = useState("");
  const [decisions, setDecisions] = useState<FashionPlanDecision[]>([]);
  const [saved, setSaved] = useState("");

  useEffect(() => {
    void api.fashionPlanningStatus().then((status) => setReady(status.ready))
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "운영 자료 상태를 확인하지 못했습니다."));
  }, []);

  useEffect(() => {
    if (!ready) return;
    void api.fashionPlanningAnalysis(growth, target).then(setData)
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "운영 자료를 분석하지 못했습니다."));
  }, [ready, growth, target]);

  useEffect(() => {
    if (!ready) return;
    void api.fashionPlanDecisions().then(setDecisions)
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "기획 기록을 읽지 못했습니다."));
  }, [ready]);

  async function importSample() {
    setBusy(true);
    setError("");
    try {
      await api.fashionPlanningImport();
      setReady(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "운영 자료를 연결하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function saveDecision() {
    if (!focus || rationale.trim().length < 5) {
      setError("판단 이유를 다섯 글자 이상 적어 주세요.");
      return;
    }
    setBusy(true);
    setError("");
    setSaved("");
    try {
      await api.fashionSavePlanDecision({ sku: focus.sku, growth_pct: growth, target_sell_through_pct: target, rationale: rationale.trim() });
      setDecisions(await api.fashionPlanDecisions());
      setSaved("검토 기록을 저장했습니다. 실제 발주나 재고는 바뀌지 않았습니다.");
      setRationale("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "기획 기록을 저장하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  const focus = data?.plans.find((plan) => plan.sku === selected) ?? data?.plans[0];
  const flow = data?.flow_summary.find((item) => item.sku === focus?.sku);
  const complete = data?.flow_summary.filter((item) => item.reconciled_with_current_inputs).length ?? 0;
  const sold = data?.flow_summary.reduce((total, item) => total + item.sold_units, 0) ?? 0;
  const receipts = data?.flow_summary.reduce((total, item) => total + item.receipts, 0) ?? 0;
  const extraOrderCount = data?.plans.filter((plan) => plan.additional_order_to_review > 0).length ?? 0;
  const excessCount = data?.plans.filter((plan) => plan.excess_units_to_review > 0).length ?? 0;
  const currentRows = data?.flow_summary.filter((item) => item.season_group === salesGroup) ?? [];

  return <section className="panel fashion-planning" aria-labelledby="fashion-planning-title">
    <div className="fashion-planning-head">
      <div><span className="section-kicker">STOCK FLOW → NEXT SEASON</span>
        <h2 id="fashion-planning-title">판매 결과를 다음 시즌 기획으로 연결하기</h2>
        <p>판매율 · 재고 수불 · F/W 물량 검토</p>
      </div>
      <span className="fashion-planning-source">전체 합성 운영자료</span>
    </div>

    {!ready && <div className="fashion-planning-empty"><div><b>운영 자료를 연결해 주세요</b><p>기존 판매·상품 값은 그대로 두고, 60일 재고 수불 1,800행과 작년 F/W 비교 자료 12행을 별도로 저장합니다.</p></div><button className="button button-primary" disabled={busy} onClick={() => void importSample()}><Database size={16}/>{busy ? "검증하는 중…" : "운영 자료 연결"}</button></div>}
    {error && <div className="error-banner"><TriangleAlert size={16}/>{error}</div>}

    {data && <>
      <div className="fashion-planning-kpis">
        <div><small>60일 판매</small><strong>{qty(sold)}개</strong><span>기존 판매 CSV와 대조</span></div>
        <div><small>기간 중 입고</small><strong>{qty(receipts)}개</strong><span>입고 예정과 구분</span></div>
        <div><small>현재 입력과 일치</small><strong>{complete} / 30개</strong><span>판매 또는 재고 수정 시 달라질 수 있음</span></div>
      </div>
      <p className="fashion-planning-tally"><b>추가 발주 검토 {extraOrderCount}종</b> · <b>준비 물량 과다 {excessCount}종</b></p>
      <details className="fashion-planning-formula"><summary>판매율 계산 기준</summary>기간 판매 수량 ÷ (기초재고 + 입고 + 재판매 가능 반품 − 공급사 반품 − 폐기 + 재고 조정). 출시 전 신상은 제외합니다.</details>
      <div className="fashion-planning-subhead"><div><h3>상품별 60일 판매율</h3></div><label>상품군 <select value={salesGroup} onChange={(e) => setSalesGroup(e.target.value)}><option value="SS">여름 잔여</option><option value="EV">겨울 이벤트</option></select></label></div>
      <div className="fashion-planning-table-wrap"><table className="data-table fashion-planning-table"><thead><tr><th>상품</th><th>판매 가능 수량</th><th>60일 판매</th><th>기간 판매율</th><th>마감 재고</th><th>자료 일치</th></tr></thead><tbody>{currentRows.map((item) => <tr key={item.sku}><td><b>{item.name.replace(/^\[[^\]]+\]\s*/, "")}</b><small>{item.sku}</small></td><td>{qty(item.opening_stock + item.receipts + item.customer_returns - item.removed_units)}개</td><td>{qty(item.sold_units)}개</td><td><SellThroughBar value={item.sell_through_pct} valid={item.reconciled_with_current_inputs}/></td><td>{qty(item.closing_stock)}개</td><td>{item.reconciled_with_current_inputs ? "일치" : "불일치"}</td></tr>)}</tbody></table></div>
      <div className="fashion-planning-controls">
        <div><h3>다음 F/W 물량 검토</h3><p>작년 비교 상품 기준 · 사용자 가정</p></div>
        <label>작년 대비 예상 수요 변화 <select value={growth} onChange={(e) => setGrowth(Number(e.target.value))}><option value={-30}>−30%</option><option value={-15}>−15%</option><option value={0}>동일</option><option value={15}>+15%</option><option value={30}>+30%</option><option value={50}>+50%</option></select></label>
        <label>목표 판매율 <select value={target} onChange={(e) => setTarget(Number(e.target.value))}><option value={70}>70%</option><option value={80}>80%</option><option value={85}>85%</option><option value={90}>90%</option><option value={95}>95%</option></select></label>
      </div>
      <div className="fashion-planning-table-wrap"><table className="data-table fashion-planning-table"><thead><tr><th>가을 신상</th><th>작년 비교 상품 판매율</th><th>현재 준비 물량</th><th>예상 수요</th><th>다음 검토</th><th/></tr></thead><tbody>{data.plans.map((plan) => <tr key={plan.sku} className={focus?.sku === plan.sku ? "selected-row" : ""}><td><button type="button" onClick={() => setSelected(plan.sku)}><b>{plan.name.replace(/^\[[^\]]+\]\s*/, "")}</b><small>{plan.sku}</small></button></td><td><SellThroughBar value={plan.prior_sell_through_pct}/><small>{qty(plan.prior_sold_units)} / {qty(plan.prior_available_units)}개</small></td><td>{qty(plan.current_supply)}개</td><td>{qty(plan.assumed_demand)}개</td><td><b>{plan.recommended_action}</b><small>{plan.additional_order_to_review ? `추가 ${qty(plan.additional_order_to_review)}개` : plan.excess_units_to_review ? `목표 초과 ${qty(plan.excess_units_to_review)}개` : "—"}</small></td><td><button type="button" aria-label={`${plan.name} 근거 보기`} onClick={() => setSelected(plan.sku)}><ArrowRight size={16}/></button></td></tr>)}</tbody></table></div>
      {focus && <div className="fashion-planning-detail">
        <div><span className="section-kicker">PLANNING EVIDENCE</span><h3>{focus.name.replace(/^\[[^\]]+\]\s*/, "")}</h3><p>비교 기준: {focus.reference_name} · 실제 동일 상품이 아닌 합성 비교 상품</p></div>
        <div className="fashion-planning-detail-grid">
          <div><small>작년 비교 상품</small><b>{qty(focus.prior_sold_units)}개 판매 / {qty(focus.prior_available_units)}개 판매 가능</b><span>매출 {won(focus.prior_revenue)} · 매출총이익 {won(focus.prior_gross_profit)}</span></div>
          <div><small>올해 신상 · 현재 입력</small><b>현재고 {qty(focus.current_stock)} + 입고 예정 {qty(focus.inbound_units)}</b><span>현재 준비 물량 {qty(focus.current_supply)}개</span></div>
          <div><small>다음 기획 · 사용자 가정</small><b>수요 {qty(focus.assumed_demand)}개 / 목표 물량 {qty(focus.target_supply)}개</b><span>추가 발주 {qty(focus.additional_order_to_review)}개 · 목표 초과 {qty(focus.excess_units_to_review)}개 · 미입고 조정 검토 최대 {qty(focus.inbound_reduction_to_review)}개</span></div>
          <div><small>가정에 따른 계산</small><b>예상 잔여 {qty(focus.projected_end_stock)}개</b><span>예상 매출 {won(focus.projected_revenue)} · 매출총이익 {won(focus.projected_gross_profit)}</span></div>
        </div>
        <div className="fashion-plan-chart" role="img" aria-label={`현재 준비 물량 ${focus.current_supply}개, 목표 준비 물량 ${focus.target_supply}개, 가정 수요 ${focus.assumed_demand}개`}>
          <div className="fashion-plan-chart-head"><h4>현재 물량과 기획 목표</h4><small>세 막대는 같은 눈금입니다 · 단위: 개</small></div>
          {([['현재 준비', focus.current_supply, 'supply'], ['목표 물량', focus.target_supply, 'target'], ['가정 수요', focus.assumed_demand, 'demand']] as const).map(([label, value, kind]) => <div className="fashion-plan-chart-row" key={kind}><span>{label}</span><div className="fashion-plan-chart-track"><span className={`fashion-plan-chart-fill ${kind}`} style={{ width: barWidth(value, Math.max(focus.current_supply, focus.target_supply, focus.assumed_demand)) }}/></div><b>{qty(value)}개</b></div>)}
          <p>{focus.additional_order_to_review > 0 ? `목표 물량까지 ${qty(focus.additional_order_to_review)}개 부족합니다. 발주 가능 여부를 확인하세요.` : focus.excess_units_to_review > 0 ? `목표 물량보다 ${qty(focus.excess_units_to_review)}개 많습니다. 입고 예정 조정 가능량을 확인하세요.` : '현재 준비 물량이 목표 물량과 같습니다.'}</p>
        </div>
        {focus.projected_revenue > 0 && <div className="fashion-profit-chart" role="img" aria-label={`가정 매출 ${won(focus.projected_revenue)} 중 상품 원가 ${won(focus.projected_revenue - focus.projected_gross_profit)}, 매출총이익 ${won(focus.projected_gross_profit)}`}>
          <div className="fashion-plan-chart-head"><h4>가정 매출의 구성</h4><small>상품 원가와 매출총이익 · 실제 성과 아님</small></div>
          <div className="fashion-profit-track"><span className="cost" style={{ width: barWidth(focus.projected_revenue - focus.projected_gross_profit, focus.projected_revenue) }}/><span className="profit" style={{ width: barWidth(focus.projected_gross_profit, focus.projected_revenue) }}/></div>
          <div className="fashion-profit-legend"><span><i className="cost"/>상품 원가 {won(focus.projected_revenue - focus.projected_gross_profit)}</span><span><i className="profit"/>매출총이익 {won(focus.projected_gross_profit)}</span></div>
        </div>}
        {flow && <p className="fashion-planning-flow">올해 신상 60일 수불: 기초 {qty(flow.opening_stock)} + 입고 {qty(flow.receipts)} + 고객 반품 {qty(flow.customer_returns)} − 판매 {qty(flow.sold_units)} − 반품·폐기 {qty(flow.removed_units)} = 마감 {qty(flow.closing_stock)}개. {flow.reconciled_with_current_inputs ? "현재 입력과 일치합니다." : "현재 입력과 차이가 있어 원본 수불을 현재 실적으로 해석하지 마세요."}</p>}
      </div>}
      {focus && <div className="fashion-planning-decision">
        <div><h3>내 판단 기록하기</h3><p>선택한 상품의 비교 자료와 가정을 바탕으로 실제로 무엇을 확인할지 적어 보세요.</p></div>
        <label htmlFor="planning-rationale">판단 이유와 확인할 조건</label>
        <textarea id="planning-rationale" rows={3} maxLength={1000} value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="예: 작년 판매율은 높았지만 올해 입고 예정량이 많아, 추가 발주 전 예약 주문과 생산 일정을 확인한다." />
        <button type="button" className="button button-primary" disabled={busy || rationale.trim().length < 5} onClick={() => void saveDecision()}>{busy ? "저장 중…" : "이 판단 저장"}</button>
        {saved && <p role="status" className="fashion-planning-saved">{saved}</p>}
      </div>}
      <div className="fashion-planning-history"><h3>저장한 기획 판단</h3>{decisions.length === 0 ? <p>아직 저장한 판단이 없습니다.</p> : <ul>{decisions.slice(0, 5).map((item) => <li key={item.id}><b>{item.name.replace(/^\[[^\]]+\]\s*/, "")}</b><span>수요 가정 {item.growth_pct > 0 ? "+" : ""}{item.growth_pct}% · 목표 판매율 {item.target_sell_through_pct}% · 추가 발주 검토 {qty(item.additional_order_to_review)}개</span><p>{item.rationale}</p></li>)}</ul>}</div>
      <p className="fashion-planning-warning"><TriangleAlert size={16}/>{data.warning} 추천 수량과 예상 이익은 시나리오 계산이며 실제 발주·매출 성과가 아닙니다.</p>
    </>}
  </section>;
}
