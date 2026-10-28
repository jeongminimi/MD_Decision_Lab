# MD Decision Lab

**주니어 MD가 상품별 판매 흐름을 보고 재고·이익을 확인해 다음 조치를 기록하는 로컬 업무 도구**

This portfolio MVP is based on practical apparel MD workflows: sales velocity, stock coverage, inbound stock, replenishment lead time, promotion planning, and live-commerce exposure.

## What the MVP is designed to show

- A relational database stores product, daily sales, and action-history records.
- Transparent rules flag stockout risk, overstock risk, slow-moving items, and insufficient data.
- Each recommendation exposes the input values and reasoning behind it.
- MD actions are recorded. A completed action can show descriptive sales, revenue, and recorded gross-margin changes across equal 7-day windows when all daily records exist. Stock at logging and current stock are shown separately.
- A separate short-form module turns an approved product/action brief into editable content drafts, which can be saved and reloaded locally. It is isolated so it can be extracted and reused by another product later.

The default workspace can use a bounded H&M sales sample or an uploaded company CSV/XLSX pair. H&M sales are observed historical records; inventory, cost, and proposed actions are not part of that source. The older F/W apparel case remains available under **합성 사례**. Recommendations are decision support, not autonomous purchasing or a claim of proven business impact.
The short-form module currently produces text drafts through a fixed local template. It does not create video, call an external AI model, or publish posts.
The action comparison is descriptive. Complete daily rows, including zero-sale days, are required for both windows; it cannot establish that the action caused any change. Sell-through rate is not computed without inventory snapshots for each period.

## Run locally

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs: <http://127.0.0.1:8000/docs>

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

The frontend expects the API at `http://127.0.0.1:8000` by default. Set `VITE_API_BASE_URL` to override it.

To try your own non-sensitive data, import the product/catalog CSV first, then import the dated sales CSV. See `docs/CSV_IMPORT.md` for columns and update behavior.

The new **실무 작업공간** lets you upload product and dated-sales CSV/XLSX files together to create an isolated company dataset. Use `sample_data/company_products_template.csv` and `sample_data/company_sales_template.csv` as column examples. After a recorded action, add newer dated sales from **내 결정 기록**. See `docs/WORKSPACE_DATA.md` for the source labels, calculation rules, and limits.

For the local H&M demonstration, keep the Kaggle ZIP files outside the repository and run from `backend/`:

```powershell
python scripts/import_hm.py --articles "C:\path\articles.csv.zip" --transactions "C:\path\transactions_train.csv.zip"
```

This importer stores only a bounded apparel sample in SQLite and does not copy customer IDs or normalized H&M prices into the MD workspace. The full dataset and images are never committed. Matching local images may be placed in `frontend/public/hm_images/`, which is gitignored.

## F/W apparel MD case

The working navigation now starts with **오늘의 할 일**, **전체 상품**, and **내 결정 기록**. All three use the same apparel product and decision records; **다음 시즌 기획** is a separate analysis view. The bundled data remains synthetic. Current input supports dated sales CSV updates and editing one product's stock, inbound quantity, price, and cost. It does not yet provide a complete real-company product/stock-ledger import or verified purchase-order workflow.

Open **F/W 의류 MD 사례** and click **패션 사례 연결**. The app validates and saves the bundled synthetic 30-product, 60-day dataset in SQLite without replacing existing records. It separates summer clearance, prelaunch fall stock, and non-reorderable winter event products. The screen shows 7/30-day demand, prior-period units, stock cover, gross margin and margin rate, decision evidence, and a gross-profit arithmetic check for extra markdowns. An MD can edit current price, cost, and stock or upload corrected daily-sales rows; the analysis refreshes after saving. Historical margin stays tied to the dated sales rows. An MD can also save a decision and its reasoning alongside a snapshot of the numbers used. The inventory snapshot is dated 2026-08-31; the app does not project it backwards to other dates. See `docs/FASHION_CASE.md` and `sample_data/fashion_fw_case/DATA_QA.md`.

At the bottom of the apparel case, click **운영 자료 연결** once. This validates and stores 1,800 synthetic daily stock-flow rows and 12 synthetic prior-season comparables in new tables, without replacing current product/sales edits. The planning panel then shows reconciled product-level 60-day sell-through, prior-year comparable sell-through, and adjustable growth/target sell-through assumptions for 2026FW initial buy review. Select a fall product, write the reason and conditions to check, then click **이 판단 저장** to keep a server-recalculated snapshot in the database. This does not place an order or change inventory. An edited product or sale can make the immutable ledger differ from the current inputs; the screen flags that difference. See `docs/FASHION_DATA_DESIGN.md` for formulas and limits.

## Scope

The active portfolio case is apparel merchandising. Public retail datasets and the former Olist practice workspace are outside the current product direction. Existing local database rows and source files are retained, but the Olist screen and API are not exposed.

## Project map

- `docs/PRODUCT_SPEC.md` — target user, workflow, MVP scope, and success criteria.
- `docs/DECISION_RULES.md` — transparent metric definitions and risk rules.
- `docs/ARCHITECTURE.md` — module boundaries and data flow.
- `docs/CSV_IMPORT.md` — supported sales CSV shape and replacement behavior.
- `docs/BUILD_LOG.md` — two-day build scope and evidence boundaries.
- `docs/PORTFOLIO_CASE_STUDY.md` — Korean walkthrough and accurate project ownership/impact description.
- `docs/FASHION_DATA_DESIGN.md` — stock-flow reconciliation, prior-season comparables, scenario formulas, and limits.
- `docs/superpowers/2026-10-27-ui-redesign.md` — UI goal and visual interpretation of the owner's reference image.
- `docs/references/wellness-ui-reference.jfif` — owner-provided style reference, retained for design review; it is not used as a production screen asset.
- `backend/app/services/analysis.py` — stock coverage and recommendation rules.
- `backend/app/modules/shortform/` — inactive, isolated source retained for possible future reuse. No shortform screen or API route is exposed in MD Decision Lab.
- `frontend/src/` — dashboard and MD workflow UI.
- `sample_data/sales_import_template.csv` — sample input matching the seeded demo catalog.
- `sample_data/products_import_template.csv` — sample catalog and inventory input.

## Portfolio framing

The project owner brings store and online-MD workflow knowledge, defines the problem and operating rules, directs AI-assisted implementation, and reviews the outputs. Code authorship and business impact must be described accurately. Do not claim that the prototype increased real sales without a controlled real-world measurement.
