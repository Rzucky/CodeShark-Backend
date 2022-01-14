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

from slugify.slugify import slugify

from classes import Rank, User, Competition, Trophy, VirtualCompetition, Task, TestCase, UploadedSolution, Session
import codeshark_config as cfg
import send_mail

from database import PGDB
db = PGDB()
db.logging(True)
db.autocommit(True)
#db.add_middle(lambda lst: lst if type(lst) in [list, tuple, set] else [lst])
#db.error_handler()

cfg.load_config()

debug_ssl  = cfg.get_config("debug_ssl")
debug_mail = cfg.get_config("debug_mail")

app = Flask(__name__)
CORS(app)

app.config["IMG_UPLOAD_FOLDER"] = cfg.get_config("img_upload_dir") # Folder must already exist !
app.config["TROPHY_UPLOAD_FOLDER"] = cfg.get_config("trophy_upload_dir") # Folder must already exist !
app.config["MAX_CONTENT_LENGTH"] = cfg.get_config("max_content_length") # bytes [=1 MB]

def connect_to_db():
	conn = psycopg2.connect(database	= cfg.get_config("postgres_name"),
							host		= cfg.get_config("postgres_host"),
							user		= cfg.get_config("postgres_user"),
							password	= cfg.get_config("postgres_pass"))
	cursor = conn.cursor()
	return conn, cursor

@app.route('/', methods=['GET'])
def home():
	task_list = []
	for task in Task.get_recent_tasks():
		task_list.append({
			"name":			f"{task.task_name}",
			"difficulty":	f"{task.difficulty}",
			"slug":			f"{task.slug}"
		})

	competition_list = Competition.get_n_closest_competitions(5)
	return {"tasks": task_list,
			"competitions": competition_list
			}, 200

@app.route('/competitions', methods=['GET'])
def competitions():
	competition_list = Competition.get_competitions()
	return {"competitions": competition_list}, 200

@app.route('/create_competition', methods=['GET','POST'])
def create_competition():
	session_id = request.headers.get('session')
	if Session.check_expired(session_id):
		return {"error": "token expired"}, 419
	session_id, username = Session.verify(session_id)
	if session_id is None:
		return {"error": "token invalid"}, 401
	
	if request.method == 'GET':
		task_list = []
		task_list_instances = Task.get_private_tasks(username)
		for task in task_list_instances:
			task_list.append({
				"name": f"{task.task_name}",
				"slug": f"{task.slug}"
			})
		return {"tasks": task_list}, 200

	elif request.method == 'POST':
		data = dict(request.form)

		img_uploaded = False
		trophy_file = ""
		try:
			# Accept image from form
			if "trophy_img" in request.files:
				file = request.files["trophy_img"]
				if file.filename != "":
					file_name = Trophy.generate_trophy_filename(username)
					file_ext = file.filename.split('.')[-1]
					trophy_file = f"{file_name}.{file_ext}"
					file.save(os.path.join(cfg.get_config("trophy_upload_dir"), trophy_file))
					img_uploaded = True
		except Exception as e:
			trophy_file = cfg.get_config("default_trophy_img")

		if img_uploaded:
			# Update db
			trophy_id = db.query(f"""INSERT INTO trofej
						(imetrofeja, slikatrofeja)
						VALUES (%s, %s) RETURNING trofejid;""", data["trophy_name"], trophy_file)

			if db.error == psycopg2.errors.UniqueViolation:
				os.remove(os.path.join(cfg.get_config("trophy_upload_dir"), trophy_file))
				return {"error": "Trophy with the same name already exists"}, 400
		else:
			trophy_id = db.query(f"""SELECT trofejid
								FROM trofej
								WHERE slikatrofeja = %s
								ORDER BY trofejid ASC LIMIT 1;""", trophy_file)
		data["username"] = username
		comp_slug, error = Competition.create_competition(data, trophy_id)
		if comp_slug is not None:
			return {"comp_slug": comp_slug}, 200
		return {"error": error}, 400

@app.route('/competition/<competition_slug>', methods=['GET', 'PUT'])
def competition(competition_slug):
	if request.method == 'GET':
		comp, error = Competition.get_competition(competition_slug)
		if comp:
			author_name, author_lastname = Task.get_author_name_from_comp_slug(competition_slug)
			tasks = Competition.get_tasks_in_comp(comp.slug)
			comp_class_name = Competition.get_class_name_from_class_id(comp.comp_class_id)
			return {
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
	user_list = User.get_users_asc()
	return {"users": user_list}, 200

@app.route('/virtual_competitions', methods=['GET'])
def virtual_competitions():
	session_id = request.headers.get('session')
	if Session.check_expired(session_id):
		return {"error": "token expired"}, 419
	session_id, username = Session.verify(session_id)
	if session_id is None:
		return {"error": "token invalid"}, 401
	virt_list_data = VirtualCompetition.get_virt_comps_from_user(username)
	virt_list = []
	for virt in virt_list_data:
		if virt[1] is None:
			tasks = VirtualCompetition.get_slugs_from_ids_from_virt(virt[0])
			virt_list.append({"tasks": tasks,
							   "virt_id": virt[0],
							   "name": "Virtual Competition"})
		else:
			tasks, name = VirtualCompetition.get_comp_data_for_virtual_real_comp(virt[1])
			virt_list.append({"tasks": tasks,
							"virt_id": virt[0],
							"name": f"Virtual {name}"})

	return {"virtual_competitions": virt_list}, 200

@app.route('/virtual_competition/<slug_real_comp>', methods=['POST'])
@app.route('/virtual_competition/<virt_id>', methods=['GET'])
@app.route('/virtual_competition', methods=['POST'])
def virtual_competition(virt_id=None, slug_real_comp=None):
	if request.method == 'POST':
		session_id = request.headers.get('session')
		if Session.check_expired(session_id):
			return {"error": "token expired"}, 419
		session_id, username = Session.verify(session_id)
		if session_id is None:
			return {"error": "token invalid"}, 401
		# creates a virtual competition from a real one
		if slug_real_comp is not None:
			if not Competition.check_if_comp_slug_exists(slug_real_comp):
				return {"error": 'Incorrect competition slug'}, 400

			virtual_id = VirtualCompetition.insert_real_into_virt(username, slug_real_comp)	
			return {"status": "Successfully created virtual competition from a real one",
					"virtual_id": f"{virtual_id}"
					}, 200
		else:
			# creates a virtual competition with random tasks
			data = request.json
			virt = VirtualCompetition.create_virt_competition(data["task_count"], username)
			task_list = VirtualCompetition.get_slugs_from_ids_from_virt(virt.virt_comp_id)
			
			return {"tasks": 		task_list,
					"virt_comp_id":	f"{virt.virt_comp_id}",
					"name": 		"Virtual Competition"
					}, 201

	elif request.method == 'GET':
		# load an already created competition
		virt, error = VirtualCompetition.get_virtual_competition(virt_id)
		if virt is not None:
			name = "Virtual Competition"
			if virt.comp_id is not None:
				# getting tasks
				virt.tasks, name = VirtualCompetition.get_comp_data_for_virtual_real_comp(virt.comp_id)
				if name is None:
					return {"error": 'Virtual competition id is not valid'}, 400
				name = f"Virtual {name}"
			else:
				virt.tasks = VirtualCompetition.get_slugs_from_ids_from_virt(virt_id)

			return {
				"tasks":			virt.tasks,
				"created_at":		virt.created_at,
				"name": 			name
			}, 200
		return {"error": error}, 400

@app.route('/avatar/<username>', methods=['GET'])
def avatar(username):
	profile_pic_url = db.query("""SELECT slikaprofila 
							FROM korisnik 
							WHERE korisnickoime = %s;""", username)
	if profile_pic_url is not None:
		return {"pfp_url": f"{profile_pic_url}"}, 200

	return {"error" : "No profile picture available"}, 404

@app.route('/task/<slug>', methods=['GET'])
def task(slug):
	session_id = request.headers.get('session')
	if Session.check_expired(session_id):
		return {"error": "token expired"}, 419
	session_id, username = Session.verify(session_id)
	if session_id is None:
		return {"error": "token invalid"}, 401

	zad, error = Task.get_task(slug)
	if error:
		return {"error": error}, 403

	uploaded_solutions = []
	user_score = UploadedSolution.check_solution_score(slug, username)
	last_user_solution = UploadedSolution.get_latest_solution(slug, username)
	uploaded_solutions_tuples = Task.get_other_task_solutions(slug)
	if user_score == 1.0:
		for uploaded_solution in uploaded_solutions_tuples:
			if uploaded_solution[1] == 1.0:
				# also get code from people with 100%
				uploaded_solutions.append({
					"username": uploaded_solution[0],
					"score": uploaded_solution[1],
					"avg_exe_time": uploaded_solution[2],
					"code": uploaded_solution[3],
				})
			else:
				uploaded_solutions.append({
					"username": uploaded_solution[0],
					"score": uploaded_solution[1],
					"avg_exe_time": uploaded_solution[2],
				})
	else:
		for uploaded_solution in uploaded_solutions_tuples:
			uploaded_solutions.append({
				"username": uploaded_solution[0],
				"score": uploaded_solution[1],
				"avg_exe_time": uploaded_solution[2],
			})

	author_name, author_lastname = Task.get_author_name(slug)
	
	return {
		"task_name":			f"{zad.task_name}",
		"difficulty":			f"{zad.difficulty}",
		"max_exe_time":			f"{zad.max_exe_time}",
		"task_text":			f"{zad.task_text}",
		"slug":					f"{zad.slug}",
		"name_last_name":		f"{author_name} {author_lastname}",
		"last_user_solution":	last_user_solution,
		"uploaded_solutions":	uploaded_solutions
		}, 200

@app.route('/tasks', methods=['GET'])
def tasks():
	task_list = []
	task_list_instances = Task.get_all_public_tasks()
	for task in task_list_instances:
		task_list.append({
			"task_name": 	f"{task.task_name}",
			"difficulty": 	f"{task.difficulty}",
			"slug":		f"{task.slug}"
		})
	return {"tasks": task_list}, 200

@app.route('/create_task', methods=['POST'])
def create_task():
	session_id = request.headers.get('session')
	if Session.check_expired(session_id):
		return {"error": "token expired"}, 419
	session_id, username = Session.verify(session_id)
	if session_id is None:
		return {"error": "token invalid"}, 401

	data = request.json

	rank = db.query(f"""SELECT nivouprava
						FROM korisnik
						WHERE korisnickoime = %s;""", username)
	if not rank:
		return {"error": "User does not exist"}, 400

	if rank not in [Rank.LEADER, Rank.ADMIN]:
		return {"error": "Insufficient rank"}, 400

	try:
		if "test_cases" not in data or len(data["test_cases"]) < 10:
			return {"error": "Not enough test cases"}, 400

		taskid = db.queryc(f"""INSERT INTO zadatak
								(imezadatka, bodovi, maxvrijemeizvrs, tekstzadatka, privatnost, slug, autorid)
								VALUES (%s, %s, %s, %s, %s, %s, (SELECT korisnikid
																	FROM korisnik
																	WHERE korisnickoime = %s))
								RETURNING zadatakid;""",
								data["task_name"], data["difficulty"], data["max_exe_time"], data["task_text"], data["private"], slugify(data["task_name"]), username,
								False)

		if db.error:
			return {"error": "Task already exists"}, 400

		for tc in data["test_cases"]:
			db.queryc(f"""INSERT INTO testprimjer
							(ulaz, izlaz, zadatakid)
							VALUES (%s, %s, %s);""",
						tc["input"], tc["output"], taskid,
						False)
			if db.error:
				return {"error": "Test case already exists"}, 400

		db.commit()

	except Exception as e:
		db.rollback()
		return {"error": db.errormsg}, 500

	return {"status": "Created task"}, 200

@app.route('/execute_task', methods=['POST'])
def execute_task():
	session_id = request.headers.get('session')
	if Session.check_expired(session_id):
		return {"error": "token expired"}, 419
	session_id, user = Session.verify(session_id)
	if session_id is None:
		return {"error": "token invalid"}, 401

	data = request.json

	try:
		slug = data["slug"]
		lang = data["lang"].lower()
		code = data["code"] # Length ?
	except:
		return {"error": "invalid data sent"}, 400

	submit_time = datetime.now()

	solutions_dir = cfg.get_config("solutions_dir")
	solution_file = f"{solutions_dir}/{user}_{time.time()}"

	user_account_name = cfg.get_config("user_account_name")
	compile_timeout = cfg.get_config("compile_timeout") # seconds

	# Prepare command for each language
	if lang in ["py3"]:
		with open(f"{solution_file}.py3", "w") as fp:
			fp.write(code)

		command = f"sudo -u {user_account_name} {cfg.get_config('python_interpreter')} {solution_file}.py3"

	elif lang in ["c++"]:
		with open(f"{solution_file}.cpp", "w") as fp:
			fp.write(code)

		# Compile
		command = f"sudo -u {user_account_name} g++ {solution_file}.cpp -o {solution_file}.out -std={cfg.get_config('c++_compiler_version')}"

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

	elif lang in ["c"]:
		with open(f"{solution_file}.c", "w") as fp:
			fp.write(code)

		# Compile
		command = f"sudo -u {user_account_name} gcc {solution_file}.c -o {solution_file}.out -std={cfg.get_config('c_compiler_version')}"

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

	task, err = Task.get_task(slug)
	if not task:
		return {
				"error": err,
			}, 403

	tests = db.query("""SELECT testprimjer.*
						FROM testprimjer
						JOIN zadatak
							USING(zadatakid)
						WHERE zadatak.slug = %s
						ORDER BY ulaz ASC""", task.slug)

	total_tests = len(tests)
	passed = 0
	results = {}
	total_time = 0

	if total_tests == 0:
		return {"error": "No test cases"}, 400

	for i, test in enumerate(tests):
		test = TestCase(*test)
		proc = subp.Popen(command, stdin=subp.PIPE, stdout=subp.PIPE)

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
	upload = UploadedSolution(	code,
								float(passed) / total_tests,
								submit_time,
								total_time / total_tests,
								db.query("SELECT korisnikid FROM korisnik WHERE korisnickoime = %s", user),
								task.task_id)

	# Delete temporary code files
	try:
		os.remove(f"{solution_file}*") # code and .out
	except OSError as e:
		pass

	db.query("""INSERT INTO uploadrjesenja
				VALUES (%s, %s, %s, %s, %s, %s)""", upload.submitted_solution,
													upload.passed,
													upload.submitted_time,
													upload.avg_exe_time,
													upload.user_id,
													upload.task_id)

	return {
				"result": f"{passed}/{total_tests}",
				"percentage": float(passed) / total_tests,
				"tests": results,
			}, 200

@app.route('/members/<username>', methods=['GET'])
def profile(username):
	user = User.get_user(username)
	if not user:
		return {"error": "user doesn't exist or wrong username"}, 400

	trophies_list = []
	trophies_list_instances = Trophy.user_trophies(username)
	for trophy in trophies_list_instances:
		trophies_list.append({
			"trophy_name":	f"{trophy.trophy_name}",
			"trophy_img": 	f"{trophy.trophy_img}"
		})

	correctly_solved = user.calc_successfully_solved()

	submitted_solutions = []
	created_competitions = []
	created_tasks = []
	if user.rank == Rank.COMPETITOR:		# Natjecatelj
		submitted_solutions_ins	= user.get_submitted_solutions()
		for task in submitted_solutions_ins:
			task_name = Task.get_task_name(task.task_id)
			submitted_solutions.append({
				"submitted_solution": f"{task.submitted_solution}",
				"passed": f"{task.passed}",
				"submitted_time": f"{task.submitted_time}",
				"avg_exe_time": f"{task.avg_exe_time}",
				"task_name": f"{task_name}"
			})

	elif user.rank in [Rank.LEADER, Rank.ADMIN]:	# Voditelj || Admin
		created_competitions_ins = user.get_created_competitons()
		for comp in created_competitions_ins: 
			comp_class_name = Competition.get_class_name_from_class_id(comp.comp_class_id)
			created_competitions.append({
				"comp_slug":		f"{comp.slug}",
				"comp_name":		f"{comp.comp_name}",
				"start_time":		f"{comp.start_time}",
				"end_time":			f"{comp.end_time}",
				"trophy_img":		f"{comp.trophy_img}",
				"task_count":		f"{comp.task_count}",
				"comp_class_name":	f"{comp_class_name}"
			})
		created_tasks_ins = user.get_created_tasks()
		for task in created_tasks_ins:
			created_tasks.append({
				"name":			f"{task.task_name}",
				"difficulty":	f"{task.difficulty}",
				"slug":			f"{task.slug}"
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
			"created_competitions": created_competitions,
			"created_tasks": created_tasks
			}, 200

@app.route('/edit_profile', methods=['POST'])
def edit_profile():
	session_id = request.headers.get('session')
	if Session.check_expired(session_id):
		return {"error": "token expired"}, 419
	session_id, fromuser = Session.verify(session_id)
	if session_id is None:
		return {"error": "token invalid"}, 401

	data = dict(request.form)

	# if "fromuser" not in data:
	# 	return {"error": "User requesting edit not specified"}, 400

#	fromuser = data.pop("fromuser")
	foruser = data.pop("foruser") if "foruser" in data else fromuser

	rank = db.query("""SELECT nivouprava
						FROM korisnik
						WHERE korisnickoime = %s""", fromuser)

	old_pfp_url = db.query("""SELECT slikaprofila
								FROM korisnik
								WHERE korisnickoime = %s;""", foruser)

	if not rank:
		return {"error": "User requesting edit does not exist"}, 400

	if not old_pfp_url:
		return {"error": "User being edited does not exist"}, 400

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

	if "password" in data and data["password"] != "":
		querystr += "lozinka = %s,"
		queryparams += [data.pop("password")]

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

	if len(data) > 0:
		return {"error": "Nonexistent property or insufficient rank"}, 400

	imgreceived = False
	file_name = ""
	file_ext = ""
	old_fname = os.path.join(app.config['IMG_UPLOAD_FOLDER'], old_pfp_url)
	
	try:
		# Accept image from form
		if "pfp_url" in request.files:
			file = request.files["pfp_url"]
			if file.filename != "":
				imgreceived = True

				file_name = User.generate_pfp_filename(newuser)
				file_ext = file.filename.split('.')[-1]
				fpath = os.path.join(app.config["IMG_UPLOAD_FOLDER"], file_name)
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
	queryparams = tuple(queryparams)

	db.query(querystr, *queryparams)

	if imgreceived:
		try:
			os.remove(f"{old_fname}")
		except OSError:
			pass

	if db.error:
		return {"error": db.errormsg}, 500

	return {"status": "Profile changes accepted"}, 200


@app.route('/login', methods=['POST'])
def login():
	session_id = request.headers.get('session')
	data = request.json

	user = User.get_user(data["username"])
	if user is None:
		return {"error": "User doesn't exist or wrong username"}, 400

	db_response = db.query("""SELECT * FROM korisnik
								WHERE korisnickoime = %s
									AND lozinka = %s""", user.username,  User.hash_password(data["password"]))

	if not db_response:
		return {"error": "Wrong password"}, 400

	#check if user is validated
	if not user.check_activated():
		return {"error": "User is not activated"}, 401
	
	session_id = Session.obtain(session_id, user.username)
	if session_id is None:
		return {"error": "Incorrect session id"}, 400

	return {"status": "Successfully logged in",
			"session_id": session_id,
			"rank": user.rank
			}, 200

@app.route('/validate/<token>', methods=['GET'])
def validate(token):
	token_timestamp = User.get_token_time(token)
	if token_timestamp is None:
		return {"error": "Token invalid"}, 400

	current_time = datetime.now()

	if current_time - timedelta(hours=1) <= token_timestamp <= current_time:
		User.set_activated(token)
		return {"data": "Successfully validated user"}, 200
	
	return {"error": "Token expired"}, 401

@app.route('/register', methods=['POST'])
def register():
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

	user_existence, error = User.check_if_user_exists(user.username, user.email)
	if user_existence:
		return {"error": error}, 400

	# Profile pic
	fpath = os.path.join(app.config["IMG_UPLOAD_FOLDER"], user.pfp_url)
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

	db.query("""INSERT INTO korisnik
					(korisnickoime, slikaprofila, lozinka, ime, prezime, email, titula, nivouprava, token, tokengeneriran)
				VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
				user.username, user.pfp_url, user.password, user.name, user.last_name, user.email, user.title, user.rank, token, current_time)

	# Sending verification mail
	if not debug_mail:
		send_mail.send_verification_mail(user.name, user.last_name, user.email, token)
		if user.rank == 2:
			send_mail.send_upgrade_mail(user)

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
