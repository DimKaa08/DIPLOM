# backend/ml/train.py
import os
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from backend.db.session import SessionLocal
from backend.db import models
from backend.ml.model import RecSysNN
from backend.ml.config import MODEL_PATH

# 1. PyTorch Dataset для загрузки данных из SQLAlchemy
class InteractionDataset(Dataset):
    def __init__(self, data):
        self.users = torch.tensor([d['user_idx'] for d in data], dtype=torch.long)
        self.items = torch.tensor([d['item_idx'] for d in data], dtype=torch.long)
        self.scores = torch.tensor([d['score'] for d in data], dtype=torch.float32)

    def __len__(self):
        return len(self.scores)

    def __getitem__(self, idx):
        return self.users[idx], self.items[idx], self.scores[idx]

def train_model(epochs: int = 5, batch_size: int = 32, lr: float = 0.01):
    print("[ML Train] Старт сессии переобучения нейросети...")
    
    # 2. Извлекаем логи из базы данных
    db = SessionLocal()
    try:
        interactions = db.query(models.UserInteraction).all()
        if len(interactions) < 10:
            print(f"[ML Train] Слишком мало данных для обучения (всего {len(interactions)} строк). Отмена.")
            return False
        
        # Форматируем данные под хэш-маппинг твоей модели
        formatted_data = []
        for inter in interactions:
            formatted_data.append({
                "user_idx": inter.user_id % 2000,
                "item_idx": abs(hash(inter.track_id)) % 10000,
                "score": float(inter.engagement_score)
            })
    finally:
        db.close()

    # 3. Подготовка PyTorch структур
    dataset = InteractionDataset(formatted_data)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # Инициализируем модель (с теми же размерами эмбеддингов)
    model = RecSysNN(n_users=2000, n_items=10000)
    
    # Если старый файл модели существует, учим не с нуля, а дообучаем (Fine-tuning)
    if os.path.exists(MODEL_PATH):
        print("[ML Train] Найдены старые веса. Загружаем для дообучения...")
        try:
            checkpoint = torch.load(MODEL_PATH, map_location=torch.device('cpu'))
            if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
                model.load_state_dict(checkpoint["state_dict"])
            else:
                model.load_state_dict(checkpoint)
        except Exception as e:
            print("[ML Train] Не удалось загрузить старые веса, начнем с нуля:", e)

    model.train()
    criterion = nn.MSELoss() # Минимизируем среднеквадратичную ошибку предсказания score
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    # 4. Цикл обучения
    for epoch in range(epochs):
        epoch_loss = 0.0
        for batch_users, batch_items, batch_scores in dataloader:
            optimizer.zero_grad()
            
            # Прямой проход (Forward pass)
            predictions = model(batch_users, batch_items)
            loss = criterion(predictions, batch_scores)
            
            # Обратный проход (Backpropagation)
            loss.backward()
            optimizer.step()
            
            epoch_loss += loss.item() * batch_users.size(0)
            
        total_epoch_loss = epoch_loss / len(dataset)
        print(f" -> Эпоха {epoch+1}/{epochs} | Loss (MSE): {total_epoch_loss:.4f}")

    # 5. Сохранение обновленных весов обратно в файл
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    torch.save(model.state_dict(), MODEL_PATH)
    print(f"[ML Train] Модель успешно обучена и сохранена в: {MODEL_PATH}")
    return True

if __name__ == "__main__":
    # Скрипт можно запускать вручную из терминала: python -m backend.ml.train
    train_model()