# Real Chrome visual/responsive review

The local Streamlit app was rendered in Google Chrome via Playwright, not only Streamlit AppTest. Viewports: desktop 1440×900, laptop 1280×800, tablet 768×1024, mobile 390×844. Evidence directory (Git-ignored): `data/analysis/final_audit_screenshots/`. The audit script and `browser_observations.json` are in that directory. The screenshots contain synthetic demo text only, no private human drafts or sealed labels.

| Screenshot | Concrete finding |
|---|---|
| `01_home_desktop.png` | Home headline, three KPIs, trend and scientific caution readable; large open white layout. |
| `02_landscape_desktop.png` | RQ1 chart/table visible; other RQ tabs exist and were clicked separately. |
| `03_topic_explorer_desktop.png` | Native topic selector and brief readable, but sparse relative to available brief fields. |
| `04_classify_initial_desktop.png` | Title/abstract fields and suggest button spaced adequately. |
| `05_classify_prediction_desktop.png` | Real model prediction appears, then visible Streamlit `KeyError: 'topic_name'` traceback. |
| `06_classify_confirmed_desktop.png` | **NOT CAPTURED**: core confirmation blocked by the above exception. No fake screenshot was substituted. |
| `07_paper_explorer_desktop.png` | Filters and sample results render; detail is an expander with metadata and OpenAlex link. |
| `08_methodology_desktop.png` | Mostly prose and a raw config dictionary; evaluation charts/tables absent. |
| `09_methodology_laptop.png` | Text wraps at 1280 px, no document-level overflow detected. |
| `09_methodology_tablet.png` | Text wraps at 768 px; navigation/sidebar occupies substantial width when open. |
| `10_home_mobile.png` | 390 px rendering readable, KPIs stack; sidebar must be collapsed after navigation. |
| `11_classify_mobile.png` | Initial form readable on narrow view; post-prediction/confirmation mobile state NOT VERIFIED because same UI exception. |

Measured `document.documentElement.scrollWidth` equaled viewport width (1440, 1280, 768, 390) for captured pages. This is **not** proof that every embedded Plotly plot or table is accessible: Streamlit tables can scroll internally. No severe clipping was observed in the viewed screenshots. Chrome screenshots were visually inspected for title/readability/sidebar/form spacing. Manual visual inspection **was completed** for the captured screens; human usability, contrast measurements, screen readers, keyboard-only and browser-matrix testing were not.

Rendered report screenshots `report_page_01.png`, `report_page_07.png`, `report_page_11.png` and presentation screenshots `slides_page_01.png`, `slides_page_05.png`, `slides_page_09.png` are colocated. They are visual audit evidence, not published product screenshots. Additional manual verification after a future fix: run `streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501`, navigate every sidebar item at the four stated viewport sizes, submit synthetic text, change it, confirm/override a topic, check table keyboard scroll and open both report links. Capture the missing confirmed-topic desktop/mobile states only after the real app works.
