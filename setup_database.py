#!/usr/bin/env python3
"""
Setup script for the Nutrition Database
This script will:
1. Create the database with proper schema
2. Import your existing CSV data
3. Show basic statistics
"""

import sys
from pathlib import Path
import logging

from database import NutritionDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Main setup function."""
    print("🍽️  Setting up Nutrition Database...")
    
    # Initialize database
    db_path = "nutrition_data.db"
    db = NutritionDatabase(db_path)
    print(f"✅ Database initialized at {db_path}")
    
    # Find existing CSV files
    csv_files = list(Path('.').glob('duke_nutrition_data_*.csv'))
    
    if csv_files:
        # Import from the most recent CSV
        latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)
        print(f"📊 Found CSV file: {latest_csv}")
        print("📥 Importing data...")
        
        try:
            items_added, items_updated = db.import_from_csv(str(latest_csv))
            print(f"✅ Import completed!")
            print(f"   - Items added: {items_added}")
            print(f"   - Items updated: {items_updated}")
        except Exception as e:
            print(f"❌ Import failed: {e}")
            return 1
    else:
        print("⚠️  No existing CSV files found")
        print("   Run your scraper first to generate initial data")
    
    # Show database statistics
    print("\n📈 Database Statistics:")
    stats = db.get_stats()
    print(f"   - Total items: {stats['total_items']}")
    print(f"   - Total units/restaurants: {stats['total_units']}")
    print(f"   - Total categories: {stats['total_categories']}")
    print(f"   - Last updated: {stats['last_updated']}")
    
    # Show available units
    print("\n🏪 Available Units/Restaurants:")
    units = db.get_units()
    for unit in units:
        print(f"   - {unit['unit_name']} (ID: {unit['unit_id']}) - {unit['item_count']} items")
    
    # Show sample categories
    print("\n🍕 Sample Categories:")
    categories = db.get_categories()
    for cat in categories[:10]:  # Show first 10
        print(f"   - {cat}")
    if len(categories) > 10:
        print(f"   ... and {len(categories) - 10} more")
    
    print("\n🎉 Setup completed successfully!")
    print("\nNext steps:")
    print("1. Test the scheduler:")
    print("   python scheduler.py --run-once")
    print("2. Set up daily scraping:")
    print("   python scheduler.py --schedule daily --time 06:00")
    print("3. Explore your data:")
    print("   python -c \"from database import NutritionDatabase; db = NutritionDatabase(); print(db.search_items('chicken'))\"")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 