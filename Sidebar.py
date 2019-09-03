# -*- Mode: python; coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
#
# Copyright (C) 2019 - viggnah
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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
from gi.repository import Gio

import rb  # @UnresolvedImport
from szyricsPrefs import GSetting
from szyricsPrefs import Preferences
import Util
from szyrics_rb3compat import ActionGroup

import os
import shutil
import mimetypes

class Sidebar(Gtk.Grid):

    def __init__(self, toggle_action_group, plugin):
        # The sidebar container
        Gtk.Grid.__init__(self)

        self.plugin = plugin  # Plugin instance
        self.shell = plugin.object
        self.player = self.shell.props.shell_player
        
        # Retrieve the lyrics folder location
        self.lyrics_folder = Util.set_lyrics_folder()

        self.position = RB.ShellUILocation.RIGHT_SIDEBAR

        # To show the sidebar on first playback (on opening rhythmbox)
        self.first = True
        # Is the sidebar visible to the user?
        self.visible = False

        self.showing_on_demand = False
        # For lyrics synchronization
        self.tags = None
        self.current_tag = None

        # Initialise here, displays in file chooser dialog
        self.title = None
        self.artist = None
        # Must exist for file selected in chooser dialog to be copied
        self.path = None
        
        # Signal flags
        self.psc_id = None
        self.pec_id = None

        # Create and put together all the elements in the sidebar (but don't show yet)
        self.init_sidebar()
        # The toggle switch for the plugin in the view menu bar
        self.toggle_action_group = toggle_action_group

    def show_sidebar(self):
        # If sidebar is chosen from the settings and the plugin is activated this method is called
        # Search lyrics if already playing (this will be the case if user reactivates plugin during playback)        
        self.gtk_style()
        if self.first and self.player.props.playing:
            self.search_lyrics(self.player, self.player.get_playing_entry())
        elif not self.first:
            self.toggle_visibility(None)

    def init_sidebar(self):
        self.overlay = Gtk.Overlay()
        # Create a TextView for displaying lyrics
        self.textview = Gtk.TextView()
        self.textview.set_editable(False)
        self.textview.set_cursor_visible(False)
        self.textview.set_left_margin(10)
        self.textview.set_right_margin(10)
        self.textview.set_pixels_above_lines(5)
        self.textview.set_pixels_below_lines(5)
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)

        # Menu shown with some options
        drop_down = Gtk.MenuButton()
        icon = Gio.ThemedIcon(name="open-menu-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        drop_down.add(image)
        drop_down.set_halign(Gtk.Align.END)
        drop_down.set_valign(Gtk.Align.START)

        menu = self.create_menu()
        drop_down.set_popup(menu)

        # Put the TextView inside a ScrollView
        self.sw = Gtk.ScrolledWindow()
        # Name for adding CSS
        self.textview.set_name("szyrics-sidebar")
        self.sw.set_hexpand(True)
        self.sw.set_vexpand(True)
        self.sw.add(self.textview)
        self.sw.set_shadow_type(Gtk.ShadowType.IN)
        # Hide the vertical scrollbar
        vsb = self.sw.get_vscrollbar()
        vsb.set_visible(False)

        # Initialize a TextBuffer to store lyrics in
        self.textbuffer = Gtk.TextBuffer()
        self.textview.set_buffer(self.textbuffer)
        # insertion = self.textbuffer.get_mark('insert')
        # it = self.textbuffer.get_iter_at_mark(insertion)
        # anch = self.textbuffer.create_child_anchor(it)
        # self.textview.add_child_at_anchor(drop_down, anch)

        # Pack everything into side pane
        self.overlay.add(self.sw)
        self.overlay.add_overlay(drop_down)
        self.add(self.overlay)
        # self.attach_next_to(self.hb, self.sw, Gtk.PositionType.TOP, 1, 1)
        self.show_all() # important

        # Colour for highlighting text
        rgba = Gdk.RGBA()
        rgba.parse("#009fd4")
        rgba_bg = Gdk.RGBA()
        rgba_bg.parse("#050709")
        # tag to style headers bold and underlined
        self.tag = self.textbuffer.create_tag(None, underline=Pango.Underline.SINGLE, weight=Pango.Weight.BOLD, foreground_rgba=rgba, background_rgba=rgba_bg, justification=Gtk.Justification.CENTER, pixels_above_lines=10, pixels_below_lines=20)
        # tag to highlight synchronized lyrics
        self.sync_tag = self.textbuffer.create_tag(None, weight=Pango.Weight.BOLD, foreground_rgba=rgba, background_rgba=rgba_bg)

        # Sidebar is made, but not visible
        self.visible = False

    def gtk_style(self):
        css = b"""
        #szyrics-sidebar {
            background-size: 25px 25px;
            background-image: linear-gradient(45deg, grey 1px, #050709 1px), linear-gradient(135deg, grey 1px, #050709 1px);
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

    def create_menu(self):
        menu = Gtk.Menu()
        self.add_menu_item(menu, _("Add LRC file"), self.add_lrc_file)
        # menu.append(Gtk.SeparatorMenuItem())
        # self.add_menu_item(menu, _("Preferences"), self.show_preferences_dialog)
        # Choose the option of going fullscreen in the sidebar drop-down
        self.add_menu_item(menu, _("Fullscreen"), self.update_preferences, "check_item")
        menu.show_all()

        return menu

    def add_menu_item(self, menu, label, callback, check_item=None):
        if check_item is None:
            item = Gtk.MenuItem(label)
            item.connect("activate", callback)
            menu.append(item)
        else:
            item = Gtk.CheckMenuItem.new_with_label(label)
            item.set_active(False)
            item.connect("toggled", callback)
            menu.append(item)

    def add_lrc_file(self, action):
        error_msg = ""
        if self.artist and self.title and self.path:
            chooser_title = "Looking for lyrics to \"" + self.title + "\" by \"" + self.artist + "\""
            file_chooser = Gtk.FileChooserDialog(chooser_title, self.shell.get_property('window'),
                                                 action=Gtk.FileChooserAction.OPEN,
                                                 buttons=(_("_Cancel"), Gtk.ResponseType.CANCEL,
                                                 _("_Add"), Gtk.ResponseType.ACCEPT))
            file_chooser.set_select_multiple(False)
            res = file_chooser.run()

            if res == Gtk.ResponseType.ACCEPT:
                src = file_chooser.get_filename()
                # filename = os.path.basename(src)
                # if filename != (self.title + '.lrc'):
                #     return
                shutil.copy2(src, self.path)
            elif res != Gtk.ResponseType.CANCEL:
                error_msg = "Oops! Something went wrong whilst adding the file."

            file_chooser.destroy()
            self.search_lyrics(self.player, self.player.get_playing_entry())
        else:
            error_msg = "Please make sure the song you want to add lyrics for is playing."

        if error_msg != "":
            error_dialog = Gtk.MessageDialog(self.shell.get_property('window'),
                                             Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                             Gtk.MessageType.INFO, Gtk.ButtonsType.OK,
                                             error_msg)
            error_dialog.show_all()
            error_dialog.run()
            error_dialog.hide()

    def show_preferences_dialog(self, action):
        content = Preferences().do_create_configure_widget()

        dialog = Gtk.Dialog(_('szyrics Preferences'), self.shell.get_property('window'),
                            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                            (Gtk.STOCK_OK, Gtk.ResponseType.OK))

        content_area = dialog.get_content_area()
        content_area.pack_start(content, True, True, 0)

        dialog.show_all()
        dialog.run()
        dialog.hide()

    def update_preferences(self, check_item):
        # Update the settings variable to the switch's state
        gs = GSetting()
        settings = gs.get_setting(gs.Path.PLUGIN)
        settings[gs.PluginKey.USE_WINDOW] = check_item.get_active()

    def toggle_visibility(self, action, param=None, data=None):
        # Check if plugin is activated in the view menu bar
        action = self.toggle_action_group.get_action('ToggleSynchronisedLyricSideBar')

        if action.get_active():
            # Show the sidebar
            self.shell.add_widget(self, self.position, True, True)
            if self.psc_id is None:
                # Search lyrics everytime the song changes 
                self.psc_id = self.player.connect('playing-song-changed', self.search_lyrics)
            self.visible = True
            # The first time we directly search for lyrics, get toggled and come back here
            if not self.first and not self.showing_on_demand:
                self.search_lyrics(self.player, self.player.get_playing_entry())
        else:
            # Disconnect signals and remove sidebar
            self.disconnect_sb_signals()

    def search_lyrics(self, player, entry):
        # Clear sync stuff
        if self.tags is not None:
            self.tags = None
            self.current_tag = None
            start, end = self.textbuffer.get_bounds()
            print(self.textbuffer.get_tag_table().get_size())
            self.textbuffer.remove_tag(self.sync_tag, start, end)
            print(self.textbuffer.get_tag_table().get_size())

        # There is nothing playing, return
        if entry is None:
            return

        # don't show lyrics for podcasts and radio
        if entry.get_entry_type().get_name() in ('iradio', 'podcast-post'):
            print("entry type: " + entry.get_entry_type().get_name())
            if not self.first:
                self.first = True
                print('removing the sidebar')
                self.toggle_action_group.get_action("ToggleSynchronisedLyricSideBar").set_active(False)
            return

        # pop out sidebar at first playback
        if self.first and not self.showing_on_demand:
            self.first = False
            if not self.visible:
                self.toggle_action_group.get_action("ToggleSynchronisedLyricSideBar").set_active(True)
                # toggling the sidebar will start lyrics search again, so we can return here
                return

        # only do something if visible
        if not self.visible:
            return

        # get the song data
        self.artist = entry.get_string(RB.RhythmDBPropType.ARTIST)
        self.title = entry.get_string(RB.RhythmDBPropType.TITLE)

        print("search lyrics for " + self.artist + " - " + self.title)

        # Find path for this song, in the cache folder.
        # Cache_folder
        # |--Artist folder
        #    |--Song.lrc
        self.path = Util.build_cache_path(self.lyrics_folder, self.artist, self.title)
        print(self.path)

        # Show lyrics in the textbuffer, common for both window and sidebar
        self.lyrics, self.tags = Util.show_lyrics(self.textbuffer, self.tag, self.tags, self.artist, self.title, Util.get_lyrics_from_cache(self.path))
        # Connect to elapsed-changed signal to handle synchronized lyrics, common for both sidebar and window. Only tag and sync_tag different
        self.pec_id = self.player.connect('elapsed-nano-changed', Util.elapsed_changed, self.current_tag, self.sync_tag, self.tags, self.textbuffer, self.textview)

    def disconnect_sb_signals(self):
        # Remove the styling applied for the sidebar
        try:
            Gtk.StyleContext.remove_provider_for_screen(
            Gdk.Screen.get_default(),
            self.style_provider)
        except:
            pass
        # Remove the sidebar and disconnect from both signals
        if self.visible:
            self.shell.remove_widget(self, self.position)
            self.visible = False
        if self.psc_id is not None:
            self.psc_id = None
        if self.pec_id is not None:
            self.pec_id = None
