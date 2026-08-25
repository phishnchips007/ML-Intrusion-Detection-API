import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

import app.main as main


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = PROJECT_ROOT / "samples" / "sample_flow.json"


@pytest.fixture
def sample():
    return json.loads(SAMPLE_PATH.read_text())


@pytest.fixture
def client():
    return TestClient(main.app)


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_service_loads_from_an_unrelated_working_directory(tmp_path):
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from fastapi.testclient import TestClient; "
                "from app.main import app; "
                "print(TestClient(app).get('/health').status_code)"
            ),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "200"


def test_known_sample_is_attack_with_model_confidence(client, sample):
    response = client.post("/predict", json=sample)

    assert response.status_code == 200
    assert response.json() == {
        "prediction": "ATTACK",
        "class": 1,
        "confidence": 1.0,
    }


def test_json_key_order_does_not_change_prediction(client, sample):
    reversed_sample = dict(reversed(list(sample.items())))

    response = client.post("/predict", json=reversed_sample)

    assert response.status_code == 200
    assert response.json()["class"] == 1


def test_missing_feature_is_rejected(client, sample):
    missing_feature = next(iter(sample))
    del sample[missing_feature]

    response = client.post("/predict", json=sample)

    assert response.status_code == 422
    assert response.json()["detail"]["missing"] == [missing_feature]


def test_unknown_feature_is_rejected(client, sample):
    sample["unexpected feature"] = 1

    response = client.post("/predict", json=sample)

    assert response.status_code == 422
    assert response.json()["detail"]["unknown"] == ["unexpected feature"]


@pytest.mark.parametrize("invalid_value", [True, "1", None, [1], {"value": 1}])
def test_non_numeric_feature_values_are_rejected(client, sample, invalid_value):
    feature = next(iter(sample))
    sample[feature] = invalid_value

    response = client.post("/predict", json=sample)

    assert response.status_code == 422
    assert response.json()["detail"]["fields"] == [feature]


@pytest.mark.parametrize("invalid_value", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_feature_values_are_rejected(client, sample, invalid_value):
    feature = next(iter(sample))
    sample[feature] = invalid_value

    response = client.post(
        "/predict",
        content=json.dumps(sample),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["fields"] == [feature]


def test_exponent_overflow_is_rejected(client, sample):
    feature = next(iter(sample))
    sample[feature] = "EXPONENT_OVERFLOW"
    request_body = json.dumps(sample).replace('"EXPONENT_OVERFLOW"', "1e309", 1)

    response = client.post(
        "/predict",
        content=request_body,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["fields"] == [feature]


def test_malformed_json_returns_controlled_error(client):
    response = client.post(
        "/predict",
        content="{not valid json",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request body"}


def test_confidence_uses_predicted_class_position(client, sample, monkeypatch):
    class NonIndexClassModel:
        classes_ = [7, 1]

        def predict(self, _frame):
            return [1]

        def predict_proba(self, _frame):
            return [[0.8, 0.2]]

    monkeypatch.setattr(main, "model", NonIndexClassModel())

    response = client.post("/predict", json=sample)

    assert response.status_code == 200
    assert response.json() == {
        "prediction": "ATTACK",
        "class": 1,
        "confidence": 0.2,
    }


def test_model_errors_do_not_leak_exception_details(client, sample, monkeypatch):
    class BrokenModel:
        def predict(self, _frame):
            raise RuntimeError("secret path: /private/model.joblib")

    monkeypatch.setattr(main, "model", BrokenModel())

    response = client.post("/predict", json=sample)

    assert response.status_code == 500
    assert response.json() == {"detail": "Prediction could not be completed"}
