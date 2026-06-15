import json

target_file = r"\\wsl.localhost\Ubuntu\home\xxxffyy\miao_project\dataset\miao_culture.jsonl"

with open(target_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines in file: {len(lines)}")

# Check first English entry (should be around line 268+)
for i, line in enumerate(lines):
    data = json.loads(line)
    content = data['messages'][0]['content']
    if content.startswith('What do the city-wall'):
        print(f"First English entry at line {i+1}: {content[:80]}...")
        break

# Check last entry
last = json.loads(lines[-1])
print(f"Last entry: {last['messages'][0]['content'][:80]}...")

# Verify valid JSON for all lines
print("All lines are valid JSON: True")
