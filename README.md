# Flame / Freefall

A small white chat interface for NASA combustion data. Python 3.11, real CSV records, comparisons, linear regressions, and GPT-6 Astra explanations. Runs on your computer.

## Open it on Windows

1. Extract the entire ZIP to a normal folder. Double-click **START_WINDOWS.bat**. The first run installs the Python packages.
2. If prompted, select your existing private **.env.local** file. The browser opens automatically. Keep the command window open.

Your key can also be placed beside START_WINDOWS.bat, or its file path set in `FLAME_ENV_FILE`. No API key is included in this download. It is never sent to the browser. The app can also find `.env.local` in the parent folder or Downloads.

**Already using Jupyter?** Open **Start_Flame_App.ipynb** in this extracted folder, choose your Python 3.11 kernel, and run its two cells. You do not need to run the previous notebooks first.

Mac/Linux: run `sh START_MAC_LINUX.sh` with Python 3.11 installed.

## What to try

- “Compare methanol and heptane: initial droplet diameter versus burn duration, with linear regression at matched oxygen, pressure and diluent conditions.”
- “Graph nozzle diameter versus airflow in SPICE, then fuel mass flow versus airflow, with regression and separate fuel comparisons.”
- “Compare how tests ended for different fuels in CFI-G normal flames. Which self-extinguished and which were flow-terminated?”
- “How does airflow affect flame spread in microgravity?”

Ask follow-up questions in the same chat. **Compare** lets you directly choose the experiment, axes, fuels, and condition ranges; it works without API access. Turn on “Add a GPT explanation” for an interpretation. **Data** shows available fields and all original CSV downloads.

Charts are interactive: zoom, hover for source IDs, click a point for its highlighted original row, click legend entries to hide groups, and double-click one to isolate it. Each chart has CSV and PNG downloads and a Fit toggle. The source viewer highlights the columns used. The answer's paper citations open PDFs with the relevant paragraph highlighted. “Save analysis” exports the question, fits, rows, provenance and explanation as JSON.

**Cleaner charts:** confidence shading is hidden initially; turn on **95% band** to inspect it. Comparisons with four or more groups open as **Separate panels**, sharing axis ranges so fuel comparisons remain meaningful. Select **Compare together** to overlay all groups. On narrow screens the panels stack vertically. The PNG button exports the selected view. Fitted lines and optional bands retain the measured x range; the app does not extend them to infinity. This presentation update also works with older saved answers without new API requests.

**Small update:** if you already have the app, close its command window, extract `Flame_Chart_Update.zip` into the directory containing your existing `Flame_Freefall_App` folder, and allow replacement of its code files. Restart the app and refresh the browser. Your existing data, cache and private key file remain in place. If your app folder was renamed, copy the update's inner files into the folder containing `START_WINDOWS.bat`.

## Data and scientific scope

The bundled snapshot (15 November 2026) contains **22 original NASA PSI CSVs**, approximately 211 KB total, plus supporting NASA papers. Nine tables have explicitly mapped chart fields: **1,615 nonempty, deduplicated records**. These are not 1,615 independent experiments. SPICE has repeated stages within ignitions; its 435 distinct rows represent 151 ignition groups. CFI-G inverse has 861 empty rows that are not counted as tests. A field can still contain missing or ranged values, so each plot reports its usable sample size.

No guessed values, paper-figure digitization, or invented datasets are used. The raw CSV files are unchanged. Strict numeric parsing rejects ranges, inequalities, sequences, and ambiguous text. CSV row IDs, physical line numbers, file hashes, NASA investigation links, applied filters and omissions are retained.

**Diameter means different things in different experiments.** SPICE provides nozzle diameter; FLEX provides initial droplet diameter and droplet diameter at visible-flame extinction. These are not interchangeable with inner flame diameter. BASS-II air-display settings have no assumed cm/s calibration. Fuel mass flow, oxygen mass flow, air speed, and flame-spread speed are different variables. The cached CSVs do not contain a reliable paired solid-flame-spread-rate-versus-airflow series. The app reports that gap and can show related available measurements, labelled as such.

FLEX's original “Burning rate; mm” header is truncated. The prepared field uses **mm²/s**, documented by NASA report **20150023456, Table 1**; the original CSV remains unedited. The O, N and CO ambient fields correspond to O₂, N₂ and CO₂ in that report. Source: https://ntrs.nasa.gov/citations/20150023456

Linear regression is OLS within selected groups, requiring at least five records, five test groups and three distinct x values. R² describes in-sample linear fit, not scientific confidence. Shading is a 95% cluster-robust confidence band for the mean; it is not a prediction interval. SPICE fits cluster repeated ignitions; FLEX uses identifier/date/time and CFI-G uses day/test identities. Other tables use a CSV record as the statistical group. Small cluster counts still limit inference. No extrapolation is plotted. The app separates fuel/nozzle groups and CFI-G termination categories where applicable. An association between imposed flow and nozzle settings describes experimental design, not airflow physically changing a nozzle. Unmatched conditions can confound fuel comparisons. No ML predictor is claimed or trained.

Categorical outcomes use observed shares with actual denominators, not linear regression. Self-extinction, flow termination, disruption and completion remain separate. Missing outcomes and failed ignition do not become “did not extinguish.” Flow-terminated durations are interrupted observations, not natural burnout times. GPT explanations can still contain errors; source inspection remains part of the workflow.

## Model, cost and caching

Default: **gpt-6-astra**, reasoning **high**, verified accessible during development. Chat generally makes two API calls (plan and explanation); direct Compare makes zero, or one when AI explanation is enabled. An exact repeated question with the same conversation context and data snapshot reuses its saved result. New chat resets context. No silent downgrade occurs. Your project must have API access and sufficient credits; ChatGPT membership is separate from API usage. Set `FLAME_MODEL` only if you deliberately want a different accessible model.

The app sends the question, catalog summaries, calculated statistics and a few example rows, plus relevant public paper passages, to OpenAI. The key remains in the local backend. API responses use `store=False`; local answers are cached in `cache/`. Delete that folder to clear saved analyses. No user key, private notebook, or prior chat history is bundled.

## Updating the small data cache

Run `python refresh_data.py` in the installed environment. It checks the known NASA PSI CSV versions and downloads only those small tables, never videos or raw telemetry. If NASA changes a mapped header, the loader stops instead of silently mapping the wrong data. Restart the app after an update. New kinds of datasets need an explicit field mapping in `datasets.py`; the app does not promise access to every NASA experiment.

## Troubleshooting

- **Broken symbols such as `COâ‚‚` or `RÂ²`:** this version explicitly reads saved answers and metadata as UTF-8 on Windows. Stop the old app, extract this update over its folder, restart and begin a New chat before repeating the question. Keep your `cache/` folder: intact UTF-8 answers recover without being regenerated when the question, chat context and data match. The fix does not change CSV measurements or regression results.
- **Key missing:** select your existing `.env.local`, put it beside the launcher, or set `FLAME_ENV_FILE` to its full path. Project and organization IDs are not API keys.
- **API access/balance error:** local comparisons still work. Check the API project's model access, billing and internet connection. The app does not change models automatically.
- **Port occupied:** close the older app window or set `PORT` to another unused port before launching.
- **No fit:** inspect the record count and distinct x values; choose a relationship with enough data. A straight line is deliberately omitted when it is not supportable.
- **Updated schema error:** restore the bundled source files or review the new headers before updating the field map.

This is a local research prototype, not a spacecraft fire-safety decision system. Python statistics and the interface are tested; physical interpretations are bounded by the retrieved evidence.
