# backend/ml/model.py

import torch
import torch.nn as nn


class RecSysNN(nn.Module):
    """
    Простая нейросеть для коллаборативной фильтрации:
    - эмбеддинги пользователей и треков
    - MLP поверх конкатенации
    - выход: скалярный скор (чем выше, тем лучше рекомендация)
    """

    def __init__(self, n_users: int, n_items: int, emb_dim: int = 64):
        super().__init__()

        self.user_emb = nn.Embedding(num_embeddings=n_users, embedding_dim=emb_dim)
        self.item_emb = nn.Embedding(num_embeddings=n_items, embedding_dim=emb_dim)

        self.mlp = nn.Sequential(
            nn.Linear(emb_dim * 2, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, user_ids: torch.Tensor, item_ids: torch.Tensor) -> torch.Tensor:
        """
        user_ids: LongTensor [batch_size]
        item_ids: LongTensor [batch_size]
        """
        u = self.user_emb(user_ids)   # [batch, emb_dim]
        i = self.item_emb(item_ids)   # [batch, emb_dim]
        x = torch.cat([u, i], dim=-1) # [batch, 2*emb_dim]
        out = self.mlp(x)             # [batch, 1]
        return out.squeeze(-1)        # [batch]
