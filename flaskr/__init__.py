import os

from flask import Flask, g

def create_app(test_config=None):

    folder_database = './database'

    # create and config the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY = 'dev',
        DATABASE = os.path.join(folder_database, 'flaskr.sqlite'),
    )

    if test_config is None:
        # load the instance config, if it exists
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)
    
    # ensure the instance folder exists
    try:
        os.makedirs(folder_database)
    except OSError:
        pass

    # a simple page that says hello
    @app.route('/hello')
    def hello():
        return 'Hello, World!'
    
    from flaskr import db
    db.init_app(app)

    from flaskr import auth
    app.register_blueprint(auth.bp)
    
    from flaskr import blog
    app.register_blueprint(blog.bp)
    app.add_url_rule('/', endpoint='index')

    from flaskr import predictions
    app.register_blueprint(predictions.bp)

    from flaskr import results
    app.register_blueprint(results.bp)

    return app

app = create_app()