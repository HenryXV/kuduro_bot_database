import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from dotenv import load_dotenv

class Spotify():
    
    def __init__(self):
        load_dotenv()
        self.client_credential = SpotifyClientCredentials(client_id=os.getenv('SPOTIFY_ID'),
                                                          client_secret=os.getenv('SPOTIFY_SECRET'))
        self.sp = spotipy.Spotify(client_credentials_manager = self.client_credential)
        
    def search_tracks(self, search, limit):
        results = self.sp.search(q = search,
                                 type = 'track', 
                                 limit = limit)
        tracks = []
        
        for track in results['tracks']['items']:
            album_name = track['album']['name']
            artists_names = ', '.join([artist['name'] for artist in track['artists']])
            duration = track['duration_ms']
            track_name = track['name']
            uri = track['uri']
            
            tracks.append({'album_n': album_name,
                           'artists_n': artists_names,
                           'duration': duration,
                           'track_n': track_name,
                           'uri': uri})
        return tracks       