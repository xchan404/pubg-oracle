"""
Frames Extractor Module
Extracts rare frames (Plane, Conqueror, RE2, Godzilla).
"""

from typing import Any

from parser.extractors.base import BaseExtractor
from parser.regex_parser import extract_frames_info


class FrameExtractor(BaseExtractor):
    def extract(self, text: str) -> dict[str, Any]:
        frames = extract_frames_info(text)
        return {
            "frames_str": frames.get('frames_str', ''),
            "conqueror_frames_count": frames.get('conqueror_frames_count'),
            "has_conqueror_frame": frames.get('has_conqueror_frame', False),
            "has_plane_frame": frames.get('has_plane_frame', False),
            "has_re2_frame": frames.get('has_re2_frame', False)
        }
