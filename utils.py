# Author: Shivam Raj (@BetterCallShiv)

import random
import re

def generate_card_data():
    numbers = list(range(1, 26))
    random.shuffle(numbers)
    card = []
    for i in range(0, 25, 5):
        card.append(numbers[i:i+5])
    return card


def parse_custom_grid(text):
    numbers = re.findall(r'\b\d+\b', text)
    numbers = [int(n) for n in numbers]
    if len(numbers) != 25:
        return None
    if any(n < 1 or n > 25 for n in numbers):
        return None
    if len(set(numbers)) != 25:
        return None
    grid = []
    for i in range(0, 25, 5):
        grid.append(numbers[i:i+5])
    return grid


def check_win_condition(card_data, marked_indices):
    line_count = 0
    patterns = []
    for r in range(5):
        if all((r, c) in marked_indices for c in range(5)):
            line_count += 1
            patterns.append(f"Row {r+1}")
    for c in range(5):
        if all((r, c) in marked_indices for r in range(5)):
            line_count += 1
            patterns.append(f"Column {c+1}")
    if all((i, i) in marked_indices for i in range(5)):
        line_count += 1
        patterns.append("Main Diagonal")
    if all((i, 4 - i) in marked_indices for i in range(5)):
        line_count += 1
        patterns.append("Anti-Diagonal")
    return line_count, patterns


def format_cell_text(value, is_marked):
    text = str(value)
    if is_marked:
        return f"{text} ✅"
    return text
