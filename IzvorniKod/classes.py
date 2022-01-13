import hashlib
import json
from slugify import slugify
from enum import IntEnum
import time

class Rank(IntEnum):
	COMPETITOR = 1
	LEADER = 2
	ADMIN = 3

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

	def calc_successfully_solved(self, cursor):
		cursor.execute("""SELECT COUNT (DISTINCT zadatakid)
						FROM uploadrjesenja	JOIN korisnik 
						USING(korisnikid) 
						WHERE korisnickoime = %s AND prolaznost = 1;""", (self.username,))
		num_correctly_solved = (cursor.fetchone())[0]
		
		# currently for testing purposes
		if num_correctly_solved == 0:
			num_correctly_solved = 1

		cursor.execute("""SELECT COUNT (DISTINCT  zadatakid)
						FROM uploadrjesenja	JOIN korisnik 
						USING(korisnikid) 
						WHERE korisnickoime = %s""", (self.username,))
		num_attempted = (cursor.fetchone())[0]

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

	def check_activated(self, cursor):
		cursor.execute("""SELECT aktivan FROM korisnik 
					WHERE korisnickoime = %s;""", (self.username,))
		db_response = cursor.fetchone()[0]
		return db_response

	def get_created_competitons(self, cursor):
		cursor.execute("""SELECT natjecanje.* 
					FROM natjecanje JOIN korisnik 
					ON(korisnikid = autorid) 
					WHERE korisnik.korisnickoime =  %s;""", (self.username,))
		lst = []
		for comp in cursor.fetchall():
			lst += [Competition(*comp)]
		return lst

	def get_submitted_solutions(self, cursor):
		cursor.execute("""SELECT uploadrjesenja.* 
					FROM uploadrjesenja JOIN korisnik 
					USING(korisnikid) 
					WHERE korisnickoime = %s LIMIT 10;""", (self.username,))
		lst = []
		for comp in cursor.fetchall():
			lst += [UploadedSolution(*comp)]
		return lst
	
	@classmethod
	def generate_pfp_filename(cls, uname):
		hsh = cls.hash_pfp_filename(f"{uname}+{time.time()}") # (call static)
		return f"pfp_{hsh}"

	@staticmethod
	def get_token_time(cursor, token):
		cursor.execute("""SELECT tokengeneriran FROM korisnik 
						WHERE token = %s;""", (token,))
		token_timestamp = cursor.fetchone()
		if token_timestamp is not None:
			return token_timestamp[0]
		return None

	@staticmethod
	def set_activated(cursor, token):
		# Activating user
		cursor.execute("""UPDATE korisnik SET aktivan = %s 
						WHERE token = %s;""", (True, token,))
		# Removing token from db
		cursor.execute("""UPDATE korisnik SET token = %s, tokengeneriran = %s 
						WHERE token = %s;""", (None, None, token,))

	@staticmethod
	def hash_password(plainpass):
		return hashlib.sha256(plainpass.encode('utf-8')).hexdigest()

	@staticmethod
	def hash_pfp_filename(username): # not the best name but leave for compatibility
		return hashlib.md5(username.encode('utf-8')).hexdigest()

	@staticmethod
	def get_users_asc(cursor):
		user_list = []
		cursor.execute("""SELECT korisnickoime, slikaprofila, ime, prezime
						FROM korisnik
						ORDER BY korisnickoime ASC;""")
		users = cursor.fetchall()
		for user in users:
			user_list.append({
				"username": f"{user[0]}",
				"pfp_url": f"{user[1]}",
				"name_last_name": f"{user[2]} {user[3]}"
			})
		return user_list

	@staticmethod
	def check_if_user_exists(cursor, username, email):
		# checking for taken username and email
		cursor.execute("""SELECT * FROM korisnik 
						WHERE email = %s;""", (email,))
		db_response = cursor.fetchone()
		if db_response is not None:
			return True, "Email already in use"

		cursor.execute("""SELECT * FROM korisnik 
						WHERE korisnickoIme = %s;""", (username,))
		db_response = cursor.fetchone()
		if db_response is not None:
			return True, "Username taken"
		return False, None

	@staticmethod
	def get_user(cursor, username):
		cursor.execute("""SELECT * FROM korisnik 
						WHERE korisnickoime = %s;""", (username,))
		resp = cursor.fetchone()
		if resp is not None:
			# ignore user ID and token related elements
			resp = resp[1:-3] 
			user = User(*resp)
			return user
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

	def get_competition(cursor, comp_slug):
		cursor.execute("""SELECT * FROM natjecanje 
						WHERE slug = %s""", (comp_slug,))
		resp = cursor.fetchone()
		if resp is not None:
			comp = Competition(*resp)
			return comp, None
		return None, "Competition does not exist"

	@staticmethod
	def get_n_closest_competitions(cursor, n):
		comp_list = []
		# gets competitions closes to the start time
		cursor.execute("""SELECT * FROM natjecanje
					WHERE (CURRENT_TIMESTAMP < vrijemekraj)
					ORDER BY vrijemepoc ASC
					LIMIT %s;""", (n,))
		resp = cursor.fetchall()
		for comp in resp:
			comp_ins = Competition(*comp)
			comp_list.append(comp_ins)
		
		# format to the form to show on front page and comp page
		competition_list = Competition.format_competitions(cursor, comp_list)
		return competition_list

	@staticmethod
	def format_competitions(cursor, comp_list_instances):
		competition_list = []
		for comp in comp_list_instances:
			comp_class_name, error = Competition.get_class_name_from_class_id(cursor, comp.comp_class_id)
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
	def get_tasks_in_comp(cursor, comp_slug):
		cursor.execute("""SELECT zadatak.slug 
					FROM zadatak JOIN natjecanje USING(natjecanjeid) 
					WHERE natjecanje.slug = %s""", (comp_slug,))
		resp = cursor.fetchall()
		task_slug_list = []
		for task in resp:
			task_slug_list.append(task[0])
		return task_slug_list

	@staticmethod
	def get_class_name_from_class_id(cursor, class_id):
		cursor.execute("""SELECT nazivklasenatjecanja 
					FROM klasanatjecanja 
					WHERE idklasenatjecanja = %s""", (class_id,))
		resp = cursor.fetchone()
		if resp is not None:
			return resp[0], None
		return None, "Class name doesn't exist"

	@staticmethod
	def create_competition(cursor, data, trophy_file):
		tasks = json.loads(data["tasks"])
		slug = slugify(data["comp_name"])

		try:
			cursor.execute(f"""SELECT trofejid
								FROM trofej
								WHERE slikatrofeja = %s;""", (trophy_file,))
			trophy_id = cursor.fetchone()[0]
		except Exception as e:
			return None, "Trophy does not exist"

		try:
			cursor.execute("""INSERT INTO natjecanje(imenatjecanja, slug, tekstnatjecanja, vrijemekraj, 
													vrijemepoc, slikatrofeja, brojzadataka, 
													autorid, idklasenatjecanja, trofejid)
							VALUES(%s, %s ,%s, %s, %s, %s, %s,
								(SELECT korisnikid FROM korisnik WHERE korisnickoime = %s),
								%s, %s) 
								RETURNING slug, natjecanjeid""",
							(data["comp_name"], slug, data["comp_text"], data["end_time"], 
							data["start_time"], trophy_file, len(tasks),
							data["username"], 1, trophy_id,))
			resp = cursor.fetchone()
			comp_slug, comp_id = resp[0], resp[1]
			
		except Exception as e:
			return None, "Error while creating competition"
		
		# only public the tasks if the competition was successful
		for task_slug in tasks:
			cursor.execute("""UPDATE zadatak
								SET natjecanjeid = %s, 
									privatnost = false
								WHERE zadatak.slug = %s;"""
						,(comp_id, task_slug.strip()))
		return comp_slug, None
	

	@staticmethod
	def check_if_comp_slug_exists(cursor, slug):
		cursor.execute("""SELECT * FROM natjecanje
						WHERE slug = %s""", (slug,))
		resp = cursor.fetchone()
		if resp is not None:
			return True
		return False


class Trophy:
	def __init__(self, trophy_id, trophy_name, trophy_img):
		self.trophy_id = trophy_id
		self.trophy_name = trophy_name
		self.trophy_img = trophy_img

	@staticmethod
	def user_trophies(cursor, username):
		cursor.execute("""SELECT trofejid, imetrofeja, slikatrofeja 
						FROM jeosvojio JOIN korisnik 
						USING(korisnikid) NATURAL JOIN trofej
						WHERE korisnickoime =  %s;""", (username,))
		trophies = cursor.fetchall()
		trophies_list = []
		for trophy in trophies:
			trophies_list.append(Trophy(*trophy))

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
	def get_all_public_tasks(cursor):
		public_tasks = []
		cursor.execute("""SELECT * FROM zadatak 
						WHERE privatnost = false 
						LIMIT 50;""")
		tasks = cursor.fetchall()

		for task in tasks:
			task_ins = Task(*task)
			public_tasks.append(task_ins)

		return public_tasks		

	# used to create random tasks with an uniform spread of difficulty
	@staticmethod
	def get_random_tasks(cursor, n):
		# if just 1, fully random
		if n == 1:
			cursor.execute("""SELECT zadatakid FROM zadatak 
						WHERE privatnost = false
						ORDER BY RANDOM ()
						LIMIT 1;""")
			return cursor.fetchone()[0]

		task_list = set()
		cursor.execute("""SELECT COUNT(DISTINCT zadatakid) 
						FROM zadatak WHERE privatnost = false;""")
		count = cursor.fetchone()[0]
		if n  > 10 or n > count:
			n = min(10, count)
		
		# ceil function without importing math
		easier_n = n // 2 + (n % 2 > 0)
		harder_n = n - easier_n

		# easier tasks
		cursor.execute("""SELECT zadatakid FROM zadatak 
						WHERE privatnost = false 
						AND bodovi IN(1, 2, 3)
						ORDER BY RANDOM ()
						LIMIT %s;""", (easier_n,))
		resp = cursor.fetchall()
		for i in resp:
			task_list.add(i[0])

		# harder tasks
		cursor.execute("""SELECT zadatakid FROM zadatak 
						WHERE privatnost = false 
						AND bodovi IN(3, 4, 5)
						ORDER BY RANDOM ()
						LIMIT %s""", (harder_n,))
		resp = cursor.fetchall()
		for i in resp:
			task_list.add(i[0])

		# if there aren't enough tasks of some kind, add randoms
		if len(task_list) < n:
			cursor.execute("""SELECT zadatakid FROM zadatak 
						WHERE privatnost = false
						ORDER BY RANDOM ()
						LIMIT %s""", (n - len(task_list),))
		resp = cursor.fetchall()
		for i in resp:
			task_list.add(i[0])	

		# in case we get a duplicate task, 
		# keeps trying until it finds a new one 
		while(len(task_list) < n):
			cursor.execute("""SELECT zadatakid FROM zadatak 
						WHERE privatnost = false
						ORDER BY RANDOM ()
						LIMIT 1""")
			task = cursor.fetchone()[0]
			if task is not None:
				task_list.add(task)
			else:
				# no tasks remaining
				return list(task_list)
		return list(task_list)

	@staticmethod
	def get_task(cursor, slug):
		cursor.execute("""SELECT * FROM zadatak 
						WHERE slug = %s;""", (slug,))
		resp = cursor.fetchone()
		if resp is not None:
			task = Task(*resp)
			if task.private == True:
				# we won't give info if the task is private or not
				return None, "Task does not exist"
			
			return task, None

		return None, "Task does not exist"

	@staticmethod
	def get_author_name(cursor, slug):
		cursor.execute("""SELECT ime, prezime 
					FROM zadatak JOIN korisnik 
					ON(korisnikid = autorid)
					WHERE zadatak.slug = %s;""", (slug,))	
		resp = cursor.fetchone()

		return resp[0], resp[1]

	@staticmethod
	def get_author_name_from_comp_slug(cursor, comp_slug):
		cursor.execute("""SELECT ime, prezime 
					FROM korisnik JOIN natjecanje 
					ON(autorid = korisnikid)
					WHERE slug =  %s;""", (comp_slug,))	
		resp = cursor.fetchone()

		return resp[0], resp[1]

	@staticmethod
	def get_recent_tasks(cursor):
		task_list = []
		cursor.execute("""SELECT * FROM zadatak 
					WHERE privatnost = false
					ORDER BY zadatakid DESC LIMIT 5;""")
		resp = cursor.fetchall()
		for task in resp:
			task_ins = Task(*task)
			task_list.append(task_ins)
		
		return task_list

	@staticmethod
	def get_private_tasks(cursor, username):
		task_list = []
		cursor.execute("""SELECT zadatak.* FROM zadatak 
					JOIN korisnik ON(korisnikid = autorid) 
					WHERE privatnost = true 
					AND korisnickoime = %s""", (username,))
		resp = cursor.fetchall()
		for task in resp:
			task_ins = Task(*task)
			task_list.append(task_ins)
		
		return task_list

	# used at profile page to show the name
	@staticmethod
	def get_task_name(cursor, id):
		cursor.execute("""SELECT imezadatka FROM zadatak
						WHERE zadatakid = %s""", (id,))
		return cursor.fetchone()[0]		

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

class VirtualCompetition:
	def __init__(self, virt_comp_id, created_at, user_id, comp_id, tasks):
		self.virt_comp_id = virt_comp_id
		self.created_at = created_at
		self.user_id = user_id
		self.comp_id = comp_id
		self.tasks = tasks

	@staticmethod
	def create_virt_competition(conn, cursor, n, username):
		tasks = Task.get_random_tasks(cursor, n)
		cursor.execute("""INSERT INTO virtnatjecanje (vrijemekreacije, korisnikid, zadaci) 
						VALUES (
							NOW(),
							(SELECT korisnikid FROM korisnik
								WHERE korisnickoime = %s),
							%s)
							RETURNING virtnatjecanjeid;""", (username, tasks))
		resp = (cursor.fetchone())[0]
		conn.commit()

		cursor.execute("""SELECT * from virtnatjecanje 
						WHERE virtnatjecanjeid = %s""", (resp,))

		return VirtualCompetition( *(cursor.fetchone()))

	@staticmethod
	def get_virtual_competition(cursor, virtual_id):
		## could someone start someone elses virtal competition?
		cursor.execute("""SELECT * FROM virtnatjecanje
						WHERE virtnatjecanjeid = %s""", (virtual_id,))
		resp = cursor.fetchone()
		if resp is not None:
			return VirtualCompetition(*resp), None
		return None, "Virtual competition does not exist"

	@staticmethod
	def get_virt_comps_from_user(cursor, username):
		cursor.execute("""SELECT virtnatjecanjeid, natjecanjeid 
					FROM virtnatjecanje 
					JOIN korisnik USING(korisnikid) 
					WHERE korisnickoime = %s""", (username,))
		virt_list = []
		resp = cursor.fetchall()
		for virt in resp:
			virt_list.append(virt)
		return virt_list

	@staticmethod
	def get_comp_data_for_virtual_real_comp(cursor, comp_id):
		# returns slugs and the name of the competition
		cursor.execute("""SELECT zadatak.slug, imenatjecanja
						FROM natjecanje JOIN zadatak
						USING(natjecanjeid)
						WHERE natjecanjeid = %s;""", (comp_id,))
		res = cursor.fetchall()
		if len(res):
			return tuple([i[0] for i in res]), res[0][1]
		return tuple(), None
	
	@staticmethod
	def get_slugs_from_ids_from_virt(cursor, virt_id):
		cursor.execute("""SELECT slug
						FROM zadatak	
						WHERE zadatakid IN(SELECT unnest(zadaci)
											FROM virtnatjecanje
											WHERE virtnatjecanjeid = %s)"""
											,(virt_id,))
		resp = cursor.fetchall()
		task_slug_list = []
		for task in resp:
			task_slug_list.append(task[0])
		return task_slug_list
	
	@staticmethod
	def insert_real_into_virt(cursor, username, slug):
		cursor.execute("""INSERT INTO virtnatjecanje
					(vrijemekreacije, korisnikid, natjecanjeid)
					VALUES(NOW(), 
							(SELECT korisnikid FROM korisnik WHERE korisnickoime = %s), 
							(SELECT natjecanjeid FROM natjecanje WHERE slug = %s)) RETURNING virtnatjecanjeid;"""
					,(username, slug,))
		return cursor.fetchone()[0]
		