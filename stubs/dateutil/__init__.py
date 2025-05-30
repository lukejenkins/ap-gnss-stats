"""
Stub file for the dateutil package to help IDE recognize it.
This file is not meant to be executed, only to provide type hints for the IDE.
"""

from typing import Any, Optional, Union
from datetime import datetime

class parser:
    """Stub for dateutil.parser"""
    
    @staticmethod
    def parse(timestr: str, 
              parserinfo: Any = None, 
              **kwargs) -> datetime:
        """
        Parse a string in one of the supported formats, 
        using the parserinfo parameters.
        
        Returns a datetime.datetime object.
        """
        ...
