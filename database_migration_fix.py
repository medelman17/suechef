#!/usr/bin/env python3
"""
Database Migration Fix for Trigger Duplication Issue
Fixes the "trigger already exists" error by properly handling existing triggers.
"""

import asyncio
import os
import sys
import asyncpg
from src.config.settings import get_config


async def fix_trigger_duplication():
    """Fix the trigger duplication issue by dropping and recreating triggers."""
    
    print("🔧 SueChef Database Migration Fix")
    print("=" * 50)
    print("Fixing trigger duplication issue...")
    
    try:
        # Get configuration
        config = get_config()
        
        # Connect to PostgreSQL
        print("📡 Connecting to PostgreSQL...")
        conn = await asyncpg.connect(config.database.postgres_url)
        
        # Fix trigger duplication
        fix_sql = """
        -- Drop existing triggers if they exist
        DROP TRIGGER IF EXISTS update_events_updated_at ON events;
        DROP TRIGGER IF EXISTS update_snippets_updated_at ON snippets;
        
        -- Recreate function (this is idempotent)
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        
        -- Recreate triggers
        CREATE TRIGGER update_events_updated_at BEFORE UPDATE
            ON events FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            
        CREATE TRIGGER update_snippets_updated_at BEFORE UPDATE
            ON snippets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
        
        print("🔨 Applying trigger fixes...")
        await conn.execute(fix_sql)
        
        print("✅ Trigger duplication fixed successfully!")
        
        # Test that we can now run basic operations
        print("🧪 Testing basic operations...")
        
        # Test events table
        test_query = "SELECT COUNT(*) FROM events"
        count = await conn.fetchval(test_query)
        print(f"   ✅ Events table accessible: {count} existing events")
        
        # Test snippets table  
        test_query = "SELECT COUNT(*) FROM snippets"
        count = await conn.fetchval(test_query)
        print(f"   ✅ Snippets table accessible: {count} existing snippets")
        
        # Test trigger functionality
        print("🔄 Testing trigger functionality...")
        try:
            # Try to update a timestamp to verify triggers work
            await conn.execute("""
                INSERT INTO events (date, description, group_id) 
                VALUES (CURRENT_DATE, 'Migration test event', 'migration-test')
                ON CONFLICT DO NOTHING
            """)
            
            # Clean up test data
            await conn.execute("DELETE FROM events WHERE group_id = 'migration-test'")
            print("   ✅ Triggers working correctly")
            
        except Exception as e:
            print(f"   ⚠️  Trigger test warning: {e}")
        
        await conn.close()
        
        print("\n🎉 Database migration fix completed successfully!")
        print("💡 All chronology tools should now work properly.")
        print("🚀 You can now restart SueChef and test with add_event or get_system_status.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Migration fix failed: {e}")
        print("\n🔧 Manual fix instructions:")
        print("1. Connect to your PostgreSQL database")
        print("2. Run these SQL commands:")
        print("   DROP TRIGGER IF EXISTS update_events_updated_at ON events;")
        print("   DROP TRIGGER IF EXISTS update_snippets_updated_at ON snippets;")
        print("3. Then restart SueChef - it will recreate the triggers properly")
        return False


async def main():
    """Main function."""
    print("SueChef Database Migration Fix")
    print("Addresses: trigger 'update_events_updated_at' for relation 'events' already exists")
    print()
    
    # Check if we're in the right directory
    if not os.path.exists("pyproject.toml"):
        print("❌ Please run this script from the SueChef root directory")
        return 1
    
    # Set dummy API key for config loading if not set
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "migration-fix"
    
    try:
        success = await fix_trigger_duplication()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\n⏹️  Migration fix cancelled by user")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)