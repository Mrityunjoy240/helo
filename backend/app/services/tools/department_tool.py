import os
import json
import logging
from typing import Dict, Any
from .base import BaseTool

logger = logging.getLogger(__name__)


class DepartmentTool(BaseTool):
    """Tool for retrieving department information"""

    name = "get_department_info"
    description = "Get information about a specific department/branch at BCREC"

    def __init__(self, data_path: str = None):
        if data_path is None:
            data_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "data", "structured_data.json"
            )
        self._load_data(data_path)

    def _load_data(self, path: str):
        self.branches = {}
        self.btech = {}
        
        try:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            abs_path = os.path.normpath(os.path.join(module_dir, "..", "..", "..", "data", "structured_data.json"))
            
            if os.path.exists(abs_path):
                with open(abs_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.btech = data.get("courses", {}).get("btech", {})
                    self.branches = self.btech.get("branches", {})
                    logger.info(f"DepartmentTool loaded from {abs_path}")
            else:
                rel_path = os.path.join(os.getcwd(), "data", "structured_data.json")
                if os.path.exists(rel_path):
                    with open(rel_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.btech = data.get("courses", {}).get("btech", {})
                        self.branches = self.btech.get("branches", {})
                        logger.info(f"DepartmentTool loaded from {rel_path}")
                else:
                    logger.warning(f"DepartmentTool: data file not found")
        except Exception as e:
            logger.error(f"Failed to load department data: {e}")

    def execute(self, department: str = None) -> Dict[str, Any]:
        """Get department information"""
        if not department:
            return self._get_all_departments()
        
        dept = department.lower().replace("-", "").replace("_", "").replace(".", "")
        
        branch_map = {
            "cse": "cse",
            "computerscience": "cse",
            "aiml": "cse_aiml",
            "ai": "cse_aiml",
            "ml": "cse_aiml",
            "it": "it",
            "informationtechnology": "it",
            "ds": "ds",
            "datascience": "ds",
            "csd": "csd",
            "computersciencedesign": "csd",
            "ece": "ece",
            "electronics": "ece",
            "communication": "ece",
            "ee": "ee",
            "electrical": "ee",
            "me": "me",
            "mechanical": "me",
            "ce": "ce",
            "civil": "ce",
        }
        
        branch_key = branch_map.get(dept)
        if not branch_key:
            return {
                "success": False,
                "error": f"Unknown department: {department}",
                "available": list(self.branches.keys())
            }
        
        return self._get_department(branch_key)

    def _get_department(self, dept_key: str) -> Dict[str, Any]:
        dept = self.branches.get(dept_key, {})
        if not dept:
            return {"success": False, "error": f"No data for {dept_key}"}
        
        return {
            "success": True,
            "department": dept_key.upper(),
            "full_name": dept.get("full_name", dept_key.upper()),
            "seats": dept.get("seats", "Contact college"),
            "cutoff": dept.get("cutoff_general", "Varies by round"),
            "placement_rate": dept.get("placement_rate", "Contact college"),
            "avg_salary": dept.get("avg_salary", "Contact college"),
            "highest_salary": dept.get("highest_salary", "Contact college")
        }

    def _get_all_departments(self) -> Dict[str, Any]:
        depts = []
        for key, dept in self.branches.items():
            depts.append({
                "code": key.upper(),
                "name": dept.get("full_name", key.upper()),
                "seats": dept.get("seats"),
                "cutoff": dept.get("cutoff_general"),
                "placement": dept.get("placement_rate")
            })
        
        return {
            "success": True,
            "category": "All B.Tech Departments",
            "departments": depts,
            "total_intake": sum(d.get("seats", 0) for d in depts)
        }

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "department": {
                        "type": "string",
                        "description": "Department code or name: cse, aiml, it, ece, ee, me, ce",
                        "enum": ["cse", "aiml", "it", "ds", "csd", "ece", "ee", "me", "ce"]
                    }
                },
                "required": []
            }
        }
