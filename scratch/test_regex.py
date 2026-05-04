import re

regex = re.compile(r"not\s+rec[ei]{2}ved", re.IGNORECASE)
print(f"Correct: {regex.search('not received')}")
print(f"Typo: {regex.search('not recieved')}")
