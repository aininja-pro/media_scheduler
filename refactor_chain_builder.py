#!/usr/bin/env python3
"""
Script to refactor ChainBuilder.jsx from 3-column to vertical stack layout.

Changes:
1. Main wrapper: flex h-full -> flex flex-col space-y-6 p-6
2. Order: Calendar (top) -> Chain Cards (middle) -> Parameters (bottom)
3. Parameters: w-80 vertical -> grid-cols-3 horizontal
4. Chain cards: grid-cols-5 large cards -> compact 180px x 100px, 5 per row
"""

def refactor_chain_builder():
    file_path = '/Users/richardrierson/Desktop/Projects/media_scheduler/frontend/src/pages/ChainBuilder.jsx'

    with open(file_path, 'r') as f:
        lines = f.readlines()

    # Find key line numbers
    main_content_start = None
    left_panel_start = None
    left_panel_end = None
    center_panel_start = None
    center_panel_end = None
    right_panel_start = None
    right_panel_end = None
    main_content_end = None

    for i, line in enumerate(lines):
        if '{/* Main Content */}' in line:
            main_content_start = i
        elif '{/* Left Panel - Chain Parameters */}' in line:
            left_panel_start = i
        elif '{/* Center Panel - Chain Preview */}' in line:
            center_panel_start = i
            # The left panel ends just before center starts
            if left_panel_end is None:
                left_panel_end = i - 1
        elif '{/* Right Panel - Info */}' in line:
            right_panel_start = i
            # Center panel ends just before right starts
            if center_panel_end is None:
                center_panel_end = i - 1

    # Find where main content div closes (should be near end)
    # Look for closing divs near the end
    for i in range(len(lines) - 1, 0, -1):
        if '</div>' in lines[i] and i > right_panel_start + 100:
            if main_content_end is None:
                main_content_end = i
                break

    print(f"Main Content Start: Line {main_content_start + 1}")
    print(f"Left Panel (Parameters): Lines {left_panel_start + 1} - {left_panel_end + 1}")
    print(f"Center Panel (Timeline): Lines {center_panel_start + 1} - {center_panel_end + 1}")
    print(f"Right Panel (Info): Lines {right_panel_start + 1} - {right_panel_end if right_panel_end else 'finding...'}")
    print(f"Main Content End: Line {main_content_end + 1 if main_content_end else 'finding...'}")

    # Extract sections
    parameters_section = lines[left_panel_start:left_panel_end + 1]
    timeline_section = lines[center_panel_start:center_panel_end + 1]

    print(f"\nParameters section: {len(parameters_section)} lines")
    print(f"Timeline section: {len(timeline_section)} lines")

    # Show first few lines of each section for verification
    print("\n--- Parameters Section (first 5 lines) ---")
    for line in parameters_section[:5]:
        print(line.rstrip())

    print("\n--- Timeline Section (first 5 lines) ---")
    for line in timeline_section[:5]:
        print(line.rstrip())

if __name__ == '__main__':
    refactor_chain_builder()
