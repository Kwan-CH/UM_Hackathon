import re


def extract_quantity_items(text: str) -> list:
    if not text:
        return []

    text = text.lower()

    results = []

    # -----------------------------
    # PATTERN 1: "20 packs rice", "15 chicken"
    # -----------------------------
    pattern1 = re.findall(r"(\d+)\s*(packs?|pieces?|plates?|boxes?)?\s*([a-zA-Z\s]+)", text)

    for qty, unit, name in pattern1:
        results.append({
            "name": name.strip().title(),
            "quantity": int(qty),
            "unit": unit if unit else "pieces"
        })

    # -----------------------------
    # PATTERN 2: "rice x20", "chicken x15"
    # -----------------------------
    pattern2 = re.findall(r"([a-zA-Z\s]+)\s*x\s*(\d+)", text)

    for name, qty in pattern2:
        results.append({
            "name": name.strip().title(),
            "quantity": int(qty),
            "unit": "pieces"
        })

    # -----------------------------
    # PATTERN 3: fallback numbers only
    # -----------------------------
    if not results:
        numbers = re.findall(r"\d+", text)
        words = re.sub(r"\d+", "", text).split()

        if numbers and words:
            results.append({
                "name": " ".join(words).title(),
                "quantity": int(numbers[0]),
                "unit": "pieces"
            })

    return results