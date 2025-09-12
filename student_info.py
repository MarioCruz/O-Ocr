from dataclasses import dataclass
from typing import Optional

@dataclass
class StudentInfo:
    student_name: str = ""
    school_name: str = ""
    poem_title: str = ""
    poem_theme: str = ""
    poem_language: str = ""
    
    @classmethod
    def from_tuple(cls, data_tuple):
        """Create StudentInfo from legacy tuple format"""
        if len(data_tuple) >= 5:
            return cls(*data_tuple[:5])
        return cls()