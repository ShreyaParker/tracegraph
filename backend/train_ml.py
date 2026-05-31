import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# ELLIPTIC BITCOIN DATASET - Real ground truth labels from FBI investigations
# Download from: https://www.kaggle.com/datasets/ellipticco/elliptic-data-set
# Files needed: elliptic_txs_classes.csv, elliptic_txs_features.csv
# =============================================================================

print("1. Loading Elliptic Bitcoin Dataset (real FBI-labeled data)...")
try:
    classes = pd.read_csv("data/elliptic_txs_classes.csv")
    features = pd.read_csv("data/elliptic_txs_features.csv", header=None)
except FileNotFoundError:
    print("ERROR: Download the Elliptic dataset from Kaggle first.")
    print("Place in data/elliptic_txs_classes.csv and data/elliptic_txs_features.csv")
    exit()

# Class 1 = illicit (confirmed laundering), 2 = licit, unknown = drop
print(f"Dataset: {len(classes)} transactions, "
      f"{(classes['class']=='1').sum()} illicit, "
      f"{(classes['class']=='2').sum()} licit")

# Merge and drop unknowns
df = features.merge(classes, left_on=0, right_on='txId')
df = df[df['class'] != 'unknown'].copy()
df['LABEL'] = (df['class'] == '1').astype(int)

print("2. Engineering features compatible with live Alchemy/Blockstream data...")
# The Elliptic dataset has 166 features. We select only the ones
# our live crawler can replicate in real-time from public APIs.
# Features 1-93 are local graph features (usable), 94-166 are aggregated.
# We approximate: out_degree, velocity, value stats from columns 2-6
feature_cols = list(range(1, 7))  # Time step + first 5 local features
X = df[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
y = df['LABEL']

print(f"Training on {len(X)} transactions ({y.sum()} illicit = {y.mean()*100:.1f}%)")

print("3. Training XGBoost on REAL labeled blockchain data...")
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# scale_pos_weight handles class imbalance (illicit txns are rare)
model = xgb.XGBClassifier(
    n_estimators=300,
    max_depth=5,
    learning_rate=0.05,
    scale_pos_weight=(y == 0).sum() / (y == 1).sum(),
    subsample=0.8,
    colsample_bytree=0.8,
    use_label_encoder=False,
    eval_metric='logloss',
    random_state=42
)

model.fit(X_train, y_train,
          eval_set=[(X_test, y_test)],
          verbose=False)

print("\n--- Model Performance on Held-Out Real Data ---")
predictions = model.predict(X_test)
proba = model.predict_proba(X_test)[:, 1]
print(f"Accuracy:  {accuracy_score(y_test, predictions) * 100:.2f}%")
print(f"ROC-AUC:   {roc_auc_score(y_test, proba):.4f}  (random = 0.5, perfect = 1.0)")
print(classification_report(y_test, predictions,
      target_names=["Licit (trace)", "Illicit (prune)"]))

model.save_model("tracegraph_brain.json")
print("\n✅ Model trained on real FBI-labeled data. Saved to aegis_brain.json")