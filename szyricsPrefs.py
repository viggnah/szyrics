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

import os

from gi.repository import Gio  # @UnresolvedImport
from gi.repository import GObject  # @UnresolvedImport
from gi.repository import Gtk  # @UnresolvedImport
from gi.repository import PeasGtk  # @UnresolvedImport

import rb  # @UnresolvedImport

SCHEMA_PATH = 'org.gnome.rhythmbox.plugins.szyrics'
GLIB_DIR = "/usr/share/glib-2.0/schemas/"


class GSetting:
    '''
    This class manages the different settings that the plugins has to
    access to read or write.
    '''
    # storage for the instance reference
    __instance = None

    class __impl:
        """ Implementation of the singleton interface """
        # below public variables and methods that can be called for GSetting
        def __init__(self):
            '''
            Initializes the singleton interface, assigning all the constants
            used to access the plugin's settings.
            '''
            source = Gio.SettingsSchemaSource.get_default()
            if not source.lookup(SCHEMA_PATH, True):
                print("Trying to run a gksudo to get the schema installed")
                os.system(
                    'gksudo --message "Szyrics needs to install a glib xml schema for saving preferences. Please type in your admin password. Afterwards, restart Rhythmbox." cp "%s" "%s"' % (
                        rb.find_plugin_file(self, "org.gnome.rhythmbox.plugins.szyrics.gschema.xml"),
                        GLIB_DIR)
                )
                os.system('gksudo --message "Compiling new glib schemas" glib-compile-schemas "%s"' % GLIB_DIR)
                raise Exception("No glib xml schema installed")

            self.Path = self._enum(PLUGIN=SCHEMA_PATH)

            self.PluginKey = self._enum(USE_WINDOW='use-window')

            self.setting = {}

        def get_setting(self, path):
            '''
            Return an instance of Gio.Settings pointing at the selected path.
            '''
            try:
                setting = self.setting[path]
            except:
                self.setting[path] = Gio.Settings(path)
                setting = self.setting[path]

            return setting

        def get_value(self, path, key):
            '''
            Return the value saved on key from the settings path.
            '''
            return self.get_setting(path)[key]

        def set_value(self, path, key, value):
            '''
            Set the passed value to key in the settings path.
            '''
            self.get_setting(path)[key] = value

        def _enum(self, **enums):
            '''
            Create an enumn.
            '''
            return type('Enum', (), enums)

    def __init__(self):
        """ Create singleton instance """
        # Check whether we already have an instance
        if GSetting.__instance is None:
            # Create and remember instance
            GSetting.__instance = GSetting.__impl()

        # Store instance reference as the only member in the handle
        self.__dict__['_GSetting__instance'] = GSetting.__instance

    def __getattr__(self, attr):
        """ Delegate access to implementation """
        return getattr(self.__instance, attr)

    def __setattr__(self, attr, value):
        """ Delegate access to implementation """
        return setattr(self.__instance, attr, value)


class Preferences(GObject.Object, PeasGtk.Configurable):
    '''
    Preferences for the Fullscreen Plugin. It holds the settings for
    the plugin and also is the responsible of creating the preferences dialog.
    '''
    __gtype_name__ = 'SzyricsPreferences'
    object = GObject.property(type=GObject.Object)  # @ReservedAssignment

    def __init__(self):
        '''
        Initialises the preferences, getting an instance of the settings saved
        by Gio.
        '''
        GObject.Object.__init__(self)
        gs = GSetting()
        self.settings = gs.get_setting(gs.Path.PLUGIN)

    def do_create_configure_widget(self):
        '''
        Creates the plugin's preferences dialog
        '''
        # create the ui
        builder = Gtk.Builder()
        builder.add_from_file(
            rb.find_plugin_file(self, 'ui/szyrics_prefs.ui')
        )
        builder.connect_signals(self)

        gs = GSetting()
        # bind the toggles to the settings
        use_window = builder.get_object('use_window_checkbox')
        # use_window.connect("notify::active", self.switch_toggled, gs.PluginKey.USE_WINDOW)
        self.settings.bind(gs.PluginKey.USE_WINDOW,
                           use_window, 'active', Gio.SettingsBindFlags.DEFAULT)

        # return the dialog
        return builder.get_object('maingrid')

    def switch_toggled(self, switch, active, key):
        self.settings[key] = switch.get_active()