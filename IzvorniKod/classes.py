import hashlib

class Korisnik:
	def __init__(self, korisnicko_ime, lozinka, slika_profila, ime, prezime, email, titula = 'amater', nivou_prava = 1):
		self.korisnicko_ime = korisnicko_ime
		self.lozinka = lozinka
		self.slika_profila = slika_profila
		self.ime = ime
		self.prezime = prezime
		self.email = email
		self.titula = titula
		self.nivou_prava = nivou_prava

	def __get_id(self, cursor):
		cursor.execute("""SELECT korisnikid FROM korisnik WHERE korisnickoime = %s;""", (self.korisnicko_ime,))
		self.korisnik_id = cursor.fetchone()[0]

	def calc_successfully_solved(self, cursor):
		self.__get_id(cursor)

		cursor.execute("""SELECT COUNT (DISTINCT zadatakid) AS BrojTocnoRijesenih
						FROM uploadrjesenja
						WHERE korisnikid = %s AND prolaznost = 1;""", (self.korisnik_id,))
		num_correctly_solved = (cursor.fetchone())[0]
		
		# currently for testing purposes
		if num_correctly_solved == 0:
			num_correctly_solved = 1

		cursor.execute("""SELECT COUNT (DISTINCT  zadatakid) AS BrojIsprobanih
						FROM uploadrjesenja
						WHERE korisnikid = %s;""", (self.korisnik_id,))
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
		cursor.execute("""SELECT aktivan FROM korisnik WHERE korisnickoime = %s;""", (self.korisnicko_ime,))
		db_response = cursor.fetchone()[0]
		return db_response

	def get_created_competitons(self, cursor):
		cursor.execute("""SELECT natjecanje.* FROM natjecanje NATURAL JOIN korisnik WHERE korisnik.korisnickoime = %s;""", (self.korisnicko_ime,))
		lst = []
		for comp in cursor.fetchall():
			lst += [Natjecanje(*comp)]
		return lst

	def get_submitted_tasks(self, cursor):
		self.__get_id(cursor)

		cursor.execute("""SELECT * FROM uploadrjesenja WHERE korisnikid = %s LIMIT 10;""", (self.korisnik_id,))
		lst = []
		for comp in cursor.fetchall():
			lst += [UploadRjesenja(*comp)]
		return lst

	@staticmethod
	def get_token_time(cursor, token):
		cursor.execute("""SELECT tokengeneriran FROM korisnik WHERE token = %s;""", (token,))
		token_timestamp = cursor.fetchone()
		if token_timestamp is not None:
			return token_timestamp[0]

		return None

	@staticmethod
	def set_activated(cursor, token):
		# Activating user
		cursor.execute("""UPDATE korisnik SET aktivan = %s WHERE token = %s;""", (True, token,))
		# Removing token from db
		cursor.execute("""UPDATE korisnik SET token = %s, tokengeneriran = %s WHERE token = %s;""", (None, None, token,))

	@staticmethod
	def hash_password(plainpass):
		return hashlib.sha256(plainpass.encode('utf-8')).hexdigest()

	@staticmethod
	def hash_pfp_filename(username):
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
				"korisnickoime": f"{user[0]}",
				"slikaprofila": f"{user[1]}",
				"ime_prezime": f"{user[2]} {user[3]}"
			})
		return user_list

	@staticmethod
	def check_if_user_exists(cursor, username, email):
		# checking for taken username and email
		cursor.execute("SELECT * FROM korisnik WHERE email = %s;", (email,))
		db_response = cursor.fetchone()
		if db_response is not None:
			return True, "Email already in use"

		cursor.execute("SELECT * FROM korisnik WHERE korisnickoIme = %s;", (username,))
		db_response = cursor.fetchone()
		if db_response is not None:
			return True, "Username taken"

		return False, None

	@staticmethod
	def get_user(cursor, username):
		cursor.execute("SELECT * FROM korisnik WHERE korisnickoime = %s;", (username,))
		resp = cursor.fetchone()
		if resp is not None:
			# ignore user ID and token related elements
			resp = resp[1:-3] 
			user = Korisnik(*resp)
			return user

		return None

class Natjecanje:
	def __init__(self, natjecanje_id, ime_natjecanja, tekst_natjecanja, vrijeme_kraj, vrijeme_poc, slika_trofeja, broj_zadatak, autor_id, id_klase_natjecanja, trofej_id):
		self.natjecanje_id = natjecanje_id
		self.ime_natjecanja = ime_natjecanja
		self.tekst_natjecanja = tekst_natjecanja
		self.vrijeme_kraj = vrijeme_kraj
		self.vrijeme_poc = vrijeme_poc
		self.slika_trofeja = slika_trofeja
		self.broj_zadatak = broj_zadatak
		self.autor_id = autor_id
		self.id_klase_natjecanja = id_klase_natjecanja
		self.trofej_id = trofej_id

	def get_competition(cursor, comp_id):
		cursor.execute("""SELECT * FROM natjecanje 
						WHERE natjecanjeid = %s""", (comp_id,))
		resp = cursor.fetchone()
		if resp is not None:
			comp = Natjecanje(*resp)
			return comp, None
		
		return None, "Competition does not exist"

	@staticmethod
	def get_n_competitions(cursor, n):
		comp_list = []
		## needs changing to closest to start
		cursor.execute("""SELECT * FROM natjecanje
						ORDER BY natjecanjeid DESC LIMIT %s;""", (n,))
		resp = cursor.fetchall()
		for comp in resp:
			comp_ins = Natjecanje(*comp)
			comp_list.append(comp_ins)
		
		return comp_list

	@staticmethod
	def format_competitions(cursor, n):
		competition_list = []
		comp_list_instances = Natjecanje.get_n_competitions(cursor, n)
		for comp in comp_list_instances:
			competition_list.append({
				"natjecanje_id":		f"{comp.natjecanje_id}",
				"ime_natjecanja":		f"{comp.ime_natjecanja}",
				"vrijeme_pocetak":		f"{comp.vrijeme_poc}",
				"vrijeme_kraj":			f"{comp.vrijeme_kraj}",
				"slika_trofeja":		f"{comp.slika_trofeja}",
				"broj_zadataka":		f"{comp.broj_zadatak}",
				"id_klase_natjecanja":	f"{comp.id_klase_natjecanja}",
			})
		
		return competition_list

class Trofej:
	def __init__(self, trofej_id, ime_trofeja, slika_trofeja):
		self.trofej_id = trofej_id
		self.ime_trofeja = ime_trofeja
		self.slika_trofeja = slika_trofeja

	@staticmethod
	def user_trophies(cursor, user):
		trophies_list = []

		cursor.execute("""SELECT trofejid, imetrofeja, slikatrofeja 
						FROM jeosvojio NATURAL JOIN trofej natural join korisnik 
						WHERE jeosvojio.korisnikid = korisnik.korisnikid 
						AND korisnickoime =  %s;""", (user.korisnicko_ime,))
		trophies = cursor.fetchall()

		for trophy in trophies:
			trofej = Trofej(*trophy)
			trophies_list.append(trofej)

		return trophies_list

class Zadatak:
	def __init__(self, zadatak_id, ime_zadatka, bodovi, max_vrijeme_izvrsavanja, tekst_zadatka, privatnost, slag, autor_id, natjecanje_id):
		self.zadatak_id = zadatak_id
		self.ime_zadatka = ime_zadatka
		self.bodovi = bodovi
		self.max_vrijeme_izvrsavanja = max_vrijeme_izvrsavanja
		self.tekst_zadatka = tekst_zadatka
		self.privatnost = privatnost
		self.slag = slag
		self.autor_id = autor_id
		self.natjecanje_id = natjecanje_id

	@staticmethod
	def get_all_public_tasks(cursor):
		public_tasks = []
		cursor.execute("""SELECT * FROM zadatak WHERE privatnost = false limit 50;""")
		tasks = cursor.fetchall()

		for task in tasks:
			task_ins = Zadatak(*task)
			public_tasks.append(task_ins)

		return public_tasks		

	@staticmethod
	def get_random_tasks(cursor, n):
		cursor.execute("""SELECT zadatakid
						FROM zadatak WHERE zadatak.privatnost = false
						ORDER BY RANDOM () 
						limit %s;""", n)
		random_tasks = [i[0] for i in cursor.fetchall()]
	
		return random_tasks

	@staticmethod
	def get_task(cursor, slug):
		cursor.execute("""SELECT * FROM zadatak WHERE slug = %s;""", (slug,))
		resp = cursor.fetchone()
		if resp is not None:
			task = Zadatak(*resp)
			if task.privatnost == True:
				# we won't give info if the task is private or not
				return None, "Task does not exist"
			
			return task, None

		return None, "Task does not exist"

	@staticmethod
	def get_author_name(cursor, slug):
		cursor.execute("""SELECT ime, prezime 
					FROM zadatak NATURAL JOIN korisnik 
					WHERE korisnik.korisnikid = zadatak.autorid 
					AND zadatak.slug = %s;""", (slug,))	
		resp = cursor.fetchone()

		return resp[0], resp[1]

	#TODO: needs to be fixed to slug
	@staticmethod
	def get_author_name_id(cursor, id):
		cursor.execute("""SELECT ime, prezime FROM korisnik 
					WHERE korisnik.korisnikid = %s;""", (id,))	
		resp = cursor.fetchone()

		return resp[0], resp[1]

	@staticmethod
	def get_recent_tasks(cursor):
		task_list = []
		cursor.execute("""SELECT * FROM zadatak 
					WHERE privatnost=false
					ORDER BY zadatakid DESC LIMIT 5;""")
		resp = cursor.fetchall()
		for task in resp:
			task_ins = Zadatak(*task)
			task_list.append(task_ins)
		
		return task_list

class TestPrimjer:
	def __init__(self, ulaz, izlaz, zadatak_id):
		self.ulaz = ulaz
		self.izlaz = izlaz
		self.zadatak_id = zadatak_id

class UploadRjesenja:
	def __init__(self, predano_rjesenje, prolaznost, vrijeme_predaje, prosj_vrijeme_izvrsenja, korisnik_id, zadatak_id):
		self.predano_rjesenje = predano_rjesenje
		self.prolaznost = prolaznost
		self.vrijeme_predaje = vrijeme_predaje
		self.prosj_vrijeme_izvrsenja = prosj_vrijeme_izvrsenja
		self.korisnik_id = korisnik_id
		self.zadatak_id = zadatak_id

class VirtualnoNatjecanje:
	def __init__(self, virt_natjecanje_id, vrijeme_kreacije, korisnik_id, natjecanje_id, zadaci):
		self.virt_natjecanje_id = virt_natjecanje_id
		self.vrijeme_kreacije = vrijeme_kreacije
		self.korisnik_id = korisnik_id
		self.natjecanje_id = natjecanje_id
		self.zadaci = zadaci
	
	@staticmethod
	def create_virt_competition(conn, cursor, n, username):
		tasks = Zadatak.get_random_tasks(cursor, n)
		cursor.execute("""INSERT INTO virtnatjecanje (vrijemekreacije, korisnikid, zadaci) 
						VALUES ( NOW(),
							(SELECT korisnikid FROM korisnik
								WHERE korisnickoime = %s),
							%s)
							RETURNING virtnatjecanjeid;""", (username, tasks))
		resp = (cursor.fetchone())[0]
		conn.commit()

		cursor.execute("""SELECT * from virtnatjecanje WHERE virtnatjecanjeid = %s""", (resp,))
		
		return VirtualnoNatjecanje( *(cursor.fetchone()))

	@staticmethod
	def get_virtual_competition(cursor, virtual_id):
		## could someone start someone elses virtal competition?
		cursor.execute("""SELECT * FROM virtnatjecanje
						WHERE virtnatjecanjeid = %s""", (virtual_id,))
		resp = cursor.fetchone()
		if resp is not None:
			return VirtualnoNatjecanje(*resp), None

		return None, "Virtual competition does not exist"

	@staticmethod
	def get_comp_data_for_virtual(cursor, comp_id):
	#def get_comp_name(cursor, comp_id):
		## potentially change to slug in the future
		cursor.execute("""	SELECT slug, imenatjecanja
							FROM virtnatjecanje
								NATURAL JOIN natjecanje
								JOIN zadatak
									USING(natjecanjeid)
							WHERE natjecanjeid = %s;""", (comp_id,))

		res = cursor.fetchall()
		if len(res) == 0:
			return tuple(), None
		else:
			return tuple([i[0] for i in res]), res[0][1]
