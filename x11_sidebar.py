"""Dock a GTK4 window to the right edge as a full-height sidebar (X11 / XWayland).

GNOME Wayland does not allow clients to set absolute window positions. Running
under GDK_BACKEND=x11 (XWayland) lets us pin, size, and raise a real edge panel.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class Rect:
    x: int
    y: int
    width: int
    height: int


def is_x11_display(display) -> bool:
    try:
        from gi.repository import GdkX11

        return isinstance(display, GdkX11.X11Display)
    except Exception:
        name = display.get_name() if display is not None else ""
        return bool(name) and not str(name).startswith("wayland")


def monitor_geometry(window) -> Rect | None:
    display = window.get_display()
    if display is None:
        return None
    surface = window.get_surface()
    monitor = None
    if surface is not None:
        try:
            monitor = display.get_monitor_at_surface(surface)
        except Exception:
            monitor = None
    if monitor is None:
        monitors = display.get_monitors()
        if monitors.get_n_items() == 0:
            return None
        monitor = monitors.get_item(0)
    geo = monitor.get_geometry()
    return Rect(geo.x, geo.y, geo.width, geo.height)


def _xlib():
    lib = ctypes.util.find_library("X11")
    if not lib:
        return None
    xlib = ctypes.CDLL(lib)
    xlib.XOpenDisplay.restype = ctypes.c_void_p
    xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    xlib.XDefaultRootWindow.restype = ctypes.c_ulong
    xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    xlib.XInternAtom.restype = ctypes.c_ulong
    xlib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    xlib.XChangeProperty.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    xlib.XMoveResizeWindow.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.c_uint,
    ]
    xlib.XRaiseWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    xlib.XFlush.argtypes = [ctypes.c_void_p]
    xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xlib.XSendEvent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_long,
        ctypes.c_void_p,
    ]
    xlib.XMapRaised.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    return xlib


# X11 constants
PropModeReplace = 0
XA_ATOM = 4
XA_CARDINAL = 6
SubstructureNotifyMask = 1 << 19
SubstructureRedirectMask = 1 << 20


class XEvent(ctypes.Structure):
    _fields_ = [("data", ctypes.c_long * 24)]


class XClientMessageEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("message_type", ctypes.c_ulong),
        ("format", ctypes.c_int),
        ("data", ctypes.c_long * 5),
    ]


def _window_xid(window) -> int | None:
    surface = window.get_surface()
    if surface is None:
        return None
    try:
        from gi.repository import GdkX11

        if isinstance(surface, GdkX11.X11Surface):
            return int(surface.get_xid())
    except Exception:
        pass
    return None


def apply_sidebar_hints(
    window,
    *,
    width: int = 420,
    edge: str = "right",
    panel_top: int = 0,
    panel_bottom: int = 0,
    always_on_top: bool = True,
    skip_taskbar: bool = True,
    reserve_strut: bool = False,
    geometry_only: bool = False,
) -> bool:
    """Pin window to an edge, full work-area height. Returns True if applied.

    geometry_only=True skips EWMH type/state updates (use while dragging resize).
    """
    geo = monitor_geometry(window)
    if geo is None:
        return False

    # Leave room for GNOME top bar / dock if present (geometry is full monitor).
    top = panel_top if panel_top else 0
    bottom = panel_bottom if panel_bottom else 0

    height = max(200, geo.height - top - bottom)
    y = geo.y + top
    w = max(280, min(width, geo.width - 40))
    if edge == "left":
        x = geo.x
    else:
        x = geo.x + geo.width - w

    # Only hint a minimum width. Never request full height as a min size —
    # that fights the WM and lets content push the window past the monitor
    # during live resize (composer falls "below the fold").
    window.set_size_request(280, 200)
    window.set_default_size(w, height)

    xid = _window_xid(window)
    if xid is None:
        return False

    xlib = _xlib()
    if xlib is None:
        return False

    dpy = xlib.XOpenDisplay(None)
    if not dpy:
        return False

    try:
        root = xlib.XDefaultRootWindow(dpy)

        def atom(name: str) -> int:
            return xlib.XInternAtom(dpy, name.encode(), 0)

        def set_cardinal(prop: str, values: list[int]) -> None:
            arr = (ctypes.c_ulong * len(values))(*[ctypes.c_ulong(v) for v in values])
            xlib.XChangeProperty(
                dpy,
                xid,
                atom(prop),
                XA_CARDINAL,
                32,
                PropModeReplace,
                ctypes.cast(arr, ctypes.c_void_p),
                len(values),
            )

        def set_atoms(prop: str, names: list[str]) -> None:
            atoms = (ctypes.c_ulong * len(names))(*[atom(n) for n in names])
            xlib.XChangeProperty(
                dpy,
                xid,
                atom(prop),
                XA_ATOM,
                32,
                PropModeReplace,
                ctypes.cast(atoms, ctypes.c_void_p),
                len(names),
            )

        if not geometry_only:
            # Utility / dock-like: not a normal floating app window
            set_atoms("_NET_WM_WINDOW_TYPE", ["_NET_WM_WINDOW_TYPE_UTILITY"])

            # EWMH state
            states: list[str] = []
            if always_on_top:
                states.append("_NET_WM_STATE_ABOVE")
            if skip_taskbar:
                states.append("_NET_WM_STATE_SKIP_TASKBAR")
                states.append("_NET_WM_STATE_SKIP_PAGER")
            if states:
                set_atoms("_NET_WM_STATE", states)
                # Also send client message so the WM applies live
                for st in states:
                    _send_state(
                        xlib, dpy, root, xid, atom("_NET_WM_STATE"), atom(st), 1
                    )

            if reserve_strut:
                # left, right, top, bottom, then partial start/end for each
                if edge == "right":
                    set_cardinal(
                        "_NET_WM_STRUT_PARTIAL",
                        [
                            0,
                            w,
                            0,
                            0,
                            0,
                            0,
                            y,
                            y + height - 1,
                            0,
                            0,
                            0,
                            0,
                        ],
                    )
                    set_cardinal("_NET_WM_STRUT", [0, w, 0, 0])
                else:
                    set_cardinal(
                        "_NET_WM_STRUT_PARTIAL",
                        [
                            w,
                            0,
                            0,
                            0,
                            y,
                            y + height - 1,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                    )
                    set_cardinal("_NET_WM_STRUT", [w, 0, 0, 0])

        # Authoritative geometry: always clamp to the monitor work area.
        xlib.XMoveResizeWindow(dpy, xid, int(x), int(y), int(w), int(height))
        if not geometry_only:
            xlib.XRaiseWindow(dpy, xid)
        xlib.XFlush(dpy)
        return True
    finally:
        xlib.XCloseDisplay(dpy)


def _send_state(xlib, dpy, root, xid, state_atom, prop_atom, action: int) -> None:
    """action: 0 remove, 1 add, 2 toggle."""
    ClientMessage = 33
    ev = XClientMessageEvent()
    ev.type = ClientMessage
    ev.serial = 0
    ev.send_event = 1
    ev.display = dpy
    ev.window = xid
    ev.message_type = state_atom
    ev.format = 32
    ev.data[0] = action
    ev.data[1] = prop_atom
    ev.data[2] = 0
    ev.data[3] = 1  # source indication: application
    ev.data[4] = 0
    mask = SubstructureNotifyMask | SubstructureRedirectMask
    xlib.XSendEvent(dpy, root, 0, mask, ctypes.byref(ev))


def backend_note() -> str:
    backend = os.environ.get("GDK_BACKEND", "")
    session = os.environ.get("XDG_SESSION_TYPE", "")
    if session == "wayland" and backend != "x11":
        return (
            "Running on pure Wayland: GNOME will not let apps pin to the screen edge. "
            "Restart with GDK_BACKEND=x11 (the run.sh script does this) for a real sidebar."
        )
    if backend == "x11" or session == "x11":
        return "X11 sidebar docking enabled."
    return ""
