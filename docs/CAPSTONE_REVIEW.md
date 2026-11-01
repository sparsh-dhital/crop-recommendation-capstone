# AI mini capstone readiness review

Reviewed against the supplied AI Mini-Capstone Project Guidelines and Ai_Capstone_Document on 1 November 2026. The project is a suitable smart-agriculture classification prototype; faculty topic approval still needs confirmation. A recommendation application can fit the guideline's smart-agriculture/recommendation examples, but using a classifier does not itself make it a knowledge-based or autonomous agent.

## Deadlines

The guidelines, page 12, list Review 3 (implementation/results) on **2 November 2026** and the final review on **9 November 2026, tentative**. Review 1 was 12 October and Review 2 was 26 October; completion of those reviews cannot be verified from the supplied materials.

## Status and pending actions

| Requirement | Evidence / status | Pending action |
|---|---|---|
| Topic and real-world problem | Seven inputs and crop-name output are clear. The guideline includes smart agriculture. | Confirm faculty approval and explain why this is supervised multi-class classification. |
| Team formation | Report lists Sparsh, Jahnavi, Shaik Rehan, Varaparla Nanda and Kishore. Guidelines normally specify four, with provisions for remaining students. | Confirm approval for five members, Kishore's full name/ID, and everyone's actual contribution. Do not invent or remove a member. |
| Problem, objectives and applications | Present in the report. | Remove unsupported claims of proven yield/profit improvements. |
| Algorithm clarity | Original report says only a generic classifier. Original notebook used Random Forest only. | Explain Decision Tree splitting, Random Forest bagging/random feature subsets/voting, 100 trees, seed 42, and why the model is suitable. |
| Working implementation | Original app predicted crops but login was only browser-side and auto-registered unknown names. | Fixed with separate registration/login, password hashing, persistent accounts, expiring/revocable sessions and CSRF checks. Run the demo on the presentation laptop. |
| Reproducible experimentation | Original scaler was fitted before the split and only RF was evaluated. | Fixed in train.py: split first, training-only scaling/CV, dummy/DT/RF comparison, regenerated artifacts. |
| Meaningful results | Original report gives a sample input and prose, but no measured comparison/confusion matrix. | Insert the new measured table, per-class metrics, two errors and confusion matrix. Add screenshots from the final running UI. |
| Architecture / workflow | Report includes a use-case diagram and a class-style diagram, not a detailed training/inference flow. Admin functions are depicted without an implemented admin interface. | Show actual offline training and online inference paths; remove or label conceptual admin/class components. |
| Documentation consistency | Cover, introduction, future scope and conclusion call this crop yield prediction. Code snippets in the DOCX are truncated/malformed. | Use “Crop Recommendation System Using Machine Learning” consistently; output is a crop label, not tonnes/hectare. Replace copied code blocks with short verified snippets and repository references. |
| Sources | Generic bibliography exists; exact CSV source/license and image credits are absent. | Obtain original dataset URL, author/license, feature definitions and rainfall period from the teammate. Verify all bibliography entries; do not assume yield-prediction papers validate this classifier. |
| Limitations | Many limitations are already described. | Add dataset-only testing, no independent farm validation, no geographic/seasonal/market inputs, no real-time sensors, and possible out-of-distribution predictions. |
| A5 poster | Not supplied. Section 7 says “may,” but workflow, final-review checklist and rubric include it. | Prepare an A5 poster (148 × 210 mm) unless faculty confirms it is not required. Include model, workflow, measured results, limits and team. QR is optional. |
| Presentation and viva | No slides/demo script or evidence of rehearsal supplied. | Rehearse the 12 presentation topics in section 6.7 and have every member explain the entire project. Slides are useful; the guideline does not explicitly mandate a PPT file. |
| AI assistance and originality | Guidelines permit AI for assistance but require verification and understanding. | Acknowledge assistance and external code/data; each member must review, run and explain the implementation. |

## Measured results to use

2,200 supplied samples; 22 classes; seven features; 1,760 training and 440 test samples; stratified split, seed 42. No missing values or duplicate rows were found. Five-fold validation uses the training partition only.

| Model | Test accuracy | Macro F1 | Test errors |
|---|---:|---:|---:|
| Majority baseline | 4.55% | 0.00395 | 420 |
| Decision Tree | 97.95% | 0.97942 | 9 |
| Random Forest | 99.55% | 0.99545 | 2 |

Random Forest training-fold accuracy is 99.26% mean with 0.59 percentage-point standard deviation. Its held-out errors were blackgram classified as maize and rice classified as jute. Discuss these as overlapping learned feature patterns in this dataset; do not claim a causal agronomic explanation without further analysis.

Use `evaluation/metrics.json`, `model_comparison.csv`, `confusion_matrix.png` and `misclassified_samples.csv` as the supporting experiment record. The original 99.32% result should be replaced when describing the new experiment. The changed split means the new number cannot be presented as a controlled performance improvement caused by fixing leakage.

## Actual technical workflow

**Offline training:** CSV → data checks → stratified split → training-only scaler and cross-validation → fit each model → evaluate on untouched test data → save RF/scaler/encoder and reports.

**Online inference:** register/sign in → server verifies account/session → validate seven measurements → apply saved scaler → Random Forest predicts an encoded label → decode crop name → display crop and available image.

Accounts are in SQLite; password hashes are scrypt. Sessions expire after eight hours and logout revokes them. Browser history is local convenience storage, not a secure account database. No admin management screen is implemented.

## Demo sequence for Review 3

1. Start the app from the README instructions and open /login.
2. Register a new demonstration account; show a clear mismatch error once, then complete registration.
3. Enter N=90, P=42, K=43, temperature=20.5, humidity=82, pH=6.5, rainfall=200. Show the rice result.
4. Explain how validation rejects humidity above 100 or pH above 14.
5. Log out; try an incorrect password, then sign in correctly. Refresh to show session persistence.
6. Show the comparison table, confusion matrix and both error cases. Explain the difference between classification and yield regression.
7. End with limitations and one realistic extension, such as testing with independently collected regional data.

## Suggested remaining work order

Before 2 November: run the repaired app on the demo laptop; study train.py/app.py; capture login/input/result screenshots; insert verified results; correct the title and yield claims; confirm roster/topic approval.

Before the tentative 9 November final: finish the corrected report and references; prepare A5 poster; rehearse all members; keep a tested local copy and a short demo recording as backup. Record actual contributions instead of assigning credit retrospectively.

## Marks to prioritize

Implementation 20; problem understanding 15; AI/algorithm clarity 15; results/analysis 15; technical competency 15; innovation/relevance 10; presentation 5; documentation/poster 5. Most marks depend on demonstrating and understanding the technical work.

## Useful viva prompts

- Why classification rather than regression? The output is one of 22 crop labels, not a numerical yield.
- What is a Decision Tree? A sequence of feature-based splits leading to a class prediction; the default criterion used here is Gini impurity.
- What does Random Forest add? Multiple trees trained with bootstrap sampling and random feature subsets; their predictions are combined.
- Why split before scaling? Test data must not influence learned preprocessing statistics.
- Is scaling essential for these tree models? Generally no; it is retained consistently in the saved inference pipeline.
- Why stratification? To preserve class proportions in training/testing and validation folds.
- Why report macro F1? It gives each crop class equal weight when combining precision and recall.
- Why is 99.55% not enough for deployment on farms? A random holdout from one dataset does not establish performance in different regions, seasons or measurement conditions.
- What does login protect? The prediction endpoint checks a real session. Password hashes and account records are on the server, not in browser localStorage.
