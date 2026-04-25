def classify_food_item(name: str) -> dict:
    name_lower = name.lower()

    # -----------------------
    # TYPE CLASSIFICATION
    # -----------------------
    if any(word in name_lower for word in ["fried", "grilled", "rice", "noodle", "curry", "cook"]):
        food_type = "cooked_meal"
    elif any(word in name_lower for word in ["salad", "vegetable", "fruit", "apple", "banana"]):
        food_type = "raw_food"
    elif any(word in name_lower for word in ["juice", "water", "tea", "coffee", "milk"]):
        food_type = "beverage"
    elif any(word in name_lower for word in ["bread", "bun", "cake", "pastry"]):
        food_type = "baked_food"
    else:
        food_type = "unknown"

    # -----------------------
    # CATEGORY CLASSIFICATION
    # -----------------------
    if any(word in name_lower for word in ["chicken", "beef", "fish", "egg", "meat"]):
        category = "protein"
    elif any(word in name_lower for word in ["rice", "noodle", "bread", "pasta"]):
        category = "grains"
    elif any(word in name_lower for word in ["vegetable", "salad", "spinach", "carrot"]):
        category = "fiber"
    elif any(word in name_lower for word in ["milk", "cheese", "yogurt"]):
        category = "dairy"
    elif any(word in name_lower for word in ["juice", "soda", "tea", "coffee"]):
        category = "beverage"
    else:
        category = "other"

    return {
        "name": name,
        "type": food_type,
        "category": category
    }