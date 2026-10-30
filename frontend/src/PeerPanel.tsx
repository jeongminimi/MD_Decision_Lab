import { useEffect, useState } from "react";
import { peerApi, type PeerContext } from "./workApi";
import "./peer.css";

const n = (value: number) => new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 }).format(value);

export default function PeerPanel({ datasetId, sku }: { datasetId: number; sku: string }) {
  const [data, setData] = useState<PeerContext | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setData(null); setError("");
    void peerApi.context(datasetId, sku).then((value) => { if (active) setData(value); })
      .catch((err) => { if (active) setError(err instanceof Error ? err.message : "동종 판매를 불러오지 못했습니다."); });
    return () => { active = false; };
  }, [datasetId, sku]);
  if (error) return <section className="panel work-panel"><h3>동종 판매 비교</h3><p className="work-empty">{error}</p></section>;
  if (!data) return <p className="work-empty">동종 상품 판매를 확인하는 중…</p>;
  if (data.scope === "other" || !data.comparison || !data.observed) return <section className="panel work-panel"><h3>동종 판매 비교</h3><p className="work-empty">{data.note}</p></section>;
  const c = data.comparison;
  const o = data.observed;
  const recentChange = o.prior_7d > 0 ? Math.round((o.units_7d / o.prior_7d - 1) * 100) : null;
  const top = data.top_peers || [];
  const max = Math.max(1, ...top.map((item) => item.units_14d), o.units_14d);
  return <section className="panel work-panel peer-panel" aria-label="동종 상품 판매 비교와 재고 검토">
    <div className="work-panel-heading"><div><span className="section-kicker">H&M 관측 · {data.as_of_date}</span><h3>동종 상품과 판매 비교</h3><small>{data.section} · {data.category} · 등록 {n(c.registered)}종 중 최근 14일 판매 관측 {n(c.active_14d)}종</small></div></div>
    <div className="peer-metrics">
      <div><small>최근 14일 판매 순위</small><b>{c.rank_14d == null ? "판매 없음" : `${n(c.rank_14d)}위 / ${n(c.active_14d)}종`}</b><span>이 상품 {n(o.units_14d)}개 · 동종 중앙값 {c.median_14d == null ? "—" : `${n(c.median_14d)}개`}</span></div>
      <div><small>최근 7일 판매 순위</small><b>{c.rank_7d == null ? "판매 없음" : `${n(c.rank_7d)}위 / ${n(c.active_7d)}종`}</b><span>최근 {n(o.units_7d)}개 · 그 전 7일 {n(o.prior_7d)}개{recentChange == null ? "" : ` (${recentChange > 0 ? "+" : ""}${n(recentChange)}%)`}</span></div>
    </div>
    {!c.enough_peers && <p className="work-caveat">최근 14일 판매가 관측된 동종 상품이 20종 미만입니다. 순위를 판단 근거로 쓰기에는 비교 대상이 적습니다.</p>}
    <div className="peer-bars" aria-label="동종 상품 최근 14일 판매량">
      {top.map((item) => <div className="peer-bar-row" key={item.sku}><span>{item.name}</span><div><i style={{ width: `${Math.max(2, item.units_14d / max * 100)}%` }}/></div><b>{n(item.units_14d)}개</b></div>)}
      {!top.some((item) => item.sku === sku) && <div className="peer-bar-row selected"><span>선택 상품</span><div><i style={{ width: `${Math.max(2, o.units_14d / max * 100)}%` }}/></div><b>{n(o.units_14d)}개</b></div>}
    </div>
    {data.inventory && data.replenishment ? <div className="peer-stock"><h4>물량 검토 <small>가상 운영 조건</small></h4><p>기준일 재고 <b>{n(data.inventory.stock_on_hand)}개</b> · 입고 소요일 <b>{n(data.inventory.lead_time_days)}일</b> · 그 전 계획 입고 <b>{n(data.inventory.inbound_before_lead)}개</b></p><p>현재 속도에서 소진 예상 <b>{data.replenishment.cover_days == null ? "계산 불가" : data.replenishment.cover_days < 0.1 ? "0.1일 미만" : `약 ${n(data.replenishment.cover_days)}일`}</b> · {data.inventory.reorderable ? <>추가 매입 검토 기준 <b>{n(data.replenishment.review_units || 0)}개</b></> : <b>재발주 불가</b>}</p><small>{data.replenishment.note} 실제 H&M 물류 재고나 확정 발주량이 아닙니다.</small></div>
      : <p className="work-caveat">이 상품의 재고 자료는 없습니다. 판매 순위만 확인할 수 있으며, 재발주 판단에는 재고·입고 예정·리드타임 입력이 필요합니다.</p>}
    <small className="peer-note">{data.note}</small>
  </section>;
}
