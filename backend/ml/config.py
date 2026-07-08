# backend/ml/config.py

EVENT_WEIGHTS = {
    "play": 0.6,
    "finish": 1.0,
    "replay": 0.9,
    "like": 1.0,
    "favorite": 1.0,
    "skip": 0.1,
}

# гиперпараметры обучения
BATCH_SIZE = 256
LR = 1e-3
EPOCHS = 10
MODEL_PATH = "backend/ml/model.pt"
MAPPINGS_PATH = "backend/ml/mappings.pt"
