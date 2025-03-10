-- MySQL Schema for Music Inventory System
-- This schema creates all tables needed for the combined music top albums script

-- Create the database if it doesn't exist
CREATE DATABASE IF NOT EXISTS music_inventory;
USE music_inventory;

-- Users table to store user information
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    lastfm_id VARCHAR(255) NOT NULL,
    email_address VARCHAR(255) NOT NULL,
    approved ENUM('YES', 'NO', 'PENDING') DEFAULT 'PENDING',
    start_time TIME DEFAULT NULL,
    end_time TIME DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY (lastfm_id)
);

-- Users playlists table to store playlist configurations
CREATE TABLE IF NOT EXISTS users_playlists (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    playlist_id VARCHAR(255) NOT NULL,
    period ENUM('WEEK', 'YEAR') DEFAULT 'WEEK',
    release_year VARCHAR(10) DEFAULT 'ALL',
    keep_updated ENUM('YES', 'NO') DEFAULT 'YES',
    years_ago VARCHAR(5) DEFAULT '0',
    play_year VARCHAR(4) DEFAULT NULL,
    songs_only ENUM('TRUE', 'FALSE') DEFAULT 'FALSE',
    populated TIMESTAMP NULL DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY (playlist_id)
);

-- Last.fm data to store user listening history
CREATE TABLE IF NOT EXISTS last_fm_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user VARCHAR(255) NOT NULL,
    artist VARCHAR(255) NOT NULL,
    album VARCHAR(255) NOT NULL,
    track VARCHAR(255) NOT NULL,
    date_time DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user (user),
    INDEX idx_artist_album (artist, album),
    INDEX idx_artist_album_track (artist, album, track),
    INDEX idx_date_time (date_time)
);

-- Last.fm album metadata
CREATE TABLE IF NOT EXISTS last_fm_album_meta (
    id INT AUTO_INCREMENT PRIMARY KEY,
    artist VARCHAR(255) NOT NULL,
    album VARCHAR(255) NOT NULL,
    spotify_album_id VARCHAR(255) DEFAULT NULL,
    spotify_update TIMESTAMP NULL DEFAULT NULL,
    bandcamp VARCHAR(255) DEFAULT NULL,
    bandcamp_update TIMESTAMP NULL DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY idx_artist_album (artist, album)
);

-- Last.fm track metadata
CREATE TABLE IF NOT EXISTS last_fm_track_meta (
    id INT AUTO_INCREMENT PRIMARY KEY,
    artist VARCHAR(255) NOT NULL,
    album VARCHAR(255) NOT NULL,
    track VARCHAR(255) NOT NULL,
    spotify_id VARCHAR(255) DEFAULT NULL,
    spotify_id_scan TIMESTAMP NULL DEFAULT NULL,
    spotify_album_id VARCHAR(255) DEFAULT NULL,
    scantime TIMESTAMP NULL DEFAULT NULL,
    danceability DECIMAL(5,4) DEFAULT NULL,
    energy DECIMAL(5,4) DEFAULT NULL,
    valence DECIMAL(5,4) DEFAULT NULL,
    tempo DECIMAL(8,4) DEFAULT NULL,
    popularity INT DEFAULT NULL,
    key_ INT DEFAULT NULL,
    loudness DECIMAL(6,3) DEFAULT NULL,
    mode_ INT DEFAULT NULL,
    speechiness DECIMAL(5,4) DEFAULT NULL,
    instrumentalness DECIMAL(5,4) DEFAULT NULL,
    liveness DECIMAL(5,4) DEFAULT NULL,
    duration_ms INT DEFAULT 0,
    release_date DATE DEFAULT NULL,
    re_release ENUM('YES', 'NO') DEFAULT NULL,
    sel_priority INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY idx_artist_album_track (artist, album, track),
    INDEX idx_spotify_id (spotify_id)
);

-- Weekly top 16 to store playlist tracks
CREATE TABLE IF NOT EXISTS weekly_top_16 (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user VARCHAR(255) NOT NULL,
    pl_order INT NOT NULL,
    artist VARCHAR(255) NOT NULL,
    album VARCHAR(255) NOT NULL,
    album_spotify_id VARCHAR(255) DEFAULT NULL,
    track VARCHAR(255) NOT NULL,
    track_spotify_id VARCHAR(255) DEFAULT NULL,
    bandcamp_url VARCHAR(255) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user (user),
    INDEX idx_artist_album (artist, album)
);

-- Error log table
CREATE TABLE IF NOT EXISTS error_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    log_row VARCHAR(255) NOT NULL,
    error TEXT NOT NULL,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Last.fm data update tracking
CREATE TABLE IF NOT EXISTS last_fm_data_update (
    id INT AUTO_INCREMENT PRIMARY KEY,
    update_from TIMESTAMP NOT NULL,
    update_epoch BIGINT NOT NULL,
    num_pages INT NOT NULL,
    num_tracks INT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sample data for testing (optional, comment out for production)
-- INSERT INTO users (lastfm_id, email_address, approved) VALUES ('example_user', 'user@example.com', 'YES');
-- INSERT INTO users_playlists (user_id, playlist_id, period) VALUES (1, 'spotify_playlist_id_here', 'WEEK');
