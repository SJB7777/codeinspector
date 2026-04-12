from logging import Filter
from pydantic import BaseModel

class FilterConfig(BaseModel):
    max_file_size_kb: float
    extensions: list[str]
    exclude_patterns: list[str]

class Config(BaseModel):
    filter: FilterConfig
    output: dict