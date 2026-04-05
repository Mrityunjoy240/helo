import os
import json
import logging
from typing import Dict, Any
from .base import BaseTool

logger = logging.getLogger(__name__)


class ContactTool(BaseTool):
    """Tool for retrieving contact information"""

    name = "get_contact_details"
    description = "Get contact information for BCREC offices and departments"

    def __init__(self, data_path: str = None):
        if data_path is None:
            data_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "data", "structured_data.json"
            )
        self._load_data(data_path)

    def _load_data(self, path: str):
        self.contacts = {}
        self.college = {}
        
        try:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            abs_path = os.path.normpath(os.path.join(module_dir, "..", "..", "..", "data", "structured_data.json"))
            
            if os.path.exists(abs_path):
                with open(abs_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.contacts = data.get("contacts", {})
                    self.college = data.get("college", {})
                    logger.info(f"ContactTool loaded from {abs_path}")
            else:
                rel_path = os.path.join(os.getcwd(), "data", "structured_data.json")
                if os.path.exists(rel_path):
                    with open(rel_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.contacts = data.get("contacts", {})
                        self.college = data.get("college", {})
                        logger.info(f"ContactTool loaded from {rel_path}")
        except Exception as e:
            logger.error(f"Failed to load contact data: {e}")

    def execute(self, contact_type: str = "all") -> Dict[str, Any]:
        """Get contact information"""
        contact_type = contact_type.lower().replace(" ", "_")
        
        if "admission" in contact_type:
            return self._get_admission_contact()
        elif "placement" in contact_type or "tpo" in contact_type:
            return self._get_placement_contact()
        elif "main" in contact_type or "office" in contact_type:
            return self._get_main_office()
        elif "principal" in contact_type:
            return self._get_principal()
        elif "cse" in contact_type or "hod" in contact_type:
            return self._get_cse_hod()
        elif "accounts" in contact_type:
            return self._get_accounts()
        elif "hostel" in contact_type:
            return self._get_hostel_contact()
        else:
            return self._get_all_contacts()

    def _get_admission_contact(self) -> Dict[str, Any]:
        admission = self.contacts.get("admissions", {})
        return {
            "success": True,
            "category": "Admissions Office",
            "phones": admission.get("phone", ["9333928874", "9832131164", "9932245570"]),
            "email": admission.get("email", "admissions@bcrec.ac.in"),
            "timing": "Mon-Fri: 10:00 AM - 5:30 PM"
        }

    def _get_placement_contact(self) -> Dict[str, Any]:
        placement = self.contacts.get("placement", {})
        return {
            "success": True,
            "category": "Training & Placement Office",
            "email": placement.get("email", "tpo.kol@bcrec.ac.in"),
            "alternate_email": placement.get("alternate_email", "bcrec_kol@yahoo.co.in"),
            "phone": placement.get("phone", "033-2355 4412")
        }

    def _get_main_office(self) -> Dict[str, Any]:
        main = self.contacts.get("main_office", {})
        return {
            "success": True,
            "category": "Main Office",
            "phones": main.get("phone", ["0343-2501353"]),
            "mobile": main.get("mobile", "+91-6297128554"),
            "email": main.get("email", "info@bcrec.ac.in"),
            "website": main.get("website", "www.bcrec.ac.in"),
            "address": self.college.get("address", "Jemua Road, Fuljhore, Durgapur - 713206"),
            "hours": main.get("hours", "Mon-Fri: 10:00 AM - 5:30 PM")
        }

    def _get_principal(self) -> Dict[str, Any]:
        principal = self.contacts.get("principal", {})
        return {
            "success": True,
            "category": "Principal",
            "email": principal.get("email", "principal@bcrec.ac.in"),
            "phone": principal.get("phone", "0343-2501353")
        }

    def _get_cse_hod(self) -> Dict[str, Any]:
        cse = self.contacts.get("departments", {}).get("cse", {})
        return {
            "success": True,
            "category": "CSE Department (HOD)",
            "name": cse.get("name", "Dr. Bappaditya Das"),
            "email": cse.get("email", "bappaditya.das@bcrec.ac.in"),
            "phone": cse.get("phone", "+91-9051218105")
        }

    def _get_accounts(self) -> Dict[str, Any]:
        accounts = self.contacts.get("accounts", {})
        return {
            "success": True,
            "category": "Accounts Department",
            "phone": accounts.get("phone", "0343-2501353 (Ext 278)"),
            "mobile": accounts.get("mobile", "7001380141"),
            "email": accounts.get("email", "accounts@bcrec.ac.in")
        }

    def _get_hostel_contact(self) -> Dict[str, Any]:
        return {
            "success": True,
            "category": "Hostel Office",
            "phone": "0343-2501353",
            "note": "Contact main office for hostel details",
            "fees": "₹35,000/sem boarding + ₹4,000/month mess"
        }

    def _get_all_contacts(self) -> Dict[str, Any]:
        return {
            "success": True,
            "category": "All Contact Information",
            "main_office": self._get_main_office(),
            "admissions": self._get_admission_contact(),
            "placement": self._get_placement_contact(),
            "principal": self._get_principal(),
            "accounts": self._get_accounts()
        }

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_type": {
                        "type": "string",
                        "description": "Type of contact: admission, placement, main, principal, cse, accounts, hostel",
                        "enum": ["admission", "placement", "main", "principal", "cse", "accounts", "hostel", "all"]
                    }
                },
                "required": []
            }
        }
