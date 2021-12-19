from flask import Flask, request
from flask_cors import CORS
from werkzeug.utils import secure_filename

from datetime import datetime, timedelta
import os
import psycopg2 # apt-get install libpq-dev
import requests
import uuid
import subprocess as subp
import shlex

from classes import Korisnik, Trofej, VirtualnoNatjecanje, Zadatak, UploadRjesenja
import codeshark_config as cfg
import send_mail

cfg.load_config()

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


def user_trophies(user, cursor):
	trophies_list = []

	cursor.execute("""SELECT trofejid, imetrofeja, slikatrofeja 
					FROM jeosvojio NATURAL JOIN trofej natural join korisnik 
					WHERE jeosvojio.korisnikid = korisnik.korisnikid and korisnickoime =  %s;""", (user.korisnicko_ime,))
	trophies = cursor.fetchall()

	for trophy in trophies:
		trofej = Trofej(*trophy)
		trophies_list.append(trofej)

	return trophies_list

@app.route('/user/<username>', methods=['GET'])
def user():
	## ?? 
	pass


@app.route('/users', methods=['GET'])
def users():
	conn, cursor = connect_to_db()
	with conn, cursor:
		user_list = Korisnik.get_users_asc(cursor)
		return {"users": user_list}, 200


@app.route('/virtual_competition', methods=['GET', 'POST'])
def virtual_competition():
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method == 'POST':
			data = request.json
			virt = VirtualnoNatjecanje.create_virt_competition(conn, cursor, data["broj"], data["korisnickoime"])
			
			return {"popis_zadataka": f"{virt.zadaci}",
					"natjecanje_id":f"{virt.natjecanje_id}"
					}, 201

		elif request.method == 'GET':
			## LOAD AN ALREADY CREATED VIRTUAL COMPETITION
			pass


@app.route('/avatar/<username>', methods=['GET'])
def avatar(username):
	conn, cursor = connect_to_db()
	with conn, cursor:
		cursor.execute("""SELECT slikaprofila FROM korisnik WHERE korisnickoime = %s;""", (username,))
		profile_pic_url = cursor.fetchone()
		if profile_pic_url is not None:
			return {"url": f"{profile_pic_url[0]}"}, 200

		return {"error" : "No profile picture available"}, 404

@app.route('/task/<taskid>', methods=['GET', 'POST'])
def task(taskid):
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method == 'GET':
			zad, error = Zadatak.get_task(taskid, cursor)
			if zad is None:
				return {"error": error}, 403

			author_name, author_lastname = Zadatak.get_author_name(zad.autor_id, cursor)
			
			return{
				"ime_zadatka":				f"{zad.ime_zadatka}",
				"tezina":					f"{zad.bodovi}",
				"max_vrijeme_izvrsavanja":	f"{zad.max_vrijeme_izvrsavanja}",
				"tekst_zadatka":			f"{zad.tekst_zadatka}",
				"slag":						f"{zad.slag}",
				"ime_prezime_autora":		f"{author_name} {author_lastname}"
				}, 200
					

		elif request.method == 'POST':
			data = request.json

			user = get_user(cursor, data["korisnickoime"])
			# can this happen? wrong request?
			if user is None:
				return {"error": "user doesn't exist or wrong username"}, 400
			pass

@app.route('/tasks', methods=['GET'])
def tasks():
	conn, cursor = connect_to_db()
	with conn, cursor:
		task_list = []
		task_list_instances = Zadatak.get_all_public_tasks(cursor)
		for task in task_list_instances:
			task_list.append({
				"task_id": f"{task.zadatak_id}",
				"name": f"{task.ime_zadatka}",
				"tezina": 	f"{task.bodovi}"
			})
		return {"tasks": task_list}, 200

@app.route('/execute_task', methods=['POST'])
def execute_task():
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method == 'POST':
			data = request.json

			#rjesenje = UploadRjesenja()
			taskid = data["zadatakid"]
			user = data["korisnickoime"]
			lang = data["lang"]
			code = data["code"] # Length ?

	# TODO: Move to config
			solutions_dir = f"/var/www/sigma.domefan.club/code_uploads"
			solution_filename = f"{user}_{time.time()}"
			solution_path = f"{solutions_dir}/{solution_filename}"
			with open(solution_path, "w") as fp:
				fp.write(code)

			user_account_name = f"korisnik"
			compile_timeout = 10 # seconds

			# Prepare program for each language
			if lang in ["py3"]:
				command = f"sudo -u {user_account_name} python3 {solution_path}"

			elif lang in ["c++"]:
				# Compile
				cpp_std = "c++11"
				command = f"sudo -u {user_account_name} g++ {solution_path} -o {solution_path}.out -std={cpp_std}"
				solution_path += ".out"

				try:
					proc = subp.run(shlex.split(command), stdout=subp.PIPE, check=True, timeout=compile_timeout)
				except subp.CalledProcessError:
					return {
								"error": "compile error",
								"compiler_output": proc.stdout,
							}, 400
				except subp.TimeoutExpired:
					return {
								"error": "compile timeout",
								"compiler_output": "",
							}, 400

				# Set permissions
				try:
					proc = subp.run(shlex.split(f"sudo -u chmod 755 {solution_path}"), check=True)
				except subp.CalledProcessError:
					return {"error": "chmod error"}, 500 # ?


				command = f"sudo -u {user_account_name} {solution_path}"

			elif lang in ["c"]:
				# Compile
				c_std = "c11"
				command = f"sudo -u {user_account_name} gcc {solution_path} -o {solution_path}.out -std={c_std}"
				solution_path += ".out"

				try:
					proc = subp.run(shlex.split(command), stdout=subp.PIPE, check=True, timeout=compile_timeout)

				except subp.CalledProcessError:
					return {
								"error": "compile error",
								"compiler_output": proc.stdout,
							}, 400

				except subp.TimeoutExpired:
					return {
								"error": "compile timeout",
								"compiler_output": "",
							}, 400

				# Set permissions
				try:
					proc = subp.run(shlex.split(f"sudo -u chmod 755 {solution_path}"), check=True)
				except subp.CalledProcessError:
					return {"error": "chmod error"}, 500 # ?


				command = f"sudo -u {user_account_name} {solution_path}"

			else:
				return {"error": "unsupported language"}, 400

			# Watch out for large amounts of tests
			command = shlex.split(command)

			zad = Zadatak.get_task(taskid, cursor)
			cursor.execute("""SELECT * FROM testprimjeri WHERE zadatakid = %s""", (taskid,))
			tests = cursor.fetchall()

			total = len(tests)
			passed = 0
			results = {}

			for i, test in enumerate(tests):
				proc = subp.Popen(command, stdin=subp.PIPE, stdout=subp.PIPE) # TODO: log executions

				try:
					start_time = time.time()
					output = progpipe.communicate(input=test[0].encode(encoding='utf-8'),
													timeout=zad.max_vrijeme_izvrsavanja)[0] # Data is also buffered in memory !
					elapsed = time.time() - start_time

					output = output.decode(encoding='utf-8').strip() # Or whatever is required
					if test[1] == output:
						results[i] = {"passed": True, "description": "correct answer"}
						passed += 1
					else:
						results[i] = {"passed": False, "description": "wrong answer"}

				except subp.TimeoutExpired:
					proc.kill()
					results[i] = {"passed": False, "description": "timeout"}

			return {
						"result": f"{passed}/total",
						"tests": results,
					}, 200


@app.route('/profile', methods=['POST'])
def profile():
	conn, cursor = connect_to_db()
	with conn, cursor:
		data = request.json

		user = get_user(cursor, data["korisnickoime"])
		if user is None:
			return {"error": "user doesn't exist or wrong username"}, 400
	
		trophies_list = []
		trophies_list_instances = user_trophies(user, cursor)
		for trophy in trophies_list_instances:
			trophies_list.append({
				"name": f"{trophy.ime_trofeja}",
				"img": 	f"{trophy.slika_trofeja}"
			})

		correctly_solved = user.calc_successfully_solved(cursor)

		return {"ime": user.ime,
				"prezime": user.prezime,
				"slikaprofila_url": user.slika_profila,
				"trophies": trophies_list,
				"titula": user.titula,
				"pokusano_zad": user.attempted,
				"uspjesno_zad": user.solved,
				"postotak_uspjesnih": correctly_solved
				}, 200
		

@app.route('/login', methods=['POST'])
def login():

	conn, cursor = connect_to_db()
	with conn, cursor:
		data = request.json

		user = get_user(cursor, data["korisnickoime"])
		if user is None:
			return {"error": "user doesn't exist or wrong username"}, 400

		cursor.execute("""SELECT * from korisnik WHERE korisnickoime = %s AND lozinka = %s""", (user.korisnicko_ime,  Korisnik.hash_password(data["lozinka"]),))
		db_response = cursor.fetchone()

		if db_response is None:
			return {"error": "wrong password"}, 400

		#check if user is validated
		verified = user.check_activated(cursor)
		if not verified:
			return {"error": "User is not activated"}, 401

		return {"data": "successfully logged in"}, 200


@app.route('/validate/<token>', methods=['GET'])
def validate(token):
	conn, cursor = connect_to_db()
	with conn, cursor:
		token_timestamp = Korisnik.get_token_time(cursor, token)
		if token_timestamp is None:
			return {"error": "Token invalid"}, 400

		current_time = datetime.now()

		if current_time - timedelta(hours=1) <= token_timestamp <= current_time:
			Korisnik.set_activated(cursor, token)
			conn.commit()
			return {"data": "Successfully validated user"}, 200
		
		return {"error": "Token expired"}, 401


@app.route('/register', methods=['POST'])
def register():
	conn, cursor = connect_to_db()
	with conn, cursor:

		file_ext = None

		data = dict(request.form)
		# default value
		if data["titula"] == "":
			data["titula"] = 'amater'

		user = Korisnik(data["korisnickoime"],
						Korisnik.hash_password(data["lozinka"]),
						f"pfp_{Korisnik.hash_pfp_filename(data['korisnickoime'])}",
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

					# successfully registered user

		except Exception as e:
			pass

		if file_ext is None:
			try:
				# Generate a random profile pic
				resp = requests.get(f'https://avatars.dicebear.com/api/jdenticon/{data["slikaprofila"]}.svg')
				with open(f"{fpath}.svg", "wb") as fp:
					fp.write(resp.content)

				file_ext = "svg"
				# successfully registered user

			except Exception as e:
				# successfully registered user but no image, gets default picture
				pass


		# Update DB
		user.slika_profila = f"{user.slika_profila}.{file_ext}"
		current_time = datetime.now()
		token = (uuid.uuid4().hex)[:16]

		cursor.execute("""INSERT INTO korisnik
									(korisnickoime, slikaprofila, lozinka, ime, prezime, email, titula, nivouprava, token, tokengeneriran)
						VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);""",
						(user.korisnicko_ime, user.slika_profila, user.lozinka, user.ime, user.prezime, user.email, user.titula, user.nivou_prava, token, current_time))
		conn.commit()

		# Sending verification mail
		if not debug_mail:
			send_mail.send_verification_mail(user.ime, user.prezime, user.email, token)


		if file_ext is None:
			return {"data": "successfully registered user but no image"}, 200
		else:
			return {"data": "successfully registered user"}, 200


if __name__  == "__main__":
	flask_config = {
		"host": cfg.get_config("flask_host"),
		"port": cfg.get_config("flask_port"),
		"debug": True,
	}

	if not debug_ssl:
		flask_config["ssl_context"] = (cfg.get_config("certfile"), cfg.get_config("keyfile"))

	app.run(**flask_config)
	