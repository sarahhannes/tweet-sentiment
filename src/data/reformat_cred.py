import codecs
import json
import sys

JSON_OUTPUT = sys.argv[1]

with codecs.open('client_secret.json', 'w', 'utf8') as f:
    f.write(json.dumps(json.loads(JSON_OUTPUT), sort_keys=True, ensure_ascii=False))
