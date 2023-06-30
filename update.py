import sqlite3, requests
from lmmy import DataContext

db = DataContext(sqlite3.connect('lmmy.db'))
query = '{ nodes(softwarename: "lemmy") { domain } }'
r = requests.post('https://api.fediverse.observer/', json = { 'query': query })
r.raise_for_status()

expect = { instance['domain'] for instance in r.json()['data']['nodes'] }
actual = db.instances()

for instance in expect.difference(actual):
	db.add_instance(instance)

for instance in actual.difference(expect):
	db.del_instance(instance)

print(f"{len(actual)} -> {len(expect)}")
