"""
Base Extractor Class
Interface for specialized data extraction modules.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, text: str) -> dict[str, Any]:
        """
        Extracts specific attributes from cleaned text.
        """
        pass
