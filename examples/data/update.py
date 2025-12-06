import json

with open('new_obama_reading.txt', 'r', encoding='utf-8') as f:
    new_reading = f.read()

with open('barack-obama.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

data['ai_reading'] = new_reading

with open('barack-obama.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('Updated successfully')

