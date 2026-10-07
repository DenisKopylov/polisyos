from pathlib import Path
import copy, hashlib, json

P = Path(__file__).parent

def validate(index):
    assert index['total_files'] == len(index['files'])
    assert index['total_bytes'] == sum(row['size_bytes'] for row in index['files'])
    for row in index['files']:
        data = (P / row['path']).read_bytes()
        assert len(data) == row['size_bytes'], row['path'] + ' size'
        assert hashlib.sha256(data).hexdigest() == row['sha256'], row['path'] + ' hash'

index = json.loads((P/'copy-index.json').read_text())
validate(index)
negatives=[]
for field,value in [('size_bytes',-1),('sha256','0'*64)]:
    corrupt=copy.deepcopy(index); corrupt['files'][0][field]=value
    try: validate(corrupt)
    except AssertionError: negatives.append({'corrupt_field':field,'outcome':'REJECTED'})
    else: raise AssertionError('corrupt deciding receipt admitted')
print(json.dumps({'validated_files':len(index['files']),'negative_controls':negatives,'outcome':'PASS'},indent=2))
