"""Author string parsing utilities."""

import re
from typing import Dict, List, Optional, Union


def parse_author_string(author: Union[str, Dict]) -> Optional[Dict[str, str]]:
    """Parse author string into structured format.
    
    Handles various formats:
    - "Name <email@example.com>"
    - "Name (email@example.com)"
    - "Name"
    - {"name": "Name", "email": "email@example.com"}
    
    Args:
        author: Author string or dict
        
    Returns:
        Dictionary with 'name' and optionally 'email' keys, or None if invalid
    """
    if not author:
        return None
    
    # If already a dict, validate and return
    if isinstance(author, dict):
        result = {}
        if 'name' in author:
            result['name'] = str(author['name']).strip()
        if 'email' in author:
            result['email'] = str(author['email']).strip()
        return result if result else None
    
    # Convert to string
    author_str = str(author).strip()
    if not author_str:
        return None
    
    author_dict = {}
    
    # Try to parse "Name <email>" format
    email_match = re.search(r'<([^>]+@[^>]+)>', author_str)
    if email_match:
        email = email_match.group(1).strip()
        name = author_str[:author_str.index('<')].strip()
        
        if name:
            author_dict['name'] = name
        if email:
            author_dict['email'] = email
    
    # Try to parse "Name (email)" format
    elif '(' in author_str and ')' in author_str:
        email_match = re.search(r'\(([^)]+@[^)]+)\)', author_str)
        if email_match:
            email = email_match.group(1).strip()
            name = author_str[:author_str.index('(')].strip()
            
            if name:
                author_dict['name'] = name
            if email:
                author_dict['email'] = email
        else:
            # Just parentheses without email
            author_dict['name'] = author_str.replace('(', '').replace(')', '').strip()
    
    # Just a name (no email)
    else:
        author_dict['name'] = author_str
    
    return author_dict if author_dict else None


def parse_author_list(authors: Union[str, List, Dict]) -> List[Dict[str, str]]:
    """Parse a list or string of authors.
    
    Args:
        authors: Can be:
            - Single author string
            - List of author strings/dicts
            - Dict with 'name' key
            - Comma-separated string of authors
            
    Returns:
        List of author dictionaries
    """
    result = []
    
    if not authors:
        return result
    
    # Handle single string with potential comma separation
    if isinstance(authors, str):
        # Check for comma-separated authors
        if ',' in authors and '<' not in authors and '(' not in authors:
            # Simple comma-separated names
            authors = [a.strip() for a in authors.split(',')]
        else:
            authors = [authors]
    
    # Handle dict with 'name' key
    elif isinstance(authors, dict):
        authors = [authors]
    
    # Process list of authors
    if isinstance(authors, list):
        for author in authors:
            parsed = parse_author_string(author)
            if parsed:
                result.append(parsed)
    
    return result


def format_author(author_dict: Dict[str, str]) -> str:
    """Format author dict back to string.
    
    Args:
        author_dict: Dictionary with 'name' and optionally 'email'
        
    Returns:
        Formatted author string
    """
    if not author_dict:
        return ""
    
    name = author_dict.get('name', '')
    email = author_dict.get('email', '')
    
    if name and email:
        return f"{name} <{email}>"
    return name or email or ""