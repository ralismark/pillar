#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
gi.require_foreign('cairo')
from gi.repository import Gtk, Gdk, Gio

import asyncio
import socket

class Battery(Gtk.Label):
    def __init__(self, bat='BAT0', ac='AC'):
        Gtk.Label.__init__(self)
        self.get_style_context().add_class("battery")

        self.bat = bat
        self.ac = ac

        async def subscribe_loop():
            sock = socket.socket(family=socket.AF_UNIX)
            sock.connect('/var/run/acpid.socket')
            reader, writer = await asyncio.open_connection(sock=sock)
            while True:
                data = await reader.readline()
                if data.decode(errors='ignore').startswith('battery'):
                    await asyncio.sleep(0.5)
                    self.update()

        asyncio.ensure_future(subscribe_loop())

        async def loop():
            while True:
                self.update()
                await asyncio.sleep(10)

        asyncio.ensure_future(loop())

    def get_battery_stats(self):
        batpath = '/sys/class/power_supply/{}/'.format(self.bat)
        acpath = '/sys/class/power_supply/{}/'.format(self.ac)

        with open(batpath + 'capacity') as f:
            lines = f.readlines()
            capacity = min(int(lines[0]), 100)

        with open(batpath + 'status') as f:
            lines = f.readlines()
            status = lines[0].strip()

        return (status, capacity)

    def update(self):
        status,capacity = self.get_battery_stats()
        self.set_tooltip_text('{}: {}%'.format(status, capacity))

        if capacity >= 100:
            capacity = 100

        ctx = self.get_style_context()
        if status != 'Discharging':
            ctx.add_class('ac')
        else:
            ctx.remove_class('ac')

        if capacity == 100:
            ctx.add_class('full')
        else:
            ctx.remove_class('full')

        for i in range(10):
            ctx.remove_class("_{}".format(i))
            ctx.remove_class("{}_".format(i))

        ctx.add_class("_{}".format(capacity % 10))
        ctx.add_class("{}_".format(capacity // 10))

        if capacity >= 100:
            self.set_text('  ')
        elif status != 'Discharging':
            self.set_text('AC')
        else:
            self.set_text(str(capacity))
