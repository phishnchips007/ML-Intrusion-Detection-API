import joblib
import pandas as pd
from fastapi import FastAPI

app = FastAPI()

bundle = joblib.load("model/random_forest_ids.joblib")
model = bundle["model"]
features = bundle["features"]

from fastapi import FastAPI

app = FastAPI()

bundle = joblib.load("model/random_forest_ids.joblib")
model = bundle["model"]
features = bundle["features"]

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/predict")
def predict(sample: dict):
    sample_df = pd.DataFrame([sample], columns=features)

    prediction = model.predict(sample_df)[0]
    probabilities = model.predict_proba(sample_df)[0]

    label = "ATTACK" if prediction == 1 else "BENIGN"
    confidence = float(probabilities[prediction])

    return {
        "prediction": label,
        "class": int(prediction),
        "confidence": round(confidence, 4)
    }
