import asyncio
import sqlite3

import tornado.web, tornado.locale, tornado.httpclient
from tornado.httputil import url_concat

class DataContext:
	__slots__ = 'db',

	def __init__(self, db):
		self.db = db

	def instances(self):
		return { instance[0] for instance in self.db.execute('''
				SELECT "domain"
				  FROM "instances"''').fetchall() }

	def has_instance(self, domain):
		return self.db.execute('''
			SELECT 1
			  FROM "instances"
			 WHERE "domain" = ?
			 LIMIT 1''', (domain,)).fetchone() is not None

	def add_instance(self, domain):
		self.db.execute('''
			INSERT
			  INTO "instances" ( "domain" )
			VALUES ( ? )''', (domain,))
		self.db.commit()

	def del_instance(self, domain):
		self.db.execute('''
			DELETE
			  FROM "communities"
			 WHERE "instance_id" IN (SELECT "id" 
			                           FROM "instances"
			                          WHERE "domain" = ?)''', (domain,))
		self.db.execute('''
			DELETE
			  FROM "communities"
			 WHERE "domain_id" IN (SELECT "id" 
			                         FROM "instances"
			                        WHERE "domain" = ?)''', (domain,))
		self.db.execute('''
			DELETE
			  FROM "instances"
			 WHERE "domain" = ?''', (domain,))
		self.db.commit()

	def has_community(self, instance, name, domain):
		return self.db.execute('''
			SELECT 1
			  FROM "communities" AS "c"
			 INNER JOIN "instances" AS "i"
			    ON "c"."instance_id" = "i"."id"
			 INNER JOIN "instances" AS "d"
			    ON "c"."domain_id" = "d"."id"
			 WHERE "i"."domain" = ?
			   AND "c"."name" = ?
			   AND "d"."domain" = ?
			 LIMIT 1''', (instance, name, domain)).fetchone() is not None

	def add_community(self, instance, name, domain):
		self.db.execute('''
			INSERT
			  INTO "communities" ( "instance_id"
			                     , "domain_id"
			                     , "name" )
			VALUES ( (SELECT "id"
			            FROM "instances"
			           WHERE "domain" = ?)
			       , (SELECT "id"
			            FROM "instances"
			           WHERE "domain" = ?)
			       , ? )''', (instance, domain, name))
		self.db.commit()


class RequestHandler(tornado.web.RequestHandler):
	__slots__ = 'db',

	def __init__(self, app, req, db):
		super().__init__(app, req)
		self.db = db


class WelcomeHandler(RequestHandler):
	async def get(self):
		to = self.get_query_argument('to')
		await self.render('welcome.html', to = to)

	async def post(self):
		to = self.get_query_argument('to')
		if not to.startswith('/c'):
			return self.redirect(f"/err")

		instance = self.get_body_argument('instance')
		if not self.db.has_instance(instance):
			return self.redirect(f"/err")

		self.set_cookie('instance', instance, expires_days = 365)
		return self.redirect(to)


class CommunityHandler(RequestHandler):
	async def get(self, name, domain):
		if not self.db.has_instance(domain):
			return self.redirect(f"/err")

		if (instance := self.get_cookie('instance')) is None:
			return self.redirect(url_concat('/welcome', { 'to': f"/c/{name}@{domain}" }))

		if not self.db.has_instance(instance):
			return self.redirect(f"/err")

		if domain == instance:
			return self.redirect(f"https://{instance}/c/{name}")

		if not self.db.has_community(instance, name, domain):
			http = tornado.httpclient.AsyncHTTPClient()
			try:
				req = await http.fetch(f"https://{instance}/api/v3/community?name={name}@{domain}",
				    headers = { 'Accept': 'application/json'})
			except:
				has = False
			else:
				has = req.code == 200

			if has:
				self.db.add_community(instance, name, domain)
			else:
				return self.redirect(f"https://{instance}/search/q/!{name}%40{domain}" +
				    "/type/All/sort/TopAll/listing_type/All/community_id/0/creator_id/0/page/1")

		return self.redirect(f"https://{instance}/c/{name}@{domain}")


class ErrorHandler(RequestHandler):
	async def get(self):
		await self.render('error.html')


async def main():
	tornado.locale.load_translations('lang')
	db = DataContext(sqlite3.connect('lmmy.db'))
	app = tornado.web.Application([
		(r"/", tornado.web.RedirectHandler, { 'url': 'https://join-lemmy.org/' }),
		(r"/welcome", WelcomeHandler, { 'db': db }),
		(r"/c/([\w.]+)@([a-zA-Z0-9._:-]+)", CommunityHandler, { 'db': db }),
		(r"/error", ErrorHandler, { 'db': db })
	])
	app.listen(8888)
	await asyncio.Event().wait()

if __name__ == '__main__':
	asyncio.run(main())
