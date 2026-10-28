# MD Decision Lab

**상품 판매·재고 데이터를 읽고, MD의 다음 행동과 콘텐츠 초안까지 이어주는 의사결정 도구**

This portfolio MVP is based on practical apparel MD workflows: sales velocity, stock coverage, inbound stock, replenishment lead time, promotion planning, and live-commerce exposure.

## What the MVP is designed to show

- A relational database stores product, daily sales, and action-history records.
- Transparent rules flag stockout risk, overstock risk, slow-moving items, and insufficient data.
- Each recommendation exposes the input values and reasoning behind it.
- MD actions are recorded. A completed action can show descriptive sales, revenue, and recorded gross-margin changes across equal 7-day windows when all daily records exist. Stock at logging and current stock are shown separately.
- A separate short-form module turns an approved product/action brief into editable content drafts, which can be saved and reloaded locally. It is isolated so it can be extracted and reused by another product later.

The seeded apparel store is synthetic demonstration data; the Olist workspace uses historical delivered orders with synthetic inventory assumptions. Recommendations are decision support, not autonomous purchasing or a claim of proven business impact.
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

## F/W apparel MD case

Open **F/W 의류 MD 사례** and click **패션 사례 연결**. The app validates and saves the bundled synthetic 30-product, 60-day dataset in SQLite without replacing existing records. It separates summer clearance, prelaunch fall stock, and non-reorderable winter event products. The screen shows 7/30-day demand, prior-period units, stock cover, gross margin and margin rate, decision evidence, and a gross-profit arithmetic check for extra markdowns. An MD can edit current price, cost, and stock or upload corrected daily-sales rows; the analysis refreshes after saving. Historical margin stays tied to the dated sales rows. An MD can also save a decision and its reasoning alongside a snapshot of the numbers used. The inventory snapshot is dated 2026-08-31; the app does not project it backwards to other dates. See `docs/FASHION_CASE.md` and `sample_data/fashion_fw_case/DATA_QA.md`.

## Olist historical demand and inventory simulation

The **Olist 시뮬레이션** workspace reads the original `.csv.gz` files from the sibling `Olist-E-Commerce-Data-Analysis/data/` folder. Set `OLIST_DATA_DIR` before starting the API if the source repository lives elsewhere. Click **Olist 데이터 연결**, download the scenario CSV template, fill the stock/cost assumptions, and upload it. The source repository was inspected at `jeongminimi/Olist-E-Commerce-Data-Analysis` (fork of `dino-21/Olist-E-Commerce-Data-Analysis`); the importer stores a checksum of the input files and does not copy them into this project.

The import uses delivered orders purchased from 2017-01-01 through 2018-08-31. Each order-item row is one unit; revenue is the sum of `price` and excludes freight. The 30-day demand window ends on the scenario's historical date. Currency is BRL. Inventory, inbound units, lead time, target cover, and cost are independently entered assumptions. Estimated margin is not an observed Olist profit. See `docs/OLIST_INTEGRATION.md` for the data contract and caveats.

`sample_data/olist_scenario_example.csv` is a clearly labelled synthetic stock/cost example for five real Olist product IDs. Upload it after connecting Olist data to see multiple risk states immediately.
`sample_data/olist_scenario_adjusted_example.csv` uses the same products and date with different inventory assumptions. Upload it to compare stockout risk, overstock risk, stock value, and replenishment suggestions while holding observed sales constant.
The analysis now shows both 7-day and 30-day demand rates, the rate selected for stock coverage, and small-sample warnings. Use **판단 근거 CSV 받기** to export observed sales, assumed stock/cost, and recommendation reasons together.

## Project map

- `docs/PRODUCT_SPEC.md` — target user, workflow, MVP scope, and success criteria.
- `docs/DECISION_RULES.md` — transparent metric definitions and risk rules.
- `docs/ARCHITECTURE.md` — module boundaries and data flow.
- `docs/CSV_IMPORT.md` — supported sales CSV shape and replacement behavior.
- `docs/BUILD_LOG.md` — two-day build scope and evidence boundaries.
- `docs/OLIST_INTEGRATION.md` — original Olist mapping, scenario format, and evidence limits.
- `docs/PORTFOLIO_CASE_STUDY.md` — Korean walkthrough and accurate project ownership/impact description.
- `docs/superpowers/2026-10-27-ui-redesign.md` — UI goal and visual interpretation of the owner's reference image.
- `docs/references/wellness-ui-reference.jfif` — owner-provided style reference, retained for design review; it is not used as a production screen asset.
- `backend/app/services/analysis.py` — stock coverage and recommendation rules.
- `backend/app/modules/shortform/` — inactive, isolated source retained for possible future reuse. No shortform screen or API route is exposed in MD Decision Lab.
- `frontend/src/` — dashboard and MD workflow UI.
- `sample_data/sales_import_template.csv` — sample input matching the seeded demo catalog.
- `sample_data/products_import_template.csv` — sample catalog and inventory input.

## Portfolio framing

The project owner brings store and online-MD workflow knowledge, defines the problem and operating rules, directs AI-assisted implementation, and reviews the outputs. Code authorship and business impact must be described accurately. Do not claim that the prototype increased real sales without a controlled real-world measurement.
