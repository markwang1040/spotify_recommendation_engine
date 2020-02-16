import numpy as np
import pandas as pd
from pandas.io.json import json_normalize
import requests
import json
import random
import urllib
import urllib.parse
from pprint import pprint
import webbrowser
import base64
from collections import MutableMapping 

# Global variables
CLIENT_ID = "1d074dccb268434b86d564fc3c49c040"
CLIENT_SECRET = "9c74275903e64f8c9bcc9dfd9195e0ff"

auth_hash = str(random.getrandbits(128)) # move this somewhere else, should not be global

redirect_uri = "https://example.com/callback"

scopes_list = ["ugc-image-upload", 
    "user-read-playback-state", 
    "user-modify-playback-state", 
    "user-read-currently-playing", 
    "streaming", 
    "app-remote-control", 
    "user-read-email",                
    "user-read-private", 
    "playlist-read-collaborative", 
    "playlist-modify-public", 
    "playlist-read-private", 
    "playlist-modify-private", 
    "user-library-modify", 
    "user-library-read", 
    "user-top-read", 
    "user-read-recently-played", 
    "user-follow-read", 
    "user-follow-modify"
]

scope_string = '%20'.join(scopes_list)

# user_data_dict endpoint:"https://api.spotify.com/v1/me/"
user_data_dict = {
    "profile":"",
    "playlists":"playlists?limit=50",
    "top_artists":"top/artists?limit=50&time_range=short_term",
    "top_tracks":"top/tracks?limit=50&time_range=short_term",
    "followed_artists":"following?type=artist&limit=50",
    "recently_played":"player/recently-played?limit=50",
    "saved_albums":"albums?limit=50",
    "saved_tracks":"tracks?limit=50"
}

def convert_flatten(d, parent_key ='', sep ='_'):
    # flattens dict:input dict, returns dict
    items = [] 
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k 
        if isinstance(v, MutableMapping):
            items.extend(convert_flatten(v, new_key, sep = sep).items()) 
        else:
            items.append((new_key, v)) 
    return dict(items) 

def user_auth():
    # request user authorization and request refresh and access tokens
    options_dict = {"client_id":CLIENT_ID,
        "response_type":"code",
        "redirect_uri":urllib.parse.quote_plus(redirect_uri),
        "state":auth_hash,
        "scope":scope_string,
        "show_dialog":"true"
        }
    endpoint = "https://accounts.spotify.com/authorize"
    r = requests.get(endpoint + "?" + "&".join([key + "=" + value for key, value in options_dict.items()]), allow_redirects=True)
    webbrowser.open(r.url) 
    callback_url = input("Enter your the URL provided upon authentication:")
    code = callback_url.strip("https://example.com/callback?code=").split("&state=")[0]
    state = callback_url.strip("https://example.com/callback?code=").split("&state=")[1]
    auth_str = '{}:{}'.format(CLIENT_ID, CLIENT_SECRET)
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()
    header = {'Authorization':'Basic {}'.format(b64_auth_str)}
    data = {
        'grant_type':'authorization_code',
        'code':code,
        'redirect_uri':redirect_uri
        }
    auth = requests.post('https://accounts.spotify.com/api/token', headers=header, data=data)
    global auth_json
    auth_json = json.loads(auth.text)

def get_token(auth_json):
    # request new tokens using refresh_token
    client_auth_str = '{}:{}'.format(CLIENT_ID, CLIENT_SECRET)
    b64_client_auth_str = base64.b64encode(client_auth_str.encode()).decode()
    header = {'Authorization':'Basic {}'.format(b64_client_auth_str)}
    data = {"grant_type":"refresh_token", "refresh_token":auth_json["refresh_token"]}
    
    refresh = requests.post('https://accounts.spotify.com/api/token', headers=header, data=data)
    refresh_json = json.loads(refresh.text)
    global refreshed_token
    refreshed_token = refresh_json["access_token"]

def get_user_data(user_element):
    # request an aspect of user data
    get_token(auth_json)
    headers = {
        'Accept':'application/json',
        'Content-Type':'application/json',
        'Authorization':'Bearer {}'.format(refreshed_token)
        }
    endpoint = "https://api.spotify.com/v1/me/"
    url = endpoint + user_data_dict[user_element]
    user_info = requests.get(url=url, headers=headers)
    user_info_dict = json.loads(user_info.text)
    if "next" in user_info_dict and user_info_dict["next"] is not None:
        more_user_info_url = user_info_dict["next"] 
        while  more_user_info_url is not None:
            get_token(auth_json)
            # grab more user data if total > limit=50
            headers = {
                'Accept':'application/json',
                'Content-Type':'application/json',
                'Authorization':'Bearer {}'.format(refreshed_token)
                }
            more_user_info = requests.get(url=more_user_info_url, headers=headers) #
            more_user_info_dict = json.loads(more_user_info.text) # 
            more_user_info_url = more_user_info_dict["next"] #
            user_info_dict["items"].extend(more_user_info_dict["items"]) 
    return user_info_dict

def get_master_user_profile():
    # request all user data and assemble dict
    global master_user_profile
    master_user_profile = {key:get_user_data(key) for key in user_data_dict}

def clean_master_user_profile(master_user_profile):
    # cleans dict
    profile = {
        key:val for key, val in master_user_profile["profile"].items() 
               if key in ["country", "explicit_content", "uri"]
    } 
    playlists = [
        {
            key:val for key, val in convert_flatten(playlist).items() 
            if key in ["description", "owner_display_name", "name", "uri"]
        } 
        for playlist in master_user_profile["playlists"]["items"]
    ]
    top_artists = [
        {
            key:val for key, val in convert_flatten(artist).items() 
            if key in ["genres", "name", "followers_total", "popularity", "uri"]
        } 
        for artist in master_user_profile["top_artists"]["items"]
    ]
    top_tracks = [
        {
            key:val for key, val in convert_flatten(track).items() 
            if key in [
                "album_release_date", "album_name", "album_uri", "artists", "duration_ms", 
                "explicit", "name", "popularity", "track_number", "uri"
            ]
        } 
        for track in master_user_profile["top_tracks"]["items"]
    ]
    for i in range(len(top_tracks)):
        top_tracks[i]["artist_name"] = top_tracks[i]["artists"][0]["name"]
        top_tracks[i]["artist_uri"] = top_tracks[i]["artists"][0]["uri"]
    top_tracks = [
        {
            key:val for key, val in track.items() 
            if key not in ["artists"]
        } 
        for track in top_tracks
    ]
    followed_artists = [
        {
            key:val for key, val in convert_flatten(artist).items() 
            if key in ["genres", "name", "followers_total", "popularity", "uri"]
        } 
        for artist in master_user_profile["top_artists"]["items"]
    ]
    recently_played = [
        {
            key:val for key, val in convert_flatten(track).items() 
            if key in [
                "track_album_release_date", "track_album_name", "track_album_uri", "track_artists", "track_duration_ms", 
                "track_explicit", "track_name", "track_popularity", "track_track_number", "uri", "played_at"
            ]
        } 
        for track in master_user_profile["recently_played"]["items"]
    ]
    for i in range(len(recently_played)):
        recently_played[i]["artist_name"] = recently_played[i]["track_artists"][0]["name"]
        recently_played[i]["artist_uri"] = recently_played[i]["track_artists"][0]["uri"]
    recently_played = [
        {
            key.replace('track_', ''):val for key, val in track.items() 
            if key not in ["track_artists"]
        } 
        for track in recently_played
    ]
    saved_albums = [
        {
            key:val for key, val in convert_flatten(track).items() 
            if key in ["added_at", "album_release_date", "album_name", "album_genres", 
                       "album_label", "album_popularity", "album_uri", "album_artists"
                      ]
        } 
        for track in master_user_profile["saved_albums"]["items"]
    ]
    for i in range(len(saved_albums)):
        saved_albums[i]["artist_name"] = saved_albums[i]["album_artists"][0]["name"]
        saved_albums[i]["artist_uri"] = saved_albums[i]["album_artists"][0]["uri"]
    saved_albums = [
        {
            key.replace('album_', ''):val 
            for key, val in album.items() if key not in ["album_artists"]
        } 
        for album in saved_albums
    ]
    saved_tracks = [
        {
            key:val for key, val in convert_flatten(track).items() 
            if key in [
                "added_at", "track_album_release_date", "track_album_name", "track_album_uri", "track_artists", "track_duration_ms", 
                "track_explicit", "track_name", "track_popularity", "track_track_number", "track_uri"]
        } 
        for track in master_user_profile["saved_tracks"]["items"]
    ]
    for i in range(len(saved_tracks)):
        saved_tracks[i]["artist_name"] = saved_tracks[i]["track_artists"][0]["name"]
        saved_tracks[i]["artist_uri"] = saved_tracks[i]["track_artists"][0]["uri"]
    
    saved_tracks = [
        {
            key.replace('track_', ''):val 
            for key, val in track.items() if key not in ["track_artists"]
        } 
        for track in saved_tracks
    ]
    global cleaned_master_user_profile
    cleaned_master_user_profile = {
        'profile':profile, 
        'playlists':playlists, 
        'top_artists':top_artists, 
        'top_tracks':top_tracks, 
        'followed_artists':followed_artists, 
        'recently_played':recently_played, 
        'saved_albums':saved_albums, 
        'saved_tracks':saved_tracks
    }

def populate_album_genres(cleaned_master_user_profile):
    # populates the list of saved_albums within cleaned_master_user_profile dict with
    # a list of the first artist's genres
    for album in cleaned_master_user_profile["saved_albums"]:
        get_token(auth_json)
        headers = {
            'Accept':'application/json',
            'Content-Type':'application/json',
            'Authorization':'Bearer {}'.format(refreshed_token)
            }
        album_endpoint = "https://api.spotify.com/v1/albums/"
        album_url = album_endpoint + album["uri"].split(":")[2]
        album_info = requests.get(url=album_url, headers=headers)
        album_info_dict = json.loads(album_info.text)
        album_artist_uri = album_info_dict["artists"][0]["uri"]
        artist_enpoint = "https://api.spotify.com/v1/artists/"
        artist_url = artist_enpoint + album_artist_uri.split(":")[2]
        artist_info =  requests.get(url=artist_url, headers=headers)
        artist_info_dict = json.loads(artist_info.text)
        artist_genres = artist_info_dict["genres"]
        album.update(genres = artist_genres) 


def main():
    user_auth()
    print("Spotify user authorized.")
    get_master_user_profile()
    print("Object created: master_user_profile.")
    clean_master_user_profile(master_user_profile)
    print("Object created: cleaned_master_user_profile.")
    populate_album_genres(cleaned_master_user_profile)
    print("Populated albums with genres.")
    print("The Spotify profile contains the following elements:\n", cleaned_master_user_profile.keys())


if __name__ == "__main__":
    main()
