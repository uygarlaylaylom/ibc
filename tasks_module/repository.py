from supabase import Client
from typing import List, Dict, Any, Optional
from .models import TaskCreate, Task

def insert_task(supabase: Client, task: TaskCreate) -> Optional[Dict[str, Any]]:
    """Inserts a TaskCreate object into the Supabase tasks table."""
    try:
        # Pydantic models to dict, ensuring datetime is ISO matched
        data = task.dict()
        if data['due_date']:
            data['due_date'] = data['due_date'].isoformat()

        # No longer used since we use add_note, but kept for signature
        response = supabase.table("activities").insert(data).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error inserting task: {e}")
        return None

def get_all_tasks(supabase: Client) -> List[Dict[str, Any]]:
    """Fetches all tasks from Supabase."""
    try:
        response = supabase.table("activities").select("*, companies(company_name)").eq("type", "task").order("created_at", desc=True).execute()
        tasks = []
        if response.data:
            for item in response.data:
                task = item.copy()
                task['task_description'] = item['content']
                if item.get('companies'):
                    task['source_company'] = item['companies'].get('company_name', 'Unknown')
                else:
                    task['source_company'] = 'Unknown'
                tasks.append(task)
        return tasks
    except Exception as e:
        print(f"Error fetching tasks: {e}")
        return []

def update_task_status(supabase: Client, task_id: str, new_status: str) -> bool:
    """Updates the status of a task."""
    try:
        response = supabase.table("activities").update({"status": new_status}).eq("id", task_id).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error updating task status for {task_id}: {e}")
        return False

def update_task_priority(supabase: Client, task_id: str, new_priority: str) -> bool:
    """Updates the priority of a task."""
    try:
        response = supabase.table("activities").update({"priority": new_priority}).eq("id", task_id).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error updating task priority for {task_id}: {e}")
        return False
        
def bulk_update_tasks(supabase: Client, updates: List[Dict[str, Any]]) -> bool:
    """Updates multiple tasks (e.g. from data editor changes)."""
    success = True
    for update in updates:
        task_id = update.get("id")
        if not task_id:
            continue
            
        payload = {}
        if "status" in update: payload["status"] = update["status"]
        if "priority" in update: payload["priority"] = update["priority"]
        
        if not payload:
            continue
            
        try:
            supabase.table("activities").update(payload).eq("id", task_id).execute()
        except Exception as e:
            print(f"Error bulk updating task {task_id}: {e}")
            success = False
            
    return success
