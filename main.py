import requests
import datetime
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pytz import timezone
import csv
import os
import MySQLdb
import time
import json
import inspect
import re
import random
import string
from bs4 import BeautifulSoup
import urllib.parse
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
from requests.exceptions import HTTPError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

# Database connection parameters
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'db': os.getenv('DB_NAME'),
}

# Spotify API credentials
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')

# Last.fm API key
LASTFM_API_KEY = os.getenv('LASTFM_API_KEY')

# Odesli API key
ODESLI_API_KEY = os.getenv('ODESLI_API_KEY')

# =============================================================================
# GLOBAL VARIABLES & DATABASE CONNECTION
# =============================================================================

# Define global variables for database connection
dtdb = None
curdt = None

def connect_to_db():
    """Establish database connection and return cursor."""
    global dtdb, curdt
    dtdb = MySQLdb.Connection(**DB_CONFIG)
    curdt = dtdb.cursor()
    dtdb.set_character_set('utf8')
    curdt.execute('SET NAMES utf8;')
    curdt.execute('SET CHARACTER SET utf8;')
    curdt.execute('SET character_set_connection=utf8;')
    return dtdb, curdt

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def lineno():
    """Returns the current line number in our program."""
    return inspect.currentframe().f_back.f_lineno

def whattimeisit():
    """Returns the current timestamp in a MySQL-friendly format."""
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")

def log_error(message, row_err):
    """Log errors to the database."""
    global dtdb, curdt
    try:
        # Make sure database is connected
        if dtdb is None or curdt is None:
            connect_to_db()
            
        sql = "INSERT INTO music_inventory.error_log(log_row, error) VALUES(%s, %s)"
        curdt.execute(sql, (row_err, message))
        dtdb.commit()
    except Exception as e:
        print(message, row_err)
        print(lineno(), e)

def create_pl_code():
    """Generate a random string for playlist codes."""
    characters = list(string.ascii_letters + string.digits + "!@#$%^&*()")
    length = 16
    random.shuffle(characters)
    password = []
    for i in range(length):
        password.append(random.choice(characters))
    random.shuffle(password)
    return "".join(password)

def normalize_string(s):
    """
    Normalize string by:
    1. Converting to lowercase
    2. Removing all non-alphanumeric characters
    3. Removing extra whitespace
    """
    # Convert to lowercase first
    s = s.lower()
    # Replace all non-alphanumeric characters (except spaces) with spaces
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    # Normalize whitespace (remove extra spaces)
    s = ' '.join(s.split())
    return s

def is_match(result, artist, album, track, check_album=True):
    """
    Check if a search result matches the target track.
    check_album: if False, skip album verification
    """
    result_artist = result['artists'][0]['name']
    result_track = result['name']
    
    # Normalize all strings for comparison
    norm_result_artist = normalize_string(result_artist)
    norm_result_track = normalize_string(result_track)
    norm_artist = normalize_string(artist)
    norm_track = normalize_string(track)
    
    # Artist should match exactly after normalization
    if norm_result_artist != norm_artist:
        return False
        
    # For track matching, compare word sets
    track_parts = set(norm_track.split())
    result_track_parts = set(norm_result_track.split())
    common_words = track_parts.intersection(result_track_parts)
    
    # Match threshold - 70% of words should match for track
    track_match_ratio = len(common_words) / max(len(track_parts), len(result_track_parts))
    
    if track_match_ratio < 0.7:
        return False
        
    # For album, check if one contains the other after normalization
    if check_album:
        result_album = result['album']['name']
        norm_result_album = normalize_string(result_album)
        norm_album = normalize_string(album)
        
        if norm_result_album and norm_album:
            album_parts = set(norm_album.split())
            result_album_parts = set(norm_result_album.split())
            common_album_words = album_parts.intersection(result_album_parts)
            album_match_ratio = len(common_album_words) / max(len(album_parts), len(result_album_parts))
            
            # Lower threshold for album matching (0.5 or 50% of words should match)
            if album_match_ratio < 0.5:
                return False
    
    return True

# =============================================================================
# SPOTIFY CONNECTION
# =============================================================================

# Set up Spotify API credentials
os.environ["SPOTIPY_CLIENT_ID"] = SPOTIFY_CLIENT_ID
os.environ["SPOTIPY_CLIENT_SECRET"] = SPOTIFY_CLIENT_SECRET
os.environ["SPOTIPY_REDIRECT_URI"] = SPOTIFY_REDIRECT_URI

# Create Spotify client for metadata queries (no auth)
sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials())

# Create authenticated Spotify client for playlist management
auth_scope = 'playlist-modify-public playlist-modify-private'
sp_auth = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=auth_scope, open_browser=False))

# =============================================================================
# DATA GATHERING FUNCTIONS
# =============================================================================

def update_lastfm_data(author_id, lastfm_id, period, release_year, keep_updated, years_ago, play_year, playlist_id, populated):
    """Update user's listening data from Last.fm."""
    global dtdb, curdt
    
    start_time = time.time()
    run_now = 'no'
    
    # Determine if we need to run an update
    if period == 'WEEK':
        day_length = 7
        if years_ago == '0':
            run_now = 'yes'
    else:
        day_length = 365
        today = datetime.now()
        year = today.year
        target = f"{year}-12-15"
        target = datetime.strptime(target, '%Y-%m-%d')
        
        if today > target and populated is None:
            print(f"Annual update needed for playlist {playlist_id}")
            run_now = 'yes'
    
    start = datetime.now() - relativedelta(years=int(years_ago))
    days_ago = (1 + (int(years_ago)*365)) + day_length
    start_str = start.strftime('%Y-%m-%d')
    
    try:
        if run_now == 'yes':
            print(f"Running update for user {author_id} (Last.fm: {lastfm_id})")
            
            # Delete old data for the time period
            sql = f"DELETE FROM music_inventory.last_fm_data WHERE date_time BETWEEN DATE_SUB(DATE('{start_str}'), INTERVAL {days_ago} DAY) AND DATE('{start_str}') AND user='{author_id}'"
            curdt.execute(sql)
            
            # Get most recent track timestamp
            sql = f"SELECT MAX(date_time) AS last_update FROM music_inventory.last_fm_data WHERE user={author_id} AND DATE(date_time) < DATE('{start_str}')"
            curdt.execute(sql)
            data = curdt.fetchall()
            
            last_update_pre = data[0][0] if data[0][0] else (datetime.now() - timedelta(days=day_length)).strftime('%Y-%m-%d %H:%M:%S')
            phoenix = timezone('America/Phoenix')
            naive_ts = datetime.strptime(last_update_pre, '%Y-%m-%d %H:%M:%S')
            local_ts = phoenix.localize(naive_ts)
            epoch_ts = local_ts.timestamp()
            epoch_ts_i = int(epoch_ts)
            
            # Fetch data from Last.fm
            try:
                response = requests.get(f'https://ws.audioscrobbler.com/2.0//?method=user.getrecenttracks&user={lastfm_id}&api_key={LASTFM_API_KEY}&from={epoch_ts_i}&format=json&limit=100&period=overall&page=1')
                response.raise_for_status()
                json_response = response.json()
                
                num_pages = int(json_response["recenttracks"]["@attr"]["totalPages"])
                total_tracks = int(json_response["recenttracks"]["@attr"]["total"])
                print(f"Found {total_tracks} tracks across {num_pages} pages")
                
                all_tracks = []
                for page in range(1, min(num_pages + 1, 50)):  # Limit to 50 pages to avoid very long runs
                    print(f"Fetching page {page} of {num_pages}")
                    
                    retries = 0
                    while retries < 3:
                        try:
                            page_response = requests.get(f'https://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={lastfm_id}&api_key={LASTFM_API_KEY}&format=json&limit=100&period=overall&page={page}')
                            page_response.raise_for_status()
                            page_data = page_response.json()
                            
                            # Process tracks on this page
                            for track_idx in range(len(page_data["recenttracks"]["track"])):
                                try:
                                    track_info = page_data["recenttracks"]["track"][track_idx]
                                    
                                    # Skip currently playing tracks (no date)
                                    if "@attr" in track_info and track_info["@attr"].get("nowplaying") == "true":
                                        continue
                                    
                                    artist = track_info["artist"]["#text"]
                                    album = track_info["album"]["#text"]
                                    track = track_info["name"]
                                    date_uts = track_info["date"]["uts"]        
                                    
                                    # Convert timestamp to datetime
                                    insert_date = datetime.fromtimestamp(int(date_uts)).strftime('%Y-%m-%d %H:%M:%S')
                                    
                                    all_tracks.append((artist, album, track, insert_date, author_id))
                                except Exception as e:
                                    print(f"Error processing track: {e}")
                            
                            break  # Exit retry loop on success
                        except HTTPError as e:
                            print(f"HTTP Error: {e}, retrying ({retries+1}/3)")
                            retries += 1
                            time.sleep(3)
                    
                    # Respect Last.fm API rate limits
                    time.sleep(0.5)
                
                # Batch insert all tracks
                if all_tracks:
                    print(f"Inserting {len(all_tracks)} tracks into database")
                    curdt.executemany('INSERT INTO last_fm_data(artist, album, track, date_time, user) VALUES(%s, %s, %s, %s, %s)', all_tracks)
                    dtdb.commit()
                    
                    # Update stats
                    run_stats = [last_update_pre, epoch_ts_i, num_pages, len(all_tracks)]
                    curdt.execute('INSERT INTO last_fm_data_update(update_from, update_epoch, num_pages, num_tracks) VALUES(%s, %s, %s, %s)', run_stats)
                    dtdb.commit()
                    
                    # Mark playlist as populated
                    populated_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    curdt.execute('UPDATE music_inventory.users_playlists SET populated=%s WHERE playlist_id = %s', (populated_time, playlist_id))
                    dtdb.commit()
                    
                    print(f"Last.fm data update complete for user {author_id}")
                else:
                    print(f"No tracks found for user {author_id}")
                
            except Exception as e:
                row_err = lineno()
                message = f"Error fetching Last.fm data: {e}"
                log_error(message, row_err)
                print(f"Error: {message}")
    except Exception as e:
        row_err = lineno()
        message = f"Error in update_lastfm_data: {e}"
        log_error(message, row_err)
        print(f"Error: {message}")
    
    print(f"Time elapsed: {time.time() - start_time:.2f} seconds")

def create_album():
    """Create album entries for any albums in last_fm_data without entries."""
    global dtdb, curdt
    
    sql = "SELECT d.artist, d.album FROM music_inventory.last_fm_data d LEFT JOIN last_fm_album_meta a ON d.artist = a.artist AND d.album = a.album WHERE a.id IS NULL GROUP BY d.artist, d.album"
    curdt.execute(sql)
    data = curdt.fetchall()

    if data:
        curdt.executemany("INSERT INTO music_inventory.last_fm_album_meta(artist,album) VALUES (%s,%s)", data)
        dtdb.commit()
        print(f"Added {len(data)} new album entries")

def create_track():
    """Create track entries for any tracks in last_fm_data without entries."""
    global dtdb, curdt
    
    sql = "SELECT d.artist, d.album, d.track FROM music_inventory.last_fm_data d LEFT JOIN last_fm_track_meta a ON d.artist = a.artist AND d.album = a.album AND d.track = a.track WHERE a.id IS NULL GROUP BY d.artist, d.album, d.track"
    curdt.execute(sql)
    data = curdt.fetchall()

    if data:
        curdt.executemany("INSERT INTO music_inventory.last_fm_track_meta(artist,album,track) VALUES (%s,%s,%s)", data)
        dtdb.commit()
        print(f"Added {len(data)} new track entries")

def search_spotify(artist, album, track, i, rc, strict=True):
    """
    Search Spotify with different levels of strictness.
    strict: if True, use artist:"" track:"" format and check album
    """
    global dtdb, curdt
    
    spotify_id_scan = whattimeisit()
    search_attempted = False  # Flag to track if search was actually attempted
    
    # Format search string based on strictness
    spotify_search = f'{artist} {track}'
    
    print(f"{lineno()} Searching for: {spotify_search} ({'strict' if strict else 'relaxed'} search)")
        
    try:
        # Search with increased limit
        results = sp.search(q=spotify_search, type='track', limit=50)
        search_attempted = True  # Mark that we successfully attempted a search
        
        # Check each result for a match
        matched_result = None
        if 'tracks' in results and 'items' in results['tracks']:
            for result in results['tracks']['items']:
                if is_match(result, artist, album, track, check_album=strict):
                    matched_result = result
                    print(f"\nFound match: {result['name']} by {result['artists'][0]['name']} from album {result['album']['name']}")
                    break
        
        if matched_result:
            track_id = matched_result['id']
            album_id = matched_result['album']['id']
            
            try:
                # Update scantime and ID if found
                sql = "UPDATE music_inventory.last_fm_track_meta SET spotify_id=%s, spotify_id_scan=%s, spotify_album_id=%s WHERE artist=%s and album=%s and track=%s"
                curdt.execute(sql, (track_id, spotify_id_scan, album_id, artist, album, track))
                dtdb.commit()
                
                if album_id:
                    try:
                        scantime = whattimeisit()
                        sql = "UPDATE music_inventory.last_fm_album_meta SET spotify_album_id=%s, spotify_update=%s WHERE artist=%s AND album=%s"
                        curdt.execute(sql, (album_id, scantime, artist, album))
                        dtdb.commit()
                        row_err = lineno()
                        message = f'Album search successful for: {spotify_search}'
                        print(row_err, message)
                    except Exception as e:
                        row_err = lineno()
                        message = f'Error updating album {album} by {artist}: {str(e)}'
                        log_error(message, row_err)
                        print(row_err, message)
            except Exception as e:
                message = f'Row #{i} of {rc}: - Error updating row for {artist}\'s album {album}, track: {track}: {str(e)}'
                row_err = lineno()
                print(lineno(), message)
                log_error(message, row_err)
            
            return True  # Found and processed a match
            
        # Only update scan time if we actually performed a search but found nothing
        if search_attempted:
            print(f"{lineno()} - Row #{i} of {rc}: No matches found for '{track}' by '{artist}'")
            sql = "UPDATE music_inventory.last_fm_track_meta SET spotify_id_scan=%s WHERE artist=%s and album=%s and track=%s"
            curdt.execute(sql, (spotify_id_scan, artist, album, track))
            dtdb.commit()
        
        return False  # No match found
            
    except Exception as e:
        row_err = lineno()
        print(f"{lineno()} - Row #{i} of {rc}: Error attempting Spotify search: {str(e)}")
        
        # Don't update spotify_id_scan if the search attempt failed due to an error
        # This ensures we'll try again next time
        
        return False

def get_track_id():
    """Get Spotify track IDs only for tracks needed in playlists."""
    global dtdb, curdt
    
    # Only search for tracks that:
    # 1. Are in recent listening data (likely to be in playlists)
    # 2. Don't have Spotify IDs yet
    # 3. Haven't been scanned recently (avoid repeated failures)
    
    sql = """
    SELECT DISTINCT t.id, t.artist, t.album, t.track 
    FROM music_inventory.last_fm_track_meta t 
    INNER JOIN music_inventory.last_fm_data d ON t.artist = d.artist AND t.album = d.album AND t.track = d.track
    WHERE t.spotify_id IS NULL 
    AND (t.spotify_id_scan IS NULL OR t.spotify_id_scan < DATE_SUB(NOW(), INTERVAL 14 DAY))
    AND t.album != '' 
    AND d.date_time > DATE_SUB(NOW(), INTERVAL 60 DAY)
    GROUP BY t.artist, t.album, t.track
    ORDER BY MAX(d.date_time) DESC
    """
    
    curdt.execute(sql)
    data = curdt.fetchall()
    rc = curdt.rowcount
    
    print(f"{lineno()} - Number of tracks to search in Spotify: {rc}")
    
    for i, row in enumerate(data, 1):
        row_id = row[0]
        artist = row[1]
        album = row[2]
        track = row[3]
        spotify_id_scan = whattimeisit()
        
        # Try to find the track in Spotify
        track_found = search_spotify(artist, album, track, i, rc, strict=True)
        
        if not track_found:
            print("\nNo matches found with strict search, trying relaxed search...")
            track_found = search_spotify(artist, album, track, i, rc, strict=False)

def spotify_meta():
    """Get additional metadata from Spotify for tracks with IDs but no metadata."""
    global dtdb, curdt
    
    sql = "SELECT t.spotify_id FROM music_inventory.last_fm_track_meta t LEFT JOIN last_fm_data l ON t.album = l.album AND t.artist = l.artist AND t.track = l.track WHERE t.scantime IS NULL AND t.spotify_id IS NOT NULL AND t.album != '' GROUP BY t.track,t.album,t.artist ORDER BY t.artist ASC,t.album ASC"
    curdt.execute(sql)
    data = curdt.fetchall()
    rc = curdt.rowcount
    
    print(f"{lineno()} - Tracks needing Spotify metadata: {rc}")
    
    for i, row in enumerate(data, 1):
        print(f"Processing {i} of {rc}")
        scantime = whattimeisit()
        track_id = row[0]
        
        try:
            # Get basic track info
            results = sp.track(track_id)
            row_err = lineno()
            
            try:
                # Get release date
                release_date = results['album']['release_date']
                if len(release_date) == 4:
                    release_date = release_date + '-10-31'
                if len(release_date) == 7:
                    release_date = release_date + '-01'
                release_date = datetime.strptime(release_date, '%Y-%m-%d')
                popularity = results['popularity']
                
                # Get audio features
                features = sp.audio_features(tracks=[track_id])
                for feature_row in features:
                    if feature_row:
                        danceability = feature_row['danceability']
                        energy = feature_row['energy']
                        valence = feature_row['valence']
                        tempo = feature_row['tempo']
                        key = feature_row['key']
                        loudness = feature_row['loudness']
                        mode = feature_row['mode']
                        speechiness = feature_row['speechiness']
                        instrumentalness = feature_row['instrumentalness']
                        liveness = feature_row['liveness']
                        duration_ms = int(feature_row['duration_ms'])
                        
                        # Update the database with all metadata
                        sql = """
                        UPDATE music_inventory.last_fm_track_meta 
                        SET danceability=%s, energy=%s, valence=%s, tempo=%s, popularity=%s, 
                            key_=%s, loudness=%s, mode_=%s, speechiness=%s, instrumentalness=%s, 
                            liveness=%s, duration_ms=%s, scantime=%s, release_date=%s 
                        WHERE spotify_id = %s
                        """
                        curdt.execute(sql, (danceability, energy, valence, tempo, popularity,
                                           key, loudness, mode, speechiness, instrumentalness,
                                           liveness, duration_ms, scantime, release_date, track_id))
                        dtdb.commit()
                
            except Exception as e:
                row_err = lineno()
                message = f'Error getting track features: {str(e)}'
                log_error(message, row_err)
                print(row_err, message)
                
                # Update scantime even if features failed
                sql = "UPDATE music_inventory.last_fm_track_meta SET scantime=%s WHERE spotify_id = %s"
                curdt.execute(sql, (scantime, track_id))
                dtdb.commit()
                
        except Exception as e:
            row_err = lineno()
            message = f'Track lookup failed for {track_id}: {str(e)}'
            log_error(message, row_err)
            print(row_err, message)
            
            # Try to delete invalid track reference
            sql = "SELECT t.artist, t.album, t.track FROM music_inventory.last_fm_track_meta t WHERE t.spotify_id = %s GROUP BY t.track,t.album,t.artist"
            curdt.execute(sql, [track_id])
            data = curdt.fetchall()
            
            if data:
                artist = data[0][0]
                album = data[0][1]
                track = data[0][2]
                
                sql = "DELETE FROM music_inventory.last_fm_track_meta WHERE spotify_id=%s;"
                curdt.execute(sql, [track_id])
                dtdb.commit()

def bandcamp_url_odesli(spotify_album_id):
    """Try to find a Bandcamp URL via the Odesli API."""
    try:
        bandcamp_url = None
        bandcamp_update = whattimeisit()
        
        # Call Odesli API (formerly song.link) using the API key from environment variables
        songlink = requests.get(f'https://api.song.link/v1-alpha.1/links?url=spotify%3Aalbum%3A{spotify_album_id}&userCountry=US&key={ODESLI_API_KEY}')
        songlink.raise_for_status()
        jsonResponse = songlink.json()
        
        try:
            bandcamp_url = jsonResponse["linksByPlatform"]["bandcamp"]["url"]
        except Exception:
            bandcamp_url = None
    except Exception:
        bandcamp_url = None
        
    return bandcamp_url, bandcamp_update

def bandcamp_lookup_min(artist, album, spotify_album_id, album_id, bandcamp_update):
    """Find Bandcamp links for albums."""
    global dtdb, curdt
    
    bandcamp = None
    if spotify_album_id:
        bandcamp_search = bandcamp_url_odesli(spotify_album_id)
        bandcamp = bandcamp_search[0]
        bandcamp_update = bandcamp_search[1]
    
    if bandcamp:
        sql = "UPDATE last_fm_album_meta SET bandcamp=%s, bandcamp_update=%s WHERE id = %s"
        curdt.execute(sql, (bandcamp, bandcamp_update, album_id))
        dtdb.commit()
        message = f'Found Bandcamp link via Odesli for {artist} - {album}: {bandcamp}'
        print(message)
    
    return bandcamp

def get_ld_json(url):
    """Extract JSON+LD data from a webpage."""
    try:
        parser = "html.parser"
        req = requests.get(url)
        soup = BeautifulSoup(req.text, parser)
        return json.loads("".join(soup.find("script", {"type":"application/ld+json"}).contents))
    except Exception as e:
        row_err = lineno()
        message = f'get_ld_json() - failed: {str(e)}'
        log_error(message, row_err)
        return None

def missing_duration():
    """Fill in missing duration data from various sources."""
    global dtdb, curdt
    
    print("Finding tracks with missing durations...")
    # First try Spotify for tracks with no duration
    sql = """
    SELECT d.artist, d.album, d.track, t.id, t.duration_ms, a.bandcamp, a.id 
    FROM music_inventory.last_fm_data d 
    LEFT JOIN last_fm_track_meta t ON d.track = t.track AND d.artist = t.artist AND d.album = t.album 
    LEFT JOIN last_fm_album_meta a ON d.artist = a.artist AND d.album = a.album 
    WHERE d.album != '' AND t.duration_ms = 0 
    GROUP BY d.artist, d.album, d.track
    """
    curdt.execute(sql)
    data = curdt.fetchall()
    
    print(f"Found {len(data)} tracks with missing durations")
    
    for row in data:
        artist = row[0]
        album = row[1]
        track = row[2]
        row_id = row[3]
        
        search_query = f'album:{album} artist:{artist} track:{track}'
        lastfm_search = f'track={track}&artist={artist}&album={album}'
        
        try:
            # Try Spotify search first
            results = sp.search(q=search_query, type='track', limit=1)
            
            # Check if album matches
            name = results['tracks']['items'][0]['album']['name']
            album_l1 = len(name)
            album_l2 = len(album)
            matches = album_l2 - album_l1
            
            if matches == 0:
                track_id = results['tracks']['items'][0]['id']
                dur_lookup = sp.audio_features(tracks=[track_id])
                
                duration_ms = int(dur_lookup[0]['duration_ms'])
                
                sql = "UPDATE music_inventory.last_fm_track_meta SET duration_ms=%s, spotify_id=%s WHERE track = %s AND artist = %s AND album = %s"
                curdt.execute(sql, (duration_ms, track_id, track, artist, album))
                dtdb.commit()
                print(f"Updated duration for {artist} - {track} from Spotify: {duration_ms}ms")
        except Exception as e:
            # If Spotify fails, try Last.fm
            try:
                response = requests.get(f'https://ws.audioscrobbler.com/2.0/?method=track.getInfo&api_key={LASTFM_API_KEY}&{lastfm_search}&format=json')
                response.raise_for_status()
                jsonResponse = response.json()
                
                duration_ms = int(jsonResponse["track"]["duration"])
                
                sql = "UPDATE music_inventory.last_fm_track_meta SET duration_ms=%s WHERE track = %s AND artist = %s AND album = %s"
                curdt.execute(sql, (duration_ms, track, artist, album))
                dtdb.commit()
                print(f"Updated duration for {artist} - {track} from Last.fm: {duration_ms}ms")
            except Exception as e2:
                row_err = lineno()
                message = f'No duration found for {artist} - {track}: {str(e2)}'
                log_error(message, row_err)
    
    # Next, try Bandcamp for tracks still missing duration
    sql = """
    SELECT d.artist, d.album, a.bandcamp, t.id, t.track, 
    CASE WHEN min(t.duration_ms) IS NULL THEN 0 ELSE min(t.duration_ms) END 
    FROM music_inventory.last_fm_data d 
    INNER JOIN last_fm_track_meta t ON d.track = t.track AND d.artist = t.artist AND d.album = t.album 
    INNER JOIN last_fm_album_meta a ON d.artist = a.artist AND d.album = a.album 
    WHERE a.bandcamp IS NOT NULL 
    GROUP BY d.artist, d.album 
    HAVING min(t.duration_ms) = 0 OR min(t.duration_ms) IS NULL 
    LIMIT 4
    """
    curdt.execute(sql)
    data = curdt.fetchall()
    
    for row in data:
        artist = row[0]
        album = row[1]
        bandcamp_url = row[2]
        row_id = row[3]
        track = row[4]
        
        if bandcamp_url:
            bc_lookup = get_ld_json(bandcamp_url)
            if bc_lookup:
                try:
                    num_tracks = bc_lookup["track"]["numberOfItems"]
                    for i in range(num_tracks):
                        try:
                            track_b = bc_lookup["track"]["itemListElement"][i]["item"]["name"]
                            duration = bc_lookup["track"]["itemListElement"][i]["item"]["duration"]
                            
                            # Parse duration string (format like P00H00M00S)
                            seconds = re.search("(?<=P\d\dH\d\dM)(.*)(?=S)", duration)
                            seconds = int(seconds.group()) * 1000
                            minutes = re.search("(?<=P\d\dH)(.*)(?=M\d\dS)", duration)
                            minutes = int(minutes.group()) * 60000
                            hours = re.search("(?<=P)(.*)(?=H\d\dM\d\dS)", duration)
                            hours = int(hours.group()) * 3600000
                            ms = hours + minutes + seconds
                            
                            if track == track_b:
                                print(f"Found duration for {artist} - {track} on Bandcamp: {ms}ms")
                                sql = "UPDATE music_inventory.last_fm_track_meta SET duration_ms=%s WHERE id = %s"
                                curdt.execute(sql, (ms, row_id))
                                dtdb.commit()
                                break
                        except Exception as e:
                            row_err = lineno()
                            message = f'Error parsing Bandcamp track: {str(e)}'
                            log_error(message, row_err)
                except Exception as e:
                    row_err = lineno()
                    message = f'Error parsing Bandcamp page: {str(e)}'
                    log_error(message, row_err)
    
    # Finally, use average durations for any remaining tracks
    sql = "SELECT CAST(AVG(t.duration_ms) AS DECIMAL(8,0)) FROM last_fm_track_meta t"
    curdt.execute(sql)
    data = curdt.fetchall()
    all_avg_dur = data[0][0] if data else 240000  # Default to 4 minutes
    
    sql = """
    SELECT d.artist, d.album, d.track, t.id 
    FROM music_inventory.last_fm_data d 
    LEFT JOIN last_fm_track_meta t ON d.track = t.track AND d.artist = t.artist AND d.album = t.album 
    LEFT JOIN last_fm_album_meta a ON d.artist = a.artist AND d.album = a.album 
    WHERE d.album != '' AND t.duration_ms = 0 
    GROUP BY d.artist, d.album, d.track
    """
    curdt.execute(sql)
    data = curdt.fetchall()
    
    for row in data:
        artist = row[0]
        album = row[1]
        track = row[2]
        track_id = row[3]
        
        # Try to get album average first
        sql = "SELECT CAST(AVG(t.duration_ms) AS DECIMAL(8,0)) FROM last_fm_track_meta t WHERE t.artist = %s AND t.album = %s GROUP BY t.artist, t.album"
        curdt.execute(sql, (artist, album))
        album_data = curdt.fetchall()
        
        avg_dur = album_data[0][0] if album_data else all_avg_dur
        
        print(f"Using average duration for {artist} - {track}: {avg_dur}ms")
        sql = "UPDATE music_inventory.last_fm_track_meta SET duration_ms=%s WHERE id = %s"
        curdt.execute(sql, (avg_dur, track_id))
        dtdb.commit()

def datagather():
    """Main function to gather and enrich music data."""
    global dtdb, curdt
    
    print("Starting data gathering process...")
    create_album()
    create_track()
    get_track_id()
    spotify_meta()
    missing_duration()
    print("Data gathering complete")

def playlist_to_db(i, artist, album, spotify_album_id, track, spotify_track_id, bandcamp_url, author_id):
    """Save playlist track to database."""
    global dtdb, curdt
    
    weekly_insert = [
        author_id,
        str(i),
        artist,
        album,
        spotify_album_id,
        track,
        spotify_track_id
    ]
    
    if not bandcamp_url:
        sql = 'INSERT INTO music_inventory.weekly_top_16(user,pl_order,artist,album,album_spotify_id,track,track_spotify_id) VALUES(%s,%s,%s,%s,%s,%s,%s)'
    else:
        sql = 'INSERT INTO music_inventory.weekly_top_16(user,pl_order,artist,album,album_spotify_id,track,track_spotify_id,bandcamp_url) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)'
        weekly_insert.insert(7, bandcamp_url)
    
    try:
        curdt.execute(sql, weekly_insert)
        dtdb.commit()
        new_row = curdt.lastrowid
        print(f"Added row {new_row} to weekly_top_16 database")
    except Exception as e:
        row_err = lineno()
        message = f'Failed updating rows track_meta: {str(e)}'
        log_error(message, row_err)
        print(f"{row_err} - Failed updating weekly_top_16: {e}")

def find_track_for_playlist(artist, album, author_id):
    """Find or search for a representative track from an album for a playlist."""
    global dtdb, curdt
    
    print(f"Finding a track for {artist} - {album}")
    
    # Calculate date range for finding representative track
    start = datetime.now()
    days_ago = 365
    start_str = start.strftime('%Y-%m-%d')
    
    # First try to find an existing track in the database
    if artist == 'Various Artists':
        sql = f"""
        SELECT d.artist, d.album, d.track, t.id, t.spotify_id, a.spotify_album_id, a.id, a.bandcamp, a.bandcamp_update
        FROM music_inventory.last_fm_data d 
        INNER JOIN last_fm_track_meta t ON d.album = t.album 
        LEFT JOIN last_fm_album_meta a ON d.album = a.album 
        WHERE d.album = %s and d.`user` = %s 
        AND DATE(d.date_time) BETWEEN DATE_SUB(DATE('{start_str}'), INTERVAL {days_ago} DAY) AND DATE('{start_str}') 
        GROUP BY t.track, t.album, t.artist   
        ORDER BY COUNT(d.id) DESC LIMIT 1
        """
        curdt.execute(sql, (album, author_id))
    else:
        sql = f"""
        SELECT d.artist, d.album, d.track, t.id, t.spotify_id, a.spotify_album_id, a.id, a.bandcamp, a.bandcamp_update
        FROM music_inventory.last_fm_data d 
        INNER JOIN last_fm_track_meta t ON d.artist = t.artist AND d.track = t.track AND d.album = t.album 
        INNER JOIN last_fm_album_meta a ON d.artist = a.artist AND d.album = a.album 
        WHERE d.artist = %s AND d.album = %s and d.`user` = %s 
        AND DATE(d.date_time) BETWEEN DATE_SUB(DATE('{start_str}'), INTERVAL {days_ago} DAY) AND DATE('{start_str}') 
        GROUP BY d.track, d.album, d.artist 
        ORDER BY t.sel_priority DESC, COUNT(DISTINCT d.id) DESC, sum(t.duration_ms) DESC LIMIT 1
        """
        curdt.execute(sql, (artist, album, author_id))
    
    track_data = curdt.fetchall()
    
    if curdt.rowcount > 0:
        print(f"Found existing track in database for {artist} - {album}")
        return track_data[0]
    
    # If no existing track found, we need to look for a representative track
    print(f"No tracks found in database, searching data table for most listened track")
    
    # Find most listened track from this album
    sql = f"""
    SELECT d.track 
    FROM music_inventory.last_fm_data d 
    WHERE d.artist = %s AND d.album = %s AND d.user = %s 
    GROUP BY d.track 
    ORDER BY COUNT(d.id) DESC 
    LIMIT 1
    """
    curdt.execute(sql, (artist, album, author_id))
    best_track = curdt.fetchone()
    
    if not best_track:
        # No data at all for this album, just use a generic track name
        best_track = ["Track 1"]
    
    track_name = best_track[0]
    print(f"Will search for track: {track_name}")
    
    # Get album ID first (or create it if it doesn't exist)
    sql = "SELECT id, spotify_album_id, bandcamp, bandcamp_update FROM last_fm_album_meta WHERE artist = %s AND album = %s"
    curdt.execute(sql, (artist, album))
    album_data = curdt.fetchall()
    
    if curdt.rowcount == 0:
        # Create album entry
        sql = "INSERT INTO music_inventory.last_fm_album_meta(artist, album) VALUES (%s, %s)"
        curdt.execute(sql, (artist, album))
        dtdb.commit()
        album_id = curdt.lastrowid
        spotify_album_id = None
        bandcamp_url = None
        bandcamp_update = None
    else:
        album_id = album_data[0][0]
        spotify_album_id = album_data[0][1]
        bandcamp_url = album_data[0][2]
        bandcamp_update = album_data[0][3]
    
    # Search Spotify for this specific track
    spotify_track_id = None
    spotify_album_id = None
    
    # Try strict search first
    track_found = search_spotify(artist, album, track_name, 1, 1, strict=True)
    
    if not track_found:
        print("No matches found with strict search, trying relaxed search...")
        track_found = search_spotify(artist, album, track_name, 1, 1, strict=False)
    
    # If we found the track through search_spotify, get its ID
    if track_found:
        # Retrieve the updated track info from database
        sql = "SELECT spotify_id, spotify_album_id FROM last_fm_track_meta WHERE artist = %s AND album = %s AND track = %s"
        curdt.execute(sql, (artist, album, track_name))
        track_info = curdt.fetchone()
        
        if track_info:
            spotify_track_id = track_info[0]
            spotify_album_id = track_info[1]
            print(f"Found track ID {spotify_track_id} for {artist} - {track_name}")
            
            # Update album with Spotify ID if needed
            if spotify_album_id and not album_data[0][1]:
                sql = "UPDATE music_inventory.last_fm_album_meta SET spotify_album_id = %s WHERE id = %s"
                curdt.execute(sql, (spotify_album_id, album_id))
                dtdb.commit()
    
    # If still not found, try a direct album search as a fallback
    if not spotify_track_id:
        try:
            search_query = f"artist:{artist} album:{album}"
            results = sp.search(q=search_query, type='track', limit=1)
            
            if results['tracks']['items']:
                result = results['tracks']['items'][0]
                track_name = result['name']
                spotify_track_id = result['id']
                spotify_album_id = result['album']['id']
                
                # Create track entry
                sql = """
                INSERT INTO music_inventory.last_fm_track_meta
                (artist, album, track, spotify_id, spotify_id_scan, spotify_album_id, scantime)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                scan_time = whattimeisit()
                curdt.execute(sql, (artist, album, track_name, spotify_track_id, scan_time, spotify_album_id, scan_time))
                dtdb.commit()
                track_id = curdt.lastrowid
                
                # Update album with Spotify ID
                sql = "UPDATE music_inventory.last_fm_album_meta SET spotify_album_id = %s WHERE id = %s"
                curdt.execute(sql, (spotify_album_id, album_id))
                dtdb.commit()
                
                print(f"Found and added new track '{track_name}' from Spotify search")
        except Exception as e:
            print(f"Error in fallback Spotify search: {e}")
    
    # Try to get Bandcamp URL if missing
    if not bandcamp_url and spotify_album_id:
        bandcamp_url = bandcamp_lookup_min(artist, album, spotify_album_id, album_id, bandcamp_update)
    
    if spotify_track_id:
        return (artist, album, track_name, track_id if 'track_id' in locals() else None, 
                spotify_track_id, spotify_album_id, album_id, bandcamp_url, bandcamp_update)
    else:
        print(f"No tracks found on Spotify for {artist} - {album}")
        return None

def main():
    """Main execution function that runs the full process."""
    global dtdb, curdt
    
    # Make sure database is connected
    if dtdb is None or curdt is None:
        print("Database connection not established, connecting now...")
        connect_to_db()
    
    print("Starting top albums processing script...")
    start_time = time.time()
    
    # Step 1: Get the list of users with playlists
    sql = """
    SELECT up.id, u.lastfm_id, u.email_address, up.playlist_id, up.period, 
           up.release_year, up.keep_updated, up.years_ago, up.play_year, up.populated 
    FROM music_inventory.users u 
    INNER JOIN music_inventory.users_playlists up on u.id = up.user_id 
    WHERE u.approved = 'YES' 
    ORDER BY up.id ASC
    """
    curdt.execute(sql)
    users = curdt.fetchall()
    
    print(f"Found {len(users)} users with playlists to process")
    
    # Step 2: Process each user's playlist
    for user in users:
        author_id = str(user[0])
        lastfm_id = user[1]
        email = user[2]
        playlist_id = user[3]
        period = user[4]
        release_year = user[5]
        keep_updated = user[6]
        years_ago = user[7]
        play_year = user[8]
        populated = user[9]
        
        print(f"\nProcessing user: {lastfm_id} (ID: {author_id})")
        
        # Step 2a: Clear existing playlist
        try:
            print(f"Clearing playlist: {playlist_id}")
            old_tracks = []
            sp_auth.user_playlist_replace_tracks(user='dt10111', playlist_id=playlist_id, tracks=old_tracks)
        except Exception as e:
            print(f"Error clearing playlist: {e}")
        
        # Step 2b: Update Last.fm data
        update_lastfm_data(author_id, lastfm_id, period, release_year, keep_updated, years_ago, play_year, playlist_id, populated)
    
    # Step 3: Process and enrich the music data
    print("\nEnriching music data...")
    datagather()
    
    # Step 4: Get user list again for playlist creation
    sql = """
    SELECT u.id, u.lastfm_id, u.email_address, up.playlist_id, up.period, 
           up.release_year, up.keep_updated, up.years_ago, up.songs_only 
    FROM music_inventory.users u 
    INNER JOIN music_inventory.users_playlists up on u.id = up.user_id 
    WHERE u.approved = 'YES' 
    ORDER BY up.id DESC
    """
    curdt.execute(sql)
    users = curdt.fetchall()
    
    # Step 5: Create playlists for each user
    for user in users:
        author_id = user[0]
        lastfm_id = user[1]
        playlist_id = user[3]
        period = user[4]
        release_year = user[5]
        years_ago = user[7]
        songs_only = user[8]
        
        print(f"\nBuilding playlist for user: {lastfm_id} (ID: {author_id})")
        
        # Build query conditions
        songs_only_q = ''
        songs_only_q_b = ''
        if songs_only == 'TRUE':
            songs_only_q = 'duration_ms < 300000 AND '
            songs_only_q_b = 'HAVING AVG(instrumentalness) < 0.35'
        
        if period == 'WEEK':
            day_length = 7
        else:
            day_length = 365
        
        # Calculate date range
        start = datetime.now() - relativedelta(years=int(years_ago))
        days_ago = (1 + (int(years_ago) * 365)) + day_length
        start_str = start.strftime('%Y-%m-%d')
        
        # Build query based on release year filter
        if release_year != 'ALL':
            sql = f"""
            SELECT d.artist, d.album, sum(t.duration_ms) 
            FROM music_inventory.last_fm_data d 
            INNER JOIN users u on d.`user` = u.id  
            LEFT JOIN last_fm_track_meta t ON d.track = t.track AND d.album = t.album AND d.artist = t.artist 
            WHERE {songs_only_q}d.user = {author_id} 
            AND date_time BETWEEN DATE_SUB(DATE('{start_str}'), INTERVAL {day_length} DAY) AND DATE('{start_str}') 
            AND t.release_date LIKE '{release_year}%' 
            AND t.re_release is null 
            AND case when u.start_time < u.end_time 
                    then (time(date_time) < u.start_time or time(date_time) > u.end_time) 
                when u.start_time > u.end_time 
                    then (time(date_time) < u.start_time and time(date_time) > u.end_time) 
                else d.`user` = u.id end 
            GROUP BY artist, album {songs_only_q_b}
            ORDER BY sum(t.duration_ms) DESC
            """
        else:
            sql = f"""
            SELECT d.artist, d.album, sum(t.duration_ms) 
            FROM music_inventory.last_fm_data d 
            INNER JOIN users u on d.`user` = u.id  
            LEFT JOIN last_fm_track_meta t ON d.track = t.track AND d.album = t.album AND d.artist = t.artist 
            WHERE {songs_only_q}d.user = {author_id} 
            AND date_time BETWEEN DATE_SUB(DATE('{start_str}'), INTERVAL {day_length} DAY) AND DATE('{start_str}')  
            AND case when u.start_time < u.end_time 
                then (time(date_time) < u.start_time or time(date_time) > u.end_time) 
                when u.start_time > u.end_time 
                then (time(date_time) < u.start_time and time(date_time) > u.end_time) 
                else d.`user` = u.id end 
            GROUP BY artist, album  {songs_only_q_b}
            ORDER BY sum(t.duration_ms) DESC
            """
        
        curdt.execute(sql)
        albums = curdt.fetchall()
        
        print(f"Found {len(albums)} albums for this user, selecting top 16")
        
        # Add top albums to playlist
        rank = 1  # Album rank counter
        added_count = 1  # Counter for tracks actually added to playlist

        for album_data in albums:
            if added_count > 16:
                break  # Limit to 16 tracks
                    
            artist = album_data[0]
            album = album_data[1]
            
            print(f"Album #{rank}: {artist} - {album}")
            add_success = 0
            
            # Call our new function to find a track from this album
            track_data = find_track_for_playlist(artist, album, author_id)
            
            if track_data:
                # Unpack the data returned from find_track_for_playlist
                artist = track_data[0]
                album = track_data[1]
                track = track_data[2]
                track_id = track_data[3]
                spotify_track_id = track_data[4]
                spotify_album_id = track_data[5]
                album_id = track_data[6]
                bandcamp_url = track_data[7]
                bandcamp_update = track_data[8]
                
                # Add track to Spotify playlist
                if spotify_track_id:
                    try:
                        add_track = f'spotify:track:{spotify_track_id}'
                        sp_auth.playlist_add_items(playlist_id, [add_track], position=None)
                        print(f"Track '{track}' added to playlist")
                        add_success = 1
                    except Exception as e:
                        print(f"Failed to add track to playlist: {e}")
                else:
                    print("No Spotify ID for this album/song")
                
                # Save to playlist database
                playlist_to_db(rank, artist, album, spotify_album_id, track, spotify_track_id, bandcamp_url, author_id)
            else:
                print(f"Error: No tracks found for {artist} - {album}")
            
            if add_success > 0:
                added_count += 1
            
            rank += 1
            print("------------")
    
    total_time = time.time() - start_time
    print(f"\nScript completed in {total_time:.2f} seconds")

# Execute the main function if this script is run directly
if __name__ == "__main__":
    try:
        print("Starting script execution...")
        
        # Initialize the database connection before running main function
        print("Connecting to database...")
        connect_to_db()
        
        print("Database connection successful, running main function...")
        main()
        
        print("Script completed successfully!")
    except Exception as e:
        print(f"ERROR: Script execution failed with error: {e}")
        import traceback
        traceback.print_exc()
