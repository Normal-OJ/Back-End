from flask import Flask

from model import auth_api, test_api

# Create a flask app
app = Flask(__name__)
app.url_map.strict_slashes = False

# Regist flask blueprint
app.register_blueprint(auth_api, url_prefix='/auth')
app.register_blueprint(test_api, url_prefix='/test')

if __name__ == '__main__':
	app.run()
