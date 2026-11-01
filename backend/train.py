"""Reproduce evaluation with preprocessing learned only from training data."""
from pathlib import Path
import hashlib
import json
import pickle
import platform
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, ConfusionMatrixDisplay, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parent
FEATURES = ['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']


def train():
    data_path = ROOT / 'data' / 'Crop_recommendation.csv'
    data = pd.read_csv(data_path)
    if data[FEATURES + ['label']].isna().any().any():
        raise ValueError('Dataset contains missing values; review before training.')
    if not np.isfinite(data[FEATURES].to_numpy()).all():
        raise ValueError('Dataset contains non-finite feature values.')
    if data.duplicated().any():
        raise ValueError('Dataset contains duplicate rows; review before splitting.')
    encoder = LabelEncoder().fit(data['label'])
    X_train, X_test, y_train, y_test = train_test_split(
        data[FEATURES], encoder.transform(data['label']),
        test_size=0.2, random_state=42, stratify=data['label'])
    models = {
        'Dummy baseline': DummyClassifier(strategy='most_frequent'),
        'Decision Tree': DecisionTreeClassifier(random_state=42),
        'Random Forest': RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=1),
    }
    # Compare on training folds only. Retain the original Random Forest deployment choice.
    # The held-out test is used for reporting, never for hyperparameter tuning/selection.
    results, fitted = {}, {}
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    output = ROOT.parent / 'evaluation'
    output.mkdir(exist_ok=True)
    for name, estimator in models.items():
        pipeline = make_pipeline(StandardScaler(), estimator)
        cv = cross_val_score(pipeline, X_train, y_train, cv=folds, scoring='accuracy')
        start = time.perf_counter()
        pipeline.fit(X_train, y_train)
        fit_seconds = time.perf_counter() - start
        start = time.perf_counter()
        predicted = pipeline.predict(X_test)
        predict_seconds = time.perf_counter() - start
        results[name] = {
            'accuracy': accuracy_score(y_test, predicted),
            'macro_f1': f1_score(y_test, predicted, average='macro', zero_division=0),
            'cv_accuracy_mean': float(cv.mean()), 'cv_accuracy_std': float(cv.std()),
            'correct': int((predicted == y_test).sum()), 'incorrect': int((predicted != y_test).sum()),
            'fit_seconds': fit_seconds, 'predict_seconds': predict_seconds,
            'classification_report': classification_report(y_test, predicted, target_names=encoder.classes_,
                                                          output_dict=True, zero_division=0),
        }
        fitted[name] = pipeline
    pipeline = fitted['Random Forest']
    predicted = pipeline.predict(X_test)
    cm = confusion_matrix(y_test, predicted)
    pd.DataFrame(cm, index=encoder.classes_, columns=encoder.classes_).to_csv(output / 'confusion_matrix.csv')
    fig, ax = plt.subplots(figsize=(12, 11))
    ConfusionMatrixDisplay(cm, display_labels=encoder.classes_).plot(ax=ax, cmap='Greens', colorbar=False, xticks_rotation=90)
    ax.set_title('Random Forest — held-out test set (440 samples)')
    fig.tight_layout()
    fig.savefig(output / 'confusion_matrix.png', dpi=150)
    plt.close(fig)
    errors = X_test.copy()
    errors['actual'] = encoder.inverse_transform(y_test)
    errors['predicted'] = encoder.inverse_transform(predicted)
    errors[errors.actual != errors.predicted].to_csv(output / 'misclassified_samples.csv', index_label='source_row')
    summary = {
        'dataset_sha256': hashlib.sha256(data_path.read_bytes()).hexdigest(),
        'rows': len(data), 'features': FEATURES, 'classes': encoder.classes_.tolist(),
        'class_counts': {k: int(v) for k, v in data.label.value_counts().sort_index().items()},
        'missing_values': int(data.isna().sum().sum()), 'duplicate_rows': int(data.duplicated().sum()),
        'train_samples': len(X_train), 'test_samples': len(X_test), 'seed': 42,
        'split': '80/20 stratified; scaler fitted on training data only; 5-fold CV within training set',
        'deployed_model': 'Random Forest',
        'versions': {'python': platform.python_version(), 'sklearn': sklearn.__version__, 'numpy': np.__version__, 'pandas': pd.__version__},
        'models': results,
        'limitations': ['Single dataset; no independent farm or region validation.',
                       'Dataset source, license, nutrient units and rainfall period require confirmation from the team.',
                       'Accuracy is crop-label classification accuracy, not yield prediction or guaranteed farming suitability.'],
    }
    (output / 'metrics.json').write_text(json.dumps(summary, indent=2))
    pd.DataFrame([{k: v for k, v in result.items() if k != 'classification_report'} | {'model': name}
                  for name, result in results.items()]).to_csv(output / 'model_comparison.csv', index=False)
    for filename, obj in [('model.pkl', pipeline.steps[-1][1]), ('scaler.pkl', pipeline.steps[0][1]), ('label_encoder.pkl', encoder)]:
        with (ROOT / 'models' / filename).open('wb') as stream:
            pickle.dump(obj, stream)
    print(pd.read_csv(output / 'model_comparison.csv').to_string(index=False))
    print('\nMisclassified Random Forest examples:')
    print(errors[errors.actual != errors.predicted].to_string())
    return summary


if __name__ == '__main__':
    train()
