import os
import logging
from flask import Flask, redirect, request, session, render_template
from last_fm_auth import get_lastfm_api_key
from last_fm_data_service import get_user_top_tracks
from recommendation_service import generate_recommendations

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        if username:
            session['username'] = username
            return redirect('/recommendations')
        else:
            return render_template('home.html', error="Please enter a Last.fm username.")
    return render_template('home.html')

@app.route('/recommendations')
def recommendations():
    username = session.get('username')
    if not username:
        return redirect('/login')
    
    try:
        logger.info(f"Fetching top tracks for user {username} from the last month...")
        top_tracks = get_user_top_tracks(username, period='1month', limit=30)
        
        if not top_tracks:
            logger.error(f"No top tracks found for user {username}")
            return render_template('recommendations.html', 
                                  tracks=[], 
                                  error=f"Unable to retrieve listening history for {username}. Please check the username and try again.")
        
        logger.info(f"Found {len(top_tracks)} top tracks")
        
        logger.info("Generating recommendations using machine learning...")
        recommended_tracks, message = generate_recommendations(top_tracks)
        
        return render_template('recommendations.html', 
                              tracks=recommended_tracks,
                              message=message)
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        return render_template('recommendations.html', 
                              tracks=[], 
                              error="An error occurred while generating recommendations. Please try again later.")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
