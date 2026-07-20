import csv

# Read the CSV file and extract first 50 author names and IDs
author_data = []

with open('data/derived_metrics/rising_stars.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        if i >= 50:
            break
        author_data.append({
            'name': row['author_name'],
            'id': row['author_id']
        })

# Write to a text file in "name | id" format
with open('rising_stars_top50.txt', 'w', encoding='utf-8') as f:
    for author in author_data:
        f.write(f"{author['name']} | {author['id']}\n")

print(f'Successfully saved {len(author_data)} author entries to rising_stars_top50.txt')
print('First 10 entries:')
for i, author in enumerate(author_data[:10]):
    print(f'{i+1}. {author["name"]} | {author["id"]}')
