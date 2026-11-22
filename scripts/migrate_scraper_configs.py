"""
Migration script for scraper configurations.

This script handles:
1. Adding missing top-level fields (cron_schedule, concurrency, proxy, group_id)
2. Converting old step format to new unified format with action_config
3. Ensuring parsing_rules are stored as lists
4. Backfilling default values for missing fields
"""
import json
from typing import Dict, Any, List
from datetime import datetime

# Import database models
try:
    from src.model.scraper_config_model import ScraperConfigModel
    from src.model.scraper_schema import ScraperStep, ScraperStepWrapper
    from src.database.session import SessionLocal
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the project root with proper environment setup")
    exit(1)


def migrate_config(config_id: int) -> Dict[str, Any]:
    """
    Migrate a single scraper configuration to include all new fields.
    
    Args:
        config_id: ID of the configuration to migrate
        
    Returns:
        Dictionary with migration results and any warnings/errors
    """
    db = SessionLocal()
    try:
        # Get the existing configuration
        config = db.query(ScraperConfigModel).filter(ScraperConfigModel.id == config_id).first()
        
        if not config:
            return {
                "config_id": config_id,
                "status": "not_found",
                "message": f"Configuration with ID {config_id} not found"
            }
        
        changes_made = []
        warnings = []
        
        # Check and add missing top-level fields
        if config.cron_schedule is None:
            config.cron_schedule = ""  # Empty string for no schedule
            changes_made.append("cron_schedule (set to empty)")
        
        if config.concurrency is None:
            config.concurrency = 1  # Default concurrency
            changes_made.append("concurrency (set to default: 1)")
        
        if config.proxy is None:
            config.proxy = {}  # Empty dict for no proxy
            changes_made.append("proxy (set to empty)")
        
        if config.group_id is None:
            warnings.append("group_id is NULL - this should reference a project/group")
        
        # Migrate steps from old format to new unified format
        if config.steps and len(config.steps) > 0:
            migrated_steps = []
            
            for step_idx, step_data in enumerate(config.steps):
                try:
                    # Try to load as dict first
                    if isinstance(step_data, str):
                        step_dict = json.loads(step_data)
                    else:
                        step_dict = step_data
                    
                    # Check if this is old format (has mode and target_url at top level)
                    has_old_format = (
                        isinstance(step_dict, dict) and 
                        'mode' in step_dict and 
                        'target_url' in step_dict
                    )
                    
                    if has_old_format:
                        # Convert from old format to new unified format
                        wrapper = ScraperStepWrapper(**step_dict)
                        unified_step = wrapper.to_unified_format()
                        migrated_steps.append(unified_step.dict())
                        changes_made.append(f"step[{step_idx}] (converted from old format)")
                    else:
                        # Already in new format or needs validation
                        step_obj = ScraperStep(**step_dict)
                        unified_step = step_obj.to_unified_format()
                        migrated_steps.append(unified_step.dict())
                
                except Exception as e:
                    warnings.append(f"Error migrating step[{step_idx}]: {str(e)}")
                    # Keep original step data to avoid data loss
                    migrated_steps.append(step_data if isinstance(step_data, dict) else json.loads(step_data))
            
            config.steps = migrated_steps
        
        # Save the migrated configuration
        db.commit()
        
        return {
            "config_id": config.id,
            "name": config.name,
            "status": "migrated",
            "changes_made": changes_made if changes_made else ["no_changes_needed"],
            "warnings": warnings,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
