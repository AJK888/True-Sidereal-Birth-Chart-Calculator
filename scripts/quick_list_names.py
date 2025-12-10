import sqlite3

conn = sqlite3.connect('synthesis_astrology.db')
c = conn.cursor()

c.execute('SELECT COUNT(*) FROM famous_people')
count = c.fetchone()[0]

c.execute('SELECT name FROM famous_people ORDER BY name')
names = [r[0] for r in c.fetchall()]

with open('database_names.txt', 'w', encoding='utf-8') as f:
    f.write(f"FAMOUS PEOPLE IN DATABASE: {count} total\n")
    f.write("=" * 70 + "\n\n")
    for i, name in enumerate(names, 1):
        f.write(f"{i}. {name}\n")

print(f"Total: {count} people")
print(f"List saved to: database_names.txt")
print(f"\nFirst 30 names:")
for i, name in enumerate(names[:30], 1):
    print(f"{i}. {name}")

if count > 30:
    print(f"\n... and {count - 30} more (see database_names.txt for full list)")

conn.close()

