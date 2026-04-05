import os
import json
import logging
from typing import Dict, Any, Optional, List
from .base import BaseTool

logger = logging.getLogger(__name__)


class BCRECTool(BaseTool):
    """
    Unified BCREC Tool for answering all college-related queries.
    Uses the combined_kb.json for fast, accurate answers.
    """

    name = "get_bcrec_info"
    description = "Get comprehensive information about Dr. B.C. Roy Engineering College (BCREC) including courses, fees, placements, admission, hostel, infrastructure, departments, and contact details."

    def __init__(self, data_path: str = None):
        if data_path is None:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            data_path = os.path.normpath(
                os.path.join(module_dir, "..", "..", "..", "data", "knowledge_base", "combined_kb.json")
            )
        self.data = self._load(data_path)
        self._build_indexes()

    def _load(self, path: str) -> Dict[str, Any]:
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"BCRECTool loaded from {path}")
                    return data
            else:
                logger.warning(f"Knowledge base not found at {path}")
                return {}
        except Exception as e:
            logger.error(f"Failed to load knowledge base: {e}")
            return {}

    def _build_indexes(self):
        self.courses_index = {}
        self.dept_index = {}

        if not self.data:
            return

        courses = self.data.get("courses", {})
        for course_type, course_data in courses.items():
            if isinstance(course_data, dict):
                for code, info in course_data.items():
                    if isinstance(info, dict):
                        info["course_type"] = course_type
                        self.courses_index[code] = info
                        self.courses_index[code.lower()] = info

        depts = self.data.get("departments", {})
        for dept_code, dept_info in depts.items():
            self.dept_index[dept_code] = dept_info
            self.dept_index[dept_code.lower()] = dept_info

    def _normalize_course_code(self, code: str) -> Optional[str]:
        if not code:
            return None
        code = code.upper().replace("-", "").replace(" ", "").replace(".", "")
        code_map = {
            "CSE": "CSE", "COMPUTER": "CSE", "COMPUTERSCIENCE": "CSE",
            "IT": "IT", "INFORMATIONTECHNOLOGY": "IT",
            "ECE": "ECE", "ELECTRONICS": "ECE", "ELECTRONICSANDCOMMUNICATION": "ECE",
            "EE": "EE", "ELECTRICAL": "EE", "ELECTRICALENGINEERING": "EE",
            "ME": "ME", "MECHANICAL": "ME", "MECHANICALENGINEERING": "ME",
            "CE": "CE", "CIVIL": "CE", "CIVILENGINEERING": "CE",
            "CSD": "CSD", "DESIGN": "CSD", "COMPUTERSCIENCEANDDESIGN": "CSD",
            "AIML": "AIML", "AIML": "AIML", "ARTIFICIALINTELLIGENCE": "AIML",
            "DS": "DS", "DATASCIENCE": "DS", "DATASCIENCE": "DS",
            "CY": "CY", "CYBERSECURITY": "CY", "CYBERSECURITY": "CY",
            "MBA": "MBA", "MASTEROFBUSINESSADMINISTRATION": "MBA",
            "MCA": "MCA", "MASTEROFCOMPUTERAPPLICATIONS": "MCA",
            "MTECH": "M.Tech", "ME": "ME",
            "Btech": "CSE", "BTECH": "CSE", "B": "CSE"
        }
        return code_map.get(code)

    def execute(self, query_type: str = None, course: str = None, department: str = None) -> Dict[str, Any]:
        """
        Execute BCREC information lookup.
        
        Args:
            query_type: Type of query - fee, course, placement, admission, hostel, 
                       department, hod, cutoff, contact, infrastructure, placement, all
            course: Course code (CSE, IT, ECE, etc.)
            department: Department name
        """
        try:
            if query_type == "fee" or query_type == "fees":
                return self._get_fee_info(course)
            elif query_type == "course" or query_type == "courses":
                return self._get_course_info(course)
            elif query_type == "placement" or query_type == "placements":
                return self._get_placement_info(course)
            elif query_type == "admission":
                return self._get_admission_info()
            elif query_type == "hostel":
                return self._get_hostel_info()
            elif query_type == "department" or query_type == "hod":
                return self._get_department_info(department)
            elif query_type == "cutoff":
                return self._get_cutoff_info(course)
            elif query_type == "contact":
                return self._get_contact_info()
            elif query_type == "infrastructure":
                return self._get_infrastructure_info()
            elif query_type == "scholarship":
                return self._get_scholarship_info()
            elif query_type == "college":
                return self._get_college_overview()
            else:
                return self._get_all_info()
        except Exception as e:
            logger.error(f"BCRECTool execution error: {e}")
            return {"success": False, "error": str(e)}

    def _get_fee_info(self, course: str = None) -> Dict[str, Any]:
        if not course:
            return {
                "success": True,
                "fees": self.data.get("fees_summary", {}),
                "message": "Use course parameter to get specific fee details"
            }

        code = self._normalize_course_code(course)
        if code and code in self.courses_index:
            course_data = self.courses_index[code]
            if "fees" in course_data:
                return {
                    "success": True,
                    "course": code,
                    "course_name": course_data.get("full_name", ""),
                    "total_fees": f"Rs. {course_data['fees']['total']:,}",
                    "admission_fee": f"Rs. {course_data['fees']['admission']:,}",
                    "duration": course_data.get("duration", ""),
                    "fees_breakdown": self.data.get("fees_summary", {})
                }

        return {"success": False, "error": f"Course '{course}' not found or has no fee data"}

    def _get_course_info(self, course: str = None) -> Dict[str, Any]:
        if not course:
            courses_list = []
            for course_type, courses in self.data.get("courses", {}).items():
                if isinstance(courses, dict):
                    for code, info in courses.items():
                        if isinstance(info, dict):
                            courses_list.append({
                                "code": code,
                                "name": info.get("full_name", ""),
                                "type": course_type,
                                "intake": info.get("intake", "N/A")
                            })
            return {"success": True, "courses": courses_list}

        code = self._normalize_course_code(course)
        if code and code in self.courses_index:
            info = self.courses_index[code]
            return {
                "success": True,
                "code": code,
                "full_name": info.get("full_name", ""),
                "type": info.get("course_type", ""),
                "intake": info.get("intake", "N/A"),
                "duration": info.get("duration", ""),
                "nba_accredited": info.get("nba", False),
                "fees": info.get("fees", {}),
                "placement": info.get("placement", {}),
                "cutoff": info.get("cutoff", {})
            }

        return {"success": False, "error": f"Course '{course}' not found"}

    def _get_placement_info(self, course: str = None) -> Dict[str, Any]:
        if course:
            code = self._normalize_course_code(course)
            if code and code in self.courses_index:
                info = self.courses_index[code]
                return {
                    "success": True,
                    "course": code,
                    "placement": info.get("placement", {}),
                    "message": f"{code} placement data"
                }

        return {
            "success": True,
            "overall_rate": self.data.get("placements", {}).get("overall_rate_2025", "N/A"),
            "highest_package": self.data.get("placements", {}).get("highest_package", {}),
            "top_companies": self.data.get("placements", {}).get("top_companies_2026", []),
            "internship": self.data.get("placements", {}).get("internship", {})
        }

    def _get_admission_info(self) -> Dict[str, Any]:
        return {
            "success": True,
            "admission": self.data.get("admission", {}),
            "courses": list(self.data.get("courses", {}).keys())
        }

    def _get_hostel_info(self) -> Dict[str, Any]:
        return {
            "success": True,
            "hostel": self.data.get("hostel", {})
        }

    def _get_department_info(self, department: str = None) -> Dict[str, Any]:
        if department:
            code = self._normalize_course_code(department)
            if code and code in self.dept_index:
                return {
                    "success": True,
                    "department": code,
                    "info": self.dept_index[code]
                }
            return {"success": False, "error": f"Department '{department}' not found"}

        return {
            "success": True,
            "departments": self.data.get("departments", {})
        }

    def _get_cutoff_info(self, course: str = None) -> Dict[str, Any]:
        if course:
            code = self._normalize_course_code(course)
            if code and code in self.courses_index:
                info = self.courses_index[code]
                return {
                    "success": True,
                    "course": code,
                    "cutoff": info.get("cutoff", {})
                }

        cutoffs = {}
        for code, info in self.courses_index.items():
            if info.get("cutoff"):
                cutoffs[code] = info.get("cutoff")
        return {"success": True, "cutoffs": cutoffs}

    def _get_contact_info(self) -> Dict[str, Any]:
        college = self.data.get("college", {})
        return {
            "success": True,
            "contact": {
                "phones": college.get("phones", []),
                "mobile": college.get("mobile", ""),
                "email": college.get("email", ""),
                "address": college.get("address", ""),
                "website": college.get("website", ""),
                "timings": college.get("timings", "")
            },
            "principal": self.data.get("principal", {}),
            "placements_contact": self.data.get("placements", {}).get("contacts", {}),
            "admission_contact": self.data.get("admission", {}).get("contacts", {})
        }

    def _get_infrastructure_info(self) -> Dict[str, Any]:
        return {
            "success": True,
            "infrastructure": self.data.get("infrastructure", {}),
            "student_life": self.data.get("student_life", {})
        }

    def _get_scholarship_info(self) -> Dict[str, Any]:
        return {
            "success": True,
            "scholarships": self.data.get("admission", {}).get("scholarships", {})
        }

    def _get_college_overview(self) -> Dict[str, Any]:
        return {
            "success": True,
            "college": self.data.get("college", {}),
            "principal": self.data.get("principal", {})
        }

    def _get_all_info(self) -> Dict[str, Any]:
        return {
            "success": True,
            "message": "Use query_type parameter for specific information",
            "query_types": ["fee", "course", "placement", "admission", "hostel", 
                          "department", "cutoff", "contact", "infrastructure", "scholarship", "college"]
        }

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "description": "Type of query: fee, course, placement, admission, hostel, department, hod, cutoff, contact, infrastructure, scholarship, college, all",
                        "enum": ["fee", "course", "placement", "admission", "hostel", 
                                "department", "hod", "cutoff", "contact", "infrastructure",
                                "scholarship", "college", "all"]
                    },
                    "course": {
                        "type": "string",
                        "description": "Course code (CSE, IT, ECE, EE, ME, CE, CSD, AIML, DS, CY, MBA, MCA, M.Tech)"
                    },
                    "department": {
                        "type": "string",
                        "description": "Department name (CSE, IT, ECE, etc.)"
                    }
                },
                "required": []
            }
        }


def get_bcrec_tool() -> BCRECTool:
    """Get BCREC tool instance"""
    return BCRECTool()
