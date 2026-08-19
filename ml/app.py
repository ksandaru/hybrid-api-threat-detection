"""FastAPI inference service (Phase 5).

Loads the artefacts produced by ml/train.py once at startup and scores feature
vectors sent by the Express detection middleware.

The interface is deliberately narrow. The middleware sends a flat object of
named features and receives a score; it knows nothing about which models exist
or how their outputs are combined. Either side can therefore be replaced without
touching the other, which is what lets the Phase 9 evaluation construct its four
configurations by substitution rather than by editing the request path.

Endpoints:
    GET  /health   readiness, loaded artefacts, model versions
    GET  /meta     canonical feature order and active weights
    POST /predict  score one feature vector

Scoring:
    score = w_rf * P_rf(attack) + w_xgb * P_xgb(attack) + w_iso * normalised_iso

Random Forest and XGBoost emit calibrated probabilities directly. Isolation
Forest emits an unbounded anomaly score, which is mapped onto [0, 1] using
percentile bounds of the training-split score distribution recorded by
ml/train.py. Without that mapping the third term would silently dominate or
vanish depending on the scale the forest happened to produce.

Known limitation, measured in Phase 4 and repeated here because it bears
directly on how this score should be used: the classifiers assign zero
importance to four of the five flow features, because those are zero-filled
throughout the offline corpus. This service therefore carries useful signal for
SQL injection but close to none for brute force or credential stuffing. The rule
engine in the middleware computes those features live and is the stage that
detects them. Weighting in Phase 6 must account for that.
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

import joblib
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel, Field

MODEL_DIR = Path(__file__).parent / "models"

# Weights and threshold come from the artefact written by ml/train.py, so the
# service scores exactly the combination the operating point was measured
# against. Environment variables override, which is how Phase 9 sweeps them.
W_RF = W_XGB = W_ISO = None
ATTACK_THRESHOLD = None

app = FastAPI(
    title="Hybrid API Threat Detection - Inference Service",
    version="1.0.0",
)

STATE: Dict[str, object] = {"ready": False, "error": None}


def _env_float(name: str, default) -> float:
    """Read a float from the environment, treating unset and empty as absent.

    Docker Compose expands `${W_RF:-}` to an empty string rather than leaving
    the variable unset, so os.getenv returns "" and float("") raises. An
    optional override that is merely not being used must not stop the service
    from starting.
    """
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return float(default)
    try:
        return float(raw)
    except ValueError:
        print(f"[config] ignoring non-numeric {name}={raw!r}, using {default}")
        return float(default)


def _load() -> None:
    """Load every artefact once. Failures are recorded rather than raised so
    /health can report why the service is not ready instead of the process
    dying silently behind a restart loop."""
    try:
        meta = json.loads((MODEL_DIR / "feature_order.json").read_text(encoding="utf-8"))
        STATE["feature_order"] = meta["feature_order"]
        global W_RF, W_XGB, W_ISO, ATTACK_THRESHOLD
        op = meta.get("operating_point") or {}
        w = op.get("weights") or {}
        W_RF = _env_float("W_RF", w.get("random_forest", 0.4))
        W_XGB = _env_float("W_XGB", w.get("xgboost", 0.4))
        W_ISO = _env_float("W_ISO", w.get("isolation_forest", 0.2))
        ATTACK_THRESHOLD = _env_float(
            "ML_ATTACK_THRESHOLD", op.get("selected_threshold", 0.5))
        STATE["operating_point"] = op

        cal = meta.get("iso_calibration") or {}
        STATE["iso_p1"] = float(cal.get("p1", 0.0))
        STATE["iso_p99"] = float(cal.get("p99", 1.0))
        STATE["iso_calibrated"] = bool(cal)

        STATE["random_forest"] = joblib.load(MODEL_DIR / "random_forest.pkl")
        STATE["xgboost"] = joblib.load(MODEL_DIR / "xgboost.pkl")
        STATE["isolation_forest"] = joblib.load(MODEL_DIR / "isolation_forest.pkl")
        STATE["scaler"] = joblib.load(MODEL_DIR / "scaler.pkl")
        STATE["ready"] = True
        STATE["error"] = None
    except Exception as exc:  # noqa: BLE001 - reported through /health
        STATE["ready"] = False
        STATE["error"] = f"{type(exc).__name__}: {exc}"


@app.on_event("startup")
def startup() -> None:
    t0 = time.perf_counter()
    _load()
    STATE["load_ms"] = round((time.perf_counter() - t0) * 1000, 1)


class PredictRequest(BaseModel):
    features: Dict[str, float] = Field(
        ..., description="Feature name to value. Missing names default to 0.0."
    )
    threshold: Optional[float] = Field(
        None, description="Override the attack threshold for this call."
    )


def _vectorise(features: Dict[str, float]):
    """Order the incoming object by the canonical feature order.

    Ordering is taken from feature_order.json rather than from the request, so a
    client that sends the right names in the wrong order is still scored
    correctly. Unknown names are reported rather than silently dropped, since a
    typo would otherwise present as a plausible but wrong prediction.
    """
    order = STATE["feature_order"]
    missing = [n for n in order if n not in features]
    unexpected = [n for n in features if n not in order]
    vector = np.array([[float(features.get(n, 0.0)) for n in order]], dtype="float64")
    return vector, missing, unexpected


def _normalise_iso(raw: float) -> float:
    lo, hi = STATE["iso_p1"], STATE["iso_p99"]
    if hi <= lo:
        return 0.0
    return float(np.clip((raw - lo) / (hi - lo), 0.0, 1.0))


@app.get("/health")
def health():
    return {
        "status": "ok" if STATE["ready"] else "unavailable",
        "ready": STATE["ready"],
        "error": STATE["error"],
        "models": ["random_forest", "xgboost", "isolation_forest"],
        "iso_calibrated": STATE.get("iso_calibrated", False),
        "threshold": ATTACK_THRESHOLD,
        "load_ms": STATE.get("load_ms"),
    }


@app.get("/meta")
def meta():
    if not STATE["ready"]:
        return {"ready": False, "error": STATE["error"]}
    return {
        "ready": True,
        "feature_order": STATE["feature_order"],
        "weights": {"random_forest": W_RF, "xgboost": W_XGB, "isolation_forest": W_ISO},
        "attack_threshold": ATTACK_THRESHOLD,
        "iso_calibration": {"p1": STATE["iso_p1"], "p99": STATE["iso_p99"]},
        "operating_point": STATE.get("operating_point"),
    }


@app.post("/predict")
def predict(req: PredictRequest):
    started = time.perf_counter()

    if not STATE["ready"]:
        # The middleware treats any non-success as a reason to fall back to
        # rules, so this is reported plainly rather than as an exception.
        return {
            "score": 0.0,
            "is_attack": False,
            "error": STATE["error"] or "models not loaded",
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }

    vector, missing, unexpected = _vectorise(req.features)
    scaled = STATE["scaler"].transform(vector)

    t = time.perf_counter()
    p_rf = float(STATE["random_forest"].predict_proba(scaled)[0, 1])
    ms_rf = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    p_xgb = float(STATE["xgboost"].predict_proba(scaled)[0, 1])
    ms_xgb = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    raw_iso = float(-STATE["isolation_forest"].score_samples(scaled)[0])
    ms_iso = (time.perf_counter() - t) * 1000
    p_iso = _normalise_iso(raw_iso)

    score = W_RF * p_rf + W_XGB * p_xgb + W_ISO * p_iso
    threshold = req.threshold if req.threshold is not None else ATTACK_THRESHOLD

    return {
        "score": round(score, 6),
        "is_attack": bool(score >= threshold),
        "threshold": threshold,
        "details": {
            "random_forest": {"probability": round(p_rf, 6), "weight": W_RF, "ms": round(ms_rf, 3)},
            "xgboost": {"probability": round(p_xgb, 6), "weight": W_XGB, "ms": round(ms_xgb, 3)},
            "isolation_forest": {
                "raw": round(raw_iso, 6),
                "normalised": round(p_iso, 6),
                "weight": W_ISO,
                "ms": round(ms_iso, 3),
            },
            "missing_features": missing,
            "unexpected_features": unexpected,
        },
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
