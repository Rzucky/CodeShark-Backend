from flask import Flask, request
from flask_cors import CORS
from werkzeug.utils import secure_filename

from datetime import datetime, timedelta
import os
import psycopg2 # apt-get install libpq-dev
import requests
import shlex
import subprocess as subp
import time
import uuid

from classes import Korisnik, Natjecanje, Trofej, VirtualnoNatjecanje, Zadatak, TestPrimjer, UploadRjesenja
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

@app.route('/', methods=['GET'])
def home():
	conn, cursor = connect_to_db()
	with conn, cursor:
		task_list = []
		task_list_instances = Zadatak.get_recent_tasks(cursor)
		for task in task_list_instances:
			task_list.append({
				"name": f"{task.ime_zadatka}",
				"tezina": 	f"{task.bodovi}",
				"slug": f"{task.slag}"
			})

		competition_list = Natjecanje.format_competitions(cursor, 5)

		return {"tasks": task_list,
				"competitions": competition_list
				}, 200

@app.route('/competitions', methods=['GET'])
def competitions():
	conn, cursor = connect_to_db()
	with conn, cursor:
		competition_list = Natjecanje.format_competitions(cursor, 50)
		return {"competitions": competition_list}, 200

@app.route('/create_competition', methods=['GET','POST'])
def create_competition():
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method == 'GET':
			username = request.headers.get('session')
			task_list = []
			task_list_instances = Zadatak.get_private_tasks(cursor, username)
			for task in task_list_instances:
				task_list.append({
					"name": f"{task.ime_zadatka}",
					"slug": f"{task.slag}"
				})
			return {"tasks": task_list}, 200

		elif request.method == 'POST':
			data = dict(request.form)
			comp_id, error = Natjecanje.create_competition(cursor, data)
			if comp_id is not None:
				return {"natjecanje_id": comp_id}, 200
			return {"error": error}, 400

@app.route('/competition/<competition_id>', methods=['GET', 'PUT'])
def competition(competition_id):
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method == 'GET':
			comp, error = Natjecanje.get_competition(cursor, competition_id)
			if comp is not None:
				# this needs to be fixed to competition slug and not id 
				author_name, author_lastname = Zadatak.get_author_name_id(cursor, comp.autor_id)
				tasks = Natjecanje.get_tasks_in_comp(cursor, comp.natjecanje_id)
				comp_class_name, error = Natjecanje.get_class_name_from_class_id(cursor, comp.id_klase_natjecanja)
				return{
					"natjecanje_id":		f"{comp.natjecanje_id}",
					"ime_natjecanja":		f"{comp.ime_natjecanja}",
					"tekst_natjecanja":		f"{comp.tekst_natjecanja}",
					"ime_prezime_autora":	f"{author_name} {author_lastname}",
					"vrijeme_poc":			f"{comp.vrijeme_poc}",
					"vrijeme_kraj":			f"{comp.vrijeme_kraj}",
					"slika_trofeja":		f"{comp.slika_trofeja}",
					"trofej_id":			f"{comp.trofej_id}",
					"broj_zadataka":		f"{comp.broj_zadatak}",
					"ime_klase_natjecanja":	f"{comp_class_name}",
					"zadaci":				tasks
				}, 200
			else:
				return {"error": error}, 403

	# paziti kod kreiranja natjecanja na rank, PUT method

@app.route('/users', methods=['GET'])
def users():
	conn, cursor = connect_to_db()
	with conn, cursor:
		user_list = Korisnik.get_users_asc(cursor)
		return {"users": user_list}, 200

@app.route('/virtual_competitions', methods=['GET'])
def virtual_competitions():
	conn, cursor = connect_to_db()
	with conn, cursor:
		username = request.headers.get('session')
		virt_list_data = VirtualnoNatjecanje.get_virt_comps_from_user(cursor, username)
		virt_list = []
		for virt in virt_list_data:
			if virt[1] is None:
				slugs = VirtualnoNatjecanje.get_slugs_from_ids_from_virt(cursor, virt[0])
				virt_list.append({"tasks": slugs,
								"name": "Virtual Competition"})
			else:
				slugs, name = VirtualnoNatjecanje.get_comp_data_for_virtual_real_comp(cursor, virt[1])
				virt_list.append({"tasks": slugs,
								"name": f"Virtual {name}"})

		return {"virtual_competitions": virt_list}, 200

@app.route('/virtual_competition/<id_real_comp>', methods=['POST'])
@app.route('/virtual_competition/<virt_id>', methods=['GET'])
@app.route('/virtual_competition', methods=['POST'])
def virtual_competition(virt_id = None, id_real_comp = None):
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method == 'POST':
			username = request.headers.get('session')
			# creates a virtual competition from a real one
			if id_real_comp is not None:
				virtual_id = VirtualnoNatjecanje.insert_real_into_virt(cursor, username, id_real_comp)	
				return {"status": "Successfully created virtual competition from a real one",
						"virtual_id": f"{virtual_id}"
						}, 200
			else:
				# creates a virtual competition with random tasks
				data = request.json
				virt = VirtualnoNatjecanje.create_virt_competition(conn, cursor, data["broj"], username)
				task_list = VirtualnoNatjecanje.get_slugs_from_ids_from_virt(cursor, virt.virt_natjecanje_id)
				
				return {"tasks": 		task_list,
						"virt_comp_id":	f"{virt.virt_natjecanje_id}",
						"name": 		"Virtual Competition"
						}, 201

		elif request.method == 'GET':
			# load an already created competition
			virt, error = VirtualnoNatjecanje.get_virtual_competition(cursor, virt_id)
			if virt is not None:
				name = "Virtual Competition"
				if virt.natjecanje_id is not None:
					# getting tasks
					virt.zadaci, name = VirtualnoNatjecanje.get_comp_data_for_virtual_real_comp(cursor, virt.natjecanje_id)
					name = f"Virtual {name}"

				return {
					"natjecanje_id":	virt.natjecanje_id,
					"tasks":			virt.zadaci,
					"created_at":		virt.vrijeme_kreacije,
					"name": 			name
				}, 200
			return {"error": error}, 400

@app.route('/avatar/<username>', methods=['GET'])
def avatar(username):
	conn, cursor = connect_to_db()
	with conn, cursor:
		cursor.execute("""SELECT slikaprofila FROM korisnik WHERE korisnickoime = %s;""", (username,))
		profile_pic_url = cursor.fetchone()
		if profile_pic_url is not None:
			return {"url": f"{profile_pic_url[0]}"}, 200

		return {"error" : "No profile picture available"}, 404

@app.route('/task/<slug>', methods=['GET', 'POST'])
def task(slug):
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method == 'GET':
			zad, error = Zadatak.get_task(cursor, slug)
			if zad is None:
				return {"error": error}, 403

			author_name, author_lastname = Zadatak.get_author_name(cursor, slug)
			
			return{
				"ime_zadatka":				f"{zad.ime_zadatka}",
				"tezina":					f"{zad.bodovi}",
				"max_vrijeme_izvrsavanja":	f"{zad.max_vrijeme_izvrsavanja}",
				"tekst_zadatka":			f"{zad.tekst_zadatka}",
				"slug":						f"{zad.slag}",
				"ime_prezime_autora":		f"{author_name} {author_lastname}"
				}, 200
					

		elif request.method == 'POST':
			data = request.json

			user = Korisnik.get_user(cursor, data["korisnickoime"])
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
				"name": 	f"{task.ime_zadatka}",
				"tezina": 	f"{task.bodovi}",
				"slug":		f"{task.slag}"
			})
		return {"tasks": task_list}, 200

@app.route('/execute_task', methods=['POST'])
def execute_task():
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method == 'POST':
			data = request.json

			slug = data["slug"]
			user = data["korisnickoime"]
			lang = data["lang"]
			code = data["code"] # Length ?

			submit_time = datetime.now()

			solutions_dir = cfg.get_config("solutions_dir")
			solution_file = f"{solutions_dir}/{user}_{time.time()}"
			with open(solution_file, "w") as fp:
				fp.write(code)

			user_account_name = cfg.get_config("user_account_name")
			compile_timeout = cfg.get_config("compile_timeout") # seconds

			# Prepare command for each language
			if lang.lower() in ["py3"]:
				command = f"sudo -u {user_account_name} {cfg.get_config('python_interpreter')} {solution_file}"

			elif lang.lower() in ["c++"]:
				# Compile
				command = f"sudo -u {user_account_name} g++ {solution_file} -o {solution_file}.out -std={cfg.get_config('c++_compiler_version')}"

				proc = None
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
				proc = None
				try:
					proc = subp.run(shlex.split(f"sudo -u {user_account_name} chmod 755 {solution_file}.out"), check=True)
				except subp.CalledProcessError:
					return {"error": "chmod error"}, 503 # ?

				# Set actual execution command
				command = f"sudo -u {user_account_name} {solution_file}.out"

			elif lang.lower() in ["c"]:
				# Compile
				command = f"sudo -u {user_account_name} gcc {solution_file} -o {solution_file}.out -std={cfg.get_config('c_compiler_version')}"

				proc = None
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
				proc = None
				try:
					proc = subp.run(shlex.split(f"sudo -u {user_account_name} chmod 755 {solution_file}.out"), check=True)
				except subp.CalledProcessError:
					return {"error": "chmod error"}, 503 # ?

				# Set actual execution command
				command = f"sudo -u {user_account_name} {solution_file}.out"

			else:
				return {"error": "unsupported language"}, 400

			# Watch out for large amounts of tests
			command = shlex.split(command)

			zad = Zadatak.get_task(cursor, slug)
			cursor.execute("""SELECT testprimjer.* FROM testprimjer NATURAL JOIN zadatak WHERE zadatak.slug = %s ORDER BY ulaz ASC;""", (zad.slug,))
			tests = cursor.fetchall()

			total_tests = len(tests)
			passed = 0
			results = {}
			total_time = 0

			for i, test in enumerate(tests):
				test = TestPrimjer(*test)
				proc = subp.Popen(command, stdin=subp.PIPE, stdout=subp.PIPE) # TODO: log executions

				try:
					start_time = time.time()
					output = proc.communicate(input=test.ulaz.encode(encoding='utf-8'),
												timeout=zad.max_vrijeme_izvrsavanja)[0] # Data is also buffered in memory !
					total_time += time.time() - start_time

					output = output.decode(encoding='utf-8').strip() # Or whatever is required
					if test.izlaz == output:
						results[i] = {"passed": True, "description": "correct answer"}
						passed += 1
					else:
						results[i] = {"passed": False, "description": "wrong answer"}

				except subp.TimeoutExpired:
					proc.kill()
					results[i] = {"passed": False, "description": "timeout"}

			# Store solution data
			cursor.execute("SELECT korisnikid WHERE korisnickoime = %s;", (user,))
			upload = UploadRjesenja(code,
									float(passed) / total_tests,
									submit_time,
									total_time / total_tests,
									cursor.fetchone()[0],
									zad.zadatak_id)

			# Delete temporary code files
			try:
				os.remove(f"{solution_file}*") # code and .out
			except OSError as e:
				# TODO: Log the error (just don't use Log4j pls)
				pass

			cursor.execute("""INSERT INTO uploadrjesenja
								VALUES (%s, %s, %s, %s, %s, %s);""", (upload.predano_rjesenje,
																	upload.prolaznost,
																	upload.vrijeme_predaje,
																	upload.prosj_vrijeme_izvrsenja,
																	upload.korisnik_id,
																	upload.zadatak_id))
			conn.commit()

			return {
						"result": f"{passed}/{total_tests}",
						"tests": results,
					}, 200

@app.route('/members/<username>', methods=['GET'])
def members(username):
	conn, cursor = connect_to_db()
	with conn, cursor:
		user = Korisnik.get_user(cursor, username)
		if user is None:
			return {"error": "user doesn't exist or wrong username"}, 400
	
		trophies_list = []
		trophies_list_instances = Trofej.user_trophies(cursor, user)
		for trophy in trophies_list_instances:
			trophies_list.append({
				"name": f"{trophy.ime_trofeja}",
				"img": 	f"{trophy.slika_trofeja}"
			})

		correctly_solved = user.calc_successfully_solved(cursor)
		
		submitted_tasks = []
		created_competitions = []
		if user.nivou_prava == 1:		# Natjecatelj
			submitted_tasks_ins	= user.get_submitted_tasks(cursor)
			for task in submitted_tasks_ins:
				task = task.__dict__
				del task["korisnik_id"]
				submitted_tasks.append(task)

		elif user.nivou_prava in [2, 3]:	# Voditelj || Admin
			created_competitions_ins = user.get_created_competitons(cursor)
			for comp in created_competitions_ins: #TODO: potential error handling? is it possible?
				comp_class_name, error = Natjecanje.get_class_name_from_class_id(cursor, comp.id_klase_natjecanja)
				created_competitions.append({
					"natjecanje_id":		f"{comp.natjecanje_id}",
					"ime_natjecanja":		f"{comp.ime_natjecanja}",
					"vrijeme_pocetak":		f"{comp.vrijeme_poc}",
					"vrijeme_kraj":			f"{comp.vrijeme_kraj}",
					"slika_trofeja":		f"{comp.slika_trofeja}",
					"broj_zadataka":		f"{comp.broj_zadatak}",
					"ime_klase_natjecanja":	f"{comp_class_name}"
				})

		return {"ime": user.ime,
				"prezime": user.prezime,
				"slikaprofila_url": user.slika_profila,
				"rank": user.nivou_prava,
				"email": user.email,
				"trophies": trophies_list,
				"titula": user.titula,
				"pokusano_zad": user.attempted,
				"uspjesno_zad": user.solved,
				"postotak_uspjesnih": correctly_solved,
				"submitted_tasks": submitted_tasks,
				"created_competitions": created_competitions
				}, 200

@app.route('/login', methods=['POST'])
def login():
	conn, cursor = connect_to_db()
	with conn, cursor:
		data = request.json

		user = Korisnik.get_user(cursor, data["korisnickoime"])
		if user is None:
			return {"error": "User doesn't exist or wrong username"}, 400

		cursor.execute("""SELECT * from korisnik WHERE korisnickoime = %s AND lozinka = %s""", (user.korisnicko_ime,  Korisnik.hash_password(data["lozinka"]),))
		db_response = cursor.fetchone()

		if db_response is None:
			return {"error": "Wrong password"}, 400

		#check if user is validated
		verified = user.check_activated(cursor)
		if not verified:
			return {"error": "User is not activated"}, 401

		return {"status": "Successfully logged in",
				"rank": user.nivou_prava
				}, 200

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
			data["titula"] = 'tutlek'

		user = Korisnik(data["korisnickoime"],
						Korisnik.hash_password(data["lozinka"]),
						f"pfp_{Korisnik.hash_pfp_filename(data['korisnickoime'])}",
						data["ime"],
						data["prezime"],
						data["email"],
						data["titula"],
						data["nivouprava"])

		user_existance, error = Korisnik.check_if_user_exists(cursor, user.korisnicko_ime, user.email)
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
