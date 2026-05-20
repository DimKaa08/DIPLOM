from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel


class TrackOut(BaseModel):
    id: str
    source: str
    title: str
    artist: str
    duration: Optional[int] = None
    thumbnail_url: Optional[str] = None


class BasePlugin(ABC):
    source_name: str

    @abstractmethod
    def search(self, query: str) -> List[TrackOut]:
        """
        Выполняет поиск треков по запросу.
        Возвращает список объектов TrackOut.
        """
        raise NotImplementedError

    @abstractmethod
    def get_stream_url(self, track_id: str) -> Optional[str]:
        """
        Возвращает прямой URL для стриминга аудио.
        Если источник не поддерживает стрим — возвращает None.
        """
        raise NotImplementedError
