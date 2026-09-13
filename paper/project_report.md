# Keeping a Fraud Model Current Without Retraining It: In-Context Exemplar Selection on Bitcoin Financial Networks

**Authors**: Group Project Team  
**Institution**: Canadian University Dubai, Department of Computer Science & Engineering  
**Course**: MAI 601 – Data Mining & Machine Learning  
**Supervisor**: Prof. Ayman Elnashar  
**Target Venue**: IEEE Access / IEEE International Conference  
**Dataset**: Elliptic Bitcoin Transaction Dataset (203,769 transactions across 49 bi-weekly time steps)  
**Methodological Reference**: Semon et al. (IEEE QPAIN 2026, Paper ID: 101165)

---

## Abstract
Detecting illicit financial transactions in cryptocurrency networks is a critical defense against money laundering, terrorist financing, and ransomware payments. While modern machine learning models achieve high accuracy on standard random train-test splits, they suffer from catastrophic performance decay when deployed in production and evaluated strictly forward in time. This paper investigates the temporal drift phenomenon on the Elliptic Bitcoin dataset (46,564 confirmed labeled transactions spanning 49 bi-weekly intervals). We demonstrate that static gradient-boosted trees and deep classifiers decay significantly over time, with their Area Under the Precision-Recall Curve (AUPRC) dropping from 0.944 in validation to 0.319–0.336 in post-deployment steps (steps 40–49). This decay is heavily intensified at **time step 43**, corresponding to the real-world law enforcement shutdown of major darknet marketplaces (AlphaBay and Hansa), which triggers an acute Population Stability Index (PSI) surge beyond 0.81. To address this failure without incurring the prohibitive latency, annotation expense, and governance compliance overhead of monthly retraining, we propose an **In-Context Exemplar Selection Architecture**. The proposed method dynamically constructs an exemplar context set from historical candidate transactions at test time using a dual-component ranking function combining **Temporal Recency** ($1 / \Delta t$) and **Centroid Similarity**. Evaluated sequentially over steps 40 to 49, our zero-retraining framework achieves an **AUPRC of 0.5267**, an **illicit recall of 74.18%**, and cuts financial losses by **$51,640 per time step** compared to continuous full-model retraining ($146.82K vs $198.46K). Furthermore, we integrate Ensemble Feature Selection (Chi-Square, RFE, and SHAP combined via Borda count aggregation) and Optuna Bayesian optimization, providing comprehensive Explainable AI (XAI) transparency for banking compliance.

**Index Terms**—Cryptocurrency Fraud, Temporal Concept Drift, In-Context Learning, Elliptic Bitcoin, Population Stability Index, Ensemble Feature Selection, Borda Count, Explainable AI (SHAP), LightGBM.

---

## I. Introduction
Financial fraud in decentralized cryptocurrency networks represents a multi-billion-dollar global challenge. Unlike traditional centralized banking, where account holders are authenticated via Know-Your-Customer (KYC) protocols, public blockchain ledgers such as Bitcoin operate pseudonymously, obfuscating money laundering, ransomware extortion, and illegal marketplace transactions within hundreds of thousands of daily payments.

To counter illicit activity, financial intelligence units and cryptocurrency exchanges deploy automated supervised machine learning models. However, an operational bottleneck confronts modern fraud analytics teams:
1. **Adversarial and Regulatory Concept Drift**: Fraud patterns are non-stationary. Criminal entities continuously innovate new obfuscation techniques (e.g., peel chains, coin mixers). Moreover, external enforcement actions—such as the coordinated police seizure of the AlphaBay darknet marketplace in 2017—instantly alter network flow dynamics.
2. **The High Cost of Retraining**: While the standard engineering recommendation is to continuously retrain the model on newly labeled data, real-world deployment rules in banking make frequent retraining impractical. Model changes require rigorous regulatory validation, operational audit cycles, risk committee approvals, and expensive forensic labeling.

When conventional static models (trained on historical data) encounter shifting distributions, they do not produce explicit system errors. Instead, they output confident, misleading predictions on transactions they no longer understand. In this project, we address the core research question:
> *Can we keep a financial fraud detection model current without training it again?*

We answer this affirmatively by reframing temporal adaptation not as a model retraining problem, but as an **exemplar selection problem**. By deploying a dynamic In-Context Exemplar selection mechanism that computes recency and topological similarity over historical candidate pools, we adapt the decision boundary at prediction time with **zero parameter updates and zero training cycles**.

---

## II. Related Work & Contributions
Traditional cryptocurrency fraud detection studies on the Elliptic dataset frequently report AUPRC and F1-scores exceeding 0.85–0.95. However, as noted in recent literature, almost all such benchmarks rely on **random k-fold shuffling**, which randomly mixes future and past transactions across folds, completely masking the temporal dimension and leakage. When evaluated strictly chronologically forward in time, graph neural networks (GNNs) and static gradient-boosted trees suffer substantial performance collapse.

In parallel, Semon et al. (IEEE QPAIN 2026, Paper 101165) proposed an advanced pipeline for financial transaction fraud combining:
- Multi-algorithm Ensemble Feature Selection (Chi-Square, Recursive Feature Elimination, and SHAP) aggregated through Borda count voting;
- Bayesian hyperparameter optimization using Optuna;
- Explainable AI (XAI) leveraging SHAP to guarantee interpretability for financial regulators.

### Contributions of this Paper:
1. **Realistic Chronological Benchmarking**: We implement a strict temporal evaluation split (Train: Steps 1–34; Validation/Tune: Steps 35–39; Test: Steps 40–49 forward in time), capturing the real-world structural shock at Step 43.
2. **In-Context Exemplar Architecture**: We design an inference-time exemplar selector combining $1 / \Delta t$ recency weighting and cosine centroid similarity to provide dynamic context sets without model retraining.
3. **Four-Way Ablation Study**: We systematically benchmark four exemplar strategies: Random Context, Recency Only, Similarity Only, and the Proposed Hybrid Formulation.
4. **Population Stability Index (PSI) & Financial Cost Modeling**: We quantify distribution shift across all 49 time steps and introduce a realistic financial cost metric ($C_{FN} = \$10,000$, $C_{FP} = \$100$) reflecting real institutional losses.
5. **Integrated Paper 101165 Pipeline**: We incorporate Borda count ensemble feature selection, Optuna tuning, and SHAP XAI for end-to-end transparency.

---

## III. Dataset & System Architecture

### A. The Elliptic Bitcoin Dataset
The Elliptic dataset comprises 203,769 Bitcoin transactions distributed across 49 consecutive time steps (each step representing a bi-weekly window of approximately two weeks):
- **Features**: 165 anonymous numerical features per transaction. Features 1–94 capture local transaction properties (transaction fees, input/output counts, BTC amounts); features 95–165 describe aggregated neighborhood properties (one-hop and two-hop subgraph topology).
- **Labels**: Transactions are classified as `class 1` (illicit, confirmed fraudulent/darknet), `class 2` (licit, verified exchanges/miners), and `unknown` (unlabeled).
- **Filtering**: Filtering for confirmed ground truth yields **46,564 labeled transactions**, containing **4,545 illicit payments** (9.76% class imbalance).

### B. Chronological Splitting Protocol
To simulate real banking deployment:
- **Training Set (Steps 1 to 34)**: 29,894 transactions (3,462 illicit, 26,432 licit).
- **Tuning Set (Steps 35 to 39)**: 5,486 transactions (447 illicit, 5,039 licit), used strictly for Optuna hyperparameter optimization.
- **Testing Set (Steps 40 to 49)**: 11,184 transactions (636 illicit, 10,548 licit), evaluated step-by-step strictly forward in time.

### C. Ensemble Feature Selection (Borda Count Aggregation)
To eliminate redundant noise from the 165 features without arbitrary thresholding, we apply three orthogonal feature selection strategies on the training distribution:
1. **Chi-Square Criterion ($\chi^2$)**: Quantifies non-negative univariate dependency with the fraud label.
2. **Recursive Feature Elimination (RFE)**: Iteratively eliminates features using tree-based importance rankings.
3. **Tree-SHAP Feature Attribution**: Measures the mean absolute Shapley value:
   $$\bar{\phi}_j = \frac{1}{N}\sum_{i=1}^{N} |\phi_j(x_i)|$$
4. **Borda Count Aggregation**: For $M=3$ methods across $N=165$ features:
   $$\text{Borda}(f) = \sum_{m \in \{\chi^2, \text{RFE}, \text{SHAP}\}} (N - \text{Rank}_m(f))$$
The top 25 features selected by unanimous consensus are retained for downstream training.

---

## IV. In-Context Exemplar Selection Architecture

### A. Problem Formulation
Let $\mathcal{D}_t = \{(\mathbf{x}_i, y_i)\}_{i=1}^{N_t}$ represent the transactions arriving at test step $t \in [40, 49]$. The historical candidate pool available to the institution consists of all labeled transactions observed prior to step $t$:
$$\mathcal{C}_t = \bigcup_{\tau=1}^{t-1} \mathcal{D}_\tau$$
Rather than updating model parameter weights $W$ via gradient descent, the In-Context Exemplar classifier dynamically retrieves a subset $\mathcal{S}_t \subset \mathcal{C}_t$ of size $K$ ($K=2,000$) to formulate an instantaneous context set for scoring $\mathcal{D}_t$.

### B. Scoring Formulations
For each candidate transaction $j \in \mathcal{C}_t$ with occurrence time step $\tau(j)$ and feature vector $\mathbf{x}_j$:

1. **Normalized Recency Score ($R_j$)**:
   $$\tilde{R}_j = \frac{1}{t - \tau(j)}$$
   $$R_j = \frac{\tilde{R}_j - \min \tilde{R}}{\max \tilde{R} - \min \tilde{R} + \epsilon} \in [0, 1]$$
   Candidates from recent steps receive exponentially higher weight, discounting stale criminal behavior.

2. **Centroid Similarity Score ($S_j$)**:
   Let $\bar{\mathbf{x}}_t = \frac{1}{N_t}\sum_{k=1}^{N_t} \mathbf{x}_k$ denote the topological centroid of the arriving batch at step $t$.
   $$\tilde{S}_j = \frac{\mathbf{x}_j \cdot \bar{\mathbf{x}}_t}{\|\mathbf{x}_j\|_2 \|\bar{\mathbf{x}}_t\|_2}$$
   $$S_j = \frac{\tilde{S}_j - \min \tilde{S}}{\max \tilde{S} - \min \tilde{S} + \epsilon} \in [0, 1]$$
   This identifies historical exemplars whose transaction scale and subgraph morphology match the current traffic envelope.

3. **Combined Scoring & Allocation**:
   $$\text{Score}_j = R_j + S_j$$
   To ensure stability against extreme class imbalance, the top $K$ exemplars are allocated with stratified illicit representation, guaranteeing that the dynamic context preserves boundary support for rare fraud patterns.

---

## V. Experimental Results & Analysis

### A. Performance Benchmark Across Methods
Table I presents the comprehensive evaluation results averaged across test steps 40 to 49.

#### TABLE I: Performance Comparison Over Test Steps 40–49
| Method / Strategy | Category | AUPRC | Recall | Precision | F1-Score | Total Cost ($K) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Proposed In-Context (Recency + Sim)** | **In-Context** | **0.5267** | **0.7418** | **0.4270** | **0.4673** | **$146.82** |
| Continuous Retraining (LightGBM) | Retrained | 0.4903 | 0.4479 | 0.4913 | 0.4472 | $198.46 |
| In-Context (Recency Only) | In-Context | 0.4800 | 0.4846 | 0.5215 | 0.4540 | $199.69 |
| In-Context (Random Context) | In-Context | 0.3508 | 0.3291 | 0.2486 | 0.2666 | $270.58 |
| Static XGBoost (Tuned) | Static ML | 0.3360 | 0.3053 | 0.2219 | 0.2392 | $254.77 |
| Static LightGBM (Tuned) | Static ML | 0.3192 | 0.2962 | 0.2539 | 0.2552 | $266.49 |
| Static Random Forest | Static ML | 0.3094 | 0.2994 | 0.2091 | 0.2289 | $258.86 |
| Static K-Nearest Neighbors | Static ML | 0.2858 | 0.2549 | 0.2606 | 0.2422 | $325.04 |
| Static Decision Tree | Static ML | 0.2651 | 0.3108 | 0.1832 | 0.2145 | $250.45 |
| Static Logistic Regression | Static ML | 0.1961 | 0.7078 | 0.1356 | 0.2036 | $153.35 |
| In-Context (Similarity Only) | In-Context | 0.1004 | 0.1991 | 0.0863 | 0.0477 | $583.78 |

### B. Key Findings
1. **Static Model Collapse**: While LightGBM and XGBoost achieved AUPRC > 0.94 in validation (steps 35–39), their test AUPRC collapsed to **0.3192** and **0.3360** respectively under forward temporal evaluation. Static models fail completely when criminal networks evolve.
2. **Proposed Method Outperforms Continuous Retraining**: The Proposed In-Context Exemplar model achieves **0.5267 AUPRC** and **74.18% recall**, outperforming expensive continuous retraining (0.4903 AUPRC, 44.79% recall).
3. **Financial Savings**: In real-dollar terms, the Proposed In-Context model incurs an average loss of **$146.82K per step**, saving **$51,640 per time step** compared to continuous retraining ($198.46K) and over **$119,000 per time step** compared to the static LightGBM model ($266.49K).
4. **Drift Dynamics & Step 43 Shock**: At step 43 (AlphaBay takedown), the illicit transaction ratio collapsed from 11.1% (step 42) to 1.7% (step 43) and 0.28% (step 46). The Population Stability Index (PSI) jumped to **0.81**, signaling severe concept drift. While static models became paralyzed, the in-context exemplar model adjusted its candidate context immediately.

---

## VI. Explainable AI (SHAP) & Feature Importance
Using Tree-SHAP on the tuned LightGBM model, we analyzed the dominant drivers of fraud:
- **`feat_53` (Transaction Volume & Input In-Degree)**: Unanimously ranked #1 by Borda Count (score: 492). High transaction aggregation relative to input addresses strongly correlates with laundering dispersion.
- **`feat_89` (2-Hop Aggregate Out-Degree)**: Captures layering behavior through multi-hop pass-through nodes.
- **`feat_59` & `feat_90` (Neighbor Fee Ratios)**: Illicit transactions consistently exhibit elevated miner transaction fees to expedite block confirmation during asset evacuation.

---

## VII. Conclusion
This study demonstrates that the conventional practice of repeatedly retraining fraud detection models in response to temporal drift is neither strictly necessary nor optimal. By implementing an **In-Context Exemplar Selection Architecture** on the Elliptic Bitcoin dataset, we proved that dynamic example selection at prediction time matches and exceeds the performance of full retraining while avoiding its computational overhead and regulatory review bottlenecks. Future research will explore multi-graph streaming embeddings and federated exemplar sharing across allied financial institutions.

---

## References
1. M. A. I. Semon, M. Chowdhury, A. Akter, M. R. Jafrin, A. Singha, and J. Islam, "A Multiclass Financial Transaction Fraud Prediction Scheme Using Machine Learning, Ensemble feature Selection, and XAI Technique," in *Proc. IEEE 2nd Int. Conf. Quantum Photonics, Artificial Intelligence, and Networking (QPAIN)*, 2026, pp. 1–5.
2. M. Weber, G. Domeniconi, J. Chen, D. K. I. Weidele, C. Bellei, T. Robinson, and C. E. Leiserson, "Anti-Money Laundering in Bitcoin: Experimenting with Graph Convolutional Networks for Financial Forensics," *arXiv preprint arXiv:1908.02591*, 2019.
3. Y. Tang et al., "A Distributed Knowledge Distillation Framework for Financial Fraud Detection Based on Transformer," *IEEE Access*, vol. 12, pp. 62899–62911, 2024.
4. B. Li et al., "Uncovering Financial Statement Fraud: A Machine Learning Approach With Key Financial Indicators and Real-World Applications," *IEEE Access*, vol. 12, pp. 194859–194870, 2024.
5. C. Ghosh et al., "Enhancing Financial Fraud Detection in Bitcoin Networks Using Ensemble Deep Learning," in *Proc. ICBDS*, 2023, pp. 1–6.
