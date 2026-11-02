import { useEffect, useState } from "react";
import { operationApi, type WorkOperation } from "./workApi";

type DecisionRef = { id: number; name: string; action: string; as_of_date: string };
const n = (v: number) => new Intl.NumberFormat("ko-KR").format(v);
const money = (v: number | null) => v == null ? "자료 없음" : `₩${n(v)}`;
const kinds: Record<string, string> = { ordered: "발주 완료", received: "입고", sale: "판매", stock_count: "재고 실사",
  started: "행사 시작", finished: "행사 종료", cancelled: "취소" };
const statuses: Record<string, string> = { planned: "계획", ordered: "발주 완료", partial: "일부 입고",
  received: "입고 완료", active: "진행 중", finished: "종료", cancelled: "취소" };

export default function OperationsPanel({ datasetId, source, decisions }: {
  datasetId: number; source: "sim" | "work"; decisions: DecisionRef[];
}) {
  const [items, setItems] = useState<WorkOperation[]>([]);
  const [decisionId, setDecisionId] = useState(0);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [units, setUnits] = useState("");
  const [arrival, setArrival] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const eligible = decisions.filter(d => /매입|할인|기획전/.test(d.action));
  const selected = eligible.find(d => d.id === decisionId);
  const replenish = selected?.action.includes("매입");
  useEffect(() => { void operationApi.list(datasetId).then(setItems).catch(e => setError(String(e))); }, [datasetId]);
  function choose(id: number) {
    setDecisionId(id);
    const d = eligible.find(row => row.id === id);
    setStart(d?.as_of_date || ""); setEnd(""); setUnits(""); setArrival(""); setError("");
  }
  async function create() {
    if (!selected || !start) return;
    setBusy(true); setError("");
    try {
      await operationApi.create({ decision_source: source, decision_id: selected.id, planned_start: start,
        ...(replenish ? { planned_units: Number(units), expected_receipt_date: arrival } : { planned_end: end }), note });
      setItems(await operationApi.list(datasetId)); choose(0); setNote("");
    } catch (e) { setError(e instanceof Error ? e.message : "계획을 저장하지 못했습니다."); }
    finally { setBusy(false); }
  }
  return <section className="panel work-panel" aria-label="실행 및 결과 기록">
    <div className="work-panel-heading"><div><h2>실행 및 결과 기록</h2>
      <small>판단을 계획으로 연결하고, 실제 진행 날짜와 수량을 계속 기록합니다.</small></div></div>
    {source === "sim" && <p className="work-empty">H&M 상품의 기존 재고·발주는 가상 운영 조건입니다. 아래 실행·입고·판매값도 사용자가 입력한 시나리오 기록으로 구분됩니다.</p>}
    {eligible.length > 0 && <div className="operation-form">
      <label>저장한 판단<select value={decisionId} onChange={e => choose(Number(e.target.value))}><option value={0}>판단 선택</option>
        {eligible.map(d => <option key={d.id} value={d.id}>{d.name} · {d.action} · {d.as_of_date}</option>)}</select></label>
      {selected && <><label>{replenish ? "발주 예정일" : "행사 시작일"}<input type="date" min={selected.as_of_date} value={start} onChange={e => setStart(e.target.value)}/></label>
        {replenish ? <><label>발주 수량<input type="number" min="1" value={units} onChange={e => setUnits(e.target.value)}/></label>
          <label>예상 입고일<input type="date" min={start} value={arrival} onChange={e => setArrival(e.target.value)}/></label></>
          : <label>행사 종료일<input type="date" min={start} value={end} onChange={e => setEnd(e.target.value)}/></label>}
        <label>실행 메모<input value={note} onChange={e => setNote(e.target.value)}/></label>
        <button className="button button-primary" type="button" disabled={busy || !start || (replenish ? !arrival || Number(units) < 1 : !end)} onClick={() => void create()}>실행 계획 저장</button></>}
    </div>}
    {error && <p className="work-error" role="alert">{error}</p>}
    {items.length ? <div className="work-decision-list">{items.map(op => <OperationRow key={op.id} item={op} onChanged={async () => setItems(await operationApi.list(datasetId))}/>)}</div>
      : <p className="work-empty">저장한 실행 계획이 없습니다.</p>}
  </section>;
}

function OperationRow({ item, onChanged }: { item: WorkOperation; onChanged: () => Promise<void> }) {
  const [kind, setKind] = useState(item.kind === "replenish" ? "received" : "started");
  const [date, setDate] = useState(item.planned_start);
  const [units, setUnits] = useState("");
  const [revenue, setRevenue] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const eventKinds = item.kind === "replenish" ? ["ordered", "received", "sale", "stock_count", "cancelled"]
    : ["started", "finished", "sale", "stock_count", "cancelled"];
  async function save() {
    setBusy(true); setError("");
    try {
      await operationApi.event(item.id, { event_date: date, kind,
        ...(["received", "sale", "stock_count"].includes(kind) ? { units: Number(units) } : {}),
        ...(kind === "sale" && revenue !== "" ? { revenue_krw: Number(revenue) } : {}),
        note, client_key: crypto.randomUUID() });
      setUnits(""); setRevenue(""); setNote(""); await onChanged();
    } catch (e) { setError(e instanceof Error ? e.message : "진행 기록을 저장하지 못했습니다."); }
    finally { setBusy(false); }
  }
  return <article className="work-decision-row"><div><b>{item.name} · {item.kind === "replenish" ? "추가 매입" : item.kind === "campaign" ? "온라인 기획전" : "가격 할인"}</b>
    <span>{statuses[item.status] || item.status}{item.source_label === "scenario_record" ? " · 시나리오 입력" : ""}</span></div>
    <small>계획 {item.planned_start}{item.planned_end ? `~${item.planned_end}` : ""}{item.expected_receipt_date ? ` · 입고 예정 ${item.expected_receipt_date}` : ""}</small>
    {item.kind === "replenish" ? <p>발주 계획 {n(item.planned_units || 0)}개 · 입고 기록 {n(item.received_units)}개 · 미입고 {n((item.planned_units || 0) - item.received_units)}개</p>
      : <p>행사 {item.period_days}일 예상 판매 {n(item.expected_period_units || 0)}개 · 기록된 판매 {n(item.recorded_sales_units)}개 · 기간 예상 매출 {money(item.expected_period_revenue_krw)} · 기록된 매출 {money(item.recorded_revenue_krw)}</p>}
    {item.kind !== "replenish" && item.events.some(e => e.kind === "sale") && <small>기간 예상 대비 기록된 판매 {item.expected_period_units == null ? "비교 불가" : `${item.recorded_sales_units - item.expected_period_units >= 0 ? "+" : ""}${n(item.recorded_sales_units - item.expected_period_units)}개`}{item.recorded_revenue_krw != null && item.expected_period_revenue_krw != null ? ` · 매출 ${item.recorded_revenue_krw - item.expected_period_revenue_krw >= 0 ? "+" : ""}${money(item.recorded_revenue_krw - item.expected_period_revenue_krw)}` : ""} · 30일 예상을 기간 일수로 균등 환산한 값이며 행사의 인과 효과를 뜻하지 않습니다.</small>}
    <small>시작 재고 {item.opening_stock == null ? "자료 없음" : `${n(item.opening_stock)}개`} · 기록 기준 현재 재고 {item.current_stock == null ? "자료 없음" : `${n(item.current_stock)}개`} · 기간 예상 이익 {money(item.expected_period_profit_krw)} · 기록 기준 이익 {money(item.recorded_profit_krw)}</small>
    <small>재고는 이 상품의 실행 계획에 입력한 입고·판매·실사를 날짜순으로 반영합니다. 빠진 거래가 있으면 재고 실사로 보정하세요.</small>
    <div className="operation-form"><label>진행 내용<select value={kind} onChange={e => setKind(e.target.value)}>{eventKinds.map(k => <option key={k} value={k}>{kinds[k]}</option>)}</select></label>
      <label>날짜<input type="date" min={item.planned_start} value={date} onChange={e => setDate(e.target.value)}/></label>
      {["received", "sale", "stock_count"].includes(kind) && <label>수량<input type="number" min="0" value={units} onChange={e => setUnits(e.target.value)}/></label>}
      {kind === "sale" && <label>실제 매출액(선택)<input type="number" min="0" value={revenue} onChange={e => setRevenue(e.target.value)}/></label>}
      <label>메모<input value={note} onChange={e => setNote(e.target.value)}/></label>
      <button type="button" className="button button-secondary" disabled={busy || !date || (["received", "sale", "stock_count"].includes(kind) && units === "")} onClick={() => void save()}>진행 기록 저장</button></div>
    {item.events.length > 0 && <div className="operation-events">{item.events.map(e => <small key={e.id}>{e.event_date} · {kinds[e.kind]}{e.units != null ? ` ${n(e.units)}개` : ""}{e.stock_after != null ? ` · 기록 기준 재고 ${n(e.stock_after)}개` : ""}{e.revenue_krw != null ? ` · 매출 ${money(e.revenue_krw)}` : ""}{e.note ? ` · ${e.note}` : ""}</small>)}</div>}
    {error && <p className="work-error" role="alert">{error}</p>}
  </article>;
}
