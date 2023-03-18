# **NMSSGE**

No Man's Sky SaveGame Editor (nmssge) can load and save Hello Games savefiles (.hg) and plain json.
For *easy* editing the file will be displayed in a tree struct on the left side and human readable json on the right side.

---

# Usage

## gui

with `Open`/`Save` buttons you can open and save .hg and .json files.
on the left side you can browse the json tree and select specific nodes to display.
on the right side you can view and edit the json data.

> clicking on the `root` node may hang nmssge for several minutes in order to render the json text.

Alt+O and Alt+S are shortcuts for `Open` and `Save`.
Ctrl+Q and ESC close the window.

## commandline

`nmssge.py {file}`
The only supported parameter is `{file}`, which allows you to load a file on program startup.

---

# Requirements

- `pyside6` - QT6 gui bindings
- `python-lz4` - read/write compressed savefiles
