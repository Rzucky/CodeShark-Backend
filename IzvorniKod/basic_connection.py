from flask import Flask, request
from flask_restful import Api, Resource

#import random
import psycopg2


app = Flask(__name__)
api = Api(app)


def connect_to_db():
    conn = psycopg2.connect(host="161.97.182.243", database="codeshark", user="codeshark_user", password="kmice")
    cursor = conn.cursor()
    return conn, cursor


# checking for taken username
def check_if_user_exists(cursor, username):
    cursor.execute("SELECT * FROM korisnik WHERE korisnickoIme = %s;", (username,))
    db_response = cursor.fetchone()
    print(db_response)
    if db_response is None:
        return False
    
    return True



@app.route('/login', methods=['POST'])
def login():
    _, cursor = connect_to_db()
    if request.method == 'POST':
        data = request.json
        
        user_existance = check_if_user_exists(cursor, data["korisnickoime"])
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

        user_existance = check_if_user_exists(cursor, data["korisnickoime"])
        if user_existance:
            return {"error": "username taken"}, 400
           
        
        cursor.execute("""INSERT INTO korisnik
                                    (korisnickoime, slikaprofila, lozinka, ime, prezime, email, titula, nivouprava)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s);""",
                         (data["korisnickoime"], "juan.png", data["lozinka"], data["ime"], data["prezime"], data["email"], 'amater', data["nivouprava"]))
        conn.commit()
       
        return {"data": "successfully registered user"}, 200

    else:
        return {"error": "not POST requst"}, 400

if __name__  == "__main__":
	app.run(debug=True)