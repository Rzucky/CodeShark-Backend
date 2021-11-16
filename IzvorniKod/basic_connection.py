from flask import Flask, request
from flask_restful import Api

import psycopg2

from classes import Korisnik 

app = Flask(__name__)
api = Api(app)


def connect_to_db():
    conn = psycopg2.connect(host="161.97.182.243", database="codeshark", user="codeshark_user", password="kmice")
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
    resp = cursor.fetchone()[1:]
    print(resp)
    user = Korisnik(*resp)
    return user


#def pass_hashing()


@app.route('/login', methods=['POST'])
def login():

    conn, cursor = connect_to_db()
    with conn, cursor:
        if request.method == 'POST':
            data = request.json

            user = get_user(cursor, data["korisnickoime"])

        
            user_existance = check_if_user_exists(cursor, user.korisnickoime, user.email)
            if user_existance:
                #TODO hashing password
                cursor.execute("""SELECT * from korisnik WHERE korisnickoime = %s AND lozinka = %s""", (data["korisnickoime"],  data["lozinka"],))
                db_response = cursor.fetchone()

                if db_response is not None:
                    return {"data": "successfully logged in"}, 200
                
                return {"error": "wrong password"}, 400

            return {"error": "user doesn't exist or wrong username"}, 400

        
        return {"error": "not POST requst"}, 400


@app.route('/register', methods=['POST'])
def register():
    conn, cursor = connect_to_db()
    
    if request.method == 'POST':
        data = request.json
        print(data)

        user = Korisnik(data["korisnickoime"], data["slikaprofila"], data["lozinka"], data["ime"], data["prezime"], data["email"], data["titula"], data["nivouprava"])
        print(f"user: {user}")
        output = user.calc_successfully_solved(cursor)
        print(f"output: {output}")


        user_existance, error = check_if_user_exists(cursor, user.korisnickoime, user.email)
        if user_existance:
            return {"error": error}, 400
           
        
        cursor.execute("""INSERT INTO korisnik
                                    (korisnickoime, slikaprofila, lozinka, ime, prezime, email, titula, nivouprava)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s);""",
                         (user.korisnickoime, user.slikaprofila, user.lozinka, user.ime, user.prezime, user.email, user.titula, user.nivouprava))
        conn.commit()
       
        return {"data": "successfully registered user"}, 200

    else:
        return {"error": "not POST requst"}, 400

if __name__  == "__main__":
	app.run(debug=True)