"""Load trusted local artifacts once; use their saved preprocessing for inference."""

import json
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost
from xgboost import XGBClassifier

RISK_RULES = {
    "ATTACK_with_anomaly": {"score": 90, "level": "HIGH"},
    "ATTACK_without_anomaly": {"score": 80, "level": "HIGH"},
    "BENIGN_with_anomaly": {"score": 40, "level": "MEDIUM"},
    "BENIGN_without_anomaly": {"score": 0, "level": "LOW"},
}


class ModelLoadError(RuntimeError):
    pass


class FeatureValidationError(ValueError):
    def __init__(self, errors):
        super().__init__("Flow feature names do not match the trained schema.")
        self.errors = errors


def model_package_version(name):
    # xgboost and the smaller Linux xgboost-cpu distribution provide the same module.
    return xgboost.__version__ if name == "xgboost" else version(name)


def assess_risk(predicted_class, anomaly_flag):
    suffix = "with_anomaly" if anomaly_flag else "without_anomaly"
    rule = RISK_RULES[f"{predicted_class}_{suffix}"]
    return rule["score"], rule["level"]


class ModelService:
    def __init__(self, artifacts_dir):
        self.artifacts_dir = Path(artifacts_dir)
        self.metadata = self._read("model_params.json")
        self.schema = self._read("feature_schema.json")
        self.evaluation = self._read("evaluation_metrics.json")
        comparison_path = self.artifacts_dir.parent / "reports/model_comparison.json"
        self.comparison = json.loads(comparison_path.read_text(encoding="utf-8")) if comparison_path.is_file() else None
        self.label_mapping = self._read("label_mapping.json")
        if self.metadata.get("eligible_for_api_demo") is not True:
            raise ModelLoadError("The exported model has not passed its fixed quality gate.")
        if self.label_mapping != {"BENIGN": 0, "ATTACK": 1}:
            raise ModelLoadError("Expected the BENIGN/ATTACK binary label mapping.")
        self.feature_names = self.schema["feature_names"]
        if not self.feature_names or len(set(self.feature_names)) != len(self.feature_names):
            raise ModelLoadError("Model feature names must be nonempty and unique.")
        self.model_version = self.metadata["model_version"]
        for name, expected in self.metadata["versions"].items():
            if name != "python" and model_package_version(name) != expected:
                raise ModelLoadError(f"Install the recorded {name}=={expected} from requirements-model.txt.")

        selected = self.metadata["selected_candidate"]
        if selected == "xgboost":
            # The Colab Python snapshot is not portable to this Windows runtime.
            self.model = XGBClassifier(n_jobs=2)
            self.model.load_model(self.artifacts_dir / "model.ubj")
            self.model_format = "xgboost_ubjson"
        elif selected == "random_forest":
            self.model = joblib.load(self.artifacts_dir / "model.joblib")
            self.model_format = "joblib"
        else:
            raise ModelLoadError("Unsupported classifier type.")
        self.preprocessor = joblib.load(self.artifacts_dir / "preprocessor.joblib")
        self.anomaly_model = joblib.load(self.artifacts_dir / "anomaly_model.joblib")
        if int(self.preprocessor.n_features_in_) != len(self.feature_names):
            raise ModelLoadError("The saved preprocessing input count differs from the schema.")
        selected_count = len(self.schema["selected_feature_names"])
        if int(self.model.n_features_in_) != selected_count or int(self.anomaly_model.n_features_in_) != selected_count:
            raise ModelLoadError("The classifier, anomaly model and selected feature count differ.")
        if set(self.model.classes_.tolist()) != {0, 1}:
            raise ModelLoadError("The classifier classes differ from the binary label mapping.")

    def _read(self, filename):
        return json.loads((self.artifacts_dir / filename).read_text(encoding="utf-8"))

    def validate_features(self, flows):
        expected = set(self.feature_names)
        errors = []
        for index, flow in enumerate(flows):
            supplied = set(flow.features)
            if supplied != expected:
                errors.append({
                    "flow_index": index,
                    "missing_features": sorted(expected - supplied),
                    "unknown_features": sorted(supplied - expected),
                })
        if errors:
            raise FeatureValidationError(errors)

    def predict(self, flows):
        self.validate_features(flows)
        # DataFrame columns explicitly restore training order, independent of JSON order.
        frame = pd.DataFrame([flow.features for flow in flows], columns=self.feature_names, dtype=float)
        prepared = self.preprocessor.transform(frame)
        probabilities = np.asarray(self.model.predict_proba(prepared))
        scores = -self.anomaly_model.decision_function(prepared)
        if not np.isfinite(probabilities).all() or not np.isfinite(scores).all():
            raise RuntimeError("Model returned non-finite prediction values.")
        if probabilities.shape != (len(flows), 2) or (probabilities < 0).any() or (probabilities > 1).any():
            raise RuntimeError("Model returned invalid class probabilities.")
        classes = self.model.classes_[probabilities.argmax(axis=1)]
        inverse = {value: name for name, value in self.label_mapping.items()}
        attack_column = list(self.model.classes_).index(1)
        results = []
        for index, class_id in enumerate(classes):
            predicted_class = inverse[int(class_id)]
            anomaly_flag = bool(scores[index] > 0)
            score, level = assess_risk(predicted_class, anomaly_flag)
            results.append({
                "predicted_class": predicted_class,
                "predicted_attack_category": None,
                "confidence": float(probabilities[index].max()),
                "confidence_type": "uncalibrated_model_probability",
                "attack_probability": float(probabilities[index, attack_column]),
                "anomaly_score": float(scores[index]),
                "anomaly_flag": anomaly_flag,
                "risk_level": level,
                "risk_score": score,
                "model_version": self.model_version,
                "source": flows[index].source,
            })
        return results

    def info(self):
        return {
            "active_model": self.metadata["selected_candidate"],
            "model_version": self.model_version,
            "model_format": self.model_format,
            "classification_mode": "binary",
            "supported_classes": ["BENIGN", "ATTACK"],
            "training_attack_labels": self.schema["supported_attack_labels"],
            "attack_category_prediction_supported": False,
            "feature_names": self.feature_names,
            "input_feature_count": len(self.feature_names),
            "selected_feature_count": len(self.schema["selected_feature_names"]),
            "missing_values": "Send null for an unavailable value; keep every required feature key.",
            "probability_note": "Confidence and attack_probability are uncalibrated model probabilities.",
            "anomaly_note": "Higher -decision_function is more unusual; >0 flags an anomaly. It is not a probability or attack category.",
            "risk_rules": RISK_RULES,
            "risk_note": "Rule-based alert priority scores, not measured attack probabilities.",
            "evaluation": self.evaluation,
            "comparison": self.comparison,
            "training": self.metadata,
            "scope": "Educational prototype trained on BENIGN and DDoS in one CIC-IDS2017 capture.",
        }
