import re
import os, sys
import string
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import xml.dom.minidom
import Util

from urllib.parse import urlparse
from urllib.parse import unquote

from gi.repository import RB
from gi.repository import Gtk
from gi.repository import Gio


try:
    import chardet
except:
    print("module chardet not found or not installed!")

# Splits the LRC file into time stamp tags and lyrics
def parse_lrc(data):
    tag_regex = "(\[\d+\:\d+\.\d*])"
    match = re.search(tag_regex, data)

    # Not an LRC file
    if match is None:
        return (data, None)

    data = data[match.start():]
    splitted = re.split(tag_regex, data)[1:]

    tags = []
    lyrics = ''
    for i in range(len(splitted)):
        if i % 2 == 0:
            # tag
            tags.append((time_to_seconds(splitted[i]), splitted[i + 1]))
        else:
            # lyrics
            lyrics += splitted[i]

    return (lyrics, tags)

# Return every time stamp in nanoseconds. [01:13.56] -> 73,560,000,000 ns
def time_to_seconds(timestamp):
    timestamp = re.sub(r'[^\d\.]', ' ', timestamp).split()
    seconds = float(timestamp[-1])
    for n in range(1, 3, 1):
        try:
            seconds += float(timestamp[-1 - n]) * 60 ** n
        except IndexError:
            pass
    return seconds * 10 ** 9

# Folder where all Song.lrc files are stored
def set_lyrics_folder():
    folder = os.path.join(RB.user_cache_dir(), "synchronised_lyrics")
    folder = os.path.expanduser(folder)
    if not os.path.exists(folder):
        os.mkdir(folder)

    return folder

# Get the path to a particular artist's song lyric file
def build_cache_path(lyrics_folder, artist, title):
    artist_folder = os.path.join(lyrics_folder, artist[:128])
    if not os.path.exists(artist_folder):
        os.mkdir(artist_folder)

    return os.path.join(artist_folder, title[:128] + '.lrc')

# Open, read the Song.lrc file and return its contents (if it exists, else empty string)
def get_lyrics_from_cache(path):
    # try to load lyrics from cache
    if os.path.exists(path):
        try:
            cachefile = open(path, "r")
            lyrics = cachefile.read()
            cachefile.close()
        except:
            print("error reading cache file")
            return ""

        print("got lyrics from cache")
        return lyrics

    return ""

# Display the artitst, title and song lyrics on the textbuffer
def show_lyrics(textbuffer, tag, tags, artist, title, lyrics):
    if lyrics == "":
        print("no lyrics found")
        lyrics = _("No lyrics found. Add lyrics through the drop-down menu in the sidebar")
        tags = None
    else:
        lyrics, tags = Util.parse_lrc(lyrics)

    textbuffer.set_text("%s - %s\n%s" % (artist, title, lyrics))

    # make 'artist - title' header bold and underlined 
    start = textbuffer.get_start_iter()
    end = start.copy()
    end.forward_to_line_end()
    textbuffer.apply_tag(tag, start, end)

    return lyrics, tags

# Highlight text according to the time stamp (tags variable)
def elapsed_changed(player, seconds, current_tag, sync_tag, tags, textbuffer, textview):
    # Not an LRC file, so no tags
    if tags is None:
        return

    matching_tag = None
    for tag in tags:
        time, _ = tag
        # Iterate through all time stamps (ascending order) and find the one with time stamp greater than the song's current playing time
        if time > seconds:
            break
        matching_tag = tag

    # No tag, or same as previous tag (song has not adavanced enough to highlight next line, or ended)
    if matching_tag is None or current_tag == matching_tag:
        return

    # Assign the new tag to current_tag variable
    current_tag = matching_tag

    # Remove old tag
    start, end = textbuffer.get_bounds()
    textbuffer.remove_tag(sync_tag, start, end)

    # Highlight next line
    line = tags.index(current_tag) + 1
    start = textbuffer.get_iter_at_line(line)
    end = start.copy()
    end.forward_to_line_end()
    textbuffer.apply_tag(sync_tag, start, end)
    # Scroll if necessary
    textview.scroll_to_iter(start, 0, True, 0, 0.5)
