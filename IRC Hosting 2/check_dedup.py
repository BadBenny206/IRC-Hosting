import json

with open('output/json/sec-1.json') as f:
    data = json.load(f)
    sub_a = data['subsections'][0]
    content = sub_a['content']
    
    # Count table-related occurrences
    not_over_count = content.count('Not over')
    table_count = content.count('[TABLE]')
    income_is_count = content.count('If taxable income is')
    
    print(f"Subsection (a) details:")
    print(f"  Content length: {len(content)} chars")
    print(f"  'Not over' count: {not_over_count}")
    print(f"  '[TABLE]' markers: {table_count}")
    print(f"  'If taxable income is' count: {income_is_count}")
    
    # Check for duplication
    if not_over_count == 1 or income_is_count == 1:
        print("\n✓ SUCCESS: Table text appears only once (no duplication)")
    else:
        print(f"\n✗ WARNING: Table text may be duplicated")
    
    # Show first 400 chars
    print(f"\nContent preview:\n{content[:400]}...")
