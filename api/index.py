from datetime import datetime
from flask import Flask, flash, render_template, request, redirect, url_for
from flask_bootstrap import Bootstrap5
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, URLField, TextAreaField
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms.validators import DataRequired
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
from flask_mailman import Mail, EmailMessage
from supabase import create_client, Client

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_ANON_KEY")
supabase: Client = create_client(url, key)

class UploadProject(FlaskForm):
    project_url = URLField('Enter Project URL', validators=[DataRequired()])
    title = StringField('Project Title', validators=[DataRequired()])
    description = TextAreaField('Project Description', validators=[DataRequired()])
    image = FileField('Project Image', validators=[
        FileRequired(),
        FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')
    ])
    submit = SubmitField('Submit Project')

class ContactMe(FlaskForm):
    name = StringField('Your Name', validators=[DataRequired()])
    email = StringField('Your Email', validators=[DataRequired()])
    message = TextAreaField('Your Message', validators=[DataRequired()])
    submit = SubmitField('Send Message')


# Point template_folder and static_folder one level up to the root
app = Flask(
    __name__,
    template_folder='../templates',
    static_folder='../static',
)

bootstrap = Bootstrap5(app)
# Load secret key with a clear dev fallback and visible warning
secret = os.getenv('SECRET_KEY')
if not secret:
    print("WARNING: SECRET_KEY not set in environment; using insecure development key.")
app.config['SECRET_KEY'] = secret or 'dev-secret'

# Load DB URI with a safe sqlite fallback for local development
db_uri = os.getenv('DATABASE_URI')
if not db_uri:
    fallback = os.path.join(os.getcwd(), 'app.db')
    db_uri = f"sqlite:///{fallback}"
    print(f"INFO: DATABASE_URI not set; falling back to {db_uri}")
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False  # MUST be False for Port 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_SERVER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_APP_PASSWORD')

mail = Mail(app)

# Initialize SQLAlchemy with a resilient fallback. On some serverless hosts
# a DB driver (e.g. psycopg2) may be unavailable; catch init errors and
# fall back to an ephemeral sqlite DB so the process doesn't crash with
# ModuleNotFoundError during import.
try:
    db = SQLAlchemy(app)
    migrate = Migrate(app, db)
except Exception as e:
    # Log the failure and switch to a safe sqlite fallback in /tmp
    print(f"ERROR: SQLAlchemy init failed: {e}")
    fallback = 'sqlite:////tmp/app.db'
    print(f"Falling back to sqlite database at {fallback}")
    app.config['SQLALCHEMY_DATABASE_URI'] = fallback
    db = SQLAlchemy(app)
    migrate = Migrate(app, db)

# Provide a cache-busting version for static assets (falls back to 1)
try:
    css_path = os.path.join(app.root_path, 'static', 'styles', 'styles.css')
    app.jinja_env.globals['static_version'] = int(os.path.getmtime(css_path))
except Exception:
    app.jinja_env.globals['static_version'] = 1

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_url = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200), nullable=False)


@app.route('/', methods=['POST', 'GET'])
def home():
    form=ContactMe()
    projects = Project.query.all() 
    current_year = datetime.now().year
    is_admin = request.args.get('admin') == '1234'
    return render_template('index.html', projects=projects, current_year=current_year, is_admin=is_admin, form=form)


@app.route('/admin', methods=['POST', 'GET'])
def admin():
    admin_key = request.args.get('admin')
    if admin_key != '1234':
        return "Unauthorized", 403

    form = UploadProject()
    if form.validate_on_submit():
        title = form.title.data
        url = form.project_url.data
        description = form.description.data
        f = form.image.data
        filename = secure_filename(f.filename)
        file_content = f.read()
        supabase.storage.from_('project-images').upload(
            path=filename,
            file=file_content,
            file_options={"content-type": f.content_type}
        )

        image_url = supabase.storage.from_('my-portfolio-storage').get_public_url(filename)

        new_project = Project(
            project_url=url,
            title=title,
            description=description,
            image=image_url
        )
        db.session.add(new_project)
        db.session.commit()
        print("New project added to the database.")
        return redirect(url_for('home'))

    return render_template('admin.html', form=form, hide_nav=True, admin_key=admin_key, is_admin=True)


@app.route('/delete/<int:project_id>', methods=['POST'])
def delete_project(project_id):
    if request.args.get('admin') != '1234':
        return "Unauthorized", 403
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    return redirect(url_for('home'))


@app.route('/contact_me', methods=['GET', 'POST'])
def contact_me():
    form=ContactMe()
    try:
        if form.validate_on_submit():
            # 1. Create a formatted string for the body
            full_message_body = (
                f"Name: {form.name.data}\n"
                f"Email: {form.email.data}\n\n"
                f"Message:\n{form.message.data}"
            )

            msg = EmailMessage(
                subject=f"New Portfolio Message from {form.name.data}",
                body=full_message_body,
                from_email=app.config['MAIL_USERNAME'], # Your authenticated Gmail
                to=["kenengbusiness@gmail.com"],         # Sending it to yourself
                reply_to=[form.email.data]               # Clicking 'Reply' will email the sender
            )
            
            msg.send()
            flash("Email sent successfully!", "success")
            return redirect(url_for('home'))

    except Exception as e:
        print(f"Failed to send email: {e}")
        flash("Failed to send email. Please try again later.", "danger")

    print('Form validation failed.')
    return render_template('contact.html', form=form)

# @app.route('/x-handle')
# def x_handle():
    


if __name__ == '__main__':
    app.run(debug=True)


# Register a simple 500 handler that logs the exception for easier debugging
@app.errorhandler(500)
def internal_error(error):
    app.logger.exception('Server Error: %s', error)
    return 'Internal Server Error', 500

