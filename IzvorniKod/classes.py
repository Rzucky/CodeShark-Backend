class Korisnik:
	def __init__(self, korisnickoime, slikaprofila, lozinka, ime, prezime, email, titula = 'amater', nivouprava = 1):
		self.korisnickoime = korisnickoime
		self.slikaprofila = slikaprofila
		self.lozinka = lozinka #possible leaks?
		self.ime = ime
		self.prezime = prezime
		self.email = email
		self.titula = titula
		self.nivouprava = nivouprava


	def __get_id(self, cursor):
		cursor.execute("""SELECT korisnikid FROM korisnik WHERE korisnickoime = %s;""", (self.korisnickoime,))
		self.korisnikid = cursor.fetchone()
		print(self.korisnikid)



	def calc_successfully_solved(self, cursor):
		self.__get_id(cursor)

		cursor.execute("""SELECT COUNT (DISTINCT zadatakid) AS BrojTocnoRijesenih
							FROM uploadrjesenja
						WHERE korisnikid = %s AND prolaznost = 1;""", (self.korisnikid,))
		num_correctly_solved = (cursor.fetchone())[0]
		print(f"num solved : {num_correctly_solved}")
		if num_correctly_solved == 0:
			num_correctly_solved = 1

		cursor.execute("""SELECT COUNT (DISTINCT  zadatakid) AS BrojIsprobanih
							FROM uploadrjesenja
						WHERE korisnikid = %s;""", (self.korisnikid,))
		num_attempted = (cursor.fetchone())[0]
		print(f"num attempted : {num_attempted}")
		if num_attempted == 0:
			num_attempted = 3

		self.solved = num_correctly_solved
		self.attempted = num_attempted
		
		#just in case
		if self.attempted != 0:
			return self.solved / self.attempted
		else:
			return 0
