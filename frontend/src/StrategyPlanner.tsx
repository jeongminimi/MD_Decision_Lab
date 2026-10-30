import { useState } from "react";
import "./strategy-planner.css";

type StrategyId = "discount" | "campaign" | "display" | "live" | "replenish";
type Placement = "online" | "store";
type Option = { discount_pct: number; expected_units_30d: number; purchase_units: number };
export type StrategyResult = {
  feasible: boolean;
  estimated_revenue_krw: number | null;
  estimated_gross_profit_krw: number | null;
  estimated_remaining_units: number | null;
  expected_units_30d: number;
  first_gap_date: string | null;
  max_gap_units: number;
};

const strategies: { id: StrategyId; title: string; hint: string }[] = [
  { id: "discount", title: "가격 할인", hint: "할인 폭을 정하고 이익을 확인" },
  { id: "campaign", title: "온라인 기획전", hint: "기획전 노출과 할인을 함께 검토" },
  { id: "display", title: "상품 노출", hint: "상세페이지 또는 매장 진열 검토" },
  { id: "live", title: "라이브 노출", hint: "방송에서 상품을 소개할지 검토" },
  { id: "replenish", title: "추가 매입", hint: "판매에 필요한 물량 확보 검토" },
];

const format = (value: number) => new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 }).format(value);
const won = (value: number) => `${value < 0 ? "−" : ""}₩${format(Math.abs(value))}`;

export default function StrategyPlanner({ observedUnits, ready, canReorder, compareOption, saveDecision }: {
  observedUnits: number;
  ready: boolean;
  canReorder: boolean;
  compareOption: (option: Option) => Promise<StrategyResult>;
  saveDecision: (decision: Option & {
    baseline_expected_units_30d: number; selected_option: "A" | "B";
    action: string; rationale: string;
  }) => Promise<void>;
}) {
  const [strategy, setStrategy] = useState<StrategyId>("campaign");
  const [placement, setPlacement] = useState<Placement>("online");
  const [baselineUnits, setBaselineUnits] = useState(observedUnits);
  const [plannedUnits, setPlannedUnits] = useState(observedUnits);
  const [discount, setDiscount] = useState(15);
  const [purchase, setPurchase] = useState(0);
  const [results, setResults] = useState<[StrategyResult, StrategyResult] | null>(null);
  const [choice, setChoice] = useState<"A" | "B">("B");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const pricePlan = strategy === "discount" || strategy === "campaign";
  const purchasePlan = strategy === "replenish";
  const proposed: Option = {
    discount_pct: pricePlan ? discount : 0,
    expected_units_30d: plannedUnits,
    purchase_units: purchasePlan ? purchase : 0,
  };
  const action = strategy === "discount" ? "가격 할인 검토" :
    strategy === "campaign" ? "온라인 기획전 검토" :
      strategy === "display" ? placement === "online" ? "온라인 상세 노출 검토" : "매장 진열 검토" :
        strategy === "live" ? "라이브 노출 검토" : "추가 매입 검토";
  const valid = ready && Number.isInteger(baselineUnits) && baselineUnits >= 0 &&
    Number.isInteger(plannedUnits) && plannedUnits >= 0 &&
    Number.isInteger(purchase) && purchase >= 0 && discount >= 0 && discount <= 70;

  function chooseStrategy(id: StrategyId) {
    if (id === "replenish" && !canReorder) return;
    setStrategy(id);
    setDiscount(id === "discount" || id === "campaign" ? 15 : 0);
    setPurchase(0);
    setResults(null);
    setChoice("B");
    setMessage("");
  }

  async function calculate() {
    if (!valid) return;
    setBusy(true); setMessage("");
    try {
      const current: Option = { discount_pct: 0, expected_units_30d: baselineUnits, purchase_units: 0 };
      const pair = await Promise.all([compareOption(current), compareOption(proposed)]);
      setResults(pair as [StrategyResult, StrategyResult]);
    } catch (error) { setMessage(error instanceof Error ? error.message : "계산을 완료하지 못했습니다."); }
    finally { setBusy(false); }
  }

  async function save() {
    if (!results || reason.trim().length < 5 || !results[choice === "A" ? 0 : 1].feasible) return;
    setBusy(true); setMessage("");
    try {
      await saveDecision({ ...proposed, baseline_expected_units_30d: baselineUnits,
        selected_option: choice, action: choice === "A" ? "현재 운영 유지" : action, rationale: reason.trim() });
      setReason(""); setMessage("전략과 판단 이유를 저장했습니다.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "판단을 저장하지 못했습니다."); }
    finally { setBusy(false); }
  }

  const maximum = Math.max(1, ...(results || []).map((result) => Math.max(0, result.estimated_gross_profit_krw || 0)));
  const difference = results && results.every((result) => result.estimated_gross_profit_krw != null)
    ? results[1].estimated_gross_profit_krw! - results[0].estimated_gross_profit_krw! : null;

  return <section className="strategy-planner" aria-label="판매 및 마케팅 전략 수립">
    <header className="strategy-heading"><div><span className="strategy-eyebrow">판매 및 마케팅 전략</span><h3>상품별 판매 전략 비교</h3><p>전략을 고르고 예상 판매량을 입력하면, 현재 운영과 이익·재고를 비교할 수 있습니다.</p></div><span className="strategy-badge">MD 판단 시뮬레이션</span></header>

    <div className="strategy-step"><div className="strategy-step-title"><span>1</span><div><b>검토할 행동 선택</b><small>할인, 기획전, 노출 또는 물량 확보</small></div></div>
      <div className="strategy-cards">{strategies.map((entry) => <button type="button" key={entry.id}
        className={strategy === entry.id ? "selected" : ""} aria-pressed={strategy === entry.id}
        disabled={entry.id === "replenish" && !canReorder} onClick={() => chooseStrategy(entry.id)}>
        <strong>{entry.title}</strong><small>{entry.id === "replenish" && !canReorder ? "재발주 불가 상품" : entry.hint}</small>
      </button>)}</div>
    </div>

    <div className="strategy-step"><div className="strategy-step-title"><span>2</span><div><b>30일 판매를 예상하기</b><small>최근 30일 판매 {format(observedUnits)}개를 참고해 직접 바꿔보세요.</small></div></div>
      <div className="strategy-assumptions"><label><span>현재 운영 유지 시</span><strong>예상 판매량</strong><input type="number" min="0" step="1" value={baselineUnits} onChange={(event) => { setBaselineUnits(Number(event.target.value)); setResults(null); }}/><small>가격·노출·매입을 바꾸지 않는 경우</small></label>
        <label><span>선택한 전략: {action}</span><strong>예상 판매량</strong><input type="number" min="0" step="1" value={plannedUnits} onChange={(event) => { setPlannedUnits(Number(event.target.value)); setResults(null); }}/><small>전략 후 얼마나 팔릴지 MD가 가정한 수량</small></label></div>
      {strategy === "display" && <div className="strategy-extra"><label>노출 위치<select value={placement} onChange={(event) => { setPlacement(event.target.value as Placement); setResults(null); }}><option value="online">온라인 상세페이지</option><option value="store">오프라인 매장 진열</option></select></label></div>}
      {pricePlan && <div className="strategy-extra"><label>전략 할인율 (%)<input type="number" min="0" max="70" step="1" value={discount} onChange={(event) => { setDiscount(Number(event.target.value)); setResults(null); }}/></label><small>판매가를 낮추면 개당 이익도 줄어듭니다.</small></div>}
      {purchasePlan && <div className="strategy-extra"><label>추가 매입량 (개)<input type="number" min="0" step="1" value={purchase} onChange={(event) => { setPurchase(Number(event.target.value)); setResults(null); }}/></label><small>입고 소요일을 반영해 재고 공백을 확인합니다.</small></div>}
      {!ready && <p className="strategy-warning">계산하려면 위쪽에 재고·판매가·원가를 먼저 입력하세요.</p>}
      <button type="button" className="strategy-calculate" disabled={!valid || busy} onClick={() => void calculate()}>{busy ? "계산 중…" : "예상 이익·재고 계산"}</button>
    </div>

    {results && <div className="strategy-step strategy-results"><div className="strategy-step-title"><span>3</span><div><b>숫자를 보고 판단하기</b><small>실행 결과가 아닌 입력한 조건의 예상치입니다.</small></div></div>
      <div className="strategy-result-grid">{results.map((result, index) => <button type="button" key={index}
        className={`strategy-result ${choice === (index === 0 ? "A" : "B") ? "selected" : ""}`}
        aria-pressed={choice === (index === 0 ? "A" : "B")} onClick={() => setChoice(index === 0 ? "A" : "B")}>
        <span className="strategy-result-title">{index === 0 ? "현재 운영 유지" : action}</span>
        <span className="strategy-result-profit">{result.feasible && result.estimated_gross_profit_krw != null ? won(result.estimated_gross_profit_krw) : "재고 부족"}</span>
        <span className="strategy-result-caption">예상 매출총이익</span>
        <span className="strategy-result-bar"><i style={{ width: `${result.feasible ? Math.max(0, (result.estimated_gross_profit_krw || 0) / maximum * 100) : 0}%` }}/></span>
        <span className="strategy-result-facts"><span>예상 매출 <b>{result.estimated_revenue_krw == null ? "계산 불가" : won(result.estimated_revenue_krw)}</b></span><span>남는 재고 <b>{result.estimated_remaining_units == null ? "계산 불가" : `${format(result.estimated_remaining_units)}개`}</b></span></span>
        {result.first_gap_date && <span className="strategy-gap">{result.first_gap_date}부터 재고 공백 · 최대 {format(result.max_gap_units)}개</span>}
      </button>)}</div>
      <div className="strategy-difference"><span>제안 전략 − 현재 운영</span><strong>{difference == null ? "재고 공백으로 비교 불가" : `${difference >= 0 ? "+" : ""}${won(difference)}`}</strong><small>예상 매출총이익 차이</small></div>
      <label className="strategy-reason">이 판단을 선택한 이유<textarea rows={2} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="예: 할인 후 30개 판매를 가정해도 이익이 줄어 현재가를 유지한다."/></label>
      <button type="button" className="strategy-save" disabled={busy || reason.trim().length < 5 || !results[choice === "A" ? 0 : 1].feasible} onClick={() => void save()}>{choice === "A" ? "현재 운영 유지" : action} 판단 저장</button>
      <p className="strategy-limit">판매량은 직접 입력한 가정입니다. 방문·노출 수가 없어 전환율은 계산하지 않으며, 광고·제작비는 매출총이익에 포함되지 않습니다.</p>
    </div>}
    {message && <p className="strategy-message" role="status">{message}</p>}
  </section>;
}
