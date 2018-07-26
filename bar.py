#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
gi.require_foreign('cairo')
from gi.repository import Gtk, Gdk, Gio

import cairo
import xcffib as xcb
import xcffib.xproto as xproto

import asyncio
import os
import struct
import time

# locals
import battery
import bspwm

class Win(Gtk.Window):
    def __init__(self, show=True, **kargs):
        Gtk.Window.__init__(self, **kargs)

        # enable true transparency
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual != None and screen.is_composited():
            self.set_visual(visual)

        # be able to draw stuff ourselves
        self.set_app_paintable(True)
        # self.connect('draw', self.area_draw)

        if show:
            self.show_all()

    def screen_geom(self):
        # get screen size
        screen = self.get_screen()
        monitor = screen.get_monitor_at_window(screen.get_active_window())
        return screen.get_monitor_geometry(monitor)

    def property_change(self, prop, prop_type, form, mode, data):
        # Gobject has no API to set properties (strangely), so we have to use xcb instead
        conn = xcb.connect()
        def get_atom(atom):
            ia = conn.core.InternAtom(False, len(atom), atom)
            return ia.reply().atom

        conn.core.ChangePropertyChecked(int(mode), self.get_window().get_xid(), get_atom(prop), get_atom(prop_type),
                form, int(len(data) / form * 8), data).check()

class Dock(Win):
    def __init__(self, **kwargs):
        Win.__init__(self, show=False, **kwargs)

        # make it a dock
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_decorated(False)
        # self.set_resizable(False)

        # set size
        geom = self.screen_geom()
        self.move(0, 0)
        self.resize(30, geom.height)
        # self.set_default_size(30, 500)
        # self.set_size_request(30, 500)

        # win_geom = Gdk.Geometry()
        # win_geom.max_width = 30
        # win_geom.max_height = geom.height
        # self.set_geometry_hints(self, win_geom, Gdk.WindowHints.MAX_SIZE)

        # required for property_change
        self.show_all()

        # left, right, top, bottom, left_start_y, left_end_y, right_start_y, right_end_y, top_start_x, top_end_x, bottom_start_x, bottom_end_x
        strut = [0] * 12
        strut[0] = 30
        strut[5] = geom.height
        self.property_change('_NET_WM_STRUT_PARTIAL', 'CARDINAL', 32, Gdk.PropMode.REPLACE, struct.pack('I' * 12, *strut))
        self.property_change('_NET_WM_STRUT', 'CARDINAL', 32, Gdk.PropMode.REPLACE, struct.pack('I' * 4, *strut[0:4]))

class Clock(Gtk.Label):
    def __init__(self, fmt):
        Gtk.Label.__init__(self)
        self.time_fmt = fmt
        self.get_style_context().add_class("clock")

        async def loop():
            while True:
                self.update_time()
                await asyncio.sleep(1)

        asyncio.ensure_future(loop())

    def update_time(self):
        self.set_markup(time.strftime(self.time_fmt))
        self.set_tooltip_text(time.strftime('%c'))

def PowerButton():
    menu = Gtk.Menu()
    for l,e in [
                ("shutdown", lambda _: os.system("systemctl poweroff")),
                ("reboot", lambda _: os.system("systemctl reboot")),
                ("logout", lambda _: os.system("systemctl --user stop x11@{}.target".format(os.getenv("DISPLAY")))),
                (None, None),
                ("hibernate", lambda _: os.system("systemctl hibernate")),
                ("suspend", lambda _: os.system("systemctl suspend")),
                ("hybrid sleep", lambda _: os.system("systemctl hybrid-sleep")),
                ]:
        if l is None:
            menu.append(Gtk.SeparatorMenuItem())
            continue
        mi = Gtk.MenuItem(l)
        mi.connect("activate", e)
        menu.append(mi)
    menu.show_all()

    button = Gtk.Button(name="power-button", relief=Gtk.ReliefStyle.NONE)
    button.add(Gtk.Label(label="⏻"))
    button.connect('clicked', lambda _: menu.popup_at_pointer())

    return button

def EBox(widget, *args, **kwargs):
    event_box = Gtk.EventBox(*args, **kwargs);
    event_box.add(widget)
    return event_box

def init():
    win = Dock()

    top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    mid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
    bot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.END)
    bigbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    bigbox.set_homogeneous(True)

    bigbox.add(EBox(top, name="topbox"))
    bigbox.add(EBox(mid, name="midbox"))
    bigbox.add(EBox(bot, name="botbox"))
    win.add(bigbox)

    mid.add(bspwm.DesktopView())

    bot.add(Clock('%I\n%M\n%S'))
    bot.add(battery.Battery())
    bot.add(PowerButton())

    async def tray():
        await asyncio.sleep(0.2)
        await asyncio.create_subprocess_exec("stalonetray", "-c", "/dev/null",
                "--vertical", "--slot-size", "30", "--window-strut", "left",
                "--transparent", "--grow-gravity", "N", "--sticky")

    asyncio.ensure_future(tray())

    win.show_all()
    win.connect('delete-event', lambda *args: asyncio.get_event_loop().stop())

    return win
