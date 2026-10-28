from .contracts import ContentDraft, ProductContentBrief


def create_draft(brief: ProductContentBrief) -> ContentDraft:
    """Local template adapter. Replace behind this contract when a model provider is added."""
    audience = f"{brief.audience}을 위한 " if brief.audience.strip() else ""
    offer_line = f"{brief.offer.strip()} " if brief.offer.strip() else ""
    context_line = f"오늘은 {brief.action_context.strip()}을(를) 소개할게요." if brief.action_context.strip() else ""
    return ContentDraft(
        hook=f"{audience}{brief.product_name}, 이런 디테일을 찾고 있었다면 확인해 보세요.",
        script_beats=[
            f"0–3초 | 훅: {brief.product_name}의 핵심 장점을 한 문장으로 보여줍니다.",
            f"3–10초 | 특징: {brief.key_feature}",
            f"10–16초 | 상황: {context_line or '실제 착용 장면과 활용 상황을 보여줍니다.'}",
            f"16–20초 | 안내: {offer_line}상세 정보와 재고를 확인하도록 안내합니다.",
        ],
        caption=f"{brief.product_name} — {brief.key_feature}. {offer_line}상품 정보와 옵션은 판매 페이지에서 확인해 주세요.",
        call_to_action="상세 페이지에서 색상·사이즈와 현재 재고를 확인해 보세요.",
        review_note="초안입니다. 가격·혜택·재고·소재 정보가 현재 판매 정보와 일치하는지 확인한 뒤 사용하세요.",
    )
