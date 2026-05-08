from dotenv import load_dotenv
load_dotenv('token.env')
from data import q

print('=== All regions, province count, and rows-with-default-type count ===')
df = q('''
    SELECT
      "Reg. name" AS region,
      COUNT(DISTINCT "Prov. name") AS provinces,
      SUM(CASE WHEN Type = 'Residential housing' THEN 1 ELSE 0 END) AS rh_rows,
      COUNT(*) AS total_rows
    FROM omi
    GROUP BY "Reg. name"
    ORDER BY "Reg. name"
''')
print(df.to_string())

print()
print('=== Distinct types in dataset ===')
df2 = q('SELECT DISTINCT Type FROM omi ORDER BY Type')
print(df2.to_string())

print()
print('=== Regions where province list is empty/null ===')
df3 = q('''
    SELECT "Reg. name", COUNT(*) AS rows_with_null_prov
    FROM omi
    WHERE "Prov. name" IS NULL OR "Prov. name" = ''
    GROUP BY "Reg. name"
''')
print(df3.to_string())

print()
print('=== Sample of region names with raw bytes (looking for whitespace/odd chars) ===')
df4 = q('''
    SELECT DISTINCT "Reg. name", LENGTH("Reg. name") AS len
    FROM omi
    ORDER BY "Reg. name"
''')
print(df4.to_string())
