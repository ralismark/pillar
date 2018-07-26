#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
gi.require_foreign('cairo')
from gi.repository import Gtk, Gdk

import asyncio
import os
import socket

from xcffib import ffi, lib

def parse_display(name=ffi.NULL):
    if type(name) == str:
        name = name.encode()

    host = ffi.new('char**')
    display = ffi.new('int*')
    screen = ffi.new('int*')

    if lib.xcb_parse_display(name, host, display, screen):
        try:
            return (ffi.string(host[0]).decode(), display[0], screen[0])
        finally:
            lib.free(host[0])

    return None

def get_socket_path():
    path = os.environ.get('BSPWM_SOCKET')
    if path:
        return path

    display = parse_display()
    if display:
        return '/tmp/bspwm{}_{}_{}-socket'.format(*display)

    # Some better default, or throw?
    raise FileNotFoundError('Bspwm socket path not found', 'No $BSPWM_SOCKET and xcb_parse_display failed')

def create_socket():
    sock = socket.socket(family=socket.AF_UNIX)
    sock.connect(get_socket_path())
    return sock

def make_payload(cmd):
    return b'\0'.join(cmd.encode().split(b' ')) + b'\0'

def run_command(cmd):
    sock = create_socket()
    sock.send(make_payload(cmd))
    return sock

def process_report(rpt):
    out = []
    monitor = None
    for item in rpt[1:].split(':'):
        if item[0] in 'Mm':
            monitor = {
                    'focus': item[0] == 'M',
                    'name': item[1:],
                    'focus_dsk': None,
                    'desktops': [],
                    'layout': None,
                    'state': None,
                    }
            out.append(monitor)
        elif item[0] in 'OoFfUu':
            if item[0] in 'Oo':
                kind = 'occupied'
            elif item[0] in 'Ff':
                kind = 'free'
            elif item[0] in 'Uu':
                kind = 'urgent'

            dsk = {
                'idx': 1 + len(monitor['desktops']),
                'focus': None,
                'kind': kind,
                'name': item[1:],
                }

            if item[0].isupper():
                monitor['focus_dsk'] = dsk
                dsk['focus'] = {
                        'layout': None,
                        'state': None,
                        }

            monitor['desktops'].append(dsk)
        elif item[0] in 'L':
            if item[1] == 'T':
                monitor['focus_dsk']['focus']['layout'] = 'tiling'
            elif item[1] == 'M':
                monitor['focus_dsk']['focus']['layout'] = 'monocle'
        elif item[0] in 'T':
            if item[1] == 'T':
                monitor['focus_dsk']['focus']['state'] = 'tiled'
            elif item[1] == 'P':
                monitor['focus_dsk']['focus']['state'] = 'pseudo_tiled'
            elif item[1] == 'F':
                monitor['focus_dsk']['focus']['state'] = 'floating'
            elif item[1] == '=':
                monitor['focus_dsk']['focus']['state'] = 'fullscreen'
            elif item[1] == '@':
                monitor['focus_dsk']['focus']['state'] = '@'
    # TODO process G
    return out

async def subscribe():
    reader, writer = await asyncio.open_connection(sock=run_command('subscribe report'))
    while True:
        data = await reader.readline()
        yield process_report(data.decode())

class DesktopEntry(Gtk.Button):
    def __init__(self):
        Gtk.EventBox.__init__(self, relief=Gtk.ReliefStyle.NONE)
        self.get_style_context().add_class("desktop-entry")

        self.label = Gtk.Label()
        self.add(self.label)

        self.desktop = None

        self.connect('clicked', self._on_click)

    def _set_desktop(self, dsk):
        if self.desktop == dsk:
            return

        self.desktop = dsk

        ctx = self.get_style_context()

        if dsk['focus'] is not None:
            ctx.add_class('focused')
        else:
            ctx.remove_class('focused')

        if dsk['kind'] == 'urgent':
            ctx.add_class('urgent')
            ctx.add_class('occupied')
        elif dsk['kind'] == 'occupied':
            ctx.remove_class('urgent')
            ctx.add_class('occupied')
        else:
            ctx.remove_class('urgent')
            ctx.remove_class('occupied')

        text = dsk['name']

        if dsk['focus'] is not None:
            text = '–{}–'.format(text)

        self.label.set_text(text)

    def _on_click(self, widget):
        if self.desktop is not None:
            run_command('desktop ^{} --focus'.format(self.desktop['idx']))

class DesktopView(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.get_style_context().add_class("desktops")

        self.decktops = None

        async def updateloop():
            async for r in subscribe():
                self._update(r)

        asyncio.ensure_future(updateloop())

        self.show_all()

    def _update(self, report):
        monitor = report[0]
        desktops = monitor['desktops']

        root = self.get_toplevel()
        if isinstance(root, Gtk.Window):
            root.set_visible(monitor['focus_dsk']['focus']['state'] != 'fullscreen')

        children = self.get_children()

        # Get number of children correct
        if len(children) > len(desktops):
            for child in children[len(desktops):]:
                self.remove(child)
        if len(children) < len(desktops):
            for i in range(len(desktops) - len(children)):
                self.add(DesktopEntry())

        children = self.get_children()

        for child,dsk in zip(children, desktops):
            child._set_desktop(dsk)

        self.show_all()
