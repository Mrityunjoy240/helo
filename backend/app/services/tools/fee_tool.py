import os
import json
import logging
from typing import Dict, Any, Optional
from .base import BaseTool

logger = logging.getLogger(__name__)


class FeeTool(BaseTool):
    """Tool for retrieving fee information"""

    name = "get_course_fees"
    description = "Get fee structure for a specific course at BCREC"

    def __init__(self, data_path: str = None):
        if data_path is None:
            data_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "data", "structured_data.json"
            )
        self._load_data(data_path)

    def _load_data(self, path: str):
        """Load structured data"""
        self.fees = {}
        self.courses = {}
        
        try:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            abs_path = os.path.normpath(os.path.join(module_dir, "..", "..", "..", "data", "structured_data.json"))
            
            if os.path.exists(abs_path):
                with open(abs_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.fees = data.get("fees", {})
                    self.courses = data.get("courses", {})
                    logger.info(f"FeeTool loaded from {abs_path}")
            else:
                rel_path = os.path.join(os.getcwd(), "data", "structured_data.json")
                if os.path.exists(rel_path):
                    with open(rel_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.fees = data.get("fees", {})
                        self.courses = data.get("courses", {})
                        logger.info(f"FeeTool loaded from {rel_path}")
        except Exception as e:
            logger.error(f"Failed to load fee data: {e}")

    def execute(self, course: str = "btech") -> Dict[str, Any]:
        """Get fee information for a course"""
        course = course.lower()
        
        if course in ["btech", "bt ech", "b. tech", "btech"]:
            return self._get_btech_fees()
        elif course in ["mba", "mba"]:
            return self._get_mba_fees()
        elif course in ["mca", "mca"]:
            return self._get_mca_fees()
        elif course in ["mtech", "m. tech", "mt ech"]:
            return self._get_mtech_fees()
        elif course in ["hostel", "hostel fee", "hostel fees"]:
            return self._get_hostel_fees()
        else:
            return {
                "success": False,
                "error": f"Unknown course: {course}",
                "available_courses": ["btech", "mba", "mca", "mtech", "hostel"]
            }

    def _get_btech_fees(self) -> Dict[str, Any]:
        btech = self.fees.get("btech", {})
        return {
            "success": True,
            "course": "B.Tech",
            "duration": "4 years (8 semesters)",
            "total_fees": btech.get("total", "₹4.49 Lakhs - ₹6.1 Lakhs"),
            "per_year": btech.get("per_year", "₹1.09 Lakhs - ₹1.69 Lakhs"),
            "per_semester": btech.get("per_semester", "₹63,250"),
            "breakdown": {
                "tuition_per_sem": "₹45,000",
                "development_per_sem": "₹5,000",
                "library_per_sem": "₹1,000",
                "admission_fee": "₹10,000"
            }
        }

    def _get_mba_fees(self) -> Dict[str, Any]:
        mba = self.fees.get("mba", {})
        return {
            "success": True,
            "course": "MBA",
            "duration": "2 years (4 semesters)",
            "total_fees": mba.get("total", "₹4.29 Lakhs"),
            "per_semester": mba.get("per_semester", "₹55,000"),
            "first_year": "₹2.25 Lakhs"
        }

    def _get_mca_fees(self) -> Dict[str, Any]:
        mca = self.courses.get("mca", {})
        return {
            "success": True,
            "course": "MCA",
            "duration": "3 years (6 semesters)",
            "total_fees": mca.get("total_fees", "₹2.17 Lakhs"),
            "entrance": "WB-JECA"
        }

    def _get_mtech_fees(self) -> Dict[str, Any]:
        mtech = self.fees.get("mtech", {})
        return {
            "success": True,
            "course": "M.Tech",
            "duration": "2 years (4 semesters)",
            "total_fees": mtech.get("total", "₹1.26 Lakhs - ₹2.27 Lakhs"),
            "first_year": mtech.get("first_year", "₹69,000 - ₹1.19 Lakhs"),
            "entrance": "GATE or MAKAUT-PGCET"
        }

    def _get_hostel_fees(self) -> Dict[str, Any]:
        hostel = self.fees.get("hostel", {})
        return {
            "success": True,
            "category": "Hostel Fees",
            "boarding_per_semester": hostel.get("boarding_per_sem", "₹35,000"),
            "mess_per_month": hostel.get("mess_per_month", "₹4,000"),
            "security_deposit": hostel.get("security_deposit", "₹10,000"),
            "note": "Separate hostels for boys and girls"
        }

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "course": {
                        "type": "string",
                        "description": "Course name: btech, mba, mca, mtech, hostel",
                        "enum": ["btech", "mba", "mca", "mtech", "hostel"]
                    }
                },
                "required": []
            }
        }
