# -*- Mode: python; coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
#
# Copyright (C) 2013 - Benjamin Bach <benjamin@overtag.dk>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.

from gi.repository import GObject  # @UnresolvedImport
from gi.repository import Gtk  # @UnresolvedImport
from gi.repository import Gdk  # @UnresolvedImport
from gi.repository import GdkPixbuf  # @UnresolvedImport
from gi.repository import Pango
from gi.repository import RB

import rb  # @UnresolvedImport
from CairoWidgets import FullscreenEntryButton
from synclyPrefs import GSetting
import Util

import os
import mimetypes

from syncly_rb3compat import url2pathname

class Fullscreen(Gtk.Window):
    # Scales the prefetched album art for later use
    ALBUM_ART_W = 800
    ALBUM_ART_H = 800

    def __init__(self, toggle_action_group, plugin):

        self.shell = plugin.object
        self.player = self.shell.props.shell_player
        self.backend = plugin  # Plugin instance

        # The fullscreen window
        Gtk.Window.__init__(self)
        # Referenced in CSS
        self.set_name("syncly-fullscreen-window")
        # If the window is closed in any event, 'delete_event' method is called
        self.connect("delete_event", self.delete_event)
        # For specific keyboard key presses
        self.connect("key_press_event", self.key_press)

        w = self
        s = w.get_screen()
        # Using the screen of the Window, the monitor it's on can be identified
        m = s.get_monitor_at_window(s.get_active_window())
        # Then get the geometry of that monitor
        monitor = s.get_monitor_geometry(m)
        # This is an example output
        print("Height: %s, Width: %s" % (monitor.height, monitor.width))
        if monitor.height < monitor.width:
            self._albumCoverHeight = monitor.height / 3
            self._albumCoverWidth = monitor.height / 3
        else:
            self._albumCoverHeight = monitor.width / 3
            self._albumCoverWidth = monitor.width / 3

        # Setting the icon that shows on Alt+Tab
        try:
            icon_theme = Gtk.icon_theme_get_default()
            self.set_icon(icon_theme.load_icon("view-fullscreen",
                                               Gtk.ICON_SIZE_DIALOG, Gtk.ICON_LOOKUP_FORCE_SVG))
        except:
            pass

        # If no album art is available, the default image
        self.no_artwork = GdkPixbuf.Pixbuf.new_from_file_at_size(
            rb.find_plugin_file(self.backend, "img/rhythmbox-missing-artwork.svg"),
            self._albumCoverWidth,
            self._albumCoverHeight
        )

        # Retrieve the lyrics folder location
        self.lyrics_folder = Util.set_lyrics_folder()

        # Create and put together all the elements in the sidebar (but don't show yet)
        self.init_window(monitor)

        # If nothing is playing, opens fullscreen window -> (show default image)
        self.set_artwork()        
        # Add the background colour, text properties
        self.gtk_style()
        # Show and go fullscreen
        self.show_all()
        self.fullscreen()

        self.pause_circle_exists = False
        # Used for synchronized lyrics
        self.tags = None
        self.current_tag = None
        # Signal flags
        self.fsc_id = None
        self.fsrc_id = None
        self.fec_id = None
        self.fspc_id = None
        # The toggle switch for the plugin in the view menu bar
        self.toggle_action_group = toggle_action_group

        # If window opened with the song paused, show the play circle
        if self.player.get_playing_source():
            if not self.player.get_playing()[1]:
                self.add_play_circle()

        # Colour for highlighting text
        rgba = Gdk.RGBA()
        rgba.parse("#009fd4")
        # tag to style headers bold and underlined
        self.tag = self.textbuffer.create_tag(None, size_points=24, underline=Pango.Underline.SINGLE, weight=Pango.Weight.BOLD, foreground_rgba=rgba, pixels_above_lines=10, pixels_below_lines=20)
        # tag to highlight synchronized lyrics
        self.sync_tag = self.textbuffer.create_tag(None, weight=Pango.Weight.BOLD, foreground_rgba=rgba)

        # Receive notification of song changes
        self.fsrc_id = self.player.connect("playing-source-changed", self.reload_lyrics)
        self.fsc_id = self.player.connect("playing-song-changed", self.reload_lyrics)
        # self.player.connect("playing-changed", self.reload_lyrics)

        # TODO: This signal is not fired - which should we listen for?
        # We should use the cover_db,
        # but what are its signals??
        cover_db = RB.ExtDB(name='album-art')
        self.fspc_id = self.player.connect("playing-song-property-changed", self.notify_metadata)
        cover_db.connect("added", self.notify_cover_art_change)

        # Load lyrics on immediatley opening the fullscreen window
        self.reload_lyrics(self.player, self.player.get_playing_entry())

    def init_window(self, monitor):
        self.set_title("Fullscreen Synchronised Lyrics View")
        # Initialising the icons for pausing and playing
        self.set_play_circle()
        self.set_pause_circle()

        # Container for the album art and lyrics inside the window
        self.grid = Gtk.Grid(column_spacing=25)

        # To show the play/pause icons on top of the album art
        self.overlay = Gtk.Overlay()
        # To make image clickable put it inside an eventbox
        self.event_box = Gtk.EventBox()
        self.event_box.set_name("event-box")
        self.album_widget = Gtk.Image()
        self.album_widget.set_name("album-art")
        # Overlay
        # |-- Eventbox (connected to signals) 
        #    |-- Image
        self.overlay.set_margin_left(monitor.width/10)
        self.overlay.add(self.event_box)
        self.event_box.add(self.album_widget)
        self.event_box.connect("button_press_event", self.image_click_playpause)
        self.event_box.connect("enter_notify_event", self.add_pause_circle)
        self.event_box.connect("leave_notify_event", self.remove_pause_circle)

        # Create a TextView for displaying lyrics
        self.textview = Gtk.TextView()
        self.textview.set_name("syncly-lyrics-textview")
        self.textview.set_editable(False)
        self.textview.set_cursor_visible(False)
        self.textview.set_left_margin(10)
        self.textview.set_right_margin(10)
        self.textview.set_pixels_above_lines(5)
        self.textview.set_pixels_below_lines(5)
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        self.textview.set_justification(Gtk.Justification.CENTER)

        # Put the TextView inside a ScrollView
        sw = Gtk.ScrolledWindow()
        sw.set_hexpand(True) # important
        sw.set_vexpand(True)
        sw.add(self.textview)
        sw.set_shadow_type(Gtk.ShadowType.NONE)
        # Hide the vertical scrollbar
        vsb = sw.get_vscrollbar()
        vsb.set_visible(False)

        # Initialize a TextBuffer to store lyrics in
        self.textbuffer = Gtk.TextBuffer()
        self.textview.set_buffer(self.textbuffer)

        # Attach the Overlay and ScrolledWindow to the grid
        self.grid.add(self.overlay)
        self.grid.attach_next_to(sw, self.overlay, Gtk.PositionType.RIGHT, 1, 1)

        # # Overlay for background image of window
        # main_overlay = Gtk.Overlay()
        # # The background image
        # main_image = Gtk.Image()
        # # Background from SVGBackgrounds.com
        # main_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
        #     rb.find_plugin_file(self.backend, "img/Liquid-Cheese.svg"),
        #     self.get_size().width,
        #     self.get_size().height)
        # main_image.set_from_pixbuf(main_pixbuf)
        # main_overlay.add(main_image)
        # # Now overlay the grid with all the elements
        # main_overlay.add_overlay(self.grid)
        # Now add everything to the window
        self.add(self.grid)

    def image_click_playpause(self, widget=None, event=None):
        # self.player.get_playing() -> returns (True, playing=True/False). https://developer.gnome.org/rhythmbox/unstable/RBShellPlayer.html#rb-shell-player-get-playing
        print("image clicked")
        # self.player.props.playing cannot say if playing or paused
        if self.player.get_playing_source():
            self.album_widget.set_opacity(0.5)
            if self.player.get_playing()[1]:
                self.remove_pause_circle(self.pause_circle, None)
                self.player.pause()
                self.add_play_circle()
            else:
                self.remove_play_circle()
                self.player.play()
                self.add_pause_circle(self.pause_circle, None)

    def set_play_circle(self):
        self.play_circle = Gtk.Image()
        self.play_circle_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
            rb.find_plugin_file(self.backend, "img/play-circle.svg"),
            self._albumCoverWidth/4,
            self._albumCoverHeight/4
        )
        self.play_circle.set_from_pixbuf(self.play_circle_pixbuf)
        self.play_circle.show_all()

    def set_pause_circle(self):
        self.pause_circle = Gtk.Image()
        self.pause_circle_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
            rb.find_plugin_file(self.backend, "img/pause-circle.svg"),
            self._albumCoverWidth/4,
            self._albumCoverHeight/4
        )
        self.pause_circle.set_from_pixbuf(self.pause_circle_pixbuf)
        self.pause_circle.show_all()

    def add_play_circle(self):
        self.overlay.add_overlay(self.play_circle)
        # Click passes through the image to the Eventbox
        self.overlay.set_overlay_pass_through(self.play_circle, True)

    def remove_play_circle(self):
        self.overlay.remove(self.play_circle)

    def add_pause_circle(self, widget, event):
        # Play/pause check needed for "enter_notify_event"
        if self.player.get_playing_source():
            self.album_widget.set_opacity(0.5)
            if self.player.get_playing()[1]:
                self.overlay.add_overlay(self.pause_circle)
                # Click passes through the image to the Eventbox
                self.overlay.set_overlay_pass_through(self.pause_circle, True)
                self.pause_circle_exists = True
            else:
                self.pause_circle_exists = False

    def remove_pause_circle(self, widget, event):
        self.album_widget.set_opacity(1)
        if self.pause_circle_exists:
            self.overlay.remove(self.pause_circle)
            self.pause_circle_exists = False
        
    def gtk_style(self):
        css = b"""
        #syncly-fullscreen-window {
            background-size: 25px 25px;
            background-image: linear-gradient(45deg, grey 1px, #050709 1px), linear-gradient(135deg, grey 1px, #050709 1px);
        }
        #lyrics-textviesyncly-w {
            background: transparent;
            font-family: Helvetica;
            font-size: 18px;
            font-weight: 400;
        }
        """
        self.style_provider = Gtk.CssProvider()
        self.style_provider.load_from_data(css)

        # Must remove while exiting otherwise applies for the rhythmbox player as well
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            self.style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # Put the album art retrieved into a Gtk.Image()
    def set_artwork(self, pixbuf=None):
        if not pixbuf:
            self.albumPixbuf = self.no_artwork
        else:
            # Keep aspect ratios
            h = pixbuf.get_height()
            w = pixbuf.get_width()
            # print("pre h = %s, pre w = %s" % (h, w))
            if h == 0 or w == 0:
                self.albumPixbuf = self.no_artwork
            else:
                # Scaled to the monitor width and height
                scaled_w = w / (h / float(self._albumCoverHeight)) if h > w else self._albumCoverWidth
                scaled_h = h / (w / float(self._albumCoverWidth)) if w > h else self._albumCoverHeight
                pixbuf = pixbuf.scale_simple(int(scaled_w), int(scaled_h),
                                             GdkPixbuf.InterpType.BILINEAR)
                self.albumPixbuf = pixbuf
            # print("h = %s, w = %s" % (h, w))

        self.album_widget.set_from_pixbuf(self.albumPixbuf)
        self.album_widget.show_all()

    def reload_lyrics(self, player, entry):
        entry = self.player.get_playing_entry()
        # There is nothing playing, return
        if not entry:
            return

        # clear sync stuff
        if self.tags is not None:
            self.tags = None
            self.current_tag = None
            start, end = self.textbuffer.get_bounds()
            print(self.textbuffer.get_tag_table().get_size())
            self.textbuffer.remove_tag(self.sync_tag, start, end)
            print(self.textbuffer.get_tag_table().get_size())

        # don't show lyrics for podcasts and radio
        if entry.get_entry_type().get_name() in ('iradio', 'podcast-post'):
            print("entry type: " + entry.get_entry_type().get_name())
            self.toggle_action_group.get_action("ToggleSynchronisedLyricSideBar").set_active(False)
            return

        # get the song data
        self.artist = entry.get_string(RB.RhythmDBPropType.ARTIST)
        self.title = entry.get_string(RB.RhythmDBPropType.TITLE)

        print("search lyrics for " + self.artist + " - " + self.title)

        self.path = Util.build_cache_path(self.lyrics_folder, self.artist, self.title)
        print(self.path)

        # Set cover art
        self.set_cover_art(entry)
        # Show lyrics
        self.lyrics, self.tags = Util.show_lyrics(self.textbuffer, self.tag, self.tags, self.artist, self.title, Util.get_lyrics_from_cache(self.path))

        # Connect to elapsed-changed signal to handle synchronized lyrics
        self.fec_id = self.player.connect('elapsed-nano-changed', Util.elapsed_changed, self.current_tag, self.sync_tag, self.tags, self.textbuffer, self.textview)
    
    def set_cover_art(self, entry):
        if entry:
            self.set_artwork(self.get_cover(entry))

    def get_cover(self, entry):
        if entry:
            # Try to find an album cover in the folder of the currently playing track
            cover_dir = os.path.dirname(url2pathname(entry.get_playback_uri()).replace('file://', ''))
            # TODO: use os.walk()
            if os.path.isdir(cover_dir):
                for f in os.listdir(cover_dir):
                    file_name = os.path.join(cover_dir, f)
                    mt = mimetypes.guess_type(file_name)[0]
                    if mt and mt.startswith('image/'):
                        if True in [x in os.path.splitext(f)[0].lower() for x in
                                    ['cover', 'album', 'albumart', 'folder', 'front']]:
                            return GdkPixbuf.Pixbuf.new_from_file_at_size(file_name, self.ALBUM_ART_W, self.ALBUM_ART_H)

            # Otherwise use what's found by the album art plugin
            key = entry.create_ext_db_key(RB.RhythmDBPropType.ALBUM)
            cover_db = RB.ExtDB(name='album-art')
            art_location = cover_db.lookup(key)
            if art_location and not isinstance(art_location, str):
                # RB 3.2 returns a tuple (path, key)
                art_location = art_location[0]

            if art_location and os.path.exists(art_location):
                return GdkPixbuf.Pixbuf.new_from_file_at_size(art_location, self.ALBUM_ART_W, self.ALBUM_ART_H)

    def notify_metadata(self, player, uri, prop, *args, **kwargs):
        """Subscribe to metadata changes from database"""
        self.set_cover_art(player.get_playing_entry())

    def notify_cover_art_change(self, *args):
        self.set_cover_art(self.shell.props.shell_player.get_playing_entry())

    # If the window is closed due to any event, exit gracefully
    def delete_event(self, widget, event, data=None):
        self.quit_window()

    def key_press(self, widget, event, data=None):
        # Quit on ESC key press
        if event.keyval == Gdk.KEY_Escape:
            self.quit_window()
        # Play/pause the song on Space key press
        elif event.keyval == Gdk.KEY_space:
            self.image_click_playpause()

    def quit_window(self):
        ''' Look into this for this scenario : Changing settings to sidebar with fullscreen open --> we want to destroy the fullscreen window and pop out the sidebar '''
        # If the plugin is activated in the view menu bar, deactivate it as the window is being destroyed
        action = self.toggle_action_group.get_action('ToggleSynchronisedLyricSideBar')
        if action.get_active():
            self.toggle_action_group.get_action('ToggleSynchronisedLyricSideBar').set_active(False)

        # Remove the styling applied for the window and TextView
        try:
            Gtk.StyleContext.remove_provider_for_screen(
            Gdk.Screen.get_default(),
            self.style_provider)
        except:
            pass
        # Disconnect all signal
        self.disconnect_fs_signals()
        # Destroy the window
        self.destroy()

    def disconnect_fs_signals(self):
        if self.fsc_id is not None:
            self.player.disconnect(self.fsc_id)
            self.player.disconnect(self.fsrc_id)
            self.player.disconnect(self.fspc_id)
            self.fsc_id = None
            self.fsrc_id = None
            self.fspc_id = None
        if self.fec_id is not None:
            self.player.disconnect(self.fec_id)
            self.fec_id = None

