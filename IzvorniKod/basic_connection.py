from flask import Flask, request
from flask_restful import Api
from flask_cors import CORS
from werkzeug.utils import secure_filename

import psycopg2
import hashlib
from datetime import datetime, timedelta
import uuid
import os
import requests

from classes import Korisnik
import codeshark_config as cfg
import send_mail

app = Flask(__name__)
CORS(app)
api = Api(app)

app.config["UPLOAD_FOLDER"] = "./static"	# Folder must already exist !
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024	# 1 MB

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
	if resp is not None:
		# ignore user ID and token related elements
		resp = resp[1:-3] 
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
	return user.check_activated(cursor)
	

@app.route('/login', methods=['POST'])
def login():

	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method != 'POST':
			return {"error": "not POST request"}, 400

		data = request.json

		user = get_user(cursor, data["korisnickoime"])
		if user is None:
			return {"error": "user doesn't exist or wrong username"}, 400

		cursor.execute("""SELECT * from korisnik WHERE korisnickoime = %s AND lozinka = %s""", (user.korisnicko_ime,  hash_password(data["lozinka"]),))
		db_response = cursor.fetchone()

		if db_response is None:
			return {"error": "wrong password"}, 400

		#check if user is validated
		verified = check_verified(user, cursor)
		if not verified:
			return {"error": "User is not activated"}, 400
		
		return {"data": "successfully logged in"}, 200


@app.route('/validate/<token>', methods=['GET'])
def validate(token):
	conn, cursor = connect_to_db()
	with conn, cursor:
		token_timestamp = get_token_time(cursor, token)
		if token_timestamp is None:
			return {"error": "Token invalid"}, 200

		current_time = datetime.now()

		if current_time - timedelta(hours=1) <= token_timestamp <= current_time:
			set_activated(cursor, token)
			conn.commit()
			return {"data": "Successfully validated user"}, 200
		
		return {"error": "Token expired"}, 200
		

@app.route('/register', methods=['POST'])
def register():
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method != 'POST':
			return {"error": "not POST request"}, 400

		data = request.json

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

		# Sending verification mail
		send_mail.send_verification_mail(user.ime, user.prezime, user.email, token)

		# Profile pic
		fname = f"pfp_{user.korisnicko_ime}"
		fpath = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(fname))
		try:
			# Accept image from form
			if "file" in request.files:
				file = request.files["file"]
				if file.filename != "":
					file.save(f"{fpath}.{file.filename.split('.')[-1]}")
					
					return {"data": "successfully registered user"}, 200

		except Exception as e:
			pass

		try:
			# Generate a random profile pic
			resp = requests.get(f"https://avatars.dicebear.com/api/jdenticon/{fname}.svg")
			with open(f"{fpath}.svg", "wb") as fp:
				fp.write(resp.content)

			return {"data": "successfully registered user"}, 200

		except Exception as e:
			return {"data": "successfully registered user but no image"}, 200

		#testing user printing 
		#output = user.calc_successfully_solved(cursor)
		# for attr in dir(user):
		# 	print("obj.%s = %r" % (attr, getattr(user, attr)))


if __name__  == "__main__":
	cfg.load_config()
	app.run(host='0.0.0.0', debug=False, ssl_context=('/etc/letsencrypt/live/sigma.domefan.club/fullchain.pem','/etc/letsencrypt/live/sigma.domefan.club/privkey.pem'))
