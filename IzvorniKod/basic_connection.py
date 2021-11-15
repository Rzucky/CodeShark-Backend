from flask import Flask, request
from flask_restful import Api, Resource

import random
import psycopg2


app = Flask(__name__)
api = Api(app)



def connect_to_db():
    conn = psycopg2.connect(host="161.97.182.243", database="codeshark", user="codeshark_user", password="kmice")
    cursor = conn.cursor()
    return conn, cursor


# id_list = ['1', '2']
# class FirstTest(Resource):
# 	def get(self,given_id):
# 		if given_id in id_list:
# 			return {"data":f"{given_id} is allowed"}
# 		else:
# 			return {"data":"Error"}, 
# 			418

# 	def post(self,given_id):
# 		return {"data":"First test passed"}


# api.add_resource(FirstTest, "/test/<string:given_id>")

@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        data = request.json
        print(data)
        conn, cursor = connect_to_db()
        random_num = random.randint(1,400)
        cursor.execute("""INSERT into korisnik
                                    (korisnikid, korisnickoime, slikaprofila, lozinka, ime, prezime, email, titula, nivouprava)
                         VALUES (%s ,%s, %s, %s, %s, %s, %s, %s, %s);""",
                         (random_num, data["korisnickoime"], "juan.png", data["lozinka"], data["ime"], data["prezime"], data["email"], 'amater',data["nivouprava"], ))
        conn.commit()
        #print("success")
        return {}, 200
    else:
        return {}, 400

if __name__  == "__main__":
	app.run(debug=True)