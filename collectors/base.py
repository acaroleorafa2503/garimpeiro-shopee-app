
from abc import ABC, abstractmethod

class Collector(ABC):
    @abstractmethod
    def collect(self, product: dict) -> dict:
        """Return public market signals for one product."""
        raise NotImplementedError
