
import shutil
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from app.config import settings

logger = logging.getLogger(__name__)

class BackupService:
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        
        # Directories to backup
        self.targets = [
            Path(settings.upload_dir),
            Path(settings.chroma_persist_dir)
        ]
        
    def create_backup(self) -> Dict:
        """
        Create a zip backup of the data directories.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
        backup_path = self.backup_dir / backup_name
        
        try:
            # Create a temporary folder to collect files
            temp_dir = self.backup_dir / "temp_backup"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir()
            
            files_count = 0
            
            # Copy targets to temp dir
            for target in self.targets:
                if target.exists():
                    dest = temp_dir / target.name
                    if target.is_dir():
                        shutil.copytree(target, dest)
                        files_count += len(list(target.rglob('*')))
                    else:
                        shutil.copy2(target, dest)
                        files_count += 1
                else:
                    logger.warning(f"Backup target not found: {target}")
            
            # Zip the temp dir
            zip_path = shutil.make_archive(str(backup_path), 'zip', temp_dir)
            
            # Cleanup temp
            shutil.rmtree(temp_dir)
            
            logger.info(f"Backup created successfully: {zip_path}")
            
            return {
                "filename": f"{backup_name}.zip",
                "path": zip_path,
                "timestamp": timestamp,
                "size_bytes": os.path.getsize(zip_path),
                "files_count": files_count
            }
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            raise Exception(f"Backup failed: {e}")

    def list_backups(self) -> List[Dict]:
        """
        List all available backups.
        """
        backups = []
        for file in self.backup_dir.glob("*.zip"):
            stats = file.stat()
            backups.append({
                "filename": file.name,
                "timestamp": datetime.fromtimestamp(stats.st_mtime).isoformat(),
                "size_bytes": stats.st_size
            })
            
        # Sort by timestamp descending
        backups.sort(key=lambda x: x["timestamp"], reverse=True)
        return backups

    def delete_backup(self, filename: str) -> bool:
        """
        Delete a specific backup file.
        """
        file_path = self.backup_dir / filename
        if file_path.exists():
            os.remove(file_path)
            logger.info(f"Deleted backup: {filename}")
            return True
        return False
