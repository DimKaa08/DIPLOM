# backend/ml/train.py
import os

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

from backend.db.session import SessionLocal
from backend.db import models
from backend.ml.model import RecSysNN
from backend.ml.config import MODEL_PATH, MAPPINGS_PATH


# ─── DATASET ────────────────────────────────────────────────────────────────

class InteractionDataset(Dataset):
    def __init__(self, data):
        self.users  = torch.tensor([d["user_idx"] for d in data], dtype=torch.long)
        self.items  = torch.tensor([d["item_idx"] for d in data], dtype=torch.long)
        self.scores = torch.tensor([d["score"]    for d in data], dtype=torch.float32)

    def __len__(self):
        return len(self.scores)

    def __getitem__(self, idx):
        return self.users[idx], self.items[idx], self.scores[idx]


# ─── ОБУЧЕНИЕ ───────────────────────────────────────────────────────────────

def train_model(epochs: int = 5, batch_size: int = 32, lr: float = 0.01) -> bool:
    print("[ML Train] Старт сессии переобучения нейросети...")

    # ── 1. ЗАГРУЖАЕМ ДАННЫЕ ИЗ БД ────────────────────────────────────────────
    db = SessionLocal()
    try:
        interactions = db.query(models.UserInteraction).all()

        if len(interactions) < 10:
            print(f"[ML Train] Слишком мало данных ({len(interactions)} строк). Минимум: 10. Отмена.")
            return False

        # ── 2. СТРОИМ ДЕТЕРМИНИРОВАННЫЕ МАППИНГИ ─────────────────────────────
        # ИСПРАВЛЕНО: раньше использовались user_id % 2000 и hash(track_id) % 10000.
        # Проблемы: коллизии при > 2000 пользователях, нестабильность hash() между
        # запусками Python (рандомизируется с Python 3.3 по умолчанию).
        # Решение: строим явные словари {реальный_id → индекс_эмбеддинга}.
        # sorted() гарантирует одинаковый порядок при каждом запуске.
        unique_user_ids  = sorted({i.user_id  for i in interactions})
        unique_track_ids = sorted({i.track_id for i in interactions})  # Integer FK на tracks.id

        user2idx: dict[int, int] = {uid: idx for idx, uid in enumerate(unique_user_ids)}
        item2idx: dict[int, int] = {tid: idx for idx, tid in enumerate(unique_track_ids)}

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

    # ── 3. ПОДГОТОВКА PYTORCH СТРУКТУР ───────────────────────────────────────
    dataset    = InteractionDataset(formatted_data)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # Размер модели = реальное количество уникальных сущностей.
    # ИСПРАВЛЕНО: раньше RecSysNN(n_users=2000, n_items=10000) было захардкожено
    # в трёх местах и не масштабировалось с ростом данных.
    n_users = len(user2idx)
    n_items = len(item2idx)
    print(f"[ML Train] Размер модели: {n_users} пользователей, {n_items} треков")

    model = RecSysNN(n_users=n_users, n_items=n_items)

    # ── 4. FINE-TUNING: загружаем старые веса, если они есть ─────────────────
    if os.path.exists(MODEL_PATH):
        print("[ML Train] Найдены старые веса, пробуем дообучить...")
        try:
            checkpoint     = torch.load(MODEL_PATH, map_location="cpu")
            saved_n_users  = checkpoint.get("n_users", 0)
            saved_n_items  = checkpoint.get("n_items", 0)

            if saved_n_users == n_users and saved_n_items == n_items:
                # Размер не изменился — безопасно загружаем веса
                model.load_state_dict(checkpoint["state_dict"])
                print("[ML Train] Веса загружены. Дообучаем существующую модель.")
            else:
                # Данных стало больше — размер эмбеддингов вырос, старые веса
                # несовместимы по форме. Обучаем с нуля.
                print(
                    f"[ML Train] Размер изменился "
                    f"({saved_n_users}→{n_users} users, {saved_n_items}→{n_items} items). "
                    f"Обучаем с нуля."
                )
        except Exception as e:
            print(f"[ML Train] Не удалось загрузить старые веса: {e}. Обучаем с нуля.")

    # ── 5. ЦИКЛ ОБУЧЕНИЯ ─────────────────────────────────────────────────────
    model.train()
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    for epoch in range(epochs):
        epoch_loss = 0.0
        for batch_users, batch_items, batch_scores in dataloader:
            optimizer.zero_grad()
            predictions = model(batch_users, batch_items)
            loss = criterion(predictions, batch_scores)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * batch_users.size(0)

        print(f"  Эпоха {epoch + 1}/{epochs} | MSE loss: {epoch_loss / len(dataset):.4f}")

    # ── 6. СОХРАНЕНИЕ МОДЕЛИ И МАППИНГОВ ─────────────────────────────────────
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

    # Сохраняем веса вместе с размерами — чтобы при загрузке знать,
    # какого размера создавать RecSysNN, без хардкода констант.
    torch.save(
        {
            "state_dict": model.state_dict(),
            "n_users":    n_users,
            "n_items":    n_items,
        },
        MODEL_PATH,
    )

    # Маппинги нужны при инференсе: user_id → индекс, track.id → индекс.
    # Без них инференс вынужден использовать нестабильный hash() — мы это убрали.
    torch.save(
        {"user2idx": user2idx, "item2idx": item2idx},
        MAPPINGS_PATH,
    )

    print(f"[ML Train] Готово. Модель → {MODEL_PATH}, маппинги → {MAPPINGS_PATH}")
    return True


# Запуск вручную: python -m backend.ml.train
if __name__ == "__main__":
    train_model()