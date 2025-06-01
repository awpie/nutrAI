import sqlite3
import pandas as pd
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NutritionDatabase:
    def __init__(self, db_path: str = "nutrition_data.db"):
        """Initialize the nutrition database."""
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create food_items table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS food_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT UNIQUE NOT NULL,
                    item_name TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    unit_name TEXT NOT NULL,
                    category TEXT,
                    subcategory TEXT,
                    serving_size TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create nutrition_facts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS nutrition_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT NOT NULL,
                    calories INTEGER,
                    total_fat TEXT,
                    saturated_fat TEXT,
                    trans_fat TEXT,
                    cholesterol TEXT,
                    sodium TEXT,
                    total_carb TEXT,
                    dietary_fiber TEXT,
                    sugars TEXT,
                    protein TEXT,
                    scraped_at DATETIME NOT NULL,
                    FOREIGN KEY (item_id) REFERENCES food_items (item_id)
                )
            ''')
            
            # Create ingredients table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ingredients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT NOT NULL,
                    ingredients TEXT,
                    allergens TEXT,
                    scraped_at DATETIME NOT NULL,
                    FOREIGN KEY (item_id) REFERENCES food_items (item_id)
                )
            ''')
            
            # Create scraping_log table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scraping_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME,
                    items_found INTEGER,
                    items_added INTEGER,
                    items_updated INTEGER,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_food_items_item_id ON food_items (item_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_food_items_unit_id ON food_items (unit_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_food_items_category ON food_items (category)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_food_items_subcategory ON food_items (subcategory)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_nutrition_facts_item_id ON nutrition_facts (item_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_nutrition_facts_scraped_at ON nutrition_facts (scraped_at)')
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def clear_food_data(self):
        """Clear all food data (items, nutrition facts, ingredients) but keep scraping logs."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Clear data tables in order (respecting foreign keys)
            cursor.execute('DELETE FROM ingredients')
            cursor.execute('DELETE FROM nutrition_facts') 
            cursor.execute('DELETE FROM food_items')
            
            conn.commit()
            logger.info("All food data cleared from database")
    
    def insert_fresh_food_data(self, food_data: List[Dict]) -> int:
        """
        Insert fresh food data after clearing existing data.
        This is simpler than checking for existing items.
        Returns the number of items inserted.
        """
        scraped_at = datetime.now(timezone.utc).isoformat()
        items_inserted = 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for item in food_data:
                # Insert food item
                cursor.execute('''
                    INSERT INTO food_items (item_id, item_name, unit_id, unit_name, category, subcategory, serving_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item['item_id'], item['item_name'], item['unit_id'], 
                    item['unit_name'], item['category'], item.get('subcategory'), item['serving_size']
                ))
                
                # Insert nutrition facts
                cursor.execute('''
                    INSERT INTO nutrition_facts 
                    (item_id, calories, total_fat, saturated_fat, trans_fat, cholesterol, 
                     sodium, total_carb, dietary_fiber, sugars, protein, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item['item_id'], 
                    self._parse_calories(item.get('calories')),
                    item.get('total_fat'), item.get('saturated_fat'), item.get('trans_fat'),
                    item.get('cholesterol'), item.get('sodium'), item.get('total_carb'),
                    item.get('dietary_fiber'), item.get('sugars'), item.get('protein'),
                    item.get('scraped_at', scraped_at)
                ))
                
                # Insert ingredients
                cursor.execute('''
                    INSERT INTO ingredients (item_id, ingredients, allergens, scraped_at)
                    VALUES (?, ?, ?, ?)
                ''', (
                    item['item_id'], item.get('ingredients'), item.get('allergens'),
                    item.get('scraped_at', scraped_at)
                ))
                
                items_inserted += 1
            
            conn.commit()
        
        logger.info(f"Inserted {items_inserted} fresh food items")
        return items_inserted
    
    def refresh_all_data(self, food_data: List[Dict]) -> int:
        """
        Complete refresh: clear all data and insert fresh data.
        This is the main method for daily scraping.
        Returns the number of items inserted.
        """
        logger.info("Starting complete data refresh...")
        
        # Clear existing data
        self.clear_food_data()
        
        # Insert fresh data
        items_inserted = self.insert_fresh_food_data(food_data)
        
        logger.info(f"Data refresh completed: {items_inserted} items")
        return items_inserted
    
    def insert_food_data(self, food_data: List[Dict]) -> Tuple[int, int]:
        """
        Legacy method for backward compatibility.
        Now uses refresh_all_data approach.
        Returns tuple of (items_added, items_updated) for compatibility.
        """
        items_inserted = self.refresh_all_data(food_data)
        # For compatibility, return as (added, updated) where all items are "added"
        return items_inserted, 0
    
    def import_from_csv(self, csv_path: str) -> Tuple[int, int]:
        """Import data from CSV file using fresh refresh approach."""
        df = pd.read_csv(csv_path)
        food_data = df.to_dict('records')
        return self.insert_food_data(food_data)
    
    def get_all_items(self, unit_id: Optional[str] = None, category: Optional[str] = None, subcategory: Optional[str] = None) -> List[Dict]:
        """Get all food items with optional filtering."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            query = '''
                SELECT f.*, 
                       n.calories, n.total_fat, n.saturated_fat, n.trans_fat,
                       n.cholesterol, n.sodium, n.total_carb, n.dietary_fiber,
                       n.sugars, n.protein,
                       i.ingredients, i.allergens
                FROM food_items f
                LEFT JOIN nutrition_facts n ON f.item_id = n.item_id
                LEFT JOIN ingredients i ON f.item_id = i.item_id
            '''
            
            params = []
            where_clauses = []
            
            if unit_id:
                where_clauses.append('f.unit_id = ?')
                params.append(unit_id)
            if category:
                where_clauses.append('f.category = ?')
                params.append(category)
            if subcategory:
                where_clauses.append('f.subcategory = ?')
                params.append(subcategory)
            
            if where_clauses:
                query += ' WHERE ' + ' AND '.join(where_clauses)
            
            query += ' ORDER BY f.item_name'
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_item_by_id(self, item_id: str) -> Optional[Dict]:
        """Get a specific food item by its ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT f.*, 
                       n.calories, n.total_fat, n.saturated_fat, n.trans_fat,
                       n.cholesterol, n.sodium, n.total_carb, n.dietary_fiber,
                       n.sugars, n.protein,
                       i.ingredients, i.allergens
                FROM food_items f
                LEFT JOIN nutrition_facts n ON f.item_id = n.item_id
                LEFT JOIN ingredients i ON f.item_id = i.item_id
                WHERE f.item_id = ?
            ''', (item_id,))
            
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def search_items(self, search_term: str) -> List[Dict]:
        """Search items by name."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT f.*, 
                       n.calories, n.total_fat, n.saturated_fat, n.trans_fat,
                       n.cholesterol, n.sodium, n.total_carb, n.dietary_fiber,
                       n.sugars, n.protein,
                       i.ingredients, i.allergens
                FROM food_items f
                LEFT JOIN nutrition_facts n ON f.item_id = n.item_id
                LEFT JOIN ingredients i ON f.item_id = i.item_id
                WHERE f.item_name LIKE ?
                ORDER BY f.item_name
            ''', (f'%{search_term}%',))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_units(self) -> List[Dict]:
        """Get all available units/restaurants."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT unit_id, unit_name, COUNT(*) as item_count
                FROM food_items 
                GROUP BY unit_id, unit_name
                ORDER BY unit_name
            ''')
            return [{'unit_id': row[0], 'unit_name': row[1], 'item_count': row[2]} 
                    for row in cursor.fetchall()]
    
    def get_categories(self, unit_id: Optional[str] = None) -> List[str]:
        """Get all available categories."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if unit_id:
                cursor.execute('''
                    SELECT DISTINCT category FROM food_items 
                    WHERE unit_id = ? AND category IS NOT NULL
                    ORDER BY category
                ''', (unit_id,))
            else:
                cursor.execute('''
                    SELECT DISTINCT category FROM food_items 
                    WHERE category IS NOT NULL
                    ORDER BY category
                ''')
            return [row[0] for row in cursor.fetchall()]
    
    def get_subcategories(self, unit_id: Optional[str] = None, category: Optional[str] = None) -> List[str]:
        """Get all available subcategories."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            params = []
            where_clauses = ['subcategory IS NOT NULL']
            
            if unit_id:
                where_clauses.append('unit_id = ?')
                params.append(unit_id)
            if category:
                where_clauses.append('category = ?')
                params.append(category)
            
            query = f'''
                SELECT DISTINCT subcategory FROM food_items 
                WHERE {' AND '.join(where_clauses)}
                ORDER BY subcategory
            '''
            
            cursor.execute(query, params)
            return [row[0] for row in cursor.fetchall()]
    
    def log_scraping_session(self, started_at: datetime, completed_at: Optional[datetime] = None,
                           items_found: int = 0, items_added: int = 0, items_updated: int = 0,
                           status: str = 'started', error_message: Optional[str] = None) -> int:
        """Log a scraping session."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO scraping_log 
                (started_at, completed_at, items_found, items_added, items_updated, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (started_at, completed_at, items_found, items_added, items_updated, status, error_message))
            conn.commit()
            return cursor.lastrowid
    
    def update_scraping_session(self, log_id: int, completed_at: datetime,
                              items_found: int = 0, items_added: int = 0, items_updated: int = 0,
                              status: str = 'completed', error_message: Optional[str] = None):
        """Update a scraping session log."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE scraping_log 
                SET completed_at = ?, items_found = ?, items_added = ?, items_updated = ?, 
                    status = ?, error_message = ?
                WHERE id = ?
            ''', (completed_at, items_found, items_added, items_updated, status, error_message, log_id))
            conn.commit()
    
    def get_scraping_history(self, limit: int = 10) -> List[Dict]:
        """Get recent scraping history."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM scraping_log 
                ORDER BY started_at DESC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def _parse_calories(self, calories_str: str) -> Optional[int]:
        """Parse calories string to integer."""
        if not calories_str:
            return None
        try:
            # Remove any non-digit characters and convert to int
            return int(''.join(filter(str.isdigit, str(calories_str))))
        except (ValueError, TypeError):
            return None
    
    def export_to_csv(self, output_path: str, unit_id: Optional[str] = None):
        """Export data to CSV."""
        items = self.get_all_items(unit_id=unit_id)
        df = pd.DataFrame(items)
        df.to_csv(output_path, index=False)
        logger.info(f"Exported {len(items)} items to {output_path}")
    
    def get_stats(self) -> Dict:
        """Get database statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM food_items')
            total_items = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT unit_id) FROM food_items')
            total_units = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT category) FROM food_items WHERE category IS NOT NULL')
            total_categories = cursor.fetchone()[0]
            
            cursor.execute('SELECT MAX(updated_at) FROM food_items')
            last_updated = cursor.fetchone()[0]
            
            # Get the last scraping info
            cursor.execute('SELECT scraped_at FROM nutrition_facts ORDER BY scraped_at DESC LIMIT 1')
            last_scraped = cursor.fetchone()
            last_scraped = last_scraped[0] if last_scraped else None
            
            return {
                'total_items': total_items,
                'total_units': total_units,
                'total_categories': total_categories,
                'last_updated': last_updated,
                'last_scraped': last_scraped
            }

# Convenience functions
def create_database(db_path: str = "nutrition_data.db") -> NutritionDatabase:
    """Create and return a new database instance."""
    return NutritionDatabase(db_path)

def import_csv_to_db(csv_path: str, db_path: str = "nutrition_data.db") -> Tuple[int, int]:
    """Import CSV data to database."""
    db = NutritionDatabase(db_path)
    return db.import_from_csv(csv_path) 