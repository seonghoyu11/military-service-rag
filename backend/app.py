from flask import Flask
from flask_cors import CORS

from routes.query import query_bp


def create_app():
    app = Flask(__name__)
    CORS(app)
    app.register_blueprint(query_bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5001)