# Author: Shivam Raj (@BetterCallShiv)

import random
import re

def generate_card_data(grid_size=5):
    max_num = grid_size * grid_size
    numbers = list(range(1, max_num + 1))
    random.shuffle(numbers)
    card = []
    for i in range(0, max_num, grid_size):
        card.append(numbers[i:i+grid_size])
    return card


def parse_custom_grid(text, grid_size=5):
    max_num = grid_size * grid_size
    numbers = re.findall(r'\b\d+\b', text)
    numbers = [int(n) for n in numbers]
    if len(numbers) != max_num:
        return None
    if any(n < 1 or n > max_num for n in numbers):
        return None
    if len(set(numbers)) != max_num:
        return None
    grid = []
    for i in range(0, max_num, grid_size):
        grid.append(numbers[i:i+grid_size])
    return grid


def check_win_condition(card_data, marked_indices, grid_size=5):
    line_count = 0
    patterns = []
    for r in range(grid_size):
        if all((r, c) in marked_indices for c in range(grid_size)):
            line_count += 1
            patterns.append(f"Row {r+1}")
    for c in range(grid_size):
        if all((r, c) in marked_indices for r in range(grid_size)):
            line_count += 1
            patterns.append(f"Column {c+1}")
    if all((i, i) in marked_indices for i in range(grid_size)):
        line_count += 1
        patterns.append("Main Diagonal")
    if all((i, (grid_size - 1) - i) in marked_indices for i in range(grid_size)):
        line_count += 1
        patterns.append("Anti-Diagonal")
    return line_count, patterns


def format_cell_text(value, is_marked):
    text = str(value)
    if is_marked:
        return f"{text} ✅"
    return text
