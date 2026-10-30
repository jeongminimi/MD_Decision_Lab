import { useEffect, useState } from "react";
import { peerApi, type SeasonGroup, type SeasonPlan, type SeasonReview } from "./workApi";
import "./season-planner.css";

const fmt = (value: number) => new Intl.NumberFormat("ko-KR").format(value);
const groupKey = (group: SeasonGroup) => `${group.section}\u0000${group.category}`;

export default function SeasonPlanner({ datasetId }: { datasetId: number }) {
  const [scope, setScope] = useState<"apparel" | "accessory">("apparel");
  const [groups, setGroups] = useState<SeasonGroup[]>([]);
  const [sectionChoice, setSectionChoice] = useState("");
  const [group, setGroup] = useState("");
  const [review, setReview] = useState<SeasonReview | null>(null);
  const [plans, setPlans] = useState<SeasonPlan[]>([]);
  const [chosen, setChosen] = useState<Record<string, number>>({});
  const [rationale, setRationale] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let live = true;
    void Promise.all([peerApi.groups(datasetId), peerApi.plans(datasetId)]).then(([nextGroups, nextPlans]) => {
      if (live) { setGroups(nextGroups); setPlans(nextPlans); setError(""); }
    }).catch((err) => { if (live) setError(err instanceof Error ? err.message : "자료를 불러오지 못했습니다."); });
    return () => { live = false; };
  }, [datasetId]);

  const available = groups.filter((item) => item.scope === scope);
  const sections = [...new Set(available.map((item) => item.section))];
  const categories = available.filter((item) => item.section === sectionChoice);
  useEffect(() => {
    setSectionChoice(available[0]?.section || "");
    setGroup(available[0] ? groupKey(available[0]) : "");
  }, [scope, groups]);
  useEffect(() => {
    const found = groups.find((item) => groupKey(item) === group);
    setReview(null); setChosen({}); setNotice("");
    if (!found) return;
    let live = true;
    void peerApi.review(datasetId, found.section, found.category, found.scope).then((data) => {
      if (live) { setReview(data); setError(""); }
    }).catch((err) => { if (live) setError(err instanceof Error ? err.message : "지난 시즌 판매를 불러오지 못했습니다."); });
    return () => { live = false; };
  }, [datasetId, group, groups]);

  function toggle(sku: string) {
    setChosen((current) => {
      const next = { ...current };
      if (sku in next) delete next[sku];
      else if (Object.keys(next).length < 5) next[sku] = 1;
      return next;
    });
  }

  async function save() {
    if (!review) return;
    const entries = Object.entries(chosen);
    if (entries.length < 2 || entries.length > 5) { setError("기획 후보를 2~5종 선택해 주세요."); return; }
    if (entries.some(([, units]) => !Number.isInteger(units) || units < 1)) { setError("각 상품의 준비 물량을 1개 이상 입력해 주세요."); return; }
    if (rationale.trim().length < 5) { setError("판단 이유를 5자 이상 적어 주세요."); return; }
    setSaving(true); setError(""); setNotice("");
    try {
      await peerApi.savePlan({ dataset_id: datasetId, section: review.section, category: review.category, scope: review.scope,
        candidates: entries.map(([sku, planned_units]) => ({ sku, planned_units })), rationale: rationale.trim() });
      setPlans(await peerApi.plans(datasetId));
      setNotice("기획안과 당시 판매 근거를 저장했습니다.");
    } catch (err) { setError(err instanceof Error ? err.message : "기획안을 저장하지 못했습니다."); }
    finally { setSaving(false); }
  }

  const maxWeek = Math.max(1, ...(review?.weekly.flatMap((item) => [item.units_2019, item.units_2020]) ?? [1]));
  return <section className="panel work-panel season-planner">
    <div className="work-panel-heading"><div><span className="section-kicker">NEXT SEASON · H&M 관측 판매</span><h2>유사 상품을 보고 다음 시즌 물량 검토</h2><small>같은 섹션·종류 여러 상품의 지난 시즌과 올해 판매를 비교합니다.</small></div></div>
    <div className="season-filters"><div role="group" aria-label="상품 범위"><button type="button" className={scope === "apparel" ? "active" : ""} onClick={() => setScope("apparel")}>의류</button><button type="button" className={scope === "accessory" ? "active" : ""} onClick={() => setScope("accessory")}>액세서리</button></div><label>섹션 <select value={sectionChoice} onChange={(event) => { const next = event.target.value; setSectionChoice(next); const first = available.find((item) => item.section === next); setGroup(first ? groupKey(first) : ""); }}>{sections.map((section) => <option key={section} value={section}>{section}</option>)}</select></label><label>종류 <select value={group} onChange={(event) => setGroup(event.target.value)}>{categories.map((item) => <option key={groupKey(item)} value={groupKey(item)}>{item.category} ({fmt(item.products)}종)</option>)}</select></label></div>
    {error && <p className="work-error" role="alert">{error}</p>}{notice && <p className="season-notice" role="status">{notice}</p>}
    {review && <>
      <div className="season-summary"><span>2019년 7~8월 <b>{fmt(review.totals["2019"])}개</b><small>판매 관측 {fmt(review.totals.active_2019)}종</small></span><span>2020년 7~8월 <b>{fmt(review.totals["2020"])}개</b><small>판매 관측 {fmt(review.totals.active_2020)}종</small></span></div>
      <div className="season-chart" aria-label="2019년과 2020년 주간 판매량 비교">{review.weekly.map((week) => <div className="season-week" key={week.week_index}><small>{week.start_2020.slice(5)}</small><div className="season-bars"><span style={{ height: `${Math.max(2, week.units_2019 / maxWeek * 100)}%` }} title={`2019년 ${fmt(week.units_2019)}개`}/><span style={{ height: `${Math.max(2, week.units_2020 / maxWeek * 100)}%` }} title={`2020년 ${fmt(week.units_2020)}개`}/></div><b>{fmt(week.units_2019)} / {fmt(week.units_2020)}</b></div>)}</div>
      <p className="season-legend"><i/> 2019년 <i/> 2020년 · 막대는 각 연도 7~8월의 같은 주차 판매 수량</p>
      <h3>기획 후보 선택 <small>2~5종 · 선택한 상품마다 준비 물량 입력</small></h3>
      <div className="table-scroll"><table className="data-table work-table"><thead><tr><th>선택</th><th>상품</th><th>2019년 7~8월</th><th>2020년 7~8월</th><th>최근 14일</th><th>준비 물량</th></tr></thead><tbody>{review.candidates.map((item) => <tr key={item.sku}><td><input type="checkbox" aria-label={`${item.name} 기획 후보 선택`} checked={item.sku in chosen} onChange={() => toggle(item.sku)}/></td><td><b>{item.name}</b><small>{item.sku}</small></td><td>{fmt(item.units_2019)}개</td><td>{fmt(item.units_2020)}개</td><td>{fmt(item.units_14d)}개</td><td>{item.sku in chosen ? <input className="season-qty" type="number" min="1" step="1" aria-label={`${item.name} 준비 물량`} value={chosen[item.sku]} onChange={(event) => setChosen((current) => ({ ...current, [item.sku]: Number(event.target.value) }))}/> : "—"}</td></tr>)}</tbody></table></div>
      <label className="season-reason">기획 판단 이유<textarea value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="예: 작년보다 올해 같은 상품군의 판매가 늘었고, 후보 3종의 최근 14일 반응도 높아 다음 시즌 물량을 검토합니다."/></label>
      <button type="button" className="button button-primary" onClick={() => void save()} disabled={saving}>{saving ? "저장 중…" : `기획안 저장 · ${fmt(Object.values(chosen).reduce((sum, value) => sum + (Number.isFinite(value) ? value : 0), 0))}개`}</button>
      <details className="work-source-details"><summary>비교 기준</summary><p>{review.note} 준비 물량은 MD의 기획 가정이며 실제 발주가 아닙니다. 2020년 8월 31일 이후 판매는 사용하지 않았습니다.</p></details>
    </>}
    {plans.length > 0 && <details className="season-saved"><summary>저장한 다음 시즌 기획안 {plans.length}건</summary>{plans.map((plan) => <article key={plan.id}><b>{plan.section} · {plan.category}</b><span>{plan.candidates.length}종 · 준비 물량 {fmt(plan.planned_units)}개</span><small>{plan.candidates.map((item) => `${plan.sales_snapshot.candidates.find((source) => source.sku === item.sku)?.name || item.sku} ${fmt(item.planned_units)}개`).join(" · ")}</small><p>{plan.rationale}</p><small>기준일 {plan.as_of_date} · 당시 판매 근거 저장</small></article>)}</details>}
  </section>;
}
