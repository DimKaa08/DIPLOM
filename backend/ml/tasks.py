# backend/ml/tasks.py
import os
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from backend.celery_app import celery_app
from backend.db.session import SessionLocal
from backend.db import models
from backend.ml.model import RecSysNN
from backend.ml.train import InteractionDataset
from backend.ml.config import MODEL_PATH, MAPPINGS_PATH


@celery_app.task(
    bind=True,
    name="ml.train",
    max_retries=0,       # не повторять — нет смысла, данные те же
    time_limit=600,      # убить задачу, если она висит > 10 минут
    soft_time_limit=540, # за 1 минуту до убийства — мягкое предупреждение
)
def train_task(self, epochs: int = 5, batch_size: int = 16, lr: float = 0.01):
    """
    Celery-задача переобучения нейросети.

    bind=True даёт доступ к self.update_state() — так фронтенд может
    опрашивать /train-status/{task_id} и видеть прогресс в реальном времени.

    Статусы задачи:
      PENDING  — задача в очереди, воркер ещё не взял
      STARTED  — воркер взял задачу
      PROGRESS — обучение идёт, в meta есть номер эпохи
      SUCCESS  — готово, в result детали
      FAILURE  — что-то пошло не так, в result traceback
    """

    # ── 1. ЗАГРУЖАЕМ ДАННЫЕ ───────────────────────────────────────────────────
    self.update_state(state="PROGRESS", meta={"step": "Загрузка данных из БД", "epoch": 0, "epochs": epochs})

    db = SessionLocal()
    try:
        interactions = db.query(models.UserInteraction).all()

        if len(interactions) < 10:
            return {
                "success": False,
                "reason": f"Недостаточно данных: {len(interactions)} строк, нужно минимум 10.",
            }

        unique_user_ids  = sorted({i.user_id  for i in interactions})
        unique_track_ids = sorted({i.track_id for i in interactions})

        user2idx = {uid: idx for idx, uid in enumerate(unique_user_ids)}
        item2idx = {tid: idx for idx, tid in enumerate(unique_track_ids)}

        formatted_data = [
            {
                "user_idx": user2idx[i.user_id],
                "item_idx": item2idx[i.track_id],
                "score":    float(i.engagement_score),
            }
            for i in interactions
        ]

    finally:
        db.close()

    # ── 2. ПОДГОТОВКА МОДЕЛИ ──────────────────────────────────────────────────
    self.update_state(
        state="PROGRESS",
        meta={"step": "Инициализация модели", "epoch": 0, "epochs": epochs},
    )

    n_users = len(user2idx)
    n_items = len(item2idx)
    model   = RecSysNN(n_users=n_users, n_items=n_items)

    if os.path.exists(MODEL_PATH):
        try:
            checkpoint    = torch.load(MODEL_PATH, map_location="cpu")
            saved_n_users = checkpoint.get("n_users", 0)
            saved_n_items = checkpoint.get("n_items", 0)

            if saved_n_users == n_users and saved_n_items == n_items:
                model.load_state_dict(checkpoint["state_dict"])
        except Exception as e:
            print(f"[ML Task] Не удалось загрузить старые веса: {e}. Обучаем с нуля.")

    # ── 3. ЦИКЛ ОБУЧЕНИЯ ──────────────────────────────────────────────────────
    dataset    = InteractionDataset(formatted_data)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    model.train()
    optimizer  = torch.optim.Adam(model.parameters(), lr=lr)
    criterion  = nn.MSELoss()

    for epoch in range(epochs):
        # Обновляем статус перед каждой эпохой — фронтенд увидит прогресс
        self.update_state(
            state="PROGRESS",
            meta={
                "step":   f"Обучение: эпоха {epoch + 1} из {epochs}",
                "epoch":  epoch + 1,
                "epochs": epochs,
            },
        )

        epoch_loss = 0.0
        for batch_users, batch_items, batch_scores in dataloader:
            optimizer.zero_grad()
            predictions = model(batch_users, batch_items)
            loss        = criterion(predictions, batch_scores)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * batch_users.size(0)

        print(f"[ML Task] Эпоха {epoch + 1}/{epochs} | MSE: {epoch_loss / len(dataset):.4f}")

    # ── 4. СОХРАНЕНИЕ ─────────────────────────────────────────────────────────
    self.update_state(state="PROGRESS", meta={"step": "Сохранение весов", "epoch": epochs, "epochs": epochs})

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

    torch.save(
        {"state_dict": model.state_dict(), "n_users": n_users, "n_items": n_items},
        MODEL_PATH,
    )
    torch.save({"user2idx": user2idx, "item2idx": item2idx}, MAPPINGS_PATH)

    return {
        "success": True,
        "n_users": n_users,
        "n_items": n_items,
        "epochs":  epochs,
    }