import { useState } from "react";
import { Activity, Boxes, ChartNoAxesCombined, LayoutDashboard, Menu, X } from "lucide-react";
import FashionPage from "./FashionPage";
import WorkPage from "./WorkPage";

export type WorkView = "overview" | "products" | "actions" | "planning";

const labels: Record<WorkView, string> = {
  overview: "오늘의 할 일",
  products: "전체 상품",
  actions: "내 결정 기록",
  planning: "다음 시즌 기획",
};

export default function App() {
  const [view, setView] = useState<WorkView>("overview");
  const [mode, setMode] = useState<"work" | "sample">("work");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  function navigate(next: WorkView) {
    setView(next);
    setMobileNavOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return <div className="app-shell">
    {mobileNavOpen && <button className="mobile-nav-backdrop" aria-label="메뉴 닫기" onClick={() => setMobileNavOpen(false)} />}
    <aside className={`sidebar ${mobileNavOpen ? "mobile-open" : ""}`}>
      <div className="brand-lockup"><div className="brand-mark">MD</div><div><strong>Decision Lab</strong><span>COMMERCE INTELLIGENCE</span></div></div>
      <div className="workspace-mode" aria-label="작업 모드"><button className={mode === "work" ? "active" : ""} onClick={() => { setMode("work"); navigate("overview"); }}>실무 작업공간</button><button className={mode === "sample" ? "active" : ""} onClick={() => { setMode("sample"); navigate("overview"); }}>합성 사례</button></div>
      <nav className="side-nav" aria-label="주요 메뉴">
        <button className={view === "overview" ? "active" : ""} onClick={() => navigate("overview")}><LayoutDashboard size={17} /> 오늘의 할 일</button>
        <button className={view === "products" ? "active" : ""} onClick={() => navigate("products")}><Boxes size={17} /> 전체 상품</button>
        <button className={view === "actions" ? "active" : ""} onClick={() => navigate("actions")}><Activity size={17} /> 내 결정 기록</button>
        <p className="nav-spaced">분석</p>
        <button className={view === "planning" ? "active" : ""} onClick={() => navigate("planning")}><ChartNoAxesCombined size={17} /> 다음 시즌 기획</button>
      </nav>
      <div className="sidebar-bottom"><div className="user-row"><div className="avatar">JM</div><div><b>MD 매니저</b><small>로컬 작업공간</small></div></div></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><button className="mobile-menu" aria-label="메뉴 열기" aria-expanded={mobileNavOpen} onClick={() => setMobileNavOpen((open) => !open)}>{mobileNavOpen ? <X size={20} /> : <Menu size={20} />}</button><div className="breadcrumbs"><span>MD Decision Lab</span><b>/</b><strong>{labels[view]}</strong></div></header>
      <div className="content-wrap">{mode === "work" ? <WorkPage view={view} onNavigate={navigate}/> : <FashionPage view={view} onNavigate={navigate}/>}<footer className="page-footer"><span>MD Decision Lab · 로컬 MD 작업공간</span><span>시나리오는 실제 매출 성과가 아닙니다.</span></footer></div>
    </main>
  </div>;
}
