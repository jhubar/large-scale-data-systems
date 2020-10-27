import os
# To generate a new secret key:
# >>> import random, string
# >>> "".join([random.choice(string.printable) for _ in range(24)])

SECRET_KEY = "d:UVI?e)b8Q\t-MKh>]~&l6c8"

FB_APP_ID = 734208050641073
SQLALCHEMY_TRACK_MODIFICATIONS = True
basedir = os.path.abspath(os.path.dirname(__file__))
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
