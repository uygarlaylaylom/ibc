import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from .models import TaskCreate

def parse_and_create_task(source_company: str, raw_description: str) -> Optional[TaskCreate]:
    """
    Smart Parsing Logic:
    1. Extract hashtags using r"#(\w+)".
    2. Lowercase tags, remove duplicates.
    3. If no tags found, return None (do not create a task).
    4. Compute Priority: 
       - High: acil, urgent, bug, teklif
       - Low: low, düşük
       - Normal: otherwise
    5. Compute Due Date:
       - yarın, tomorrow -> datetime.now() + 1 day
       - haftaya, next_week -> datetime.now() + 7 days
    """
    
    # Extract tags
    tags = re.findall(r"#(\w+)", raw_description)
    
    # Extract mentions and brackets
    mentions_raw = re.findall(r"@(\w+)", raw_description)
    mentions = list(set(mentions_raw)) # unique mentions
    
    bracket_raw = re.findall(r"\[(.*?)\]", raw_description)
    bracket_category = bracket_raw[-1] if bracket_raw else None # Take the last found bracket as the category, or first
    
    # If no tags, mentions, or categories, ignore (or maybe just keep tags as primary condition)
    # The prompt actually implies creating tasks via a "New Note" input, so we might want to create a task 
    # even if there are no tags, but the original logic returns None if no tags. Let's keep the logic that if tags, mentions or category exists, it's valid. Or just return if no text. 
    # Prompt: "No Hashtags: If no tags found, return None (do not create a task)." So keep original constraint, or loosen it? Let's keep original:
    if not tags and not mentions and not bracket_category:
        return None
        
    # Lowercase and unique tags
    unique_tags = list(set(tag.lower() for tag in tags))
    
    # Clean description by removing the hashtags or keep them? 
    # Usually we can keep them in description or strip them. We'll strip them for a clean description.
    # Actually, instructions just say "extract", keeping the raw desc is fine.
    
    # Priority defaults
    priority = "Normal"
    high_priority_keywords = {'acil', 'urgent', 'bug', 'teklif'}
    low_priority_keywords = {'low', 'düşük'}
    
    if any(tag in high_priority_keywords for tag in unique_tags):
        priority = "High"
    elif any(tag in low_priority_keywords for tag in unique_tags):
        priority = "Low"
        
    # Date extraction
    due_date = None
    tomorrow_keywords = {'yarın', 'tomorrow'}
    next_week_keywords = {'haftaya', 'next_week'}
    
    if any(tag in tomorrow_keywords for tag in unique_tags):
        due_date = datetime.now() + timedelta(days=1)
    elif any(tag in next_week_keywords for tag in unique_tags):
        due_date = datetime.now() + timedelta(days=7)
        
    # Return a validated TaskCreate model
    return TaskCreate(
        source_company=source_company,
        task_description=raw_description, # keep hashtags in text so it looks natural
        tags=unique_tags,
        mentions=mentions,
        bracket_category=bracket_category,
        priority=priority,
        due_date=due_date
    )
