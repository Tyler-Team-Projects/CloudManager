from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class CloudFile(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int
    modified_at: Optional[datetime] = None
    mime_type: Optional[str] = None
    file_id: Optional[str] = None
    hash: Optional[str] = None
    hash_type: str = "md5"
    is_downloaded: bool = False
    is_synced: bool = False
    last_checked: Optional[datetime] = None