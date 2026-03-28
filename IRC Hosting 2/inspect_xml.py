content = open('IRC/usc26.xml', encoding='utf-8').read()
idx = content.find('identifier="/us/usc/t26/s1"')
print(content[idx:idx+4000])
