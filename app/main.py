import logging
import math
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import Body, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "model" / "random_forest_ids.joblib"

bundle = joblib.load(MODEL_PATH)
model = bundle["model"]
features = bundle["features"]

app = FastAPI()


@app.exception_handler(RequestValidationError)
async def invalid_request_handler(_request, _exc):
    # Keep malformed JSON and wrong top-level shapes from echoing parser internals.
    return JSONResponse(status_code=422, content={"detail": "Invalid request body"})

@app.get("/health")
def health_check():
    return {"status": "healthy"}


def _validate_feature_map(sample: dict[str, Any]) -> None:
    expected = set(features)
    supplied = set(sample)
    missing = sorted(expected - supplied)
    unknown = sorted(supplied - expected)

    if missing or unknown:
        # Reject incomplete vectors and schema drift before they reach the model.
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Feature map must contain exactly the stored model features",
                "missing": missing,
                "unknown": unknown,
            },
        )

    invalid = []
    for name in features:
        value = sample[name]
        is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
        try:
            is_finite = is_number and math.isfinite(value)
        except (OverflowError, TypeError):
            is_finite = False
        if not is_finite:
            invalid.append(name)

    if invalid:
        # JSON strings/bools and non-finite floats can be silently coerced by Pandas.
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Every feature value must be a finite JSON number",
                "fields": invalid,
            },
        )


@app.post("/predict")
def predict(sample: dict[str, Any] = Body(...)):
    """Return the predicted class and model confidence, not objective accuracy."""
    _validate_feature_map(sample)

    # JSON object order is irrelevant; the stored training order is authoritative.
    sample_df = pd.DataFrame(
        [[sample[name] for name in features]],
        columns=features,
    )

    try:
        prediction = model.predict(sample_df)[0]
        probabilities = model.predict_proba(sample_df)[0]
        # Probability columns follow classes_, which need not equal array indexes.
        class_index = list(model.classes_).index(prediction)
        confidence = float(probabilities[class_index])
        label = "ATTACK" if prediction == 1 else "BENIGN"
        prediction_class = int(prediction)
    except Exception:
        # Do not expose model, filesystem, or stack-trace details to API clients.
        logger.exception("Inference failed")
        raise HTTPException(
            status_code=500,
            detail="Prediction could not be completed",
        ) from None

    return {
        "prediction": label,
        "class": prediction_class,
        "confidence": round(confidence, 4),
    }
