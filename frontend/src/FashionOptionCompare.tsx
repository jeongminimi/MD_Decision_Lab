import { useState } from "react";
import { CheckCircle2, TriangleAlert } from "lucide-react";
import { api } from "./api";
import type { FashionAnalysis, FashionComparison, FashionDecision, FashionOptionInput } from "./types";
import "./fashion-compare.css";

const number = (value: number) => new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 }).format(value);
const won = (value: number) => `₩${number(value)}`;

interface FashionOptionCompareProps {
  item: FashionAnalysis;
  decisions: FashionDecision[];
  onDecisionSaved: () => Promise<void>;
}

export default function FashionOptionCompare({ item, decisions, onDecisionSaved }: FashionOptionCompareProps) {
  const isUpcoming = item.season_group === "2026FW";
  const isCarryover = item.season_group === "2025FW";
  const [discount, setDiscount] = useState(isUpcoming ? 0 : 15);
  const [expectedUnits, setExpectedUnits] = useState(item.units_30d);
  const [purchaseUnits, setPurchaseUnits] = useState(0);
  const [result, setResult] = useState<FashionComparison | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Decision state
  const [chosenOption, setChosenOption] = useState<"A" | "B" | "hold">("B");
  const [rationale, setRationale] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState("");

  function changed(update: () => void) {
    update();
    setResult(null);
    setError("");
    setSaveSuccess("");
  }

  async function compare() {
    setError("");
    setSaveSuccess("");
    if (!Number.isFinite(discount) || discount < 0 || discount > 70 || !Number.isInteger(expectedUnits)
      || expectedUnits < 0 || !Number.isInteger(purchaseUnits) || purchaseUnits < 0) {
      setError("할인율은 0~70%, 판매량과 매입량은 0 이상의 정수로 입력하세요.");
      return;
    }
    if (isUpcoming && expectedUnits === 0) {
      setError("출시 전 신상은 예상 30일 판매량을 1개 이상 가정해 주세요. 이 값은 실제 수요 예측이 아닙니다.");
      return;
    }
    const options: FashionOptionInput[] = [
      { label: "A · 현재 가격 유지", discount_pct: 0, expected_units_30d: item.units_30d, purchase_units: 0 },
      { label: "B · 변경안", discount_pct: discount, expected_units_30d: expectedUnits, purchase_units: item.reorderable ? purchaseUnits : 0 },
    ];
    setBusy(true);
    try {
      const res = await api.fashionCompareOptions(item.sku, options);
      setResult(res);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "두 안을 비교하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveDecision() {
    if (!rationale.trim() || rationale.trim().length < 5) {
      setError("판단 이유를 5자 이상 적어주세요.");
      return;
    }

    setSaving(true);
    setError("");
    setSaveSuccess("");

    try {
      const [a, b] = result?.options ?? [];
      const chosen = chosenOption === "A" ? a : chosenOption === "B" ? b : null;

      // Guardrail: If infeasible, never send arbitrary profit
      const isFeasible = chosen ? chosen.feasible : null;
      const estGrossProfit = (chosen && isFeasible) ? chosen.estimated_gross_profit : null;
      const estRevenue = (chosen && isFeasible) ? chosen.estimated_revenue : null;
      const estRemaining = (chosen && isFeasible) ? chosen.estimated_remaining_stock : null;

      await api.fashionCreateDecision({
        sku: item.sku,
        action_type: chosenOption === "A" ? "option_a" : chosenOption === "B" ? "option_b" : "hold",
        chosen_option: chosenOption,
        discount_pct: chosen ? chosen.discount_pct : null,
        expected_units_30d: chosen ? chosen.expected_units_30d : null,
        purchase_units: chosen ? chosen.purchase_units : 0,
        estimated_revenue: estRevenue,
        estimated_gross_profit: estGrossProfit,
        estimated_remaining_stock: estRemaining,
        feasible: isFeasible,
        rationale: rationale.trim(),
      });

      await onDecisionSaved();
      setSaveSuccess("선택한 조치와 계산 결과 스냅샷을 판단 기록에 안전하게 저장했습니다.");
      setRationale("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "판단을 저장하지 못했습니다.");
    } finally {
      setSaving(false);
    }
  }

  const [a, b] = result?.options ?? [];
  const difference = a?.estimated_gross_profit != null && b?.estimated_gross_profit != null
    ? b.estimated_gross_profit - a.estimated_gross_profit : null;
  const profitScale = Math.max(1, Math.abs(a?.estimated_gross_profit ?? 0), Math.abs(b?.estimated_gross_profit ?? 0));

  const productDecisions = decisions.filter((d) => d.sku === item.sku);

  return (
    <section className="fashion-compare" aria-labelledby="compare-title">
      <div className="fashion-compare-heading">
        <div>
          <span className="section-kicker">DECISION LAB · SCENARIO COMPARISON</span>
          <h3 id="compare-title">{isUpcoming ? "출시 전 판매량을 가정하면 재고는 충분할까요?" : isCarryover ? "남은 재고 안에서 어떤 판매안을 택할까요?" : "가격을 바꾸면 이익은 어떻게 달라질까요?"}</h3>
        </div>
      </div>

      <p className="fashion-compare-intro">A안: 현재가·최근 30일 판매량 {number(item.units_30d)}개 유지 · B안: 할인율과 판매량 입력. 모두 시나리오 가정입니다.</p>

      <div className="fashion-compare-simple-inputs">
        <label>
          B안 할인율 (%)
          <input
            aria-label="B안 할인율"
            type="number"
            min="0"
            max="70"
            step="1"
            value={discount}
            onChange={(event) => changed(() => setDiscount(Number(event.target.value)))}
          />
        </label>
        <label>
          B안 예상 30일 판매량 (가정)
          <input
            aria-label="B안 예상 판매량"
            type="number"
            min="0"
            step="1"
            value={expectedUnits}
            onChange={(event) => changed(() => setExpectedUnits(Number(event.target.value)))}
          />
        </label>
      </div>

      {item.reorderable && (
        <details className="fashion-compare-more">
          <summary>추가 매입도 가정해 보기 (선택)</summary>
          <label>
            B안 추가 매입량 (EA)
            <input
              aria-label="B안 추가 매입량"
              type="number"
              min="0"
              step="1"
              value={purchaseUnits}
              onChange={(event) => changed(() => setPurchaseUnits(Number(event.target.value)))}
            />
          </label>
        </details>
      )}
      {!item.reorderable && (
        <small className="fashion-compare-disabled-note">
          {isCarryover ? "이 상품은 작년 겨울 이월 상품으로 재발주할 수 없어 추가 매입을 비교하지 않습니다." : "이 상품은 재발주할 수 없어 추가 매입을 비교하지 않습니다."}
        </small>
      )}

      <div className="fashion-compare-actions">
        <button className="button button-primary" onClick={() => void compare()} disabled={busy}>
          {busy ? "계산 중…" : "결과 비교"}
        </button>
      </div>

      {error && <p className="fashion-compare-error" role="alert"><TriangleAlert size={16} /> {error}</p>}
      {saveSuccess && <p className="fashion-compare-success" role="status"><CheckCircle2 size={16} /> {saveSuccess}</p>}

      {result && (
        <div className="fashion-compare-summary" aria-live="polite">
          <div className="fashion-compare-visual">
            <h4>예상 매출총이익 비교</h4>
            <p>두 막대는 같은 눈금입니다. 할인과 판매량은 입력한 가정이며 실제 성과가 아닙니다.</p>
            {[a, b].map((option, index) => <div className="fashion-compare-visual-row" key={option.label}>
              <span>{index === 0 ? "A · 유지" : "B · 변경"}</span>
              <div className="fashion-compare-visual-track" role="img" aria-label={`${option.label} 예상 매출총이익 ${option.feasible && option.estimated_gross_profit != null ? won(option.estimated_gross_profit) : '재고 부족으로 계산 제외'}`}>
                {option.feasible && option.estimated_gross_profit != null && <span className={option.estimated_gross_profit < 0 ? "loss" : "gain"} style={{ width: `${Math.abs(option.estimated_gross_profit) / profitScale * 100}%` }} />}
              </div>
              <b>{option.feasible && option.estimated_gross_profit != null ? won(option.estimated_gross_profit) : "계산 제외"}</b>
            </div>)}
            {((a.estimated_gross_profit ?? 0) < 0 || (b.estimated_gross_profit ?? 0) < 0) && <small>붉은 막대는 매출총손실을 뜻하며 길이는 손익의 절댓값입니다.</small>}
          </div>
          <div className="fashion-compare-row fashion-compare-row-head">
            <span>비교 항목</span>
            <b>A · 현재 가격 유지</b>
            <b>B · 변경안</b>
          </div>
          <div className="fashion-compare-row">
            <span>적용 판매가</span>
            <b>{won(a.unit_price)}</b>
            <b>{won(b.unit_price)} {b.discount_pct > 0 && <small>({b.discount_pct}% 할인)</small>}</b>
          </div>
          <div className="fashion-compare-row">
            <span>판매량 가정</span>
            <b>{number(a.expected_units_30d)}개</b>
            <b>{number(b.expected_units_30d)}개</b>
          </div>
          <div className="fashion-compare-row">
            <span>사용 가능 재고</span>
            <b>{number(a.available_units)}개</b>
            <b>{number(b.available_units)}개{b.purchase_units > 0 ? ` (추가 매입 ${number(b.purchase_units)}개 포함)` : ""}</b>
          </div>
          <div className="fashion-compare-row">
            <span>예상 매출액</span>
            <b>{a.feasible ? won(a.estimated_revenue!) : `재고 ${number(a.shortfall_units)}개 부족`}</b>
            <b>{b.feasible ? won(b.estimated_revenue!) : `재고 ${number(b.shortfall_units)}개 부족`}</b>
          </div>
          <div className="fashion-compare-row">
            <span>예상 매출총이익</span>
            <b>{a.feasible ? won(a.estimated_gross_profit!) : "재고 부족 (계산 제외)"}</b>
            <b>{b.feasible ? won(b.estimated_gross_profit!) : "재고 부족 (계산 제외)"}</b>
          </div>
          <div className="fashion-compare-row">
            <span>예상 잔여 재고</span>
            <b>{a.feasible ? `${number(a.estimated_remaining_stock!)}개` : "계산 제외"}</b>
            <b>{b.feasible ? `${number(b.estimated_remaining_stock!)}개` : "계산 제외"}</b>
          </div>

          {difference != null && (
            <p className="fashion-compare-difference">
              B안의 예상 매출총이익은 A안보다 <b>{difference >= 0 ? "+" : "−"}{won(Math.abs(difference))}</b>입니다.
              {difference < 0 && <span> (할인으로 인한 단가 하락을 수량 증가가 충분히 메우지 못함)</span>}
            </p>
          )}

          {(!a.feasible || !b.feasible) && (
            <div className="fashion-compare-warning-box">
              <TriangleAlert size={16} />
              <span>가정한 판매량이 사용 가능 재고보다 많으면 이익 수치를 계산하거나 저장하지 않습니다.</span>
            </div>
          )}

          {b.purchase_units > 0 && (
            <p className="fashion-compare-cash-note">
              추가 매입에 필요한 현금: <b>{won(b.purchase_cash_required)}</b> (매출총이익과 별도로 표시합니다).
            </p>
          )}

          <div className="fashion-compare-disclaimer">
            <small>
              ※ {result.note}
            </small>
          </div>

          {/* 통합된 '내 판단 남기기' 섹션 */}
          <div className="fashion-decision-box" aria-labelledby="decision-box-title">
            <div className="fashion-decision-box-header">
              <span className="section-kicker">MD RECORD</span>
              <h4 id="decision-box-title">내 판단 남기기</h4>
              <p>선택한 안과 판단 이유를 저장합니다.</p>
            </div>

            <div className="fashion-option-picker" role="radiogroup" aria-label="선택할 조치안">
              <button
                type="button"
                role="radio"
                aria-checked={chosenOption === "A"}
                className={`picker-btn ${chosenOption === "A" ? "active" : ""}`}
                onClick={() => setChosenOption("A")}
              >
                <strong>A안 선택</strong>
                <span>현재가 유지 ({number(a.expected_units_30d)}개)</span>
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={chosenOption === "B"}
                className={`picker-btn ${chosenOption === "B" ? "active" : ""}`}
                onClick={() => setChosenOption("B")}
              >
                <strong>B안 선택</strong>
                <span>{b.discount_pct}% 할인 ({number(b.expected_units_30d)}개)</span>
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={chosenOption === "hold"}
                className={`picker-btn ${chosenOption === "hold" ? "active" : ""}`}
                onClick={() => setChosenOption("hold")}
              >
                <strong>보류 선택</strong>
                <span>추가 검토 및 관망</span>
              </button>
            </div>

            <div className="fashion-chosen-preview">
              {chosenOption === "A" && (
                <p>
                  <b>[A안 선택 스냅샷]</b> 할인 0% · 가정 판매 {number(a.expected_units_30d)}개 ·{" "}
                  예상 매출총이익: <b>{a.feasible ? won(a.estimated_gross_profit!) : "재고 부족 (계산 제외)"}</b> ·{" "}
                  예상 잔여 재고: {a.feasible ? `${number(a.estimated_remaining_stock!)}개` : "계산 제외"}
                </p>
              )}
              {chosenOption === "B" && (
                <p>
                  <b>[B안 선택 스냅샷]</b> 할인 {b.discount_pct}% · 가정 판매 {number(b.expected_units_30d)}개 ·{" "}
                  추가 매입: {b.purchase_units}개 ·{" "}
                  예상 매출총이익: <b>{b.feasible ? won(b.estimated_gross_profit!) : "재고 부족 (계산 제외)"}</b> ·{" "}
                  예상 잔여 재고: {b.feasible ? `${number(b.estimated_remaining_stock!)}개` : "계산 제외"}
                </p>
              )}
              {chosenOption === "hold" && (
                <p>
                  <b>[보류 선택 스냅샷]</b> 가격 및 판매량을 즉시 변경하지 않고 추가 시장 수요와 재고 추이를 모니터링합니다.
                </p>
              )}
            </div>

            <div className="fashion-decision-input-group">
              <label htmlFor="fashion-rationale-input">판단 이유 (5자 이상 필수)</label>
              <textarea
                id="fashion-rationale-input"
                aria-label="판단 이유"
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                placeholder="예: 재발주가 불가능한 시즌오프 품목이므로 A안을 유지하여 잔여 재고를 정상 마진으로 자연 소진한다."
                rows={3}
              />
            </div>

            <button
              className="button button-primary fashion-save-btn"
              disabled={saving || rationale.trim().length < 5}
              onClick={() => void handleSaveDecision()}
            >
              {saving ? "저장 중…" : "이 판단으로 기록 저장"}
            </button>
          </div>
        </div>
      )}

      {/* 과거 판단 기록 목록 */}
      {productDecisions.length > 0 && (
        <div className="fashion-decision-history">
          <h4>이 상품의 판단 기록 ({productDecisions.length}건)</h4>
          <div className="fashion-history-list">
            {productDecisions.map((dec) => {
              const optionBadge = dec.chosen_option === "A" ? "A안 (현재가 유지)"
                : dec.chosen_option === "B" ? "B안 (변경안)"
                : dec.chosen_option === "hold" ? "보류 (추가 확인)"
                : dec.action_type;

              return (
                <div className="fashion-history-item" key={dec.id}>
                  <div className="fashion-history-head">
                    <span className="decision-badge">{optionBadge}</span>
                    <time>{dec.created_at ? new Date(dec.created_at).toLocaleDateString("ko-KR") : dec.as_of_date}</time>
                  </div>
                  <p className="fashion-history-rationale">{dec.rationale}</p>
                  <div className="fashion-history-snapshot">
                    {dec.chosen_option && dec.chosen_option !== "hold" && (
                      <small>
                        <b>시나리오:</b> 할인 {dec.discount_pct ?? 0}% · 가정 {number(dec.expected_units_30d ?? 0)}개 ·{" "}
                        매출총이익: {dec.feasible && dec.estimated_gross_profit != null ? won(dec.estimated_gross_profit) : "재고 부족 (계산 제외)"}
                      </small>
                    )}
                    <small>
                      <b>기준 스냅샷:</b> 기준일 {dec.as_of_date} · 7일 {dec.observed_units_7d}개 · 30일 {dec.observed_units_30d}개 · 재고 {dec.assumed_stock_on_hand}개
                    </small>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
