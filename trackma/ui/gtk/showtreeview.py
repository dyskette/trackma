# This file is part of Trackma.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from gi.repository import Gtk, Gdk, Gio, GLib, Pango, GObject, Graphene
from trackma import utils
from trackma.ui.gtk import TrackmaColumns


class ShowListStore(Gtk.ListStore):
    __cols = (
        ('id', int),
        ('title', str),
        ('stat', int),
        ('score', float),
        ('stat-text', str),
        ('score-text', str),
        ('total-eps', int),
        ('subvalue', int),
        ('avail-eps', GObject.TYPE_PYOBJECT),
        ('color', str),
        ('stat-pcent', int),
        ('start', str),
        ('end', str),
        ('my-start', str),
        ('my-end', str),
        ('my-status', str),
        ('status', int),
    )

    def __init__(self, decimals=0, colors=dict()):
        super().__init__(*self.__class__.__columns__())
        self.colors = colors
        self.decimals = decimals
        self.set_sort_column_id(1, Gtk.SortType.ASCENDING)

    @staticmethod
    def format_date(date):
        if date:
            try:
                return date.strftime('%Y-%m-%d')
            except ValueError:
                return '?'
        else:
            return '-'

    @classmethod
    def __columns__(cls):
        return (k for i, k in cls.__cols)

    @classmethod
    def column(cls, key):
        try:
            return cls.__cols.index(next(i for i in cls.__cols if i[0] == key))
        except ValueError:
            return None

    def _get_color(self, show, eps):
        if show.get('queued'):
            return self.colors['is_queued']
        elif eps and max(eps) > show['my_progress']:
            return self.colors['new_episode']
        elif show['status'] == utils.Status.AIRING:
            return self.colors['is_airing']
        elif show['status'] == utils.Status.NOTYET:
            return self.colors['not_aired']
        else:
            return None

    def append(self, show, altname=None, eps=None):
        episodes_str = "{} / {}".format(show['my_progress'],
                                        show['total'] or '?')
        if show['total'] and show['my_progress'] <= show['total']:
            progress = (float(show['my_progress']) / show['total']) * 100
        else:
            progress = 0

        title_str = show['title']
        if altname:
            title_str += " [%s]" % altname

        score_str = "%0.*f" % (self.decimals, show['my_score'])
        aired_eps = utils.estimate_aired_episodes(show)

        if eps:
            available_eps = eps.keys()
        else:
            available_eps = []

        start_date = self.format_date(show['start_date'])
        end_date = self.format_date(show['end_date'])
        my_start_date = self.format_date(show['my_start_date'])
        my_finish_date = self.format_date(show['my_finish_date'])

        row = [show['id'],
               title_str,
               show['my_progress'],
               show['my_score'],
               episodes_str,
               score_str,
               show['total'],
               aired_eps,
               available_eps,
               self._get_color(show, available_eps),
               progress,
               start_date,
               end_date,
               my_start_date,
               my_finish_date,
               show['my_status'],
               show['status']
               ]
        super().append(row)

    def update_or_append(self, show):
        for row in self:
            if int(row[0]) == show['id']:
                self.update(show, row)
                return
        self.append(show)

    def update(self, show, row=None):
        if not row:
            for row in self:
                if int(row[0]) == show['id']:
                    break
        if row and int(row[0]) == show['id']:
            episodes_str = "{} / {}".format(show['my_progress'],
                                            show['total'] or '?')
            row[2] = show['my_progress']
            row[4] = episodes_str

            score_str = "%0.*f" % (self.decimals, show['my_score'])

            row[3] = show['my_score']
            row[5] = score_str
            row[9] = self._get_color(show, row[8])
            row[15] = show['my_status']
        return

        # print("Warning: Show ID not found in ShowView (%d)" % show['id'])

    def update_title(self, show, altname=None):
        for row in self:
            if int(row[0]) == show['id']:
                if altname:
                    title_str = "%s [%s]" % (show['title'], altname)
                else:
                    title_str = show['title']

                row[1] = title_str
                return

    def remove(self, show=None, id=None):
        for row in self:
            if int(row[0]) == (show['id'] if show is not None else id):
                Gtk.ListStore.remove(self, row.iter)
                return

    def playing(self, show, is_playing):
        # Change the color if the show is currently playing
        for row in self:
            if int(row[0]) == show['id']:
                if is_playing:
                    row[9] = self.colors['is_playing']
                else:
                    row[9] = self._get_color(show, row[8])
                return


class ShowListFilter(Gtk.TreeModelFilter):
    def __init__(self, status=None, *args, **kwargs):
        super().__init__(
            *args,
            **kwargs
        )
        self.set_visible_func(self.status_filter)
        self._status = status

    def status_filter(self, model, iter, data):
        return self._status is None or model[iter][15] == self._status

    def get_value(self, obj, key='id'):
        try:
            if type(obj) == Gtk.TreePath:
                obj = self.get_iter(obj)
            if isinstance(key, (str,)):
                key = self.props.child_model.column(key)
            return super().get_value(obj, key)
        except:
            return None


class ShowTreeView(Gtk.TreeView):
    __gtype_name__ = 'ShowTreeView'

    __gsignals__ = {'column-toggled': (GObject.SignalFlags.RUN_LAST,
                                       GObject.TYPE_PYOBJECT, (GObject.TYPE_STRING, GObject.TYPE_BOOLEAN))}

    def __init__(self, window, status, colors, visible_columns, progress_style=1):
        Gtk.TreeView.__init__(self)

        self._window = window
        self.colors = colors
        self.visible_columns = visible_columns
        self.progress_style = progress_style

        self.set_enable_search(True)
        self.set_search_column(1)
        self.set_property('has-tooltip', True)
        self.connect('query-tooltip', self.show_tooltip)

        menu, action_group, action_group_name = self._create_header_action_menu(status)
        self.insert_action_group(action_group_name, action_group)

        for column in TrackmaColumns().AVAILABLE_COLUMNS:
            tree_column = self._create_treeview_column(column)
            self._add_button_header_popover(tree_column, menu)
            self.append_column(tree_column)

    def _create_header_action_menu(self, status):
        menu = Gio.Menu()
        action_group = Gio.SimpleActionGroup()
        action_group_name = 'columns'

        for column in TrackmaColumns().AVAILABLE_COLUMNS:
            is_active = column.description in self.visible_columns
            status_name = status if status is not None else 'all'
            action_name = 'view-column-{}-{}'.format(status_name, column.name)

            action = Gio.SimpleAction.new_stateful(
                action_name,
                None,
                GLib.Variant.new_boolean(is_active))

            action.connect('change-state', self._header_menu_item, column.description)
            action_group.add_action(action)

            menu.append(column.description, '{}.{}'.format(action_group_name, action_name))

        return (menu, action_group, action_group_name)

    def _create_treeview_column(self, column):
        tree_column = Gtk.TreeViewColumn(column.description)
        tree_column.name = column.name
        tree_column.set_sort_column_id(column.order)

        if column.description not in self.visible_columns:
            tree_column.set_visible(False)

        if column == TrackmaColumns().TITLE:
            self._set_title_column(tree_column)
        elif column == TrackmaColumns().PROGRESS:
            self._set_progress_column(tree_column)
        elif column == TrackmaColumns().STAT_PERCENTAGE:
            self._set_percentage_column(tree_column)
        elif column == TrackmaColumns().SCORE:
            self._set_score_column(tree_column)
        elif column == TrackmaColumns().START:
            self._set_start_column(tree_column)
        elif column == TrackmaColumns().END:
            self._set_end_column(tree_column)
        elif column == TrackmaColumns().MY_START:
            self._set_my_start_column(tree_column)
        elif column == TrackmaColumns().MY_END:
            self._set_my_end_column(tree_column)

        return tree_column

    def _add_button_header_popover(self, tree_column, menu):
        header_button = tree_column.get_button()

        gesture_click_controller = Gtk.GestureClick()
        gesture_click_controller.set_button(Gdk.BUTTON_SECONDARY)
        gesture_click_controller.connect('pressed', self._header_button_press)
        header_button.add_controller(gesture_click_controller)

        popover = Gtk.PopoverMenu()
        popover.set_menu_model(menu)
        popover.set_parent(header_button)

        header_button.popover_menu = popover

    def _set_title_column(self, title_column):
        renderer = Gtk.CellRendererText()
        title_column.pack_start(renderer, False)
        title_column.set_resizable(True)
        title_column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        title_column.set_expand(True)
        title_column.add_attribute(renderer, 'text', TrackmaColumns().TITLE)
        # Using foreground-gdk does not work, possibly due to the timing of it being set
        title_column.add_attribute(renderer, 'foreground', TrackmaColumns().COLOR)
        renderer.set_property('ellipsize', Pango.EllipsizeMode.END)

    def _set_progress_column(self, progress_column):
        renderer = Gtk.CellRendererText()
        progress_column.pack_start(renderer, False)
        progress_column.add_attribute(renderer, 'text', 4)
        progress_column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        progress_column.set_expand(False)

    def _set_percentage_column(self, percentage_column):
        renderer = None
        if self.progress_style == 0:
            renderer = Gtk.CellRendererProgress()
            percentage_column.pack_start(renderer, False)
            percentage_column.add_attribute(renderer, 'value', 10)
        else:
            renderer = ProgressCellRenderer(self.colors)
            percentage_column.pack_start(renderer, False)
            percentage_column.add_attribute(renderer, 'value', 2)
            percentage_column.add_attribute(renderer, 'total', 6)
            percentage_column.add_attribute(renderer, 'subvalue', 7)
            percentage_column.add_attribute(renderer, 'eps', 8)
        renderer.set_fixed_size(100, -1)

    def _set_score_column(self, score_column):
        renderer = Gtk.CellRendererText()
        score_column.pack_start(renderer, False)
        score_column.add_attribute(renderer, 'text', 5)

    def _set_start_column(self, start_column):
        renderer = Gtk.CellRendererText()
        start_column.pack_start(renderer, False)
        start_column.add_attribute(renderer, 'text', 11)

    def _set_end_column(self, end_column):
        renderer = Gtk.CellRendererText()
        end_column.pack_start(renderer, False)
        end_column.add_attribute(renderer, 'text', 12)

    def _set_my_start_column(self, my_start_column):
        renderer = Gtk.CellRendererText()
        my_start_column.pack_start(renderer, False)
        my_start_column.add_attribute(renderer, 'text', 13)

    def _set_my_end_column(self, my_end_column):
        renderer = Gtk.CellRendererText()
        my_end_column.pack_start(renderer, False)
        my_end_column.add_attribute(renderer, 'text', 14)

    def _header_button_press(self, controller, n_press, x, y):
        header_button = controller.get_widget()
        self._show_popover(header_button.popover_menu, x, y)

    def _show_popover(self, popover, x, y):
        rect = Gdk.Rectangle()
        rect.x = x
        rect.y = y
        popover.set_pointing_to(rect)
        popover.popup()
        return Gdk.EVENT_STOP

    @property
    def filter(self):
        return self.props.model.props.model

    def show_tooltip(self, view, x, y, keyboard_mode, tooltip):
        has_path, model, path, _iter = view.get_tooltip_context(
            x, y, keyboard_mode)

        if has_path:
            _, col, _, _ = view.get_path_at_pos(x, y)
            renderer = next(k for i, k in enumerate(col.get_cells()) if i == 0)
            lines = []

            if col.name == TrackmaColumns().STAT_PERCENTAGE.name:
                lines.append("Watched: %d" %
                             view.filter.get_value(path, 'stat'))
                if view.filter.get_value(path, 'subvalue') and not view.filter.get_value(path, 'status') == utils.Status.NOTYET:
                    lines.append("Aired%s: %d" % (' (estimated)' if view.filter.get_value(
                        path, 'status') == utils.Status.AIRING else '', view.filter.get_value(path, 'subvalue')))

                if len(view.filter.get_value(path, 'avail-eps')) > 0:
                    lines.append("Available: %d" %
                                 max(view.filter.get_value(path, 'avail-eps')))

                lines.append("Total: %s" %
                             (view.filter.get_value(path, 'total-eps') or '?'))

            if len(lines):
                tooltip.set_markup('\n'.join(lines))
                self.set_tooltip_cell(tooltip, path, col, renderer)
                return True

        return False

    def _header_menu_item(self, action, new_visible_state, column_name):
        action.set_state(new_visible_state)
        self.emit('column-toggled', column_name, new_visible_state)

    def select(self, show):
        """Select specified row or first if not found"""
        for row in self.get_model():
            if int(row[0]) == show['id']:
                selection = self.get_selection()
                selection.select_iter(row.iter)
                return

        self.get_selection().select_path(Gtk.TreePath.new_first())


class ProgressCellRenderer(Gtk.CellRenderer):
    value = 0
    subvalue = 0
    _total = 0
    eps = []
    _subheight = 5

    __gproperties__ = {
        "value": (GObject.TYPE_INT, "Value",
                  "Progress percentage", 0, 100000, 0,
                  GObject.ParamFlags.READWRITE),

        "subvalue": (GObject.TYPE_INT, "Subvalue",
                     "Sub percentage", 0, 100000, 0,
                     GObject.ParamFlags.READWRITE),

        "total": (GObject.TYPE_INT, "Total",
                  "Total percentage", 0, 100000, 0,
                  GObject.ParamFlags.READWRITE),

        "eps": (GObject.TYPE_PYOBJECT, "Episodes",
                "Available episodes",
                GObject.ParamFlags.READWRITE),
    }

    def __init__(self, colors):
        Gtk.CellRenderer.__init__(self)
        self.colors = colors
        self.value = self.get_property("value")
        self.subvalue = self.get_property("subvalue")
        self.total = self.get_property("total")
        self.eps = self.get_property("eps")

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    @property
    def total(self):
        return self._total if self._total > 0 else len(self.eps)

    @total.setter
    def total(self, value):
        self._total = value

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_snapshot(self, snapshot, widget, background_area, cell_area, flags):
        (x, y, w, h) = self.do_get_size(widget, cell_area)

        snapshot.append_color(
            self.__get_color(self.colors['progress_bg']),
            Graphene.Rect.alloc().init(x, y, w, h))

        if not self.total:
            return

        if self.subvalue:
            if self.subvalue > self.total:
                mid = w
            else:
                mid = int(w / float(self.total) * self.subvalue)

            snapshot.append_color(
                self.__get_color(self.colors['progress_sub_bg']),
                Graphene.Rect.alloc().init(x, y+h-self._subheight, mid, h-(h-self._subheight)))

        if self.value:
            if self.value >= self.total:
                snapshot.append_color(
                    self.__get_color(self.colors['progress_complete']),
                    Graphene.Rect.alloc().init(x, y, w, h))
            else:
                mid = int(w / float(self.total) * self.value)

                snapshot.append_color(
                    self.__get_color(self.colors['progress_fg']),
                    Graphene.Rect.alloc().init(x, y, mid, h))

        if self.eps:
            for episode in self.eps:
                if episode > 0 and episode <= self.total:
                    start = int(w / float(self.total) * (episode - 1))
                    finish = int(w / float(self.total) * episode)

                    snapshot.append_color(
                        self.__get_color(self.colors['progress_sub_fg']),
                        Graphene.Rect.alloc().init(x+start, y+h-self._subheight,
                                      finish-start, h-(h-self._subheight)))

    def do_get_size(self, widget, cell_area):
        if cell_area is None:
            return 0, 0, 0, 0
        x = cell_area.x
        y = cell_area.y
        w = cell_area.width
        h = cell_area.height
        return x, y, w, h

    @staticmethod
    def __get_color(color_string):
        color = Gdk.RGBA()
        color.parse(color_string)
        return color

