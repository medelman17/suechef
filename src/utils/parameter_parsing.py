"""Parameter parsing utilities for handling MCP client variations."""

import json
from typing import List, Optional, Union, Any


def parse_string_list(value: Union[str, List[str], None]) -> Optional[List[str]]:
    """
    Parse a list parameter that might come as a string or native list.
    
    MCP clients sometimes send arrays as JSON strings instead of native arrays.
    This function handles both cases gracefully.
    
    Args:
        value: The parameter value (could be string, list, or None)
        
    Returns:
        List of strings or None
        
    Examples:
        parse_string_list('["item1", "item2"]') -> ["item1", "item2"]
        parse_string_list(["item1", "item2"]) -> ["item1", "item2"]
        parse_string_list(None) -> None
        parse_string_list("") -> None
    """
    if value is None:
        return None
    
    # If it's already a list, return it
    if isinstance(value, list):
        # Ensure all items are strings
        return [str(item) for item in value]
    
    # If it's a string, try to parse as JSON
    if isinstance(value, str):
        value = value.strip()
        
        # Handle empty string
        if not value:
            return None
        
        # If it looks like JSON, try to parse it
        if value.startswith('[') and value.endswith(']'):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except (json.JSONDecodeError, ValueError):
                pass
        
        # If it's a comma-separated string, split it
        if ',' in value:
            return [item.strip() for item in value.split(',') if item.strip()]
        
        # Single item string
        return [value]
    
    # For any other type, try to convert to string list
    try:
        if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
            return [str(item) for item in value]
        else:
            return [str(value)]
    except Exception:
        return None


def normalize_event_parameters(
    date: str,
    description: str,
    parties: Union[str, List[str], None] = None,
    document_source: Optional[str] = None,
    excerpts: Optional[str] = None,
    tags: Union[str, List[str], None] = None,
    significance: Optional[str] = None,
    group_id: str = "default"
) -> dict:
    """
    Normalize all event parameters to handle MCP client variations.
    
    Returns a dictionary with properly parsed parameters.
    """
    return {
        "date": date,
        "description": description,
        "parties": parse_string_list(parties),
        "document_source": document_source,
        "excerpts": excerpts,
        "tags": parse_string_list(tags),
        "significance": significance,
        "group_id": group_id
    }


def normalize_snippet_parameters(
    citation: str,
    key_language: str,
    tags: Union[str, List[str], None] = None,
    context: Optional[str] = None,
    case_type: Optional[str] = None,
    group_id: str = "default"
) -> dict:
    """
    Normalize snippet parameters to handle MCP client variations.
    """
    return {
        "citation": citation,
        "key_language": key_language,
        "tags": parse_string_list(tags),
        "context": context,
        "case_type": case_type,
        "group_id": group_id
    }