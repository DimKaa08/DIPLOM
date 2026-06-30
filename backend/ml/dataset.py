# backend/ml/dataset.py

from typing import List, Tuple
import torch
from torch.utils.data import Dataset

class EventsDataset(Dataset):
    def __init__(self, samples: List[Tuple[int, int, float]]):
        """
        samples: список (user_idx, item_idx, label)
        """
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        u, i, y = self.samples[idx]
        return (
            torch.tensor(u, dtype=torch.long),
            torch.tensor(i, dtype=torch.long),
            torch.tensor(y, dtype=torch.float32),
        )
