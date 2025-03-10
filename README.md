# Last.fm Rewind

A powerful system that automatically creates personalized Spotify playlists based on your Last.fm listening history. This tool analyzes your listening patterns, identifies your top albums for a given time period, and creates Spotify playlists with representative tracks from those albums.

In its current state, you will need to know how to manually edit your database to run this, as no interface has been developed. 

Yet.

## Features

- **Personalized Playlists**: Create weekly or yearly playlists based on your most listened albums
- **Multiple Filtering Options**:
  - Filter by release year
  - Filter by time of day (exclude sleep hours, etc.)
  - Focus on songs vs. longer tracks (instrumentals, etc.)
- **Bandcamp Integration**: Find Bandcamp links for albums you love
- **Audio Analysis**: Stores Spotify audio features (danceability, energy, etc.) for deeper insights
- **Multi-user Support**: Manage playlists for multiple Last.fm accounts

## System Requirements

- Python 3.6+
- MySQL database
- Last.fm API key
- Spotify API credentials
- Odesli API key (formerly song.link) 

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/lastfm-music-inventory.git
   cd lastfm-music-inventory
   ```

2. Install required Python packages:
   ```
   pip install -r requirements.txt
   ```

3. Set up the MySQL database:
   ```
   mysql -u your_username -p < music-inventory-schema.sql
   ```

4. Create a `.env` file in the project root with the following parameters:
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

## Usage

### Adding Users

1. Add a user to the `users` table with their Last.fm username and email:
   ```sql
   INSERT INTO users (lastfm_id, email_address, approved) 
   VALUES ('your_lastfm_username', 'your_email@example.com', 'YES');
   ```

2. Set up a playlist configuration:
   ```sql
   INSERT INTO users_playlists (
       user_id, 
       playlist_id, 
       period, 
       release_year, 
       keep_updated, 
       years_ago
   ) VALUES (
       1,                          -- Your user ID from the users table
       'spotify_playlist_id_here', -- Spotify playlist ID
       'WEEK',                     -- WEEK or YEAR
       'ALL',                      -- ALL or specific year (like '2023')
       'YES',                      -- Keep updated automatically
       '0'                         -- 0 for current, or number of years ago
   );
   ```

### Running the Script

Run the main script to update playlists:

```
python main.py
```

This will:
1. Connect to the database
2. Process each user's Last.fm listening history
3. Identify their top albums for the specified period
4. Find representative tracks for each album
5. Create/update Spotify playlists with these tracks
6. Store the playlist information in the database

### Scheduled Execution

For automatic playlist updates, set up a cron job or scheduled task:

```
# Example cron job for weekly updates (runs every Sunday at 2 AM)
0 2 * * 0 /path/to/python /path/to/lastfm-music-inventory/main.py
```

## How It Works

1. **Data Collection**: Retrieves listening history from Last.fm API
2. **Data Enrichment**: Adds Spotify IDs, audio features, and Bandcamp links
3. **Album Analysis**: Identifies top albums based on listening time
4. **Track Selection**: Finds the most representative track from each album
5. **Playlist Creation**: Updates Spotify playlists with selected tracks

## Advanced Configuration

### Time Filtering

You can set time ranges to exclude (e.g., work hours) by updating the `start_time` and `end_time` columns in the `users` table:

```sql
UPDATE users SET start_time='09:00:00', end_time='17:00:00' WHERE id=1;
```

### Songs-Only Mode

To focus on shorter tracks (under 5 minutes) and exclude instrumentals:

```sql
UPDATE users_playlists SET songs_only='TRUE' WHERE id=1;
```

### Historical Playlists

Create playlists for previous years:

```sql
INSERT INTO users_playlists (user_id, playlist_id, period, years_ago) 
VALUES (1, 'spotify_playlist_id', 'YEAR', '1');
```

## Troubleshooting

### Common Issues

- **API Rate Limits**: The script includes pauses to respect Last.fm and Spotify API rate limits
- **Track Matching**: The system uses several fallback methods to match tracks across services
- **Missing Data**: Check the `error_log` table for detailed error information


## License

[MIT License](LICENSE)

## Acknowledgements

- [Last.fm API](https://www.last.fm/api)
- [Spotify Web API](https://developer.spotify.com/documentation/web-api/)
- [Odesli API](https://odesli.co/)
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/)
- [Spotipy](https://spotipy.readthedocs.io/)
