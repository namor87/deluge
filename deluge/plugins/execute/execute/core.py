#
# core.py
#
# Copyright (C) 2009 Andrew Resch <andrewresch@gmail.com>
#
# Deluge is free software.
#
# You may redistribute it and/or modify it under the terms of the
# GNU General Public License, as published by the Free Software
# Foundation; either version 3 of the License, or (at your option)
# any later version.
#
# deluge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with deluge.    If not, write to:
# 	The Free Software Foundation, Inc.,
# 	51 Franklin Street, Fifth Floor
# 	Boston, MA  02110-1301, USA.
#
#    In addition, as a special exception, the copyright holders give
#    permission to link the code of portions of this program with the OpenSSL
#    library.
#    You must obey the GNU General Public License in all respects for all of
#    the code used other than OpenSSL. If you modify file(s) with this
#    exception, you may extend this exception to your version of the file(s),
#    but you are not obligated to do so. If you do not wish to do so, delete
#    this exception statement from your version. If you delete this exception
#    statement from all source files in the program, then also delete it here.
#
#

import os
import time
import hashlib
from subprocess import Popen, PIPE

from deluge.log import LOG as log
from deluge.plugins.pluginbase import CorePluginBase
import deluge.component as component
from deluge.configmanager import ConfigManager
from deluge.core.rpcserver import export
from deluge.event import DelugeEvent

DEFAULT_CONFIG = {
    "commands": []
}

EXECUTE_ID = 0
EXECUTE_EVENT = 1
EXECUTE_COMMAND = 2


class ExecuteCommandAddedEvent(DelugeEvent):
    """
    Emitted when a new command is added.
    """
    def __init__(self, command_id, event, command):
        self._args = [command_id, event, command]

class ExecuteCommandRemovedEvent(DelugeEvent):
    """
    Emitted when a command is removed.
    """
    def __init__(self, command_id):
        self._args = [command_id]

class Core(CorePluginBase):
    def enable(self):
        self.config = ConfigManager("execute.conf", DEFAULT_CONFIG)
        event_manager = component.get("EventManager")
        event_manager.register_event_handler("TorrentFinishedEvent",
            self.on_torrent_finished)
        log.debug("Example core plugin enabled!")

    def execute_commands(self, torrent_id, event):
        torrent = component.get("TorrentManager").torrents[torrent_id]
        info = torrent.get_status(["name", "save_path",
            "move_on_completed_path"])

        torrent_name = info["name"]
        path = info["save_path"] if \
            info["move_on_completed_path"] == info["save_path"] else \
            info["move_on_completed_path"]

        for command in self.config["commands"]:
            if command[EXECUTE_EVENT] == event:
                command = os.path.expandvars(command[EXECUTE_COMMAND])
                command = os.path.expanduser(command)
                p = Popen([command, torrent_id, torrent_name, path],
                    stdin=PIPE, stdout=PIPE, stderr=PIPE)
                if p.wait() != 0:
                    log.warn("Execute command failed with exit code %d",
                        p.returncode)

    def disable(self):
        self.config.save()
        event_manager = component.get("EventManager")
        event_manager.deregister_event_handler("TorrentFinishedEvent",
            self.on_torrent_finished)
        log.debug("Example core plugin disabled!")

    def on_torrent_finished(self, torrent_id):
        self.execute_commands(torrent_id, "complete")

    ### Exported RPC methods ###
    @export
    def add_command(self, event, command):
        command_id = hashlib.sha1(str(time.time())).hexdigest()
        self.config["commands"].append((command_id, event, command))
        component.get("EventManager").emit(ExecuteCommandAddedEvent(command_id, event, command))

    @export
    def get_commands(self):
        return self.config["commands"]

    @export
    def remove_command(self, command_id):
        for command in self.config["commands"]:
            if command[EXECUTE_ID] == command_id:
                self.config["commands"].remove(command)
                component.get("EventManager").emit(ExecuteCommandRemovedEvent(command_id))
                break

    @export
    def save_command(self, command_id, event, cmd):
        for command in self.config["commands"]:
            if command[EXECUTE_ID] == command_id:
                command[EXECUTE_EVENT] = event
                command[EXECUTE_COMMAND] = cmd
                break