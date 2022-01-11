from flask import Flask, request
from flask_cors import CORS

from datetime import datetime, timedelta
import os
import psycopg2 # apt-get install libpq-dev
import requests
import shlex
import subprocess as subp
import time
import uuid

from classes import Rank, User, Competition, Trophy, VirtualCompetition, Task, TestCase, UploadedSolution
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
		task_list_instances = Task.get_recent_tasks(cursor)
		for task in task_list_instances:
			task_list.append({
				"name": f"{task.task_name}",
				"difficulty": 	f"{task.difficulty}",
				"slug": f"{task.slug}"
			})

		competition_list = Competition.get_n_closest_competitions(cursor, 5)

		return {"tasks": task_list,
				"competitions": competition_list
				}, 200

@app.route('/competitions', methods=['GET'])
def competitions():
	conn, cursor = connect_to_db()
	with conn, cursor:
		competition_list = Competition.get_n_closest_competitions(cursor, 50)
		return {"competitions": competition_list}, 200

@app.route('/create_competition', methods=['GET','POST'])
def create_competition():
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method == 'GET':
			username = request.headers.get('session')
			task_list = []
			task_list_instances = Task.get_private_tasks(cursor, username)
			for task in task_list_instances:
				task_list.append({
					"name": f"{task.task_name}",
					"slug": f"{task.slug}"
				})
			return {"tasks": task_list}, 200

		elif request.method == 'POST':
			data = dict(request.form)
			comp_slug, error = Competition.create_competition(cursor, data)
			if comp_slug is not None:
				return {"comp_slug": comp_slug}, 200
			return {"error": error}, 400

@app.route('/competition/<competition_slug>', methods=['GET', 'PUT'])
def competition(competition_slug):
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method == 'GET':
			comp, error = Competition.get_competition(cursor, competition_slug)
			if comp is not None:
				# this needs to be fixed to competition slug and not id 
				author_name, author_lastname = Task.get_author_name_from_comp_slug(cursor, competition_slug)
				tasks = Competition.get_tasks_in_comp(cursor, comp.slug)
				comp_class_name, error = Competition.get_class_name_from_class_id(cursor, comp.comp_class_id)
				return{
					"comp_slug":		f"{comp.slug}",
					"comp_name":		f"{comp.comp_name}",
					"comp_text":		f"{comp.comp_text}",
					"author_name":		f"{author_name} {author_lastname}",
					"start_time":		f"{comp.start_time}",
					"end_time":			f"{comp.end_time}",
					"trophy_img":		f"{comp.trophy_img}",
					"trophy_id":		f"{comp.trophy_id}",
					"task_count":		f"{comp.task_count}",
					"comp_class_name":	f"{comp_class_name}",
					"tasks":			tasks
				}, 200
			else:
				return {"error": error}, 403

	# paziti kod kreiranja natjecanja na rank, PUT method

@app.route('/users', methods=['GET'])
def users():
	conn, cursor = connect_to_db()
	with conn, cursor:
		user_list = User.get_users_asc(cursor)
		return {"users": user_list}, 200

@app.route('/virtual_competitions', methods=['GET'])
def virtual_competitions():
	conn, cursor = connect_to_db()
	with conn, cursor:
		username = request.headers.get('session')
		virt_list_data = VirtualCompetition.get_virt_comps_from_user(cursor, username)
		virt_list = []
		for virt in virt_list_data:
			if virt[1] is None:
				slugs = VirtualCompetition.get_slugs_from_ids_from_virt(cursor, virt[0])
				virt_list.append({"tasks": slugs,
								"name": "Virtual Competition"})
			else:
				slugs, name = VirtualCompetition.get_comp_data_for_virtual_real_comp(cursor, virt[1])
				virt_list.append({"tasks": slugs,
								"name": f"Virtual {name}"})

		return {"virtual_competitions": virt_list}, 200

@app.route('/virtual_competition/<slug_real_comp>', methods=['POST'])
@app.route('/virtual_competition/<virt_id>', methods=['GET'])
@app.route('/virtual_competition', methods=['POST'])
def virtual_competition(virt_id=None, slug_real_comp=None):
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method == 'POST':
			username = request.headers.get('session')
			# creates a virtual competition from a real one
			if slug_real_comp is not None:
				if not Competition.check_if_comp_slug_exists(cursor, slug_real_comp):
					return {"error": 'Incorrect competition slug'}, 400

				virtual_id = VirtualCompetition.insert_real_into_virt(cursor, username, slug_real_comp)	
				return {"status": "Successfully created virtual competition from a real one",
						"virtual_id": f"{virtual_id}"
						}, 200
			else:
				# creates a virtual competition with random tasks
				data = request.json
				virt = VirtualCompetition.create_virt_competition(conn, cursor, data["task_count"], username)
				task_list = VirtualCompetition.get_slugs_from_ids_from_virt(cursor, virt.virt_comp_id)
				
				return {"tasks": 		task_list,
						"virt_comp_id":	f"{virt.virt_comp_id}",
						"name": 		"Virtual Competition"
						}, 201

		elif request.method == 'GET':
			# load an already created competition
			virt, error = VirtualCompetition.get_virtual_competition(cursor, virt_id)
			if virt is not None:
				name = "Virtual Competition"
				if virt.comp_id is not None:
					# getting tasks
					virt.tasks, name = VirtualCompetition.get_comp_data_for_virtual_real_comp(cursor, virt.comp_id)
					if name is None:
						return {"error": 'Virtual competition id is not valid'}, 400
					name = f"Virtual {name}"

				return {
					"tasks":			virt.tasks,
					"created_at":		virt.created_at,
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
			return {"pfp_url": f"{profile_pic_url[0]}"}, 200

		return {"error" : "No profile picture available"}, 404

@app.route('/task/<slug>', methods=['GET', 'POST'])
def task(slug):
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method == 'GET':
			zad, error = Task.get_task(cursor, slug)
			if zad is None:
				return {"error": error}, 403

			author_name, author_lastname = Task.get_author_name(cursor, slug)
			
			return{
				"task_name":			f"{zad.task_name}",
				"difficulty":			f"{zad.difficulty}",
				"max_exe_time":			f"{zad.max_exe_time}",
				"task_text":			f"{zad.task_text}",
				"slug":					f"{zad.slug}",
				"name_last_name":		f"{author_name} {author_lastname}"
				}, 200
					

		elif request.method == 'POST':
			data = request.json

			user = User.get_user(cursor, data["username"])
			# can this happen? wrong request?
			if user is None:
				return {"error": "user doesn't exist or wrong username"}, 400
			pass

@app.route('/tasks', methods=['GET'])
def tasks():
	conn, cursor = connect_to_db()
	with conn, cursor:
		task_list = []
		task_list_instances = Task.get_all_public_tasks(cursor)
		for task in task_list_instances:
			task_list.append({
				"task_name": 	f"{task.task_name}",
				"difficulty": 	f"{task.difficulty}",
				"slug":		f"{task.slug}"
			})
		return {"tasks": task_list}, 200

@app.route('/execute_task', methods=['POST'])
def execute_task():
	conn, cursor = connect_to_db()
	with conn, cursor:
		if request.method == 'POST':
			data = request.json

			slug = data["slug"]
			user = data["username"]
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

			task, err = Task.get_task(cursor, slug)
			if task is None:
				return {
						"result": f"1/0",
						"tests": {},
					}, 403
			cursor.execute("""SELECT testprimjer.* FROM testprimjer NATURAL JOIN zadatak WHERE zadatak.slug = %s ORDER BY ulaz ASC;""", (task.slug,))
			tests = cursor.fetchall()

			total_tests = len(tests)
			passed = 0
			results = {}
			total_time = 0

			for i, test in enumerate(tests):
				test = TestCase(*test)
				proc = subp.Popen(command, stdin=subp.PIPE, stdout=subp.PIPE) # TODO: log executions

				try:
					start_time = time.time()
					output = proc.communicate(input=test.input.encode(encoding='utf-8'),
												timeout=float(task.max_exe_time))[0] # Data is also buffered in memory !
					total_time += time.time() - start_time

					output = output.decode(encoding='utf-8').strip() # Or whatever is required
					if test.output == output:
						results[i] = {"passed": True, "description": "correct answer"}
						passed += 1
					else:
						results[i] = {"passed": False, "description": "wrong answer"}

				except subp.TimeoutExpired:
					proc.kill()
					results[i] = {"passed": False, "description": "timeout"}

			# Store solution data
			cursor.execute("SELECT korisnikid FROM korisnik WHERE korisnickoime = %s;", (user,))
			upload = UploadedSolution(code,
									float(passed) / total_tests,
									submit_time,
									total_time / total_tests,
									cursor.fetchone()[0],
									task.task_id)

			# Delete temporary code files
			try:
				os.remove(f"{solution_file}*") # code and .out
			except OSError as e:
				# TODO: Log the error (just don't use Log4j pls)
				pass

			cursor.execute("""INSERT INTO uploadrjesenja
								VALUES (%s, %s, %s, %s, %s, %s);""", (upload.submitted_solution,
																	upload.passed,
																	upload.submitted_time,
																	upload.avg_exe_time,
																	upload.user_id,
																	upload.task_id))
			conn.commit()

			return {
						"result": f"{passed}/{total_tests}",
						"tests": results,
					}, 200

@app.route('/members/<username>', methods=['GET'])
def profile(username):
	conn, cursor = connect_to_db()
	with conn, cursor:
		user = User.get_user(cursor, username)
		if user is None:
			return {"error": "user doesn't exist or wrong username"}, 400
	
		trophies_list = []
		trophies_list_instances = Trophy.user_trophies(cursor, username)
		for trophy in trophies_list_instances:
			trophies_list.append({
				"trophy_name":	f"{trophy.trophy_name}",
				"trophy_img": 	f"{trophy.trophy_img}"
			})

		correctly_solved = user.calc_successfully_solved(cursor)

		submitted_solutions = []
		created_competitions = []
		if user.rank == Rank.COMPETITOR:		# Natjecatelj
			submitted_solutions_ins	= user.get_submitted_solutions(cursor)
			for task in submitted_solutions_ins:
				task_name = Task.get_task_name(cursor, task.task_id)
				submitted_solutions.append({
					"submitted_solution": f"{task.submitted_solution}",
					"passed": f"{task.passed}",
					"submitted_time": f"{task.submitted_time}",
					"avg_exe_time": f"{task.avg_exe_time}",
					## all in one query?
					"task_name": f"{task_name}"
				})

		elif user.rank in [Rank.LEADER, Rank.ADMIN]:	# Voditelj || Admin
			created_competitions_ins = user.get_created_competitons(cursor)
			for comp in created_competitions_ins: #TODO: potential error handling? is it possible?
				comp_class_name, error = Competition.get_class_name_from_class_id(cursor, comp.comp_class_id)
				created_competitions.append({
					"comp_slug":		f"{comp.slug}",
					"comp_name":		f"{comp.comp_name}",
					"start_time":		f"{comp.start_time}",
					"end_time":			f"{comp.end_time}",
					"trophy_img":		f"{comp.trophy_img}",
					"task_count":		f"{comp.task_count}",
					"comp_class_name":	f"{comp_class_name}"
				})

		return {"name": user.name,
				"last_name": user.last_name,
				"pfp_url": user.pfp_url,
				"rank": user.rank,
				"email": user.email,
				"trophies": trophies_list,
				"title": user.title,
				"attempted": user.attempted,
				"solved": user.solved,
				"correctly_solved": correctly_solved,
				"submitted_solutions": submitted_solutions,
				"created_competitions": created_competitions
				}, 200

@app.route('/edit_profile', methods=['POST'])
def edit_profile():
	conn, cursor = connect_to_db()
	with conn, cursor:
		data = dict(request.form)

		if "fromuser" not in data:
			return {"error": "User requesting edit not specified"}, 400

		fromuser = data.pop("fromuser")
		foruser = data.pop("foruser") if "foruser" in data else fromuser

		cursor.execute("""SELECT nivouprava
							FROM korisnik
							WHERE korisnickoime = %s;""", (fromuser,))
		rank = cursor.fetchone()
		
		cursor.execute(f"""SELECT slikaprofila
							FROM korisnik
							WHERE korisnickoime = %s;""", (foruser,))
		old_pfp_url = cursor.fetchone()

		if len(rank) == 0:
			return {"error": "User requesting edit does not exist"}, 400

		if len(old_pfp_url) == 0:
			return {"error": "User being edited does not exist"}, 400

		rank = rank[0]
		old_pfp_url = old_pfp_url[0]

		if foruser != fromuser and rank != Rank.ADMIN:
			return {"error": "Insufficient rank"}, 400

		querystr = "UPDATE korisnik SET "
		queryparams = []
		
		if "name" in data and data["name"] != "":
			querystr += "ime = %s,"
			queryparams += [data.pop("name")]

		if "last_name" in data and data["last_name"] != "":
			querystr += "prezime = %s,"
			queryparams += [data.pop("last_name")]

		newuser = foruser # Used if new profile pic was sent

		if rank == Rank.ADMIN: # Only admin
			if "email" in data and data["email"] != "":
				querystr += "email = %s,"
				queryparams += [data.pop("email")]

			if "rank" in data and data["rank"] != "":
				querystr += "nivouprava = %s,"
				queryparams += [data.pop("rank")]

			if "username" in data and data["username"] != "":
				querystr += "korisnickoime = %s,"
				newuser = data.pop("username")
				queryparams += [newuser]

			if "password" in data and data["password"] != "":
				querystr += "lozinka = %s,"
				queryparams += [data.pop("password")]

		if len(data) > 0:
			return {"error": "Nonexistent property or insufficient rank"}, 400

		imgreceived = False
		file_name = ""
		file_ext = ""
		old_fname = os.path.join(app.config['UPLOAD_FOLDER'], old_pfp_url)
		
		try:
			# Accept image from form
			if "pfp_url" in request.files:
				file = request.files["pfp_url"]
				if file.filename != "":
					imgreceived = True

					file_name = User.generate_pfp_filename(newuser)
					file_ext = file.filename.split('.')[-1]
					fpath = os.path.join(app.config["UPLOAD_FOLDER"], file_name)
					file.save(f"{fpath}.{file_ext}")

		except Exception as e:
			imgreceived = False

		if len(queryparams) == 0 and not imgreceived:
			return {"error": "No data sent"}, 400

		if imgreceived:
			querystr += "slikaprofila = %s,"
			queryparams += [f"{file_name}.{file_ext}"]

		querystr = querystr[:-1] if querystr.endswith(",") else querystr
		querystr += f" WHERE korisnickoime = %s;"
		queryparams += [foruser]

		try:
			cursor.execute(querystr, queryparams)
			conn.commit()

			if imgreceived:
				try:
					os.remove(f"{old_fname}")
				except OSError:
					pass

			return {"status": "Profile changes accepted"}, 200
		except Exception as e:
			return {"error": str(e)}, 500


@app.route('/login', methods=['POST'])
def login():
	conn, cursor = connect_to_db()
	with conn, cursor:
		data = request.json

		user = User.get_user(cursor, data["username"])
		if user is None:
			return {"error": "User doesn't exist or wrong username"}, 400

		cursor.execute("""SELECT * from korisnik WHERE korisnickoime = %s AND lozinka = %s""", (user.username,  User.hash_password(data["password"]),))
		db_response = cursor.fetchone()

		if db_response is None:
			return {"error": "Wrong password"}, 400

		#check if user is validated
		verified = user.check_activated(cursor)
		if not verified:
			return {"error": "User is not activated"}, 401

		return {"status": "Successfully logged in",
				"rank": user.rank
				}, 200

@app.route('/validate/<token>', methods=['GET'])
def validate(token):
	conn, cursor = connect_to_db()
	with conn, cursor:
		token_timestamp = User.get_token_time(cursor, token)
		if token_timestamp is None:
			return {"error": "Token invalid"}, 400

		current_time = datetime.now()

		if current_time - timedelta(hours=1) <= token_timestamp <= current_time:
			User.set_activated(cursor, token)
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
		if data["title"] == "":
			data["title"] = 'amater'

		user = User(data["username"],
						User.hash_password(data["password"]),
						User.generate_pfp_filename(data["username"]),
						data["name"],
						data["last_name"],
						data["email"],
						data["title"],
						data["rank"])

		user_existance, error = User.check_if_user_exists(cursor, user.username, user.email)
		if user_existance:
			return {"error": error}, 400

		# Profile pic
		fpath = os.path.join(app.config["UPLOAD_FOLDER"], user.pfp_url)
		try:
			# Accept image from form
			if "pfp_url" in request.files:
				file = request.files["pfp_url"]
				if file.filename != "":
					file_ext = file.filename.split('.')[-1]
					file.save(f"{fpath}.{file_ext}")

					# successfully registered user

		except Exception as e:
			pass

		if file_ext is None:
			try:
				# Generate a random profile pic
				resp = requests.get(f'https://avatars.dicebear.com/api/jdenticon/{data["pfp_url"]}.svg')
				with open(f"{fpath}.svg", "wb") as fp:
					fp.write(resp.content)

				file_ext = "svg"
				# successfully registered user

			except Exception as e:
				# successfully registered user but no image, gets default picture
				pass


		# Update DB
		user.pfp_url = f"{user.pfp_url}.{file_ext}"
		current_time = datetime.now()
		token = (uuid.uuid4().hex)[:16]

		cursor.execute("""INSERT INTO korisnik
									(korisnickoime, slikaprofila, lozinka, ime, prezime, email, titula, nivouprava, token, tokengeneriran)
						VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);""",
						(user.username, user.pfp_url, user.password, user.name, user.last_name, user.email, user.title, user.rank, token, current_time))
		conn.commit()

		# Sending verification mail
		if not debug_mail:
			send_mail.send_verification_mail(user.name, user.last_name, user.email, token)


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
