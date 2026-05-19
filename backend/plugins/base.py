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
        ...

    @abstractmethod
    def get_stream_url(self, track_id: str) -> str:
        ...
