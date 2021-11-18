from flask import Flask, request
from flask_restful import Api
from flask_cors import CORS

import psycopg2
import hashlib
from datetime import datetime, timezone, timedelta
import uuid

from classes import Korisnik
import codeshark_config as cfg

app = Flask(__name__)
CORS(app)
api = Api(app)


def connect_to_db():
	conn = psycopg2.connect(host		= cfg.get_config("host"),
							database	= cfg.get_config("database"),
							user		= cfg.get_config("user"),
							password	= cfg.get_config("password"))
	cursor = conn.cursor()
	return conn, cursor

# checking for taken username and email
def check_if_user_exists(cursor, username, email):
	cursor.execute("SELECT * FROM korisnik WHERE email = %s;", (email,))
	db_response = cursor.fetchone()
	if db_response is not None:
		return True, "email already in use"

	cursor.execute("SELECT * FROM korisnik WHERE korisnickoIme = %s;", (username,))
	db_response = cursor.fetchone()
	if db_response is not None:
		return True, "username taken"

	return False, None


def get_user(cursor, korisnickoime):
	cursor.execute("SELECT * FROM korisnik WHERE korisnickoime = %s;", (korisnickoime,))
	resp = cursor.fetchone()
	print(resp)
	if resp is not None:
		# ignore user ID and token related elements
		resp = resp[1:-3] 
		print(resp)

		# remove token and token timestamp from tuple 	
		# resp_list = list(resp)
		# del resp_list[-2]
		# del resp_list[-2]
		# resp = tuple(resp_list)

		user = Korisnik(*resp)
		return user
	return None

def hash_password(plainpass):
	return hashlib.sha256(plainpass.encode('utf-8')).hexdigest()

def get_token_time(cursor, token):
	cursor.execute("""SELECT tokengeneriran FROM korisnik WHERE token = %s;""", (token,))
	token_timestamp = cursor.fetchone()
	if token_timestamp is not None:
		return token_timestamp[0]
	return None

def set_activated(cursor, token):
	cursor.execute("""UPDATE korisnik SET aktivan = %s WHERE token = %s;""", (True, token,))

def check_verified(user, cursor):

	verified = user.check_activated(cursor)

	return verified

@app.route('/login', methods=['POST'])
def login():

	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method == 'POST':
			data = request.json

			user = get_user(cursor, data["korisnickoime"])
			if user is None:
				return {"error": "user doesn't exist or wrong username"}, 400
			for attr in dir(user):
				print("obj.%s = %r" % (attr, getattr(user, attr)))
			
			#user_existance = check_if_user_exists(cursor, user.korisnicko_ime, user.email)
			#if user_existance:
			cursor.execute("""SELECT * from korisnik WHERE korisnickoime = %s AND lozinka = %s""", (user.korisnicko_ime,  hash_password(data["lozinka"]),))
			db_response = cursor.fetchone()

			if db_response is not None:

				#check if user is validated
				verified = check_verified(user, cursor)
				if not verified:
					return {"error": "User is not activated"}, 400
				
				return {"data": "successfully logged in"}, 200

			return {"error": "wrong password"}, 400

			#return {"error": "user doesn't exist or wrong username"}, 400

		return {"error": "not POST requst"}, 400


@app.route('/validate/<token>', methods=['GET'])
def validate(token):
	print(token)
	conn, cursor = connect_to_db()
	with conn, cursor:
		token_timestamp = get_token_time(cursor, token)
		print(token_timestamp)
		if token_timestamp is None:
			return {"error": "Token invalid"}, 200

		current_time = datetime.now()
		print(f"current_time: {current_time}")

		if current_time - timedelta(hours=1) <= token_timestamp <= current_time:
			set_activated(cursor, token)
			conn.commit()
			return {"data": "Successfully validated user"}, 200
		
		return {"error": "Token expired"}, 200
		

		# user = get_user(cursor, data["korisnickoime"])
		# if user is None:
		# 	return {"error": "user doesn't exist or wrong username"}, 400
		



@app.route('/register', methods=['POST'])
def register():
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method == 'POST':
			data = request.json
			print(data)

			user = Korisnik(data["korisnickoime"], hash_password(data["lozinka"]), data["slikaprofila"], data["ime"], data["prezime"], data["email"], data["titula"], data["nivouprava"])

			user_existance, error = check_if_user_exists(cursor, user.korisnicko_ime, user.email)
			if user_existance:
				return {"error": error}, 400

			current_time = datetime.now()
			token = (uuid.uuid4().hex)[:16]

			cursor.execute("""INSERT INTO korisnik
										(korisnickoime, slikaprofila, lozinka, ime, prezime, email, titula, nivouprava, token, tokengeneriran)
							VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);""",
							(user.korisnicko_ime, user.slika_profila, user.lozinka, user.ime, user.prezime, user.email, user.titula, user.nivou_prava, token, current_time))
			user.set_unactivated()
			conn.commit()
			
			#testing user printing 
			#user.set_unactivated(cursor, token, current_time)
			#output = user.calc_successfully_solved(cursor)
			# for attr in dir(user):
			# 	print("obj.%s = %r" % (attr, getattr(user, attr)))

			return {"data": "successfully registered user"}, 200

		else:
			return {"error": "not POST requst"}, 400

if __name__  == "__main__":
	cfg.load_config()
	app.run(host='0.0.0.0', debug=False,ssl_context=('/etc/letsencrypt/live/sigma.domefan.club/fullchain.pem','/etc/letsencrypt/live/sigma.domefan.club/privkey.pem'))
