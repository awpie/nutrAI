# NutrAI - Duke Nutrition Database & Scraper

A comprehensive system for scraping, storing, and querying nutrition data from Duke University's dining services. This system provides automated daily scraping with a **complete refresh approach** - each scrape wipes the database and inserts fresh data, ensuring you always have the most current information from NetNutrition.

## 🚀 Features

- **Automated Daily Refresh**: Complete database refresh daily with latest nutrition data
- **SQLite Database**: Efficient storage with simple refresh approach
- **Query API**: Powerful search and filtering capabilities
- **Meal Planning**: Nutritional summaries for multiple items
- **Health-focused Queries**: Find healthy options, high-protein foods, allergen-free items
- **CLI Interface**: Easy command-line access to all features
- **Scraping Logs**: Track scraping history and performance

## 📁 Project Structure

```
nutrAI/
├── scraper.py              # Original web scraper
├── database.py             # Database management & schema
├── scheduler.py            # Automated daily scraping with refresh
├── query_api.py           # Query interface & CLI
├── setup_database.py      # Initial setup script
├── requirements.txt       # Python dependencies
├── nutrition_data.db      # SQLite database (created after setup)
├── scraping.log          # Scraping activity logs
└── duke_nutrition_data_*.csv  # CSV exports (existing)
```

## 🔄 Database Approach

This system uses a **complete refresh approach** for simplicity and data integrity:

- **Daily Refresh**: Each scraping session completely clears the database and inserts fresh data
- **No Incremental Updates**: No complex logic for detecting changes or handling updates
- **Always Current**: Database always reflects the exact current state of NetNutrition
- **Simplified Logic**: Eliminates issues with stale data, duplicate detection, etc.

This approach is perfect for nutrition data since:

- Menu items change frequently
- Nutritional information can be updated
- Complete refresh ensures data consistency
- Scraping runs once daily, so performance is not a concern

## 🛠️ Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
python setup_database.py
```

This will:

- Create the SQLite database with proper schema
- Import your existing CSV data (initial import)
- Show database statistics
- Display next steps

### 3. Test the System

```bash
# Run scraping once to test (this will refresh all data)
python scheduler.py --run-once

# Search for items
python query_api.py search "chicken"

# View all restaurants
python query_api.py restaurants
```

## 📅 Daily Scraping with Complete Refresh

### Set up automated daily scraping:

```bash
# Schedule daily scraping at 6:00 AM (complete refresh)
python scheduler.py --schedule daily --time 06:00
```

**What happens during each scrape:**

1. Start scraping session
2. Scrape all current data from NetNutrition
3. **Clear all existing data** from database
4. **Insert fresh data** from scrape
5. Log the session with item counts

### Other scheduling options:

```bash
# Hourly scraping (for testing) - full refresh each time
python scheduler.py --schedule hourly

# Weekly scraping (Mondays at 6 AM) - full refresh
python scheduler.py --schedule weekly --day monday --time 06:00

# Run as daemon (background service)
python scheduler.py --schedule daily --time 06:00 --daemon
```

### Interactive scheduler:

```bash
python scheduler.py --schedule daily --time 06:00
# Then use commands: run, status, quit
```

## 🔍 Query API

### Command Line Interface

```bash
# Search for food items
python query_api.py search "salad"
python query_api.py search "pizza" --restaurant 13

# List all restaurants
python query_api.py restaurants

# Get menu for specific restaurant
python query_api.py menu 13
python query_api.py menu 13 --category "Breakfast"

# Find healthy options (under 400 calories)
python query_api.py healthy --max-calories 300

# Find high protein items (20g+ protein)
python query_api.py protein --min-protein 25

# Find allergen-free options
python query_api.py allergen-free milk nuts

# Plan a meal with multiple items
python query_api.py meal 243782327 243782328 243782329

# Show database statistics
python query_api.py stats
```

### Python API

```python
from query_api import NutritionAPI

api = NutritionAPI()

# Search for items
chicken_items = api.search_food("chicken")
print(f"Found {len(chicken_items)} chicken items")

# Get restaurants
restaurants = api.get_restaurants()
for restaurant in restaurants:
    print(f"{restaurant['unit_name']}: {restaurant['item_count']} items")

# Find healthy options
healthy = api.find_healthy_options(max_calories=350)
print(f"Found {len(healthy)} items under 350 calories")

# Find high protein options
high_protein = api.find_high_protein(min_protein=20)
print(f"Found {len(high_protein)} high protein items")

# Allergen-free search
safe_items = api.find_by_allergens(['milk', 'nuts'])
print(f"Found {len(safe_items)} dairy and nut-free items")

# Meal planning
meal_summary = api.get_nutritional_summary(['243782327', '243782328'])
print(f"Meal total: {meal_summary['total_calories']} calories")
```

## 💾 Database Schema

### Tables

1. **food_items**: Basic food item information
2. **nutrition_facts**: Nutritional data (refreshed daily)
3. **ingredients**: Ingredient lists and allergens (refreshed daily)
4. **scraping_log**: Scraping session tracking (preserved across refreshes)

### Key Features

- **Complete Refresh**: All food data is wiped and refreshed daily
- **Efficient Querying**: Proper indexes for fast searches
- **Data Integrity**: Foreign key constraints and validation
- **Scraping History**: Complete audit trail of refresh sessions (preserved)
- **Simple Schema**: No versioning complexity since data is refreshed completely

## 📊 Monitoring Your Refreshes

### View scraping history:

```python
from database import NutritionDatabase

db = NutritionDatabase()
history = db.get_scraping_history(10)

for entry in history:
    print(f"{entry['started_at']}: {entry['status']} - "
          f"{entry['items_added']} items refreshed")
```

### Database statistics:

```python
stats = db.get_stats()
print(f"Total items: {stats['total_items']}")
print(f"Last refreshed: {stats['last_scraped']}")
```

**Note**: In refresh mode, `items_added` represents the total number of items in the refreshed database, and `items_updated` is always 0.

## 🔧 Advanced Configuration

### Manual Database Refresh

You can manually refresh the database with new data:

```python
from database import NutritionDatabase

db = NutritionDatabase()

# Clear all data and insert fresh data
items_inserted = db.refresh_all_data(new_food_data)
print(f"Database refreshed with {items_inserted} items")
```

### Clear Database Only

```python
# Clear all food data (but keep scraping logs)
db.clear_food_data()
```

### Database Path

All scripts accept a `--db-path` parameter:

```bash
python scheduler.py --db-path /path/to/custom.db --run-once
python query_api.py --db-path /path/to/custom.db search "pizza"
```

### Custom Schedules

The scheduler supports cron-like scheduling:

```python
from scheduler import NutritionScrapeScheduler

scheduler = NutritionScrapeScheduler()
scheduler.schedule_daily_scraping("06:00")  # 6 AM daily
scheduler.start()
```

### Export Data

```python
from database import NutritionDatabase

db = NutritionDatabase()
db.export_to_csv("backup.csv")  # Export all data
db.export_to_csv("cafe_only.csv", unit_id="13")  # Export specific restaurant
```

## 📈 Monitoring

### View scraping history:

```python
from database import NutritionDatabase

db = NutritionDatabase()
history = db.get_scraping_history(10)

for entry in history:
    print(f"{entry['started_at']}: {entry['status']} - "
          f"{entry['items_added']} added, {entry['items_updated']} updated")
```

### Database statistics:

```python
stats = db.get_stats()
print(f"Total items: {stats['total_items']}")
print(f"Last updated: {stats['last_updated']}")
```

## 🚀 Next Steps

1. **Set up daily scraping** for automated data refresh
2. **Monitor scraping logs** to ensure reliable daily updates
3. **Build a web interface** using Flask/FastAPI
4. **Add more restaurants** by extending the scraper
5. **Implement recommendations** based on dietary preferences
6. **Add nutrition analysis** and meal optimization features

## 🔍 Troubleshooting

### Common Issues

1. **Import errors**: Make sure all dependencies are installed
2. **Database locked**: Only one process can write to SQLite at a time
3. **Scraping failures**: Check your internet connection and Duke's website availability
4. **Missing data after refresh**: Check scraping logs for errors

### Logs

Check `scraping.log` for detailed scraping activity and error messages. Each refresh operation is logged with:

- Start/completion times
- Number of items found and inserted
- Any errors encountered

### Reset Database

To start completely fresh:

```bash
rm nutrition_data.db
python setup_database.py
```

This will recreate the database and import your existing CSV data.

---

Built for Duke University students to make informed dining choices! 🍽️📊
