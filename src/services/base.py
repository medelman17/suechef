"""Base service class for SueChef services."""

from abc import ABC
from typing import Dict, Any

from ..core.database.manager import DatabaseManager


class BaseService(ABC):
    """Base class for all SueChef services."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def _success_response(self, data: Any = None, message: str = "Operation successful") -> Dict[str, Any]:
        """Create a standard success response."""
        response = {
            "status": "success",
            "message": message
        }
        if data is not None:
            response["data"] = data
        return response
    
    def _error_response(self, message: str, error_type: str = "error") -> Dict[str, Any]:
        """Create a standard error response."""
        return {
            "status": "error",
            "message": message,
            "error_type": error_type
        }