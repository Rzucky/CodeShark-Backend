from flask import Flask, request
from flask_cors import CORS
from werkzeug.utils import secure_filename

import psycopg2 # apt-get install libpq-dev
import hashlib
from datetime import datetime, timedelta
import uuid
import os
import requests

from classes import Korisnik
import codeshark_config as cfg
import send_mail

cfg.load_config()

debug_main = cfg.get_config("debug_main")
debug_ssl  = cfg.get_config("debug_ssl")
debug_mail = cfg.get_config("debug_mail")

app = Flask(__name__)
CORS(app)


app.config["UPLOAD_FOLDER"] = cfg.get_config("img_upload_dir")	# Folder must already exist !
app.config["MAX_CONTENT_LENGTH"] = cfg.get_config("max_content_length")	# bytes [=1 MB]

def connect_to_db():
	conn = psycopg2.connect(database	= cfg.get_config("postgres_name"),
							host		= cfg.get_config("postgres_host"),
							user		= cfg.get_config("postgres_user"),
							password	= cfg.get_config("postgres_pass"))
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

def hash_pfp_filename(username):
	return hashlib.md5(username.encode('utf-8')).hexdigest()

def get_token_time(cursor, token):
	cursor.execute("""SELECT tokengeneriran FROM korisnik WHERE token = %s;""", (token,))
	token_timestamp = cursor.fetchone()
	if token_timestamp is not None:
		return token_timestamp[0]

	return None

def set_activated(cursor, token):
	# Activating user
	cursor.execute("""UPDATE korisnik SET aktivan = %s WHERE token = %s;""", (True, token,))
	# Removing token from db
	cursor.execute("""UPDATE korisnik SET token = %s, tokengeneriran = %s WHERE token = %s;""", (None, None, token,))


def check_verified(user, cursor):
	return user.check_activated(cursor)


@app.route('/avatar/<username>', methods=['GET'])
def avatar(username):
	conn, cursor = connect_to_db()
	with conn, cursor:
		cursor.execute("""SELECT slikaprofila FROM korisnik WHERE korisnickoime = %s;""", (username,))
		profile_pic_url = cursor.fetchone()
		if profile_pic_url is not None:
			return {"url": f"{profile_pic_url[0]}"}, 200

		return {"error" : "No profile picture available"}, 404


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
			return {"error": "User is not activated"}, 401

		return {"data": "successfully logged in"}, 200


@app.route('/validate/<token>', methods=['GET'])
def validate(token):
	conn, cursor = connect_to_db()
	with conn, cursor:
		token_timestamp = get_token_time(cursor, token)
		if token_timestamp is None:
			return {"error": "Token invalid"}, 400

		current_time = datetime.now()

		if current_time - timedelta(hours=1) <= token_timestamp <= current_time:
			set_activated(cursor, token)
			conn.commit()
			return {"data": "Successfully validated user"}, 200
		
		return {"error": "Token expired"}, 401


@app.route('/register', methods=['POST'])
def register():
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method != 'POST':
			return {"error": "not POST request"}, 400

		file_ext = None

		#data = request.get_json(force=True)
		data = dict(request.form)
		print(data)
		# default value
		if data["titula"] == "":
			data["titula"] = 'amater'

		user = Korisnik(data["korisnickoime"],
						hash_password(data["lozinka"]),
						f"pfp_{hash_pfp_filename(data['korisnickoime'])}",
						data["ime"],
						data["prezime"],
						data["email"],
						data["titula"],
						data["nivouprava"])

		user_existance, error = check_if_user_exists(cursor, user.korisnicko_ime, user.email)
		if user_existance:
			return {"error": error}, 400

		# Profile pic
		fpath = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(user.slika_profila))
		try:
			# Accept image from form
			if "slikaprofila" in request.files:
				file = request.files["slikaprofila"]
				if file.filename != "":
					file_ext = file.filename.split('.')[-1]
					file.save(f"{fpath}.{file_ext}")

					#return {"data": "successfully registered user"}, 200

		except Exception as e:
			pass

		if file_ext is None:
			try:
				# Generate a random profile pic
				resp = requests.get(f'https://avatars.dicebear.com/api/jdenticon/{data["slikaprofila"]}.svg')
				with open(f"{fpath}.svg", "wb") as fp:
					fp.write(resp.content)

				file_ext = "svg"
				#return {"data": "successfully registered user"}, 200

			except Exception as e:
				#return {"data": "successfully registered user but no image"}, 200
				pass


		# Update DB
		user.slika_profila = f"{user.slika_profila}.{file_ext}"
		current_time = datetime.now()
		token = (uuid.uuid4().hex)[:16]

		cursor.execute("""INSERT INTO korisnik
									(korisnickoime, slikaprofila, lozinka, ime, prezime, email, titula, nivouprava, token, tokengeneriran)
						VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);""",
						(user.korisnicko_ime, user.slika_profila, user.lozinka, user.ime, user.prezime, user.email, user.titula, user.nivou_prava, token, current_time))
		user.set_unactivated()
		conn.commit()

		# Sending verification mail
		if not debug_mail:
			print('aaaaaaaaaaaaa tu sam')
			send_mail.send_verification_mail(user.ime, user.prezime, user.email, token)
			print('aaaaaaaaaaaaa tu sam izaso')


		if file_ext is None:
			return {"data": "successfully registered user but no image"}, 200
		else:
			return {"data": "successfully registered user"}, 200

		#testing user printing 
		# output = user.calc_successfully_solved(cursor)
		# for attr in dir(user):
		# 	print("obj.%s = %r" % (attr, getattr(user, attr)))


if __name__  == "__main__":
	flask_config = {
		"host": cfg.get_config("flask_host"),
		"port": cfg.get_config("flask_port"),
		"debug": debug_main,
	}

	if not debug_ssl:
		flask_config["ssl_context"] = (cfg.get_config("certfile"), cfg.get_config("keyfile"))

	app.run(**flask_config)
	