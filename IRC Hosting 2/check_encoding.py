f = open('TreasuryRegs_Parser_XML.py', 'rb')
c = f.read()
f.close()
idx = c.find(b'sectno = f')
print('offset', idx)
if idx >= 0:
    print('bytes:', list(c[idx:idx+30]))

# also check section title  
idx2 = c.find(b'reader-heading')
print('reader-heading offset', idx2)
if idx2 >= 0:
    print('bytes:', list(c[idx2:idx2+60]))

# check the literal section symbol
idx3 = c.find(b'\xc2\xa7')  # UTF-8 bytes for §
print('UTF-8 § at offset:', idx3)
# check for double-encoded §
idx4 = c.find(b'\xc3\x82\xc2\xa7')  # double-encoded
print('double-encoded § at offset:', idx4)
