import os
import json
import logging
from typing import Dict, Any
from .base import BaseTool

logger = logging.getLogger(__name__)


class AdmissionTool(BaseTool):
    """Tool for retrieving admission information"""

    name = "get_admission_info"
    description = "Get admission requirements, process, and eligibility criteria"

    def __init__(self, data_path: str = None):
        if data_path is None:
            data_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "data", "structured_data.json"
            )
        self._load_data(data_path)

    def _load_data(self, path: str):
        self.admission = {}
        self.courses = {}
        
        try:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            abs_path = os.path.normpath(os.path.join(module_dir, "..", "..", "..", "data", "structured_data.json"))
            
            if os.path.exists(abs_path):
                with open(abs_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.admission = data.get("admission", {})
                    self.courses = data.get("courses", {})
                    logger.info(f"AdmissionTool loaded from {abs_path}")
            else:
                rel_path = os.path.join(os.getcwd(), "data", "structured_data.json")
                if os.path.exists(rel_path):
                    with open(rel_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.admission = data.get("admission", {})
                        self.courses = data.get("courses", {})
                        logger.info(f"AdmissionTool loaded from {rel_path}")
        except Exception as e:
            logger.error(f"Failed to load admission data: {e}")

    def execute(self, info_type: str = "all") -> Dict[str, Any]:
        """Get admission information"""
        info_type = info_type.lower()
        
        if info_type in ["eligibility", "criteria"]:
            return self._get_eligibility()
        elif info_type in ["process", "steps", "how to apply"]:
            return self._get_process()
        elif info_type in ["documents", "required docs", "required documents"]:
            return self._get_documents()
        elif info_type in ["dates", "deadline", "schedule", "important dates"]:
            return self._get_dates()
        elif info_type in ["entrance", "exams"]:
            return self._get_entrance()
        else:
            return self._get_all_info()

    def _get_eligibility(self) -> Dict[str, Any]:
        elig = self.admission.get("eligibility", {})
        return {
            "success": True,
            "category": "Eligibility Criteria",
            "btech": {
                "requirement": elig.get("btech", "10+2 with PCM, minimum 50% marks"),
                "entrance": "WBJEE or JEE Main"
            },
            "mba": {
                "requirement": elig.get("mba", "Bachelor's degree with 50% marks"),
                "entrance": "MAT, CMAT, CAT, or JEMAT"
            },
            "mca": {
                "requirement": elig.get("mca", "Bachelor's degree with Mathematics at 10+2"),
                "entrance": "WB-JECA"
            }
        }

    def _get_process(self) -> Dict[str, Any]:
        steps = self.admission.get("process", [])
        seat_dist = self.admission.get("seat_distribution", {})
        
        return {
            "success": True,
            "category": "Admission Process",
            "steps": [
                f"{i+1}. {step}" for i, step in enumerate(steps)
            ] if steps else [
                "1. Register and appear for WBJEE/JEE Main",
                "2. Participate in WBJEEB counseling",
                "3. Fill BCREC as preference",
                "4. Seat allotment based on rank",
                "5. Report to college with documents",
                "6. Pay fees and complete admission"
            ],
            "seat_distribution": seat_dist,
            "counseling_website": "wbjeeb.nic.in"
        }

    def _get_documents(self) -> Dict[str, Any]:
        docs = self.admission.get("documents_required", [])
        return {
            "success": True,
            "category": "Required Documents",
            "documents": docs if docs else [
                "10th and 12th Mark Sheets",
                "WBJEE/JEE Main Score Card",
                "Transfer Certificate",
                "Migration Certificate",
                "Caste Certificate (if applicable)",
                "Domicile Certificate",
                "6 passport size photographs",
                "Aadhar Card",
                "Income Certificate (for scholarships)"
            ]
        }

    def _get_dates(self) -> Dict[str, Any]:
        dates = self.admission.get("important_dates", {})
        return {
            "success": True,
            "category": "Important Dates",
            "wbjee_2026": {
                "registration": dates.get("wbjee_2026_registration", "Mar 10 - Apr 05, 2026"),
                "exam": dates.get("wbjee_2026_exam", "May 24, 2026")
            },
            "jee_main_2026_session2": dates.get("jee_main_2026_session2", "Apr 02 - Apr 08, 2026"),
            "note": "Dates are tentative. Check official websites for updates."
        }

    def _get_entrance(self) -> Dict[str, Any]:
        exams = self.admission.get("entrance_exams", {})
        return {
            "success": True,
            "category": "Entrance Exams",
            "btech": exams.get("btech", ["WBJEE", "JEE Main"]),
            "mba": exams.get("mba", ["JEMAT", "MAT", "CMAT", "CAT"]),
            "mca": exams.get("mca", ["WB-JECA"]),
            "mtech": exams.get("mtech", ["GATE", "MAKAUT-PGCET"])
        }

    def _get_all_info(self) -> Dict[str, Any]:
        return {
            "success": True,
            "category": "Admission Information",
            "eligibility": self._get_eligibility(),
            "process": self._get_process(),
            "documents": self._get_documents(),
            "dates": self._get_dates(),
            "entrance": self._get_entrance()
        }

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "description": "Type of info: eligibility, process, documents, dates, entrance, or all",
                        "enum": ["eligibility", "process", "documents", "dates", "entrance", "all"]
                    }
                },
                "required": []
            }
        }
