from bs4 import BeautifulSoup

# You can load the HTML string directly for testing
with open("egg_bite.html", "r") as file:
    html = file.read()

soup = BeautifulSoup(html, 'lxml')

# Get the item name
item_name = soup.select_one('.cbo_nn_LabelHeader').text.strip()

# Get serving size and calories
serving_info = soup.find('div', class_='cbo_nn_LabelBottomBorderLabel')
serving_size = serving_info.find_all('div')[1].text.strip()

calories_row = soup.find('td', class_='cbo_nn_LabelSubHeader')
calories = calories_row.find('div', class_='inline-div-right').text.strip()

# Get nutrition facts
nutrition_facts = {}
for div in soup.find_all('div', class_='cbo_nn_LabelBorderedSubHeader'):
    spans = div.find_all('span')
    if len(spans) >= 2:
        key = spans[0].text.strip()
        value = spans[1].text.strip()
        nutrition_facts[key] = value

# Ingredients
ingredients = soup.select_one('.cbo_nn_LabelIngredients').text.strip()

# Allergens
allergens = soup.select_one('.cbo_nn_LabelAllergens').text.strip()

# Print it all
print("Item:", item_name)
print("Serving Size:", serving_size)
print("Calories:", calories)
print("Nutrition Facts:")
for k, v in nutrition_facts.items():
    print(f"  {k}: {v}")
print("Ingredients:", ingredients)
print("Allergens:", allergens)
