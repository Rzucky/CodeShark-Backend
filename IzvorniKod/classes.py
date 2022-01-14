import hashlib
import json
from slugify import slugify
from enum import IntEnum
import time

from database import PGDB
db = PGDB()

class Rank(IntEnum):
	COMPETITOR = 1
	LEADER = 2
	ADMIN = 3

#db.add_middle(lambda lst: lst if type(lst) in [list, tuple, set] else [lst])
def check(lst):
	return lst if type(lst) in [list, tuple, set] else [lst]

class User:
	def __init__(self, username, password, pfp_url, name, last_name, email, title='amater', rank=Rank.COMPETITOR):
		self.username = username
		self.password = password
		self.pfp_url = pfp_url
		self.name = name
		self.last_name = last_name
		self.email = email
		self.title = title
		self.rank = rank

	def calc_successfully_solved(self):
		num_correctly_solved = db.query("""SELECT COUNT (DISTINCT zadatakid)
											FROM uploadrjesenja
											JOIN korisnik 
												USING(korisnikid) 
											WHERE korisnickoime = %s
												AND prolaznost = 1;""", self.username)
		
		# currently for testing purposes
		if num_correctly_solved == 0:
			num_correctly_solved = 1

		num_attempted = db.query("""SELECT COUNT (DISTINCT  zadatakid)
									FROM uploadrjesenja
									JOIN korisnik 
										USING(korisnikid) 
									WHERE korisnickoime = %s""", self.username)

		# currently for testing purposes
		if num_attempted == 0:
			num_attempted = 3

		self.solved = num_correctly_solved
		self.attempted = num_attempted
		
		# in case the user hasn't attempted any
		if self.attempted != 0:
			return self.solved / self.attempted
		else:
			return 0

	def check_activated(self):
		return db.query("""SELECT aktivan FROM korisnik 
							WHERE korisnickoime = %s;""", self.username)

	def get_created_competitons(self):
		lst = []
		for comp in db.query("""SELECT natjecanje.* 
								FROM natjecanje
								JOIN korisnik 
									ON (korisnikid = autorid) 
								WHERE korisnik.korisnickoime = %s;""", self.username):
			lst += [Competition(*comp)]
		return lst

	def get_submitted_solutions(self):
		lst = []
		for comp in db.query("""SELECT uploadrjesenja.* 
								FROM uploadrjesenja
								JOIN korisnik 
									USING(korisnikid) 
								WHERE korisnickoime = %s
								LIMIT 10;""", self.username):
			lst += [UploadedSolution(*comp)]
		return lst
	
	def get_created_tasks(self):
		lst = []
		for task in db.query("""SELECT zadatak.* FROM zadatak 
								JOIN korisnik ON(autorid = korisnikid)
								WHERE privatnost = false 
								AND korisnickoime = %s 
								LIMIT 10;""", self.username):

			lst += [Task(*task)]
		return lst

	@classmethod
	def generate_pfp_filename(cls, uname):
		hsh = cls.hash_pfp_filename(f"{uname}+{time.time()}") # (call static)
		return f"pfp_{hsh}"

	@staticmethod
	def get_token_time(token):
		token_timestamp = db.query("""SELECT tokengeneriran FROM korisnik 
										WHERE token = %s;""", token)
		if token_timestamp:
			return token_timestamp
		return None

	@staticmethod
	def set_activated(token):
		# Activating user
		db.query("""UPDATE korisnik
					SET aktivan = %s 
					WHERE token = %s""", True, token)
		# Removing token from db
		db.query("""UPDATE korisnik
					SET token = %s,
						tokengeneriran = %s 
					WHERE token = %s""", None, None, token)

	@staticmethod
	def hash_password(plainpass):
		return hashlib.sha256(plainpass.encode('utf-8')).hexdigest()

	@staticmethod
	def hash_pfp_filename(username): # not the best name but leave for compatibility
		return hashlib.md5(username.encode('utf-8')).hexdigest()

	@staticmethod
	def get_users_asc():
		user_list = []
		for user in db.query("""SELECT korisnickoime, slikaprofila, ime, prezime
								FROM korisnik
								ORDER BY korisnickoime ASC;"""):
			user_list.append({
				"username": f"{user[0]}",
				"pfp_url": f"{user[1]}",
				"name_last_name": f"{user[2]} {user[3]}"
			})
		return user_list

	@staticmethod
	def check_if_user_exists(username, email):
		# checking for taken username and email
		if db.query("""SELECT * FROM korisnik WHERE email = %s""", email):
			return True, "Email already in use"

		if db.query("""SELECT * FROM korisnik WHERE korisnickoIme = %s""", username):
			return True, "Username taken"

		return False, None

	@staticmethod
	def get_user(username):
		for resp in db.query("""SELECT *
							FROM korisnik 
							WHERE korisnickoime = %s;""", username):
			resp = resp[1:-3]
			return User(*resp)
		return None

class Competition:
	def __init__(self, comp_id, comp_name, comp_text, end_time, start_time, trophy_img, task_count, author_id, comp_class_id, trophy_id, slug):
		self.comp_id = comp_id
		self.comp_name = comp_name
		self.comp_text = comp_text
		self.end_time = end_time
		self.start_time = start_time
		self.trophy_img = trophy_img
		self.task_count = task_count
		self.author_id = author_id
		self.comp_class_id = comp_class_id
		self.trophy_id = trophy_id
		self.slug = slug

	def get_competition(comp_slug):
		for resp in check(db.query("""SELECT * FROM natjecanje 
							WHERE slug = %s""", comp_slug)):
			return Competition(*resp), None
		return None, "Competition does not exist"

	@staticmethod
	def get_competitions():
		comp_list = []
		for comp in db.query("""SELECT * FROM natjecanje
							ORDER BY vrijemepoc DESC"""):
			comp_list += [Competition(*comp)]
		
		return Competition.format_competitions(comp_list)

	@staticmethod
	def get_n_closest_competitions(n):
		comp_list = []
		for comp in db.query("""SELECT * FROM natjecanje
					WHERE (CURRENT_TIMESTAMP < vrijemekraj)
					ORDER BY vrijemepoc ASC
					LIMIT %s;""", n):
			comp_list += [Competition(*comp)]
		
		return Competition.format_competitions(comp_list)

	# format to the form to show on front page and comp page
	@staticmethod
	def format_competitions(comp_list_instances):
		competition_list = []
		for comp in comp_list_instances:
			comp_class_name, error = Competition.get_class_name_from_class_id(comp.comp_class_id)
			competition_list.append({
				"comp_slug":		f"{comp.slug}",
				"comp_name":		f"{comp.comp_name}",
				"start_time":		f"{comp.start_time}",
				"end_time":			f"{comp.end_time}",
				"trophy_img":		f"{comp.trophy_img}",
				"task_count":		f"{comp.task_count}",
				"comp_class_name":	f"{comp_class_name}",
			})

		return competition_list
	
	# list of tasks in a competition
	@staticmethod
	def get_tasks_in_comp(comp_slug):
		task_slug_list = []
		for task in check(db.query("""SELECT zadatak.slug 
								FROM zadatak
								JOIN natjecanje
									USING(natjecanjeid) 
								WHERE natjecanje.slug = %s""", comp_slug)):
			task_slug_list += [task[0]]
		return task_slug_list

	@staticmethod
	def get_class_name_from_class_id(class_id): ##
		resp = db.query("""SELECT nazivklasenatjecanja 
							FROM klasanatjecanja 
							WHERE idklasenatjecanja = %s""", class_id)
		if resp:
			return resp, None
		return None, "Class name doesn't exist"

	@staticmethod
	def create_competition(data, trophy_id):
		tasks = json.loads(data["tasks"])
		slug = slugify(data["comp_name"])

		trophy_file = db.query(f"""SELECT slikatrofeja
								FROM trofej
								WHERE trofejid = %s;""", trophy_id)

		if db.error:
			return None, "Trophy does not exist"

		for resp in check(db.query("""INSERT INTO natjecanje(imenatjecanja, slug, tekstnatjecanja, vrijemekraj, 
												vrijemepoc, slikatrofeja, brojzadataka, 
												autorid, idklasenatjecanja, trofejid)
							VALUES(%s, %s ,%s, %s, %s, %s, %s,
									(SELECT korisnikid FROM korisnik WHERE korisnickoime = %s),
									%s, %s) 
							RETURNING slug, natjecanjeid""",
						data["comp_name"], slug, data["comp_text"], data["end_time"], 
						data["start_time"], trophy_file, len(tasks),
						data["username"], 1, trophy_id)):
			comp_slug, comp_id = resp[0], resp[1]
			
		if db.error:
			return None, db.errormsg #"Error while creating competition"
		
		# only public the tasks if the competition was successful
		for task_slug in tasks:
			db.query("""UPDATE zadatak
						SET natjecanjeid = %s, 
							privatnost = false
						WHERE zadatak.slug = %s;""",
						comp_id, task_slug.strip())
		return comp_slug, None
	

	@staticmethod
	def check_if_comp_slug_exists(slug):
		if db.query("""SELECT * FROM natjecanje WHERE slug = %s""", slug):
			return True
		return False

class Trophy:
	def __init__(self, trophy_id, trophy_name, trophy_img):
		self.trophy_id = trophy_id
		self.trophy_name = trophy_name
		self.trophy_img = trophy_img

	@staticmethod
	def user_trophies(username):
		trophies_list = []
		for trophy in db.query("""SELECT trofejid, imetrofeja, slikatrofeja
									FROM jeosvojio
									JOIN korisnik 
										USING(korisnikid)
									NATURAL JOIN trofej
									WHERE korisnickoime =  %s;""", username):
			trophies_list += [Trophy(*trophy)]
		return trophies_list

	@staticmethod
	def generate_trophy_filename(uname):
		hsh = User.hash_pfp_filename(f"{uname}+{time.time()}")
		return f"trophy_{hsh}"

class Task:
	def __init__(self, task_id, task_name, difficulty, max_exe_time, task_text, private, slug, author_id, comp_id):
		self.task_id = task_id
		self.task_name = task_name
		self.difficulty = difficulty
		self.max_exe_time = max_exe_time
		self.task_text = task_text
		self.private = private
		self.slug = slug
		self.author_id = author_id
		self.comp_id = comp_id

	@staticmethod
	def get_all_public_tasks():
		public_tasks = []
		for task in db.query("""SELECT * FROM zadatak 
								WHERE privatnost = false
								LIMIT 50;"""):
			public_tasks += [Task(*task)]

		return public_tasks		

	@staticmethod
	def get_random_tasks(n):
		# if just 1, fully random
		if n == 1:
			return db.query("""SELECT zadatakid FROM zadatak 
								WHERE privatnost = false
								ORDER BY RANDOM ()
								LIMIT 1;""")

		task_list = set()
		count = db.query("""SELECT COUNT(DISTINCT zadatakid) 
							FROM zadatak WHERE privatnost = false;""")
		if n  > 10 or n > count:
			n = min(10, count)
		
		# ceil function without importing math
		easier_n = n // 2 + (n % 2 > 0)
		harder_n = n - easier_n

		# easier tasks
		for i in check(db.query("""SELECT zadatakid FROM zadatak 
							WHERE privatnost = false 
							AND bodovi IN(1, 2, 3)
							ORDER BY RANDOM ()
							LIMIT %s;""", easier_n)):
			task_list.add(i) # <<==>>

		# harder tasks
		for i in check(db.query("""SELECT zadatakid FROM zadatak 
							WHERE privatnost = false 
							AND bodovi IN(3, 4, 5)
							ORDER BY RANDOM ()
							LIMIT %s""", harder_n)):
			task_list.add(i) # <<==>>

		# if there aren't enough tasks of some kind, add randoms
		if len(task_list) < n:
			for i in check(db.query("""SELECT zadatakid FROM zadatak 
								WHERE privatnost = false
								ORDER BY RANDOM ()
								LIMIT %s""", n - len(task_list))):
				task_list.add(i) # <<==>>

		# in case we get a duplicate task, 
		# keeps trying until it finds a new one 
		while(len(task_list) < n):
			task = db.query("""SELECT zadatakid FROM zadatak 
								WHERE privatnost = false
								ORDER BY RANDOM ()
								LIMIT 1""")
			if task is not None:
				task_list.add(task)
			else:
				# no tasks remaining
				return list(task_list)
		return list(task_list)


	@staticmethod
	def get_task(slug):
		for resp in db.query("""SELECT *
							FROM zadatak 
							WHERE slug = %s""", slug):
			task = Task(*resp)
			if task.private:
				return None, "Task does not exist" # we won't give info if the task is private	
			return task, None

		return None, "Task does not exist"

	@staticmethod
	def get_author_name(slug):
		for resp in db.query("""SELECT ime, prezime
							FROM zadatak
							JOIN korisnik 
								ON (korisnikid = autorid)
							WHERE zadatak.slug = %s;""", slug):
			return resp

	@staticmethod
	def get_author_name_from_comp_slug(comp_slug):
		for resp in db.query("""SELECT ime, prezime 
							FROM korisnik
							JOIN natjecanje 
								ON (autorid = korisnikid)
							WHERE slug =  %s;""", comp_slug):
			return resp[0], resp[1]

	@staticmethod
	def get_recent_tasks():
		task_list = []
		for task in db.query("""SELECT * FROM zadatak 
								WHERE privatnost = false
								ORDER BY zadatakid DESC LIMIT 5;"""):
			task_list += [Task(*task)]
		return task_list

	@staticmethod
	def get_private_tasks(username):
		task_list = []
		for task in db.query("""SELECT zadatak.* FROM zadatak 
								JOIN korisnik ON(korisnikid = autorid) 
								WHERE privatnost = true 
								AND korisnickoime = %s""", username):
			task_list += [Task(*task)]
		return task_list

	# used at profile page to show the name
	@staticmethod
	def get_task_name(id):
		return db.query("""SELECT imezadatka FROM zadatak
							WHERE zadatakid = %s""", id)
	
	@staticmethod
	def get_other_task_solutions(slug):
		return check(db.query("""SELECT * 
					FROM(SELECT DISTINCT ON (korisnik.korisnickoime) 
								korisnik.korisnickoime, prolaznost,
								prosjvrijemeizvrs, predanorjesenje
							FROM uploadrjesenja JOIN korisnik USING(korisnikid) 
							NATURAL JOIN zadatak WHERE zadatak.slug = %s
								ORDER BY korisnickoime, prolaznost DESC, 
										prosjvrijemeizvrs ASC) AS bestruns
						ORDER BY prolaznost DESC, prosjvrijemeizvrs ASC;""", slug))

class TestCase:
	def __init__(self, input, output, task_id):
		self.input = input
		self.output = output
		self.task_id = task_id

class UploadedSolution:
	def __init__(self, submitted_solution, passed, submitted_time, avg_exe_time, user_id, task_id):
		self.submitted_solution = submitted_solution
		self.passed = passed
		self.submitted_time = submitted_time
		self.avg_exe_time = avg_exe_time
		self.user_id = user_id
		self.task_id = task_id
		
	@staticmethod
	def check_solution_score(slug, username):
		return db.query("""SELECT prolaznost FROM uploadrjesenja 
					JOIN korisnik USING(korisnikid) 
					JOIN zadatak USING(zadatakid) 
					WHERE slug = %s AND korisnickoime = %s
					ORDER BY prolaznost DESC LIMIT 1""", slug, username)

	@staticmethod
	def get_latest_solution(slug, username):
		return db.query("""SELECT predanorjesenje FROM uploadrjesenja 
					JOIN korisnik USING(korisnikid) 
					JOIN zadatak USING(zadatakid) 
					WHERE slug = %s AND korisnickoime = %s
					ORDER BY vrijemepredaje 
					DESC LIMIT 1""", slug, username)

class VirtualCompetition:
	def __init__(self, virt_comp_id, created_at, user_id, comp_id, tasks):
		self.virt_comp_id = virt_comp_id
		self.created_at = created_at
		self.user_id = user_id
		self.comp_id = comp_id
		self.tasks = tasks
	
	@staticmethod
	def create_virt_competition(n, username):
		tasks = Task.get_random_tasks(n)
		resp = db.query("""INSERT INTO virtnatjecanje (vrijemekreacije, korisnikid, zadaci) 
							VALUES (
								NOW(),
								(SELECT korisnikid FROM korisnik
									WHERE korisnickoime = %s),
								%s)
								RETURNING virtnatjecanjeid;""", username, tasks)

		for resp in check(db.query("""SELECT * from virtnatjecanje 
							WHERE virtnatjecanjeid = %s""", (resp,))):
			return VirtualCompetition(*resp)

	@staticmethod
	def get_virtual_competition(virtual_id):
		## could someone start someone elses virtal competition?
		for resp in check(db.query("""SELECT * FROM virtnatjecanje
							WHERE virtnatjecanjeid = %s""", virtual_id)):
			return VirtualCompetition(*resp), None
		return None, "Virtual competition does not exist"

	@staticmethod
	def get_virt_comps_from_user(username):
		virt_list = []
		for virt in db.query("""SELECT virtnatjecanjeid, natjecanjeid 
								FROM virtnatjecanje 
								JOIN korisnik
									USING(korisnikid) 
								WHERE korisnickoime = %s""", username):
			virt_list.append(virt)
		return virt_list

	@staticmethod
	def get_comp_data_for_virtual_real_comp(comp_id):
		# returns slugs and the name of the competition
		res = db.query("""SELECT zadatak.slug, imenatjecanja
							FROM natjecanje
							JOIN zadatak
								USING(natjecanjeid)
							WHERE natjecanjeid = %s;""", comp_id)
		if len(res):
			return tuple([i[0] for i in res]), res[0][1]
		return tuple(), None
	
	@staticmethod
	def get_slugs_from_ids_from_virt(virt_id):
		task_slug_list = []
		for task in check(db.query("""SELECT slug
								FROM zadatak
								WHERE zadatakid IN(SELECT unnest(zadaci)
													FROM virtnatjecanje
													WHERE virtnatjecanjeid = %s)""",
													virt_id)):
			task_slug_list.append(task[0])
		return task_slug_list
	
	@staticmethod
	def insert_real_into_virt(username, slug):
		return db.query("""INSERT INTO virtnatjecanje
								(vrijemekreacije, korisnikid, natjecanjeid)
							VALUES(NOW(), 
									(SELECT korisnikid FROM korisnik WHERE korisnickoime = %s), 
									(SELECT natjecanjeid FROM natjecanje WHERE slug = %s))
							RETURNING virtnatjecanjeid;""", username, slug)
