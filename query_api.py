#!/usr/bin/env python3
"""
Simple API for querying nutrition data
Provides convenient functions for common queries
"""

from typing import List, Dict, Optional, Tuple
import argparse
import json
from database import NutritionDatabase

class NutritionAPI:
    def __init__(self, db_path: str = "nutrition_data.db"):
        """Initialize the API with database connection."""
        self.db = NutritionDatabase(db_path)
    
    def search_food(self, search_term: str, unit_id: Optional[str] = None) -> List[Dict]:
        """Search for food items by name."""
        items = self.db.search_items(search_term)
        if unit_id:
            items = [item for item in items if item['unit_id'] == unit_id]
        return items
    
    def get_food_by_id(self, item_id: str) -> Optional[Dict]:
        """Get specific food item by ID."""
        return self.db.get_item_by_id(item_id)
    
    def get_restaurants(self) -> List[Dict]:
        """Get all available restaurants/units."""
        return self.db.get_units()
    
    def get_menu_by_restaurant(self, unit_id: str, category: Optional[str] = None, subcategory: Optional[str] = None) -> List[Dict]:
        """Get menu items for a specific restaurant."""
        return self.db.get_all_items(unit_id=unit_id, category=category, subcategory=subcategory)
    
    def get_categories(self, unit_id: Optional[str] = None) -> List[str]:
        """Get all available food categories."""
        return self.db.get_categories(unit_id=unit_id)
    
    def get_subcategories(self, unit_id: Optional[str] = None, category: Optional[str] = None) -> List[str]:
        """Get all available food subcategories."""
        return self.db.get_subcategories(unit_id=unit_id, category=category)
    
    def find_healthy_options(self, max_calories: int = 400, unit_id: Optional[str] = None, subcategory: Optional[str] = None) -> List[Dict]:
        """Find food items under specified calorie limit."""
        items = self.db.get_all_items(unit_id=unit_id, subcategory=subcategory)
        healthy_items = []
        
        for item in items:
            if item['calories'] and item['calories'] <= max_calories:
                healthy_items.append(item)
        
        # Sort by calories (ascending)
        return sorted(healthy_items, key=lambda x: x['calories'] or 0)
    
    def find_high_protein(self, min_protein: int = 20, unit_id: Optional[str] = None, subcategory: Optional[str] = None) -> List[Dict]:
        """Find food items with high protein content."""
        items = self.db.get_all_items(unit_id=unit_id, subcategory=subcategory)
        high_protein_items = []
        
        for item in items:
            protein_str = item.get('protein', '')
            if protein_str:
                try:
                    # Extract numeric value from protein string (e.g., "20g" -> 20)
                    protein_value = int(''.join(filter(str.isdigit, str(protein_str))))
                    if protein_value >= min_protein:
                        item['protein_value'] = protein_value
                        high_protein_items.append(item)
                except (ValueError, TypeError):
                    continue
        
        # Sort by protein content (descending)
        return sorted(high_protein_items, key=lambda x: x.get('protein_value', 0), reverse=True)
    
    def find_by_allergens(self, avoid_allergens: List[str], unit_id: Optional[str] = None, subcategory: Optional[str] = None) -> List[Dict]:
        """Find food items that don't contain specified allergens."""
        items = self.db.get_all_items(unit_id=unit_id, subcategory=subcategory)
        safe_items = []
        
        for item in items:
            allergens = item.get('allergens', '') or ''
            ingredients = item.get('ingredients', '') or ''
            
            # Check if any of the avoid_allergens are mentioned
            has_allergen = False
            for allergen in avoid_allergens:
                if (allergen.lower() in allergens.lower() or 
                    allergen.lower() in ingredients.lower()):
                    has_allergen = True
                    break
            
            if not has_allergen:
                safe_items.append(item)
        
        return safe_items
    
    def get_nutritional_summary(self, item_ids: List[str]) -> Dict:
        """Get nutritional summary for multiple items (meal planning)."""
        items = [self.db.get_item_by_id(item_id) for item_id in item_ids]
        items = [item for item in items if item]  # Filter out None items
        
        total_calories = 0
        total_protein = 0
        total_carbs = 0
        total_fat = 0
        
        for item in items:
            # Parse calories
            if item['calories']:
                total_calories += item['calories']
            
            # Parse protein (extract numbers from strings like "20g")
            protein_str = item.get('protein', '')
            if protein_str:
                try:
                    protein_val = int(''.join(filter(str.isdigit, str(protein_str))))
                    total_protein += protein_val
                except (ValueError, TypeError):
                    pass
            
            # Parse carbs
            carbs_str = item.get('total_carb', '')
            if carbs_str:
                try:
                    carbs_val = int(''.join(filter(str.isdigit, str(carbs_str))))
                    total_carbs += carbs_val
                except (ValueError, TypeError):
                    pass
            
            # Parse fat
            fat_str = item.get('total_fat', '')
            if fat_str:
                try:
                    fat_val = int(''.join(filter(str.isdigit, str(fat_str))))
                    total_fat += fat_val
                except (ValueError, TypeError):
                    pass
        
        return {
            'total_items': len(items),
            'total_calories': total_calories,
            'total_protein': f"{total_protein}g",
            'total_carbs': f"{total_carbs}g",
            'total_fat': f"{total_fat}g",
            'items': [{'id': item['item_id'], 'name': item['item_name']} for item in items]
        }
    
    def get_stats(self) -> Dict:
        """Get database statistics."""
        return self.db.get_stats()
    
    def get_scraping_history(self, limit: int = 10) -> List[Dict]:
        """Get recent scraping history."""
        return self.db.get_scraping_history(limit)

def main():
    """CLI interface for the API."""
    parser = argparse.ArgumentParser(description='Nutrition Data Query API')
    parser.add_argument('--db-path', default='nutrition_data.db', help='Database path')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search for food items')
    search_parser.add_argument('term', help='Search term')
    search_parser.add_argument('--restaurant', help='Filter by restaurant ID')
    
    # Restaurant command
    rest_parser = subparsers.add_parser('restaurants', help='List all restaurants')
    
    # Menu command
    menu_parser = subparsers.add_parser('menu', help='Get menu for restaurant')
    menu_parser.add_argument('restaurant_id', help='Restaurant ID')
    menu_parser.add_argument('--category', help='Filter by category')
    menu_parser.add_argument('--subcategory', help='Filter by subcategory')
    
    # Subcategories command
    subcat_parser = subparsers.add_parser('subcategories', help='List subcategories')
    subcat_parser.add_argument('--restaurant', help='Filter by restaurant ID')
    subcat_parser.add_argument('--category', help='Filter by category')
    
    # Healthy options command
    healthy_parser = subparsers.add_parser('healthy', help='Find healthy options')
    healthy_parser.add_argument('--max-calories', type=int, default=400, help='Maximum calories')
    healthy_parser.add_argument('--restaurant', help='Filter by restaurant ID')
    healthy_parser.add_argument('--subcategory', help='Filter by subcategory')
    
    # High protein command
    protein_parser = subparsers.add_parser('protein', help='Find high protein options')
    protein_parser.add_argument('--min-protein', type=int, default=20, help='Minimum protein (g)')
    protein_parser.add_argument('--restaurant', help='Filter by restaurant ID')
    protein_parser.add_argument('--subcategory', help='Filter by subcategory')
    
    # Allergen-free command
    allergen_parser = subparsers.add_parser('allergen-free', help='Find allergen-free options')
    allergen_parser.add_argument('allergens', nargs='+', help='Allergens to avoid')
    allergen_parser.add_argument('--restaurant', help='Filter by restaurant ID')
    allergen_parser.add_argument('--subcategory', help='Filter by subcategory')
    
    # Meal planning command
    meal_parser = subparsers.add_parser('meal', help='Plan a meal with multiple items')
    meal_parser.add_argument('item_ids', nargs='+', help='Item IDs to include in meal')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    api = NutritionAPI(args.db_path)
    
    try:
        if args.command == 'search':
            results = api.search_food(args.term, args.restaurant)
            print(f"Found {len(results)} items:")
            for item in results[:10]:  # Show first 10 results
                print(f"  {item['item_name']} - {item['calories']} cal ({item['unit_name']})")
        
        elif args.command == 'restaurants':
            restaurants = api.get_restaurants()
            print("Available restaurants:")
            for rest in restaurants:
                print(f"  {rest['unit_name']} (ID: {rest['unit_id']}) - {rest['item_count']} items")
        
        elif args.command == 'subcategories':
            subcategories = api.get_subcategories(args.restaurant, args.category)
            filter_desc = ""
            if args.restaurant:
                filter_desc += f" for restaurant {args.restaurant}"
            if args.category:
                filter_desc += f" in category '{args.category}'"
            print(f"Available subcategories{filter_desc}:")
            for subcat in subcategories:
                print(f"  {subcat}")
        
        elif args.command == 'menu':
            menu = api.get_menu_by_restaurant(args.restaurant_id, args.category, args.subcategory)
            print(f"Menu items: {len(menu)}")
            for item in menu[:20]:  # Show first 20 items
                print(f"  {item['item_name']} - {item['calories']} cal")
        
        elif args.command == 'healthy':
            healthy = api.find_healthy_options(args.max_calories, args.restaurant, args.subcategory)
            print(f"Found {len(healthy)} healthy options (≤{args.max_calories} cal):")
            for item in healthy[:10]:
                print(f"  {item['item_name']} - {item['calories']} cal ({item['unit_name']})")
        
        elif args.command == 'protein':
            high_protein = api.find_high_protein(args.min_protein, args.restaurant, args.subcategory)
            print(f"Found {len(high_protein)} high protein options (≥{args.min_protein}g):")
            for item in high_protein[:10]:
                print(f"  {item['item_name']} - {item['protein']} protein ({item['unit_name']})")
        
        elif args.command == 'allergen-free':
            safe_items = api.find_by_allergens(args.allergens, args.restaurant, args.subcategory)
            print(f"Found {len(safe_items)} items avoiding {', '.join(args.allergens)}:")
            for item in safe_items[:10]:
                print(f"  {item['item_name']} ({item['unit_name']})")
        
        elif args.command == 'meal':
            summary = api.get_nutritional_summary(args.item_ids)
            print("Meal Summary:")
            print(json.dumps(summary, indent=2))
        
        elif args.command == 'stats':
            stats = api.get_stats()
            print("Database Statistics:")
            print(json.dumps(stats, indent=2))
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 