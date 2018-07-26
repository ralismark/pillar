#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
gi.require_foreign('cairo')
from gi.repository import Gtk, Gdk, Gio, GLib

import asyncio
import gbulb
import gbulb.gtk

# Use GTK main loop
asyncio.set_event_loop_policy(gbulb.gtk.GtkEventLoopPolicy())

import signal
import sys

import bar

css_provider = None
def load_css():
    global css_provider
    if css_provider is not None:
        Gtk.StyleContext.remove_provider_for_screen(Gdk.Screen.get_default(),
                css_provider)

    css_provider = Gtk.CssProvider()
    css_provider.load_from_path('style.css')
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    print("Loaded CSS")

load_css()
asyncio.get_event_loop().add_signal_handler(signal.SIGUSR1, lambda: load_css())

async def stdin_generator():
    rd = asyncio.StreamReader()
    rd_proto = asyncio.StreamReaderProtocol(rd)
    trans,proto = await asyncio.get_event_loop().connect_read_pipe(lambda: rd_proto, sys.stdin)

    while True:
        line = await rd.readline()
        if not line:
            break
        yield line

async def input_handler():
    async for line in stdin_generator():
        if line == b'c\n':
            try:
                load_css()
            except GLib.GError as e:
                print(e)

asyncio.ensure_future(input_handler())

keep = bar.init()

# All this stuff for a graceful shutdown
try:
    asyncio.get_event_loop().run_forever()
except KeyboardInterrupt:
    pass
except:
    raise
finally:
    for task in asyncio.Task.all_tasks():
        task.cancel()

    pending = asyncio.Task.all_tasks()
    try:
        asyncio.get_event_loop().run_until_complete(asyncio.gather(*pending))
    except asyncio.CancelledError:
        pass

