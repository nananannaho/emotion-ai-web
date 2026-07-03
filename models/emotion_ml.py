"""scikit-learn 감정 분류기 (클라우드 경량)."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from config import EMOTION_LABELS, WEIGHTS_DIR
from models.emotion_features import extract_face_features
from models.emotion_infer import prepare_face_gray

logger = logging.getLogger(__name__)

CLF_PATH = WEIGHTS_DIR / "emotion_clf.joblib"


class ThinRandomForest:
    """RandomForest 트리 일부만 보관해 joblib 용량을 줄인 래퍼."""

    def __init__(self, trees, classes: np.ndarray, n_features: int):
        self.estimators_ = list(trees)
        self.classes_ = np.asarray(classes)
        self.n_features_in_ = int(n_features)
        self.n_classes_ = len(self.classes_)

    @classmethod
    def from_random_forest(cls, rf, n_trees: int) -> "ThinRandomForest":
        trees = rf.estimators_[:n_trees]
        return cls(trees, rf.classes_, rf.n_features_in_)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        preds = np.array([t.predict(X) for t in self.estimators_])
        n = X.shape[0]
        out = np.zeros((n, self.n_classes_), dtype=np.float64)
        weight = 1.0 / len(self.estimators_)
        for i in range(n):
            vals, cnts = np.unique(preds[:, i], return_counts=True)
            for val, cnt in zip(vals, cnts):
                out[i, int(val)] = cnt * weight
        return out

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


class EmotionMLClassifier:
    def __init__(self):
        self._model = None
        self._labels = EMOTION_LABELS
        self._source = ""
        self._load()

    def _load(self):
        if not CLF_PATH.exists():
            return
        try:
            import joblib

            data = joblib.load(CLF_PATH)
            self._model = data["model"]
            self._labels = list(data.get("labels", EMOTION_LABELS))
            self._source = str(data.get("source", ""))
            logger.info("감정 ML 분류기 로드: %s (%s)", CLF_PATH, self._source or "unknown")
        except Exception as exc:
            logger.warning("감정 ML 로드 실패: %s", exc)
            self._model = None

    @property
    def available(self) -> bool:
        return self._model is not None

    @property
    def fer_trained(self) -> bool:
        return "fer2013" in self._source.lower()

    def predict_distribution(self, face_gray: np.ndarray) -> dict[str, float]:
        if not self._model:
            return {}
        face = prepare_face_gray(face_gray)
        feat = extract_face_features(face).reshape(1, -1)
        if hasattr(self._model, "predict_proba"):
            probs = self._model.predict_proba(feat)[0]
            classes = self._model.classes_
            dist = {self._labels[int(c)]: float(probs[i]) for i, c in enumerate(classes)}
        else:
            pred = int(self._model.predict(feat)[0])
            emo = self._labels[pred]
            dist = {e: (1.0 if e == emo else 0.0) for e in self._labels}
        total = sum(dist.values()) or 1.0
        return {k: v / total for k, v in dist.items()}
