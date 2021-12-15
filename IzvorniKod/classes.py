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
		self.korisnik_id = cursor.fetchone()
		print(self.korisnik_id)


	def check_activated(self, cursor):
		cursor.execute("""SELECT aktivan FROM korisnik WHERE korisnickoime = %s;""", (self.korisnicko_ime,))
		db_response = cursor.fetchone()[0]
		return db_response


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

class Trofej:
	def __init__(self, trofej_id, ime_trofeja, slika_trofeja):
		self.trofej_id = trofej_id
		self.ime_trofeja = ime_trofeja
		self.slika_trofeja = slika_trofeja

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

class TestPrimjeri:
	def __init__(self, ulaz, izlaz, zadatak_id):
		self.ulaz = ulaz
		self.izlaz = izlaz
		self.zadatak_id = zadatak_id

class UploadRjesenja:
	def __init__(self, predano_rjesenje, prolaznost, vrijeme_predaje, prosj_vrijeme_izvrsenja, natjecanje_traje, korisnik_id, zadatak_id):
		self.predano_rjesenje = predano_rjesenje
		self.prolaznost = prolaznost
		self.vrijeme_predaje = vrijeme_predaje
		self.prosj_vrijeme_izvrsenja = prosj_vrijeme_izvrsenja
		self.natjecanje_traje = natjecanje_traje
		self.korisnik_id = korisnik_id
		self.zadatak_id = zadatak_id

class VirtualnoNatjecanje:
	def __init__(self, korisnik_id, natjecanje_id, rand_zad_tezine_2, rand_zad_tezine_3, rand_zad_tezine_4, rand_zad_tezine_5):
		self.korisnik_id = korisnik_id
		self.natjecanje_id = natjecanje_id
		self.rand_zad_tezine_2 = rand_zad_tezine_2
		self.rand_zad_tezine_3 = rand_zad_tezine_3
		self.rand_zad_tezine_4 = rand_zad_tezine_4
		self.rand_zad_tezine_5 = rand_zad_tezine_5
