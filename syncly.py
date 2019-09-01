import re
import os
import threading
import webbrowser
import sys
import unicodedata
import operator
import mimetypes

from threading import Thread

import rb
from gi.repository import GObject
from gi.repository import Peas
from gi.repository import Gdk
from gi.repository import RB
from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gio

import Util
import Fullscreen
import Sidebar
from syncly_rb3compat import url2pathname
from syncly_rb3compat import ActionGroup
from syncly_rb3compat import ApplicationShell
from synclyPrefs import GSetting
from synclyPrefs import Preferences

view_menu_ui = """
<ui>
    <menubar name="MenuBar">
        <menu name="ViewMenu" action="View">
            <menuitem name="syncly" action="ToggleSynchronisedLyricSideBar" />
        </menu>
    </menubar>
</ui>
"""

# Expendable, not really necessary for right-click menu
context_ui = """
<ui>
    <popup name="BrowserSourceViewPopup">
        <placeholder name="PluginPlaceholder">
            <menuitem name="synclyPopup" action="synclyPopupAction"/>
        </placeholder>
      </popup>
 
    <popup name="PlaylistViewPopup">
        <placeholder name="PluginPlaceholder">
            <menuitem name="synclyPopup" action="synclyPopupAction"/>
        </placeholder>
    </popup>
 
    <popup name="QueuePlaylistViewPopup">
        <placeholder name="PluginPlaceholder">
            <menuitem name="synclyPopup" action="synclyPopupAction"/>
        </placeholder>
    </popup>
     
    <popup name="PodcastViewPopup">
        <placeholder name="PluginPlaceholder">
            <menuitem name="synclyPopup" action="synclyPopupAction"/>
        </placeholder>
    </popup>
</ui>
"""

# Basic part for every plugin
class syncly(GObject.Object, Peas.Activatable):
    __gtype_name__ = 'syncly'
    object = GObject.property(type=GObject.Object)

    # Scales the prefetched album art for later use
    ALBUM_ART_W = 800
    ALBUM_ART_H = 800

    def __init__(self):
        GObject.Object.__init__(self)
        # GObject.threads_init()
        # Gdk.threads_init()

    def do_activate(self):
        # Get references for the Shell and the Shell-player
        self.shell = self.object
        self.player = self.shell.props.shell_player
        self.appshell = ApplicationShell(self.shell)

         # Get the user preferences
        gs = GSetting()
        self.settings = gs.get_setting(gs.Path.PLUGIN)
        self.get_user_preferences(self.settings, None, gs)
        # Watch for setting changes
        self.skc_id = self.settings.connect('changed', self.get_user_preferences, gs)
        
        # Signal flags
        self.psc_id = None
        self.pec_id = None
        self.fsc_id = None
        self.fsrc_id = None
        self.fec_id = None
        self.fspc_id = None

        # Insert the 'synchronised lyrics' item into the menubar (view column)
        self.init_menu()
        # Initialise sidebar (but don't show), nothing for fullscreen window (None)
        self.window = None
        self.sidebar = Sidebar.Sidebar(self.toggle_action_group, plugin=self)

        print("activated plugin syncly")

    def do_deactivate(self):
        # Disconnect all signals, sidebar and window
        self.sidebar.disconnect_sb_signals()
        if self.window is not None:
            self.window = None
            self.window.quit_window()

        # Disconnect signal for setting changes
        self.settings.disconnect(self.skc_id)
        self.appshell.cleanup()

        self.sw = None
        self.textbuffer = None
        self.textview = None
        self.psc_id = None
        self.visible = None
        self.player = None
        self.toggle_action_group = None
        self.context_action_group = None
        self.appshell = None
        self.ui_id = None
        self.tag = None
        self.first = None
        self.current_source = None
        self.artist = None
        self.title = None
        self.clean_artist = None
        self.clean_title = None
        self.path = None
        self.lyrics_folder = None
        self.left_sidebar = None
        self.show_first = None
        self.position = None

        self.shell = None

        print("deactivated plugin syncly")

    def init_menu(self):
        # Add actions to the Menubar and Right click list
        self.toggle_action_group = ActionGroup(self.shell, 'synclyPluginToggleActions')
        self.toggle_action_group.add_action(func=self.sidebar_or_fullscreen,
                                            action_name='ToggleSynchronisedLyricSideBar', 
                                            label=_("Synchronised Lyrics"),
                                            action_state=ActionGroup.TOGGLE,
                                            action_type='app', 
                                            accel="<Ctrl><Shift>l",
                                            tooltip=_("Display synchronised lyrics for the current playing song"))
        self.appshell.insert_action_group(self.toggle_action_group)

        # self.context_action_group = ActionGroup(self.shell, 'synclyPluginPopupActions')
        # self.context_action_group.add_action(func=self.context_action_callback,
        #                                      action_name="synclyPopupAction", 
        #                                      label=_("Synchronised lyrics"),
        #                                      tooltip=_("Display synchronised lyrics for this song"))
        # self.appshell.insert_action_group(self.context_action_group)

        self.insert_ui()

    def insert_ui(self):
        self.appshell.add_app_menuitems(view_menu_ui, 'synclyPluginToggleActions', 'view')
        # self.appshell.add_browser_menuitems(context_ui, 'synclyPluginPopupActions')

    def get_user_preferences(self, settings, key, gs):
        # The only preference option given
        self.fullscreen = settings[gs.PluginKey.USE_WINDOW]

        # Called from do_activate()
        if key is None:
            return
        # Called when the settings was actually changed
        # self.sidebar_or_fullscreen()

    def sidebar_or_fullscreen(self, *args):
        # When the plugin is toggled on, check whether to show in fullscreen or sidebar
        if self.fullscreen:
            # If toggled off, destroy the window, and return
            if not self.toggle_action_group.get_action("ToggleSynchronisedLyricSideBar").get_active():
                if self.window is not None:
                    self.window.quit_window()
                    self.window = None
                return
            # If toggled on, disconnect from sidebar signals and show fullscreen
            self.sidebar.disconnect_sb_signals()
            self.show_fullscreen()    
        else:
            # Destroy fullscreen window and disconnect from all signals
            if self.window is not None:
                self.window.quit_window()
                self.window = None
            self.show_sidebar()

    def show_fullscreen(self, *args):
        self.window = Fullscreen.Fullscreen(self.toggle_action_group, plugin=self)

    def show_sidebar(self, *args):
        self.sidebar.show_sidebar()

    def context_action_callback(self, action, param=None, data=None):
        page = self.shell.props.selected_page
        if not hasattr(page, "get_entry_view"):
            return

        selected = page.get_entry_view().get_selected_entries()
        if not selected:
            print("nothing selected")
            return

        # if multiple selections, take first
        entry = selected[0]

        # Disconnect from song-changed and elapsed-change signals
        if self.psc_id:
            self.player.disconnect(self.psc_id)
            self.player.disconnect(self.pec_id)
            self.psc_id = None
            self.pec_id = None

        if not self.visible:
            self.toggle_action_group.get_action("ToggleSynchronisedLyricSideBar").set_active(True)

        self.search_lyrics(self.player, entry)
