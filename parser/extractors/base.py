# -*- coding: utf-8 -*-
"""
Base Extractor Class
Interface for specialized data extraction modules.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extracts specific attributes from cleaned text.
        """
        pass
