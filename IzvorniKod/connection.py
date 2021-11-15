from flask import Flask
from flask_restful import Api, Resource

app = Flask(__name__)
api = Api(app)

id_list = ['1', '2']

class FirstTest(Resource):
	def get(self,given_id):
		if given_id in id_list:
			return {"data":f"{given_id} is allowed"}
		else:
			return {"data":"Error"}, 
			418

	def post(self,given_id):
		return {"data":"First test passed"}


api.add_resource(FirstTest, "/test/<string:given_id>")


# @app.route("/")
# def hello():
#     return "Hello World!"

if __name__  == "__main__":
	app.run(debug=True)