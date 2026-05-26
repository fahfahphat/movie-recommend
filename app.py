from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required,
    logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'netflix_secret_key'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

CSV_FILE = 'users.csv'
RATING_FILE = 'ratings.csv'
MOVIE_FILE = 'movies.csv'

# =========================
# INIT FILES
# =========================

if not os.path.exists(RATING_FILE):
    pd.DataFrame(columns=['username', 'movie', 'genre', 'rating']).to_csv(RATING_FILE, index=False)

if not os.path.exists(CSV_FILE):
    pd.DataFrame(columns=['id', 'username', 'password']).to_csv(CSV_FILE, index=False)

# =========================
# USER CLASS
# =========================

class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    df = pd.read_csv(CSV_FILE)
    user = df[df['id'] == int(user_id)]

    if not user.empty:
        return User(
            user.iloc[0]['id'],
            user.iloc[0]['username'],
            user.iloc[0]['password']
        )
    return None

# =========================
# MOVIES
# =========================

def load_movies():
    return pd.read_csv(MOVIE_FILE).to_dict(orient="records")

# =========================
# HOME
# =========================

@app.route('/')
def home():

    movies_df = pd.read_csv(MOVIE_FILE)
    ratings_df = pd.read_csv(RATING_FILE)

    ratings_df['rating'] = ratings_df['rating'].astype(int)

    summary = ratings_df.groupby('movie').agg(
        avg_rating=('rating', 'mean'),
        count=('rating', 'count')
    ).reset_index()

    movies_df = movies_df.merge(
        summary,
        left_on='title',
        right_on='movie',
        how='left'
    )

    movies_df.drop(columns=['movie'], inplace=True)

    movies_df['avg_rating'] = movies_df['avg_rating'].fillna(0).round(1)
    movies_df['count'] = movies_df['count'].fillna(0).astype(int)

    return render_template(
        'index.html',
        movies=movies_df.to_dict(orient='records')
    )

# =========================
# REGISTER
# =========================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        df = pd.read_csv(CSV_FILE)

        if username in df['username'].values:
            flash('Username already exists')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_id = 1 if df.empty else df['id'].max() + 1

        new_user = pd.DataFrame([{
            'id': new_id,
            'username': username,
            'password': hashed_password
        }])

        df = pd.concat([df, new_user], ignore_index=True)
        df.to_csv(CSV_FILE, index=False)

        flash('Register success!')
        return redirect(url_for('login'))

    return render_template('register.html')

# =========================
# LOGIN
# =========================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        df = pd.read_csv(CSV_FILE)
        user = df[df['username'] == username]

        if not user.empty:
            stored_password = user.iloc[0]['password']

            if check_password_hash(stored_password, password):
                login_user(User(
                    user.iloc[0]['id'],
                    username,
                    stored_password
                ))
                return redirect(url_for('home'))

        flash('Invalid username or password')

    return render_template('login.html')

# =========================
# SAVE RATING (FIXED)
# =========================

@app.route('/save_rating', methods=['POST'])
@login_required
def save_rating():

    movie = request.form['movie']
    genre = request.form['genre']

    # 🔥 FIX: convert to int
    rating = int(request.form['rating'])

    username = current_user.username

    df = pd.read_csv(RATING_FILE)

    existing = df[
        (df['username'] == username) &
        (df['movie'] == movie)
    ]

    if not existing.empty:
        df.loc[
            (df['username'] == username) &
            (df['movie'] == movie),
            'rating'
        ] = rating
    else:
        new_row = pd.DataFrame([{
            'username': username,
            'movie': movie,
            'genre': genre,
            'rating': rating
        }])

        df = pd.concat([df, new_row], ignore_index=True)

    # 🔥 ensure correct type
    df['rating'] = df['rating'].astype(int)

    df.to_csv(RATING_FILE, index=False)

    # 🔥 return JSON for realtime frontend
    return jsonify({'status': 'ok', 'rating': rating})

# =========================
# RECOMMEND (FIXED TYPE SAFE)
# =========================

@app.route('/recommend')
@login_required
def recommend():

    ratings_df = pd.read_csv(RATING_FILE)
    movies_df = pd.read_csv(MOVIE_FILE)

    user_ratings = ratings_df[
        ratings_df['username'] == current_user.username
    ]

    if user_ratings.empty:
        return render_template('recommend.html', recommendations=[])

    # safe conversion
    user_ratings['rating'] = user_ratings['rating'].astype(int)

    favorite_genre = (
        user_ratings
        .groupby('genre')['rating']
        .mean()
        .idxmax()
    )

    recommendations = movies_df[
        movies_df['genre'] == favorite_genre
    ]

    return render_template(
        'recommend.html',
        recommendations=recommendations.to_dict(orient='records'),
        favorite_genre=favorite_genre
    )

# =========================
# GET RATING (FIXED)
# =========================

@app.route('/get_rating/<movie>')
@login_required
def get_rating(movie):

    df = pd.read_csv(RATING_FILE)

    user_rating = df[
        (df['username'] == current_user.username) &
        (df['movie'] == movie)
    ]

    if not user_rating.empty:
        return jsonify({
            'rating': int(user_rating.iloc[0]['rating'])
        })

    return jsonify({'rating': 0})

# =========================
# LOGOUT
# =========================

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# =========================
# Dashboard
# =========================

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)


# =========================
# RUN
# =========================
# Run local
#if __name__ == '__main__':
   # app.run(debug=True)

# deploy Web render
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)