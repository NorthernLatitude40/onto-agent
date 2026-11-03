#!/usr/bin/env python3
"""
Migration script for updating scraper configurations from legacy format to new step-level format.

This script:
1. Reads existing scraper configs from the database
2. Converts legacy format (target_url, step2_url, etc.) to new steps array format
3. Updates the database with the new structure
4. Preserves backward compatibility by keeping old fields populated
"""

import json
from typing import List, Dict, Any
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from src.model.scraper_config_model import ScraperConfigModel
from src.common.database import Base


def migrate_legacy_to_steps():
    """
    Migrate legacy scraper configurations to new step-level format.
    
    Legacy format fields:
    - target_url: First step URL
    - step2_url: Second step URL
    - step3_url: Third step URL
    - calctotal_url: Fourth step URL
    - mode: Global mode (applied to all steps)
    
    New format:
    - steps: Array of step objects with individual modes
    """
    print("Starting scraper configuration migration...")
    
    # Database connection setup
    engine = create_engine("sqlite:///./scraper_configs.db", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get all scraper configurations
        configs = session.query(ScraperConfigModel).all()
        print(f"Found {len(configs)} scraper configurations to migrate")
        
        migrated_count = 0
        skipped_count = 0
        
        for config in configs:
            # Check if already migrated (steps field exists and is not empty)
            if config.steps and len(json.loads(config.steps)) > 0:
                print(f"✓ Config {config.id} ({config.name}) already migrated, skipping")
                skipped_count += 1
                continue
            
            # Build new steps array from legacy fields
            steps = []
            step_num = 1
            
            # Step 1: target_url
            if config.target_url:
                steps.append({
                    "id": f"step{step_num}",
                    "name": "初始请求",
                    "mode": config.mode or "api",
                    "url": config.target_url,
                    "method": "GET",
                    "params_json": "{}",
                    "headers_json": "{}",
                    "parsing_rules": [],
                })
                step_num += 1
            
            # Step 2: step2_url
            if config.step2_url:
                steps.append({
                    "id": f"step{step_num}",
                    "name": "步骤 2",
                    "mode": config.mode or "api",
                    "url": config.step2_url,
                    "method": "GET",
                    "params_json": "{}",
                    "headers_json": "{}",
                    "parsing_rules": [],
                })
                step_num += 1
            
            # Step 3: step3_url
            if config.step3_url:
                steps.append({
                    "id": f"step{step_num}",
                    "name": "步骤 3",
                    "mode": config.mode or "api",
                    "url": config.step3_url,
                    "method": "GET",
                    "params_json": "{}",
                    "headers_json": "{}",
                    "parsing_rules": [],
                })
                step_num += 1
            
            # Step 4: calctotal_url
            if config.calctotal_url:
                steps.append({
                    "id": f"step{step_num}",
                    "name": "步骤 4",
                    "mode": config.mode or "api",
                    "url": config.calctotal_url,
                    "method": "GET",
                    "params_json": "{}",
                    "headers_json": "{}",
                    "parsing_rules": [],
                })
            
            # Only update if we have steps to migrate
            if len(steps) > 0:
                config.steps = json.dumps(steps, ensure_ascii=False)
                session.add(config)
                migrated_count += 1
                print(f"✓ Migrated config {config.id} ({config.name}): {len(steps)} steps")
            else:
                skipped_count += 1
                print(f"⊘ Config {config.id} ({config.name}) has no steps, skipping")
        
        # Commit all changes
        session.commit()
        
        print("\n" + "="*60)
        print("Migration Summary:")
        print(f"  Total configurations: {len(configs)}")
        print(f"  Successfully migrated: {migrated_count}")
        print(f"  Already migrated: {skipped_count}")
        print(f"  No steps to migrate: {skipped_count}")
        print("="*60)
        
        if migrated_count > 0:
            print("\n✓ Migration completed successfully!")
        else:
            print("\nℹ No configurations needed migration.")
    
    except Exception as e:
        session.rollback()
        print(f"\n✗ Migration failed with error: {e}")
        raise
    
    finally:
        session.close()
        engine.dispose()


def validate_migration():
    """
    Validate that migration worked correctly by checking a sample of configs.
    """
    print("\nValidating migration...")
    
    engine = create_engine("sqlite:///./scraper_configs.db", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get a few configs to validate
        configs = session.query(ScraperConfigModel).limit(5).all()
        
        for config in configs:
            if config.steps:
                steps = json.loads(config.steps)
                print(f"\nConfig {config.id} ({config.name}):")
                print(f"  Steps count: {len(steps)}")
                for step in steps:
                    print(f"    - {step['name']}: {step['mode']} mode, URL: {step['url'][:50]}...")
            else:
                print(f"\nConfig {config.id} ({config.name}): No steps (legacy format)")
        
        print("\n✓ Validation completed")
    
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    print("Scraper Configuration Migration Tool")
    print("="*60)
    
    # Run migration
    migrate_legacy_to_steps()
    
    # Validate results
    validate_migration()
    
    print("\nMigration script completed.")
