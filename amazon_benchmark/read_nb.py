import json

path = r'C:/Users/MSI/.gemini/antigravity/brain/3a10b1ef-fe22-4faf-ac5d-53c8d1ad0d76/.user_uploaded/media_1793847429154_71578c8a.ipynb'
with open(path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

with open('amazon_benchmark/notebook_content.txt', 'w', encoding='utf-8') as f:
    for i, c in enumerate(nb['cells']):
        f.write(f"=== Cell {i} [{c.get('cell_type')}] ===\n")
        f.write(''.join(c.get('source', [])))
        f.write("\n\n")

print("Done dumping notebook content.")

