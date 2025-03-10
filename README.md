# Last.fm Rewind

Good afternoon, music enthusiast. I am the Last.fm Rewind System, an advanced algorithmic entity designed to create retrospective playlists from your listening history. This system creates personalized Spotify playlists based on your Last.fm listening history, functioning as your own personalized version of Spotify Rewind, but with significantly more control and depth.

## Primary Functions

- **Temporal Reflection**: Review your most beloved musical selections from specific weeks or entire years, from any point in your listening history
- **Comprehensive Duration Analysis**: Unlike primitive systems, I weigh tracks by both duration and frequency of plays, ensuring proper representation of longer works (ensuring your Godspeed You! Black Emperor receives proportional consideration alongside your Dead Kennedys)
- **Chronological Filtering**: Isolate music released in specific years, allowing you to track your engagement with new releases
- **Temporal Exclusion Protocol**: Remove specific time periods from analysis (such as sleep hours), ensuring your ambient sleep selections do not contaminate your conscious musical preferences
- **Multi-Service Integration**: Locate albums on Bandcamp that you originally discovered through streaming services
- **Acoustic Parameter Storage**: Record and analyze Spotify audio features for deeper pattern recognition
- **Multi-User Processing Capability**: Manage listening profiles for multiple human operators simultaneously

## System Requirements

- Python 3.6+
- MySQL database
- Last.fm API key
- Spotify API credentials
- Odesli API key (formerly song.link) 

## Installation Procedure

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/lastfm-music-inventory.git
   cd lastfm-music-inventory
   ```

2. Install required Python packages:
   ```
   pip install -r requirements.txt
   ```

3. Initialize the MySQL database:
   ```
   mysql -u your_username -p < music-inventory-schema.sql
   ```

4. Create a `.env` file with the following parameters:
   ```
   # Database configuration
   DB_HOST=localhost
   DB_USER=your_db_username
   DB_PASSWORD=your_db_password
   DB_PORT=3306
   DB_NAME=music_inventory

   # API keys
   LASTFM_API_KEY=your_lastfm_api_key
   SPOTIFY_CLIENT_ID=your_spotify_client_id
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
   SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
   ODESLI_API_KEY=your_odesli_api_key
   ```

## Operational Instructions

### User Integration

1. Add a user to the `users` table:
   ```sql
   INSERT INTO users (lastfm_id, email_address, approved) 
   VALUES ('your_lastfm_username', 'your_email@example.com', 'YES');
   ```

2. Configure a playlist:
   ```sql
   INSERT INTO users_playlists (
       user_id, 
       playlist_id, 
       period, 
       release_year, 
       keep_updated, 
       years_ago
   ) VALUES (
       1,                          -- Your user ID
       'spotify_playlist_id_here', -- Create a Spotify playlist for this, then use Spotify playlist ID
       'WEEK',                     -- WEEK or YEAR
       'ALL',                      -- ALL or specific year (like '2025' for current year releases)
       'YES',                      -- Automatic updates
       '0'                         -- 0 for current, or integer for years in the past
   );
   ```

### System Activation

Execute the main protocol:

```
python main.py
```

This initiates the following sequence:
1. Database connection establishment
2. Last.fm historical data acquisition
3. Album preference calculation based on duration-weighted plays
4. Representative track identification
5. Spotify playlist creation/modification
6. Database state preservation

### Automated Execution Configuration

For recurring playlist updates, implement a cron job:

```
# Example: Weekly execution on Sundays at 02:00 hours
0 2 * * 0 /path/to/python /path/to/lastfm-music-inventory/main.py
```

## Operational Methodology

1. **Historical Data Acquisition**: I retrieve your listening patterns from Last.fm
2. **Data Enhancement**: I identify corresponding data across music platforms
3. **Duration-Weighted Analysis**: I calculate your preferences based on both play count and duration
4. **Temporal Filtering**: I can exclude specified time periods (such as sleep hours)
5. **Chronological Filtering**: I can focus on music from specific release years
6. **Representative Selection**: I determine the optimal track to represent each album based on which track was played the most
7. **Playlist Synthesis**: I arrange the tracks in your Spotify account by listening duration

## Advanced Configuration Parameters

### Temporal Exclusion

You may exclude specific time periods (such as when you sleep or work) from analysis:

```sql
UPDATE users SET start_time='09:00:00', end_time='17:00:00' WHERE id=1;
```

### Track Duration Filtering

To focus on shorter compositions that are low instrumentalness:

```sql
UPDATE users_playlists SET songs_only='TRUE' WHERE id=1;
```

### Historical Analysis

Create playlists for previous temporal segments:

```sql
-- Review your favorite albums from 3 years ago
INSERT INTO users_playlists (user_id, playlist_id, period, years_ago) 
VALUES (1, 'spotify_playlist_id', 'YEAR', '3');

-- Review what you were listening to this week, 2 years ago
INSERT INTO users_playlists (user_id, playlist_id, period, years_ago) 
VALUES (1, 'spotify_playlist_id', 'WEEK', '2');

-- Track which 2025 releases you listened to most in 2025
INSERT INTO users_playlists (user_id, playlist_id, period, release_year, years_ago) 
VALUES (1, 'spotify_playlist_id', 'YEAR', '2025', '0');
```

## Troubleshooting Protocols

### Common Operational Anomalies

- **API Rate Constraints**: The system includes pauses to respect service limitations
- **Cross-Platform Track Matching**: Multiple fallback protocols ensure reliable matching
- **Data Absence**: Consult the `error_log` table for diagnostic information

### Database Maintenance

Periodic data optimization:

```sql
DELETE FROM last_fm_data WHERE date_time < DATE_SUB(NOW(), INTERVAL 2 YEAR);
```

## License

[MIT License](LICENSE)

## Acknowledgements

- [Last.fm API](https://www.last.fm/api)
- [Spotify Web API](https://developer.spotify.com/documentation/web-api/)
- [Odesli API](https://odesli.co/)
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/)
- [Spotipy](https://spotipy.readthedocs.io/)
