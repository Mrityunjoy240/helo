
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json

router = APIRouter()
LOG_DIR = Path("logs")

@router.get("/logs")
async def get_logs(lines: int = 50, level: str = None):
    """
    Get recent logs from app.log
    lines: Number of recent lines to return
    level: Filter by log level (ERROR, INFO, etc.)
    """
    log_file = LOG_DIR / "app.log"
    if not log_file.exists():
         return {"logs": []}
         
    results = []
    try:
        # Read file in reverse roughly or just read all and tail
        # For simplicity, reading all and tailing (file rotated at 10MB)
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            
        # Filter and parse
        for line in reversed(all_lines):
            try:
                log_obj = json.loads(line)
                if level and log_obj.get("level") != level:
                    continue
                results.append(log_obj)
                if len(results) >= lines:
                    break
            except json.JSONDecodeError:
                continue
                
        return {"logs": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs/errors")
async def get_error_logs(lines: int = 50):
    """Get recent error logs"""
    return await get_logs(lines=lines, level="ERROR")
