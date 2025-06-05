import requests
from bs4 import BeautifulSoup
import json
import csv
import time
from datetime import datetime
import os
import signal
import sys

BASE_URL = "https://netnutrition.cbord.com/nn-prod/Duke"
session = requests.Session()

# Global variables for graceful shutdown
all_nutrition_data = []
csv_filename = ""
fieldnames = []

def clean_text(text):
    """Clean text by removing accented characters and extra whitespace"""
    if not text:
        return ""
    return text.replace('Â', '').replace('\xa0', ' ').strip()

# Headers for main page (regular navigation)
main_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

# Headers for AJAX requests (like nutrition label)
ajax_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://netnutrition.cbord.com",
    "Referer": BASE_URL,
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "X-Requested-With": "XMLHttpRequest",
    "Priority": "u=1, i"
}

def setup_session():
    """Initialize session with proper cookies"""
    print("Setting up session...")
    # Get initial cookies
    initial_response = session.head(BASE_URL, headers=main_headers)
    print(f"Initial response status: {initial_response.status_code}")
    
    # Set the CBORD cookie to match browser (lowercase "duke")
    session.cookies.set('CBORD.netnutrition2', 'NNexternalID=duke', domain='netnutrition.cbord.com')
    
    print("Session setup complete")
    return session

def get_units():
    """Get list of all restaurants/units from the main page"""
    print("Getting list of units/restaurants...")
    main_page = session.get(BASE_URL, headers=main_headers)
    
    if main_page.status_code != 200:
        print(f"Failed to get main page: {main_page.status_code}")
        return []
    
    soup = BeautifulSoup(main_page.text, 'lxml')
    
    # Look for unit/restaurant elements
    # They might be in a dropdown, list, or have data-unit-oid attributes
    units = []
    
    # Try different possible selectors for units
    unit_elements = soup.find_all(attrs={'data-unit-oid': True})
    if unit_elements:
        print(f"Found {len(unit_elements)} units with data-unit-oid")
        for elem in unit_elements:
            unit_id = elem.get('data-unit-oid')
            unit_name = elem.text.strip() if elem.text else f"Unit {unit_id}"
            units.append({"id": unit_id, "name": unit_name})
    else:
        # If no data attributes, look for onclick handlers or other patterns
        clickable_elements = soup.find_all(attrs={'onclick': True})
        for elem in clickable_elements:
            onclick = elem.get('onclick', '')
            if 'selectunit' in onclick.lower() or 'unitoid' in onclick.lower():
                # Extract unit ID from onclick
                import re
                match = re.search(r'(\d+)', onclick)
                if match:
                    unit_id = match.group(1)
                    unit_name = elem.text.strip() if elem.text else f"Unit {unit_id}"
                    units.append({"id": unit_id, "name": unit_name})
    
    # If still no units found, try known unit ID 21 from your example
    if not units:
        print("No units found on page, using known unit 21")
        units = [{"id": "21", "name": "Default Restaurant"}]
    
    print(f"Found {len(units)} units: {[u['name'] for u in units]}")
    return units

def select_unit_and_get_menu(unit_id):
    """Select a unit/restaurant and get its menu items, handling hierarchical menus"""
    print(f"Selecting unit {unit_id}...")
    
    unit_url = f"{BASE_URL}/Unit/SelectUnitFromUnitsList"
    unit_payload = {"unitOid": str(unit_id)}
    
    response = session.post(unit_url, data=unit_payload, headers=ajax_headers)
    
    if response.status_code != 200:
        print(f"Failed to select unit {unit_id}: {response.status_code}")
        return []
    
    content_type = response.headers.get('Content-Type', '')
    if not content_type.startswith('application/json'):
        print(f"Unit selection didn't return JSON for unit {unit_id}")
        return []
    
    try:
        unit_data = json.loads(response.text)
        if not unit_data.get('success'):
            print(f"Unit selection was not successful for unit {unit_id}")
            return []
        
        # Extract menu items from the JSON response
        menu_items = []
        panels = unit_data.get('panels', [])
        
        print(f"Unit {unit_id} response has {len(panels)} panels")
        
        # First, try to get items directly from itemPanel
        items_found_directly = False
        
        for panel in panels:
            panel_id = panel.get('id', 'unknown')
            print(f"  Panel: {panel_id}")
            
            if panel.get('id') == 'itemPanel':
                html_content = panel.get('html', '')
                print(f"  ItemPanel HTML length: {len(html_content)}")
                
                if html_content:
                    items_from_panel = extract_menu_items_from_html(html_content, unit_id)
                    if items_from_panel:
                        menu_items.extend(items_from_panel)
                        items_found_directly = True
                        print(f"  Found {len(items_from_panel)} items directly in itemPanel")
                else:
                    print("  ItemPanel HTML is empty")
        
        # If no items found directly, look for menu categories to click
        if not items_found_directly:
            print("  No items found directly, looking for menu categories...")
            menu_categories = []
            
            # Look for menu categories in all panels
            for panel in panels:
                panel_id = panel.get('id', 'unknown')
                html_content = panel.get('html', '')
                
                if html_content and len(html_content) > 100:
                    soup = BeautifulSoup(html_content, 'lxml')
                    clickable_elements = soup.find_all(attrs={'onclick': True})
                    
                    for elem in clickable_elements:
                        onclick = elem.get('onclick', '')
                        text = elem.text.strip()
                        
                        # Look for menuListSelectMenu calls
                        if 'menuListSelectMenu' in onclick:
                            import re
                            match = re.search(r'menuListSelectMenu\((\d+)\)', onclick)
                            if match:
                                menu_id = match.group(1)
                                menu_categories.append({
                                    "menu_id": menu_id,
                                    "name": text,
                                    "type": "menu"
                                })
                                print(f"    Found menu category: {text} (ID: {menu_id})")
                        
                        # Look for toggleCourseItems calls
                        elif 'toggleCourseItems' in onclick:
                            import re
                            match = re.search(r'toggleCourseItems\(this,\s*(\d+)\)', onclick)
                            if match:
                                course_id = match.group(1)
                                menu_categories.append({
                                    "course_id": course_id,
                                    "name": text,
                                    "type": "course"
                                })
                                print(f"    Found course category: {text} (ID: {course_id})")
            
            # Filter menu categories to avoid duplicates from future days
            # Group by category name and take only the first one of each type
            if menu_categories:
                filtered_categories = []
                seen_category_names = set()
                
                for category in menu_categories:
                    category_name = category['name']
                    if category_name not in seen_category_names:
                        filtered_categories.append(category)
                        seen_category_names.add(category_name)
                        print(f"    Selected: {category_name} (avoiding future day duplicates)")
                    else:
                        print(f"    Skipped duplicate: {category_name}")
                
                menu_categories = filtered_categories
            
            # Click on each menu category and extract items
            if menu_categories:
                print(f"  Found {len(menu_categories)} unique categories to explore")
                
                for category in menu_categories:
                    category_name = category['name']
                    print(f"    Getting items from category: {category_name}")
                    
                    try:
                        if category['type'] == 'menu':
                            # Handle menu selection
                            menu_url = f"{BASE_URL}/Menu/SelectMenu"
                            menu_payload = {"menuOid": category['menu_id']}
                            category_response = session.post(menu_url, data=menu_payload, headers=ajax_headers)
                            selected_menu_id = category['menu_id']
                        else:  # course
                            # Handle course toggle
                            course_url = f"{BASE_URL}/Course/ToggleCourseItemsOnClick"
                            course_payload = {"courseItemsOid": category['course_id']}
                            category_response = session.post(course_url, data=course_payload, headers=ajax_headers)
                            selected_menu_id = None  # Courses don't have menu IDs
                        
                        if category_response.status_code == 200 and len(category_response.text) > 100:
                            try:
                                category_data = json.loads(category_response.text)
                                category_panels = category_data.get('panels', [])
                                
                                # Extract items from category panels
                                category_items = []
                                for cpanel in category_panels:
                                    if cpanel.get('id') == 'itemPanel':
                                        cpanel_html = cpanel.get('html', '')
                                        if cpanel_html:
                                            items_from_category = extract_menu_items_from_html(cpanel_html, unit_id, category_name)
                                            # Add menu context for nutrition requests
                                            for item in items_from_category:
                                                item['selected_menu_id'] = selected_menu_id
                                                item['category_type'] = category['type']
                                            category_items.extend(items_from_category)
                                
                                if category_items:
                                    menu_items.extend(category_items)
                                    print(f"      Found {len(category_items)} items in {category_name}")
                                else:
                                    print(f"      No items found in {category_name}")
                            
                            except json.JSONDecodeError:
                                print(f"      Failed to parse JSON for category {category_name}")
                        else:
                            print(f"      Failed to get category {category_name}: {category_response.status_code}")
                    
                    except Exception as e:
                        print(f"      Error processing category {category_name}: {e}")
                    
                    # Small delay between category requests
                    time.sleep(0.2)
            else:
                print("  No menu categories found")
        
        print(f"Found {len(menu_items)} total menu items for unit {unit_id}")
        return menu_items
        
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON for unit {unit_id}: {e}")
        return []

def extract_menu_items_from_html(html_content, unit_id, category_name=None):
    """Extract menu items from HTML content with improved subcategory association"""
    menu_items = []
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Get all food items using both methods
    def get_all_food_items(container_soup):
        """Helper to get all food items from a container using both methods"""
        items = []
        
        # Method 1: data-item-oid
        data_items = container_soup.find_all(attrs={'data-item-oid': True})
        for item in data_items:
            item_id = item.get('data-item-oid')
            item_name = clean_text(item.text)
            if item_id and item_name and len(item_name) > 2:
                items.append({
                    'id': item_id,
                    'name': ' '.join(item_name.split()),
                    'element': item,
                    'method': 'data-attr'
                })
        
        # Method 2: onclick nutrition handlers
        onclick_items = container_soup.find_all(attrs={'onclick': True})
        for item in onclick_items:
            onclick = item.get('onclick', '')
            if 'getItemNutritionLabelOnClick' in onclick:
                import re
                match = re.search(r'getItemNutritionLabelOnClick\(event,(\d+)\)', onclick)
                if match:
                    item_id = match.group(1)
                    item_name = clean_text(item.text)
                    if item_name and len(item_name) > 2:
                        items.append({
                            'id': item_id,
                            'name': ' '.join(item_name.split()),
                            'element': item,
                            'method': 'onclick'
                        })
        
        return items
    
    # Find all subcategory toggles
    subcategory_elements = []
    clickable_elements = soup.find_all(attrs={'onclick': True})
    
    for elem in clickable_elements:
        onclick = elem.get('onclick', '')
        if 'toggleCourseItems' in onclick:
            import re
            match = re.search(r'toggleCourseItems\(this,\s*(\d+)\)', onclick)
            if match:
                course_id = match.group(1)
                subcategory_name = clean_text(elem.text)
                subcategory_elements.append({
                    'course_id': course_id,
                    'name': subcategory_name,
                    'element': elem
                })
    
    print(f"    Found {len(subcategory_elements)} subcategories in HTML")
    
    # Associate items with subcategories
    assigned_items = set()
    
    for subcat in subcategory_elements:
        course_id = subcat['course_id']
        subcat_name = subcat['name']
        subcat_elem = subcat['element']
        
        associated_items = []
        
        # Approach 1: Look for containers with course ID
        course_containers = soup.find_all('div', attrs={'id': lambda x: x and course_id in str(x)})
        if not course_containers:
            course_containers = soup.find_all('div', class_=lambda x: x and course_id in str(x))
        if not course_containers:
            # Also check for other tags
            course_containers = soup.find_all(attrs={'id': lambda x: x and course_id in str(x)})
        
        for container in course_containers:
            container_items = get_all_food_items(container)
            for item_data in container_items:
                if item_data['id'] not in assigned_items:
                    associated_items.append({
                        "id": item_data['id'],
                        "name": item_data['name'],
                        "unit_id": unit_id,
                        "category": category_name,
                        "subcategory": subcat_name
                    })
                    assigned_items.add(item_data['id'])
        
        # Approach 2: Look for items positioned after subcategory in DOM structure
        if not associated_items:
            parent = subcat_elem.parent
            if parent:
                # Try broader search - look at grandparent too
                search_containers = [parent]
                if parent.parent:
                    search_containers.append(parent.parent)
                
                for search_container in search_containers:
                    # Get all elements in order
                    all_elements = search_container.find_all(True)
                    
                    # Find subcategory position
                    subcat_position = None
                    for i, elem in enumerate(all_elements):
                        if elem == subcat_elem:
                            subcat_position = i
                            break
                    
                    if subcat_position is not None:
                        # Find the next subcategory position to limit scope
                        next_subcat_position = len(all_elements)
                        for other_subcat in subcategory_elements:
                            if other_subcat['course_id'] != course_id:
                                for i, elem in enumerate(all_elements):
                                    if elem == other_subcat['element'] and i > subcat_position:
                                        next_subcat_position = min(next_subcat_position, i)
                        
                        # Collect items between current and next subcategory
                        for i in range(subcat_position + 1, next_subcat_position):
                            elem = all_elements[i]
                            
                            # Check if this element is a food item
                            item_id = elem.get('data-item-oid')
                            if not item_id:
                                onclick = elem.get('onclick', '')
                                if 'getItemNutritionLabelOnClick' in onclick:
                                    import re
                                    match = re.search(r'getItemNutritionLabelOnClick\(event,(\d+)\)', onclick)
                                    if match:
                                        item_id = match.group(1)
                            
                            if item_id and item_id not in assigned_items:
                                item_name = clean_text(elem.text)
                                if item_name and len(item_name) > 2:
                                    associated_items.append({
                                        "id": item_id,
                                        "name": ' '.join(item_name.split()),
                                        "unit_id": unit_id,
                                        "category": category_name,
                                        "subcategory": subcat_name
                                    })
                                    assigned_items.add(item_id)
                    
                    if associated_items:
                        break  # Found items, don't need to search grandparent
        
        if associated_items:
            menu_items.extend(associated_items)
            print(f"      • {subcat_name}: {len(associated_items)} items")
    
    # Handle unassigned items
    all_items = get_all_food_items(soup)
    unassigned_count = 0
    
    for item_data in all_items:
        if item_data['id'] not in assigned_items:
            menu_items.append({
                "id": item_data['id'],
                "name": item_data['name'],
                "unit_id": unit_id,
                "category": category_name,
                "subcategory": None
            })
            unassigned_count += 1
    
    if unassigned_count > 0:
        print(f"      • (No subcategory): {unassigned_count} items")
    
    total_assigned = len(assigned_items)
    print(f"    Total: {len(menu_items)} items ({total_assigned} with subcategories, {unassigned_count} without)")
    
    return menu_items

def get_nutrition_info(item_id, item_name, unit_id, menu_context=None):
    """Get nutrition information for a specific menu item"""
    nutrition_url = f"{BASE_URL}/NutritionDetail/ShowItemNutritionLabel"
    nutrition_payload = {"detailOid": str(item_id)}
    
    try:
        # If we have menu context, reestablish it to ensure proper session state
        if menu_context and menu_context.get('selected_menu_id'):
            menu_select_url = f"{BASE_URL}/Menu/SelectMenu"
            menu_payload = {"menuOid": menu_context['selected_menu_id']}
            session.post(menu_select_url, data=menu_payload, headers=ajax_headers)
        
        response = session.post(nutrition_url, data=nutrition_payload, headers=ajax_headers)
        
        if response.status_code != 200:
            print(f"Failed to get nutrition for item {item_id}: {response.status_code}")
            return None
        
        if not response.text or len(response.text) < 100:
            print(f"Empty or too short response for item {item_id}")
            return None
        
        # Parse nutrition information
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Get item name from nutrition label (more accurate than menu name)
        header_element = soup.select_one('.cbo_nn_LabelHeader')
        actual_name = clean_text(header_element.text) if header_element else clean_text(item_name)
        
        nutrition_data = {
            "item_id": item_id,
            "item_name": actual_name,
            "unit_id": unit_id,
            "serving_size": "",
            "calories": "",
            "total_fat": "",
            "saturated_fat": "",
            "trans_fat": "",
            "cholesterol": "",
            "sodium": "",
            "total_carb": "",
            "dietary_fiber": "",
            "sugars": "",
            "added_sugars": "0g",  # Default to 0g when not found
            "protein": "",
            "calcium": "",
            "iron": "",
            "potassium": "",
            "ingredients": "",
            "allergens": ""
        }
        
        # Parse serving size
        serving_divs = soup.find_all('div', class_='bold-text inline-div-right')
        for div in serving_divs:
            div_text = clean_text(div.text)
            if 'oz' in div_text or 'g)' in div_text:
                nutrition_data["serving_size"] = div_text
                break
        
        # Parse calories - special structure
        calories_section = soup.find('td', class_='cbo_nn_LabelSubHeader')
        if calories_section:
            calories_right = calories_section.find('div', class_='inline-div-right')
            if calories_right:
                nutrition_data["calories"] = clean_text(calories_right.text)
        
        # Parse nutrition facts from both bordered and non-bordered sub-headers
        nutrition_sections = soup.find_all('div', class_=['cbo_nn_LabelBorderedSubHeader', 'cbo_nn_LabelNoBorderSubHeader'])
        
        for section in nutrition_sections:
            left_div = section.find('div', class_='inline-div-left')
            if not left_div:
                continue
            
            # Check for added sugars special case (different structure)
            if 'addedSugarRow' in left_div.get('class', []):
                span = left_div.find('span')
                if span:
                    added_sugar_text = clean_text(span.text).lower()
                    # Extract "x g" from text like "include 2 g added sugars"
                    import re
                    match = re.search(r'(\d+(?:\.\d+)?)\s*g', added_sugar_text)
                    if match:
                        nutrition_data["added_sugars"] = f"{match.group(1)}g"
                continue
            
            # Get the nutrition label and value for regular nutrients
            spans = left_div.find_all('span')
            if len(spans) >= 2:
                label = clean_text(spans[0].text).lower()
                value = clean_text(spans[1].text)
                
                # Map to our nutrition data fields (case-insensitive)
                if 'total fat' in label:
                    nutrition_data["total_fat"] = value
                elif 'saturated fat' in label:
                    nutrition_data["saturated_fat"] = value
                elif 'trans' in label and 'fat' in label:
                    nutrition_data["trans_fat"] = value
                elif 'cholesterol' in label:
                    nutrition_data["cholesterol"] = value
                elif 'sodium' in label:
                    nutrition_data["sodium"] = value
                elif 'total carbohydrate' in label:
                    nutrition_data["total_carb"] = value
                elif 'dietary fiber' in label:
                    nutrition_data["dietary_fiber"] = value
                elif 'total sugars' in label or 'sugars' in label:
                    nutrition_data["sugars"] = value
                elif 'protein' in label:
                    nutrition_data["protein"] = value
                elif 'calcium' in label:
                    nutrition_data["calcium"] = value
                elif 'iron' in label:
                    nutrition_data["iron"] = value
                elif 'potassium' in label or 'potas' in label:
                    nutrition_data["potassium"] = value
        
        # Parse ingredients - specific structure
        ingredients_bold = soup.find('span', class_='cbo_nn_LabelIngredientsBold')
        if ingredients_bold:
            # Find the next span which contains the actual ingredients
            ingredients_span = ingredients_bold.find_next_sibling('span', class_='cbo_nn_LabelIngredients')
            if ingredients_span:
                nutrition_data["ingredients"] = clean_text(ingredients_span.text)
        
        # Parse allergens - look for the specific allergen structure
        allergens_bold = soup.find('span', class_='cbo_nn_LabelAllergensBold')
        if allergens_bold:
            # Find the next span which contains the actual allergens
            allergens_span = allergens_bold.find_next_sibling('span', class_='cbo_nn_LabelAllergens')
            if allergens_span:
                nutrition_data["allergens"] = clean_text(allergens_span.text)
        
        return nutrition_data
        
    except Exception as e:
        print(f"Error getting nutrition for item {item_id}: {e}")
        return None

def save_csv_data(filename_suffix=""):
    """Save current nutrition data to CSV"""
    global all_nutrition_data, csv_filename, fieldnames
    
    if not all_nutrition_data:
        print("No data to save")
        return
    
    save_filename = csv_filename
    if filename_suffix:
        # Insert suffix before file extension
        name_parts = csv_filename.rsplit('.', 1)
        save_filename = f"{name_parts[0]}_{filename_suffix}.{name_parts[1]}"
    
    print(f"\nSaving {len(all_nutrition_data)} items to {save_filename}")
    
    with open(save_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_nutrition_data)
    
    print(f"Data saved to: {save_filename}")

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print(f"\n\n=== Process interrupted by user (signal {signum}) ===")
    save_csv_data("aborted")
    print("Aborted CSV saved. You can resume scraping later or use this partial data.")
    sys.exit(0)

def scrape_all_nutrition_data():
    """Main scraping function"""
    global all_nutrition_data, csv_filename, fieldnames
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    
    print("=== Starting Duke NetNutrition Scraper ===")
    print("Press Ctrl+C at any time to save an 'aborted' CSV with current progress")
    start_time = datetime.now()
    
    # Setup
    setup_session()
    
    # Get all units/restaurants
    units = get_units()
    if not units:
        print("No units found, exiting")
        return
    
    # Prepare CSV file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"duke_nutrition_data_{timestamp}.csv"
    
    fieldnames = [
        "item_id", "item_name", "unit_id", "unit_name", "category", "subcategory", "serving_size", 
        "calories", "total_fat", "saturated_fat", "trans_fat", "cholesterol", 
        "sodium", "total_carb", "dietary_fiber", "sugars", "added_sugars",
        "protein", "calcium", "iron", "potassium", "ingredients", "allergens", "scraped_at"
    ]
    
    all_nutrition_data = []
    total_items = 0
    
    # Scrape each unit
    for unit in units:
        unit_id = unit["id"]
        unit_name = unit["name"]
        
        print(f"\n--- Processing {unit_name} (ID: {unit_id}) ---")
        
        # Get menu items for this unit
        menu_items = select_unit_and_get_menu(unit_id)
        if not menu_items:
            print(f"No menu items found for {unit_name}")
            continue
        
        # Get nutrition for each menu item
        for i, item in enumerate(menu_items, 1):
            item_id = item["id"]
            item_name = item["name"]
            item_category = item.get("category", "")
            item_subcategory = item.get("subcategory", "")
            
            print(f"  [{i}/{len(menu_items)}] Getting nutrition for: {item_name}")
            if item_subcategory:
                print(f"    Subcategory: {item_subcategory}")
            
            # Prepare menu context for nutrition request
            menu_context = {
                'selected_menu_id': item.get('selected_menu_id'),
                'category_type': item.get('category_type')
            }
            
            nutrition_data = get_nutrition_info(item_id, item_name, unit_id, menu_context)
            if nutrition_data:
                nutrition_data["unit_name"] = unit_name
                nutrition_data["category"] = item_category
                nutrition_data["subcategory"] = item_subcategory
                nutrition_data["scraped_at"] = datetime.now().isoformat()
                all_nutrition_data.append(nutrition_data)
                total_items += 1
                
                # Print progress and save periodically
                if total_items % 10 == 0:
                    print(f"    Progress: {total_items} items scraped so far")
                    # Save progress every 50 items
                    if total_items % 50 == 0:
                        save_csv_data("progress")
                        print(f"    Progress saved to CSV (every 50 items)")
            
            # Rate limiting - be nice to the server
            time.sleep(0.5)  # Wait 500ms between requests
    
    # Save final CSV
    save_csv_data()
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n=== Scraping Complete! ===")
    print(f"Total items scraped: {len(all_nutrition_data)}")
    print(f"Time taken: {duration}")
    print(f"Final data saved to: {csv_filename}")
    if len(all_nutrition_data) > 0:
        print(f"Average time per item: {duration.total_seconds() / len(all_nutrition_data):.2f} seconds")
    else:
        print("No items were scraped - check debugging output above")

if __name__ == "__main__":
    scrape_all_nutrition_data()
