# -*- coding: utf-8 -*-
#
# Copyright (C) 2011 Pedro Algarvio <pedro@algarvio.me>
#
# This file is part of Deluge and is licensed under GNU General Public License 3.0, or later, with
# the additional special exception to link portions of this program with the OpenSSL library.
# See LICENSE for more details.
#

from __future__ import division

from math import pi

from cairo import FORMAT_ARGB32, Context, ImageSurface
from gtk import DrawingArea, ProgressBar
from gtk.gdk import colormap_get_system
from pango import SCALE, WEIGHT_BOLD
from pangocairo import CairoContext

from deluge.configmanager import ConfigManager

COLOR_STATES = ['missing', 'waiting', 'downloading', 'completed']


class PiecesBar(DrawingArea):
    # Draw in response to an expose-event
    __gsignals__ = {'expose-event': 'override'}

    def __init__(self):
        DrawingArea.__init__(self)
        # Get progress bar styles, in order to keep font consistency
        pb = ProgressBar()
        pb_style = pb.get_style()
        self.text_font = pb_style.font_desc
        self.text_font.set_weight(WEIGHT_BOLD)
        # Done with the ProgressBar styles, don't keep refs of it
        del pb, pb_style

        self.set_size_request(-1, 25)
        self.gtkui_config = ConfigManager('gtkui.conf')

        self.width = self.prev_width = 0
        self.height = self.prev_height = 0
        self.pieces = self.prev_pieces = ()
        self.num_pieces = None
        self.text = self.prev_text = ''
        self.fraction = self.prev_fraction = 0
        self.progress_overlay = self.text_overlay = self.pieces_overlay = None
        self.cr = None

        self.connect('size-allocate', self.do_size_allocate_event)
        self.set_colormap(colormap_get_system())
        self.show()

    def do_size_allocate_event(self, widget, size):
        self.prev_width = self.width
        self.width = size.width
        self.prev_height = self.height
        self.height = size.height

    # Handle the expose-event by drawing
    def do_expose_event(self, event):
        # Create cairo context
        self.cr = self.window.cairo_create()
        self.cr.set_line_width(max(self.cr.device_to_user_distance(0.5, 0.5)))

        # Restrict Cairo to the exposed area; avoid extra work
        self.roundcorners_clipping()

        self.draw_pieces()
        self.draw_progress_overlay()
        self.write_text()
        self.roundcorners_border()

        # Drawn once, update width, height
        if self.resized():
            self.prev_width = self.width
            self.prev_height = self.height

    def roundcorners_clipping(self):
        self.create_roundcorners_subpath(self.cr, 0, 0, self.width, self.height)
        self.cr.clip()

    def roundcorners_border(self):
        self.create_roundcorners_subpath(self.cr, 0.5, 0.5, self.width - 1, self.height - 1)
        self.cr.set_source_rgba(0, 0, 0, 0.9)
        self.cr.stroke()

    @staticmethod
    def create_roundcorners_subpath(ctx, x, y, width, height):
        aspect = 1.0
        corner_radius = height / 10
        radius = corner_radius / aspect
        degrees = pi / 180
        ctx.new_sub_path()
        ctx.arc(x + width - radius, y + radius, radius, -90 * degrees, 0 * degrees)
        ctx.arc(x + width - radius, y + height - radius, radius, 0 * degrees, 90 * degrees)
        ctx.arc(x + radius, y + height - radius, radius, 90 * degrees, 180 * degrees)
        ctx.arc(x + radius, y + radius, radius, 180 * degrees, 270 * degrees)
        ctx.close_path()
        return ctx

    def draw_pieces(self):
        if not self.num_pieces:
            # Nothing to draw.
            return

        if self.resized() or self.pieces != self.prev_pieces or self.pieces_overlay is None:
            # Need to recreate the cache drawing
            self.pieces_overlay = ImageSurface(FORMAT_ARGB32, self.width, self.height)
            ctx = Context(self.pieces_overlay)

            if self.pieces:
                pieces = self.pieces
            elif self.num_pieces:
                # Completed torrents do not send any pieces so create list using 'completed' state.
                pieces = [COLOR_STATES.index('completed')] * self.num_pieces
            start_pos = 0
            piece_width = self.width / len(pieces)
            pieces_colors = [[color / 65535 for color in self.gtkui_config['pieces_color_%s' % state]]
                             for state in COLOR_STATES]
            for state in pieces:
                ctx.set_source_rgb(*pieces_colors[state])
                ctx.rectangle(start_pos, 0, piece_width, self.height)
                ctx.fill()
                start_pos += piece_width

        self.cr.set_source_surface(self.pieces_overlay)
        self.cr.paint()

    def draw_progress_overlay(self):
        if not self.text:
            # Nothing useful to draw, return now!
            return

        if self.resized() or self.fraction != self.prev_fraction or self.progress_overlay is None:
            # Need to recreate the cache drawing
            self.progress_overlay = ImageSurface(FORMAT_ARGB32, self.width, self.height)
            ctx = Context(self.progress_overlay)
            ctx.set_source_rgba(0.1, 0.1, 0.1, 0.3)  # Transparent
            ctx.rectangle(0, 0, self.width * self.fraction, self.height)
            ctx.fill()
        self.cr.set_source_surface(self.progress_overlay)
        self.cr.paint()

    def write_text(self):
        if not self.text:
            # Nothing useful to draw, return now!
            return

        if self.resized() or self.text != self.prev_text or self.text_overlay is None:
            # Need to recreate the cache drawing
            self.text_overlay = ImageSurface(FORMAT_ARGB32, self.width, self.height)
            ctx = Context(self.text_overlay)
            pg = CairoContext(ctx)
            pl = pg.create_layout()
            pl.set_font_description(self.text_font)
            pl.set_width(-1)  # No text wrapping
            pl.set_text(self.text)
            plsize = pl.get_size()
            text_width = plsize[0] // SCALE
            text_height = plsize[1] // SCALE
            area_width_without_text = self.width - text_width
            area_height_without_text = self.height - text_height
            ctx.move_to(area_width_without_text // 2, area_height_without_text // 2)
            ctx.set_source_rgb(1, 1, 1)
            pg.update_layout(pl)
            pg.show_layout(pl)
        self.cr.set_source_surface(self.text_overlay)
        self.cr.paint()

    def resized(self):
        return self.prev_width != self.width or self.prev_height != self.height

    def set_fraction(self, fraction):
        self.prev_fraction = self.fraction
        self.fraction = fraction

    def get_fraction(self):
        return self.fraction

    def get_text(self):
        return self.text

    def set_text(self, text):
        self.prev_text = self.text
        self.text = text

    def set_pieces(self, pieces, num_pieces):
        self.prev_pieces = self.pieces
        self.pieces = pieces
        self.num_pieces = num_pieces

    def get_pieces(self):
        return self.pieces

    def clear(self):
        self.pieces = self.prev_pieces = ()
        self.num_pieces = None
        self.text = self.prev_text = ''
        self.fraction = self.prev_fraction = 0
        self.progress_overlay = self.text_overlay = self.pieces_overlay = None
        self.cr = None
        self.update()

    def update(self):
        self.queue_draw()
